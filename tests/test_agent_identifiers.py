import json,re
import pytest
from test_task_packets import packet_world
from test_graph_catalog import hub,import_graph
from geographer.agent_requests import call_code

def walk(value):
    if isinstance(value,dict):
        for k,v in value.items():yield k;yield from walk(v)
    elif isinstance(value,list):
        for v in value:yield from walk(v)
    elif isinstance(value,str):yield value

def test_flat_response_has_canonical_ids_and_recent_alias_resolves(packet_world):
    cat,router,gid,ids=packet_world
    out=call_code(router,'search_entities',dict(graph_id='code',query='f',kinds=['function']))
    assert not any(re.fullmatch('[nwe][0-9]+',s) for s in walk(out))
    nodes=out['result']['data']['nodes']
    assert nodes and all('id' not in n and n['entity_id'].startswith('entity:') and n['cite_as'].startswith('code/entity:') for n in nodes)
    with router.lease(gid) as svc:
        from geographer.actor import ActorEncoder
        svc.active_snapshot=cat.graph(gid)['snapshot_id']
        encoder=ActorEncoder(svc,svc._context(svc.active_snapshot),'test')
        alias=encoder.aliases[ids['f']]
    content=call_code(router,'get_entity_content',dict(graph_id='code',entity_id=alias))
    assert 'def f' in json.dumps(content)

def test_ambiguous_alias_error_contains_valid_scoped_choices(packet_world):
    from geographer.agent_requests import remember_aliases,error
    cat,router,gid,ids=packet_world;sid=cat.graph(gid)['snapshot_id']
    remember_aliases(router,gid,sid,{'n99999':ids['f']})
    remember_aliases(router,gid,sid,{'n99999':ids['g']})
    with pytest.raises(ValueError) as caught:call_code(router,'get_entity_content',dict(graph_id='code',entity_id='n99999'))
    e=error('get_entity_content',caught.value)['error']
    assert e['example']['graph_id']=='code' and e['example']['entity_id'] in ids.values()
    assert {x['entity_id'] for x in e['choices']}==set(ids.values())

def test_recent_alias_does_not_cross_client_connections(packet_world):
    from geographer.agent_requests import ALIAS_CONNECTION,remember_aliases
    cat,router,gid,ids=packet_world;sid=cat.graph(gid)['snapshot_id']
    remember_aliases(router,gid,sid,{'n99999':ids['f']})
    token=ALIAS_CONNECTION.set(object())
    try:
        with pytest.raises(ValueError,match='Search this graph first'):
            call_code(router,'get_entity_content',dict(graph_id='code',entity_id='n99999'))
    finally:ALIAS_CONNECTION.reset(token)

def test_agent_federation_also_has_no_display_aliases(hub,tmp_path):
    cat,router,a=hub;b=import_graph(cat,tmp_path/'b','B')
    router.max_result_chars=7500
    out=router.federated_search([a['graph_id'],b['graph_id']],'research',agent=True)
    assert not any(re.fullmatch('[nwe][0-9]+',s) for s in walk(out))
    assert len(json.dumps(out,ensure_ascii=False))<=7500
