"""helper_tree_balls_v1: deterministic disjoint BFS balls with proved hop bounds."""
from __future__ import annotations

from collections import deque
from .analysis import subject_graph,tarjan,DEFAULT_FILTER,TreeIndex,Partition
from .model import digest


def distances(adjacency,start,max_depth=None):
    result={start:0};queue=deque([start])
    while queue:
        u=queue.popleft()
        if max_depth is not None and result[u]>=max_depth:continue
        for v in sorted(adjacency[u]):
            if v not in result:result[v]=result[u]+1;queue.append(v)
    return result


def contract_helpers(graph,snapshot_id,protected=(),diameter=2,filters=None):
    if not isinstance(diameter,int) or isinstance(diameter,bool) or not 0<=diameter<=8:
        raise ValueError("Helper-tree diameter must be 0..8")
    filters=filters or DEFAULT_FILTER
    vertices,rels=subject_graph(graph,filters)
    rels=[r for r in rels if r.family=="static" and r.resolution_status=="exact"]
    protected=set(protected)
    scc=tarjan(vertices,[(r.source_subject_id,r.target_subject_id) for r in rels])
    cyclic={v for c in scc if len(c)>1 for v in c}
    cyclic|={r.source_subject_id for r in rels if r.source_subject_id==r.target_subject_id}
    unresolved={x for r in graph.relationships.values() if r.resolution_status in {"candidate","unresolved"} for x in (r.source_subject_id,r.target_subject_id)}
    exported=set()
    # Explicit __all__ assignments are conservatively retained as export protection.
    for record in graph.analyses.values():
        if record["algorithm_version"]=="source-bytes-v1":
            source_entity=graph.entities[record['scope']['entity_id']]
            if source_entity.kind!='file' or source_entity.language!='python':continue
            import ast,base64
            try:tree=ast.parse(base64.b64decode(record["result"]["bytes_base64"]))
            except (SyntaxError,UnicodeError):continue
            for node in ast.walk(tree):
                writes=(isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__all__' for t in node.targets) or
                        isinstance(node,(ast.AnnAssign,ast.AugAssign)) and isinstance(node.target,ast.Name) and node.target.id=='__all__')
                mutates=isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='__all__'
                if writes or mutates:
                    try:
                        values=ast.literal_eval(node.value) if writes else None
                        if not isinstance(values,(list,tuple)) or any(not isinstance(v,str) for v in values):raise ValueError('Unknown exports')
                        exported.update(values)
                    except (ValueError,TypeError):
                        # Unknown exports protect all private helpers in this source file.
                        path=record["result"]["rel_path"]
                        protected.update(v for v in vertices if graph.entities[v].rel_path==path)
    candidates=set()
    for v in vertices:
        e=graph.entities[v];name=e.qualified_name.rsplit(".",1)[-1]
        if e.kind in {"function","method"} and name.startswith("_") and not name.startswith("__") and name not in exported and not any((e.is_test,e.is_generated,e.is_vendor,e.is_external)) and v not in protected|cyclic|unresolved:
            candidates.add(v)
    adjacency={v:set() for v in vertices}
    for r in rels:
        u,v=r.source_subject_id,r.target_subject_id
        if u!=v:adjacency[u].add(v);adjacency[v].add(u)
    forest={v:adjacency[v]&candidates for v in candidates}
    visited=set();eligible=set()
    for root in sorted(candidates):
        if root in visited:continue
        component=set(distances(forest,root));visited|=component
        if sum(len(forest[v]) for v in component)==2*(len(component)-1):eligible|=component
    rho=diameter//2;unassigned=set(eligible);groups=[]
    priority={v:(digest("qi-seed-v1",snapshot_id,v),v) for v in eligible}
    while unassigned:
        remaining={v:forest[v]&unassigned for v in unassigned}
        seeds=[v for v in sorted(unassigned) if priority[v]==min(priority[w] for w in distances(remaining,v,2*rho))]
        proposals=[set(distances(remaining,seed,rho)) for seed in seeds]
        if sum(map(len,proposals))!=len(set().union(*proposals)):
            raise AssertionError("Parallel BFS proposals overlap")
        groups.extend(proposals);unassigned-=set().union(*proposals)
    groups.extend({v} for v in sorted(vertices-eligible))
    membership={};max_diameter=0;records={}
    for members in groups:
        induced={v:adjacency[v]&members for v in members}
        start=min(members);ds=distances(induced,start)
        far=min(ds,key=lambda v:(-ds[v],v))
        actual=max(distances(induced,far).values())
        if len(ds)!=len(members) or actual>diameter:raise AssertionError("Invalid intrinsic-diameter certificate")
        max_diameter=max(max_diameter,actual)
        rep=min(members) if len(members)==1 else "view:qi:"+digest(snapshot_id,filters,diameter,sorted(members))
        records[rep]=members
        for v in members:membership[v]=rep
    internal=sum(membership[r.source_subject_id]==membership[r.target_subject_id] for r in rels)
    return membership,records,dict(mode="helper_tree_balls_v1",metric="undirected_unweighted_hops",requested_diameter=diameter,
        measured_max_intrinsic_diameter=max_diameter,A=max_diameter+1,B=max_diameter,directed_reachability_preserved=False,
        group_count=len(records),internal_witness_count=internal,crossing_witness_count=len(rels)-internal,
        membership_handle="handle:qi:"+digest(snapshot_id,filters,diameter,sorted(protected)))
