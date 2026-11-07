"""Public identity closure and direct-call consistency, without model/oracle calls."""
import copy
import json
import sys
from pathlib import Path
import pytest
import jsonschema

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.harness import load_suite,model_prompt,retrieve,run_model
from evaluation.grounding import validate_actor_answer
from evaluation.transport_schema import compile_transport_schema,check_path_enum_feasibility
from geographer.pipeline import ingest
from geographer.rules import ArchitectureRules
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.tokens import TokenCounter


@pytest.fixture
def flat_prompt():
    suite,files,_=load_suite();task=next(t for t in suite['tasks'] if t['id']=='stale_document')
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('evaluation','fixture-v1',{p:b for p,b in files.items() if not p.endswith('.yaml')})],stage=3)['snapshot_id']
        model=ArchitectureRules(files['geographer.rules.yaml']);service=QueryService(store,rules=[model])
        evidence,_=retrieve(service,sid,model,store.graph(sid),files,task,'flat_search',TokenCounter())
        yield model_prompt(task,evidence,sorted({f for t in suite['tasks'] for f in t['oracle']['facts']}))


def answer(prompt):
    return dict(status='answer',facts=['document:stale','immediate_callee:app/service.py.process','basis:source'],
        citations=[dict(path='guide.md',start=6,end=9),dict(path='app/ui.py',start=7,end=7)],
        paths=[['app/ui.py.submit','app/service.py.process']],
        scope={k:prompt['evidence']['scope'][k] for k in ('snapshot_id','filter','grouping','model_digest','runtime_collection')},
        explanation='UNIT TEST ONLY; not a model response')


def test_imported_callee_is_legal_without_extra_file_or_graph_edge(flat_prompt):
    sources=[r for r in flat_prompt['evidence']['records'] if r['kind']=='source']
    assert len(sources)==3 and 'app/service.py' not in {r['path'] for r in sources}
    assert all(r['kind']!='service' for r in flat_prompt['evidence']['records'])
    compiled=compile_transport_schema(flat_prompt)
    allowed=compiled['response_format']['json_schema']['schema']['properties']['paths']['items']['items']['enum']
    assert 'app/service.py.process' in allowed
    jsonschema.validate(answer(flat_prompt),compiled['full_specialized_schema'])
    assert not validate_actor_answer(answer(flat_prompt),flat_prompt)


def test_excluded_public_target_fails_before_any_provider_request(flat_prompt):
    compiled=compile_transport_schema(flat_prompt)
    schema=copy.deepcopy(compiled['response_format']['json_schema']['schema'])
    schema['properties']['paths']['items']['items']['enum'].remove('app/service.py.process')
    with pytest.raises(ValueError,match='PATH_ENUM_INFEASIBLE'):check_path_enum_feasibility(flat_prompt,schema)
    # Reproduce v3's construction defect: scope had no identity closure.
    legacy=copy.deepcopy(flat_prompt);legacy['evidence']['scope'].pop('anchor_identities')
    with pytest.raises(ValueError,match='PATH_ENUM_INFEASIBLE'):compile_transport_schema(legacy)


def test_invalid_contract_is_archived_without_executing_adapter(flat_prompt,tmp_path):
    legacy=copy.deepcopy(flat_prompt);legacy['evidence']['scope'].pop('anchor_identities')
    marker=tmp_path/'executed'
    result=run_model([sys.executable,'-c',f'open({str(marker)!r},"w").write("bad")'],
        dict(model='TEST_ONLY',configuration={},provider_spend_cap=.01),legacy,TokenCounter(),16384,1024)
    assert result['status']=='invalid_actor_contract' and not result['provider_request_sent']
    assert not marker.exists() and 'PATH_ENUM_INFEASIBLE' in result['error']


@pytest.mark.parametrize('wrong_target',['app/helpers.py.retry_save','app/ui.py.bypass','app/ui.py.submit'])
def test_three_recorded_wrong_endpoints_get_specific_consistency_error(flat_prompt,wrong_target):
    bad=answer(flat_prompt);bad['paths'][0][-1]=wrong_target
    codes={i['code'] for i in validate_actor_answer(bad,flat_prompt)}
    assert {'PATH_ANCHORS','CALLEE_PATH_CONSISTENCY'}<=codes
    assert all(i['retryable'] for i in validate_actor_answer(bad,flat_prompt))


def test_direct_call_does_not_accept_or_misclassify_an_inserted_intermediate(flat_prompt):
    result=answer(flat_prompt);result['paths'][0].insert(1,'app/helpers.py.retry_save')
    issues=validate_actor_answer(result,flat_prompt)
    assert any(i['code']=='DIRECT_PATH_LENGTH' for i in issues)
    assert all(i['retryable'] for i in issues)
    wire=compile_transport_schema(flat_prompt)['response_format']['json_schema']['schema']
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(result,wire)


def test_multihop_intermediate_callee_is_not_forced_to_final_target(flat_prompt):
    prompt=copy.deepcopy(flat_prompt)
    prompt['answer_contract']['path_semantics']='dependency_chain'
    prompt['answer_contract']['requested_paths']=[dict(source='app/ui.py.submit',target='app/storage.py.save')]
    result=answer(prompt);result['facts']=['callee:app/helpers.py.retry_save']
    result['paths']=[['app/ui.py.submit','app/service.py.process','app/helpers.py.retry_save','app/storage.py.save']]
    codes={i['code'] for i in validate_actor_answer(result,prompt)}
    assert not {'CALLEE_PATH_CONSISTENCY','CALLEE_TASK_SCOPE'}&codes


def test_unrelated_direct_callee_is_removed_not_added_as_an_extra_path(flat_prompt):
    result=answer(flat_prompt);result['facts'].append('callee:app/storage.py.save')
    assert any(i['code']=='CALLEE_TASK_SCOPE' for i in validate_actor_answer(result,flat_prompt))


def test_identity_metadata_never_substitutes_for_call_source(flat_prompt):
    prompt=copy.deepcopy(flat_prompt)
    prompt['evidence']['records']=[r for r in prompt['evidence']['records'] if r.get('path')!='app/ui.py']
    result=answer(prompt);result['citations']=[dict(path='guide.md',start=6,end=9)]
    issues=validate_actor_answer(result,prompt)
    assert any(i['code']=='WITNESS_SOURCE_GAP' and not i['retryable'] for i in issues)


def test_archived_v3_schema_really_excluded_the_expected_public_target():
    path=Path(__file__).resolve().parents[1]/'output/phase5/actor-contract-v3-20261107/handoff/requests.jsonl'
    if not path.exists():pytest.skip('Local historical artifacts unavailable')
    request=next(r for r in map(json.loads,path.read_text(encoding='utf-8').splitlines()) if r['eval_id']=='0/stale_document/flat_search')
    schema=request['response_format']['json_schema']['schema']
    assert request['prompt']['answer_contract']['requested_paths'][0]['target']=='app/service.py.process'
    assert 'app/service.py.process' not in schema['properties']['paths']['items']['items']['enum']
