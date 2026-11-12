"""Whole, cited, snapshot-scoped task packets and explicit profile ceilings."""
import json
import pytest
from test_bridges import hub_with_code_and_papers

from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter, TOOL_PRESETS
from geographer.source import Repository
from geographer.tokens import TokenCounter


@pytest.fixture
def packet_world(tmp_path):
    cat = GraphCatalog(tmp_path / 'catalog' / 'catalog.sqlite')
    root = tmp_path / 'code'; root.mkdir()
    (root / 'm.py').write_text('def f(x):\n    return x + 1\n\ndef g(y):\n    return f(y)\n', encoding='utf-8')
    row = cat.import_project(root, Repository.from_directory(root, 'code'), label='code')
    router = GraphRouter(cat)
    with router.lease(row['graph_id']) as svc:
        ids = {r['qualified_name'].rsplit('.', 1)[-1]: r['entity_id'] for r in svc.store.connection.execute(
            "SELECT * FROM entities WHERE snapshot_id=? AND kind='function'", (cat.graph(row['graph_id'])['snapshot_id'],))}
    yield cat, router, row['graph_id'], ids
    router.close(); cat.close()


def test_packet_budget_content_handles_and_determinism(packet_world):
    _, r, gid, ids = packet_world
    p = r.compile_task_packet(gid, ['entity:' + ids['f']], 'Describe ports.')
    assert p['packet_version'] == 'task-packet-v1'
    assert p['used_tokens'] == TokenCounter().count(p) <= p['limit_tokens'] == 1200
    assert p['anchors'][0]['ref'] == 'entity:' + ids['f']
    assert 'def f(x)' in p['anchors'][0]['text']
    assert p['anchors'][0]['cite_as'] in p['handles']
    assert all(b['cite_as'] in p['handles'] for b in p['boundary'])
    assert p == r.compile_task_packet(gid, ['entity:' + ids['f']], 'Describe ports.')


def test_packet_rejects_bad_anchor_long_instruction_and_scope(packet_world):
    cat, r, gid, ids = packet_world
    with pytest.raises(ValueError, match='^INSTRUCTION_TOO_LONG'):
        r.compile_task_packet(gid, ['entity:' + ids['f']], 'x ' * 2000)
    with pytest.raises(ValueError, match='^BRIDGE_ENDPOINT_UNRESOLVED'):
        r.compile_task_packet(gid, ['entity:nope'], 'Describe.')
    scoped = GraphRouter(cat, allowed={gid})
    with pytest.raises(ValueError):
        scoped.compile_task_packet('not-this-graph', ['root'], 'Describe.')
    scoped.close()


def test_upstream_is_structured_revalidated_and_budgeted(packet_world):
    _, r, gid, ids = packet_world
    ref = 'entity:' + ids['f']
    cite = r.compile_task_packet(gid, [ref], 'Describe.')['anchors'][0]['cite_as']
    upstream = [{'task_id': 't1', 'ref': ref, 'cite': cite, 'inputs': [
        {'name': 'x', 'cite': cite}, {'name': 'ghost', 'cite': 'elsewhere/entity:nope'}],
        'outputs': [{'name': 'value', 'cite': cite}]}]
    p = r.compile_task_packet(gid, ['entity:' + ids['g']], 'Describe.', upstream=upstream)
    assert p['upstream_dropped'] == 1 and p['upstream_omitted'] == 0
    assert [i['name'] for i in p['upstream'][0]['inputs']] == ['x']
    assert p['upstream'][0]['origin'] == 'model_produced_citation_verified'
    assert cite in p['handles']
    assert p['used_tokens'] == TokenCounter().count(p) <= 1200


def test_packets_fit_connection_limit_by_dropping_whole_items(packet_world):
    _, r, gid, ids = packet_world
    r.max_result_chars = 1000
    p = r.compile_task_packet(gid, ['entity:' + ids['f'], 'entity:' + ids['g']], 'Describe.')
    assert len(json.dumps(p, ensure_ascii=False)) <= 1000
    assert p['used_tokens'] == TokenCounter().count(p)


def test_profiles_reject_without_silent_clamp(packet_world):
    cat, r, gid, _ = packet_world
    req = dict(schema_version='1.1', request_id='profile', snapshot_id=cat.graph(gid)['snapshot_id'],
               budget=dict(limit_tokens=4000, profile='tier2_forager', tokenizer='o200k_base', allow_byte_fallback=False),
               query='f', mode='lexical', repo_ids=[], kinds=[], limit=5, cursor=None)
    with pytest.raises(ValueError, match='^BUDGET_EXCEEDS_PROFILE'):
        r.query(gid, 'search_entities', req)
    assert len(TOOL_PRESETS['lead']) == 6 and 'compile_task_packet' in TOOL_PRESETS['lead']


def test_unknown_profile_is_rejected(packet_world):
    _, r, gid, ids = packet_world
    with pytest.raises(ValueError, match='PROFILE'):
        r.compile_task_packet(gid, ['entity:' + ids['f']], 'Describe.', profile='typo')


def test_known_profile_is_accepted_by_wire_and_boundary_is_real(packet_world):
    cat,r,gid,ids=packet_world
    p=r.compile_task_packet(gid,['entity:'+ids['f']],'Describe.')
    assert p['boundary']
    assert any(b['subtype']=='calls' for b in p['boundary'])
    req=dict(schema_version='1.1',request_id='profile',snapshot_id=cat.graph(gid)['snapshot_id'],
        budget=dict(limit_tokens=1800,profile='tier2_forager',tokenizer='o200k_base',allow_byte_fallback=False),
        query='f',mode='lexical',repo_ids=[],kinds=[],limit=5,cursor=None)
    assert 'error' not in r.query(gid,'search_entities',req)['result']


def test_paper_anchors_use_read_model_columns(hub_with_code_and_papers):
    cat,c,p,_=hub_with_code_and_papers
    r=GraphRouter(cat)
    packet=r.compile_task_packet(p,['doc:1'],'Describe.')
    assert 'Knowledge graphs' in packet['anchors'][0]['text']
    r.close()


def test_upstream_can_cite_an_actual_boundary_handle(packet_world):
    _,r,gid,ids=packet_world
    ref='entity:'+ids['f']; p=r.compile_task_packet(gid,[ref],'Describe.')
    boundary=p['boundary'][0]['cite_as']
    up=[dict(task_id='before',ref=ref,cite=p['anchors'][0]['cite_as'],
             inputs=[dict(name='caller',cite=boundary)],outputs=[])]
    out=r.compile_task_packet(gid,[ref],'Describe.',upstream=up)
    assert out['upstream_dropped']==0 and out['upstream'][0]['inputs'][0]['cite']==boundary
    assert boundary in out['handles']
