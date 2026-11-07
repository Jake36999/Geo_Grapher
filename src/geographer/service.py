"""Shared read-only query service used identically by HTTP and MCP."""
from __future__ import annotations

import ast
import base64
from collections import OrderedDict,defaultdict,deque
import hashlib
import json
import re
import threading
from copy import deepcopy
from functools import partial

from .analysis import (DEFAULT_FILTER,TreeIndex,Partition,partition,project,materialize_view,
                       subject_graph,boundary_ratios,cayley_bounds,selected_relationships,condensations,persist_projection_view)
from .contraction import contract_helpers
from .cursors import CursorPlans,InvalidCursor
from .model import canonical,digest
from .packing import GreedyPacker,Unit,combine,BudgetTooSmall,PACKER_VERSION
from .rules import ArchitectureRules,RuleConflict
from .tokens import TokenCounter,TokenizerUnavailable
from .wire import WireContracts
from .resources import resource_root


class QueryError(ValueError):
    def __init__(self,code,message,retryable=False):
        self.code=code;self.retryable=retryable
        super().__init__(message)


class QueryService:
    def projects(self,limit=32):
        """Small discovery manifest; never loads source bodies or merges domains."""
        with self.lock:
            rows=self.store.connection.execute("SELECT snapshot_id,config_json FROM snapshot_sets WHERE status='complete' ORDER BY created_at DESC,snapshot_id LIMIT ?",(limit+1,)).fetchall()
            snapshots=[]
            for row in rows[:limit]:
                config=json.loads(row['config_json']);sid=row['snapshot_id'];repos=[]
                for revision in self.store.connection.execute("SELECT repo_id,revision FROM snapshots WHERE snapshot_id=? AND repo_id<>'@workspace' ORDER BY repo_id",(sid,)):
                    rid=revision['repo_id'];root=self.store.connection.execute("SELECT entity_id FROM entities WHERE snapshot_id=? AND repo_id=? AND kind='repository'",(sid,rid)).fetchone()
                    policy=config.get('repository_isolation',{}).get(rid)
                    repos.append(dict(repo_id=rid,revision=revision['revision'],root_entity_id=root[0],
                        resolution_group=policy.get('resolution_group') if policy is not None else 'legacy_shared_namespace',
                        source_roots=config.get('source_roots',{}).get(rid,[]),
                        selected_file_count=self.store.connection.execute("SELECT count(*) FROM entities WHERE snapshot_id=? AND repo_id=? AND kind IN ('file','document')",(sid,rid)).fetchone()[0],
                        profiled=bool(policy and (policy['include_globs']!=['*'] or policy['exclude_globs']))))
                snapshots.append(dict(snapshot_id=sid,repositories=repos))
            return dict(snapshots=snapshots,truncated=len(rows)>limit,
                guidance='Choose snapshot_id and repo_ids explicitly; cross-project similarity requires listing every intended repository. root_entity_id anchors content and architecture queries.',
                coverage='Only configured supported source files are indexed; experimental datasets and PDFs are not implicitly imported')

    def __init__(self,store,*,rules=(),secret=None,token_directory=None,cursors=None):
        self.store=store;self.wire=WireContracts();self.token_directory=token_directory
        self.cursors=cursors or CursorPlans(secret=secret);self.packer=GreedyPacker(self.cursors)
        self.rules={r.digest:r for r in rules};self.cache=OrderedDict();self.lock=threading.RLock()
        self.handles=OrderedDict()
        self.active_snapshot=None
        self.active_version='1.0'
        self.wire11=None
        from .workspace import recover_rules
        recover_rules(self)

    def _context(self,sid):
        row=self.store.connection.execute('SELECT status FROM snapshot_sets WHERE snapshot_id=?',(sid,)).fetchone()
        if row is None:raise QueryError('SNAPSHOT_UNAVAILABLE','Snapshot not found')
        if row[0]!='complete':raise QueryError('INCOMPLETE_BUILD','Snapshot is not published')
        if sid not in self.cache:
            g=self.store.graph(sid)
            revisions=[dict(r) for r in self.store.connection.execute("SELECT repo_id,revision,digest FROM snapshots WHERE snapshot_id=? AND repo_id<>'@workspace' ORDER BY repo_id",(sid,))]
            revmap={r['repo_id']:r['revision'] for r in revisions}
            ev=defaultdict(list)
            for e in g.evidence.values():ev[e.relationship_id].append(e)
            for values in ev.values():values.sort(key=lambda e:e.evidence_id)
            sources={(g.entities[v['scope']['entity_id']].repo_id,v['result']['rel_path']):v['result'] for v in g.analyses.values()
                     if v['algorithm_version']=='source-bytes-v1' and v['scope'].get('entity_id') in g.entities}
            self.cache[sid]=dict(g=g,tree=TreeIndex(g),revisions=revisions,revmap=revmap,evidence=ev,nodes={},sources=sources)
        self.cache.move_to_end(sid)
        while len(self.cache)>4:
            _,old=self.cache.popitem(last=False)
            if 'lexical_index' in old:old['lexical_index'].close()
        return self.cache[sid]

    @staticmethod
    def fingerprint(operation,request):
        omitted={'request_id','budget','cursor','limit','page_size','evidence_page_size','evidence_cursor','alias_scope','identity_mode'}
        values={k:v for k,v in request.items() if k not in omitted}
        if operation=='inspect_relationship_witnesses':values['evidence_mode']=bool(request.get('evidence_cursor'))
        semantic_version='actor-records-v1/lexical-fusion-v1/typed-bridge-v1/source-context-v1/workspace-views-v1' if request.get('schema_version')=='1.1' else 'wire-1.0'
        return digest(PACKER_VERSION,semantic_version,operation,values)

    def _handle(self,kind,value):
        value=deepcopy(value)
        handle='handle:'+kind+':'+digest(self.active_snapshot,value)
        self.handles[handle]=value;self.handles.move_to_end(handle)
        while len(self.handles)>2048:self.handles.popitem(last=False)
        if self.active_snapshot:
            self.store.connection.execute('INSERT OR IGNORE INTO analysis_results(snapshot_id,analysis_id,algorithm_version,scope_json,result_json) VALUES(?,?,?,?,?)',
                (self.active_snapshot,handle,'query-handle-v1',canonical({'snapshot_id':self.active_snapshot}),canonical(value)))
        return handle

    def read_handle(self,handle):
        with self.lock:
            if handle not in self.handles:
                for row in self.store.connection.execute("SELECT snapshot_id FROM snapshot_sets WHERE status='complete'").fetchall():
                    found=self.store.connection.execute("SELECT result_json FROM analysis_results WHERE snapshot_id=? AND analysis_id=? AND algorithm_version='query-handle-v1'",(row[0],handle)).fetchone()
                    if found:
                        self.handles[handle]=json.loads(found[0]);break
            if handle not in self.handles:raise QueryError('NOT_FOUND','Handle expired or unavailable; repeat its query')
            self.handles.move_to_end(handle)
            while len(self.handles)>2048:self.handles.popitem(last=False)
            value=self.handles[handle]
            if handle.startswith('handle:runtime_collection:'):
                self.store.require_complete(value['snapshot_id'])
                row=self.store.connection.execute("SELECT result_json FROM analysis_results WHERE snapshot_id=? AND analysis_id=? AND algorithm_version='runtime-collection-v1'",(value['snapshot_id'],value['collection_id'])).fetchone()
                if row is None:raise QueryError('NOT_FOUND','Runtime collection unavailable')
                return json.loads(row[0])
            return deepcopy(value)

    def _coverage(self,sid,ctx,scope=None):
        failures=[{'repo_id':r['repo_id'],**f} for r in self.store.connection.execute('SELECT repo_id,parse_failures_json FROM snapshots WHERE snapshot_id=?',(sid,)) for f in json.loads(r['parse_failures_json'])]
        rels=ctx['g'].relationships.values()
        if scope is not None:rels=[r for r in rels if r.source_subject_id in scope]
        unresolved=sum(r.resolution_status in {'candidate','unresolved'} for r in rels)
        limitations=[]
        if failures:limitations.append(f'{len(failures)} input files could not be fully parsed')
        if unresolved:limitations.append(f'{unresolved} candidate or unresolved relationships in this scope')
        limitations.append('Exact static facts describe the declared resolver subset; dynamic Python behaviour is not complete')
        from .trace import collections
        runtime=collections(self.store,sid,include_quarantine=False)
        if runtime:
            limitations.append(f'{len(runtime)} runtime collections contain positive observations only; non-observation is not absence')
            if any(not r['coverage']['complete'] or r['quarantined_records'] for r in runtime):limitations.append('Runtime capture/mapping limitations are reported per collection; no whole-process coverage is implied')
        handle=self._handle('coverage',dict(snapshot_id=sid,failures=failures,unresolved_count=unresolved))
        return dict(status='partial' if failures or unresolved else 'complete_for_declared_static_subset',
                    parse_failure_count=len(failures),unresolved_count=unresolved,limitations=limitations,report_handle=handle)

    def _location(self,ctx,e):
        if e.rel_path is None or e.start_line is None:return None
        return dict(repo_id=e.repo_id,revision=ctx['revmap'].get(e.repo_id,'workspace'),rel_path=e.rel_path,start_line=e.start_line,end_line=e.end_line)

    def _node(self,ctx,eid,*,part=None,focus=None):
        if part is not None and part.kinds.get(eid) not in (None,'entity'):
            members=sorted(part.groups[eid]);kind=part.kinds[eid]
            shell=part.shells[eid]
            name=('Other children of '+ctx['g'].entities[shell].qualified_name if kind=='residual' and shell else
                  'Helper summary' if kind=='qi' else 'Unmapped' if kind=='unmapped' else 'Conceptual component')
            if kind=='conceptual' and part.grouping.get('model_digest') in self.rules:
                model=self.rules[part.grouping['model_digest']]
                name=next((c['id'] for c in model.model['components'] if eid=='view:component:'+digest(model.digest,c['id'])),name)
            return dict(id=eid,entity_id=None,kind=kind,sort='synthetic',repo_id='@workspace',language='none',qualified_name=name,
                        parent_id=shell,depth=None,source=None,flags=dict(is_test=False,is_generated=False,is_vendor=False,is_external=False),
                        member_count=len(members),membership_handle=self._handle('members',dict(members=members)),ast_body_hash=None,wl_3hop_hash=None,doi=None)
        if eid not in ctx['g'].entities:raise QueryError('NOT_FOUND','Entity is outside snapshot')
        e=ctx['g'].entities[eid]
        node=dict(id=eid,entity_id=eid,kind=e.kind,sort=e.sort,repo_id=e.repo_id,language=e.language,qualified_name=e.qualified_name,
                  parent_id=e.parent_id,depth=e.depth,source=self._location(ctx,e),
                  flags={key:bool(getattr(e,key)) for key in ('is_test','is_generated','is_vendor','is_external')},
                  member_count=len(part.groups[eid]) if part and eid in part.groups else 1,membership_handle=None,
                  ast_body_hash=e.ast_body_hash,wl_3hop_hash=e.wl_3hop_hash,doi=ctx['tree'].doi(eid,focus) if focus else None)
        if part and eid in part.groups and len(part.groups[eid])>1:
            node['membership_handle']=self._handle('members',dict(members=sorted(part.groups[eid])))
        return node

    def _evidence(self,ctx,e):
        location=None
        if e.rel_path is not None and e.start_line is not None:
            location=dict(repo_id=e.repo_id,revision=e.revision,rel_path=e.rel_path,start_line=e.start_line,end_line=e.end_line)
        return dict(id=e.evidence_id,relationship_id=e.relationship_id,category=e.category,source=location,trace_ref=e.trace_ref,
                    revision=e.revision,extractor_version=e.extractor_version,confidence=e.confidence,
                    window=dict(start=e.window_start,end=e.window_end) if e.window_start else None,
                    details_handle=self._handle('evidence',json.loads(e.details_json)))

    def _witness(self,ctx,rid,projection_id=None):
        r=ctx['g'].relationships[rid]
        return dict(id=rid,projection_id=projection_id,source=r.source_id,target=r.target_id,
                    source_subject_id=r.source_subject_id,target_subject_id=r.target_subject_id,family=r.family,subtype=r.subtype,
                    direction=r.direction,resolution_status=r.resolution_status,confidence=r.confidence,weight=r.weight,
                    weight_unit=r.weight_unit,evidence_ids=[],evidence_total=len(ctx['evidence'][rid]),evidence_next_cursor=None)

    def _inspect_request(self,sid,view_id,projection=None,relationship=None,evidence=False):
        return dict(schema_version=self.active_version,request_id='internal-plan',snapshot_id=sid,budget=dict(limit_tokens=8192,tokenizer='o200k_base',allow_byte_fallback=False),
                    view_id=view_id,projection_id=projection,relationship_id=relationship,evidence_page_size=20,
                    evidence_cursor='initial' if evidence else None,page_size=50,cursor=None)

    def _summary(self,sid,view_id,row):
        request=self._inspect_request(sid,view_id,projection=row['projection_id'])
        cursor=self.cursors.initial_cursor(sid,self.fingerprint('inspect_relationship_witnesses',request),view_id,'witnesses') if self.active_version=='1.0' else None
        return dict(id=row['projection_id'],view_id=view_id,source=row['source_rep_id'],target=row['target_rep_id'],family=row['family'],
                    subtype=row['subtype'],direction=row['direction'],resolution_status=row['resolution_status'],weight_unit=row['weight_unit'],
                    aggregated_weight=row['aggregated_weight'],witness_count=row['witness_count'],evidence_count=row['evidence_count'],
                    is_internal=bool(row['is_internal']),witness_cursor=cursor)

    def _payload(self,sid,ctx,**extra):
        return dict(view_id=None,nodes=[],relationships=[],witnesses=[],evidence_handles=[],coverage=self._coverage(sid,ctx),
                    completeness=dict(truncated=False,omitted_nodes=0,omitted_relationships=0,omitted_items=0,next_cursor=None),**extra)

    def _plan(self,operation,request,mandatory,units,view_id=None,collection='items'):
        all_data=combine(mandatory,units,copy_records=False)
        totals=dict(nodes=len(all_data['nodes']),relationships=len(all_data['relationships'])+len(all_data['witnesses']))
        return self.cursors.create(request['snapshot_id'],self.fingerprint(operation,request),view_id,collection,units,mandatory,totals)

    def _evidence_plan(self,sid,ctx,view_id,rid):
        request=self._inspect_request(sid,view_id,relationship=rid,evidence=True)
        key=(sid,self.fingerprint('inspect_relationship_witnesses',request))
        self.cursors._prune()
        if key in self.cursors.plans:return self.cursors.plans[key]
        r=ctx['g'].relationships[rid]
        data=self._payload(sid,ctx,total_witness_count=1);data['view_id']=view_id
        data['nodes']=[self._node(ctx,eid) for eid in sorted({r.source_id,r.target_id})]
        data['witnesses']=[self._witness(ctx,rid)]
        units=[Unit('evidence:'+e.evidence_id,1,150,dict(evidence_handles=[self._evidence(ctx,e)])) for e in ctx['evidence'][rid]]
        plan=self._plan('inspect_relationship_witnesses',request,data,units,view_id,'evidence')
        plan.evidence_plans[rid]=partial(self._evidence_plan,sid,ctx,view_id,rid)
        return self._actor_plan(plan,request,ctx,'inspect_relationship_witnesses') if self.active_version=='1.1' else plan

    def _actor_plan(self,plan,request,ctx,operation):
        if getattr(plan,'actor_encoder',None):return plan
        from .actor import ActorEncoder
        encoders=ctx.setdefault('actor_encoders',OrderedDict());shells=operation in {'get_architecture_context','viewport_frame'}
        key=(plan.view_id,digest(request.get('filter') or DEFAULT_FILTER),shells)
        if key not in encoders:encoders[key]=ActorEncoder(self,ctx,plan.view_id,request.get('filter'),shells)
        encoder=encoders[key];encoders.move_to_end(key)
        while len(encoders)>4:encoders.popitem(last=False)
        return encoder.prepare(plan)

    def query(self,operation,raw,*,cursor_override=None):
        with self.lock,self.store.connection:
            rid=raw.get('request_id','invalid-request') if isinstance(raw,dict) else 'invalid-request'
            if not isinstance(rid,str) or len(rid)>128:rid='invalid-request'
            error=lambda *args,**kw:{**self._error(*args,**kw),'schema_version':'1.1' if self.active_version=='1.1' else '1.0'}
            try:
                version=raw.get('schema_version','1.0') if isinstance(raw,dict) else '1.0'
                self.active_version=version
                if version=='1.1':
                    if self.wire11 is None:self.wire11=WireContracts(resource_root()/'contracts/v1.1')
                    wire=self.wire11
                else:wire=self.wire
                request=wire.validate(operation,'request',raw)
                ctx=self._context(request['snapshot_id']);sid=request['snapshot_id']
                self.active_snapshot=sid
                if version=='1.1':
                    from .actor import resolve_request_aliases
                    request=resolve_request_aliases(self,ctx,request)
                    if operation=='get_architecture_context':request.setdefault('include_diagnostics',False)
                if operation in {'search_entities','find_similar_code'}:
                    known={r['repo_id'] for r in ctx['revisions']}
                    chosen=set(request['repo_ids'])
                    if chosen-known:raise QueryError('INVALID_REQUEST','Unknown repository scope: '+', '.join(sorted(chosen-known)))
                    if len(known)>1 and not chosen:
                        raise QueryError('INVALID_REQUEST','Select repo_ids explicitly in a multi-project snapshot; pass every repository ID only for an intentional cross-project comparison. Available: '+', '.join(sorted(known)))
                if 'filter' in request and 'runtime' in request['filter']['families']:
                    window=request['filter']['runtime_window']
                    from .trace import collections
                    known=any(c['window']['start']==window['start'] and c['window']['end']==window['end'] and c['environment']==window['environment'] for c in collections(self.store,sid,include_quarantine=False))
                    if not known and not any(e.category=='dynamic_observed' and e.window_start==window['start'] and e.window_end==window['end'] and
                               json.loads(e.details_json).get('environment')==window['environment'] for e in ctx['g'].evidence.values()):
                        raise QueryError('NOT_FOUND','No telemetry collection for that window/environment')
                counter=TokenCounter(request['budget']['tokenizer'],request['budget']['allow_byte_fallback'],self.token_directory)
                cursor=cursor_override or request.get('evidence_cursor') or request.get('cursor')
                plan=None;delivered=[]
                qd=self.fingerprint(operation,request)
                if cursor:plan,delivered=self.cursors.resume(cursor,sid,qd)
                if plan is None:
                    self.cursors._prune()
                    plan=self.cursors.plans.get((sid,qd)) or self._build(operation,request,ctx)
                if version=='1.1':plan=self._actor_plan(plan,request,ctx,operation)
                base=dict(schema_version=version,request_id=request['request_id'],snapshot_id=sid,revisions=ctx['revisions'],query_digest=qd)
                limit=request.get('page_size',request.get('limit',200))
                if request.get('evidence_cursor'):limit=request['evidence_page_size']
                response=self.packer.pack(base,plan,counter,request['budget']['limit_tokens'],delivered,limit,
                    transform=partial(plan.actor_encoder.envelope_data,include_ids=request.get('identity_mode')=='canonical_map') if version=='1.1' else None,
                    transform_key=request.get('identity_mode','compact') if version=='1.1' else 'canonical')
                try:wire.validate(operation,'response',response)
                except Exception as exc:raise QueryError('INTERNAL_ERROR','Generated response violated the wire contract') from exc
                return response
            except BudgetTooSmall as exc:return error(rid,'BUDGET_TOO_SMALL',str(exc),minimum=exc.minimum)
            except TokenizerUnavailable as exc:return error(rid,'TOKENIZER_UNAVAILABLE',str(exc),retryable=True)
            except InvalidCursor as exc:return error(rid,'INVALID_CURSOR',str(exc))
            except RuleConflict as exc:return error(rid,'RULE_CONFLICT',str(exc))
            except QueryError as exc:return error(rid,exc.code,str(exc),retryable=exc.retryable)
            except (ValueError,KeyError,TypeError,UnicodeError) as exc:return error(rid,'INVALID_REQUEST',str(exc)[:500])
            except Exception as exc:
                # Schema validation exceptions are request errors; unexpected defects stay distinct.
                import jsonschema,pydantic
                if isinstance(exc,(jsonschema.ValidationError,pydantic.ValidationError)):
                    return error(rid,'INVALID_REQUEST',str(exc).splitlines()[0][:500])
                import logging
                logging.getLogger(__name__).exception('Query failed for %s',operation)
                return error(rid,'INTERNAL_ERROR','Query failed; see local server diagnostics')

    @staticmethod
    def _error(rid,code,message,retryable=False,minimum=None):
        try:
            if len(rid.encode('utf-8'))>128:rid='invalid-request'
        except UnicodeError:rid='invalid-request'
        return dict(schema_version='1.0',request_id=rid,error=dict(code=code,message=message,retryable=retryable,minimum_tokens=minimum,details_handle=None))

    def _build(self,operation,request,ctx):
        if request['schema_version']=='1.1' and operation=='search_entities':return self._actor_search(request,ctx)
        if request['schema_version']=='1.1' and operation=='get_architecture_context':return self._actor_context(request,ctx)
        if request['schema_version']=='1.1' and operation=='get_entity_content':return self._actor_content(request,ctx)
        method=getattr(self,'_'+operation,None)
        if method is None:raise QueryError('INVALID_REQUEST','Unknown operation')
        return method(request,ctx)

    def _actor_search(self,q,ctx):
        from .retrieval import LexicalIndex
        if 'lexical_index' not in ctx:ctx['lexical_index']=LexicalIndex(ctx['g'])
        config=q.get('retrieval',{'gamma':.8,'k':60})
        hits=ctx['lexical_index'].search(q['query'],q['repo_ids'],q['kinds'],mode=q['mode'],limit=q['limit'],**config)
        data=self._payload(q['snapshot_id'],ctx,hits=[]);units=[]
        for h in hits:
            ids={h['node_id'],*h['fragment_ids']}
            units.append(Unit('search:'+h['node_id'],1,1000 if h['score']==1. else h['score'],
                dict(nodes=[self._node(ctx,eid) for eid in sorted(ids)],hits=[h])))
        return self._plan('search_entities',q,data,units)

    def _actor_context(self,q,ctx):
        from .retrieval import TypedBridge
        plan=self._get_architecture_context(q,ctx);plan.mandatory['paths']=[]
        if q.get('review_queue'):
            from .workspace import triage
            result=triage(self,q['snapshot_id'],q['filter'],q['focus_id'],q['pins'],q.get('review_model_digest'),after=q.get('review_cursor'),limit=q.get('review_limit',10),queue=q['review_queue'])
            plan.mandatory['review_queue']=result
            refs={r['entity_id'] for r in result['items']}|{eid for r in result['items'] for eid in r['alternatives']}
            existing={n['id'] for n in plan.mandatory['nodes']}
            plan.mandatory['nodes'].extend(self._node(ctx,eid) for eid in sorted(refs-existing))
        if not q['include_diagnostics']:plan.units[:]=[u for u in plan.units if not (u.records.keys() & {'boundary','cayley'})]
        opts=q.get('path_request')
        if not opts:return plan
        if len(q['pins'])>8:raise QueryError('INVALID_REQUEST','At most eight typed anchor pairs per query')
        mapping=None
        if opts['boundary_model_digest']:
            model=self.rules.get(opts['boundary_model_digest'])
            if model is None:raise QueryError('NOT_FOUND','Boundary model unavailable')
            mapping=model.map_entities(ctx['g'],q['snapshot_id'])
        bridge=TypedBridge(ctx['g'],q['filter'])
        for target in sorted(q['pins']):
            path=bridge.find(q['focus_id'],target,opts['template'],max_hops=opts['max_hops'],max_expansions=opts['max_expansions'],max_anchor_subjects=opts.get('max_anchor_subjects',200),undirected=opts['undirected'],mapping=mapping)
            plan.mandatory['paths'].append({**path,'steps':[],'outcome':'omitted_by_budget','resolved_source':None,'resolved_target':None})
            witnesses=[self._witness(ctx,s['relationship_id']) for s in path['steps']]
            ids={q['focus_id'],target}|{x for w in witnesses for x in (w['source'],w['target'],w['source_subject_id'],w['target_subject_id'])}
            unit=Unit('typed-path:'+target,1,1000,dict(nodes=[self._node(ctx,eid) for eid in sorted(ids)],witnesses=witnesses,paths=[path]))
            plan.units.append(unit)
            for w in witnesses:plan.evidence_plans[w['id']]=partial(self._evidence_plan,q['snapshot_id'],ctx,plan.view_id,w['id'])
        all_data=combine(plan.mandatory,plan.units,copy_records=False)
        plan.totals.update(nodes=len(all_data['nodes']),relationships=len(all_data['relationships'])+len(all_data['witnesses']))
        return plan

    def _actor_content(self,q,ctx):
        if q['context_mode']=='source-context-v1':
            if q['content_kind']!='source':raise QueryError('INVALID_REQUEST','Source folding requires source content')
            from .source_context import build_source_plan
            plan=build_source_plan(self,q,ctx)
        else:
            plan=self._get_entity_content(q,ctx);plan.mandatory['source_context']=None
        if q.get('include_investigation'):
            from .workspace import investigation
            details=investigation(self,q,ctx);plan.mandatory['investigation']=details
            refs={f for section in details['documentary_sections'] for f in section['fragment_ids']}
            if details['overlay']:refs.update(r['entity_id'] for r in details['overlay']['records'])
            existing={n['id'] for n in plan.mandatory['nodes']}
            plan.mandatory['nodes'].extend(self._node(ctx,eid) for eid in sorted(refs-existing))
        return plan

    def _viewport_frame(self,q,ctx):
        from .viewport import build_frame
        return build_frame(self,q,ctx)

    def _search_entities(self,q,ctx):
        data=self._payload(q['snapshot_id'],ctx,hits=[])
        tokens=re.findall(r'\w+',q['query'].casefold());units=[]
        if not tokens:raise QueryError('INVALID_REQUEST','Search query must contain a word')
        for e in ctx['g'].entities.values():
            if q['repo_ids'] and e.repo_id not in q['repo_ids'] or q['kinds'] and e.kind not in q['kinds']:continue
            name=e.qualified_name.casefold();path=(e.rel_path or '').casefold()
            if not all(t in name or t in path for t in tokens):continue
            score=100*(name==q['query'].casefold())+20*name.startswith(q['query'].casefold())+5*sum(t in name for t in tokens)+sum(t in path for t in tokens)
            fields=(['qualified_name'] if any(t in name for t in tokens) else [])+(['rel_path'] if any(t in path for t in tokens) else [])
            units.append(Unit('search:'+e.entity_id,1,score+1,dict(nodes=[self._node(ctx,e.entity_id)],hits=[dict(node_id=e.entity_id,score=score,matched_fields=fields)])))
        units.sort(key=lambda u:(-u.utility,u.id))
        return self._plan('search_entities',q,data,units)

    def _conceptual_partition(self,q,ctx):
        model=self.rules.get(q['grouping']['model_digest'])
        if model is None:raise QueryError('NOT_FOUND','Conceptual model not loaded')
        mapping=model.map_entities(ctx['g'],q['snapshot_id']);base=partition(ctx['g'],q['snapshot_id'],{'mode':'atomic'},q['filter'])
        groups={};kinds={};shells={}
        for rep,atoms in base.groups.items():
            component=mapping.get(rep,'Unmapped');cid='view:component:'+digest(model.digest,component)
            groups.setdefault(cid,set()).update(atoms);kinds[cid]='unmapped' if component=='Unmapped' else 'conceptual';shells[cid]=ctx['tree'].root
        return Partition(q['grouping'],groups,kinds,shells)

    def _persist_partition(self,sid,ctx,part,filters,version):
        # Custom QI/conceptual partitions have the same witness/store invariants.
        # A mixed view consisting only of complete repository representatives is
        # exactly the default repository quotient. Reuse its indexed witnesses
        # instead of copying every leaf occurrence for a collapsed overview.
        kinds={ctx['g'].entities[rep].kind for rep in part.groups if rep in ctx['g'].entities}
        if part.groups and len(kinds)==1 and next(iter(kinds)) in {'repository','directory','file','class'} and all(rep in ctx['g'].entities and part.kinds[rep]=='entity' for rep in part.groups):
            canonical_grouping={'mode':'kind','kind':next(iter(kinds))}
            existing='view:'+digest(sid,canonical_grouping,filters,'quotient-v1')
            if self.store.connection.execute('SELECT 1 FROM analysis_views WHERE snapshot_id=? AND view_id=?',(sid,existing)).fetchone():
                # Reuse only an exactly identical partition. Kind names alone
                # cannot justify dropping residual/conceptual memberships.
                actual={r[0]:r[1] for r in self.store.connection.execute('SELECT atom_id,representative_id FROM partition_members WHERE snapshot_id=? AND view_id=?',(sid,existing))}
                if actual==part.representatives:return existing
        fh=digest(filters);vid='view:'+digest(sid,part.grouping,filters,version,{r:sorted(m) for r,m in part.groups.items()})
        if self.store.connection.execute('SELECT 1 FROM analysis_views WHERE snapshot_id=? AND view_id=?',(sid,vid)).fetchone():return vid
        rows=project(ctx['g'],part,vid,filters)
        edges=[(r['source_rep_id'],r['target_rep_id']) for r in rows if r['family'] in {'static','runtime'} and r['direction']=='directed']
        scc=condensations(sid,vid,fh,part.groups,edges)
        persist_projection_view(self.store,sid,vid,part,filters,version,rows,scc)
        return vid

    def _architecture(self,q,ctx):
        g=ctx['g'];sid=q['snapshot_id'];focus=q['focus_id'];tree=ctx['tree']
        if focus not in g.entities or any(p not in g.entities for p in q['pins']):raise QueryError('NOT_FOUND','Focus/pin is outside snapshot')
        qi=dict(mode='off',metric='undirected_unweighted_hops',requested_diameter=0,measured_max_intrinsic_diameter=0,A=1,B=0,
                directed_reachability_preserved=False,group_count=0,internal_witness_count=0,crossing_witness_count=0,membership_handle=None)
        part=self._conceptual_partition(q,ctx) if q['grouping']['mode']=='conceptual' else partition(g,sid,q['grouping'],q['filter'])
        if q['qi']['enabled']:
            if q['grouping']['mode']!='atomic':raise QueryError('INVALID_REQUEST','QI requires atomic grouping')
            if q['filter']['families']!=['static'] or q['filter']['resolution_statuses']!=['exact']:
                raise QueryError('INVALID_REQUEST','QI requires the exact static hop graph')
            protected=set(tree.ancestors(focus))|set(q['pins'])
            for model in self.rules.values():
                mapping,findings=model.check(g,sid,set(g.entities),self._coverage(sid,ctx),q['filter'])
                finding_components={x for f in findings if f['status']=='forbidden_present' for x in (f['source_component_id'],f['target_component_id'])}
                protected.update(eid for eid,c in mapping.items() if 'view:component:'+digest(model.digest,c) in finding_components)
            membership,groups,qi=contract_helpers(g,sid,protected,q['qi']['max_diameter'],q['filter'])
            newgroups={};kinds={};shells={}
            for rep,atoms in part.groups.items():
                target=membership.get(rep,rep);newgroups.setdefault(target,set()).update(atoms)
                kinds[target]='qi' if target.startswith('view:qi:') else 'entity'
                parent=tree.parents.get(rep) or tree.root
                shells[target]=tree.lca(shells[target],parent) if target in shells else parent
            part=Partition(q['grouping'],newgroups,kinds,shells)
            qi['membership_handle']=self._handle('qi',dict(groups={r:sorted(m) for r,m in groups.items()},certificate={**qi,'membership_handle':None}))
        vid=self._persist_partition(sid,ctx,part,q['filter'],'context-partition-v1') if q['qi']['enabled'] or q['grouping']['mode']=='conceptual' else materialize_view(self.store,sid,g,q['grouping'],q['filter'])[0]
        return part,vid,qi

    def _get_architecture_context(self,q,ctx):
        sid=q['snapshot_id'];part,vid,qi=self._architecture(q,ctx)
        focus=q['focus_id'];g=ctx['g'];tree=ctx['tree']
        ancestors=tree.ancestors(focus)
        mapping=part.representatives
        focus_atoms=tree.leaves(focus)
        own_atom=next((a for a in tree.children[focus] if g.entities[a].kind=='scope_atom'),focus)
        focus_reps={mapping[a] for a in focus_atoms if a in mapping}
        representative=mapping.get(own_atom,next(iter(focus_reps)) if len(focus_reps)==1 else focus)
        if not focus_reps:
            raise QueryError('INVALID_REQUEST','Filter excludes the focus entity')
        data=self._payload(sid,ctx,focus_id=focus,ancestor_ids=ancestors,representative_focus_id=representative,qi=qi,boundary=[],cayley=[])
        data['view_id']=vid
        required=set(ancestors)|{representative}|set(q['pins'])
        data['nodes']=[self._node(ctx,eid,part=part,focus=focus) for eid in sorted(required)]
        selected=tree.context(focus,q['context_radius'])|set(q['pins'])
        if g.entities[focus].repo_id!='@workspace':
            selected={eid for eid in selected if g.entities[eid].repo_id==g.entities[focus].repo_id or eid in ancestors or eid in q['pins']}
        # Ancestors are orientation shells; do not turn their entire descendant
        # population into context. Include a rep when it or an atom-owner is selected.
        reps={rep for rep,members in part.groups.items() if rep in selected or any(a in selected or g.entities[a].kind=='scope_atom' and g.entities[a].parent_id in selected for a in members)}|{representative}
        if focus not in part.groups:
            subjects,_=subject_graph(g,q['filter'])
            subject_atoms={next((a for a in tree.children[s] if g.entities[a].kind=='scope_atom'),s) for s in subjects}
            focus_set=set(focus_atoms)
            reps.update(rep for rep,members in part.groups.items() if members&focus_set and members&subject_atoms)
        units=[]
        for rep in sorted(reps-required):units.append(Unit('node:'+rep,3,20,dict(nodes=[self._node(ctx,rep,part=part,focus=focus)])))
        rows=self.store.connection.execute('SELECT * FROM quotient_projections WHERE snapshot_id=? AND view_id=? ORDER BY projection_id',(sid,vid)).fetchall()
        for row in rows:
            if row['source_rep_id'] not in reps and row['target_rep_id'] not in reps:continue
            ids={row['source_rep_id'],row['target_rep_id']}
            units.append(Unit('relationship:'+row['projection_id'],2,200 if representative in ids else 150,
                              dict(nodes=[self._node(ctx,eid,part=part,focus=focus) for eid in sorted(ids)],relationships=[self._summary(sid,vid,row)])))
        if q['schema_version']=='1.1' and not q.get('include_diagnostics',False):return self._plan('get_architecture_context',q,data,units,vid)
        vertices,rels=subject_graph(g,q['filter']);descendants=set(tree.descendants(focus));scope=vertices&descendants
        for value in boundary_ratios(g,scope,q['filter']):
            value=dict(scope_id=focus,filter_hash=digest(q['filter']),**value)
            units.append(Unit('boundary:'+value['mode'],2,100,dict(boundary=[value])))
        static_vertices,static_rels=subject_graph(g,{**q['filter'],'families':['static'],'resolution_statuses':['exact'],'runtime_window':None})
        for value in cayley_bounds(scope&static_vertices,static_rels):
            value=dict(scope_id=focus,**value);units.append(Unit('cayley:'+value['component_id'],3,100,dict(cayley=[value])))
        return self._plan('get_architecture_context',q,data,units,vid)

    def _inspect_relationship_witnesses(self,q,ctx):
        sid=q['snapshot_id'];vid=q['view_id'];g=ctx['g']
        if not self.store.connection.execute('SELECT 1 FROM analysis_views WHERE snapshot_id=? AND view_id=?',(sid,vid)).fetchone():raise QueryError('NOT_FOUND','Analysis view is outside snapshot')
        if q['relationship_id']:
            ids=[q['relationship_id']]
            if ids[0] not in g.relationships:raise QueryError('NOT_FOUND','Relationship is outside snapshot')
            if q['evidence_cursor']:return self._evidence_plan(sid,ctx,vid,ids[0])
        else:
            row=self.store.connection.execute('SELECT witness_count FROM quotient_projections WHERE snapshot_id=? AND view_id=? AND projection_id=?',(sid,vid,q['projection_id'])).fetchone()
            if row is None:raise QueryError('NOT_FOUND','Projection is outside snapshot/view')
            ids=[r[0] for r in self.store.connection.execute('SELECT relationship_id FROM quotient_witness_map WHERE snapshot_id=? AND view_id=? AND projection_id=? ORDER BY relationship_id',(sid,vid,q['projection_id']))]
        data=self._payload(sid,ctx,total_witness_count=len(ids));data['view_id']=vid
        units=[];eplans={}
        for rid in ids:
            r=g.relationships[rid];nodes=[self._node(ctx,eid) for eid in sorted({r.source_id,r.target_id})]
            witness=self._witness(ctx,rid,q['projection_id']);eplans[rid]=partial(self._evidence_plan,sid,ctx,vid,rid)
            units.append(Unit('witness:'+rid,1,1000,dict(nodes=nodes,witnesses=[witness]),required=q['relationship_id'] is not None))
            for e in ctx['evidence'][rid][:q['evidence_page_size']]:
                units.append(Unit('evidence:'+e.evidence_id,2,150,dict(nodes=nodes,witnesses=[witness],evidence_handles=[self._evidence(ctx,e)])))
        plan=self._plan('inspect_relationship_witnesses',q,data,units,vid,'witnesses');plan.evidence_plans.update(eplans)
        return plan

    def _get_entity_content(self,q,ctx):
        g=ctx['g'];eid=q['entity_id'];sid=q['snapshot_id']
        if eid not in g.entities:raise QueryError('NOT_FOUND','Entity is outside snapshot')
        e=g.entities[eid];data=self._payload(sid,ctx,entity_id=eid,chunks=[]);data['nodes']=[self._node(ctx,eid)]
        if q['content_kind']=='documentation':
            if e.kind!='fragment':raise QueryError('INVALID_REQUEST','Documentation content requires a fragment entity')
            text=g.analyses['text:'+eid]['result']['text'];start=e.start_line
        else:
            if e.rel_path is None:raise QueryError('NOT_FOUND','Entity has no source')
            source=ctx['sources'].get((e.repo_id,e.rel_path))
            if source is None:raise QueryError('NOT_FOUND','Snapshot source bytes unavailable')
            raw=base64.b64decode(source['bytes_base64'])
            import io,tokenize
            encoding,_=tokenize.detect_encoding(io.BytesIO(raw).readline)
            lines=raw.decode(encoding).splitlines(keepends=True) or [''];start=q['start_line'] or e.start_line or 1;end=q['end_line'] or e.end_line or len(lines)
            if start<1 or end>len(lines) or start>end:raise QueryError('INVALID_REQUEST','Requested range is outside snapshot source')
            text=''.join(lines[start-1:end])
        units=[]
        content_lines=text.splitlines(keepends=True) or [''];stride=32 if q['schema_version']=='1.1' else 1
        for offset in range(0,len(content_lines),stride):
            block=content_lines[offset:offset+stride];line=''.join(block)
            location=dict(repo_id=e.repo_id,revision=ctx['revmap'][e.repo_id],rel_path=e.rel_path,start_line=start+offset,end_line=start+offset+len(block)-1)
            chunk=dict(source=location,text=line,sha256=hashlib.sha256(line.encode()).hexdigest(),trust='untrusted_repository_content')
            units.append(Unit('line:'+str(start+offset).zfill(12),1,10,dict(chunks=[chunk])))
        return self._plan('get_entity_content',q,data,units)

    def _find_dependants(self,q,ctx):
        g=ctx['g'];tree=ctx['tree'];eid=q['entity_id'];sid=q['snapshot_id']
        if eid not in g.entities:raise QueryError('NOT_FOUND','Entity is outside snapshot')
        subjects,_=subject_graph(g,q['filter'])
        seeds=({eid} if g.entities[eid].kind in {'function','method','attribute','constant','parameter','external_symbol'} else set(tree.descendants(eid)))&subjects
        adjacency=defaultdict(list)
        for r in selected_relationships(g,q['filter']):
            if r.family not in {'static','runtime'} or r.direction!='directed':continue
            source,target=(r.target_subject_id,r.source_subject_id) if q['direction']=='incoming' else (r.source_subject_id,r.target_subject_id)
            adjacency[source].append((target,r.relationship_id))
        queue=deque((v,0,[]) for v in sorted(seeds));visited=set(seeds);results=[];complete=True
        while queue:
            source,depth,path=queue.popleft()
            outgoing=sorted(adjacency[source])
            if depth>=q['max_depth']:
                if any(v not in visited for v,_ in outgoing):complete=False
                continue
            for target,rid in outgoing:
                if target in visited:continue
                visited.add(target);next_path=path+[rid];results.append((target,depth+1,next_path));queue.append((target,depth+1,next_path))
                if len(results)>=q['max_results']:
                    complete=not queue;queue.clear();break
        data=self._payload(sid,ctx,start_id=eid,traversal_complete=complete,results=[]);data['nodes']=[self._node(ctx,eid)]
        vid=materialize_view(self.store,sid,g,{'mode':'atomic'},q['filter'])[0];data['view_id']=vid
        units=[]
        for target,depth,path in results:
            witnesses=[self._witness(ctx,rid) for rid in path]
            nodes={target}|{x for r in witnesses for x in (r['source'],r['target'])}
            if q['schema_version']=='1.1':nodes.update(x for r in witnesses for x in (r['source_subject_id'],r['target_subject_id']))
            units.append(Unit('path:'+target,1,1000,dict(nodes=[self._node(ctx,n) for n in sorted(nodes)],witnesses=witnesses,
                              results=[dict(node_id=target,hop_count=depth,witness_path_ids=path)])))
        plan=self._plan('find_dependants',q,data,units,vid)
        for rid in {rid for _,_,path in results for rid in path}:plan.evidence_plans[rid]=partial(self._evidence_plan,sid,ctx,vid,rid)
        return plan

    def _check_architecture(self,q,ctx):
        model=self.rules.get(q['model_digest'])
        if model is None:raise QueryError('NOT_FOUND','Architecture model not loaded')
        if q['filter']['families']!=['static'] or q['filter']['resolution_statuses']!=['exact']:
            raise QueryError('INVALID_REQUEST','Conformance compares exact static facts; uncertainty is reported separately')
        eid=q['scope_id'];g=ctx['g'];tree=ctx['tree']
        if eid not in g.entities:raise QueryError('NOT_FOUND','Scope is outside snapshot')
        members=set(tree.descendants(eid))
        coverage=self._coverage(q['snapshot_id'],ctx,members)
        mapping,findings=model.check(g,q['snapshot_id'],members,coverage,q['filter'])
        data=self._payload(q['snapshot_id'],ctx,model_digest=model.digest,world_policy=model.model['world_policy'],findings=[],
            mapping_counts=dict(mapped=sum(mapping.get(v,'Unmapped')!='Unmapped' for v in members),unmapped=sum(mapping.get(v,'Unmapped')=='Unmapped' for v in members),conflicting=0))
        data['coverage']=coverage
        units=[]
        component_names={"view:component:"+digest(model.digest,name):name for name in [*model.components,'Unmapped']}
        for finding in findings:
            if not q['include_satisfied'] and finding['status'] in {'match','allowed_present','allowed_not_present','forbidden_absent'}:continue
            if finding['witness_count']:
                witness_ids=[r.relationship_id for r in selected_relationships(g,q['filter']) if r.source_subject_id in members and
                    'view:component:'+digest(model.digest,mapping.get(r.source_subject_id,'Unmapped'))==finding['source_component_id'] and
                    'view:component:'+digest(model.digest,mapping.get(r.target_subject_id,'Unmapped'))==finding['target_component_id']]
                finding['witness_handle']=self._handle('rule_witnesses',dict(snapshot_id=q['snapshot_id'],relationship_ids=witness_ids))
            nodes=[]
            for cid in sorted({finding['source_component_id'],finding['target_component_id']}):
                name=component_names[cid];members_here={v for v,c in mapping.items() if c==name}
                nodes.append(dict(id=cid,entity_id=None,kind='unmapped' if name=='Unmapped' else 'conceptual',sort='synthetic',repo_id='@workspace',language='none',qualified_name=name,parent_id=tree.root,depth=None,source=None,
                    flags=dict(is_test=False,is_generated=False,is_vendor=False,is_external=False),member_count=len(members_here),membership_handle=self._handle('members',dict(members=sorted(members_here))),ast_body_hash=None,wl_3hop_hash=None,doi=None))
            units.append(Unit('finding:'+finding['id'],1 if finding['status']=='forbidden_present' else 2,500,dict(nodes=nodes,findings=[finding])))
        return self._plan('check_architecture',q,data,units)

    def _find_similar_code(self,q,ctx):
        g=ctx['g'];eid=q['entity_id']
        if eid not in g.entities:raise QueryError('NOT_FOUND','Entity is outside snapshot')
        e=g.entities[eid];key='ast_body_hash' if q['mode']=='exact_normalized_ast' else 'wl_3hop_hash';value=getattr(e,key)
        if e.kind not in {'function','method'} or e.language!='python' or value is None:
            raise QueryError('INVALID_REQUEST','Similarity needs a supported Python function/method and a computed hash')
        if key=='ast_body_hash' and not g.analyses.get('norm:'+eid,{}).get('result',{}).get('representation'):
            raise QueryError('NOT_FOUND','Verified normalised representation unavailable')
        data=self._payload(q['snapshot_id'],ctx,entity_id=eid,normalization_version='py-ast-v1',wl_version='directed-wl3-v1',matches=[])
        data['nodes']=[self._node(ctx,eid)];units=[]
        if value:
            for other in g.entities.values():
                if other.entity_id==eid or other.kind not in {'function','method'} or other.language!='python' or getattr(other,key)!=value:continue
                if q['repo_ids'] and other.repo_id not in q['repo_ids']:continue
                if key=='ast_body_hash' and g.analyses.get('norm:'+eid,{}).get('result',{}).get('representation')!=g.analyses.get('norm:'+other.entity_id,{}).get('result',{}).get('representation'):continue
                units.append(Unit('similar:'+other.entity_id,2,20,dict(nodes=[self._node(ctx,other.entity_id)],matches=[dict(node_id=other.entity_id,match='verified_normalized_ast' if key=='ast_body_hash' else 'wl_candidate',hash=value)])))
        return self._plan('find_similar_code',q,data,units)
