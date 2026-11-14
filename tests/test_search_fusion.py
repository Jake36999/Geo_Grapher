"""L1 public interface and informative weak observations, before implementation."""
import json
import pytest
from geographer.agent_requests import call_code,schemas
from test_agent_scent import world


def test_front_door_accepts_two_guesses_and_bounds_schema():
    import jsonschema
    schema=schemas()['search_entities']
    jsonschema.validate(dict(graph_id='local',query='the complete user question',also=['guess','other']),schema)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(dict(graph_id='local',query='q',also=['a','b','c']),schema)


def test_multiquery_keeps_canonical_scoped_source_cards(world):
    out=call_code(world[0],'search_entities',dict(graph_id='scent',query='unmatched_xyz',also=['UPLOAD_BYTES']))
    assert out['entities'][0]['entity_id']==world[1]['UPLOAD_BYTES']
    assert out['result']['data']['query_count']==2
    assert all(h['entity_id'].startswith('entity:') for h in out['result']['data']['hits'])
    assert 'n1' not in json.dumps(out['result']['data']['hits'])
    assert out['result']['data']['nodes'][0]['summary']['signature']=='UPLOAD_BYTES = 4096'
    assert len(json.dumps(out,ensure_ascii=False))<=7500
    from geographer.tokens import TokenCounter
    assert out['routing_budget']['used_tokens']==TokenCounter().count(out)


def test_single_query_ranking_unchanged_and_duplicate_query_ignored(world):
    a=call_code(world[0],'search_entities',dict(graph_id='scent',query='UPLOAD_BYTES'))
    b=call_code(world[0],'search_entities',dict(graph_id='scent',query='UPLOAD_BYTES',also=['UPLOAD_BYTES']))
    assert a['result']['data']['hits']==b['result']['data']['hits']
    assert b['result']['data']['query_count']==1
    assert not a['result']['data']['low_confidence']


def test_weak_search_returns_two_bounded_snapshot_derived_hints(world):
    out=call_code(world[0],'search_entities',dict(graph_id='scent',query='arbitrary orchard capacity'))
    data=out['result']['data']
    assert data['low_confidence'] is True
    assert len(data['try'])==2 and all(0<len(x)<=160 for x in data['try'])
    assert data['confidence']['algorithm']=='preview-confidence-v1'


def test_rrf_stable_ties_and_single_query_identity():
    from geographer.search_fusion import fuse
    a=[dict(node_id='b',score=.7,fragment_ids=['f'],matched_fields=['doc_text']),dict(node_id='a',score=.6,fragment_ids=[],matched_fields=['name'])]
    assert fuse([a])==a
    b=[dict(node_id='a',score=.8,fragment_ids=[],matched_fields=['name']),dict(node_id='b',score=.5,fragment_ids=['g'],matched_fields=['doc_text'])]
    out=fuse([a,b]);assert [h['node_id'] for h in out]==['a','b']
    assert next(h for h in out if h['node_id']=='b')['fragment_ids']==['f','g']


def test_confidence_uses_delivered_previews_not_undelivered_documentation(extract):
    from geographer.agent_scent import SourceScent
    from geographer.search_fusion import observation
    graph,_,_=extract({'m.py':'def pick():\n    """Orchard '+('amber '*30)+'. Capacity is elsewhere in this comment."""\n    return 1\n'})
    eid=next(e.entity_id for e in graph.entities.values() if e.kind=='function')
    descriptions=SourceScent(dict(g=graph,evidence={},sources={}))
    hit=dict(node_id=eid,score=1/61,matched_fields=['doc_text'],fragment_ids=[])
    result=observation([hit],'orchard capacity',descriptions)
    assert result['low_confidence'] is True
    assert result['confidence']['max_doc_overlap']==1
