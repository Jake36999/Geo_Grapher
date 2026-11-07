"""Separately labelled documentary-heavy and bounded-path reference workloads."""
from __future__ import annotations
import argparse
from collections import deque
import json
from pathlib import Path
import time
import tracemalloc

from geographer.analysis import DEFAULT_FILTER
from geographer.incremental import build_digest
from geographer.model import Graph,Entity,Relationship
from geographer.pipeline import ingest
from geographer.retrieval import LexicalIndex,TypedBridge
from geographer.source import Repository
from geographer.store import SnapshotStore
from .harness import distribution,sha


def reference_path(adj,source,target,hops):
    queue=deque([(source,0)]);seen={(source,0)}
    while queue:
        u,d=queue.popleft()
        if d and u==target:return True
        if d==hops:continue
        for v in adj.get(u,[]):
            if (v,d+1) not in seen:seen.add((v,d+1));queue.append((v,d+1))
    return False


def run(output,documents=200,vertices=2000):
    if not 1<=documents<=2000 or not 20<=vertices<=10000:raise ValueError('Invalid stress size')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    tracemalloc.start();start=time.perf_counter()
    files={'api.py':('\n'.join(f'def task_{i}(value):\n    return value\n' for i in range(documents))).encode()}
    for i in range(documents):
        files[f'guide_{i:04}.md']=(f'# Procedure {i}\n\napi.py.task_{i} implements the calibration protocol number {i}.\n\n'
                                   '## Caution\n\nThis is documentation; no runtime observation is asserted.\n'*10).encode()
    with SnapshotStore(output/'documents.sqlite') as store:
        ingestion=ingest(store,[Repository('stress','documentary-heavy-v1',files)],stage=2)
        g=store.graph(ingestion['snapshot_id']);index=LexicalIndex(g)
        build_ms=(time.perf_counter()-start)*1000;cases=[]
        for i in sorted({0,documents//2,documents-1}):
            for mode in ('lexical','hybrid','documentation'):
                query=f'api.py.task_{i}' if mode!='documentation' else f'calibration protocol {i}'
                then=time.perf_counter();hits=index.search(query,mode=mode,limit=20)
                relevant=f'api.py.task_{i}'
                names=[g.entities[h['node_id']].qualified_name for h in hits]
                cases.append(dict(query=query,mode=mode,independent_relevant_entity=relevant,
                                  rank=names.index(relevant)+1 if relevant in names else None,
                                  latency_ms=(time.perf_counter()-then)*1000,hits=names))
        index.close();doc_peak=tracemalloc.get_traced_memory()[1]
        doc=dict(workload='documentary-heavy-v1',files=len(files),source_bytes=sum(len(v) for v in files.values()),
                 source_manifest={p:sha(b) for p,b in sorted(files.items())},ingestion=ingestion,publication_validation=store.validate(ingestion['snapshot_id']),
                 index_and_ingestion_ms=build_ms,tracemalloc_peak_bytes=doc_peak,cases=cases)
    tracemalloc.reset_peak();g=Graph();adj={};half=vertices//2
    for i in range(vertices):g.add(Entity(str(i),'stress','function',f'helper_{i}',None))
    for i in range(vertices):
        bound=half if i<half else vertices
        for j in (i+1,i+7):
            if j>=bound:continue
            rid=f'{i}-{j}';g.relationships[rid]=Relationship(rid,str(i),str(j),str(i),str(j),'calls','exact',rid)
            adj.setdefault(str(i),[]).append(str(j))
    start=time.perf_counter();bridge=TypedBridge(g,DEFAULT_FILTER);path_index_ms=(time.perf_counter()-start)*1000
    cases=[]
    for target in (1,7,8,14,28,63,half,vertices-1):
        for hops in (1,4,16):
            expected=reference_path(adj,'0',str(target),hops)
            then=time.perf_counter();actual=bridge.find('0',str(target),max_hops=hops,max_expansions=20000)
            valid=all(s['relationship_id'] in g.relationships and not s['traversal_reversed'] for s in actual['steps'])
            if (actual['outcome']=='found')!=expected or not valid:raise AssertionError((target,hops,actual,expected))
            cases.append(dict(target=target,max_hops=hops,reference_found=expected,result=actual,latency_ms=(time.perf_counter()-then)*1000))
    report=dict(implementation_digest=build_digest(),documentary=doc,
                bounded_paths=dict(workload='bounded-path-stress-v1',vertices=vertices,edges=len(g.relationships),
                    index_ms=path_index_ms,cases=cases,oracle='independent depth-bounded directed BFS over constructed adjacency',
                    reference_agreement=sum((c['result']['outcome']=='found')==c['reference_found'] for c in cases),
                    latency_ms=distribution([c['latency_ms'] for c in cases])),
                tracemalloc_peak_bytes=tracemalloc.get_traced_memory()[1],
                limitations=['Synthetic development-host workloads; not C14 or model task success',
                             'No pruning acceleration enabled; reference engine baseline, no pruning speedup claim',
                             'tracemalloc enabled; shared process allocations, not isolated process RSS'])
    tracemalloc.stop();(output/'stress.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(output),documentary_cases=len(doc['cases']),path_cases=len(cases),agreement=report['bounded_paths']['reference_agreement']),indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();run(args.output)
