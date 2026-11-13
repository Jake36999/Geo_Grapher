import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('readiness',Path(__file__).parents[1]/'scripts/eval_readiness.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_missing_failed_and_stale_dry_runs_block_dispatch(tmp_path):
    source=tmp_path/'runtime.py';source.write_text('version=1')
    config={'path':'blind-batch','temperature':0.2}
    with pytest.raises(ValueError,match='mandatory'):r.require(None,config)
    checks={k:True for k in r.REQUIRED}
    with pytest.raises(ValueError):r.ticket(config,{**checks,'scope':False},[source])
    value=r.ticket(config,checks,[source]);r.require(value,config)
    with pytest.raises(ValueError):r.require(value,{'path':'different'})
    source.write_text('version=2')
    with pytest.raises(ValueError,match='changed'):r.require(value,config)


def test_snapshot_drift_blocks_dispatch_even_when_source_files_are_unchanged(tmp_path):
    import sqlite3
    catalog=tmp_path/'catalog.sqlite'
    with sqlite3.connect(catalog) as c:
        c.execute('CREATE TABLE graphs(label TEXT,graph_id TEXT,snapshot_id TEXT,code_database TEXT)')
        c.execute('INSERT INTO graphs VALUES(?,?,?,?)',('local','g','snapshot:old','code.sqlite'))
    scope=r.graph_scope(catalog,['local'])
    config=dict(catalog=str(catalog),graph_scope=scope)
    source=tmp_path/'source.py';source.write_text('unchanged')
    value=r.ticket(config,{k:True for k in r.REQUIRED},[source]);r.require(value,config)
    with sqlite3.connect(catalog) as c:c.execute("UPDATE graphs SET snapshot_id='snapshot:new'")
    with pytest.raises(ValueError,match='snapshot|scope'):r.require(value,config)
