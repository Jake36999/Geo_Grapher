"""Natural-language retrieval remains separate from exact symbol lookup."""
from geographer.retrieval import LexicalIndex


def test_plural_queries_find_singular_symbol_subtokens(extract):
    graph, _, _ = extract({'settings.py': 'WORKER_TOOL = ("open", "inspect")\ndef worker_count(): return 2\ndef tool_count(): return 3\n'})
    index = LexicalIndex(graph)
    try:
        hits = index.search('tools for workers', mode='lexical')
        assert hits and graph.entities[hits[0]['node_id']].qualified_name == 'settings.py.WORKER_TOOL'
        assert 'qualified_name' in hits[0]['matched_fields']
        assert index.search('settings.py.WORKER_TOOL')[0]['score'] == 1.0
    finally:
        index.close()


def test_function_words_do_not_outweigh_matching_subjects(extract):
    graph, _, _ = extract({'settings.py': 'WORKER_TOOL = ("open", "inspect")\ndef for_the_to(with_value): return with_value\n'})
    index = LexicalIndex(graph)
    try:
        hits = index.search('the tools for the workers to use', mode='lexical')
        assert hits and graph.entities[hits[0]['node_id']].qualified_name == 'settings.py.WORKER_TOOL'
    finally:
        index.close()


def test_exact_function_word_symbols_still_resolve(extract):
    graph, _, _ = extract({'api.py': 'def where(): return 1\ndef uses(): return 2\n'})
    index = LexicalIndex(graph)
    try:
        assert index.search('api.py.where')[0]['score'] == 1.0
        assert index.search('where', mode='lexical')
    finally:
        index.close()


def test_bounded_actor_search_preserves_the_highest_ranked_hit(tmp_path):
    from geographer.agent_requests import call_code
    from geographer.graph_catalog import GraphCatalog
    from geographer.graph_router import GraphRouter
    from geographer.source import Repository
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'settings.py').write_text(
        '# Upload buffer used for incoming files.\n'
        '# Bounds memory while accepting streams.\n'
        '# Units are raw bytes in memory.\n'
        '# Change this only with a memory budget.\n'
        'UPLOAD_BUFFER = 4096\n'
        'def upload(): return 1\n'
        'def buffer(): return 2\n'
        'def uploads(): return 3\n'
        'def buffers(): return 4\n')
    catalog = GraphCatalog(tmp_path / 'catalog.sqlite')
    graph = catalog.import_project(root, Repository.from_directory(root, 'ranked'), label='ranked')
    router = GraphRouter(catalog, max_result_chars=7500)
    try:
        with router.lease(graph['graph_id']) as service:
            index = LexicalIndex(service.store.graph(catalog.graph(graph['graph_id'])['snapshot_id']))
            try:
                highest = index.search('upload buffer')[0]['node_id']
            finally:
                index.close()
        result = call_code(router, 'search_entities', {'graph_id': 'ranked', 'query': 'upload buffer'})
        assert result['entities'][0]['entity_id'] == highest
    finally:
        router.close()
        catalog.close()
