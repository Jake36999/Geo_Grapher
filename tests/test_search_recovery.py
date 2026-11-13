"""Search remedies use structured metadata and one shared bounded action."""
import json
from geographer.agent_requests import call_code
from geographer.search_recovery import META
from test_agent_scent import world


def run(world,episode='episode',mode='auto',remaining=3,question='upload fallback capacity'):
    token=META.set(dict(episode_id=episode,question=question,mode=mode,remaining_steps=remaining))
    try:return call_code(world[0],'search_entities',dict(graph_id='scent',query='unmatched_xyz'))
    finally:META.reset(token)


def test_defer_records_trigger_without_action_or_recovered_evidence(world):
    out=run(world,mode='defer')
    assert out['recovery_pending'][0]['pattern']=='FP1'
    assert out['recovery_steps_consumed']==0 and out['recoveries']==[]
    assert out['entities']==[]


def test_research_question_recovery_happens_once_and_is_logged(world):
    a=run(world);b=run(world)
    assert a['recovery_steps_consumed']==1 and b['recovery_steps_consumed']==0
    assert a['recoveries']==b['recoveries'] and len(a['recoveries'])==1
    record=a['recoveries'][0]
    assert record['pattern']=='FP1' and record['trigger_value'] and record['action']=='verbatim_multiquery'
    assert record['outcome'] in {'resolved','unresolved'}
    assert any(e['entity_id']==world[1]['UPLOAD_BYTES'] for e in a['entities'])
    assert a['entities']==b['entities']
    assert len(json.dumps(a,ensure_ascii=False))<=7500


def test_no_remaining_budget_cannot_execute_recovery(world):
    out=run(world,remaining=0)
    assert out['recovery_steps_consumed']==0 and out['entities']==[]


def test_same_episode_cannot_change_its_question(world):
    import pytest
    run(world)
    with pytest.raises(ValueError,match='question changed'):run(world,question='different question')


def test_scoped_id_advice_is_logged_and_resolution_uses_a_real_candidate(world):
    from geographer.agent_requests import error
    token=META.set(dict(episode_id='id-episode',question='upload fallback capacity',mode='defer',remaining_steps=3))
    try:
        call_code(world[0],'search_entities',dict(graph_id='scent',query='UPLOAD_BYTES'))
        try:call_code(world[0],'get_entity_content',dict(graph_id='scent',entity_id='entity:mistyped'))
        except ValueError as exc:bad=error('get_entity_content',exc)
        record=next(r for r in bad['recoveries'] if r['pattern']=='FP6')
        assert record['outcome']=='unresolved' and record['action']=='scoped_candidates'
        choice=bad['error']['choices'][0]['entity_id']
        out=call_code(world[0],'get_entity_content',dict(graph_id='scent',entity_id=choice))
        assert next(r for r in out['recoveries'] if r['pattern']=='FP6')['outcome']=='resolved'
        assert out['coverage']
    finally:META.reset(token)


def test_pattern_used_on_another_server_is_not_run_again(world):
    token=META.set(dict(episode_id='cross-server',question='upload fallback capacity',mode='auto',remaining_steps=2,used_patterns=['FP1']))
    try:
        out=call_code(world[0],'search_entities',dict(graph_id='scent',query='unmatched_xyz'))
        assert out['recovery_steps_consumed']==0 and out['entities']==[]
    finally:META.reset(token)


def test_recovery_is_still_accounted_when_the_requested_response_budget_cannot_fit(world):
    import pytest
    from geographer.agent_requests import call_code_connection,error
    class Connection:pass
    connection=Connection()
    metadata={'geographer/recovery':dict(episode_id='tiny-budget',question='upload fallback capacity',mode='auto',remaining_steps=3)}
    with pytest.raises(ValueError) as caught:
        call_code_connection(world[0],'search_entities',dict(graph_id='scent',query='unmatched_xyz',limit_tokens=256),connection,metadata)
    out=error('search_entities',caught.value)
    assert out['recoveries'][0]['pattern']=='FP1'
    assert out['recovery_steps_consumed']==1
