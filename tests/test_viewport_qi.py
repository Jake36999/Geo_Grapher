"""Spatial QI uses the same certified partition and expandable membership as context QI."""
import copy
from conftest import viewport_request
from test_contraction_directed_service import make,HELPERS,DIRECTED

def test_spatial_directed_qi_and_expansion_restore_atomic():
    store,svc,sid,ids=make({**HELPERS,'tests/test_ignored.py':b'from lib import run\ndef test_run(): return run()\n'})
    try:
        root=next(e.entity_id for e in store.graph(sid).entities.values() if e.kind=='repository')
        q=viewport_request(sid,root);q.update(schema_version='1.1',identity_mode='canonical_map',grouping={'mode':'atomic'},layout_version='sphere-affinity-v1')
        original=svc.query('viewport_frame',q);assert 'error' not in original
        enabled=copy.deepcopy(q);enabled['qi']=dict(enabled=True,max_diameter=2,algorithm=DIRECTED)
        result=svc.query('viewport_frame',enabled);assert 'error' not in result,result
        data=result['data'];assert data['qi']['directed_reachability_preserved']
        assert data['qi']['group_count']>1
        groups=[n for n in data['nodes'] if n['kind']=='qi'];assert groups
        group=groups[0];canonical=data['ids'][group['id']]
        members=svc.read_handle(group['membership_handle'])['members'];assert len(members)>1
        expanded=copy.deepcopy(enabled);expanded['pins']=members
        expanded_result=svc.query('viewport_frame',expanded);assert 'error' not in expanded_result,expanded_result
        assert canonical not in expanded_result['data']['ids'].values()
        restored=copy.deepcopy(q);restored['qi']=dict(enabled=False,max_diameter=2,algorithm=DIRECTED)
        off=svc.query('viewport_frame',restored);assert 'error' not in off,off
        assert off['data']['partition_digest']==original['data']['partition_digest']
        assert not any(n['kind']=='qi' for n in off['data']['nodes'])
    finally:store.close()

def test_spatial_qi_requires_atomic_grouping():
    store,svc,sid,ids=make(HELPERS)
    try:
        q=viewport_request(sid,ids['ui.py.display']);q.update(schema_version='1.1',grouping={'mode':'kind','kind':'file'},qi=dict(enabled=True,max_diameter=2,algorithm=DIRECTED))
        result=svc.query('viewport_frame',q)
        assert result['error']['code']=='INVALID_REQUEST'
    finally:store.close()
