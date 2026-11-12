"""Directed graph contraction with convexity and port completeness checks."""
from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional, FrozenSet


@dataclass(frozen=True)
class Contraction:
    membership: Dict[str, str]
    blocks: Dict[str, Tuple[str, ...]]
    semantics: str = "existential_member_reachability"
    certificate: Dict = field(default_factory=dict)


def dominators(vertices: List[str], succ: Dict[str, List[str]], roots: List[str]) -> Dict[str, Optional[str]]:
    """Immediate dominators (Cooper-Harvey-Kennedy) over a virtual source joined to ``roots``.

    Roots, vertices whose idom is the virtual source, and unreachable vertices map to None.
    """
    vset = set(vertices)
    out = {v: sorted(w for w in set(succ.get(v, ())) if w in vset) for v in vset}
    source = object()  # never equal to a vertex id
    out_of = lambda v: sorted(r for r in set(roots) if r in vset) if v is source else out[v]
    order, seen, stack = [], {source}, [(source, iter(out_of(source)))]
    while stack:  # iterative DFS post-order, successors in sorted order
        v, it = stack[-1]
        nxt = next((w for w in it if w not in seen), None)
        if nxt is None:
            stack.pop(); order.append(v)
        else:
            seen.add(nxt); stack.append((nxt, iter(out_of(nxt))))
    rpo = order[::-1]
    num = {v: i for i, v in enumerate(rpo)}
    preds: Dict[object, list] = {v: [] for v in rpo}
    for v in rpo:
        for w in out_of(v):
            preds[w].append(v)
    idom: Dict[object, object] = {source: source}
    def intersect(a, b):
        while a is not b and a != b:
            while num[a] > num[b]:
                a = idom[a]
            while num[b] > num[a]:
                b = idom[b]
        return a
    changed = True
    while changed:
        changed = False
        for v in rpo[1:]:
            done = [u for u in preds[v] if u in idom]
            new = done[0]
            for u in done[1:]:
                new = intersect(u, new)
            if idom.get(v) is not new and idom.get(v) != new:
                idom[v] = new; changed = True
    return {v: (None if v not in idom or idom[v] is source else idom[v]) for v in vertices}


def is_convex(block: Set[str], succ: Dict[str, List[str]], pred: Dict[str, List[str]], 
              rank: Dict[str, int]) -> bool:
    """Check if a block is convex in the current quotient graph."""
    if len(block) <= 1:
        return True
        
    # Determine rank bounds for the block
    min_rank = min(rank[b] for b in block)
    max_rank = max(rank[b] for b in block)
    
    # Forward reachability R+
    r_plus = set()
    queue = deque(block)
    visited = set(block)
    
    while queue:
        v = queue.popleft()
        for w in succ.get(v, []):
            if w not in block and w not in visited and rank.get(w, 0) <= max_rank:
                r_plus.add(w)
                visited.add(w)
                queue.append(w)
    
    # Backward reachability R-
    r_minus = set()
    queue = deque(block)
    visited = set(block)
    
    while queue:
        v = queue.popleft()
        for w in pred.get(v, []):
            if w not in block and w not in visited and rank.get(w, 0) >= min_rank:
                r_minus.add(w)
                visited.add(w)
                queue.append(w)
    
    # Check if intersection minus block is empty
    intersection = r_plus & r_minus
    return len(intersection) == 0


def ports_complete(block: Set[str], succ: Dict[str, List[str]], pred: Dict[str, List[str]]) -> bool:
    """Check if every entry port reaches every exit port within the block."""
    if len(block) <= 1:
        return True
    
    # Identify entry and exit ports
    entry_ports = {v for v in block if any(w not in block for w in pred.get(v, []))}
    exit_ports = {v for v in block if any(w not in block for w in succ.get(v, []))}
    
    # No entry or exit ports - vacuously true
    if not entry_ports or not exit_ports:
        return True
    
    # Build subgraph induced by block
    block_succ = {v: [w for w in succ.get(v, []) if w in block] for v in block}
    
    # For each entry port, find what exit ports it can reach
    def reachable_exits_from_entry(entry):
        reached = set()
        queue = deque([entry])
        visited = set()
        
        while queue:
            v = queue.popleft()
            if v in visited:
                continue
            visited.add(v)
            
            # If this is an exit port, we've reached it
            if v in exit_ports:
                reached.add(v)
                
            # Continue exploration
            for w in block_succ.get(v, []):
                if w not in visited:
                    queue.append(w)
                    
        return reached
    
    # Check that each entry port can reach all exit ports
    all_exit_set = set(exit_ports)
    for entry in entry_ports:
        reached_exits = reachable_exits_from_entry(entry)
        # A port that is both entry and exit should reach itself
        if entry in exit_ports and entry not in reached_exits:
            reached_exits.add(entry)
        if reached_exits != all_exit_set:
            return False
            
    return True


def _subtrees(idom: Dict[str, Optional[str]], max_depth: int) -> List[frozenset]:
    """For each vertex v: v plus its dominator-tree descendants at depth 1..max_depth (size >= 2 only)."""
    children: Dict[str, List[str]] = defaultdict(list)
    for v in sorted(idom):
        if idom[v] is not None:
            children[idom[v]].append(v)
    out = []
    for v in sorted(idom):
        members, frontier = {v}, [v]
        for _ in range(max_depth):
            frontier = [c for u in frontier for c in children[u]]
            members.update(frontier)
        if len(members) >= 2:
            out.append(frozenset(members))
    return out


def contract_directed(vertices: List[str], edges: List[Tuple[str, str]], parent: Dict[str, str], 
                      protected: Set[str], max_depth: int = 3, *, 
                      candidates: Optional[List[Set[str]]] = None, 
                      ports_check: bool = True) -> Contraction:
    """Contract a directed acyclic graph based on convexity and port completeness."""
    
    # Validate inputs
    vertex_set = set(vertices)
    for u, v in edges:
        if u not in vertex_set or v not in vertex_set:
            raise ValueError("Edge endpoints must be in vertices")
    
    # Remove duplicates and self-loops
    edge_set = {(u, v) for u, v in edges if u != v}
    edges = list(edge_set)
    
    # Check for cycles using topological sort
    def is_acyclic():
        out = defaultdict(list); in_degree = {v: 0 for v in vertices}
        for u, v in edges:
            out[u].append(v); in_degree[v] += 1
        queue = deque(v for v in sorted(in_degree) if in_degree[v] == 0); processed = 0
        while queue:
            v = queue.popleft(); processed += 1
            for w in out[v]:
                in_degree[w] -= 1
                if in_degree[w] == 0:
                    queue.append(w)
        return processed == len(in_degree)

    if not is_acyclic():
        raise ValueError("Graph must be acyclic")
    
    # Build successor/predecessor maps
    succ = defaultdict(list)
    pred = defaultdict(list)
    for u, v in edges:
        succ[u].append(v)
        pred[v].append(u)
    
    # Generate candidates if not provided
    candidate_list = []
    if candidates is not None:
        candidate_list = [frozenset(c) for c in candidates]
    else:
        # Group vertices by parent
        parent_groups = defaultdict(list)
        for v in vertices:
            parent_groups[parent[v]].append(v)
        
        # Process each parent group
        for p_value in sorted(parent_groups.keys()):
            group_vertices = parent_groups[p_value]
            if len(group_vertices) < 2:
                continue
                
            group_vertex_set = set(group_vertices)
            
            # Build induced subgraph
            induced_edges = [(u, v) for u, v in edges if u in group_vertex_set and v in group_vertex_set]
            induced_succ = defaultdict(list)
            induced_pred = defaultdict(list)
            for u, v in induced_edges:
                induced_succ[u].append(v)
                induced_pred[v].append(u)
            
            # Find roots (no predecessors in induced subgraph)
            has_induced_pred = {v for u, v in induced_edges}
            roots = [v for v in group_vertices if v not in has_induced_pred]
            
            # Dominator subtrees
            if roots:
                idom = dominators(group_vertices, induced_succ, roots)
                candidate_list.extend(_subtrees(idom, max_depth))

            # Post-dominator subtrees (reverse graph)
            rev_induced_succ = defaultdict(list)
            for u, v in induced_edges:
                rev_induced_succ[v].append(u)
            
            # Find exits (no successors in induced subgraph)
            has_induced_succ = {u for u, v in induced_edges}
            exits = [v for v in group_vertices if v not in has_induced_succ]
            
            # Post-dominators
            if exits:
                idom = dominators(group_vertices, rev_induced_succ, exits)
                candidate_list.extend(_subtrees(idom, max_depth))

            # Twins
            twin_groups = defaultdict(list)
            for v in group_vertices:
                pred_key = frozenset(pred.get(v, []))
                succ_key = frozenset(succ.get(v, []))
                twin_groups[(pred_key, succ_key)].append(v)
            
            for group in twin_groups.values():
                if len(group) >= 2:
                    candidate_list.append(frozenset(group))
        
        # Deduplicate candidates
        candidate_list = list(set(candidate_list))
    
    # Sort candidates by (min(member), -len(B), tuple(sorted(B)))
    candidate_list.sort(key=lambda b: (min(b), -len(b), tuple(sorted(b))))
    
    # Current quotient Q as an arc set over quotient vertices (initially the input DAG).
    membership = {v: v for v in sorted(vertex_set)}
    arcs = set(edge_set)

    def adjacency(arc_set):
        s: Dict[str, List[str]] = {v: [] for v in set(membership.values())}
        p: Dict[str, List[str]] = {v: [] for v in s}
        for u, v in sorted(arc_set):
            s[u].append(v); p[v].append(u)
        return s, p

    def compute_rank(s, p):
        """Longest-path depth from Q's sources; None if Q is cyclic."""
        indeg = {v: len(p[v]) for v in s}
        rank = {v: 0 for v in s}
        queue = deque(sorted(v for v in s if indeg[v] == 0)); done = 0
        while queue:
            v = queue.popleft(); done += 1
            for w in s[v]:
                rank[w] = max(rank[w], rank[v] + 1); indeg[w] -= 1
                if indeg[w] == 0:
                    queue.append(w)
        return rank if done == len(s) else None

    cert_candidates = len(candidate_list)
    cert_accepted = 0
    cert_rejected: Dict[str, int] = defaultdict(int)
    accepted_blocks: Dict[str, Tuple[str, ...]] = {}
    quotient_succ, quotient_pred = adjacency(arcs)
    rank = compute_rank(quotient_succ, quotient_pred)

    for candidate in candidate_list:
        if len(candidate) < 2:
            cert_rejected["singleton"] += 1; continue
        if len({parent[v] for v in candidate}) > 1:
            cert_rejected["crosses_parent"] += 1; continue
        if candidate & protected:
            cert_rejected["protected"] += 1; continue
        if any(membership[v] != v or v in accepted_blocks for v in candidate):
            cert_rejected["overlaps_accepted"] += 1; continue
        if not is_convex(set(candidate), quotient_succ, quotient_pred, rank):
            cert_rejected["not_convex"] += 1; continue
        if ports_check and not ports_complete(set(candidate), quotient_succ, quotient_pred):
            cert_rejected["ports_incomplete"] += 1; continue
        rep = min(candidate)
        new_arcs = {(rep if u in candidate else u, rep if v in candidate else v) for u, v in arcs}
        new_arcs = {(u, v) for u, v in new_arcs if u != v}
        saved = dict(membership)
        for v in candidate:
            membership[v] = rep
        s, p = adjacency(new_arcs)
        new_rank = compute_rank(s, p)
        if new_rank is None:  # cannot happen for a convex block of a DAG (G6); counted, never accepted
            membership = saved
            cert_rejected["creates_cycle"] += 1; continue
        arcs, quotient_succ, quotient_pred, rank = new_arcs, s, p, new_rank
        accepted_blocks[rep] = tuple(sorted(candidate))
        cert_accepted += 1

    # Build final result
    final_membership = dict(sorted(membership.items()))
    final_blocks = {}
    for rep, members in sorted(accepted_blocks.items()):
        final_blocks[rep] = members
    
    # Build certificate
    certificate = {"candidates": cert_candidates, "accepted": cert_accepted,
                   "rejected": dict(sorted((k, v) for k, v in cert_rejected.items() if v > 0))}

    return Contraction(
        membership=final_membership,
        blocks=final_blocks,
        certificate=certificate
    )
