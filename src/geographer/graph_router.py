"""Graph-scoped agent routing. Display composition never creates an analysis graph."""
from collections import Counter,OrderedDict
from contextlib import contextmanager
from pathlib import Path
import threading
import sqlite3
import json

from .model import canonical
from .service import QueryService
from .store import SnapshotStore
from .tokens import TokenCounter
from copy import deepcopy

CODE_OPERATIONS={'search_entities','get_architecture_context','inspect_relationship_witnesses','get_entity_content','find_dependants','check_architecture','find_similar_code','viewport_frame'}
PAPER_OPERATIONS={'search_documents','get_outline','get_section','get_document','get_concept','find_by_concept','get_related','get_claim','get_annotations','get_corpus_status'}


class GraphRouter:
    def __init__(self,catalog):
        self.catalog=catalog;self.services=OrderedDict();self.lock=threading.RLock()
        self.leases=Counter();self.retired=set();self.borrowed=set()

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
        if not isinstance(graph_id,str) or not graph_id:raise ValueError('graph_id is required; no all-graph fallback')
        if not isinstance(request,dict):raise ValueError('request must be an object')
        graph=self.catalog.graph(graph_id)
        if operation in CODE_OPERATIONS:
            counter=TokenCounter(request.get('budget',{}).get('tokenizer','o200k_base'),request.get('budget',{}).get('allow_byte_fallback',False))
            limit=request.get('budget',{}).get('limit_tokens')
            if type(limit) is not int or limit<256:raise ValueError('Code query token budget required')
            inner=deepcopy(request);inner['budget']['limit_tokens']=max(256,limit-160)
            for _ in range(4):
                with self.lease(graph_id) as service:result=service.query(operation,inner)
                envelope=dict(graph_id=graph_id,result=result,routing_budget=dict(limit_tokens=limit,used_tokens=0))
                for _ in range(12):
                    count=counter.count(envelope)
                    if count==envelope['routing_budget']['used_tokens']:break
                    envelope['routing_budget']['used_tokens']=count
                if count<=limit and counter.count(envelope)==count:return envelope
                inner['budget']['limit_tokens']=max(256,inner['budget']['limit_tokens']-(count-limit)-32)
            return dict(graph_id=graph_id,error=dict(code='GRAPH_BUDGET_TOO_SMALL',message='Increase budget for the complete routed envelope'))
        elif operation.startswith('paper_') and operation[6:] in PAPER_OPERATIONS:
            if not graph['paper_database']:raise ValueError('This graph has no attached paper corpus')
            from pipeline import mcp_doc_graph as paper
            from pipeline.query_context import DATABASE_SCOPE
            token=DATABASE_SCOPE.set(Path(graph['paper_database']))
            try:result=paper._TOOLS[operation[6:]](**request)
            finally:DATABASE_SCOPE.reset(token)
        else:raise ValueError('Unknown graph operation')
        return dict(graph_id=graph_id,result=result)

    def summary(self):
        rows=[]
        for graph in self.catalog.graphs():
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

    def federated_search(self,graph_ids,query,*,limit_tokens=8192,mode='documentation'):
        if not isinstance(graph_ids,list) or not 2<=len(graph_ids)<=8 or len(set(graph_ids))!=len(graph_ids):raise ValueError('Choose 2..8 distinct graph IDs explicitly')
        if type(limit_tokens) is not int or not 2048<=limit_tokens<=32768:raise ValueError('Federation budget must be 2048..32768 tokens')
        if mode not in {'lexical','documentation','hybrid'} or not isinstance(query,str) or not 1<=len(query)<=500:raise ValueError('Invalid search mode or query')
        graphs=[self.catalog.graph(gid) for gid in graph_ids]
        response=dict(graph_ids=graph_ids,results=[],omitted=[],ranking='independent_per_graph_no_global_rank',tokenizer='o200k_base',used_tokens=0)
        per_graph=max(512,(limit_tokens-1000)//len(graphs))
        for graph in graphs:
            req=dict(schema_version='1.1',request_id='federated-search',snapshot_id=graph['snapshot_id'],
                budget=dict(limit_tokens=per_graph,tokenizer='o200k_base',allow_byte_fallback=False),query=query,
                mode=mode,repo_ids=[],kinds=[],limit=5,cursor=None)
            # One unavailable graph must not hide the healthy graphs' results.
            try:response['results'].append(self.query(graph['graph_id'],'search_entities',req))
            except (ValueError,sqlite3.DatabaseError,OSError) as exc:
                response['results'].append(dict(graph_id=graph['graph_id'],error=dict(code='GRAPH_UNAVAILABLE',message=str(exc)[:300])))
        counter=TokenCounter()
        # Treat each independently valid graph envelope as indivisible: removing
        # a partial node/edge collection would break endpoint closure.
        while True:
            for _ in range(12):
                count=counter.count(response)
                if count==response['used_tokens']:break
                response['used_tokens']=count
            count=counter.count(response)
            if count<=limit_tokens and count==response['used_tokens']:return response
            if not response['results']:raise ValueError('Federation metadata exceeds token budget')
            # Drop the largest envelope so the outcome doesn't depend on argument order.
            sizes=[counter.count(r) for r in response['results']]
            omitted=response['results'].pop(max(range(len(sizes)),key=lambda i:(sizes[i],i)))
            response['omitted'].append(dict(graph_id=omitted['graph_id'],reason='full_graph_envelope_omitted_by_budget'))
