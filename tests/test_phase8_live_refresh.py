"""Live publication is a validated new binding, retaining snapshots and using CAS."""
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest


def script():
    path = Path(__file__).resolve().parents[1] / 'scripts/phase8_live_refresh.py'
    spec = importlib.util.spec_from_file_location('live_refresh', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def prepared(tmp_path):
    old = tmp_path / 'old.sqlite'
    new = tmp_path / 'new.sqlite'
    for path, snapshots in [(old, ['old']), (new, ['old', 'new'])]:
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE entities(snapshot_id TEXT, rel_path TEXT)')
            c.executemany('INSERT INTO entities VALUES(?,?)', [(s, 'src/staging.py') for s in snapshots])
    catalog = tmp_path / 'catalog.sqlite'
    with sqlite3.connect(catalog) as c:
        c.execute('CREATE TABLE graphs(graph_id TEXT PRIMARY KEY,snapshot_id TEXT,code_database TEXT,profile_json TEXT)')
        c.execute('INSERT INTO graphs VALUES(?,?,?,?)', ('g', 'old', str(old), '{}'))
    return catalog, {'graph_id': 'g', 'snapshot_id': 'new', 'code_database': str(new),
        'profile_json': '{}', 'expected': {'snapshot_id': 'old', 'code_database': str(old), 'profile_json': '{}'}}


def test_publish_preserves_old_store_and_old_snapshot(prepared):
    catalog, plan = prepared
    script().publish_binding(catalog, plan)
    with sqlite3.connect(catalog) as c:
        assert c.execute('SELECT snapshot_id FROM graphs').fetchone()[0] == 'new'
    with sqlite3.connect(plan['code_database']) as c:
        assert c.execute('SELECT count(*) FROM entities WHERE snapshot_id=?', ('old',)).fetchone()[0] == 1
    assert Path(plan['expected']['code_database']).is_file()


def test_publish_refuses_a_changed_head_without_overwriting(prepared):
    catalog, plan = prepared
    with sqlite3.connect(catalog) as c:
        c.execute("UPDATE graphs SET snapshot_id='other-session'")
    with pytest.raises(ValueError, match='HEAD_CHANGED'):
        script().publish_binding(catalog, plan)
    with sqlite3.connect(catalog) as c:
        assert c.execute('SELECT snapshot_id FROM graphs').fetchone()[0] == 'other-session'


def test_publish_refuses_missing_old_snapshot(prepared):
    catalog, plan = prepared
    with sqlite3.connect(plan['code_database']) as c:
        c.execute("DELETE FROM entities WHERE snapshot_id='old'")
    with pytest.raises(ValueError, match='SNAPSHOT_VALIDATION'):
        script().publish_binding(catalog, plan)
    with sqlite3.connect(catalog) as c:
        assert c.execute('SELECT snapshot_id FROM graphs').fetchone()[0] == 'old'


def test_only_persistent_hub_destinations_are_allowed(tmp_path):
    with pytest.raises(ValueError, match='PERSISTENT_HUB'):
        script().check_destination(tmp_path / 'disposable')
