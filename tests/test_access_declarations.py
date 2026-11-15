"""All three shipped MCP surfaces need a reviewed access declaration, including opt-in annotations."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def auditor():
    spec = importlib.util.spec_from_file_location('geo_access_audit', ROOT / 'scripts/audit_tool_access.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_every_mcp_operation_has_an_access_review():
    review = json.loads((ROOT / 'docs/tool-access-declarations.json').read_text(encoding='utf-8'))
    assert auditor().validate(review['tools'], auditor().discover()) == []


def test_new_content_tool_requires_its_own_declaration():
    assert auditor().validate([], ['scoped:new_reader']) == ['UNDECLARED_ACCESS: scoped:new_reader']


def test_opt_in_paper_annotation_is_in_the_inventory_even_when_disabled():
    assert 'paper:annotate_document' in auditor().discover()


def test_discovery_uses_the_scoped_protocol_handler_not_the_empty_fastmcp_manager():
    assert {'scoped:search_entities', 'scoped:paper_get_document', 'scoped:compile_task_packet'} <= set(auditor().discover())


def test_new_protocol_content_tool_is_caught_without_changing_the_discovery_list(monkeypatch):
    from mcp import types
    import geographer.graph_server as graph_server
    original = graph_server.create_graph_mcp
    def factory(*args, **kwargs):
        server = original(*args, **kwargs); handlers = server._mcp_server.request_handlers
        previous = handlers[types.ListToolsRequest]
        async def expanded(request):
            response = await previous(request)
            response.root.tools.append(types.Tool(name='brand_new_reader', inputSchema={'type':'object'}))
            return response
        handlers[types.ListToolsRequest] = expanded
        return server
    monkeypatch.setattr(graph_server, 'create_graph_mcp', factory)
    review = json.loads((ROOT / 'docs/tool-access-declarations.json').read_text(encoding='utf-8'))
    assert auditor().validate(review['tools'], auditor().discover()) == ['UNDECLARED_ACCESS: scoped:brand_new_reader']
