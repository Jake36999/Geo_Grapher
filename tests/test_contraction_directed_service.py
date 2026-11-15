"""Directed contraction as a QI algorithm, with additive block expansion and the κ anomaly boost (wave 3 Task 3)."""
import copy
from pathlib import Path

import pytest

from geographer.analysis import DEFAULT_FILTER
from geographer.contraction_directed import boosted_kappa, kappa
from geographer.pipeline import ingest
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore

DIRECTED = "directed-helper-condensation-v1"
HELPERS = {"lib.py": b"def _a():\n    return 1\ndef _b():\n    return _a()\ndef _c():\n    return _b()\ndef run():\n    return _c()\n",
           "ui.py": b"from lib import run\ndef display():\n    return run()\n"}
# a.py <-> b.py ping-pong at file level (function level stays acyclic); c.py has the same helper shape outside any cycle.
CYCLE = {"a.py": b"from b import qb\ndef pa():\n    return _a1()\ndef _a1():\n    return _a2()\ndef _a2():\n    return qb()\ndef qa():\n    return 1\n",
         "b.py": b"from a import qa\ndef pb():\n    return _b1()\ndef _b1():\n    return _b2()\ndef _b2():\n    return qa()\ndef qb():\n    return 2\n",
         "c.py": b"def pc():\n    return _c1()\ndef _c1():\n    return _c2()\ndef _c2():\n    return 3\ndef qc():\n    return 4\n"}


def make(files):
    store = SnapshotStore()
    sid = ingest(store, [Repository("repo", "revision", files)], stage=3)["snapshot_id"]
    svc = QueryService(store, secret=b"x" * 32)
    ids = {e.qualified_name: e.entity_id for e in store.graph(sid).entities.values()}
    return store, svc, sid, ids


def request(sid, focus, *, algorithm=None, limit=8192):
    qi = {"enabled": True, "max_diameter": 2}
    if algorithm:
        qi["algorithm"] = algorithm
    return dict(schema_version="1.1", request_id="directed", snapshot_id=sid,
                budget=dict(limit_tokens=limit, tokenizer="o200k_base", allow_byte_fallback=False),
                focus_id=focus, grouping={"mode": "atomic"}, context_radius=2, filter=copy.deepcopy(DEFAULT_FILTER),
                pins=[], qi=qi, cursor=None)


@pytest.fixture
def service_with_helpers():
    store, svc, sid, ids = make(HELPERS)
    yield svc, sid, ids
    store.close()


def frame(svc, req, *, allow_small=False):
    result = svc.query("get_architecture_context", req)
    if allow_small and result.get("error", {}).get("code") == "BUDGET_TOO_SMALL":
        return None
    assert "error" not in result, result
    svc.wire11.validate("get_architecture_context", "response", result)
    return result["data"]


def entity_ids(data):
    """Qualified names of the frame's atomic nodes (node ids are view-local aliases)."""
    return {n["qualified_name"] for n in data["nodes"] if n["kind"] != "qi"}


def test_directed_qi_reports_preserved_reachability(service_with_helpers):
    svc, sid, ids = service_with_helpers
    data = frame(svc, request(sid, ids["ui.py.display"], algorithm=DIRECTED))
    qi = data["qi"]
    assert qi["mode"] == DIRECTED and qi["directed_reachability_preserved"] is True
    assert qi["semantics"] == "existential_member_reachability" and qi["requested_diameter"] == 2
    assert any(n["kind"] == "qi" for n in data["nodes"])
    handle = svc.read_handle(qi["membership_handle"])
    assert handle["certificate"]["contraction"]["accepted"] >= 1
    block = next(m for m in handle["groups"].values() if len(m) > 1)
    assert {ids["lib.py.run"], ids["lib.py._c"], ids["lib.py._b"], ids["lib.py._a"]} == set(block)


def test_focus_and_pins_are_never_inside_a_directed_block(service_with_helpers):
    svc, sid, ids = service_with_helpers
    req = request(sid, ids["lib.py._c"], algorithm=DIRECTED); req["pins"] = [ids["lib.py._a"]]
    groups = svc.read_handle(frame(svc, req)["qi"]["membership_handle"])["groups"]
    for members in groups.values():
        if len(members) > 1:
            assert ids["lib.py._c"] not in members and ids["lib.py._a"] not in members


def test_old_algorithm_unchanged_by_default(service_with_helpers):
    svc, sid, ids = service_with_helpers
    assert frame(svc, request(sid, ids["ui.py.display"]))["qi"]["mode"] == "helper_tree_balls_v1"
    assert frame(svc, request(sid, ids["ui.py.display"], algorithm="helper_tree_balls_v1"))["qi"]["directed_reachability_preserved"] is False


def test_unknown_algorithm_is_an_invalid_request(service_with_helpers):
    svc, sid, ids = service_with_helpers
    result = svc.query("get_architecture_context", request(sid, ids["ui.py.display"], algorithm="nope"))
    assert result["error"]["code"] == "INVALID_REQUEST"


def test_kappa_formulas():
    assert boosted_kappa(1.5, violation=True, feedback=True) == 6.0
    assert boosted_kappa(1.5, violation=False, feedback=True) == 3.0
    assert boosted_kappa(1.5, violation=True, feedback=False) == 4.5
    assert boosted_kappa(1.5, violation=False, feedback=False) == 1.5
    assert kappa(0, 1, 100, 40) == round(2 / 60, 6) and kappa(-2, 0, 10, 40) == round(2.718281828459045 ** -1, 6)


def test_block_summary_first_then_members_expand_additively(service_with_helpers):
    svc, sid, ids = service_with_helpers
    members = {"lib.py.run", "lib.py._c", "lib.py._b", "lib.py._a"}
    full = frame(svc, request(sid, ids["ui.py.display"], algorithm=DIRECTED))
    assert members <= entity_ids(full)  # with room, the block's members are expanded alongside its summary
    smallest = None
    for limit in range(400, 8192, 50):  # the smallest budget that admits the summary
        data = frame(svc, request(sid, ids["ui.py.display"], algorithm=DIRECTED, limit=limit), allow_small=True)
        if data and any(n["kind"] == "qi" for n in data["nodes"]):
            smallest = data; break
    assert smallest is not None
    assert len(members & entity_ids(smallest)) < len(members)  # the summary is admitted before all members


@pytest.fixture
def service_with_two_blocks_one_in_cycle():
    store, svc, sid, ids = make(CYCLE)
    yield svc, sid, ids
    store.close()


def test_anomaly_boost_expands_feedback_arc_block_first(service_with_two_blocks_one_in_cycle):
    svc, sid, ids = service_with_two_blocks_one_in_cycle
    from geographer.discovery import feedback_arcs
    assert feedback_arcs(svc.store, sid), "fixture must have a file-level feedback arc"
    cyclic = {q for f in ("a", "b") for q in (f"{f}.py.p{f}", f"{f}.py._{f}1", f"{f}.py._{f}2")}
    plain = {"c.py.pc", "c.py._c1", "c.py._c2"}
    focus = next(e.entity_id for e in svc.store.graph(sid).entities.values() if e.kind == "repository")
    got = set()
    for limit in range(300, 8192, 25):
        data = frame(svc, request(sid, focus, algorithm=DIRECTED, limit=limit), allow_small=True)
        got = entity_ids(data) if data else set()
        if got & (cyclic | plain):
            break
    assert got & cyclic and not (got & plain), "a block touching a feedback-arc witness must expand before an equal-DOI plain block"


def test_service_never_disables_port_check():
    source = Path(__file__).resolve().parents[1].joinpath("src/geographer/service.py").read_text(encoding="utf-8")
    assert "ports_check" not in source
