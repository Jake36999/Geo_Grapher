"""Invalid IDs have bounded real choices from this connection and graph only."""
import json
import pytest
from test_task_packets import packet_world
from geographer.agent_requests import call_code_connection, error
from geographer.source import Repository


class Connection:
    pass


def rejection(router, connection, graph, value):
    with pytest.raises(ValueError) as caught:
        call_code_connection(router, 'get_entity_content', {'graph_id': graph, 'entity_id': value}, connection)
    return error('get_entity_content', caught.value)['error']


def test_invalid_id_offers_recent_real_candidate_and_executable_example(packet_world):
    cat, router, gid, ids = packet_world
    connection = Connection()
    call_code_connection(router, 'search_entities', {'graph_id': 'code', 'query': 'm.py.f'}, connection)
    result = rejection(router, connection, 'code', ids['f'][:-3] + 'bad')
    assert 1 <= len(result['choices']) <= 3
    assert len(json.dumps(result['choices'], ensure_ascii=False)) <= 400
    assert len(result['message']) <= 400
    choice = result['choices'][0]
    assert choice == {'entity_id': ids['f'], 'qualified_name': 'm.py.f', 'cite_as': 'code/entity:' + ids['f']}
    actual = call_code_connection(router, 'get_entity_content', result['example'], connection)
    assert 'def f' in json.dumps(actual)


def test_recovery_cache_never_crosses_connections_or_graphs(packet_world, tmp_path):
    cat, router, gid, ids = packet_world
    first, second = Connection(), Connection()
    call_code_connection(router, 'search_entities', {'graph_id': 'code', 'query': 'm.py.f'}, first)
    assert 'choices' not in rejection(router, second, 'code', ids['f'][:-3] + 'bad')
    root = tmp_path / 'other'
    root.mkdir()
    (root / 'other.py').write_text('def other(): return 2\n')
    graph = cat.import_project(root, Repository.from_directory(root, 'other'), label='other')
    assert 'choices' not in rejection(router, first, 'other', ids['f'])


def test_without_recent_search_only_exact_name_lookup_is_allowed(packet_world):
    cat, router, gid, ids = packet_world
    connection = Connection()
    found = rejection(router, connection, 'code', 'm.py.f')
    assert found['choices'][0]['entity_id'] == ids['f']
    assert 'choices' not in rejection(router, connection, 'code', 'entirely_unknown')
