"""Graph lifecycle: independent copy, safe delete, in-memory active set (master G8)."""
import json
import shutil
import threading
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from geographer.graph_merge import plan_merge, execute_merge
from geographer.graph_server import create_graph_http
from test_graph_catalog import hub, import_graph, request  # noqa: F401


def merge_two(catalog, a, b, label='Merged'):
    ids = [a, b]
    plan = plan_merge(catalog, ids, label)
    return execute_merge(catalog, ids, label, plan['plan_id'])


def test_copy_is_independent_and_queryable(hub, tmp_path):
    catalog, router, first = hub
    copy = catalog.copy_graph(first['graph_id'], 'A copy')
    assert copy['graph_id'] != first['graph_id'] and copy['copied_from'] == first['graph_id']
    assert catalog.graph(copy['graph_id'])['snapshot_id'] == first['ingestion']['snapshot_id'] == copy['snapshot_id']
    row = catalog.graph(copy['graph_id'])
    assert row['paper_database'] is None and row['root_key'] == 'copy:' + copy['graph_id']
    assert Path(row['code_database']) == catalog.path.parent / 'graphs' / copy['graph_id'] / 'code.sqlite'
    assert router.query(copy['graph_id'], 'search_entities', request(first))['result']['data']['hits']
    assert catalog.copy_graph(first['graph_id'], 'A copy')['graph_id'] == copy['graph_id']
    # A copy must not make its source root look like an overlap.
    assert catalog.plan_root(tmp_path / 'a')['collisions'] == []


def test_delete_removes_owned_store_and_bridges(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    bridge = catalog.add_bridge(first['graph_id'], 'root', second['graph_id'], 'root', 'reference', 'test', [{'note': 'x'}])
    path = Path(catalog.graph(second['graph_id'])['code_database'])
    router.query(second['graph_id'], 'search_entities', request(second))  # opens the store
    receipt = catalog.delete_graph(second['graph_id'], retire=router.retire_graph)
    assert receipt['deleted'] == second['graph_id'] and receipt['bridges_removed'] == [bridge] and not path.exists()
    assert not path.parent.exists() and receipt['files_kept'] == [] and str(path) in receipt['files_unlinked']
    with pytest.raises(ValueError):
        catalog.graph(second['graph_id'])
    assert catalog.bridges([first['graph_id']]) == []


def test_delete_refuses_merge_source_and_never_unlinks_registered_store(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    merged = merge_two(catalog, first['graph_id'], second['graph_id'])
    with pytest.raises(ValueError, match='^GRAPH_IN_USE'):
        catalog.delete_graph(first['graph_id'], retire=router.retire_graph)
    with pytest.raises(ValueError, match='^GRAPH_IN_USE'):
        catalog.delete_graph(merged['graph_id'], retire=router.retire_graph)  # has a merge receipt
    third = import_graph(catalog, tmp_path / 'c', 'C')
    with pytest.raises(ValueError, match='^GRAPH_IN_USE'):
        catalog.delete_graph(third['graph_id'], protected=frozenset({third['graph_id']}))
    assert catalog.graph(first['graph_id'])
    external = tmp_path / 'external.sqlite'
    shutil.copy(catalog.graph(second['graph_id'])['code_database'], external)
    gid = catalog.register_existing_store(external)
    receipt = catalog.delete_graph(gid, retire=router.retire_graph)
    assert external.exists() and receipt['files_kept'] == [str(external.resolve())] and receipt['files_unlinked'] == []


def test_delete_waits_for_leases_then_unlinks(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    key, _ = router.acquire(second['graph_id'])
    t = threading.Timer(0.3, router.release, args=(key,))
    t.start()
    receipt = catalog.delete_graph(second['graph_id'], retire=router.retire_graph)
    t.join()
    assert receipt['files_unlinked']


def test_retire_times_out_with_graph_busy(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    key, _ = router.acquire(second['graph_id'])
    with pytest.raises(ValueError, match='^GRAPH_BUSY'):
        router.retire_graph(second['graph_id'], timeout=0.2)
    assert catalog.graph(second['graph_id'])  # nothing was deleted
    router.release(key)
    router.retire_graph(second['graph_id'], timeout=1)


def test_delete_endpoint_requires_matching_label(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    client = TestClient(create_graph_http(router), base_url='http://127.0.0.1:8774')
    wrong = client.request('DELETE', f"/api/graphs/{second['graph_id']}", json={'confirm_label': 'nope'})
    assert wrong.status_code == 400 and catalog.graph(second['graph_id'])
    ok = client.request('DELETE', f"/api/graphs/{second['graph_id']}", json={'confirm_label': 'B'})
    assert ok.status_code == 200 and ok.json()['deleted'] == second['graph_id']
    assert client.request('DELETE', f"/api/graphs/{second['graph_id']}", json={'confirm_label': 'B'}).status_code == 404


def test_delete_endpoint_protects_primary(hub, tmp_path):
    catalog, router, first = hub
    client = TestClient(create_graph_http(router, primary_graph_id=first['graph_id']), base_url='http://127.0.0.1:8774')
    refused = client.request('DELETE', f"/api/graphs/{first['graph_id']}", json={'confirm_label': 'A'})
    assert refused.status_code == 409 and refused.json()['error'].startswith('GRAPH_IN_USE')


def test_copy_endpoint_and_graph_summary_fields(hub, tmp_path):
    catalog, router, first = hub
    client = TestClient(create_graph_http(router), base_url='http://127.0.0.1:8774')
    assert client.post(f"/api/graphs/{first['graph_id']}/copy", json={'label': ''}).status_code == 400
    response = client.post(f"/api/graphs/{first['graph_id']}/copy", json={'label': 'Fork'})
    assert response.status_code == 200 and response.json()['copied_from'] == first['graph_id']
    rows = {g['graph_id']: g for g in client.get('/api/graphs').json()['graphs']}
    copy = rows[response.json()['graph_id']]
    assert copy['label'] == 'Fork' and copy['owned_store'] is True and copy['bridge_count'] == 0
    assert copy['graph_kind'] == 'copy' and copy['availability'] == 'available'


def test_active_set_validation_and_pruning_on_delete(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    client = TestClient(create_graph_http(router), base_url='http://127.0.0.1:8774')
    assert client.get('/api/workspace/active-graphs').json()['graph_ids'] == [first['graph_id']]
    ids = [second['graph_id'], first['graph_id']]
    assert client.put('/api/workspace/active-graphs', json={'graph_ids': ids}).json()['graph_ids'] == ids
    assert client.get('/api/workspace/active-graphs').json()['graph_ids'] == ids
    for bad in ([], [first['graph_id']] * 2, ['g_' + '0' * 24], ids * 3, 'x'):
        assert client.put('/api/workspace/active-graphs', json={'graph_ids': bad}).status_code == 400
    five = [first['graph_id']] + [catalog.copy_graph(first['graph_id'], f'c{i}')['graph_id'] for i in range(4)]
    assert client.put('/api/workspace/active-graphs', json={'graph_ids': five}).status_code == 400
    assert client.request('DELETE', f"/api/graphs/{second['graph_id']}", json={'confirm_label': 'B'}).status_code == 200
    assert client.get('/api/workspace/active-graphs').json()['graph_ids'] == [first['graph_id']]


def test_cli_copy_and_delete(hub, tmp_path, monkeypatch, capsys):
    import sys
    from geographer import cli
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    cat = str(catalog.path)
    monkeypatch.setattr(sys, 'argv', ['geographer', 'copy-graph', '--catalog', cat, '--graph-id', first['graph_id'], '--label', 'CLI copy'])
    cli.main()
    copied = json.loads(capsys.readouterr().out)
    assert copied['copied_from'] == first['graph_id']
    monkeypatch.setattr(sys, 'argv', ['geographer', 'delete-graph', '--catalog', cat, '--graph-id', second['graph_id'], '--confirm-label', 'wrong'])
    with pytest.raises(ValueError):
        cli.main()
    monkeypatch.setattr(sys, 'argv', ['geographer', 'delete-graph', '--catalog', cat, '--graph-id', second['graph_id'], '--confirm-label', 'B'])
    cli.main()
    assert json.loads(capsys.readouterr().out)['deleted'] == second['graph_id']
