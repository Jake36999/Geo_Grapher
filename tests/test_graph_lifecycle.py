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
    assert 'stratum' not in json.loads(row['profile_json'])
    catalog.set_stratum(first['graph_id'], 'primary', 'gold', 'code')
    stratified = catalog.copy_graph(first['graph_id'], 'Stratified')
    assert json.loads(catalog.graph(stratified['graph_id'])['profile_json'])['stratum'] == json.loads(catalog.graph(first['graph_id'])['profile_json'])['stratum']
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


def test_retired_graph_cannot_reopen_before_catalog_delete(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    router.query(second['graph_id'], 'search_entities', request(second))
    path = Path(catalog.graph(second['graph_id'])['code_database'])
    seen = []

    def retire_then_probe(gid):
        router.retire_graph(gid)
        with pytest.raises(ValueError, match='^GRAPH_BUSY'):
            router.acquire(gid)  # catalog row still exists here
        seen.append(True)
    receipt = catalog.delete_graph(second['graph_id'], retire=retire_then_probe, restore=router.unretire_graph)
    assert seen and receipt['files_kept'] == [] and not path.exists()


def test_refused_or_timed_out_delete_leaves_graph_acquirable(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    key, _ = router.acquire(second['graph_id'])
    original = router.retire_graph
    with pytest.raises(ValueError, match='^GRAPH_BUSY'):
        catalog.delete_graph(second['graph_id'], retire=lambda g: original(g, timeout=0.2))
    router.release(key)
    router.release(router.acquire(second['graph_id'])[0])
    with pytest.raises(ValueError, match='^GRAPH_IN_USE'):
        catalog.delete_graph(second['graph_id'], retire=router.retire_graph, protected=frozenset({second['graph_id']}))
    router.release(router.acquire(second['graph_id'])[0])
    # Refusal discovered only inside the transaction (after retire) also restores access.
    def retire_then_merge(gid):
        router.retire_graph(gid)
        merge_two(catalog, first['graph_id'], gid)
    with pytest.raises(ValueError, match='^GRAPH_IN_USE'):
        catalog.delete_graph(second['graph_id'], retire=retire_then_merge, restore=router.unretire_graph)
    router.release(router.acquire(second['graph_id'])[0])


def test_merge_landing_during_retire_aborts_delete_without_changes(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / 'b', 'B')
    path = Path(catalog.graph(second['graph_id'])['code_database'])
    bridge = catalog.add_bridge(first['graph_id'], 'root', second['graph_id'], 'root', 'reference', 'test', [{'note': 'x'}])

    def retire_then_merge(gid):
        router.retire_graph(gid)
        merge_two(catalog, first['graph_id'], gid)
    with pytest.raises(ValueError, match='^GRAPH_IN_USE'):
        catalog.delete_graph(second['graph_id'], retire=retire_then_merge)
    assert catalog.graph(second['graph_id']) and path.is_file()
    assert [b['bridge_id'] for b in catalog.bridges([first['graph_id'], second['graph_id']])] == [bridge]


def test_copy_backup_does_not_hold_catalog_lock(hub, tmp_path):
    catalog, router, first = hub
    other = import_graph(catalog, tmp_path / 'b', 'B')
    started, release = threading.Event(), threading.Event()
    real = catalog._backup

    def slow(src, dst):
        started.set()
        assert release.wait(30)
        real(src, dst)

    catalog._backup = slow
    result = {}
    worker = threading.Thread(target=lambda: result.update(catalog.copy_graph(first['graph_id'], 'Slow')))
    worker.start()
    try:
        assert started.wait(30)
        probe = {}
        reader = threading.Thread(target=lambda: probe.update(row=catalog.graph(other['graph_id'])))
        reader.start();reader.join(5)
        assert not reader.is_alive() and probe['row']['graph_id'] == other['graph_id']
    finally:
        release.set();worker.join(30)
    assert result['graph_id'] and catalog.graph(result['graph_id'])


def test_copy_clears_stale_store_files(hub, tmp_path):
    catalog, router, first = hub
    from geographer.model import digest
    new_id = 'g_' + digest('copy-v1', first['graph_id'], 'Stale', first['ingestion']['snapshot_id'])[:24]
    directory = catalog.path.parent / 'graphs' / new_id
    directory.mkdir(parents=True)
    for name in ('code.sqlite', 'code.sqlite-wal', 'code.sqlite-shm'):
        (directory / name).write_bytes(b'stale')
    copy = catalog.copy_graph(first['graph_id'], 'Stale')
    assert copy['graph_id'] == new_id
    assert not (directory / 'code.sqlite-wal').exists()
    assert router.query(new_id, 'search_entities', request(first))['result']['data']['hits']


def test_concurrent_same_id_copies_do_not_clobber(hub, tmp_path):
    catalog, router, first = hub
    inside = threading.Event()
    release = threading.Event()
    original = catalog._backup

    def slow(src, dst):
        inside.set()
        assert release.wait(30)
        original(src, dst)

    catalog._backup = slow
    outcomes = []

    def run():
        try:
            outcomes.append(('ok', catalog.copy_graph(first['graph_id'], 'Race')['graph_id']))
        except ValueError as exc:
            outcomes.append(('err', str(exc)))

    a = threading.Thread(target=run)
    a.start()
    try:
        assert inside.wait(30)
        b = threading.Thread(target=run)
        b.start();b.join(10)
        assert not b.is_alive()
    finally:
        release.set();a.join(30)
    kinds = sorted(k for k, _ in outcomes)
    assert kinds == ['err', 'ok'] and any('GRAPH_BUSY' in v for k, v in outcomes if k == 'err')
    new_id = next(v for k, v in outcomes if k == 'ok')
    assert Path(catalog.graph(new_id)['code_database']).is_file()
    assert router.query(new_id, 'search_entities', request(first))['result']['data']['hits']


def test_copy_busy_refusal_clears_in_progress_marker(hub, tmp_path):
    catalog, router, first = hub
    inside = threading.Event()
    release = threading.Event()
    original = catalog._backup

    def slow(src, dst):
        inside.set()
        assert release.wait(30)
        original(src, dst)

    catalog._backup = slow
    worker = threading.Thread(target=lambda: catalog.copy_graph(first['graph_id'], 'Again'))
    worker.start()
    try:
        assert inside.wait(30)
        with pytest.raises(ValueError, match='GRAPH_BUSY'):
            catalog.copy_graph(first['graph_id'], 'Again')
    finally:
        release.set();worker.join(30)
    assert catalog._copying == set()
    catalog._backup = original
    again = catalog.copy_graph(first['graph_id'], 'Again')
    assert catalog.graph(again['graph_id'])
    # A different label after a refusal also works.
    assert catalog.copy_graph(first['graph_id'], 'Other')['graph_id'] != again['graph_id']


def test_failing_second_copy_keeps_published_directory(hub, tmp_path):
    catalog, router, first = hub
    original = catalog._backup
    published = {}

    def backup_then_publish(src, dst):
        original(src, dst)
        # Simulate the race winner publishing this id while we were mid-backup.
        path = dst.execute('PRAGMA database_list').fetchone()[2]
        new_id = Path(path).parent.name
        with catalog.lock, catalog.connection:
            catalog.connection.execute('INSERT INTO graphs VALUES(?,?,?,?,?,NULL,?,?,?)', (
                new_id, 'copy:' + new_id, 'r', 'Keep', path, first['ingestion']['snapshot_id'], '{}', 'now'))
        published['id'] = new_id;published['path'] = Path(path)
        raise RuntimeError('post-publish failure')

    catalog._backup = backup_then_publish
    with pytest.raises(RuntimeError):
        catalog.copy_graph(first['graph_id'], 'Keep')
    assert published['path'].is_file()
    assert catalog.graph(published['id'])
    assert catalog._copying == set()
