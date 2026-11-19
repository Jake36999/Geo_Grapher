"""What an agent sees from the graph hub's MCP server: results a text-only client can read, and descriptions that
name only the arguments the tool really takes (agent review 2026-11-19, F-04 and F-06)."""
import json

import anyio
import pytest
from mcp import types

from geographer.graph_server import create_graph_mcp, flat_guidance
from test_graph_catalog import hub  # noqa: F401


def call(router, name, arguments, text_content):
    handler = create_graph_mcp(router, text_content=text_content)._mcp_server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(method="tools/call", params=types.CallToolRequestParams(name=name, arguments=arguments))
    return anyio.run(handler, request).root


def tools(router):
    handler = create_graph_mcp(router)._mcp_server.request_handlers[types.ListToolsRequest]
    return {t.name: t for t in anyio.run(handler, types.ListToolsRequest(method="tools/list")).root.tools}


def test_results_are_structured_only_by_default(hub):
    catalog, router, first = hub
    result = call(router, "list_graphs", {}, text_content=False)
    assert result.content == [] and result.structuredContent["graphs"][0]["graph_id"] == first["graph_id"]


def test_a_text_only_client_can_ask_for_the_json_as_text(hub):
    catalog, router, first = hub
    result = call(router, "list_graphs", {}, text_content=True)
    assert len(result.content) == 1 and result.content[0].type == "text"
    assert json.loads(result.content[0].text) == result.structuredContent  # the same answer, not a different one


def test_an_error_is_also_readable_as_text(hub):
    catalog, router, first = hub
    result = call(router, "list_bridges", {"graph_ids": ["g_does_not_exist"]}, text_content=True)
    assert result.isError and "error" in json.loads(result.content[0].text)


def test_descriptions_name_only_arguments_the_tool_takes(hub):
    catalog, router, first = hub
    listed = tools(router)
    for name, tool in listed.items():
        props = set((tool.inputSchema or {}).get("properties", {}))
        # a flat tool must not tell an agent to pass an argument its schema refuses
        for argument in ("content_kind", "direction"):
            if argument in tool.description:
                assert argument in props, f"{name} mentions {argument} but does not accept it"
    assert "content_kind" not in listed["search_entities"].description
    assert "get_entity_content(entity_id=" in listed["search_entities"].description
    assert "outgoing" not in listed["find_dependants"].description and "incoming" in listed["find_dependants"].description
    assert "max_depth" in listed["find_dependants"].inputSchema["properties"]


def test_the_rewrite_leaves_other_guidance_alone():
    assert flat_guidance("check_architecture", "keep this") == "keep this"
    assert flat_guidance("search_entities", "x get_entity_content(content_kind=\"documentation\") y").startswith("x get_entity_content(entity_id=")
