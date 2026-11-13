"""Small MCP front door; strict wire requests remain a separate programmatic API."""
from copy import deepcopy
import json
import re
import jsonschema
from .analysis import DEFAULT_FILTER
from .model import digest
from .task_packets import PROFILE_CEILINGS
from .tokens import TokenCounter


def schemas(single=False):
    string={'type':'string'}
    common={'graph_id':string,'profile':{'enum':list(PROFILE_CEILINGS)},'limit_tokens':{'type':'integer','minimum':256},
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
    ex=example(op)
    if op=='list_graphs':ex={}
    text=f'{field}: {reason[:140]}. Example: {op}({json.dumps(ex,separators=(",",":"))})'
    return dict(error=dict(code='INVALID_GRAPH_REQUEST',field=field,message=text[:400],example=ex))


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
                if not args.get('alias_scope'):raise ValueError('Use entities[].entity_id from search, or provide alias_scope with an alias')
                from .actor import resolve_request_aliases
                value=resolve_request_aliases(svc,svc._context(sid),dict(snapshot_id=sid,alias_scope=args['alias_scope'],entity_id=value))['entity_id']
            if value not in g.entities:raise ValueError(f'{key} is not in this graph snapshot; search_entities first')
            return value
        request=dict(schema_version='1.1',request_id='agent:'+digest(op,gid,args)[:24],snapshot_id=sid,
            budget=dict(limit_tokens=limit,profile=profile,tokenizer='o200k_base',allow_byte_fallback=False),
            cursor=args.get('cursor'),identity_mode='canonical_map')
        if op=='search_entities':request.update(query=args['query'],mode='hybrid',repo_ids=[],kinds=args.get('kinds',[]),limit=args.get('limit',8))
        elif op=='get_entity_content':
            eid=entity('entity_id');e=g.entities[eid]
            a,b=args.get('start_line'),args.get('end_line')
            if a is not None and b is None:b=e.end_line
            if b is not None and a is None:a=e.start_line or 1
            request.update(entity_id=eid,content_kind='documentation' if e.kind=='fragment' else 'source',
                start_line=a,end_line=b,context_mode='range',context_radius=0)
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
        counter=TokenCounter();working=limit
        for _ in range(10):
            request['budget']['limit_tokens']=working
            out=router.query(gid,op,request)
            inner=out.get('result',{})
            if 'error' in out or 'error' in inner:
                err=out.get('error') or inner['error'];raise ValueError(f"{err.get('code','ERROR')}: {err.get('message','query failed')}")
            data=inner.get('data',{});ids=data.get('ids',{});nodes={n['id']:n for n in data.get('nodes',[])}
            selected=[h['node_id'] for h in data.get('hits',[])] if op=='search_entities' else list(nodes)
            out['entities']=[dict(entity_id=ids.get(i,i),cite_as=graph['label']+'/entity:'+ids.get(i,i),
                qualified_name=nodes[i].get('qualified_name'),source=nodes[i].get('source')) for i in selected if i in nodes]
            if clamped:out['budget_clamped_to']=limit
            out['routing_budget']['limit_tokens']=limit
            for _ in range(12):
                n=counter.count(out)
                if n==out['routing_budget']['used_tokens']:break
                out['routing_budget']['used_tokens']=n
            size=len(json.dumps(out,ensure_ascii=False))
            cap=router.max_result_chars
            if n<=limit and (not cap or size<=cap):return out
            ratio=min(limit/max(n,1),cap/size if cap else 1)*.85
            reduced=max(256,int(working*ratio))
            if reduced>=working:break
            working=reduced
        raise ValueError('RESULT_TOO_LARGE: try fewer results or a smaller source range')
