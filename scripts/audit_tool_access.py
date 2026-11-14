"""Enumerate every shipped MCP surface, including opt-in paper annotation, without serving/calling it."""
import argparse
import asyncio
import ast
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def discover():
    from geographer.server import OPERATIONS
    from geographer.graph_server import create_graph_mcp
    names = {'canonical:' + name for name in OPERATIONS}
    # Enumerate the actual list_tools response, without opening a store or invoking a tool.
    router = SimpleNamespace(allowed=None, offered_tools=None,
        catalog=SimpleNamespace(graphs=lambda: [{'paper_database':'metadata-only-presence-marker'}]))
    from mcp import types
    server = create_graph_mcp(router)._mcp_server
    result = asyncio.run(server.request_handlers[types.ListToolsRequest](types.ListToolsRequest(method='tools/list')))
    names |= {'scoped:' + tool['name'] for tool in result.model_dump()['tools']}
    tree = ast.parse((ROOT / 'pipeline/mcp_doc_graph.py').read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'tool' for d in node.decorator_list):
                names.add('paper:' + node.name)
    return sorted(names)


def validate(rows, tools):
    indexed = {row['tool']: row for row in rows}; problems = []
    if len(indexed) != len(rows): problems.append('DUPLICATE_ACCESS_DECLARATION')
    for name in tools:
        row = indexed.get(name)
        if row is None: problems.append('UNDECLARED_ACCESS: ' + name); continue
        if not row.get('actors') or type(row.get('returns_content')) is not bool:
            problems.append('INVALID_ACCESS: ' + name)
        if row.get('returns_content') and (row.get('status') not in {'conforms','diverges'} or not row.get('fixes')):
            problems.append('INVALID_CONTENT_ACCESS: ' + name)
        if not set(row.get('authorship_may_return', [])) <= {'owner_created','generated','third_party'}:
            problems.append('INVALID_AUTHORSHIP: ' + name)
    for name in sorted(set(indexed)-set(tools)): problems.append('ORPHANED_ACCESS: ' + name)
    return problems


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--discover', action='store_true'); parser.add_argument('--declarations', type=Path,
        default=ROOT / 'docs/tool-access-declarations.json'); args = parser.parse_args()
    if args.discover:
        print(json.dumps(discover())); return
    review = json.loads(args.declarations.read_text(encoding='utf-8')); problems = validate(review['tools'], discover())
    content = [r for r in review['tools'] if r['returns_content']]
    print(json.dumps(dict(operations=len(review['tools']), content=len(content),
                         conforms=sum(r['status']=='conforms' for r in content), problems=problems), indent=2))
    raise SystemExit(bool(problems))


if __name__ == '__main__': main()
