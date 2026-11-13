"""Small MCP front door; strict wire requests remain a separate programmatic API."""
from copy import deepcopy
from collections import OrderedDict
from contextvars import ContextVar
from weakref import WeakKeyDictionary
from difflib import SequenceMatcher
import json
import re
import jsonschema
from .analysis import DEFAULT_FILTER
from .model import digest
from .task_packets import PROFILE_CEILINGS
from .tokens import TokenCounter

ALIAS_CONNECTION=ContextVar('geographer_alias_connection',default=None)

def enforce_cap(router,op,result):
    cap=router.max_result_chars
    if not cap or len(json.dumps(result,ensure_ascii=False))<=cap:return result
    out=error(op,ValueError('Result exceeds max_result_chars; request fewer results or a smaller source range'))
    out['error']['code']='BUDGET_TOO_SMALL'
    return out

def call_code_connection(router,op,args,connection):
    with router.catalog.lock:
        sessions=getattr(router,'agent_sessions',None)
        if sessions is None:sessions=router.agent_sessions=WeakKeyDictionary()
        identity=sessions.setdefault(connection,object())
    token=ALIAS_CONNECTION.set(identity)
    try:return call_code(router,op,args)
    finally:ALIAS_CONNECTION.reset(token)


def schemas(single=False):
    string={'type':'string'}
    common={'graph_id':{'type':'string','description':'Prefer the graph label from list_graphs, e.g. librarian-v2.'},'profile':{'enum':list(PROFILE_CEILINGS)},'limit_tokens':{'type':'integer','minimum':256},
            'alias_scope':string,'cursor':string}
    fields={
        'search_entities':({'query':string,'kinds':{'type':'array','items':string},'limit':{'type':'integer','minimum':1,'maximum':50}},['query']),
        'get_entity_content':({'entity_id':string,'start_line':{'type':'integer','minimum':1},'end_line':{'type':'integer','minimum':1}},['entity_id']),
        'get_architecture_context':({'focus_id':string,'radius':{'type':'integer','minimum':0,'maximum':2},'pins':{'type':'array','items':string},
            'qi':{'type':'boolean'},'algorithm':{'enum':['helper_tree_balls_v1','directed-helper-condensation-v1']}},['focus_id']),
        'find_dependants':({'entity_id':string,'max_depth':{'type':'integer','minimum':1,'maximum':32}},['entity_id']),
        'check_architecture':({'scope_id':string,'model_digest':string},[]),
        'find_similar_code':({'entity_id':string,'limit':{'type':'integer','minimum':1,'maximum':50}},['entity_id']),
        'inspect_relationship_witnesses':({'relationship_id':string,'view_id':string},['relationship_id','view_id'])}
    return {op:dict(type='object',properties={**common,**props},required=([] if single else ['graph_id'])+required,
                    additionalProperties=False) for op,(props,required) in fields.items()}


def example(op):
    if op.startswith('paper_'):
        request=({'query':'graph'} if op=='paper_search_documents' else {'concept':'graph'} if op=='paper_find_by_concept' else {'title':'doc:1'})
        return {'graph_id':'<graph_id>','request':request}
    ex={'graph_id':'<graph_id>',**{
        'search_entities':{'query':'clerk'},'get_entity_content':{'entity_id':'<entity_id>'},
        'get_architecture_context':{'focus_id':'<entity_id>'},'find_dependants':{'entity_id':'<entity_id>'},
        'check_architecture':{},'find_similar_code':{'entity_id':'<entity_id>'},
        'inspect_relationship_witnesses':{'relationship_id':'<relationship_id>','view_id':'<view_id>'},
        'compile_task_packet':{'anchors':['entity:<canonical_id>'],'instruction':'Describe ports.'},
        'analyze_cross_graphs':{'graph_ids':['<graph_a>','<graph_b>'],'mode':'clone_candidates'},
        'federated_search':{'graph_ids':['<graph_a>','<graph_b>'],'query':'graph'},
        'list_bridges':{'graph_ids':['<graph_a>','<graph_b>']},'list_graphs':{}}.get(op,{})}
    if op in {'analyze_cross_graphs','federated_search','list_bridges','list_graphs'}:ex.pop('graph_id',None)
    return ex


def error(op,exc):
    field='arguments'
    if isinstance(exc,jsonschema.ValidationError):
        field='.'.join(map(str,exc.absolute_path)) or 'arguments';reason=exc.message
    else:reason=str(exc).split('\n',1)[0]
    ex=getattr(exc,'example',None) or example(op)
    if op=='list_graphs':ex={}
    text=f'{field}: {reason[:140]}. Example: {op}({json.dumps(ex,separators=(",",":"))})'
    out=dict(error=dict(code='INVALID_GRAPH_REQUEST',field=field,message=text[:400],example=ex))
    if op in {'search_entities','get_entity_content'}:out.update(coverage=[],coverage_truncated=False)
    if hasattr(exc,'choices'):out['error']['choices']=exc.choices
    return out


def remember_aliases(router,gid,sid,mapping):
    cache=getattr(router,'agent_aliases',None)
    if cache is None:cache=router.agent_aliases=OrderedDict()
    for alias,canonical in sorted(mapping.items()):
        if not re.fullmatch(r'[nwe][1-9][0-9]*',alias):continue
        key=(ALIAS_CONNECTION.get(),gid,sid,alias);values=cache.setdefault(key,[])
        if canonical not in values:values.append(canonical)
        # Retain ambiguity rather than guessing a previous identity.
        values[:]=sorted(values)[:4];cache.move_to_end(key)
        while len(cache)>256:cache.popitem(last=False)


def remember_search(router,gid,sid,out):
    cache=getattr(router,'agent_recent_search',None)
    if cache is None:cache=router.agent_recent_search=OrderedDict()
    for row in out.get('entities',[]):
        key=(ALIAS_CONNECTION.get(),gid,sid,row['entity_id'])
        cache[key]={k:row[k] for k in ('entity_id','qualified_name','cite_as')}
        cache.move_to_end(key)
        while len(cache)>256:cache.popitem(last=False)


def unknown_entity(router,gid,graph,g,key,value):
    scope=(ALIAS_CONNECTION.get(),gid,graph['snapshot_id'])
    recent=getattr(router,'agent_recent_search',{})
    choices=[v for k,v in reversed(list(recent.items())) if k[:3]==scope]
    def priority(row):
        target=row['entity_id'].removeprefix('entity:');asked=value.removeprefix('entity:')
        prefix=0
        for a,b in zip(target,asked):
            if a!=b:break
            prefix+=1
        similarity=SequenceMatcher(None,value.casefold(),row['qualified_name'].casefold()).ratio()
        return (-prefix,-similarity,row['qualified_name'],row['entity_id'])
    if choices:choices.sort(key=priority)
    else:
        choices=[dict(entity_id=e.entity_id,qualified_name=e.qualified_name,cite_as=graph['label']+'/entity:'+e.entity_id)
                 for e in sorted(g.entities.values(),key=lambda e:(e.qualified_name,e.entity_id))
                 if value in (e.qualified_name,e.qualified_name.rsplit('.',1)[-1])]
    bounded=[]
    for row in choices:
        if len(json.dumps(bounded+[row],ensure_ascii=False))<=400:bounded.append(row)
        if len(bounded)==3:break
    reason='choose a returned entity_id' if bounded else 'search_entities first'
    exc=ValueError(f'{key} is not in this graph snapshot; {reason}')
    if bounded:
        exc.choices=bounded
        exc.example={'graph_id':graph['label'],key:bounded[0]['entity_id']}
    return exc


def canonical_flat(router,gid,graph,out,remember=False):
    """The flat surface is a canonical projection, not the strict wire format."""
    from .actor import REFS,ARRAY_REFS
    inner=out.get('result',{});d=inner.get('data',{});ids=d.pop('ids',{})
    if remember:remember_aliases(router,gid,graph['snapshot_id'],ids)
    def convert(v,key=None):
        if isinstance(v,dict):return {k:convert(x,k) for k,x in v.items() if k!='identity_scope'}
        if isinstance(v,list):return [convert(x,key) for x in v]
        return ids.get(v,v) if isinstance(v,str) and key in REFS|ARRAY_REFS else v
    inner['data']=d=convert(d)
    for n in d.get('nodes',[]):
        eid=n.pop('id');n['entity_id']=eid;n['cite_as']=graph['label']+'/entity:'+eid
    for key in ('hits','results','matches'):
        for record in d.get(key,[]):
            if 'node_id' in record:record['entity_id']=record.pop('node_id')
    for key in ('relationships','witnesses'):
        for record in d.get(key,[]):
            if 'id' in record:record['relationship_id']=record.pop('id')
    for key in ('schema_version','request_id','budget'):inner.pop(key,None)
    out['format']='agent-canonical-v1'
    return out


def profile_budget(router,arguments,default=32768):
    connection=getattr(router,'agent_profile','tier1_lead')
    profile=arguments.get('profile',connection)
    if profile not in PROFILE_CEILINGS:raise ValueError('Unknown profile; choose tier3_leaf, tier2_forager or tier1_lead')
    ceiling=min(PROFILE_CEILINGS[profile],PROFILE_CEILINGS[connection])
    if PROFILE_CEILINGS[profile]>ceiling:profile=connection
    asked=arguments.get('limit_tokens',min(default,ceiling))
    if type(asked) is not int or asked<256:raise ValueError('limit_tokens must be an integer >=256')
    return profile,min(asked,ceiling),asked>ceiling


def call_code(router,op,args):
    gid=router.resolve(args.get('graph_id'));router.permit(gid)
    profile,limit,clamped=profile_budget(router,args)
    with router.catalog.lock,router.lease(gid) as svc,svc.lock:
        graph=router.catalog.graph(gid);sid=graph['snapshot_id'];g=svc.store.graph(sid)
        roots=sorted(e.entity_id for e in g.entities.values() if e.kind=='repository')
        def entity(key):
            value=args[key]
            prefix=graph['label']+'/entity:'
            if value.startswith(prefix):value=value[len(prefix):]
            if value.startswith('entity:entity:'):value=value[7:]
            if re.fullmatch(r'n[1-9][0-9]*',value):
                if args.get('alias_scope'):
                    from .actor import resolve_request_aliases
                    value=resolve_request_aliases(svc,svc._context(sid),dict(snapshot_id=sid,alias_scope=args['alias_scope'],entity_id=value))['entity_id']
                else:
                    choices=getattr(router,'agent_aliases',{}).get((ALIAS_CONNECTION.get(),gid,sid,value),[])
                    if len(choices)==1:value=choices[0]
                    elif choices:
                        exc=ValueError('Ambiguous recent alias; use one of the canonical choices')
                        exc.example={'graph_id':graph['label'],key:choices[0]}
                        exc.choices=[dict(entity_id=e,cite_as=graph['label']+'/entity:'+e) for e in choices]
                        raise exc
                    else:raise ValueError('Search this graph first and use entity_id or cite_as from its results')
            if value not in g.entities:raise unknown_entity(router,gid,graph,g,key,value)
            return value
        request=dict(schema_version='1.1',request_id='agent:'+digest(op,gid,args)[:24],snapshot_id=sid,
            budget=dict(limit_tokens=limit,profile=profile,tokenizer='o200k_base',allow_byte_fallback=False),
            cursor=args.get('cursor'),identity_mode='canonical_map')
        coverage_range=None;context_ranges=None;context_omitted=0;constant_cards=None;constants_omitted=0;omit_content_summary=False
        from .agent_scent import scent
        descriptions=scent(svc._context(sid))
        if op=='search_entities':request.update(query=args['query'],mode='hybrid',repo_ids=[],kinds=args.get('kinds',[]),limit=args.get('limit',8))
        elif op=='get_entity_content':
            eid=entity('entity_id');e=g.entities[eid]
            a,b=args.get('start_line'),args.get('end_line')
            if a is not None and b is None:b=e.end_line
            if b is not None and a is None:a=e.start_line or 1
            request.update(entity_id=eid,content_kind='documentation' if e.kind=='fragment' else 'source',
                start_line=a,end_line=b,context_mode='range',context_radius=0)
            coverage_range=(a or e.start_line,b or e.end_line)
            if a is None and b is None:
                context_ranges=descriptions.context(eid)
                constant_cards=descriptions.calls_constants(eid)
                if context_ranges:
                    request['start_line'],request['end_line']=context_ranges[0][2:4]
                    context_omitted=max(0,e.end_line-context_ranges[0][3])+max(0,context_ranges[0][2]-descriptions.comment_start(e))
            if e.kind=='fragment':
                text=g.analyses['text:'+eid]['result']['text']
                coverage_range=(e.start_line,e.start_line+len(text.splitlines(keepends=True) or [''])-1)
        elif op=='get_architecture_context':request.update(focus_id=entity('focus_id'),grouping={'mode':'atomic'},context_radius=args.get('radius',1),
            pins=args.get('pins',[]),filter=deepcopy(DEFAULT_FILTER),qi=dict(enabled=args.get('qi',False),max_diameter=2,
                algorithm=args.get('algorithm','helper_tree_balls_v1')))
        elif op=='find_dependants':request.update(entity_id=entity('entity_id'),direction='incoming',filter=deepcopy(DEFAULT_FILTER),max_depth=args.get('max_depth',1),max_results=20)
        elif op=='find_similar_code':request.update(entity_id=entity('entity_id'),mode='exact_normalized_ast',repo_ids=[],limit=args.get('limit',5))
        elif op=='check_architecture':
            models=sorted(svc.rules)
            if not models:
                return dict(graph_id=gid,graph_label=graph['label'],snapshot_id=sid,analysis_status='not_configured',findings=[],
                    hint='No architecture rule model is configured; no conformance verdict was made.')
            if len(models)>1 and not args.get('model_digest'):raise ValueError('Multiple architecture models: supply model_digest')
            request.update(model_digest=args.get('model_digest',models[0]),scope_id=entity('scope_id') if args.get('scope_id') else roots[0],
                filter=deepcopy(DEFAULT_FILTER),include_satisfied=False,page_size=20)
        else:request.update(relationship_id=args['relationship_id'],view_id=args['view_id'],projection_id=None,
            evidence_page_size=5,evidence_cursor=None,page_size=20)
        if op in {'get_architecture_context','find_dependants'}:
            return bounded_context(router,gid,op,request,graph,limit,clamped)
        counter=TokenCounter();working=limit;search_count=request.get('limit',0);search_materialized=None;search_total=0
        for _ in range(64 if op=='search_entities' else 24):
            request['budget']['limit_tokens']=32768 if op=='search_entities' else working
            if op=='search_entities':request['budget'].pop('profile',None)
            if op=='search_entities':
                if search_materialized is None:
                    search_materialized=router.query(gid,op,request)
                    search_total=len(search_materialized.get('result',{}).get('data',{}).get('hits',[]))
                    search_count=min(search_count,search_total)
                out=deepcopy(search_materialized)
            else:out=router.query(gid,op,request)
            inner=out.get('result',{})
            if 'error' in out or 'error' in inner:
                err=out.get('error') or inner['error'];raise ValueError(f"{err.get('code','ERROR')}: {err.get('message','query failed')}")
            data=inner.get('data',{});ids=data.get('ids',{});nodes={n['id']:n for n in data.get('nodes',[])}
            selected=[h['node_id'] for h in data.get('hits',[])] if op=='search_entities' else list(nodes)
            out['entities']=[dict(entity_id=ids.get(i,i),cite_as=graph['label']+'/entity:'+ids.get(i,i),
                qualified_name=nodes[i].get('qualified_name'),source=nodes[i].get('source')) for i in selected if i in nodes]
            if clamped:out['budget_clamped_to']=limit
            out=canonical_flat(router,gid,graph,out,op=='search_entities')
            data=out['result']['data']
            if op=='search_entities':
                # Keep the original candidate pool/ranking while fitting its flat
                # projection. Ancestor navigation records belong to context tools.
                data['hits']=data.get('hits',[])[:search_count]
                hits={h['entity_id']:h for h in data.get('hits',[])}
                data['nodes']=[{k:v for k,v in node.items() if k in {'entity_id','cite_as','qualified_name','kind','source','summary'}}
                               for node in data.get('nodes',[]) if node['entity_id'] in hits]
                for node in data['nodes']:
                    if node['entity_id'] in hits:
                        node['summary']=descriptions.card(node['entity_id'],args['query'],node.get('summary',{}),hits[node['entity_id']])
                data['hits']=[{k:v for k,v in hit.items() if k in {'entity_id','score'}} for hit in data['hits']]
                data.pop('coverage',None)
                for key in ('view_id','relationships','witnesses','evidence_handles'):
                    if not data.get(key):data.pop(key,None)
                out['result'].pop('query_digest',None)
                out['entities']=[{k:v for k,v in row.items() if k!='source'} for row in out['entities'] if row['entity_id'] in hits]
                if search_count<search_total:
                    data['completeness']['truncated']=True
                    out['search_hits_omitted']=search_total-search_count
            elif op=='get_entity_content':
                if omit_content_summary:
                    for node in data.get('nodes',[]):
                        for key in ('summary','group_preview'):node.pop(key,None)
                if context_ranges:
                    data['chunks']=[descriptions.chunk(eid,r) for r in context_ranges]
                    data['usage_context']=True
                    data['context_complete']=not context_omitted
                    if context_omitted:out['context_omitted']=context_omitted
                if constant_cards:data['calls_constants']=constant_cards
                if constants_omitted:out['constants_omitted']=constants_omitted
            if op in {'search_entities','get_entity_content'}:
                from .agent_coverage import coverage_metadata
                out.update(coverage_metadata(op,out['result']['data'],coverage_range))
            out['routing_budget']['limit_tokens']=limit
            for _ in range(12):
                n=counter.count(out)
                if n==out['routing_budget']['used_tokens']:break
                out['routing_budget']['used_tokens']=n
            size=len(json.dumps(out,ensure_ascii=False))
            cap=router.max_result_chars
            if n<=limit and (not cap or size<=cap):
                if op=='search_entities':remember_search(router,gid,sid,out)
                return out
            ratio=min(limit/max(n,1),cap/size if cap else 1)*.85
            if context_ranges and len(context_ranges)>1:
                context_ranges.pop();context_omitted+=1
                continue
            if context_ranges and context_ranges[0][2]<e.start_line:
                r=context_ranges[0];context_omitted+=e.start_line-r[2]
                context_ranges[0]=(r[0],r[1],e.start_line,r[3],r[4],r[5])
                continue
            if constant_cards:
                constant_cards=constant_cards[:-1];constants_omitted+=1
                continue
            if context_ranges and not omit_content_summary:
                omit_content_summary=True;context_omitted+=1
                continue
            if op=='search_entities' and search_count>1:
                search_count-=1
                continue
            reduced=max(256,int(working*ratio))
            if reduced>=working:break
            working=reduced
        raise ValueError('RESULT_TOO_LARGE: try fewer results or a smaller source range')


def bounded_context(router,gid,op,request,graph,limit,clamped):
    """Project an internal wire result into a bounded, explicitly degraded flat result.

    Internal materialisation is bounded separately; only the final, recounted
    envelope crosses the agent's profile boundary. Strict calls never use this.
    """
    counter=TokenCounter();degraded=[];focus=request.get('focus_id',request.get('entity_id'));candidate=None
    internal=deepcopy(request);internal['budget']=dict(limit_tokens=32768,tokenizer='o200k_base',allow_byte_fallback=False)
    def fetch():
        out=router.query(gid,op,internal)
        err=out.get('error') or out.get('result',{}).get('error')
        if err:raise ValueError(f"{err['code']}: {err['message']}")
        return out
    def fit(out,focus_only=False):
        nonlocal candidate
        d=out['result']['data'];ids=d.get('ids',{})
        out['entities']=[dict(entity_id=ids.get(n['id'],n['id']),cite_as=graph['label']+'/entity:'+ids.get(n['id'],n['id']),
            qualified_name=n.get('qualified_name'),source=n.get('source')) for n in d['nodes']
            if not focus_only or ids.get(n['id'],n['id'])==focus]
        if degraded:out['degraded']=list(degraded)
        if clamped:out['budget_clamped_to']=limit
        out['routing_budget']['limit_tokens']=limit
        candidate=canonical_flat(router,gid,graph,deepcopy(out))
        for _ in range(12):
            count=counter.count(candidate)
            if candidate['routing_budget']['used_tokens']==count:break
            candidate['routing_budget']['used_tokens']=count
        return count<=limit and (not router.max_result_chars or len(json.dumps(candidate,ensure_ascii=False))<=router.max_result_chars)
    def summaries(out):
        for n in out['result']['data']['nodes']:n.pop('summary',None)
    out=fetch()
    if fit(out):return candidate
    degraded.append('optional_node_summaries_omitted');summaries(out)
    if fit(out):return candidate
    if op=='get_architecture_context' and internal['context_radius']:
        internal['context_radius']=0;out=fetch();summaries(out);degraded.append('context_radius_reduced_to_0')
        if fit(out):return candidate
    d=out['result']['data'];ids=d.get('ids',{})
    ancestors=set(d.get('ancestor_ids',[]))
    for i,n in enumerate(d['nodes']):
        if n['id'] in ancestors and ids.get(n['id'],n['id'])!=focus:
            d['nodes'][i]=dict(id=n['id'],qualified_name=n.get('display_label') or n.get('qualified_name','').rsplit('/',1)[-1].rsplit('.',1)[-1])
    degraded.append('ancestor_nodes_reduced_to_ids_and_labels')
    if fit(out,True):return candidate
    keep={n['id'] for n in d['nodes'] if n['id'] in ancestors or ids.get(n['id'],n['id'])==focus}
    omitted=len(d['nodes'])-len(keep)
    d['nodes']=[n for n in d['nodes'] if n['id'] in keep]
    for key in ('relationships','witnesses'):
        if key in d:d[key]=[r for r in d[key] if r['source'] in keep and r['target'] in keep]
    for key in ('results','hits'):
        if key in d:d[key]=[r for r in d[key] if r['node_id'] in keep]
    d['ids']={k:v for k,v in ids.items() if k in keep}
    degraded.append(f'optional_context_nodes_omitted:{omitted}')
    if fit(out,True):return candidate
    focus_node=next(n for n in d['nodes'] if ids.get(n['id'],n['id'])==focus)
    # Ancestors are context too: do not refuse a focus that fits by itself.
    out['result']['data']=dict(nodes=[{k:v for k,v in focus_node.items() if k in {'id','entity_id','qualified_name','kind','source'}}],
        ancestor_ids=[],relationships=[],witnesses=[],**({'results':[]} if op=='find_dependants' else {}))
    # Preserve the canonical lookup until projection, including the focus alias.
    out['result']['data']['ids']={focus_node['id']:focus}
    degraded.append(f'ancestor_context_omitted:{len(ancestors)};focus_only')
    if fit(out,True):return candidate
    raise ValueError('BUDGET_TOO_SMALL: focus node alone does not fit; increase the connection cap')
