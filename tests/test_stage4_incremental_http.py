import copy,json
from dataclasses import asdict
from starlette.testclient import TestClient
from geographer.incremental import ParseCache
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.server import create_http_app
from geographer.service import QueryService


def test_incremental_exporter_change_rebinds_unchanged_importer():
    initial={'a.py':b'def helper(): return 1\n','b.py':b'from a import helper\ndef run(): return helper()\n'}
    changed={**initial,'a.py':b'helper = object()\n'}
    with SnapshotStore() as store:
        old=ingest(store,[Repository('r','old',initial)],stage=3)
        updated=ingest(store,[Repository('r','new',changed)],stage=3,previous_snapshot_id=old['snapshot_id'])
        report=updated['incremental'];assert report['changed_files']==[('r','a.py')]
        assert report['reused_normal_forms']==1
        g=store.graph(updated['snapshot_id']);assert all(r.resolution_status!='exact' for r in g.relationships.values() if r.subtype=='calls')
        with SnapshotStore() as cold:
            fresh=ingest(cold,[Repository('r','new',changed)],stage=3)
            clean=cold.graph(fresh['snapshot_id'])
            for name in ('entities','relationships','evidence'):
                assert {k:asdict(v) for k,v in getattr(g,name).items()}=={k:asdict(v) for k,v in getattr(clean,name).items()}
        assert store.validate(updated['snapshot_id'])==[]
        assert store.graph(old['snapshot_id']).relationships # Previous immutable result survives.


def test_parse_cache_content_grammar_and_bounded_retention():
    cache=ParseCache(max_entries=2,max_source_bytes=256)
    a=cache.parse('x=1','a.py');assert cache.parse('x=1','a.py') is a
    assert cache.hits==1
    assert cache.parse('x=2','a.py') is not a
    cache.parse('y=3','b.py');assert len(cache.entries)==2 and cache.bytes<=256


def test_ui_metadata_keyset_and_scoped_computed_diagnostics():
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'a.py':b'def f(): return 1\ndef g(): return f()\n','b.py':b'x=1\n','c.py':b'y=2\n'})],stage=3)['snapshot_id']
        service=QueryService(store);ctx=service._context(sid);root=next(e.entity_id for e in ctx['g'].entities.values() if e.kind=='repository')
        with TestClient(create_http_app(service),base_url="http://127.0.0.1:8765") as client:
            bootstrap=client.get('/api/v1/bootstrap').json();assert bootstrap['snapshots'][0]['snapshot_id']==sid
            seen=[];after=''
            while True:
                r=client.get('/api/v1/hierarchy',params={'snapshot_id':sid,'parent_id':root,'limit':1,'after':after}).json()
                assert not set(seen)&{n['id'] for n in r['nodes']};seen.extend(n['id'] for n in r['nodes']);after=r['next_after']
                if not after:break
            assert len(seen)==3
            eid=next(e.entity_id for e in ctx['g'].entities.values() if e.qualified_name=='a.py.g')
            diagnostics=client.get('/api/v1/diagnostics',params={'snapshot_id':sid,'entity_id':eid}).json()
            assert diagnostics['boundary'][0]['ratio']==1. and diagnostics['ast_body_hash']
            assert client.post('/api/v1/entities',json={'snapshot_id':sid,'ids':[{}]}).status_code==400
            assert client.post('/api/v1/viewport/frame',content='{broken',headers={'content-type':'application/json'}).status_code==400
            assert client.post('/api/v1/viewport/page',content='{broken',headers={'content-type':'application/json'}).status_code==400
            assert client.post('/api/v1/search_entities',content='{}',headers={'content-length':'5000000','content-type':'application/json'}).status_code==413
