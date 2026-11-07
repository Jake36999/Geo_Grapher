"""Unrelated project ownership, import namespaces, retrieval and root geometry."""
import copy,json
import pytest
from geographer.source import Repository
from geographer.pipeline import ingest
from geographer.store import SnapshotStore
from geographer.service import QueryService
from geographer.geometry import norm,sub,EPS
from geographer.project_inputs import load_workspace_manifest,inspect_project
from test_stage3_service import base
from test_stage4_geometry import viewport_request


@pytest.fixture
def projects():
    store=SnapshotStore()
    a=Repository('alpha','r',{'utils.py':b'def run(): return 1\n','app.py':b'from utils import run\ndef start(): return run()\n','README.md':b'# Research\nrun refers to the application only.\n'})
    b=Repository('beta','r',{'utils.py':b'def run(): return 1\n','foreign.py':b'def unrelated(): return 2\n','README.md':b'# Research\nrun is a hypothesis in this unrelated project.\n'})
    report=ingest(store,[a,b],stage=3);svc=QueryService(store)
    yield svc,report['snapshot_id']
    store.close()


def test_isolated_imports_and_documentary_mentions(projects):
    svc,sid=projects;g=svc._context(sid)['g']
    calls=[r for r in g.relationships.values() if r.subtype=='calls']
    assert len(calls)==1 and calls[0].resolution_status=='exact'
    assert all(g.entities[r.source_subject_id].repo_id==g.entities[r.target_subject_id].repo_id for r in g.relationships.values())
    assert all(g.entities[i['fragment_id']].repo_id==g.entities[i['entity_id']].repo_id for i in g.incidences)


def test_external_import_never_binds_to_unrelated_project():
    with SnapshotStore() as store:
        a=Repository('a','r',{'app.py':b'from foreign import unrelated\nunrelated()\n'})
        b=Repository('b','r',{'foreign.py':b'def unrelated(): return 2\n'})
        sid=ingest(store,[a,b])['snapshot_id'];g=store.graph(sid)
        assert all(g.entities[r.target_subject_id].repo_id=='a' for r in g.relationships.values())
        assert all(r.resolution_status=='unresolved' for r in g.relationships.values())


def test_linked_namespace_is_explicit_and_keeps_separate_roots():
    with SnapshotStore() as store:
        a=Repository('a','r',{'app.py':b'from foreign import target\ntarget()\n'},resolution_group='one-application')
        b=Repository('b','r',{'foreign.py':b'def target(): return 2\n'},resolution_group='one-application')
        sid=ingest(store,[a,b])['snapshot_id'];g=store.graph(sid)
        assert any(g.entities[r.source_subject_id].repo_id!=g.entities[r.target_subject_id].repo_id and r.resolution_status=='exact' for r in g.relationships.values())
        roots=[e for e in g.entities.values() if e.kind=='repository']
        assert len({e.parent_id for e in roots})==1 and not {e.entity_id for e in roots}&{e.parent_id for e in roots}


@pytest.mark.parametrize('version',['1.0','1.1'])
def test_search_requires_scope_and_all_projects_is_deliberate(projects,version):
    svc,sid=projects;q={**base(sid),'schema_version':version,'query':'run','mode':'lexical','repo_ids':[],'kinds':['function'],'limit':20,'cursor':None}
    result=svc.query('search_entities',q);assert result['error']['code']=='INVALID_REQUEST' and 'repo_ids' in result['error']['message']
    for ids in (['alpha'],['beta'],['alpha','beta']):
        result=svc.query('search_entities',{**q,'repo_ids':ids});assert 'error' not in result,result
        assert {n['repo_id'] for n in result['data']['nodes']}<=set(ids)
    assert 'error' in svc.query('search_entities',{**q,'repo_ids':['not-indexed']})


def test_similarity_never_compares_other_project_by_default(projects):
    svc,sid=projects;g=svc._context(sid)['g'];focus=next(e.entity_id for e in g.entities.values() if e.repo_id=='alpha' and e.qualified_name=='utils.py.run')
    q={**base(sid),'entity_id':focus,'mode':'exact_normalized_ast','repo_ids':[],'limit':20,'cursor':None}
    assert svc.query('find_similar_code',q)['error']['code']=='INVALID_REQUEST'
    same=svc.query('find_similar_code',{**q,'repo_ids':['alpha']});assert same['data']['matches']==[]
    compared=svc.query('find_similar_code',{**q,'repo_ids':['beta']});assert len(compared['data']['matches'])==1


def test_roots_are_disjoint_sibling_spheres_when_focus_is_nested(projects):
    svc,sid=projects;ctx=svc._context(sid);g=ctx['g'];roots=[e for e in g.entities.values() if e.kind=='repository']
    focus=next(e.entity_id for e in g.entities.values() if e.repo_id=='alpha' and e.kind=='function')
    result=svc.query('viewport_frame',viewport_request(sid,focus));assert 'error' not in result,result
    spheres={s['node_id']:s for s in result['data']['spheres']}
    a,b=[spheres[e.entity_id] for e in roots]
    assert norm(sub(a['center'],b['center']))+EPS>=a['radius']+b['radius']
    assert all(e.parent_id==ctx['tree'].root for e in roots)
    assert not any(n['repo_id']=='beta' and n['kind'] not in {'repository'} for n in result['data']['nodes'])


def test_context_radius_does_not_sweep_in_unrelated_project(projects):
    svc,sid=projects;g=svc._context(sid)['g'];focus=next(e.entity_id for e in g.entities.values() if e.repo_id=='alpha' and e.kind=='repository')
    from geographer.analysis import DEFAULT_FILTER
    q={**base(sid),'focus_id':focus,'grouping':{'mode':'atomic'},'context_radius':2,'filter':copy.deepcopy(DEFAULT_FILTER),'pins':[],'qi':{'enabled':False,'max_diameter':2},'cursor':None}
    result=svc.query('get_architecture_context',q);assert 'error' not in result,result
    assert not any(n['repo_id']=='beta' for n in result['data']['nodes'])


def test_discovery_lists_scopes_without_content(projects):
    svc,sid=projects;result=svc.projects();snapshot=next(r for r in result['snapshots'] if r['snapshot_id']==sid)
    assert {r['repo_id'] for r in snapshot['repositories']}=={'alpha','beta'}
    assert all(r['resolution_group'] is None and r['root_entity_id'] for r in snapshot['repositories'])
    assert 'hypothesis' not in json.dumps(result)


def test_profile_budget_pruning_and_duplicate_roots(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir();(a/'src').mkdir();(a/'src'/'a.py').write_text('pass');(a/'other.py').write_text('raise Exception()');(b/'README.md').write_text('# Different domain')
    data=dict(version=1,repositories=[dict(repo_id='a',path=str(a),source_roots=['src'],include_globs=['src/*']),dict(repo_id='b',path=str(b))])
    path=tmp_path/'manifest.json';path.write_text(json.dumps(data))
    repos=load_workspace_manifest(path);assert list(repos[0].files)==['src/a.py'] and repos[1].repo_id=='b'
    with pytest.raises(ValueError):Repository.from_directory(a,'a',max_files=1)
    data['repositories'][1]['path']=str(a/'src');path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='nonoverlapping'):load_workspace_manifest(path)
    assert not inspect_project(a,max_entries=1)['complete']


def test_duplicate_ids_fail_before_snapshot_publication():
    with SnapshotStore() as store:
        with pytest.raises(ValueError):ingest(store,[Repository('same','r',{}),Repository('same','r2',{})])
        assert store.connection.execute('SELECT count(*) FROM snapshot_sets').fetchone()[0]==0
