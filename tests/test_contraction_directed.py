"""directed-helper-condensation-v1 (master G6): sequential convex contraction with complete ports."""
import random
from collections import defaultdict

import pytest

from geographer.contraction_directed import Contraction, contract_directed, dominators, is_convex, ports_complete


# --- test-local helpers (random only generates inputs; analyses never use it, master G12) -----------

def quotient_edges(c, edges):
    return sorted({(c.membership.get(u, u), c.membership.get(v, v)) for u, v in edges
                   if c.membership.get(u, u) != c.membership.get(v, v)})


def _succ(edges):
    s = defaultdict(set)
    for u, v in edges:
        s[u].add(v)
    return s


def is_acyclic(edges):
    s = _succ(edges); state = {}
    def visit(u):
        state[u] = 1
        for v in s[u]:
            if state.get(v) == 1 or (v not in state and not visit(v)):
                return False
        state[u] = 2
        return True
    return all(visit(u) for u in sorted({x for e in edges for x in e}) if u not in state)


def reach_from(edges, u):
    s = _succ(edges); seen = set(); stack = [u]
    while stack:
        for v in s[stack.pop()]:
            if v not in seen:
                seen.add(v); stack.append(v)
    return seen


def reaches(edges, u, v):
    return u == v or v in reach_from(edges, u)


def reachable_pairs(edges):
    nodes = sorted({x for e in edges for x in e})
    return [(a, b) for a in nodes for b in sorted(reach_from(edges, a))]


def random_dag(rng):
    n = rng.randint(4, 30)
    vertices = [f"v{i:02d}" for i in range(n)]
    edges = [(vertices[i], vertices[j]) for i in range(n) for j in range(i + 1, n) if rng.random() < 0.15]
    parent = {v: f"p{rng.randint(0, 3)}" for v in vertices}
    return vertices, edges, parent


# --- G6 counterexample and building blocks -----------------------------------------------------------

def test_gemini_counterexample_blocks_are_not_both_accepted():
    # D: a→b, c→d. Candidates {a,d} and {b,c} are each convex in D but together form a quotient 2-cycle.
    edges = [("a", "b"), ("c", "d")]
    c = contract_directed(["a", "b", "c", "d"], edges, parent={v: "p" for v in "abcd"}, protected=set(),
                          candidates=[{"a", "d"}, {"b", "c"}], ports_check=False)
    assert c.blocks == {"a": ("a", "d")} and c.certificate["rejected"] == {"not_convex": 1}
    assert is_acyclic(quotient_edges(c, edges))


def test_dominators_diamond():
    idom = dominators(["r", "x", "y", "z"], {"r": ["x", "y"], "x": ["z"], "y": ["z"], "z": []}, ["r"])
    assert idom == {"r": None, "x": "r", "y": "r", "z": "r"}


def test_dominators_chain_and_multiple_roots():
    idom = dominators(["a", "b", "c", "d"], {"a": ["c"], "b": ["c"], "c": ["d"], "d": []}, ["a", "b"])
    assert idom == {"a": None, "b": None, "c": None, "d": "c"}  # c is joined from two roots: only the virtual source dominates it


def test_convexity_rejects_reentry():
    succ = {"a": ["y"], "y": ["b"], "b": []}; pred = {"a": [], "y": ["a"], "b": ["y"]}; rank = {"a": 0, "y": 1, "b": 2}
    assert not is_convex({"a", "b"}, succ, pred, rank) and is_convex({"a", "y", "b"}, succ, pred, rank)


def test_ports_complete():
    # x→a→b→y and x→c (c is an entry that cannot reach exit b inside the block)
    succ = {"x": ["a", "c"], "a": ["b"], "b": ["y"], "c": [], "y": []}
    pred = {"x": [], "a": ["x"], "b": ["a"], "c": ["x"], "y": ["b"]}
    assert ports_complete({"a", "b"}, succ, pred)
    assert not ports_complete({"a", "b", "c"}, succ, pred)
    assert ports_complete({"c"}, succ, pred)  # no exit port: vacuously complete


def test_protected_vertices_never_contracted():
    c = contract_directed(["r", "h1", "h2"], [("r", "h1"), ("h1", "h2")], parent={"r": "p", "h1": "p", "h2": "p"}, protected={"h1"})
    assert all("h1" not in m for m in c.blocks.values())


def test_protected_spine_rejected_even_when_a_perfect_block():
    c = contract_directed(["r", "h1", "h2"], [("r", "h1"), ("h1", "h2")], parent={v: "p" for v in ("r", "h1", "h2")},
                          protected={"r"}, candidates=[{"r", "h1", "h2"}, {"h1", "h2"}])
    assert c.blocks == {"h1": ("h1", "h2")} and c.certificate["rejected"] == {"protected": 1}


def test_rejection_reasons_singleton_crosses_parent_overlap_ports():
    edges = [("a", "b"), ("x", "a"), ("x", "c")]
    parent = {"a": "p", "b": "p", "c": "p", "x": "q"}
    c = contract_directed(["a", "b", "c", "x"], edges, parent, protected=set(),
                          candidates=[{"a"}, {"a", "x"}, {"a", "b"}, {"a", "c"}])
    # canonical order: {a,b}, {a,c}, {a,x} (size 2), then {a}. {a,b} is accepted first; {a,c} then overlaps it.
    assert c.blocks == {"a": ("a", "b")}
    rejected = c.certificate["rejected"]
    assert rejected == {"singleton": 1, "crosses_parent": 1, "overlaps_accepted": 1}
    assert c.certificate["candidates"] == 4 and c.certificate["accepted"] == 1
    assert sum(rejected.values()) + c.certificate["accepted"] == c.certificate["candidates"]


def test_ports_incomplete_rejected_with_ports_check():
    edges = [("x", "a"), ("a", "b"), ("b", "y"), ("x", "c")]
    parent = {"a": "p", "b": "p", "c": "p", "x": "q", "y": "q"}
    c = contract_directed(["a", "b", "c", "x", "y"], edges, parent, protected=set(), candidates=[{"a", "b", "c"}])
    assert c.blocks == {} and c.certificate["rejected"] == {"ports_incomplete": 1}


def test_cyclic_input_is_refused():
    with pytest.raises(ValueError):
        contract_directed(["a", "b"], [("a", "b"), ("b", "a")], {"a": "p", "b": "p"}, protected=set())


def test_membership_covers_every_vertex_and_semantics():
    c = contract_directed(["r", "h1", "h2"], [("r", "h1"), ("h1", "h2")], parent={v: "p" for v in ("r", "h1", "h2")}, protected={"r"})
    assert set(c.membership) == {"r", "h1", "h2"} and c.membership["r"] == "r"
    assert c.semantics == "existential_member_reachability"
    assert isinstance(c, Contraction)


def test_generators_find_a_helper_chain():
    # entry -> h1 -> h2 -> h3 (private helper chain under one parent); entry is protected
    vertices = ["entry", "h1", "h2", "h3"]
    edges = [("entry", "h1"), ("h1", "h2"), ("h2", "h3")]
    c = contract_directed(vertices, edges, parent={v: "p" for v in vertices}, protected={"entry"})
    assert c.blocks == {"h1": ("h1", "h2", "h3")}
    assert c.certificate["accepted"] == 1 and c.certificate["candidates"] >= 1 and "rejected" in c.certificate


def test_parallel_twins_are_generated_but_fail_port_completeness():
    # s fans out to t1, t2 which both feed z: t1 and t2 are twins. Each is an entry and an exit port, and t1 does not
    # reach t2, so invariant II (every entry reaches every exit, master G6) rejects them (ruling W3-2).
    vertices = ["s", "t1", "t2", "z"]
    edges = [("s", "t1"), ("s", "t2"), ("t1", "z"), ("t2", "z")]
    c = contract_directed(vertices, edges, parent={v: "p" for v in vertices}, protected={"s", "z"})
    assert c.blocks == {}
    assert c.certificate == {"candidates": 2, "accepted": 0, "rejected": {"protected": 1, "ports_incomplete": 1}}


# --- properties -------------------------------------------------------------------------------------

def test_property_no_false_reachability_and_witnessed_arcs():
    for seed in range(300):
        vertices, edges, parent = random_dag(random.Random(seed))
        c = contract_directed(vertices, edges, parent, protected=set())
        q = quotient_edges(c, edges)
        assert is_acyclic(q), seed
        members = lambda X: c.blocks.get(X, (X,))
        for (A, B) in reachable_pairs(q):
            assert any(reaches(edges, u, v) for u in members(A) for v in members(B)), seed
        eset = set(edges)
        for (A, B) in q:
            assert any((u, v) in eset for u in members(A) for v in members(B)), seed
        for rep, ms in c.blocks.items():
            assert rep == min(ms) and len(ms) >= 2 and len({parent[m] for m in ms}) == 1, seed
            assert ms == tuple(sorted(ms))


def test_property_some_blocks_are_formed():
    formed = sum(bool(contract_directed(*random_dag(random.Random(s)), protected=set()).blocks) for s in range(100))
    assert formed >= 10  # the generators are not vacuous


def test_contraction_is_deterministic_under_input_order():
    vertices, edges, parent = random_dag(random.Random(7))
    baseline = contract_directed(vertices, edges, parent, protected=set())
    for seed in range(10):
        rng = random.Random(seed); v2, e2 = vertices[:], edges[:]; rng.shuffle(v2); rng.shuffle(e2)
        assert contract_directed(v2, e2, parent, protected=set()) == baseline


def test_later_candidates_are_judged_against_the_contracted_quotient():
    # a→b→c→d, with x→b and c→y. After {b,c} is accepted, the candidate {a,d} must be judged in Q where
    # a→{bc}→d: it is not convex there (a path leaves a and re-enters d through the block).
    vertices = ["a", "b", "c", "d", "x", "y"]
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("x", "b"), ("c", "y")]
    parent = {v: "p" for v in vertices}
    c = contract_directed(vertices, edges, parent, protected=set(), candidates=[{"b", "c"}, {"a", "d"}], ports_check=False)
    assert c.blocks == {"b": ("b", "c")} and c.certificate["rejected"] == {"not_convex": 1}
    # and the quotient stays a DAG with forward arcs only
    q = quotient_edges(c, edges)
    assert is_acyclic(q) and ("b", "a") not in q and ("b", "x") not in q
