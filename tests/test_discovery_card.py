import os
import subprocess
import sys

import pytest

from geographer.discovery import fas_min, build_card, render_markdown, quotient_cycles, feedback_arcs
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore

FILES = {
    "a.py": "from b import g\n\ndef f():\n    return g()\n\ndef k():\n    return 1\n",
    "b.py": "from a import k\n\ndef g():\n    return 1\n\ndef h():\n    return k()\n",
}


def _build(store):
    repo = Repository("repo", "fixture-revision", {p: s.encode() for p, s in FILES.items()})
    return store, ingest(store, [repo], stage=3)["snapshot_id"]


@pytest.fixture
def ping_pong_store():
    store = SnapshotStore()
    yield _build(store)
    store.close()


@pytest.fixture
def ping_pong_store_path(tmp_path):
    path = tmp_path / "pp.sqlite"
    store = SnapshotStore(path)
    _build(store)
    store.close()
    return path


def test_fas_exact_regime_on_triangle():
    w, order = fas_min(3, {(0, 1): 1, (1, 2): 1, (2, 0): 1})
    assert w == 1 and sorted(order) == [0, 1, 2]


def test_fas_exact_prefers_lightest_back_arcs():
    w, order = fas_min(2, {(0, 1): 5, (1, 0): 2})
    assert w == 2 and order == [0, 1]


def test_fas_floor_is_one():
    assert fas_min(2, {})[0] == 1


def test_fas_greedy_regime_is_deterministic():
    k = 10
    edges = {(i, (i + 1) % k): 1 for i in range(k)} | {(i, (i + 3) % k): 2 for i in range(k)}
    assert fas_min(k, edges) == fas_min(k, dict(reversed(list(edges.items()))))


def test_card_finds_ping_pong_file_cycle(ping_pong_store):
    card = build_card(*ping_pong_store)
    top = card["quotient_cycles"][0]
    assert top["rho_c6"] == 1.0 and set(top["members_labels"]) == {"a.py", "b.py"}


def test_card_honesty_line_without_runtime(ping_pong_store):
    card = build_card(*ping_pong_store)
    assert "no runtime, performance or quality claim" in card["honesty"]
    assert all(row["source_analysis"] for sect in ("quotient_cycles", "boundary_bottlenecks", "surprising_links") for row in card[sect])
    assert card["card_version"] == "discovery-card-v1" and card["sources"]


def test_card_bytes_identical_across_processes(ping_pong_store_path):
    outs = {subprocess.run([sys.executable, "-m", "geographer", "discovery-report", "--store", str(ping_pong_store_path), "--out", "-"],
                           env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, check=True).stdout for seed in ("1", "2")}
    assert len(outs) == 1 and next(iter(outs))


def test_quotient_cycles_and_feedback_arcs(ping_pong_store):
    cycles = quotient_cycles(*ping_pong_store)
    assert len(cycles) == 1 and cycles[0]["member_rel_paths"] == ["a.py", "b.py"]
    arcs = feedback_arcs(*ping_pong_store)
    # A 2-cycle needs exactly one back direction; the fixture's a->b and b->a each carry two
    # projection rows (calls, imports_from), so the one back direction yields two projection ids.
    rows = ping_pong_store[0].connection.execute(
        "SELECT source_rep_id,target_rep_id FROM quotient_projections WHERE projection_id IN (%s)" % ",".join("?" * len(arcs)), sorted(arcs)).fetchall()
    assert len(arcs) == 2 and len({tuple(r) for r in rows}) == 1


def test_markdown_under_token_budget(ping_pong_store):
    from geographer.tokens import TokenCounter
    assert TokenCounter().count(render_markdown(build_card(*ping_pong_store))) <= 1100


def test_mcp_discovery_resources(ping_pong_store_path, tmp_path):
    import anyio
    from mcp import types
    from geographer.graph_catalog import GraphCatalog
    from geographer.graph_router import GraphRouter
    from geographer.graph_server import create_graph_mcp
    catalog = GraphCatalog(tmp_path / "catalog.sqlite")
    graph_id = catalog.register_existing_store(ping_pong_store_path)
    graph_id = graph_id["graph_id"] if isinstance(graph_id, dict) else graph_id
    router = GraphRouter(catalog)
    try:
        server = create_graph_mcp(router)._mcp_server
        handlers = server.request_handlers

        async def read(uri):
            req = types.ReadResourceRequest(method="resources/read", params=types.ReadResourceRequestParams(uri=uri))
            return (await handlers[types.ReadResourceRequest](req)).root.contents[0]

        async def go():
            return (await read(f"geographer://graphs/{graph_id}/discovery"), await read(f"geographer://graphs/{graph_id}/discovery.md"))
        js, md = anyio.run(go)
        assert '"card_version":"discovery-card-v1"' in js.text and "no runtime, performance or quality claim" in md.text
    finally:
        router.close()
        catalog.close()
