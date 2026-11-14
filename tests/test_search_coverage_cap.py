"""Coverage overhead must not strand fitting at a large requested hit count."""
import json
from geographer.agent_requests import call_code
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.source import Repository


def test_large_search_limit_fits_with_coverage(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    source = '\n'.join(f'def quartz_{n}():\n    """quartz contracts {"evidence " * 25}"""\n    return {n}\n' for n in range(50))
    (root / 'api.py').write_text(source)
    catalog = GraphCatalog(tmp_path / 'catalog.sqlite')
    row = catalog.import_project(root, Repository.from_directory(root, 'cap'), label='cap')
    router = GraphRouter(catalog, max_result_chars=7500)
    try:
        out = call_code(router, 'search_entities', {'graph_id': 'cap', 'query': 'quartz', 'limit': 50})
        assert out['entities'] and out['coverage']
        assert len(json.dumps(out, ensure_ascii=False)) <= 7500
    finally:
        router.close()
        catalog.close()
