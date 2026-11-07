"""Stage 2 deterministic partitions, projections, SCCs and scoped diagnostics."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import heapq
import json
from typing import TYPE_CHECKING

from .model import Graph, canonical, digest

if TYPE_CHECKING:
    from .store import SnapshotStore

DEFAULT_FILTER = {"repo_ids": [], "families": ["static"], "subtypes": [], "resolution_statuses": ["exact"],
                  "include_tests": False, "include_generated": False, "include_vendor": False,
                  "include_external": True, "runtime_window": None}


def eligible_entity(entity, filters):
    return ((not filters["repo_ids"] or entity.repo_id in filters["repo_ids"]) and
            (filters["include_tests"] or not entity.is_test) and
            (filters["include_generated"] or not entity.is_generated) and
            (filters["include_vendor"] or not entity.is_vendor) and
            (filters["include_external"] or not entity.is_external))


def selected_relationships(graph, filters=None):
    f = filters or DEFAULT_FILTER
    runtime_windows=None
    for rid in sorted(graph.relationships):
        r = graph.relationships[rid]
        if r.family not in f["families"] or r.resolution_status not in f["resolution_statuses"]:
            continue
        if f["subtypes"] and r.subtype not in f["subtypes"]:
            continue
        if r.family=='runtime':
            requested=f['runtime_window']
            if requested is None:continue
            if runtime_windows is None:
                runtime_windows=defaultdict(set)
                for evidence in graph.evidence.values():
                    if evidence.category=='dynamic_observed':
                        runtime_windows[evidence.relationship_id].add((evidence.window_start,evidence.window_end,json.loads(evidence.details_json).get('environment')))
            if (requested['start'],requested['end'],requested['environment']) not in runtime_windows[r.relationship_id]:continue
        if eligible_entity(graph.entities[r.source_id], f) and eligible_entity(graph.entities[r.target_id], f):
            yield r


class TreeIndex:
    def __init__(self, graph):
        self.graph = graph
        self.children = {eid: [] for eid in graph.entities}
        self.parents = {eid: e.parent_id for eid, e in graph.entities.items()}
        roots = []
        for eid, parent in self.parents.items():
            if parent is None:
                roots.append(eid)
            else:
                self.children[parent].append(eid)
        if len(roots) != 1:
            raise ValueError("Tree requires one root")
        self.root = roots[0]
        for cs in self.children.values():
            cs.sort()
        self.up = {eid: json.loads(e.ancestors_binary_lifting_json) for eid, e in graph.entities.items()}
        self.leaf_order = []
        self.intervals = {}
        stack = [(self.root, False)]
        starts = {}
        while stack:
            eid, leaving = stack.pop()
            if leaving:
                self.intervals[eid] = (starts[eid], len(self.leaf_order))
                continue
            starts[eid] = len(self.leaf_order)
            stack.append((eid, True))
            if self.children[eid]:
                stack.extend((c, False) for c in reversed(self.children[eid]))
            else:
                self.leaf_order.append(eid)

    def leaves(self, eid):
        start, end = self.intervals[eid]
        return self.leaf_order[start:end]

    def descendants(self,eid):
        stack=[eid]
        while stack:
            node=stack.pop();yield node
            stack.extend(reversed(self.children[node]))

    def ancestors(self, eid):
        path = []
        while eid is not None:
            path.append(eid)
            eid = self.parents[eid]
        return list(reversed(path))

    def lca(self, x, y):
        e = self.graph.entities
        if e[x].depth < e[y].depth:
            x, y = y, x
        delta = e[x].depth-e[y].depth
        for j in range(len(self.up[x])):
            if delta & (1 << j):
                x = self.up[x][j]
        if x == y:
            return x
        for j in reversed(range(len(self.up[x]))):
            if self.up[x][j] != self.up[y][j]:
                x, y = self.up[x][j], self.up[y][j]
        return self.up[x][0]

    def distance(self, x, y):
        e = self.graph.entities
        return e[x].depth+e[y].depth-2*e[self.lca(x,y)].depth

    def doi(self, x, focus):
        return -(self.distance(x,focus)+self.graph.entities[x].depth)

    def context(self, focus, radius):
        if radius not in (0,1,2):
            raise ValueError("Context radius must be 0,1,2")
        # DOI >= -depth(focus)-2r is equivalent to depth(x)-depth(LCA)<=r:
        # union the first r descendant levels of every focus ancestor. Starting
        # every ancestor at depth zero avoids scanning unrelated deep branches.
        result=set(self.ancestors(focus));queue=deque((p,0) for p in sorted(result))
        while queue:
            parent,depth=queue.popleft()
            if depth==radius:continue
            for child in self.children[parent]:
                if child not in result:result.add(child);queue.append((child,depth+1))
        return result


@dataclass
class Partition:
    grouping: dict
    groups: dict[str, set[str]]
    kinds: dict[str, str]
    shells: dict[str, str | None]

    @property
    def representatives(self):
        return {atom: rep for rep, members in self.groups.items() for atom in members}


def partition(graph, snapshot_id, grouping, filters=None, *, tree=None):
    tree = tree or TreeIndex(graph)
    f = filters or DEFAULT_FILTER
    universe = {eid for eid in tree.leaf_order if eligible_entity(graph.entities[eid], f)}
    groups, kinds, shells = {}, {}, {}
    def assign(rep, leaves, kind="entity", shell=None):
        leaves = set(leaves) & universe
        if leaves:
            groups.setdefault(rep,set()).update(leaves)
            kinds[rep] = kind
            shells[rep] = shell
    mode = grouping["mode"]
    if mode == "mixed":
        revealed = {tree.root}
        for eid in grouping["revealed_ids"]:
            if eid not in graph.entities:
                raise ValueError("Revealed ID is outside snapshot")
            revealed.update(tree.ancestors(eid))
        grouping = {"mode": "mixed", "revealed_ids": sorted(revealed)}
        stack = [tree.root]
        while stack:
            p = stack.pop()
            active = [c for c in tree.children[p] if c in revealed]
            if not active:
                assign(p, tree.leaves(p), shell=tree.parents[p])
            else:
                unseen = [c for c in tree.children[p] if c not in revealed]
                if unseen:
                    rep = "view:residual:" + digest("residual-v1", snapshot_id, p, unseen)
                    assign(rep, (a for c in unseen for a in tree.leaves(c)), "residual", p)
                stack.extend(reversed(active))
    elif mode in {"depth", "kind", "atomic"}:
        for atom in sorted(universe):
            current = atom
            if mode == "depth":
                while graph.entities[current].depth > grouping["depth"]:
                    current = tree.parents[current]
            elif mode == "kind":
                ancestors = list(reversed(tree.ancestors(atom)))
                current = next((p for p in ancestors if graph.entities[p].kind == grouping["kind"]), atom)
            elif graph.entities[current].kind == "scope_atom":
                current = tree.parents[current]
            assign(current,[atom],shell=tree.parents[current])
    else:
        raise ValueError("Unsupported containment grouping")
    result = Partition(grouping, groups, kinds, shells)
    mapped = [a for members in groups.values() for a in members]
    if len(mapped)!=len(set(mapped)) or set(mapped)!=universe:
        raise AssertionError("Partition must cover every in-scope leaf once")
    return result


def project(graph, part, view_id, filters=None):
    mapping = part.representatives
    buckets=defaultdict(list)
    for r in selected_relationships(graph, filters):
        if r.source_id not in mapping or r.target_id not in mapping:
            raise ValueError("Selected relationship endpoint missing from partition")
        source,target=mapping[r.source_id],mapping[r.target_id]
        if r.direction=="symmetric":
            source,target=sorted((source,target))
        buckets[(source,target,r.family,r.subtype,r.direction,r.resolution_status,r.weight_unit)].append(r)
    evidence=defaultdict(int)
    for e in graph.evidence.values():
        evidence[e.relationship_id]+=1
    rows=[]
    for key,witnesses in sorted(buckets.items()):
        source,target,family,subtype,direction,status,unit=key
        rows.append(dict(projection_id="projection:"+digest(view_id,key), source_rep_id=source,target_rep_id=target,
                         family=family,subtype=subtype,direction=direction,resolution_status=status,weight_unit=unit,
                         witness_count=len(witnesses),evidence_count=sum(evidence[r.relationship_id] for r in witnesses),
                         aggregated_weight=sum(r.weight for r in witnesses),is_internal=int(source==target),
                         witnesses=sorted(r.relationship_id for r in witnesses)))
    return rows


def tarjan(vertices, edges):
    """Iterative Tarjan avoids dependence on Python recursion depth."""
    adjacency={v:set() for v in vertices}
    for u,v in edges:
        adjacency[u].add(v)
    index,low,on_stack,stack={}, {},set(),[]
    components=[]
    for root in sorted(adjacency):
        if root in index:
            continue
        index[root]=low[root]=len(index)
        stack.append(root);on_stack.add(root)
        frames=[(root,iter(sorted(adjacency[root])),None)]
        while frames:
            v,neighbors,parent=frames[-1]
            try:
                w=next(neighbors)
            except StopIteration:
                frames.pop()
                if parent is not None:
                    low[parent]=min(low[parent],low[v])
                if low[v]==index[v]:
                    members=[]
                    while True:
                        w=stack.pop();on_stack.remove(w);members.append(w)
                        if w==v:break
                    components.append(tuple(sorted(members)))
                continue
            if w not in index:
                index[w]=low[w]=len(index);stack.append(w);on_stack.add(w)
                frames.append((w,iter(sorted(adjacency[w])),v))
            elif w in on_stack:
                low[v]=min(low[v],index[w])
    return sorted(components)


def condensations(snapshot_id, view_id, filter_hash, vertices, edges):
    edges=set(edges)
    components=tarjan(vertices,edges)
    membership={v:digest(snapshot_id,view_id,filter_hash,list(c)) for c in components for v in c}
    sizes={membership[c[0]]:len(c) for c in components}
    adj={cid:set() for cid in sizes}
    indegree={cid:0 for cid in sizes}
    for u,v in sorted(edges):
        a,b=membership[u],membership[v]
        if a!=b and b not in adj[a]:adj[a].add(b);indegree[b]+=1
    rank={cid:0 for cid in sizes}
    ready=[cid for cid,d in indegree.items() if d==0];heapq.heapify(ready)
    while ready:
        cid=heapq.heappop(ready)
        for target in sorted(adj[cid]):
            rank[target]=max(rank[target],rank[cid]+1)
            indegree[target]-=1
            if indegree[target]==0:heapq.heappush(ready,target)
    return {v:dict(scc_id=cid,component_size=sizes[cid],dag_rank=rank[cid],has_self_loop=int((v,v) in edges))
            for v,cid in membership.items()}


def subject_graph(graph, filters=None):
    f=filters or DEFAULT_FILTER
    vertices={e.entity_id for e in graph.entities.values() if e.kind in {"file","function","method","class"}
              and eligible_entity(e,f)}
    rels=[r for r in selected_relationships(graph,f) if r.family in {"static","runtime"} and r.direction=="directed"]
    vertices.update(x for r in rels for x in (r.source_subject_id,r.target_subject_id))
    return vertices,rels


def wl3(graph, filters=None):
    f=filters or DEFAULT_FILTER
    vertices,rels=subject_graph(graph,f)
    rels=[r for r in rels if r.family=="static"]
    colors={v:digest(["wl0-v1",graph.entities[v].language,graph.entities[v].kind,graph.entities[v].ast_body_hash]) for v in vertices}
    incoming,outgoing=defaultdict(list),defaultdict(list)
    for r in rels:
        outgoing[r.source_subject_id].append(r)
        incoming[r.target_subject_id].append(r)
    for _ in range(3):
        colors={v:digest(["directed-wl3-v1",colors[v],
                    sorted(["out",r.family,r.subtype,colors[r.target_subject_id]] for r in outgoing[v]),
                    sorted(["in",r.family,r.subtype,colors[r.source_subject_id]] for r in incoming[v])]) for v in sorted(vertices)}
    return colors


def boundary_ratios(graph, selected, filters=None):
    _,rels=subject_graph(graph,filters)
    units={r.weight_unit for r in rels}
    if len(units)>1:
        raise ValueError("Boundary metrics cannot mix weight units")
    unit=next(iter(units),"edge_count")
    outgoing=incoming=out_volume=in_volume=0.0
    pairs=defaultdict(float)
    for r in rels:
        u,v=r.source_subject_id,r.target_subject_id
        if u in selected:
            out_volume+=r.weight
            if v not in selected:outgoing+=r.weight
        if v in selected:
            in_volume+=r.weight
            if u not in selected:incoming+=r.weight
        if u!=v:pairs[tuple(sorted((u,v)))]+=r.weight
    cut=volume=0.0
    for (u,v),w in pairs.items():
        volume+=w*(int(u in selected)+int(v in selected))
        if (u in selected)!=(v in selected):cut+=w
    return [dict(mode=mode,weight_unit=unit,cut_weight=c,volume=v,ratio=c/v if v else None,status="ok" if v else "zero_volume")
            for mode,c,v in (("outgoing",outgoing,out_volume),("incoming",incoming,in_volume),("undirected",cut,volume))]


def cayley_bounds(vertices, relationships):
    vertices=set(vertices)
    raw=[r for r in relationships if r.source_subject_id in vertices and r.target_subject_id in vertices]
    adjacency={v:set() for v in vertices}
    for r in raw:
        if r.source_subject_id!=r.target_subject_id:
            adjacency[r.source_subject_id].add(r.target_subject_id)
            adjacency[r.target_subject_id].add(r.source_subject_id)
    visited=set();results=[];components=[];component_of={}
    for root in sorted(vertices):
        if root in visited:continue
        queue=[root];component=set()
        while queue:
            v=queue.pop()
            if v in component:continue
            component.add(v);queue.extend(adjacency[v]-component)
        visited|=component
        component_index=len(components)
        for v in component:component_of[v]=component_index
        components.append(component)
    by_component=defaultdict(list)
    for r in raw:by_component[component_of[r.source_subject_id]].append(r)
    for component_index,component in enumerate(components):
        occurrences=by_component[component_index]
        edges={tuple(sorted((r.source_subject_id,r.target_subject_id))) for r in occurrences
               if r.source_subject_id!=r.target_subject_id}
        loops=sum(r.source_subject_id==r.target_subject_id for r in occurrences)
        n,m=len(component),len(edges)
        delta=max((len(adjacency[v]) for v in component),default=0)
        parity=delta if n*delta%2==0 else delta+1
        valid=n>=2 and m>=1
        results.append(dict(component_id="component:"+digest(sorted(component)),n=n,m=m,max_degree=delta,
                            parity_degree=parity if valid else None,lower_bound=n*parity/(2*m)-1 if valid else None,
                            removed_self_loops=loops,collapsed_parallel_edges=len(occurrences)-loops-m,
                            status="ok" if valid else "not_applicable",interpretation="abelian_completion_degree_lower_bound"))
    return results


def materialize_view(store: "SnapshotStore", sid, graph, grouping, filters=None):
    filters=filters or DEFAULT_FILTER
    part=partition(graph,sid,grouping,filters)
    fh=digest(filters)
    vid="view:"+digest(sid,part.grouping,filters,"quotient-v1")
    if store.connection.execute("SELECT 1 FROM analysis_views WHERE snapshot_id=? AND view_id=?",(sid,vid)).fetchone():
        return vid,part
    projections=project(graph,part,vid,filters)
    edges=[(r["source_rep_id"],r["target_rep_id"]) for r in projections if r["family"] in {"static","runtime"} and r["direction"]=="directed"]
    scc=condensations(sid,vid,fh,part.groups,edges)
    persist_projection_view(store,sid,vid,part,filters,'quotient-v1',projections,scc)
    return vid,part


def persist_projection_view(store,sid,vid,part,filters,version,rows,scc):
    """One atomic batch path for ordinary, mixed, QI and conceptual quotients."""
    c=store.connection;fh=digest(filters);level_key=canonical(part.grouping)
    c.execute('SAVEPOINT projection_bulk')
    try:
        store._insert('analysis_views',dict(snapshot_id=sid,view_id=vid,grouping_json=level_key,filter_json=canonical(filters),filter_hash=fh,algorithm_version=version))
        store.insert_many('view_representatives',(dict(snapshot_id=sid,view_id=vid,representative_id=rep,kind=part.kinds[rep],
            entity_id=rep if part.kinds[rep]=='entity' else None,parent_shell_id=part.shells[rep],member_count=len(members)) for rep,members in sorted(part.groups.items())))
        atom_order=heapq.merge(*([(atom,rep) for atom in sorted(members)] for rep,members in sorted(part.groups.items())))
        store.insert_many('partition_members',(dict(snapshot_id=sid,view_id=vid,atom_id=atom,representative_id=rep) for atom,rep in atom_order))
        store.insert_many('quotient_projections',(dict(snapshot_id=sid,view_id=vid,**{k:v for k,v in row.items() if k!='witnesses'}) for row in rows))
        witness_order=heapq.merge(*([(rid,row['projection_id']) for rid in row['witnesses']] for row in rows))
        store.insert_many('quotient_witness_map',(dict(snapshot_id=sid,view_id=vid,projection_id=pid,relationship_id=rid) for rid,pid in witness_order))
        store.insert_many('level_scc_condensations',(dict(snapshot_id=sid,view_id=vid,filter_hash=fh,level_key=level_key,representative_id=rep,**record) for rep,record in sorted(scc.items())))
        c.execute('RELEASE projection_bulk')
    except BaseException:
        c.execute('ROLLBACK TO projection_bulk');c.execute('RELEASE projection_bulk');raise


def witness_page(store, sid, view_id, projection_id, after="", limit=50):
    if not 1<=limit<=200:
        raise ValueError("Page size must be 1..200")
    return [dict(r) for r in store.connection.execute("""SELECT r.* FROM quotient_witness_map AS w
      JOIN relationships AS r ON r.snapshot_id=w.snapshot_id AND r.relationship_id=w.relationship_id
      WHERE w.snapshot_id=? AND w.view_id=? AND w.projection_id=? AND w.relationship_id>?
      ORDER BY w.relationship_id COLLATE BINARY LIMIT ?""",(sid,view_id,projection_id,after,limit))]


def prepare_analysis(graph):
    hashes=wl3(graph)
    for eid,value in hashes.items():
        graph.entities[eid].wl_3hop_hash=value
    graph.analyses["wl:"+digest(DEFAULT_FILTER)]=dict(algorithm_version="directed-wl3-v1",scope={"filter":DEFAULT_FILTER},result={"node_hashes":hashes})
    vertices,rels=subject_graph(graph)
    tree=TreeIndex(graph)
    for e in sorted(graph.entities.values(),key=lambda e:e.entity_id):
        if e.kind not in {"repository","package","directory"}:continue
        # Subject membership via ownership interval, including owners of scope atoms.
        scope_atoms=set(tree.leaves(e.entity_id))
        selected={v for v in vertices if set(tree.leaves(v)) & scope_atoms}
        graph.analyses["diagnostic:"+e.entity_id]=dict(algorithm_version="boundary-cayley-v1",scope={"entity_id":e.entity_id,"filter":DEFAULT_FILTER},
            result={"boundary":boundary_ratios(graph,selected),"cayley":cayley_bounds(selected,rels)})
