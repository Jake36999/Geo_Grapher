import json

import pytest

from geographer.provenance import metadata, annotate_flat


@pytest.mark.parametrize('purpose,expected', [('own-current', 'owner_created'),
    ('own-legacy', 'owner_created'), ('own-docs', 'owner_created'),
    ('research-docs', 'third_party'), ('third-party', 'third_party'), ('generated', 'generated')])
def test_projection_resolves_authorship_once_at_the_graph_boundary(purpose, expected):
    graph = {'label': 'fixture', 'profile_json': json.dumps({'stratum': {'purpose': purpose}})}
    assert metadata(graph)['authorship'] == expected
    out = annotate_flat(graph, {'entities': [{'entity_id': 'a'}]})
    assert out['entities'][0]['authorship'] == expected
    assert out['entities'][0]['cite_as'] == 'fixture/entity:a'


def test_unclassified_graph_is_a_defect_never_silently_own():
    graph = {'label': 'fixture', 'profile_json': '{}'}
    assert metadata(graph)['authorship'] is None
    assert metadata(graph)['authorship_resolution'] == 'unclassified'


def test_third_party_data_authorship_enforces_the_reader_boundary():
    from geographer.provenance import enforce_reader
    graph = {'label': 'dataset', 'profile_json': json.dumps({'stratum': {
        'role': 'data', 'authorship': 'third_party'}})}
    with pytest.raises(ValueError, match='THIRD_PARTY_SCOPE'):
        enforce_reader(graph, consumer_role='clerk')


def test_multi_graph_transport_metadata_preserves_each_source_author():
    from types import SimpleNamespace
    from geographer.provenance import response_metadata
    graphs = {'own': {'graph_id': 'own', 'label': 'own', 'profile_json': json.dumps({
        'stratum': {'authorship': 'owner_created'}})},
        'ref': {'graph_id': 'ref', 'label': 'ref', 'profile_json': json.dumps({
            'stratum': {'authorship': 'third_party'}})}}
    router = SimpleNamespace(resolve=lambda ref: ref, catalog=SimpleNamespace(graph=lambda ref: graphs[ref]))
    out = response_metadata(router, {'graph_ids': ['own', 'ref']})
    assert {r['authorship'] for r in out['source_provenance']} == {'owner_created', 'third_party'}


@pytest.mark.parametrize('authorship', [None, 'owner_created', 'third_party'])
def test_canonical_transport_reports_unclassified_authorship_without_changing_v11_body(tmp_path, authorship):
    import asyncio
    from mcp import types
    from geographer.graph_catalog import GraphCatalog
    from geographer.graph_router import GraphRouter
    from geographer.server import create_server
    from test_graph_catalog import import_graph, request
    catalog = GraphCatalog(tmp_path / 'catalog.sqlite')
    graph = import_graph(catalog, tmp_path / 'repo', 'fixture')
    if authorship:
        with catalog.connection:
            catalog.connection.execute('UPDATE graphs SET profile_json=?',
                (json.dumps({'stratum': {'authorship': authorship}}),))
    router = GraphRouter(catalog)
    with router.lease(graph['graph_id']) as service:
        server = create_server(service, wire_version='1.1')._mcp_server
        result = asyncio.run(server.request_handlers[types.CallToolRequest](types.CallToolRequest(
            method='tools/call', params={'name': 'search_entities', 'arguments': request(graph)})))
        data = result.model_dump(mode='json', by_alias=True)
        assert data['_meta']['access']['authorship_resolution'] == ('declared' if authorship else 'unclassified')
        assert data['_meta']['access']['authorship'] == authorship
        assert data['structuredContent']['schema_version'] == '1.1'
        assert 'access' not in data['structuredContent']  # stable contract body
    router.close()
    catalog.close()
