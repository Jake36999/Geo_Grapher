"""Physical merge and shared rendering must not silently blend project identity."""
import copy
import json
from pathlib import Path
import sqlite3

import pytest
from starlette.testclient import TestClient

from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.graph_merge import plan_merge, execute_merge
from geographer.graph_composition import compose_frame
from geographer.graph_server import create_graph_http
from geographer.source import Repository
from geographer.store import SnapshotStore


@pytest.fixture
def projects(tmp_path):
    catalog=GraphCatalog(tmp_path/'catalog'/'catalog.sqlite')
    ids=[]
    for name in ('Alpha','Beta'):
        root=tmp_path/name;root.mkdir()
        (root/'app.py').write_text('def helper():\n    """Local helper."""\n    return 1\n\ndef entry():\n    return helper()\n',encoding='utf-8')
        (root/'README.md').write_text(name+' project references app.entry.',encoding='utf-8')
        ids.append(catalog.import_project(root,Repository.from_directory(root,name),label=name)['graph_id'])
    router=GraphRouter(catalog)
    yield catalog,router,ids
    router.close();catalog.close()


def paper(catalog,gid,path,definition):
    from pipeline.stage3_build_db import DDL,load_nodes_file
    from pipeline.artifacts import write_json
    from pipeline.maintain import annotate
    with sqlite3.connect(path) as conn:
        conn.row_factory=sqlite3.Row;conn.executescript(DDL)
        artifact=path.with_suffix('.json')
        write_json(artifact,dict(file_path='same.pdf',metadata=dict(title='A sufficiently long shared research title',doi='10.1/same',authors=['A. Author']),
            sections=[dict(heading='Methods',position=0,text=definition,claims=[dict(text=definition,claim_type='finding')],concepts=[dict(name='field',definition=definition,concept_type='term')])]))
        load_nodes_file(artifact,conn);conn.commit()
        revision=conn.execute("SELECT value FROM corpus_metadata WHERE key='revision'").fetchone()[0]
        annotate(conn,kind='note',text='Archived origin',source_refs=[dict(kind='claim',id=1)],expected_revision=revision,author='test')
    catalog.attach_papers(gid,path)


def test_merge_new_destination_preserves_sources_and_rebuilds_analysis(projects):
    catalog,router,ids=projects
    originals={gid:router.service(gid).store.export(catalog.graph(gid)['snapshot_id']) for gid in ids}
    plan=plan_merge(catalog,ids,'Combined modules')
    assert len(catalog.graphs())==2
    result=execute_merge(catalog,ids,'Combined modules',plan['plan_id'])
    assert execute_merge(catalog,ids,'Combined modules',plan['plan_id'])==result
    assert len(catalog.graphs())==3
    with pytest.raises(sqlite3.IntegrityError,match='immutable'):
        with catalog.connection:catalog.connection.execute("UPDATE merge_receipts SET receipt_json='{}'")
    for gid in ids:assert router.service(gid).store.export(catalog.graph(gid)['snapshot_id'])==originals[gid]
    merged=router.service(result['graph_id']);sid=result['snapshot_id'];g=merged.store.graph(sid)
    assert len([e for e in g.entities.values() if e.kind=='workspace'])==1
    assert {e.repo_id for e in g.entities.values() if e.kind=='repository'}==set(ids)
    assert not merged.store.validate(sid)
    assert any(a['algorithm_version']=='directed-wl3-v1' for a in g.analyses.values())
    assert any(a['algorithm_version']=='helper_tree_balls_v1' for a in g.analyses.values())
    assert any(a['algorithm_version']=='declaration-v1' for a in g.analyses.values())
    assert all(g.entities[r.source_id].repo_id==g.entities[r.target_id].repo_id for r in g.relationships.values())
    assert merged.store.connection.execute('SELECT count(*) FROM quotient_projections WHERE snapshot_id=?',(sid,)).fetchone()[0]>0
    assert catalog.plan_root(Path(catalog.graph(ids[0])['root_path']))['collisions']==[]


@pytest.mark.parametrize('invalid',[None,'not-a-plan'])
def test_unreviewed_merge_never_publishes(projects,invalid):
    catalog,_,ids=projects
    with pytest.raises(ValueError,match='reviewed'):execute_merge(catalog,ids,'Merged',invalid)
    assert len(catalog.graphs())==2
    assert not list(catalog.path.parent.glob('graphs/*/papers-*'))


def test_stale_merge_plan_and_duplicate_namespaces_rejected(projects):
    catalog,router,ids=projects;plan=plan_merge(catalog,ids,'Merged')
    source=catalog.graph(ids[0]);root=Path(source['root_path'])
    (root/'README.md').write_text('Changed source content.',encoding='utf-8')
    catalog.import_project(root,Repository.from_directory(root,'Alpha'),label='Alpha')
    with pytest.raises(ValueError,match='changed'):execute_merge(catalog,ids,'Merged',plan['plan_id'])
    plan=plan_merge(catalog,ids,'Merged');merged=execute_merge(catalog,ids,'Merged',plan['plan_id'])
    with pytest.raises(ValueError,match='overlapping'):plan_merge(catalog,[merged['graph_id'],ids[0]],'Double counted')


def test_paper_merge_preserves_homonyms_documents_provenance_and_archives(projects,tmp_path):
    from pipeline.corpus import refresh
    catalog,router,ids=projects
    for gid,definition in zip(ids,['Electromagnetic field measurement.','Anthropological field study.']):paper(catalog,gid,tmp_path/(gid+'.sqlite'),definition)
    before=[router.query(gid,'paper_get_concept',dict(name='field')) for gid in ids]
    plan=plan_merge(catalog,ids,'Research modules');result=execute_merge(catalog,ids,'Research modules',plan['plan_id'])
    target=catalog.graph(result['graph_id'])
    concepts=router.query(target['graph_id'],'paper_get_concept',dict(name='field'))['result']['matches']
    assert {c['definition'] for c in concepts}=={'Electromagnetic field measurement.','Anthropological field study.'}
    assert {c['origins'][0]['source_graph'] for c in concepts}==set(ids)
    with sqlite3.connect(target['paper_database']) as conn:
        conn.row_factory=sqlite3.Row
        assert conn.execute('SELECT count(*) FROM read_documents').fetchone()[0]==2
        assert conn.execute('SELECT count(*) FROM read_concepts').fetchone()[0]==2
        assert conn.execute('SELECT count(*) FROM annotations').fetchone()[0]==2
        origins=list(conn.execute('SELECT * FROM document_origins'))
        assert {r['source_graph'] for r in origins}==set(ids)
        for raw in conn.execute('SELECT source_refs_json FROM annotations'):
            ref=json.loads(raw[0])[0]
            assert ref['source_record']['id']==1
            assert ref['origin']['id']==1
            assert ref['source_document_id'] in {o['doc_id'] for o in origins}
        assert refresh(conn)['refresh_mode']=='unchanged'
        for origin in origins:
            data=router.query(target['graph_id'],'paper_get_document',dict(title='doc:'+str(origin['doc_id'])))['result']
            assert data['provenance']['sources'][0]['source_path']=='same.pdf'
            assert data['provenance']['sources'][0]['origin']['graph_id']==origin['source_graph']
            annotations=router.query(target['graph_id'],'paper_get_annotations',dict(title='doc:'+str(origin['doc_id']),annotation_id=data['annotations'][0]['id'],source_index=0))['result']['annotations']
            assert annotations[0]['origin']['source_graph']==origin['source_graph']
            assert annotations[0]['archived_source']['origin']['graph_id']==origin['source_graph']
    assert [router.query(gid,'paper_get_concept',dict(name='field')) for gid in ids]==before


def test_paper_edit_invalidates_plan_including_annotation_edits(projects,tmp_path):
    from pipeline.maintain import annotate
    catalog,_,ids=projects;path=tmp_path/'papers.sqlite';paper(catalog,ids[0],path,'Physics field measurement.')
    plan=plan_merge(catalog,ids,'Merged')
    with sqlite3.connect(path) as conn:
        conn.row_factory=sqlite3.Row
        revision=conn.execute("SELECT value FROM corpus_metadata WHERE key='revision'").fetchone()[0]
        annotate(conn,kind='note',text='New annotation',source_refs=[dict(kind='claim',id=1)],expected_revision=revision,author='test')
    with pytest.raises(ValueError,match='changed'):execute_merge(catalog,ids,'Merged',plan['plan_id'])


def test_composed_details_remain_disjoint_and_focus_is_local(projects):
    catalog,router,ids=projects
    before=compose_frame(router,[dict(graph_id=gid,context_radius=2) for gid in ids])
    assert before['composition']=='display_only'
    assert all(len(f['frame']['spheres'])>2 for f in before['frames'])
    assert sum(len(f['frame']['curves']) for f in before['frames'])>0
    first,second=before['frames']
    assert first['world_center'][0]+first['root_radius']<second['world_center'][0]-second['root_radius']
    for item in before['frames']:
        frame=item['frame'];nodes={n['id'] for n in frame['nodes']}
        assert all(r['source'] in nodes and r['target'] in nodes for r in frame['relationships'])
    focus=next(n['entity_id'] for n in first['frame']['nodes'] if n['kind']=='function')
    after=compose_frame(router,[dict(graph_id=first['graph_id'],focus_id=focus,context_radius=2),dict(graph_id=second['graph_id'],context_radius=2)])
    assert after['frames'][1]==second
    assert after['frames'][0]['focus_id']==focus
    assert len(catalog.graphs())==2


def test_shared_frame_partial_failure_and_http_merge_review(projects):
    catalog,router,ids=projects
    with TestClient(create_graph_http(router),base_url='http://127.0.0.1:8774') as client:
        result=client.post('/api/graphs/frame',json=dict(graphs=[dict(graph_id=ids[0],focus_id='not-a-node'),dict(graph_id=ids[1])]))
        assert result.status_code==200
        frames=result.json()['frames']
        assert sum('error' in f for f in frames)==1
        assert sum('frame' in f for f in frames)==1
        assert client.post('/api/graphs/frame',json=dict(graphs=[dict(graph_id='unknown')])).status_code==400
        assert client.post('/api/graphs/frame',json=dict(graphs=[dict(graph_id=ids[0])]*2)).status_code==400
        plan=client.post('/api/graphs/merge/plan',json=dict(graph_ids=ids,label='UI merge')).json()
        assert client.post('/api/graphs/merge/execute',json=dict(graph_ids=ids,label='UI merge',plan_id='stale')).status_code==409
        result=client.post('/api/graphs/merge/execute',json=dict(graph_ids=ids,label='UI merge',plan_id=plan['plan_id']))
        assert result.status_code==200,result.text
        assert len(client.get('/api/graphs').json()['graphs'])==3


def test_new_merge_generation_refreshes_router_and_mounted_workspace(projects):
    catalog,router,ids=projects
    plan=plan_merge(catalog,ids,'Evolving');first=execute_merge(catalog,ids,'Evolving',plan['plan_id'])
    original=catalog.graph(first['graph_id']);old_key,old_service=router.acquire(first['graph_id'])
    with TestClient(create_graph_http(router),base_url='http://127.0.0.1:8774') as client:
        url='/graphs/'+first['graph_id']+'/api/v1/bootstrap'
        assert client.get(url).json()['snapshots'][0]['snapshot_id']==first['snapshot_id']
        source=catalog.graph(ids[0]);root=Path(source['root_path'])
        (root/'README.md').write_text('Updated generation.',encoding='utf-8')
        catalog.import_project(root,Repository.from_directory(root,'Alpha'),label='Alpha')
        plan=plan_merge(catalog,ids,'Evolving');second=execute_merge(catalog,ids,'Evolving',plan['plan_id'])
        assert first['graph_id']==second['graph_id'] and first['snapshot_id']!=second['snapshot_id']
        assert client.get(url).json()['snapshots'][0]['snapshot_id']==second['snapshot_id']
        assert router.service(second['graph_id']) is not old_service
        assert Path(original['code_database']).is_file()
        # A leased (in-flight) previous generation stays usable until released.
        assert old_service.store.graph(first['snapshot_id'])
        router.release(old_key)
        assert old_key not in router.services and [k for k in router.services if k[0]==first['graph_id']]==[(first['graph_id'],catalog.graph(first['graph_id'])['code_database'])]


def test_source_change_during_build_keeps_previous_destination_live(projects,monkeypatch):
    catalog,router,ids=projects
    plan=plan_merge(catalog,ids,'Stable');first=execute_merge(catalog,ids,'Stable',plan['plan_id'])
    previous=catalog.graph(first['graph_id']);store=router.service(first['graph_id']).store;archive=store.export(first['snapshot_id'])
    source=catalog.graph(ids[0]);root=Path(source['root_path'])
    (root/'README.md').write_text('First change.',encoding='utf-8')
    catalog.import_project(root,Repository.from_directory(root,'Alpha'),label='Alpha')
    plan=plan_merge(catalog,ids,'Stable');original_merge=SnapshotStore.merge
    def changing(self,sources,**kwargs):
        result=original_merge(self,sources,**kwargs)
        (root/'README.md').write_text('Changed during build.',encoding='utf-8')
        catalog.import_project(root,Repository.from_directory(root,'Alpha'),label='Alpha')
        return result
    monkeypatch.setattr(SnapshotStore,'merge',changing)
    with pytest.raises(ValueError,match='Source changed'):execute_merge(catalog,ids,'Stable',plan['plan_id'])
    assert catalog.graph(first['graph_id'])==previous
    assert store.export(first['snapshot_id'])==archive
    assert store.connection.execute('SELECT count(*) FROM snapshot_sets').fetchone()[0]==1


def test_corrupt_graph_does_not_remove_healthy_composed_frame(projects,tmp_path):
    catalog,router,ids=projects;path=tmp_path/'broken.sqlite';path.write_bytes(b'not sqlite')
    with catalog.connection:catalog.connection.execute('UPDATE graphs SET code_database=? WHERE graph_id=?',(str(path),ids[0]))
    response=compose_frame(router,[dict(graph_id=gid) for gid in ids])
    assert sum('frame' in f for f in response['frames'])==1
    assert sum('error' in f for f in response['frames'])==1


def test_cli_plan_and_explicit_execution(projects):
    import subprocess,sys
    catalog,_,ids=projects
    common=['--catalog',str(catalog.path),'--label','CLI union']
    for gid in ids:common+=['--graph-id',gid]
    def cli(command,extra=[]):
        result=subprocess.run([sys.executable,'-m','geographer',command,*common,*extra],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
        return json.loads(result.stdout)
    plan=cli('plan-graph-merge')
    assert len(catalog.graphs())==2
    receipt=cli('merge-graphs',['--plan-id',plan['plan_id']])
    assert receipt['graph_id']==plan['destination_graph_id']
    assert len(catalog.graphs())==3


def test_merge_identity_collision_cannot_replace_project_registration(projects,monkeypatch):
    import geographer.graph_merge as merging
    catalog,_,ids=projects;original=catalog.graph(ids[0])
    monkeypatch.setattr(merging,'digest',lambda *args:ids[0][2:]+'0'*40)
    with pytest.raises(ValueError,match='identity collision'):plan_merge(catalog,ids,'Collision')
    assert catalog.graph(ids[0])==original


def test_six_graph_frames_occupy_centre_and_five_separate_hex_slots(projects,tmp_path):
    import math
    catalog,router,ids=projects
    for name in ('Gamma','Delta','Epsilon','Zeta'):
        root=tmp_path/name;root.mkdir();(root/'app.py').write_text('def entry(): return 1\n',encoding='utf-8')
        ids.append(catalog.import_project(root,Repository.from_directory(root,name),label=name)['graph_id'])
    result=compose_frame(router,[dict(graph_id=gid) for gid in ids])
    assert [f['graph_id'] for f in result['frames']]==ids
    assert result['frames'][0]['world_center']==[0.,0.,0.]
    assert all('error' not in f for f in result['frames'])
    for i,a in enumerate(result['frames']):
        for b in result['frames'][i+1:]:
            assert math.dist(a['world_center'],b['world_center'])>a['root_radius']+b['root_radius']
