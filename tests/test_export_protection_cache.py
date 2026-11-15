"""Stage-three export protection is source-derived and survives process restarts."""
import ast
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.contraction import contract_helpers

def test_stage3_persists_export_scan_and_query_does_not_parse(tmp_path,monkeypatch):
    db=tmp_path/'scan.sqlite'
    with SnapshotStore(db) as store:
        sid=ingest(store,[Repository('r','v1',{'m.py':b'__all__ = ["_public"]\ndef _public(): return 1\ndef _private(): return 2\n'})],stage=3)['snapshot_id']
    with SnapshotStore(db) as store:
        g=store.graph(sid)
        assert any(r['algorithm_version']=='helper-export-protection-v1' for r in g.analyses.values())
        def forbidden(*a,**k):raise AssertionError('A persisted export scan must not reparse source')
        monkeypatch.setattr(ast,'parse',forbidden)
        membership,groups,_=contract_helpers(g,sid)
        public=next(e.entity_id for e in g.entities.values() if e.qualified_name.endswith('._public'))
        assert groups[membership[public]]=={public}

def test_lazy_scan_preserves_dynamic_augmented_and_encoded_exports(tmp_path):
    from geographer.export_protection import export_protection
    with SnapshotStore(tmp_path/'mixed.sqlite') as store:
        sid=ingest(store,[Repository('r','v1',{'m.py':b'# coding: latin-1\n# caf\xe9\n__all__ = dynamic()\n__all__ += ["_later"]\ndef _later(): return 1\n'})],stage=2)['snapshot_id']
        g=store.graph(sid);scan=export_protection(g)
        assert scan=={'exported_names':['_later'],'protected_paths':['m.py']}
        assert export_protection(g) is scan
