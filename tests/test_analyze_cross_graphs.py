"""analyze_cross_graphs (cross-graph-v1) and the `cross` tool preset (master D6; wave 3 Task 6)."""
import pytest

from geographer.cross_graph import pack_items
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import TOOL_PRESETS, GraphRouter, offered_tools
from geographer.model import canonical
from geographer.source import Repository
from geographer.tokens import TokenCounter


def module(n, *, changed=()):
    out = []
    for i in range(n):
        body = f"    return {i} + 1\n" if i in changed else f"    return {i}\n"
        out.append(f"def fn_{i:03d}(x):\n{body}")
    return "\n".join(out)


@pytest.fixture
def router_two_graphs_many_entities(tmp_path):
    catalog = GraphCatalog(tmp_path / "cat" / "catalog.sqlite")
    ids = []
    for name, text in (("v1", module(60)), ("v2", module(55, changed={3, 4, 5}))):
        root = tmp_path / name; root.mkdir()
        (root / "m.py").write_text(text, encoding="utf-8")
        ids.append(catalog.import_project(root, Repository.from_directory(root, name), label=name)["graph_id"])
    router = GraphRouter(catalog)
    yield router, ids[0], ids[1]
    router.close(); catalog.close()


def test_cross_preset_has_six_tools():
    assert len(TOOL_PRESETS["cross"]) == 6 and "analyze_cross_graphs" in TOOL_PRESETS["cross"]
    assert offered_tools("cross") == TOOL_PRESETS["cross"] and "analyze_cross_graphs" in offered_tools("analyze_cross_graphs")


def test_evolution_diff_fits_budget_and_is_endpoint_closed(router_two_graphs_many_entities):
    router, a, b = router_two_graphs_many_entities
    out = router.analyze_cross_graphs([b, a], "evolution_diff", limit_tokens=1800)
    assert out["graph_ids"] == sorted([a, b]) and out["used_tokens"] <= 1800 and out["omitted_items"] > 0
    assert out["used_tokens"] == TokenCounter().count(out)
    assert out["engine_version"] == "cross-graph-v1" and out["ranking"] == "independent_per_graph_no_global_rank"
    node_ids = {(n["graph_id"], n["id"]) for n in out["nodes"]}
    assert all((e["graph_id"], e["id"]) in node_ids for it in out["items"] for e in it["endpoints"])
    used = {(e["graph_id"], e["id"]) for it in out["items"] for e in it["endpoints"]}
    assert node_ids == used  # no orphan nodes
    assert all(n["cite_as"].startswith(("v1/entity:", "v2/entity:")) for n in out["nodes"])
    counts = out["header"]["counts"]["classes"]
    assert counts["EXACT_AST_SURVIVOR"] >= 50 and counts["STRATUM_EXCLUSIVE"] >= 5
    assert "items" not in out["header"]  # the header carries only counts (Gemini defect 1)


def test_unavailable_modes_and_wrong_counts_rejected(router_two_graphs_many_entities):
    router, a, b = router_two_graphs_many_entities
    with pytest.raises(ValueError, match="MODE_NOT_AVAILABLE"):
        router.analyze_cross_graphs([a, b], "bridge_impact")
    with pytest.raises(ValueError, match="MODE_NOT_AVAILABLE"):
        router.analyze_cross_graphs([a, b], "theory_conformance")
    with pytest.raises(ValueError):
        router.analyze_cross_graphs([a], "clone_candidates")
    with pytest.raises(ValueError):
        router.analyze_cross_graphs([a, b], "nope")
    with pytest.raises(ValueError):
        router.analyze_cross_graphs([a, b], "evolution_diff", limit_tokens=100)


def test_cursor_resumes_without_duplicates_and_covers_everything(router_two_graphs_many_entities):
    router, a, b = router_two_graphs_many_entities
    seen, cursor, pages = [], None, 0
    while True:
        page = router.analyze_cross_graphs([a, b], "evolution_diff", limit_tokens=1800, cursor=cursor)
        assert page["used_tokens"] <= 1800
        seen.extend(canonical(i) for i in page["items"]); pages += 1
        cursor = page["next_cursor"]
        if cursor is None:
            break
        assert pages < 50
    assert pages >= 2 and len(seen) == len(set(seen)) == page["header"]["total_items"]


def test_stale_and_invalid_cursors(router_two_graphs_many_entities, tmp_path):
    router, a, b = router_two_graphs_many_entities
    first = router.analyze_cross_graphs([a, b], "evolution_diff", limit_tokens=1800)
    with pytest.raises(ValueError, match="INVALID_CURSOR"):
        router.analyze_cross_graphs([a, b], "evolution_diff", cursor="nope")
    with pytest.raises(ValueError, match="STALE_CURSOR"):
        router.analyze_cross_graphs([a, b], "clone_candidates", cursor=first["next_cursor"])  # bound to mode + snapshots
    root = tmp_path / "v2"; (root / "m.py").write_text(module(54), encoding="utf-8")
    router.catalog.import_project(root, Repository.from_directory(root, "v2"), label="v2")
    with pytest.raises(ValueError, match="STALE_CURSOR"):
        router.analyze_cross_graphs([a, b], "evolution_diff", cursor=first["next_cursor"])


def test_clone_candidates_items_and_closure(router_two_graphs_many_entities):
    router, a, b = router_two_graphs_many_entities
    out = router.analyze_cross_graphs([a, b], "clone_candidates", limit_tokens=4096)
    assert out["items"] and {i["match"] for i in out["items"]} <= {"py-ast-v1", "signature+guard"}
    node_ids = {(n["graph_id"], n["id"]) for n in out["nodes"]}
    assert all((e["graph_id"], e["id"]) in node_ids for it in out["items"] for e in it["endpoints"])


def test_bridge_candidates_are_unreviewed_and_write_nothing(router_two_graphs_many_entities):
    router, a, b = router_two_graphs_many_entities
    out = router.analyze_cross_graphs([a, b], "bridge_candidates", limit_tokens=4096)
    assert all(i["status"] == "unreviewed" and i["score"] >= 0.30 for i in out["items"])
    assert router.catalog.connection.execute("SELECT count(*) FROM bridge_proposals").fetchone()[0] == 0
    assert router.catalog.bridges([a, b]) == []


def test_respects_connection_allow_list(router_two_graphs_many_entities):
    router, a, b = router_two_graphs_many_entities
    scoped = GraphRouter(router.catalog, allowed=[a])
    try:
        with pytest.raises(ValueError, match="not available"):
            scoped.analyze_cross_graphs([a, b], "evolution_diff")
    finally:
        scoped.close()


def test_pack_items_drops_whole_items_and_keeps_closure():
    header = dict(engine_version="cross-graph-v1", next_cursor="x" * 26, limit_tokens=300)
    bundles = [dict(item=dict(n=i, endpoints=[dict(graph_id="g", id=f"e{i}")]), nodes=[dict(graph_id="g", id=f"e{i}", qualified_name="q" * 20)])
               for i in range(100)]
    counter = TokenCounter()
    out = pack_items(header, bundles, 300, counter)
    assert 0 < len(out["items"]) < 100 and out["omitted_items"] == 100 - len(out["items"])
    assert out["used_tokens"] == counter.count(out) <= 300
    assert [i["n"] for i in out["items"]] == list(range(len(out["items"])))  # in order, whole
    assert {n["id"] for n in out["nodes"]} == {f"e{i}" for i in range(len(out["items"]))}
    with pytest.raises(ValueError, match="BUDGET_TOO_SMALL"):
        pack_items(dict(big="x" * 4000), bundles, 300, counter)


def test_mcp_tool_listed_in_cross_preset(router_two_graphs_many_entities):
    import anyio
    from geographer.graph_server import create_graph_mcp
    router, a, b = router_two_graphs_many_entities
    scoped = GraphRouter(router.catalog, tools="cross")
    mcp = create_graph_mcp(scoped)
    async def names():
        from mcp.types import ListToolsRequest
        handler = mcp._mcp_server.request_handlers[ListToolsRequest]
        result = await handler(ListToolsRequest(method="tools/list"))
        return sorted(t.name for t in result.root.tools)
    try:
        assert anyio.run(names) == sorted(TOOL_PRESETS["cross"])
    finally:
        scoped.close()


def test_connection_char_cap_is_respected_by_dropping_whole_items(router_two_graphs_many_entities):
    import json
    router, a, b = router_two_graphs_many_entities
    capped = GraphRouter(router.catalog, max_result_chars=7500)
    try:
        seen, cursor = [], None
        for mode in ("evolution_diff", "clone_candidates", "bridge_candidates"):
            cursor = None
            while True:
                out = capped.analyze_cross_graphs([a, b], mode, limit_tokens=8192, cursor=cursor)
                assert len(json.dumps(out, ensure_ascii=False)) <= 7500
                if mode == "evolution_diff":
                    seen.extend(canonical(i) for i in out["items"]); total = out["header"]["total_items"]
                cursor = out["next_cursor"]
                if cursor is None:
                    break
        assert len(seen) == len(set(seen)) == total  # every item delivered exactly once across capped pages
    finally:
        capped.close()
