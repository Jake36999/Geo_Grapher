"""Cross-snapshot identity and the drift classifier (master G3, as amended by ruling W2-5)."""
import json
import sys

import pytest

from geographer.drift import OUTCOME, drift_report, resolve, tier
from geographer.store import SnapshotStore
from test_fingerprints import drop_table_copy, fp

BASE = (
    "def g(y):\n"
    "    return y + 1\n"
    "\n"
    "def f(x):\n"
    "    # note\n"
    "    if x > 1:\n"
    "        return g(x)\n"
    "    return 0\n"
)

EDITS = {
    "": (BASE, BASE),
    "insert_line_above": (BASE, "# header\n" + BASE),
    "change_comment": (BASE, BASE.replace("# note", "# a different note")),
    "refactor_body_same_calls": (BASE, BASE.replace("    return 0\n", "    return -1\n")),
    "edit_callee_body_only": (BASE, BASE.replace("return y + 1", "return y + 2")),
    "change_signature": (BASE, BASE.replace("def f(x):", "def f(x, z=0):")),
    "change_guard": (BASE, BASE.replace("if x > 1:", "if x >= 1:")),
    "change_call_target": (BASE, BASE.replace("return g(x)", "return h(x)") + "\ndef h(y):\n    return y\n"),
    "rename_function_same_body": (BASE, BASE.replace("def f(x):", "def f_renamed(x):")),
    "delete_function": (BASE, BASE.split("def f(x):")[0]),
}


def _norm(qn):
    return qn.removeprefix("repo.").replace(".py.", ".")


def drift_for(tmp_path, pair, *, drop_base_fingerprints=False):
    before, after = pair
    store_a, sid_a, _ = fp(tmp_path / "a", {"m.py": before})
    store_b, sid_b, _ = fp(tmp_path / "b", {"m.py": after})
    if drop_base_fingerprints:
        copy = tmp_path / "old.sqlite"
        drop_table_copy(store_a, copy, "entity_fingerprints")
        store_a = SnapshotStore(copy)
    report = drift_report(store_a, sid_a, store_b, sid_b)
    names = {eid: _norm(e.qualified_name) for eid, e in store_a.graph(sid_a).entities.items()}
    return {names[row["entity_id"]]: row["tier"] for row in report["entities"]}, report


@pytest.mark.parametrize("edit,expected", [
    ("", "IDENTICAL"),
    ("insert_line_above", "LINE_SHIFT"),
    ("change_comment", "COSMETIC"),
    ("refactor_body_same_calls", "BODY_REFACTOR"),
    ("edit_callee_body_only", "NEIGHBOUR_DRIFT"),
    ("change_signature", "CONTRACT_CHANGE"),
    ("change_guard", "CONTRACT_CHANGE"),
    ("change_call_target", "CONTRACT_CHANGE"),
    ("rename_function_same_body", "MOVED"),
    ("delete_function", "MISSING"),
])
def test_tier_for_scripted_edit(tmp_path, edit, expected):
    tiers, _ = drift_for(tmp_path, EDITS[edit])
    assert tiers["m.f"] == expected


def test_callee_edit_is_body_refactor_for_the_callee(tmp_path):
    tiers, _ = drift_for(tmp_path, EDITS["edit_callee_body_only"])
    assert tiers["m.g"] == "BODY_REFACTOR"


def test_outcome_matrix_is_master_g3():
    assert OUTCOME["NEIGHBOUR_DRIFT"] == {"STRICT_BYTE_SPAN": "NOOP", "AST_ALPHA_INVARIANT": "NOOP",
                                          "CONTROL_GUARD_INVARIANT": "NOOP", "TOPOLOGICAL_WL3": "SUSPECT"}
    assert OUTCOME["BODY_REFACTOR"]["CONTROL_GUARD_INVARIANT"] == "NOOP"
    assert OUTCOME["BODY_REFACTOR"]["STRICT_BYTE_SPAN"] == "HARD"
    assert OUTCOME["MOVED"] == {"STRICT_BYTE_SPAN": "REANCHOR", "AST_ALPHA_INVARIANT": "NOOP",
                                "CONTROL_GUARD_INVARIANT": "NOOP", "TOPOLOGICAL_WL3": "SUSPECT"}
    assert set(OUTCOME["CONTRACT_CHANGE"].values()) == {"HARD"} and set(OUTCOME["MISSING"].values()) == {"HARD"}
    assert set(OUTCOME["UNKNOWN"].values()) == {"UNKNOWN"}
    assert set(OUTCOME) == {"IDENTICAL", "LINE_SHIFT", "COSMETIC", "BODY_REFACTOR", "NEIGHBOUR_DRIFT",
                            "CONTRACT_CHANGE", "MOVED", "MISSING", "UNKNOWN"}


def test_drift_on_store_without_fingerprints_is_unknown_not_hard(tmp_path):
    _, report = drift_for(tmp_path, EDITS["change_signature"], drop_base_fingerprints=True)
    assert report["entities"] and set(report["counts"]) == {"UNKNOWN"}


def test_tier_unit_rules():
    row = dict(span_sha256="s", ast_body_hash="a", signature_hash="g", ts_guard_hash="t",
               exact_out_edges_hash="o", wl_3hop_hash="w")
    assert tier(row, None, 1, None, False) == "MISSING"
    assert tier(None, row, 1, 1, False) == "UNKNOWN"
    assert tier(row, dict(row, signature_hash="x"), 1, 1, True) == "MOVED"
    # a contract change outranks a cosmetic span change
    assert tier(row, dict(row, span_sha256="z", ts_guard_hash="x"), 1, 1, False) == "CONTRACT_CHANGE"
    # a span change outranks neighbour drift (quotes must re-anchor)
    assert tier(row, dict(row, span_sha256="z", wl_3hop_hash="x"), 1, 1, False) == "COSMETIC"


def test_resolve_prefers_id_then_qualname_then_unique_ast():
    class E:
        def __init__(self, repo_id, qualified_name, kind):
            self.repo_id, self.qualified_name, self.kind = repo_id, qualified_name, kind
    base = {"e1": {"ast_body_hash": "A"}, "e2": {"ast_body_hash": "B"}, "e3": {"ast_body_hash": "C"},
            "e4": {"ast_body_hash": "D"}}
    new = {"e1": {"ast_body_hash": "A"}, "n2": {"ast_body_hash": "B2"}, "n3": {"ast_body_hash": "C"},
           "n4": {"ast_body_hash": "D"}, "n5": {"ast_body_hash": "D"}}
    be = {"e1": E("r", "m.a", "function"), "e2": E("r", "m.b", "function"), "e3": E("r", "m.c", "function"),
          "e4": E("r", "m.d", "function")}
    ne = {"e1": E("r", "m.a", "function"), "n2": E("r", "m.b", "function"), "n3": E("r", "m.c2", "function"),
          "n4": E("r", "m.x", "function"), "n5": E("r", "m.y", "function")}
    out = resolve(base, new, be, ne)
    assert out["e1"] == ("e1", "same_id")
    assert out["e2"] == ("n2", "same_qualname")
    assert out["e3"] == ("n3", "unique_ast")
    assert out["e4"] == (None, "none")  # ast D is not unique in the new snapshot


def test_report_is_sorted_and_deterministic(tmp_path):
    _, r1 = drift_for(tmp_path / "x", EDITS["change_comment"])
    _, r2 = drift_for(tmp_path / "y", EDITS["change_comment"])
    ids = [row["entity_id"] for row in r1["entities"]]
    assert ids == sorted(ids) and r1 == r2


def test_cli_drift_report_writes_json(tmp_path, monkeypatch):
    before, after = EDITS["change_guard"]
    store_a, sid_a, _ = fp(tmp_path / "a", {"m.py": before}, db=tmp_path / "a.sqlite")
    store_b, sid_b, _ = fp(tmp_path / "b", {"m.py": after}, db=tmp_path / "b.sqlite")
    store_a.close(); store_b.close()
    out = tmp_path / "drift.json"
    from geographer import cli
    monkeypatch.setattr(sys, "argv", ["geographer", "drift-report", "--store-a", str(tmp_path / "a.sqlite"),
                                      "--snapshot-a", sid_a, "--store-b", str(tmp_path / "b.sqlite"),
                                      "--snapshot-b", sid_b, "--out", str(out)])
    cli.main()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["counts"].get("CONTRACT_CHANGE", 0) >= 1
