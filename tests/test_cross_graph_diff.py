"""Cross-graph fingerprint diff, quotient-cycle delta and catalog clone join (U11)."""
import sqlite3

import pytest

from geographer.cross_graph import CLASSES, clone_pairs, diff_graphs, diff_rows, quotient_cycle_delta
from geographer.graph_catalog import GraphCatalog
from geographer.source import Repository


def row(qn, kind="function", ast=None, sig=None, guard="G", wl=None, rel="m.py", line=1):
    return dict(kind=kind, qualified_name=qn, ast_body_hash=ast, signature_hash=sig or "sig:" + qn,
                ts_guard_hash=guard, wl_3hop_hash=wl, rel_path=rel, start_line=line)


A = {"a1": row("m.h", ast="AH", wl="W1"),
     "a2": row("m.r", ast="AR1", sig="SR", wl="W2"),
     "a3": row("m.k1", ast="AK1", wl="WK"),
     "a4": row("m.f", ast="AF1", sig="SF1", guard="GF1", wl="W4"),
     "a5": row("m.x", ast="AX", wl="W5")}
B = {"b1": row("n.h", ast="AH", wl="W9"),
     "b2": row("n.r", ast="AR2", sig="SR", wl="W8"),
     "b3": row("n.k2", ast="AK2", wl="WK"),
     "b4": row("n.f", ast="AF2", sig="SF2", guard="GF2", wl="W7"),
     "b5": row("n.y", ast="AY", wl="W6")}


def test_diff_rows_classifies_all_five_classes():
    d = diff_rows(A, B)
    assert d["classes"] == {"EXACT_AST_SURVIVOR": 1, "CONTRACT_PRESERVING_REFACTOR": 1, "TOPOLOGICAL_ROLE_ANALOG": 1,
                            "SIGNATURE_OR_GUARD_DRIFT": 1, "STRATUM_EXCLUSIVE": 2}
    pairs = {(p["entity_a"], p["entity_b"]): p["class"] for p in d["pairs"]}
    assert pairs == {("a1", "b1"): "EXACT_AST_SURVIVOR", ("a2", "b2"): "CONTRACT_PRESERVING_REFACTOR",
                     ("a3", "b3"): "TOPOLOGICAL_ROLE_ANALOG", ("a4", "b4"): "SIGNATURE_OR_GUARD_DRIFT"}
    assert d["exclusive_a"] == ["a5"] and d["exclusive_b"] == ["b5"]
    assert CLASSES == ("EXACT_AST_SURVIVOR", "CONTRACT_PRESERVING_REFACTOR", "TOPOLOGICAL_ROLE_ANALOG",
                       "SIGNATURE_OR_GUARD_DRIFT", "STRATUM_EXCLUSIVE")


def test_keys_must_be_unique_on_both_sides():
    a = {"a1": row("m.load", ast="X1"), "a2": row("p.load", ast="X2")}  # two 'load' in a
    b = {"b1": row("q.load", ast="X3")}
    d = diff_rows(a, b)
    assert d["classes"].get("SIGNATURE_OR_GUARD_DRIFT", 0) == 0 and d["classes"]["STRATUM_EXCLUSIVE"] == 3


def test_kind_must_match_and_null_hashes_never_match():
    a = {"a1": row("m.C", kind="class", ast=None, wl=None)}
    b = {"b1": row("n.C", kind="function", ast=None, wl=None, sig="other")}
    assert diff_rows(a, b)["classes"] == {"STRATUM_EXCLUSIVE": 2}


def test_pairs_sorted_by_class_order_then_ids_and_mirror_symmetric():
    d = diff_rows(A, B)
    order = [CLASSES.index(p["class"]) for p in d["pairs"]]
    assert order == sorted(order)
    m = diff_rows(B, A)
    assert {(p["entity_b"], p["entity_a"]) for p in m["pairs"]} == {(p["entity_a"], p["entity_b"]) for p in d["pairs"]}


def test_quotient_cycle_delta_states():
    a = [dict(member_rel_paths=["a.py", "b.py"], qcics=2.0), dict(member_rel_paths=["c.py", "d.py"], qcics=1.0),
         dict(member_rel_paths=["e.py", "f.py"], qcics=1.0), dict(member_rel_paths=["g.py", "h.py"], qcics=1.0)]
    b = [dict(member_rel_paths=["a.py", "b.py"], qcics=1.0), dict(member_rel_paths=["c.py", "d.py", "x.py"], qcics=1.5),
         dict(member_rel_paths=["e.py", "f.py"], qcics=1.02), dict(member_rel_paths=["y.py", "z.py"], qcics=0.7)]
    out = quotient_cycle_delta(a, b)
    assert out["counts"] == {"COUPLING_REDUCED": 1, "COUPLING_INCREASED": 1, "INVARIANT": 1,
                             "CYCLE_DISSOLVED": 1, "CYCLE_INTRODUCED": 1}
    assert [e["state"] for e in out["entries"]] == sorted(e["state"] for e in out["entries"])


def test_quotient_cycle_delta_empty():
    assert quotient_cycle_delta([], []) == {"entries": [], "counts": {}}


# --- integration through a real catalog --------------------------------------------------------

PING = {"a.py": "from b import g\n\ndef f():\n    return g()\n\ndef k():\n    return 1\n",
        "b.py": "from a import k\n\ndef g():\n    return 2\n\ndef h():\n    return k()\n"}
PONG = {"a.py": "from b import g\n\ndef f():\n    return g()\n\ndef k():\n    return 1\n",
        "b.py": "def g():\n    return 2\n\ndef h():\n    return 3\n"}
SHARED = "def shared_util(values):\n    total = 0\n    for v in values:\n        total += v * 2\n    return total\n"


def make_graph(catalog, root, label, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return catalog.import_project(root, Repository.from_directory(root, label), label=label)["graph_id"]


@pytest.fixture
def catalog(tmp_path):
    c = GraphCatalog(tmp_path / "cat" / "catalog.sqlite")
    yield c
    c.close()


def test_diff_graphs_reports_dissolved_ping_pong_cycle(catalog, tmp_path):
    a = make_graph(catalog, tmp_path / "v1", "v1", PING)
    b = make_graph(catalog, tmp_path / "v2", "v2", PONG)
    d = diff_graphs(catalog, a, b)
    assert d["quotient_cycle_delta"]["counts"] == {"CYCLE_DISSOLVED": 1}
    assert d["classes"]["EXACT_AST_SURVIVOR"] >= 2  # f, g, k unchanged
    assert d["graph_a"] == a and d["graph_b"] == b


def test_clone_pairs_find_copy_pasted_function_across_three_graphs(catalog, tmp_path):
    ids = [make_graph(catalog, tmp_path / n, n, {"u.py": SHARED + f"\ndef only_{n}():\n    return '{n}'\n"})
           for n in ("p1", "p2", "p3")]
    out = clone_pairs(catalog, ids)
    assert {p["match"] for p in out["pairs"]} == {"py-ast-v1"} and len(out["pairs"]) == 3 and not out["truncated"]
    assert all(p["graph_a"] < p["graph_b"] for p in out["pairs"])
    assert clone_pairs(catalog, ids, limit=1)["truncated"] is True


def test_cross_graph_refuses_graph_without_fingerprints(catalog, tmp_path):
    a = make_graph(catalog, tmp_path / "v1", "v1", PING)
    b = make_graph(catalog, tmp_path / "v2", "v2", PONG)
    path = catalog.graph(b)["code_database"]
    con = sqlite3.connect(path)
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'immutable_entity_fingerprints_%'").fetchall():
        con.execute(f"DROP TRIGGER {name}")
    con.execute("DELETE FROM entity_fingerprints"); con.commit(); con.close()
    with pytest.raises(ValueError, match="^FINGERPRINTS_NOT_COMPUTED"):
        diff_graphs(catalog, a, b)
    with pytest.raises(ValueError, match="^FINGERPRINTS_NOT_COMPUTED"):
        clone_pairs(catalog, [a, b])


def test_clone_pairs_validates_graph_ids(catalog, tmp_path):
    a = make_graph(catalog, tmp_path / "v1", "v1", PING)
    with pytest.raises(ValueError):
        clone_pairs(catalog, [a])
    with pytest.raises(ValueError):
        clone_pairs(catalog, [a, a])


def test_clone_pairs_ignore_older_snapshots_in_the_same_store(catalog, tmp_path):
    ids = [make_graph(catalog, tmp_path / n, n, {"u.py": SHARED}) for n in ("q1", "q2")]
    root = tmp_path / "q1"; (root / "extra.py").write_text("def extra():\n    return 9\n", encoding="utf-8")
    catalog.import_project(root, Repository.from_directory(root, "q1"), label="q1")  # second snapshot, same store
    out = clone_pairs(catalog, ids)
    assert len(out["pairs"]) == 1
