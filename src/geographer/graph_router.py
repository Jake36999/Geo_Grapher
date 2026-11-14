"""Graph-scoped agent routing. Display composition never creates an analysis graph."""
from collections import Counter,OrderedDict
from contextlib import contextmanager
from pathlib import Path
import os
import threading
import time
import sqlite3
import json
import re

from .federation import Candidate,MODALITIES,TIER_WEIGHT,intent,select,utility
from .model import canonical,digest
from .service import QueryService
from .store import SnapshotStore
from .tokens import TokenCounter
from copy import deepcopy
from .provenance import enforce_reader, metadata, stratum, third_party

CODE_OPERATIONS={'search_entities','get_architecture_context','inspect_relationship_witnesses','get_entity_content','find_dependants','check_architecture','find_similar_code','viewport_frame'}
PAPER_OPERATIONS={'search_documents','get_outline','get_section','get_document','get_concept','find_by_concept','get_related','get_claim','get_annotations','get_corpus_status'}


# Compact tool surfaces for hosts that offer an agent only a few tools per turn
# (e.g. Librarian bundles: at most 6 per outside server).
TOOL_PRESETS={
    'papers':frozenset({'list_graphs','paper_search_documents','paper_get_document','paper_find_by_concept','paper_get_related','paper_get_section'}),
    'code':frozenset({'list_graphs','search_entities','get_architecture_context','find_dependants','get_entity_content','check_architecture'}),
    'cross':frozenset({'list_graphs','federated_search','list_bridges','analyze_cross_graphs','search_entities','get_entity_content'}),
    'lead':frozenset({'list_graphs','search_entities','get_architecture_context','get_entity_content','analyze_cross_graphs','compile_task_packet'}),
}
CROSS_MODES=('evolution_diff','clone_candidates','bridge_candidates','bridge_impact','theory_conformance')
CROSS_LATER=()


def offered_tools(spec):
    """None (all tools), a preset name, or a comma-separated list of tool names."""
    if spec is None or spec in ('','all'):return None
    if spec in TOOL_PRESETS:return TOOL_PRESETS[spec]
    names=frozenset(s.strip() for s in str(spec).split(',') if s.strip())
    known={op for op in CODE_OPERATIONS-{'viewport_frame'}}|{'paper_'+op for op in PAPER_OPERATIONS}|{'list_graphs','list_bridges','federated_search','analyze_cross_graphs','compile_task_packet'}
    unknown=sorted(names-known)
    if unknown or not names:raise ValueError(f"Unknown tools {unknown}; use 'all', {sorted(TOOL_PRESETS)} or tool names")
    return names


def _add_citation_handles(node,label):
    """Give every document reference a graph-qualified handle, e.g.
    'ai-research-papers/doc:152'. Agents renumbered bare doc:N IDs by position;
    a string handle naming its graph is harder to renumber or misattribute."""
    if isinstance(node,dict):
        for key in ('id','document_id'):
            ref=node.get(key)
            if isinstance(ref,str) and ref.startswith('doc:') and ref[4:].isdigit() and 'cite_as' not in node:
                node['cite_as']=f'{label}/{ref}'
        for value in node.values():_add_citation_handles(value,label)
    elif isinstance(node,list):
        for value in node:_add_citation_handles(value,label)


class GraphRouter:
    def __init__(self,catalog,allowed=None,max_result_chars=None,tools=None,semantic=None,consumer_role='lead'):
        self.catalog=catalog;self.services=OrderedDict();self.lock=threading.RLock();self.cond=threading.Condition(self.lock)
        self.leases=Counter();self.retired=set();self.borrowed=set();self.deleting=set()
        self.offered_tools=offered_tools(tools)
        self.semantic_config=semantic
        if consumer_role not in {'lead', 'research_helper', 'clerk', 'scribe'}:raise ValueError('Unknown consumer_role')
        self.consumer_role=consumer_role
        if consumer_role in {'clerk','scribe'} and allowed is None:
            raise ValueError('THIRD_PARTY_SCOPE: Clerk/Scribe require an explicit own-graph allow-list')
        if max_result_chars is not None and (type(max_result_chars) is not int or max_result_chars<1000):
            raise ValueError('max_result_chars must be an integer of at least 1000')
        self.max_result_chars=max_result_chars
        # Optional per-connection allow-list: scoping becomes an access boundary,
        # so an agent cannot hop to a graph its library was not given.
        self.allowed=None if allowed is None else frozenset(allowed)
        if self.allowed is not None:
            if not self.allowed:raise ValueError('An allow-list must name at least one graph')
            for gid in self.allowed:enforce_reader(catalog.graph(gid), consumer_role=consumer_role)

    def permit(self,graph_id):
        if self.allowed is not None and graph_id not in self.allowed:
            raise ValueError('graph_id is not available on this connection')
        enforce_reader(self.catalog.graph(graph_id), consumer_role=self.consumer_role)

    def label(self,graph_id):
        return self.catalog.graph(graph_id)['label']

    def resolve(self,graph_ref):
        """A graph_id, or an unambiguous graph label, to the canonical graph_id.

        Errors list the graphs this connection may use, so an agent that mistyped
        a 24-hex ID can recover instead of guessing."""
        if graph_ref in (None,'') and self.allowed is not None and len(self.allowed)==1:
            return next(iter(self.allowed))  # A single-graph connection is unambiguous.
        if not isinstance(graph_ref,str) or not graph_ref:raise ValueError('graph_id is required; no all-graph fallback')
        graphs=self.catalog.graphs()
        visible=[g for g in graphs if (self.allowed is None or g['graph_id'] in self.allowed)
                 and not json.loads(g['profile_json']).get('disabled')]
        if any(g['graph_id']==graph_ref for g in visible):return graph_ref
        named=[g for g in visible if g['label'].casefold()==graph_ref.casefold()]
        if len(named)==1:return named[0]['graph_id']
        choices=', '.join(f"{g['label']} ({g['graph_id']})" for g in visible[:12])
        if len(named)>1:raise ValueError(f'Graph label {graph_ref!r} is ambiguous; use a graph_id: {choices}')
        if any(graph_ref in (g['graph_id'],g['label']) for g in graphs):
            raise ValueError('graph_id is not available on this connection; available: '+choices)
        raise ValueError(f'Unknown graph_id {graph_ref[:80]!r}; available: {choices}')

    def bridges(self,graph_ids):
        graph_ids=[self.resolve(gid) for gid in graph_ids]
        for gid in graph_ids:self.permit(gid)
        # Lineage state (master G5) so read-only clients can see staleness.
        return [{**b,'state':self.catalog.bridge_state(b['bridge_id'])} for b in self.catalog.bridges(graph_ids)]

    def bridge_proposals(self,graph_ids,status='pending'):
        graph_ids=[self.resolve(gid) for gid in graph_ids]
        for gid in graph_ids:self.permit(gid)
        return self.catalog.proposals(graph_ids,status)

    def propose_bridges(self,graph_a,graph_b,kind,limit=50):
        a,b=self.resolve(graph_a),self.resolve(graph_b);self.permit(a);self.permit(b)
        return self.catalog.propose_bridges(a,b,kind=kind,limit=limit)

    def review_proposal(self,proposal_id,decision,rationale):
        p=self.catalog.proposal(proposal_id);self.permit(p['source_graph']);self.permit(p['target_graph'])
        return self.catalog.review_proposal(proposal_id,decision,rationale)

    def close(self):
        with self.lock:
            for key,(store,_) in self.services.items():
                if key not in self.borrowed:store.close()
            self.services.clear();self.leases.clear();self.retired.clear();self.borrowed.clear()

    def bind_existing(self,graph_id,service):
        """Share the original main service, including its rules and query state."""
        row=self.catalog.graph(graph_id)
        actual=service.store.connection.execute('PRAGMA database_list').fetchone()[2]
        if not actual or not Path(actual).samefile(row['code_database']):raise ValueError('Main service does not own this graph database')
        with self.lock:
            key,current=self._open(graph_id) # Retains the normal ownership check.
            if current is service:return
            if self.leases[key]:raise ValueError('Cannot replace a leased graph service')
            self.services[key][0].close();self.services[key]=(service.store,service);self.borrowed.add(key)

    def _open(self,graph_id):
        self.permit(graph_id)
        row=self.catalog.graph(graph_id)
        key=(graph_id,row['code_database'])
        with self.lock:
            if graph_id in self.deleting:raise ValueError('GRAPH_BUSY: the graph is being deleted')
            if key not in self.services:
                from .cursor_secret import persisted_secret
                path=Path(row['code_database'])
                if not path.is_file():raise ValueError('Graph store missing')
                with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as check:
                    if not check.execute("SELECT 1 FROM sqlite_master WHERE name='snapshots'").fetchone():raise ValueError('Graph store schema missing')
                    owners={r[0] for r in check.execute("SELECT DISTINCT repo_id FROM snapshots WHERE repo_id<>'@workspace'")}
                if owners!=set(json.loads(row['profile_json']).get('owner_repo_ids',[graph_id])):
                    raise ValueError('Store ownership does not match graph_id')
                store=SnapshotStore(path)
                self.services[key]=(store,QueryService(store,secret=persisted_secret(path)))
                # A newer generation supersedes older ones; close each once idle.
                for old in [k for k in self.services if k[0]==graph_id and k!=key]:
                    self.retired.add(old);self._close_if_idle(old)
            self.services.move_to_end(key)
            self.services[key][1].graph_provenance = metadata(row)
            return key,self.services[key][1]

    def _close_if_idle(self,key):
        if key in self.retired and not self.leases[key] and key in self.services:
            store=self.services.pop(key)[0]
            if key not in self.borrowed:store.close()
            self.borrowed.discard(key);self.retired.discard(key);self.leases.pop(key,None)

    def service(self,graph_id):
        return self._open(graph_id)[1]

    def acquire(self,graph_id):
        with self.lock:
            key,service=self._open(graph_id);self.leases[key]+=1
            return key,service

    def release(self,key):
        with self.lock:
            self.leases[key]-=1;self._close_if_idle(key);self.cond.notify_all()

    def retire_graph(self,graph_id,timeout=10.0):
        """Retire every service generation of a graph and wait until all are closed."""
        deadline=time.monotonic()+timeout
        with self.cond:
            self.deleting.add(graph_id)
            keys=[k for k in self.services if k[0]==graph_id]
            for key in keys:self.retired.add(key);self._close_if_idle(key)
            while any(k in self.services for k in keys):
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    self.retired.difference_update(keys);self.deleting.discard(graph_id)
                    raise ValueError('GRAPH_BUSY: the graph still has active requests')
                self.cond.wait(remaining)

    def unretire_graph(self,graph_id):
        """Clear the deletion tombstone once a delete finished or was abandoned."""
        with self.cond:self.deleting.discard(graph_id)

    @contextmanager
    def lease(self,graph_id):
        key,service=self.acquire(graph_id)
        try:yield service
        finally:self.release(key)

    def query(self,graph_id,operation,request):
        graph_id=self.resolve(graph_id)
        if not isinstance(request,dict):raise ValueError('request must be an object')
        from .task_packets import check_profile
        check_profile(request.get('budget',{}).get('profile'),request.get('budget',{}).get('limit_tokens'))
        self.permit(graph_id)
        graph=self.catalog.graph(graph_id);label=graph['label']
        enforce_reader(graph, consumer_role=self.consumer_role, profile=request.get('budget',{}).get('profile'))
        if operation in CODE_OPERATIONS:
            counter=TokenCounter(request.get('budget',{}).get('tokenizer','o200k_base'),request.get('budget',{}).get('allow_byte_fallback',False))
            limit=request.get('budget',{}).get('limit_tokens')
            if type(limit) is not int or limit<256:raise ValueError('Code query token budget required')
            inner=deepcopy(request);inner['budget']['limit_tokens']=max(256,limit-160)
            for _ in range(4):
                with self.lease(graph_id) as service:result=service.query(operation,inner)
                envelope=dict(graph_id=graph_id,graph_label=label,result=result,routing_budget=dict(limit_tokens=limit,used_tokens=0), **metadata(graph))
                for _ in range(12):
                    count=counter.count(envelope)
                    if count==envelope['routing_budget']['used_tokens']:break
                    envelope['routing_budget']['used_tokens']=count
                if count<=limit and counter.count(envelope)==count:return envelope
                inner['budget']['limit_tokens']=max(256,inner['budget']['limit_tokens']-(count-limit)-32)
            return dict(graph_id=graph_id,graph_label=label,error=dict(code='GRAPH_BUDGET_TOO_SMALL',message='Increase budget for the complete routed envelope'))
        elif operation.startswith('paper_') and operation[6:] in PAPER_OPERATIONS:
            if not graph['paper_database']:raise ValueError('This graph has no attached paper corpus')
            from pipeline import mcp_doc_graph as paper
            from pipeline.query_context import DATABASE_SCOPE
            token=DATABASE_SCOPE.set(Path(graph['paper_database']))
            try:result=paper._TOOLS[operation[6:]](**request)
            finally:DATABASE_SCOPE.reset(token)
            _add_citation_handles(result,label)
            if third_party(graph):
                def mark(value):
                    if isinstance(value,dict):
                        if 'cite_as' in value:value['provenance']='third_party'
                        for child in list(value.values()):mark(child)
                    elif isinstance(value,list):
                        for child in value:mark(child)
                mark(result)
        else:raise ValueError('Unknown graph operation')
        return self._fit(dict(graph_id=graph_id,graph_label=label,result=result, **metadata(graph)))

    # Top-level paged lists in paper results, and the pagination object each one owns.
    PAGED={'results':'pagination','documents':'pagination','related':'pagination','claims':'claim_pagination','matches':'concept_pagination'}

    def _fit(self,envelope):
        """Respect a client's size cap (e.g. Librarian withholds structured results
        over 8,000 chars) by dropping whole trailing items and moving next_offset back,
        never by cutting JSON. The agent pages for the rest."""
        limit=self.max_result_chars;result=envelope.get('result')
        if not limit or not isinstance(result,dict):return envelope
        size=lambda:len(json.dumps(envelope,ensure_ascii=False,default=str))
        trimmed=0
        while size()>limit:
            lists=[(k,v) for k,v in result.items() if k in self.PAGED and isinstance(v,list) and len(v)>1]
            if not lists:break
            key,items=max(lists,key=lambda kv:len(json.dumps(kv[1],ensure_ascii=False,default=str)))
            items.pop();trimmed+=1
            page=result.get(self.PAGED[key])
            if isinstance(page,dict):page.update(next_offset=page.get('offset',0)+len(items),truncated=True)
            if key in ('results','documents') and isinstance(result.get('count'),int):result['count']=len(items)
        if trimmed:
            result['size_limit']=dict(max_chars=limit,items_withheld=trimmed,
                note='Trimmed to fit this connection; page with the next_offset shown to see the rest.')
        return envelope

    def summary(self):
        rows=[]
        for graph in self.catalog.graphs():
            if json.loads(graph['profile_json']).get('disabled'):continue
            if self.allowed is not None and graph['graph_id'] not in self.allowed:continue
            availability='available';error=None;count=None
            try:
                with self.lease(graph['graph_id']) as service:
                    with service.lock:
                        count=service.store.connection.execute('SELECT count(*) FROM entities WHERE snapshot_id=?',(graph['snapshot_id'],)).fetchone()[0]
            except (ValueError,sqlite3.DatabaseError,OSError) as exc:
                availability='unavailable';error=str(exc)[:300]
            profile=json.loads(graph['profile_json'])
            rows.append(dict(label=graph['label'],graph_id=graph['graph_id'],root_path=graph['root_path'],
                graph_kind=profile.get('graph_kind','project'),repo_ids=profile.get('owner_repo_ids',[graph['graph_id']]),
                source_graph_ids=[s['graph_id'] for s in profile.get('source_graphs',[])],
                owned_store=self.catalog.owns_store(graph),bridge_count=self.catalog.bridge_count(graph['graph_id']),copied_from=profile.get('copied_from'),
                snapshot_id=graph['snapshot_id'],entity_count=count,papers_available=bool(graph['paper_database']),availability=availability,error=error,
                stratum=stratum(graph), **metadata(graph)))
        return dict(graphs=rows,scope_policy='one_graph_per_call; explicit federation only',composition='display_only')

    def _stratum(self,graph):
        """(trust_tier, modality) from profile_json['stratum'], else the default:
        silver code, or silver paper for a paper-only graph (papers, 0 code entities)."""
        stratum=json.loads(graph['profile_json']).get('stratum')
        if isinstance(stratum,dict) and stratum.get('trust_tier') in TIER_WEIGHT and stratum.get('modality') in MODALITIES:
            return stratum['trust_tier'],stratum['modality']
        if graph['paper_database']:
            with self.lease(graph['graph_id']) as service:
                with service.lock:
                    code=service.store.connection.execute("SELECT count(*) FROM entities WHERE snapshot_id=? AND kind IN ('class','function','method','attribute','constant')",(graph['snapshot_id'],)).fetchone()[0]
            if not code:return 'silver','paper'
        return 'silver','code'

    @staticmethod
    def _hit_facts(envelope,query):
        """1-based ranks of the returned hits and how many name the query exactly."""
        data=(envelope.get('result') or {}).get('data') or {}
        hits=data.get('hits') or []
        names={n.get('id'):str(n.get('qualified_name',''))for n in data.get('nodes') or []}
        needle=query.casefold();exact=0
        for hit in hits:
            name=names.get(hit.get('node_id'),'').casefold()
            if name and (name==needle or name.rsplit('.',1)[-1]==needle):exact+=1
        return list(range(1,len(hits)+1)),exact

    @staticmethod
    def _nested_error(envelope):
        """The error object of a routed envelope: top level, or nested under `result`."""
        if not isinstance(envelope,dict):return None
        for holder in (envelope,envelope.get('result')):
            if isinstance(holder,dict) and isinstance(holder.get('error'),dict):return holder['error']
        return None

    def analyze_cross_graphs(self,graph_ids,mode,*,limit_tokens=4096,cursor=None,profile=None,
                             start=None,max_hops=6,pinned_graphs=(),theory_graph=None,code_graph=None):
        """cross-graph-v1: one mode-parameterised read-only analysis over explicitly selected graphs.

        Items are packed whole under an exact complete-envelope cap; every item endpoint has a node
        (endpoint closure); a snapshot-bound cursor resumes in order. Graph-local rankings only.
        """
        from .cross_graph import clone_pairs,diff_graphs,pack_items
        from .task_packets import check_profile
        check_profile(profile,limit_tokens)
        if mode in CROSS_LATER:raise ValueError(f'MODE_NOT_AVAILABLE: {mode} arrives in a later wave')
        if mode not in CROSS_MODES:raise ValueError(f'Unknown mode; choose one of {list(CROSS_MODES)}')
        if not isinstance(graph_ids,list):raise ValueError('graph_ids must be a list')
        graph_ids=sorted(self.resolve(g) for g in graph_ids)
        want=(2,2) if mode in {'evolution_diff','theory_conformance'} else (2,8)
        if not want[0]<=len(graph_ids)<=want[1] or len(set(graph_ids))!=len(graph_ids):
            raise ValueError(f'{mode} needs {want[0]}' + ('' if want[0]==want[1] else f'..{want[1]}') + ' distinct graph IDs')
        if type(limit_tokens) is not int or not 1024<=limit_tokens<=32768:raise ValueError('limit_tokens must be 1024..32768')
        for gid in graph_ids:self.permit(gid)
        rows={gid:self.catalog.graph(gid) for gid in graph_ids}
        if mode=='bridge_impact':
            if not isinstance(start,dict) or set(start)!={'graph_id','ref'}:raise ValueError('IMPACT_START_REQUIRED')
            start=dict(start,graph_id=self.resolve(start['graph_id']))
            pinned_graphs=sorted(self.resolve(g) for g in pinned_graphs)
            if start['graph_id'] not in graph_ids or not set(pinned_graphs)<=set(graph_ids):raise ValueError('Impact endpoints must be selected graphs')
        if mode=='theory_conformance':
            if not theory_graph or not code_graph:raise ValueError('CONFORMANCE_ROLES_REQUIRED')
            theory_graph,code_graph=self.resolve(theory_graph),self.resolve(code_graph)
            if theory_graph==code_graph or {theory_graph,code_graph}!=set(graph_ids):raise ValueError('Conformance roles must identify the selected pair')
        extra=(start,max_hops,pinned_graphs,theory_graph,code_graph,
            [(b['bridge_id'],self.catalog.bridge_state(b['bridge_id'])) for b in self.catalog.bridges(graph_ids)]) if mode in {'bridge_impact','theory_conformance'} else ()
        key=digest(mode,graph_ids,[rows[g]['snapshot_id'] for g in graph_ids],extra)[:16]
        offset=0
        if cursor is not None:
            if not isinstance(cursor,str) or not re.fullmatch(r'[0-9a-f]{16}:[0-9]{1,9}',cursor):raise ValueError('INVALID_CURSOR')
            if cursor.split(':')[0]!=key:raise ValueError('STALE_CURSOR: a selected graph has a new snapshot; restart without a cursor')
            offset=int(cursor.split(':')[1])
        label={g:rows[g]['label'] for g in graph_ids}
        names={}
        def node(gid,ref,qualified_name=None):
            return dict(graph_id=gid,id=ref,qualified_name=qualified_name,cite_as=f"{label[gid]}/{ref}")
        def lookup(gid,eids):
            from .store import SnapshotStore
            want_ids=sorted(set(eids)-set(names.get(gid,{})))
            if want_ids:
                with SnapshotStore(rows[gid]['code_database']) as store:
                    for start in range(0,len(want_ids),500):
                        chunk=want_ids[start:start+500]
                        for eid,qn in store.connection.execute('SELECT entity_id,qualified_name FROM entities WHERE snapshot_id=? AND entity_id IN (%s)'%','.join('?'*len(chunk)),(rows[gid]['snapshot_id'],*chunk)):
                            names.setdefault(gid,{})[eid]=qn
            return names.get(gid,{})
        omitted=[];bundles=[];counts={}
        if mode=='evolution_diff':
            a,b=graph_ids
            try:result=diff_graphs(self.catalog,a,b)
            except ValueError as exc:
                result=None;omitted=[dict(graph_id=g,reason=str(exc).split(':')[0]) for g in graph_ids]
            if result is not None:
                counts=dict(classes=result['classes'],quotient_cycle_delta=result['quotient_cycle_delta']['counts'])
                for p in result['pairs']:
                    ends=[node(a,'entity:'+p['entity_a'],p['qualified_name_a']),node(b,'entity:'+p['entity_b'],p['qualified_name_b'])]
                    bundles.append(dict(item=dict(kind='pair',**{'class':p['class']},endpoints=[dict(graph_id=n['graph_id'],id=n['id']) for n in ends]),nodes=ends))
                for gid,side in ((a,'exclusive_a'),(b,'exclusive_b')):
                    qn=lookup(gid,result[side])
                    for eid in result[side]:
                        end=node(gid,'entity:'+eid,qn.get(eid))
                        bundles.append(dict(item=dict(kind='exclusive',**{'class':'STRATUM_EXCLUSIVE'},endpoints=[dict(graph_id=gid,id=end['id'])]),nodes=[end]))
                for entry in result['quotient_cycle_delta']['entries']:
                    bundles.append(dict(item=dict(kind='quotient_cycle',**entry,endpoints=[]),nodes=[]))
        elif mode=='clone_candidates':
            try:result=clone_pairs(self.catalog,graph_ids,limit=5000)
            except ValueError as exc:
                result=None;omitted=[dict(graph_id=g,reason=str(exc).split(':')[0]) for g in graph_ids]
            if result is not None:
                by={}
                for p in result['pairs']:
                    by.setdefault(p['graph_a'],[]).append(p['entity_a']);by.setdefault(p['graph_b'],[]).append(p['entity_b'])
                qn={g:lookup(g,ids) for g,ids in by.items()}
                counts=dict(pairs=len(result['pairs']),truncated=result['truncated'])
                for p in result['pairs']:
                    ends=[node(p['graph_a'],'entity:'+p['entity_a'],qn[p['graph_a']].get(p['entity_a'])),node(p['graph_b'],'entity:'+p['entity_b'],qn[p['graph_b']].get(p['entity_b']))]
                    bundles.append(dict(item=dict(kind='clone',match=p['match'],endpoints=[dict(graph_id=n['graph_id'],id=n['id']) for n in ends]),nodes=ends))
        elif mode=='bridge_candidates':
            from .bridges import alias_policy,code_candidates,paper_candidates,score_pairs
            policy=alias_policy();sides={}
            for gid in graph_ids:
                try:
                    r=rows[gid]
                    sides[gid]=paper_candidates(r['paper_database'],policy) if r['paper_database'] else code_candidates(r['code_database'],r['snapshot_id'],policy) if r['snapshot_id'] else []
                except (ValueError,sqlite3.DatabaseError,OSError) as exc:omitted.append(dict(graph_id=gid,reason=type(exc).__name__))
            ok=[g for g in graph_ids if g in sides]
            pairs=[(a,b,p) for i,a in enumerate(ok) for b in ok[i+1:] for p in score_pairs(sides[a],sides[b],200)]
            pairs.sort(key=lambda x:(-x[2]['score'],x[0],x[2]['source_ref'],x[1],x[2]['target_ref']))
            counts=dict(candidates=len(pairs))
            for a,b,p in pairs:
                qa=lookup(a,[p['source_ref'][7:]]) if p['source_ref'].startswith('entity:') and not rows[a]['paper_database'] else {}
                qb=lookup(b,[p['target_ref'][7:]]) if p['target_ref'].startswith('entity:') and not rows[b]['paper_database'] else {}
                ends=[node(a,p['source_ref'],qa.get(p['source_ref'][7:])),node(b,p['target_ref'],qb.get(p['target_ref'][7:]))]
                bundles.append(dict(item=dict(kind='bridge_candidate',score=p['score'],features=p['features'],status='unreviewed',
                    endpoints=[dict(graph_id=n['graph_id'],id=n['id']) for n in ends]),nodes=ends))
        hint=None
        if mode in {'bridge_impact','theory_conformance'}:
            from .cross_graph import bridge_impact,conformance
            if mode=='bridge_impact':
                result=bridge_impact(self.catalog,(start['graph_id'],start['ref']),max_hops=max_hops,pinned_graphs=set(pinned_graphs),graph_ids=set(graph_ids))
                counts=dict(bridges_considered=result['bridges_considered'],dependants=len(result['dependants']))
                for item in result['dependants']:
                    ends={(item['graph_id'],item['ref'])}
                    for step in item['path']:
                        for end in ('from','to'):ends.add((step[end]['graph_id'],step[end]['ref']))
                    nodes=[node(g,r) for g,r in sorted(ends)]
                    bundles.append(dict(item=dict(kind='bridge_impact',**item,endpoints=[dict(graph_id=n['graph_id'],id=n['id']) for n in nodes]),nodes=nodes))
            else:
                result=conformance(self.catalog,theory_graph,code_graph);hint=result['hint']
                counts=dict(bridges_considered=result['bridges_considered'],findings=len(result['findings']))
                for item in result['findings']:
                    nodes=[node(g,item[k]) for g,k in ((theory_graph,'theory_ref'),(code_graph,'code_ref')) if item[k]]
                    bundles.append(dict(item=dict(kind='theory_conformance',**item,endpoints=[dict(graph_id=n['graph_id'],id=n['id']) for n in nodes]),nodes=nodes))
        if offset>len(bundles):raise ValueError('INVALID_CURSOR')
        header=dict(engine_version='cross-graph-v1',mode=mode,graph_ids=graph_ids,ranking='independent_per_graph_no_global_rank',
            omitted_graphs=omitted,
            scope_anchor_identities=[dict(graph_id=g,snapshot_id=rows[g]['snapshot_id'],id='root',qualified_name=label[g],basis='snapshot_identity_only') for g in graph_ids],
            header=dict(counts=counts,total_items=len(bundles),offset=offset),
            next_cursor=key+':'+'9'*9,limit_tokens=limit_tokens)  # placeholder cursor reserves its maximum size
        if hint is not None:header['hint']=hint
        counter=TokenCounter();budget=limit_tokens
        size=lambda o:len(json.dumps(o,ensure_ascii=False,default=str))
        for _ in range(8):
            out=pack_items(header,bundles[offset:],budget,counter)
            if not out['items'] and offset<len(bundles):raise ValueError('BUDGET_TOO_SMALL: the next item does not fit; raise limit_tokens')
            end=offset+len(out['items'])
            out['next_cursor']=f'{key}:{end}' if end<len(bundles) else None
            out['used_tokens']=counter.count(out)
            # A connection size cap (e.g. a Librarian client withholds results over ~8,000 chars): shrink the
            # token budget so whole items drop and the cursor resumes, instead of the client withholding all.
            if not self.max_result_chars or size(out)<=self.max_result_chars or len(out['items'])<=1:break
            budget=max(256,int(budget*self.max_result_chars/size(out)*0.9))
        if self.max_result_chars and size(out)>self.max_result_chars:
            raise ValueError('RESULT_TOO_LARGE: one item exceeds this connection\'s max_result_chars')
        return out

    def compile_task_packet(self,graph_id,anchors,instruction,*,profile='tier3_leaf',upstream=()):
        from .task_packets import compile_packet
        return compile_packet(self,graph_id,anchors,instruction,profile=profile,upstream=upstream)

    def federated_search(self,graph_ids,query,*,limit_tokens=8192,mode='documentation',profile=None,agent=False):
        from .task_packets import check_profile
        check_profile(profile,limit_tokens)
        if isinstance(graph_ids,list):graph_ids=[self.resolve(gid) for gid in graph_ids]
        if not isinstance(graph_ids,list) or not 2<=len(graph_ids)<=8 or len(set(graph_ids))!=len(graph_ids):raise ValueError('Choose 2..8 distinct graph IDs explicitly')
        minimum=256 if profile is not None else 2048
        if type(limit_tokens) is not int or not minimum<=limit_tokens<=32768:raise ValueError(f'Federation budget must be {minimum}..32768 tokens')
        if mode not in {'lexical','documentation','hybrid'} or not isinstance(query,str) or not 1<=len(query)<=500:raise ValueError('Invalid search mode or query')
        for gid in graph_ids:self.permit(gid)
        graphs=sorted((self.catalog.graph(gid) for gid in graph_ids),key=lambda g:g['graph_id'])
        for graph in graphs:enforce_reader(graph, consumer_role=self.consumer_role, profile=profile)
        counter=TokenCounter();kind=intent(query)
        # No pre-split (F21): every graph is queried against the whole budget less the response
        # skeleton (graph ids, omission rows, selection maps). pc-mckp-v1 then selects whole
        # envelopes under the total, so a graph whose smallest envelope cannot fit is omitted.
        skeleton=dict(graph_ids=graph_ids,results=[],omitted=[dict(graph_id=g['graph_id'],reason='no_relevant_hits') for g in graphs],
            ranking='independent_per_graph_no_global_rank',tokenizer='o200k_base',used_tokens=limit_tokens,
            selection=dict(method='pc-mckp-v1',tiers={g['graph_id']:'omit' for g in graphs},utility={g['graph_id']:0 for g in graphs}))
        per_graph=max(256,min(limit_tokens,32768)-counter.count(skeleton))
        envelopes={};unavailable={};candidates=[];utilities={};budget_short=set()
        for graph in graphs:
            gid=graph['graph_id']
            # One unavailable graph must not hide the healthy graphs' results.
            try:
                tiers={}
                for tier,limit in (('full',5),('compact',2)):
                    req=dict(schema_version='1.1',request_id='federated-search',snapshot_id=graph['snapshot_id'],
                        budget=dict(limit_tokens=per_graph,tokenizer='o200k_base',allow_byte_fallback=False),query=query,
                        mode=mode,repo_ids=[],kinds=[],limit=limit,cursor=None)
                    if agent:req['identity_mode']='canonical_map'
                    envelope=self.query(gid,'search_entities',req)
                    # The router nests a service error under `result`; it is never "no hits".
                    err=self._nested_error(envelope)
                    if err is not None:
                        if str(err.get('code','')).endswith('BUDGET_TOO_SMALL'):continue
                        raise ValueError(str(err.get('message','graph error')))
                    tiers[tier]=envelope
                if not tiers:budget_short.add(gid)
                trust,modality=self._stratum(graph)
                try:store_mb=os.path.getsize(graph['code_database'])/1_000_000
                except OSError:store_mb=0.
            except (ValueError,sqlite3.DatabaseError,OSError) as exc:
                unavailable[gid]=str(exc)[:300];continue
            envelopes[gid]=tiers;utilities[gid]={}
            for tier,envelope in tiers.items():
                ranks,exact=self._hit_facts(envelope,query)
                # With at most two full hits the compact envelope carries nothing less.
                if tier=='compact' and 'full' in tiers and len(self._hit_facts(tiers['full'],query)[0])<=2:continue
                utilities[gid][tier]=utility(trust,modality,kind,store_mb,ranks,exact)
                candidates.append(Candidate(gid,tier,counter.count(envelope),utilities[gid][tier]))
        def assemble(chosen):
            response=dict(graph_ids=graph_ids,results=[],omitted=[],ranking='independent_per_graph_no_global_rank',tokenizer='o200k_base',used_tokens=0,
                selection=dict(method='pc-mckp-v1',tiers={},utility={}))
            for graph in graphs:
                gid=graph['graph_id'];tier=chosen.get(gid,'omit')
                response['selection']['tiers'][gid]=tier
                response['selection']['utility'][gid]=0 if gid in unavailable else utilities[gid].get(tier,0)
                if gid in unavailable:response['omitted'].append(dict(graph_id=gid,reason='GRAPH_UNAVAILABLE',message=unavailable[gid]))
                else:
                    if tier!='omit':response['results'].append(envelopes[gid][tier])
                    if tier!='full':
                        reason='budget_compact_only' if tier=='compact' else 'budget_omitted' if gid in budget_short or any(utilities[gid].values()) else 'no_relevant_hits'
                        response['omitted'].append(dict(graph_id=gid,reason=reason))
            return response
        def fit(response):
            for _ in range(12):
                count=counter.count(response)
                if count==response['used_tokens']:break
                response['used_tokens']=count
            count=counter.count(response)
            return count if count==response['used_tokens'] else limit_tokens+1
        # Envelopes are indivisible: a partial node/edge list would break endpoint closure.
        # The skeleton prices everything but the envelopes; overflow found after exact
        # counting of the assembled response tightens the budget and selects again.
        budget=limit_tokens-fit(assemble({}))
        for _ in range(5):
            response=assemble(select(candidates,budget))
            count=fit(response)
            if count<=limit_tokens:return self._fit_federation(response,limit_tokens,counter,query,mode,agent)
            budget-=count-limit_tokens
        response=assemble({})
        if fit(response)>limit_tokens:raise ValueError('Federation metadata exceeds token budget')
        return self._fit_federation(response,limit_tokens,counter,query,mode,agent)

    def _fit_federation(self,response,limit_tokens,counter,query,mode,agent=False):
        """Shrink whole hit envelopes, then omit graphs, in utility order."""
        cap=self.max_result_chars
        if not cap and not agent:return response
        def present():
            out=deepcopy(response) if agent else response
            if agent:
                from .agent_requests import canonical_flat
                for env in out['results']:
                    canonical_flat(self,env['graph_id'],self.catalog.graph(env['graph_id']),env)
                    for _ in range(12):
                        count=counter.count(env)
                        if env['routing_budget']['used_tokens']==count:break
                        env['routing_budget']['used_tokens']=count
            for _ in range(12):
                count=counter.count(out)
                if count==out['used_tokens']:break
                out['used_tokens']=count
            return out
        while True:
            projected=present()
            if (not cap or len(json.dumps(projected,ensure_ascii=False))<=cap) and counter.count(projected)<=limit_tokens:return projected
            if not response['results']:raise ValueError('Federation metadata exceeds connection cap')
            envelope=min(response['results'],key=lambda r:(response['selection']['utility'][r['graph_id']],r['graph_id']))
            gid=envelope['graph_id'];d=envelope['result'].get('data',{});hits=d.get('hits',[])
            response['omitted']=[r for r in response['omitted'] if r['graph_id']!=gid]
            response['omitted'].append(dict(graph_id=gid,reason='size_limit'))
            if len(hits)>1:
                # Re-pack fewer whole hits so inner wire counts, cursors and
                # endpoint definitions stay valid as well as the outer budget.
                graph=self.catalog.graph(gid)
                req=dict(schema_version='1.1',request_id='federated-size-fit',snapshot_id=graph['snapshot_id'],
                    budget=dict(limit_tokens=envelope['routing_budget']['limit_tokens'],tokenizer='o200k_base',allow_byte_fallback=False),
                    query=query,mode=mode,repo_ids=[],kinds=[],limit=len(hits)-1,cursor=None)
                if agent:req['identity_mode']='canonical_map'
                smaller=self.query(gid,'search_entities',req)
                if self._nested_error(smaller):
                    response['results'].remove(envelope);response['selection']['tiers'][gid]='omit';response['selection']['utility'][gid]=0
                else:
                    response['results'][response['results'].index(envelope)]=smaller
                    response['selection']['tiers'][gid]='compact'
                    trust,modality=self._stratum(graph);ranks,exact=self._hit_facts(smaller,query)
                    response['selection']['utility'][gid]=utility(trust,modality,intent(query),os.path.getsize(graph['code_database'])/1_000_000,ranks,exact)
            else:
                response['results'].remove(envelope);response['selection']['tiers'][gid]='omit'
                response['selection']['utility'][gid]=0
