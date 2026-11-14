import json

import pytest

from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.source import Repository
from geographer.agent_requests import canonical_flat


@pytest.fixture
def world(tmp_path):
    catalog = GraphCatalog(tmp_path / 'catalog.sqlite'); rows = []
    for name, role in [('own', 'current'), ('upstream', 'third_party')]:
        root = tmp_path / name; root.mkdir(); (root / 'm.py').write_text('def example(x):\n    return x\n')
        row = catalog.import_project(root, Repository.from_directory(root, name), label=name)
        catalog.set_stratum(row['graph_id'], role, 'bronze' if role == 'third_party' else 'gold', 'code')
        rows.append(row['graph_id'])
    router = GraphRouter(catalog)
    yield catalog, router, *rows
    router.close(); catalog.close()


def test_clerk_connection_refuses_third_party_before_open(world):
    cat, _, own, third = world
    with pytest.raises(ValueError, match='THIRD_PARTY_SCOPE'):
        GraphRouter(cat, allowed=[own, third], consumer_role='clerk', tools='lead')


def test_tier3_packet_refused_before_reading_anchors(world):
    _, router, _, third = world
    with pytest.raises(ValueError, match='THIRD_PARTY_SCOPE'):
        router.compile_task_packet(third, ['entity:missing'], 'Describe.', profile='tier3_leaf')


def test_search_and_packet_provenance_are_graph_qualified(world):
    cat, router, _, third = world
    sid = cat.graph(third)['snapshot_id']
    request = dict(schema_version='1.1', request_id='fixture', snapshot_id=sid,
        budget=dict(limit_tokens=8192, tokenizer='o200k_base', allow_byte_fallback=False),
        query='example', mode='lexical', repo_ids=[], kinds=[], limit=5, cursor=None)
    out = router.query(third, 'search_entities', request)
    flat = canonical_flat(router, third, cat.graph(third), out)
    assert flat['provenance'] == 'third_party'
    assert flat['result']['data']['hits']
    assert all(h['provenance'] == 'third_party' and h['cite_as'].startswith('upstream/')
               for h in flat['result']['data']['hits'])
    with router.lease(third) as service:
        eid = service.store.connection.execute("SELECT entity_id FROM entities WHERE kind='function' AND snapshot_id=?", (sid,)).fetchone()[0]
    packet = router.compile_task_packet(third, ['entity:' + eid], 'Describe.', profile='tier2_forager')
    assert packet['provenance'] == 'third_party'
    assert packet['anchors'][0]['provenance'] == 'third_party'


def test_federated_rows_have_provenance(world):
    _, router, own, third = world
    result = router.federated_search([own, third], 'example', limit_tokens=8192, mode='lexical', agent=True)
    external = next(r for r in result['results'] if r['graph_id'] == third)
    assert external['provenance'] == 'third_party'


def test_equivalence_cannot_cross_third_party_boundary(world):
    cat, _, own, third = world
    with pytest.raises(ValueError, match='THIRD_PARTY_BRIDGE'):
        cat.add_bridge(own, 'root', third, 'root', 'concept_equivalence', 'person asked', [{'owner_decision': True}])
    assert cat.propose_bridges(own, third, kind='concept_equivalence') == []
    with pytest.raises(ValueError, match='OWNER_DECISION_REQUIRED'):
        cat.add_bridge(own, 'root', third, 'root', 'reference', 'some rationale', [{'automatic': True}])
    assert cat.add_bridge(own, 'root', third, 'root', 'reference', 'explicit owner choice', [{'owner_decision': True}])


def test_generated_clerk_mcp_entry_contains_only_own_graphs(world):
    from geographer.provenance import mcp_entries
    cat, _, own, third = world
    entries = mcp_entries(cat, ['pinned-geographer'])
    clerk = entries['geo-own-packets']['args']
    assert '--consumer-role' in clerk and 'clerk' in clerk
    assert own in clerk and third not in clerk
    assert third in entries['geo-references']['args']


def test_clerk_server_requires_an_explicit_allowlist(world):
    cat, _, _, _ = world
    with pytest.raises(ValueError, match='THIRD_PARTY_SCOPE'):
        GraphRouter(cat, consumer_role='clerk')


def test_flat_search_cannot_drop_tier3_scope_during_internal_materialisation(world):
    from geographer.agent_requests import call_code
    _, router, _, third = world
    with pytest.raises(ValueError, match='THIRD_PARTY_SCOPE'):
        call_code(router, 'search_entities', dict(graph_id=third, query='example', profile='tier3_leaf'))


def test_final_flat_search_preserves_provenance_after_projection(world):
    from geographer.agent_requests import call_code
    _, router, _, third = world
    out = call_code(router, 'search_entities', dict(graph_id=third, query='example', profile='tier2_forager'))
    for key in ('hits', 'nodes'):
        assert out['result']['data'][key]
        assert all(row['provenance']=='third_party' and row['cite_as'].startswith('upstream/')
                   for row in out['result']['data'][key])
