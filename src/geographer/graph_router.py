"""Graph-scoped agent routing. Display composition never creates an analysis graph."""
from collections import Counter,OrderedDict
from contextlib import contextmanager
from pathlib import Path
import os
import threading
import sqlite3
import json

from .federation import Candidate,MODALITIES,TIER_WEIGHT,intent,select,utility
from .model import canonical
from .service import QueryService
from .store import SnapshotStore
from .tokens import TokenCounter
from copy import deepcopy

CODE_OPERATIONS={'search_entities','get_architecture_context','inspect_relationship_witnesses','get_entity_content','find_dependants','check_architecture','find_similar_code','viewport_frame'}
PAPER_OPERATIONS={'search_documents','get_outline','get_section','get_document','get_concept','find_by_concept','get_related','get_claim','get_annotations','get_corpus_status'}


# Compact tool surfaces for hosts that offer an agent only a few tools per turn
# (e.g. Librarian bundles: at most 6 per outside server).
TOOL_PRESETS={
    'papers':frozenset({'list_graphs','paper_search_documents','paper_get_document','paper_find_by_concept','paper_get_related','paper_get_section'}),
    'code':frozenset({'list_graphs','search_entities','get_architecture_context','find_dependants','get_entity_content','check_architecture'}),
}


def offered_tools(spec):
    """None (all tools), a preset name, or a comma-separated list of tool names."""
    if spec is None or spec in ('','all'):return None
    if spec in TOOL_PRESETS:return TOOL_PRESETS[spec]
    names=frozenset(s.strip() for s in str(spec).split(',') if s.strip())
    known={op for op in CODE_OPERATIONS-{'viewport_frame'}}|{'paper_'+op for op in PAPER_OPERATIONS}|{'list_graphs','list_bridges','federated_search'}
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
    def __init__(self,catalog,allowed=None,max_result_chars=None,tools=None):
        self.catalog=catalog;self.services=OrderedDict();self.lock=threading.RLock()
        self.leases=Counter();self.retired=set();self.borrowed=set()
        self.offered_tools=offered_tools(tools)
        if max_result_chars is not None and (type(max_result_chars) is not int or max_result_chars<1000):
            raise ValueError('max_result_chars must be an integer of at least 1000')
        self.max_result_chars=max_result_chars
        # Optional per-connection allow-list: scoping becomes an access boundary,
        # so an agent cannot hop to a graph its library was not given.
        self.allowed=None if allowed is None else frozenset(allowed)
        if self.allowed is not None:
            if not self.allowed:raise ValueError('An allow-list must name at least one graph')
            for gid in self.allowed:catalog.graph(gid)

    def permit(self,graph_id):
        if self.allowed is not None and graph_id not in self.allowed:
            raise ValueError('graph_id is not available on this connection')

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
        visible=[g for g in graphs if self.allowed is None or g['graph_id'] in self.allowed]
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
        return self.catalog.bridges(graph_ids)

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
            if key not in self.services:
                from .server import persisted_secret
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
            self.leases[key]-=1;self._close_if_idle(key)

    @contextmanager
    def lease(self,graph_id):
        key,service=self.acquire(graph_id)
        try:yield service
        finally:self.release(key)

    def query(self,graph_id,operation,request):
        graph_id=self.resolve(graph_id)
        if not isinstance(request,dict):raise ValueError('request must be an object')
        self.permit(graph_id)
        graph=self.catalog.graph(graph_id);label=graph['label']
        if operation in CODE_OPERATIONS:
            counter=TokenCounter(request.get('budget',{}).get('tokenizer','o200k_base'),request.get('budget',{}).get('allow_byte_fallback',False))
            limit=request.get('budget',{}).get('limit_tokens')
            if type(limit) is not int or limit<256:raise ValueError('Code query token budget required')
            inner=deepcopy(request);inner['budget']['limit_tokens']=max(256,limit-160)
            for _ in range(4):
                with self.lease(graph_id) as service:result=service.query(operation,inner)
                envelope=dict(graph_id=graph_id,graph_label=label,result=result,routing_budget=dict(limit_tokens=limit,used_tokens=0))
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
        else:raise ValueError('Unknown graph operation')
        return self._fit(dict(graph_id=graph_id,graph_label=label,result=result))

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
            if self.allowed is not None and graph['graph_id'] not in self.allowed:continue
            availability='available';error=None;count=None
            try:
                with self.lease(graph['graph_id']) as service:
                    with service.lock:
                        count=service.store.connection.execute('SELECT count(*) FROM entities WHERE snapshot_id=?',(graph['snapshot_id'],)).fetchone()[0]
            except (ValueError,sqlite3.DatabaseError,OSError) as exc:
                availability='unavailable';error=str(exc)[:300]
            profile=json.loads(graph['profile_json'])
            rows.append(dict(graph_id=graph['graph_id'],label=graph['label'],root_path=graph['root_path'],
                graph_kind=profile.get('graph_kind','project'),repo_ids=profile.get('owner_repo_ids',[graph['graph_id']]),
                source_graph_ids=[s['graph_id'] for s in profile.get('source_graphs',[])],
                snapshot_id=graph['snapshot_id'],entity_count=count,papers_available=bool(graph['paper_database']),availability=availability,error=error))
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

    def federated_search(self,graph_ids,query,*,limit_tokens=8192,mode='documentation'):
        if isinstance(graph_ids,list):graph_ids=[self.resolve(gid) for gid in graph_ids]
        if not isinstance(graph_ids,list) or not 2<=len(graph_ids)<=8 or len(set(graph_ids))!=len(graph_ids):raise ValueError('Choose 2..8 distinct graph IDs explicitly')
        if type(limit_tokens) is not int or not 2048<=limit_tokens<=32768:raise ValueError('Federation budget must be 2048..32768 tokens')
        if mode not in {'lexical','documentation','hybrid'} or not isinstance(query,str) or not 1<=len(query)<=500:raise ValueError('Invalid search mode or query')
        for gid in graph_ids:self.permit(gid)
        graphs=sorted((self.catalog.graph(gid) for gid in graph_ids),key=lambda g:g['graph_id'])
        per_graph=max(512,(limit_tokens-1000)//len(graphs))
        counter=TokenCounter();kind=intent(query)
        envelopes={};unavailable={};candidates=[];utilities={}
        for graph in graphs:
            gid=graph['graph_id']
            # One unavailable graph must not hide the healthy graphs' results.
            try:
                tiers={}
                for tier,limit in (('full',5),('compact',2)):
                    req=dict(schema_version='1.1',request_id='federated-search',snapshot_id=graph['snapshot_id'],
                        budget=dict(limit_tokens=per_graph,tokenizer='o200k_base',allow_byte_fallback=False),query=query,
                        mode=mode,repo_ids=[],kinds=[],limit=limit,cursor=None)
                    envelope=self.query(gid,'search_entities',req)
                    if isinstance(envelope,dict) and 'error' in envelope:raise ValueError(str(envelope['error'].get('message','graph error')))
                    tiers[tier]=envelope
                trust,modality=self._stratum(graph)
                try:store_mb=os.path.getsize(graph['code_database'])/1_000_000
                except OSError:store_mb=0.
            except (ValueError,sqlite3.DatabaseError,OSError) as exc:
                unavailable[gid]=str(exc)[:300];continue
            envelopes[gid]=tiers;utilities[gid]={}
            for tier,envelope in tiers.items():
                ranks,exact=self._hit_facts(envelope,query)
                # With at most two full hits the compact envelope carries nothing less.
                if tier=='compact' and len(self._hit_facts(tiers['full'],query)[0])<=2:continue
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
                    if tier!='full':response['omitted'].append(dict(graph_id=gid,reason='budget_compact_only' if tier=='compact' else 'budget_omitted'))
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
        budget=limit_tokens-fit(assemble({c.graph_id:'full' for c in candidates}|{g:'omit' for g in unavailable}))
        for _ in range(5):
            response=assemble(select(candidates,budget))
            count=fit(response)
            if count<=limit_tokens:return response
            budget-=count-limit_tokens
        response=assemble({})
        if fit(response)>limit_tokens:raise ValueError('Federation metadata exceeds token budget')
        return response
