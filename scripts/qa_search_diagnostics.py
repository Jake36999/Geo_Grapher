"""No-model discovery diagnostics through the agent-facing code adapter."""
import argparse
import json
from pathlib import Path

from geographer.agent_requests import call_code
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--graph', required=True)
    parser.add_argument('--query', action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Use a new evidence path; preserve every first result')
    catalog = GraphCatalog(args.catalog)
    router = GraphRouter(catalog, max_result_chars=7500)
    rows = []
    try:
        for query in args.query:
            result = call_code(router, 'search_entities', {'graph_id': args.graph, 'query': query})
            rows.append({'query': query, 'response': result})
            args.out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
            print(json.dumps({'query': query, 'entities': [e.get('qualified_name') for e in result.get('entities', [])]}, ensure_ascii=False))
    finally:
        router.close()
        catalog.close()


if __name__ == '__main__':
    main()
