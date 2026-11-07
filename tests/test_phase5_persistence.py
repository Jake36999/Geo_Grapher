"""Bulk publication preserves witness identity and rolls back partial views."""
import sqlite3
import pytest
from geographer.analysis import materialize_view, project, DEFAULT_FILTER

def test_bulk_projection_rows_and_witnesses_match_reference(extract):
    g,store,report=extract({'a.py':'def f(): pass\ndef g():\n f()\n f()\n','b.py':'from a import f\nf()\n'})
    sid=report['snapshot_id'];vid,part=materialize_view(store,sid,g,{'mode':'kind','kind':'file'})
    reference=project(g,part,vid,DEFAULT_FILTER)
    actual=[dict(r) for r in store.connection.execute('SELECT * FROM quotient_projections WHERE view_id=? ORDER BY projection_id',(vid,))]
    assert {r['projection_id']:r for r in actual}=={row['projection_id']:dict(snapshot_id=sid,view_id=vid,**{k:v for k,v in row.items() if k!='witnesses'}) for row in reference}
    actual_witnesses={(r[0],r[1]) for r in store.connection.execute('SELECT projection_id,relationship_id FROM quotient_witness_map WHERE view_id=?',(vid,))}
    assert actual_witnesses=={(row['projection_id'],rid) for row in reference for rid in row['witnesses']}
    assert not store.validate(sid)

def test_bulk_failure_leaves_no_partial_view_or_members(extract,monkeypatch):
    g,store,report=extract({'a.py':'def f(): pass\nf()\n'})
    original=store.insert_many
    def fail(table,rows):
        original(table,rows)
        if table=='partition_members':raise RuntimeError('injected interruption')
    monkeypatch.setattr(store,'insert_many',fail)
    with pytest.raises(RuntimeError):materialize_view(store,report['snapshot_id'],g,{'mode':'atomic'})
    for table in ('analysis_views','view_representatives','partition_members','quotient_projections','quotient_witness_map','level_scc_condensations'):
        assert store.connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0]==0
    assert store.connection.execute('PRAGMA foreign_key_check').fetchone() is None

def test_mixed_partition_reuses_identical_ingestion_rollup(extract):
    from geographer.analysis import partition
    from geographer.service import QueryService
    g,store,report=extract({'a.py':'def f(): pass\nf()\n','b.py':'def g(): pass\ng()\n'})
    sid=report['snapshot_id'];file_view,_=materialize_view(store,sid,g,{'mode':'kind','kind':'file'})
    revealed=[eid for eid,e in g.entities.items() if e.kind in {'workspace','repository','file'}]
    mixed=partition(g,sid,{'mode':'mixed','revealed_ids':revealed})
    svc=QueryService(store);ctx=svc._context(sid)
    assert svc._persist_partition(sid,ctx,mixed,DEFAULT_FILTER,'viewport-partition-v1')==file_view
    assert store.connection.execute('SELECT count(*) FROM analysis_views').fetchone()[0]==1
