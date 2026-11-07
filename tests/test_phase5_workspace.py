"""P5.3 view isolation, model lifecycle, review provenance and shared content."""
import copy,json
import pytest
from starlette.testclient import TestClient
from geographer.analysis import DEFAULT_FILTER,partition
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.service import QueryService
from geographer.server import create_http_app
from geographer.tokens import TokenCounter
from geographer.workspace import append_annotation,overlay,load_rules,triage
from test_stage4_geometry import viewport_request

RULES='''version: "1.0"
world_policy: open
components:
  - id: interface
    selectors: [{repo_id: r, path_glob: "ui.py"}]
  - id: core
    selectors: [{repo_id: r, path_glob: "core.py"}]
rules:
  - {id: blocked, type: forbid, source: interface, target: core, rationale: "Use the boundary API"}
'''

@pytest.fixture
def workspace():
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'ui.py':b'from core import target\ndef run(x): return target(x)\ndef unknown(x): return x.missing()\n',
            'core.py':b'def target(x):\n """Return the incoming value."""\n return x\nclass Store:\n def open(self): return target(1)\n',
            'docs.md':b'# API\n\nThe run function calls target.\n'})],stage=3)['snapshot_id']
        svc=QueryService(store,secret=b'w'*32);model=load_rules(svc,sid,RULES)['model_digest']
        ctx=svc._context(sid);focus=next(e.entity_id for e in ctx['g'].entities.values() if e.qualified_name=='ui.py.run')
        yield svc,sid,focus,model

@pytest.mark.parametrize('grouping',[{'mode':'kind','kind':kind} for kind in ('repository','directory','file','class')]+[{'mode':'atomic'},{'mode':'conceptual'}])
def test_all_display_groupings_keep_full_partition_witnesses_and_containment(workspace,grouping):
    svc,sid,focus,model=workspace;q=viewport_request(sid,focus)
    grouping={**grouping,**({'model_digest':model} if grouping['mode']=='conceptual' else {})}
    q.update(schema_version='1.1',identity_mode='canonical_map',grouping=grouping)
    before=[tuple(r) for r in svc.store.connection.execute('SELECT entity_id,parent_id,depth FROM entities WHERE snapshot_id=?',(sid,))]
    result=svc.query('viewport_frame',q);assert 'data' in result,result
    svc.wire11.validate('viewport_frame','response',result);assert TokenCounter().count(result)<=32768
    data=result['data'];nodes={n['id'] for n in data['nodes']};spheres={s['node_id']:s for s in data['spheres']}
    assert all(r['source'] in nodes and r['target'] in nodes for r in data['relationships'])
    assert all(c['relationship_id'] in {r['id'] for r in data['relationships']} for c in data['curves'])
    for node in data['nodes']:
        if node['parent_id'] in spheres and node['id'] in spheres:
            import math
            child,parent=spheres[node['id']],spheres[node['parent_id']]
            assert math.dist(child['center'],parent['center'])+child['radius']<=parent['radius']+1e-4
    assert before==[tuple(r) for r in svc.store.connection.execute('SELECT entity_id,parent_id,depth FROM entities WHERE snapshot_id=?',(sid,))]
    atoms=[r[0] for r in svc.store.connection.execute('SELECT atom_id FROM partition_members WHERE snapshot_id=? AND view_id=?',(sid,data['view_id']))]
    assert len(atoms)==len(set(atoms))==sum(len(v) for v in partition(svc._context(sid)['g'],sid,{'mode':'atomic'},DEFAULT_FILTER).groups.values())
    if grouping['mode']=='conceptual':assert {'interface','core','Unmapped'}<={n['qualified_name'] for n in data['nodes']}
    assert not svc.store.validate(sid)

def test_live_rules_invalid_reload_preserves_prior_and_recovers_after_restart(workspace):
    svc,sid,focus,model=workspace
    with TestClient(create_http_app(svc),base_url='http://127.0.0.1:8765') as c:
        before=c.get('/api/v1/bootstrap').json()['models']
        invalid=c.post('/api/workspace/rules',json=dict(snapshot_id=sid,text=RULES.replace('path_glob: "core.py"','path_glob: "ui.py"'),activate=True))
        assert invalid.status_code==400
        assert c.get('/api/v1/bootstrap').json()['models']==before
        changed=c.post('/api/workspace/rules',json=dict(snapshot_id=sid,text=RULES.replace('type: forbid','type: allow'),activate=True))
        assert changed.status_code==200 and changed.json()['model_digest']!=model
        assert c.post('/api/workspace/rules',json=dict(snapshot_id=sid,path='C:/arbitrary.yaml')).status_code==400
    reopened=QueryService(svc.store)
    assert {model,changed.json()['model_digest']}<=reopened.rules.keys()

def test_overlay_decisions_replay_without_promoting_facts_and_reject_stale_snapshot(workspace):
    svc,sid,focus,model=workspace;g=svc.store.graph(sid)
    before={r.relationship_id:r.resolution_status for r in g.relationships.values()}
    first=append_annotation(svc,sid,focus,'Hypothesis, not a parser conclusion')
    second=append_annotation(svc,sid,focus,'Reviewed as a useful annotation','accepted',first['overlay_id'])
    assert overlay(QueryService(svc.store),sid,first['overlay_id'])==first
    assert second['previous_overlay_id']==first['overlay_id'] and len(second['records'])==2
    assert before=={r.relationship_id:r.resolution_status for r in svc.store.graph(sid).relationships.values()}
    other=ingest(svc.store,[Repository('r','other',{'a.py':b'pass\n'})],stage=3)['snapshot_id']
    with pytest.raises(ValueError):overlay(svc,other,second['overlay_id'])
    q=dict(schema_version='1.1',request_id='investigation',snapshot_id=sid,budget=dict(limit_tokens=32768,tokenizer='o200k_base',allow_byte_fallback=False),
        entity_id=focus,content_kind='source',context_mode='source-context-v1',context_radius=1,start_line=None,end_line=None,cursor=None,include_investigation=True)
    plain=svc.query('get_entity_content',q);review=svc.query('get_entity_content',{**q,'overlay_id':second['overlay_id']})
    assert 'data' in plain and 'data' in review,review
    assert plain['data']['source_context']==review['data']['source_context']
    details=review['data']['investigation'];assert details['statement_steps'] and details['documentary_sections']
    assert details['overlay']['records'][-1]['claim_kind']=='reviewed_annotation'
    assert len(details['call_relationship_ids'])==1
    assert any('not an execution sequence' in gap for gap in details['limitations'])
    assert {f for section in details['documentary_sections'] for f in section['fragment_ids']}<={n['id'] for n in review['data']['nodes']}

def test_triage_is_occurrence_grouped_deterministic_and_scoped(workspace):
    svc,sid,focus,model=workspace;svc.active_snapshot=sid
    result=triage(svc,sid,DEFAULT_FILTER,focus,model_digest=model,limit=1)
    assert result==triage(svc,sid,DEFAULT_FILTER,focus,model_digest=model,limit=1)
    assert result['items'] and result['items'][0]['target_degree'] is None
    assert result['items'][0]['reason_codes']
    unmapped=triage(svc,sid,DEFAULT_FILTER,focus,model_digest=model,queue='unmapped')
    assert all('UNMAPPED_COMPONENT' in r['reason_codes'] for r in unmapped['items'])
    with TestClient(create_http_app(svc),base_url='http://127.0.0.1:8765') as c:
        assert c.post('/api/workspace/triage',json=dict(snapshot_id=sid,filter={'invalid':True})).status_code==400

def test_shared_actor_review_queue_matches_workspace_and_counts_full_envelope(workspace):
    svc,sid,focus,model=workspace;svc.active_snapshot=sid
    expected=triage(svc,sid,DEFAULT_FILTER,focus,model_digest=model,limit=1)
    q=dict(schema_version='1.1',request_id='triage-parity',snapshot_id=sid,budget=dict(limit_tokens=32768,tokenizer='o200k_base',allow_byte_fallback=False),
        focus_id=focus,grouping={'mode':'atomic'},context_radius=1,filter=copy.deepcopy(DEFAULT_FILTER),pins=[],qi={'enabled':False,'max_diameter':2},cursor=None,
        review_queue='unknown_locality',review_model_digest=model,review_limit=1)
    response=svc.query('get_architecture_context',q);assert 'data' in response,response
    actual=response['data']['review_queue'];assert actual['ordering']==expected['ordering']
    assert [r['occurrence_id'] for r in actual['items']]==[r['occurrence_id'] for r in expected['items']]
    definitions={n['id'] for n in response['data']['nodes']}
    assert all(r['entity_id'] in definitions and set(r['alternatives'])<=definitions for r in actual['items'])
    assert TokenCounter().count(response)<=32768
    tiny=svc.query('get_architecture_context',{**q,'budget':{**q['budget'],'limit_tokens':256}})
    assert tiny['error']['code']=='BUDGET_TOO_SMALL'

def test_warning_encodings_and_witness_projection_keep_original_direction(workspace):
    svc,sid,focus,model=workspace;q=viewport_request(sid,focus);q['context_radius']=2
    data=svc.query('viewport_frame',q)['data'];view=data['view_id']
    rid=next(r.relationship_id for r in svc._context(sid)['g'].relationships.values() if r.source_subject_id==focus and r.subtype=='calls')
    with TestClient(create_http_app(svc),base_url='http://127.0.0.1:8765') as c:
        path=c.post('/api/workspace/path',json=dict(snapshot_id=sid,view_id=view,relationship_ids=[rid])).json()['steps'][0]
        assert path['source']==focus and path['projections']
        semantics=c.post('/api/workspace/semantics',json=dict(snapshot_id=sid,view_id=view,model_digest=model,projection_ids=[r['id'] for r in data['relationships']])).json()
        assert semantics['severity']=='warning' and semantics['warning_projection_ids']

def test_grouped_scene_budget_keeps_connected_code_before_unindexed_placeholders():
    with SnapshotStore() as store:
        noise='\n'.join(f'import missing_{i}' for i in range(80))+'\n'
        sid=ingest(store,[Repository('r','rev',{'a.py':b'from b import work\ndef run(): return work()\n','b.py':b'def work(): return 1\n','noise.py':noise.encode(),'tests/test_b.py':b'from b import work\ndef test_work(): return work()\n'})],stage=3)['snapshot_id']
        svc=QueryService(store);g=svc._context(sid)['g'];focus=next(e.entity_id for e in g.entities.values() if e.kind=='repository')
        q={**viewport_request(sid,focus),'schema_version':'1.1','identity_mode':'canonical_map','grouping':{'mode':'kind','kind':'file'},'node_budget':12}
        result=svc.query('viewport_frame',q);assert 'data' in result,result
        assert result['data']['curves']
        assert {'a.py','b.py'}<={n['qualified_name'] for n in result['data']['nodes']}
        changed=svc.query('viewport_frame',{**q,'filter':{**q['filter'],'include_tests':True}})
        def centres(r):return {r['data']['ids'][s['node_id']]:s['center'] for s in r['data']['spheres']}
        a,b=centres(result),centres(changed)
        assert all(a[k]==b[k] for k in a.keys()&b.keys())
