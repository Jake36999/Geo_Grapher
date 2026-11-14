"""Snapshot-scoped bridge traversal and documentary conformance findings."""
from __future__ import annotations
import heapq
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from .analysis import DEFAULT_FILTER
from .actor import resolve_request_aliases
from .bridges import _doc_sources, parse_ref, resolve_ref
from .store import SnapshotStore


def bridge_impact(catalog, start, *, max_hops=6, pinned_graphs=frozenset(), graph_ids=None):
    from .graph_router import GraphRouter
    allowed = set(graph_ids) if graph_ids is not None else {g['graph_id'] for g in catalog.graphs()}
    if type(max_hops) is not int or not 0 <= max_hops <= 32:
        raise ValueError('max_hops must be 0..32')
    if len(start) != 2 or start[0] not in allowed or not set(pinned_graphs) <= allowed:
        raise ValueError('Impact endpoints must be selected graphs')
    resolve_ref(catalog, *start)
    rows = {g:catalog.graph(g) for g in sorted(allowed)}
    bridges = [b for b in catalog.bridges(sorted(allowed)) if catalog.bridge_state(b['bridge_id']) in {'accepted','provisional_reanchored'}]
    outgoing = defaultdict(list)
    for b in bridges:
        try:
            resolve_ref(catalog,b['source_graph'],b['source_ref']); resolve_ref(catalog,b['target_graph'],b['target_ref'])
        except ValueError:
            continue
        target = (b['target_graph'],b['target_ref'])
        tier = json.loads(rows[target[0]]['profile_json']).get('stratum',{}).get('trust_tier')
        cost = 0.2 + (2.5 if tier == 'bronze_transcript' and target[0] not in pinned_graphs else 0)
        outgoing[b['source_graph'],b['source_ref']].append((target,cost,'bridge',b['bridge_id']))
    router = GraphRouter(catalog,allowed=allowed); cache = {}
    def neighbours(gid,ref):
        key = (gid,ref)
        if key in cache: return cache[key]
        result = list(outgoing[key]); kind, parts = parse_ref(ref)
        if kind == 'entity':
            with router.lease(gid) as svc, svc.lock:
                sid = rows[gid]['snapshot_id']
                req = dict(schema_version='1.1',request_id='bridge-impact',snapshot_id=sid,
                    budget=dict(limit_tokens=32768,tokenizer='o200k_base',allow_byte_fallback=False),
                    entity_id=parts['entity'],direction='incoming',filter={**DEFAULT_FILTER,'resolution_statuses':['exact','candidate']},
                    max_depth=1,max_results=1000,cursor=None)
                while True:
                    envelope = svc.query('find_dependants',req)
                    if 'error' in envelope: raise ValueError(str(envelope['error']))
                    data = envelope['data']; witnesses = {w['id']:w for w in data['witnesses']}
                    def decode(alias,field):
                        return resolve_request_aliases(svc,svc._context(sid),dict(snapshot_id=sid,view_id=data['view_id'],
                            alias_scope=data['identity_scope'],**{field:alias}))[field]
                    for item in data['results']:
                        for wid in item['witness_path_ids']:
                            w = witnesses[wid]
                            result.append(((gid,'entity:'+decode(item['node_id'],'entity_id')),
                                1.1 if w['resolution_status']=='candidate' else 1.0,'intra',decode(wid,'relationship_id')))
                    req['cursor'] = data['completeness'].get('next_cursor')
                    if not req['cursor']: break
        cache[key] = sorted(result,key=lambda x:(x[1],x[0],x[2],x[3]))
        return cache[key]
    start = tuple(start); heap = [(0.0,start[0],start[1],0,())]
    best = {(start[0],start[1],0):(0.0,())}; chosen = {}
    try:
        while heap:
            cost,gid,ref,hops,path = heapq.heappop(heap)
            if best.get((gid,ref,hops)) != (cost,path): continue
            chosen.setdefault((gid,ref),(cost,path))
            if hops == max_hops: continue
            for (tg,tr),weight,kind,rid in neighbours(gid,ref):
                nc = round(cost+weight,6); np = path+((kind,gid,ref,tg,tr,rid),); key=(tg,tr,hops+1)
                if key not in best or (nc,np) < best[key]:
                    best[key]=(nc,np);heapq.heappush(heap,(nc,tg,tr,hops+1,np))
    finally:
        router.close()
    items=[]
    for (gid,ref),(cost,path) in sorted(chosen.items(),key=lambda x:(x[1][0],x[0])):
        if (gid,ref)==start: continue
        steps=[dict(kind=k,**{'from':dict(graph_id=a,ref=ar),'to':dict(graph_id=b,ref=br)},id=rid) for k,a,ar,b,br,rid in path]
        items.append(dict(graph_id=gid,ref=ref,cost=cost,path=steps))
    return dict(dependants=items,bridges_considered=len(bridges),max_hops=max_hops)


def conformance(catalog, theory_graph, code_graph):
    from .discovery import _boundary_bottlenecks
    theory,code = catalog.graph(theory_graph),catalog.graph(code_graph)
    if theory_graph == code_graph or not theory['paper_database']:
        raise ValueError('Conformance requires a theory paper graph and a distinct code graph')
    bridges = catalog.bridges([theory_graph,code_graph])
    if not bridges: return dict(findings=[],bridges_considered=0,hint='Review bridge proposals first.')
    findings=[]; covered=set(); linked=set()
    def finding(state,tr=None,cr=None,bid=None):
        cites=[]
        if tr: cites.append(theory['label']+'/'+tr)
        if cr: cites.append(code['label']+'/'+cr)
        findings.append(dict(state=state,theory_ref=tr,code_ref=cr,bridge_id=bid,cite_as=cites))
    for b in bridges:
        tr,cr=(b['source_ref'],b['target_ref']) if b['source_graph']==theory_graph else (b['target_ref'],b['source_ref'])
        linked.add(cr); state=catalog.bridge_state(b['bridge_id'])
        if state in {'suspect_stale','demoted_contestable'}:
            finding('STALE_BRIDGE',tr,cr,b['bridge_id'])
        elif state=='accepted' and b['kind'] in {'reference','concept_equivalence'} and cr.startswith('entity:'):
            try:
                resolve_ref(catalog,code_graph,cr);resolve_ref(catalog,theory_graph,tr)
            except ValueError:
                continue
            covered.add(tr);finding('VERIFIED_IMPLEMENTATION',tr,cr,b['bridge_id'])
    with sqlite3.connect(Path(theory['paper_database']).resolve().as_uri()+'?mode=ro',uri=True) as con:
        refs=set()
        for (doc,) in con.execute('SELECT id FROM read_documents ORDER BY id'):
            refs.add(f'doc:{doc}')
            refs.update(f'doc:{doc}#claim:{cid}' for (cid,) in con.execute('SELECT id FROM read_claims WHERE doc_id=? ORDER BY id',(doc,)))
            sources=_doc_sources(con,doc)
            refs.update(f'doc:{doc}#section:{sid}' for (sid,) in con.execute('SELECT id FROM sections WHERE doc_id IN (%s) ORDER BY id'%','.join('?'*len(sources)),sources))
        for ref in sorted(refs-covered): finding('SPECIFICATION_ABSENCE',ref)
    with SnapshotStore(code['code_database']) as store:
        sid=code['snapshot_id']; graph=store.graph(sid)
        documented={r[0] for r in store.connection.execute('SELECT entity_id FROM documentary_incidences WHERE snapshot_id=?',(sid,))}
        for row in _boundary_bottlenecks(graph)[:10]:
            eid=row['entity_id'];ref='entity:'+eid
            if ref not in linked and eid not in documented: finding('UNDOCUMENTED_DIVERGENCE',cr=ref)
    findings.sort(key=lambda f:(f['state'],f['theory_ref'] or '',f['code_ref'] or '',f['bridge_id'] or ''))
    return dict(findings=findings,bridges_considered=len(bridges),hint=None)
