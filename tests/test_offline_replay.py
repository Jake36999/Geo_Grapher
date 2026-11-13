"""The free evaluator preserves inputs and reports equivalence ranks honestly."""
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import sys
import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from eval_retrieval_offline import metrics,proposed_rrf,target_rank,read_development
from offline_graphs import ReadOnlyStore
from geographer.store import SnapshotStore


def test_frozen_store_cannot_mutate_or_migrate(tmp_path):
    path=tmp_path/'snapshot.db'
    store=SnapshotStore(path);store.close()
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    frozen=ReadOnlyStore(path)
    try:
        assert frozen.connection.execute('SELECT count(*) FROM snapshot_sets').fetchone()[0]==0
        with pytest.raises(sqlite3.OperationalError):frozen.connection.execute('CREATE TABLE unwanted(x)')
    finally:frozen.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before


def test_rrf_deterministic_and_equivalence_set_scored():
    hit=lambda eid:dict(node_id=eid)
    assert proposed_rrf([[hit('b'),hit('a')],[hit('a'),hit('b')]])==['a','b']
    assert target_rank(['a','b'],{'b','c'})==2
    rows=[dict(rank=2),dict(rank=None)]
    assert metrics(rows)['recall@1']['hits']==0
    assert metrics(rows)['recall@3']==dict(hits=1,total=2,rate=.5)


def test_sealed_v2_name_blocked_before_parsing(tmp_path):
    path=tmp_path/'heldout-v2.json';path.write_text('private',encoding='utf-8')
    with pytest.raises(ValueError,match='forbidden'):read_development(path)
