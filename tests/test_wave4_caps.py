"""Flat clients degrade honestly; strict clients retain their wire contract."""
import json
import pytest
from test_graph_catalog import hub,import_graph
from test_task_packets import packet_world
from geographer.agent_requests import call_code
from geographer.tokens import TokenCounter

def test_federation_char_cap_keeps_whole_envelopes(hub,tmp_path):
    cat,router,_=hub
    rows=[]
    for label in ('many-a','many-b'):
        root=tmp_path/label;root.mkdir()
        for i in range(8):(root/f'module_{i}.py').write_text(f'def research_{i}():\n    """Research methods for independent graphs."""\n    return {i}\n')
        from geographer.source import Repository
        rows.append(cat.import_project(root,Repository.from_directory(root,label),label=label))
    a,b=rows
    router.max_result_chars=7500
    out=router.federated_search([a['graph_id'],b['graph_id']],'research',limit_tokens=8192)
    assert len(json.dumps(out,ensure_ascii=False))<=7500
    assert out['used_tokens']==TokenCounter().count(out)
    assert any(r['reason']=='size_limit' for r in out['omitted'])
    for envelope in out['results']:
        d=envelope['result']['data'];ids={n['id'] for n in d['nodes']}
        assert all(r['source'] in ids and r['target'] in ids for r in d['relationships'])

@pytest.mark.parametrize('cap',[2600,4500])
def test_flat_context_and_dependants_degrade_under_cap(packet_world,cap):
    cat,router,gid,ids=packet_world
    router.max_result_chars=cap
    for op,key in [('get_architecture_context','focus_id'),('find_dependants','entity_id')]:
        out=call_code(router,op,dict(graph_id=gid,**{key:ids['f']}))
        assert 'error' not in out and 'error' not in out.get('result',{})
        assert len(json.dumps(out,ensure_ascii=False))<=cap
        assert out['degraded']
        assert out['routing_budget']['used_tokens']==TokenCounter().count(out)
        assert any(e['entity_id']==ids['f'] for e in out['entities'])
