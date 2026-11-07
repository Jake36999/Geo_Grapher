"""Independent evaluation/grader regressions; mock adapters are never model results."""
import copy
import json
import sys
from pathlib import Path
import pytest

# Evaluation is checkout tooling and intentionally outside the installed runtime.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.harness import (load_suite,grade,ANSWER_SCHEMA,pack_evidence,
                               closure_errors,run_model,schedule,ARMS,model_prompt)
from geographer.tokens import TokenCounter


def example():
    suite,files,_=load_suite();task=suite['tasks'][1]
    scope=dict(snapshot_id='pinned',filter='exact_static_calls',grouping='atomic',model_digest='rules',runtime_collection=None)
    evidence=dict(scope=scope,records=[dict(kind='source',path=p,start=1,end=len(raw.decode().splitlines()),text=raw.decode()) for p,raw in files.items()])
    answer=dict(status=task['oracle']['status'],facts=task['oracle']['facts'][:],
                citations=[{k:c[k] for k in ('path','start','end')} for c in task['oracle']['citations']],
                paths=copy.deepcopy(task['oracle']['paths']),scope=scope.copy(),explanation='Static witnesses; execution is not established.')
    return task,files,evidence,answer


def test_source_locked_manual_oracles_and_all_six_task_categories():
    suite,_,_=load_suite()
    assert len(suite['tasks'])==12
    assert {'implementation','cross_subsystem','callers_callees','impact','quotient_cycle','rule_violation'} <= {t['category'] for t in suite['tasks']}


@pytest.mark.parametrize('fault',['direction','citation','scope','certainty','missing_step','missing_fact','unknown_path','absent_source','unobserved_runtime','extra_key'])
def test_grader_rejects_plausible_but_unsupported_answers(fault):
    task,files,evidence,answer=example()
    assert grade(task,answer,evidence,files)['passed']
    if fault=='direction':answer['paths'][0].reverse()
    elif fault=='citation':answer['citations'][0]['start']=999
    elif fault=='scope':answer['scope']['snapshot_id']='stale'
    elif fault=='certainty':answer['facts'].append('execution:proven')
    elif fault=='missing_step':answer['paths'][0].pop(1)
    elif fault=='missing_fact':answer['facts'].pop()
    elif fault=='unknown_path':answer['citations'][0]['path']='outside.py'
    elif fault=='absent_source':evidence['records']=[]
    elif fault=='unobserved_runtime':answer['status']='abstain'
    elif fault=='extra_key':answer['convincing_prose']='trust me'
    assert not grade(task,answer,evidence,files)['passed']


def test_all_oracles_can_be_graded_from_source_without_the_extractor():
    suite,files,_=load_suite();_,_,evidence,_=example()
    for task in suite['tasks']:
        answer=dict(status=task['oracle']['status'],facts=task['oracle']['facts'],
            citations=[{k:c[k] for k in ('path','start','end')} for c in task['oracle']['citations']],
            paths=task['oracle']['paths'],scope=evidence['scope'],explanation='Grader fixture, not a model result.')
        assert grade(task,answer,evidence,files)['passed'],task['id']


def test_prompt_never_contains_selected_task_oracle():
    task,_,evidence,_=example();prompt=model_prompt(task,evidence,['basis:static'])
    assert set(prompt)=={'protocol','instructions','question','evidence','answer_schema','answer_contract','shared_label_vocabulary'}
    assert 'oracle' not in prompt


@pytest.mark.parametrize('encoding',['o200k_base','cl100k_base'])
def test_whole_bundle_budget_endpoint_closure_and_unicode(encoding):
    counter=TokenCounter(encoding)
    graph={'data':{'nodes':[{'id':'a'},{'id':'b'}],'relationships':[{'source':'a','target':'b'}]}}
    bundles=[{'kind':'service','envelope':graph},{'kind':'source','text':'λ🙂漢字'*1000}]
    result=pack_evidence({'scope':'static'},bundles,counter,200)
    assert counter.count(result)<=200
    assert result['records']==bundles[:1] and result['omitted_bundles']==[1]
    assert not closure_errors(result['records'][0]['envelope'])
    graph['data']['nodes'].pop()
    assert closure_errors(graph)


def test_byte_fallback_uses_byte_upper_bound_not_div4(tmp_path):
    counter=TokenCounter(allow_byte_fallback=True,directory=tmp_path)
    result=pack_evidence({'s':'x'},[{'text':'🙂'*100}],counter,160)
    assert counter.cost(result)<=160 and result['records']==[]


def test_preregistered_random_schedule_retains_every_failure_slot():
    tasks=[{'id':'a'},{'id':'b'}]
    first=schedule(tasks,3,505)
    assert first==schedule(tasks,3,505)
    assert len(first)==3*2*len(ARMS)
    assert first!=schedule(tasks,3,506)


def test_adapter_preflight_never_executes_over_budget(tmp_path):
    marker=tmp_path/'executed'
    config=dict(model='fixture-not-real-model',configuration={},provider_spend_cap=.01)
    result=run_model([sys.executable,'-c',f'open({str(marker)!r},"w").write("bad")'],config,{'large':'x'*1000},TokenCounter(),100,80)
    assert result['status']=='budget_rejected' and not marker.exists()


@pytest.mark.parametrize('fault',['none','provider_budget','local_budget','wrong_model','failed','invalid'])
def test_explicit_mock_adapter_protocol_and_two_budget_ledgers(fault):
    config=dict(model='fixture-not-real-model',configuration={'seed':1},provider_spend_cap=.01)
    response=dict(model=config['model'],provider_request_id='test-only-not-provider',usage=dict(input_tokens=100,output_tokens=20),answer={'explanation':'ok'})
    if fault=='provider_budget':response['usage']['input_tokens']=9000
    if fault=='local_budget':response['answer']['explanation']='漢字'*200
    if fault=='wrong_model':response['model']='not-pinned'
    code='import sys; sys.stdin.read(); '
    code+= 'sys.exit(7)' if fault=='failed' else 'print("not json")' if fault=='invalid' else f'print({json.dumps(response)!r})'
    result=run_model([sys.executable,'-c',code],config,{'question':'test'},TokenCounter(),2048,256)
    assert result['status']==dict(none='recorded',provider_budget='model_budget_exceeded',local_budget='model_budget_exceeded',wrong_model='invalid_adapter_response',failed='adapter_failed',invalid='invalid_adapter_response')[fault]


def test_offline_end_to_end_records_unverified_and_keeps_all_arms(tmp_path):
    from evaluation.run import run
    manifest,summary=run(tmp_path/'run',repeats=1)
    assert manifest['model_evaluation']=='unverified_no_adapter_configured'
    assert set(summary)==set(ARMS)
    assert all(s['samples']==12 and s['model_status_counts']=={'unverified':12} for s in summary.values())
    assert all(s['retrieval_errors']==0 for s in summary.values())
    assert len((tmp_path/'run/transcripts.jsonl').read_text(encoding='utf-8').splitlines())==60


def test_toolset_audit_keeps_repository_path_separate_from_occurrence_paths(tmp_path,monkeypatch):
    from evaluation import toolset
    from geographer.source import Repository
    _,files,_=load_suite();repo=Repository('ToolSet',toolset.COMMIT,{p:b for p,b in files.items() if p.endswith('.py')})
    monkeypatch.setattr(toolset,'SOURCE_DIGEST',repo.content_digest)
    monkeypatch.setattr(toolset.Repository,'from_git',lambda *a,**kw:repo)
    paths=[]
    def status(command):paths.append(command[2]);return b'unchanged'
    monkeypatch.setattr(toolset.subprocess,'check_output',status)
    oracle=tmp_path/'oracle.json';oracle.write_text(json.dumps(dict(scope='Test-only manual source oracle',expected=[
        dict(site=['app/ui.py',7,11],target=['app/service.py',4,'process'])])),encoding='utf-8')
    report=toolset.run(tmp_path/'out',tmp_path/'repository',oracle)
    assert paths==[str(tmp_path/'repository')]*2 and report['worktree_unchanged']
    assert report['independent_oracle']['correct_exact']==1


def test_stress_workloads_use_independent_path_reference(tmp_path):
    from evaluation.stress import run
    result=run(tmp_path/'stress',documents=3,vertices=20)
    assert not result['documentary']['publication_validation']
    assert result['bounded_paths']['reference_agreement']==24


def test_adapter_rejects_duplicate_and_nonfinite_json():
    from evaluation.harness import strict_json
    for raw in ('{"model":"a","model":"b"}','{"usage":NaN}'):
        with pytest.raises(ValueError):strict_json(raw)


def test_valid_scope_labels_do_not_create_false_negative_answer_grades():
    task,files,evidence,answer=example()
    answer['facts']+=['basis:source','runtime:unknown','static_call:not_execution']
    result=grade(task,answer,evidence,files)
    assert result['passed'] and result['facts_correct'] and not result['strict_v1_fact_set_match']
    assert result['unsupported_facts']==[]


def test_custom_harness_export_import_retains_missing_budget_and_identity_failures(tmp_path):
    from evaluation.handoff import export,score
    from evaluation.harness import ROOT,sha
    from geographer.model import canonical
    suite,_,_=load_suite();tasks={t['id']:t for t in suite['tasks']};_,_,evidence,_=example()
    run=tmp_path/'run';run.mkdir()
    manifest=dict(task_manifest_sha256=sha((ROOT/'tasks.json').read_bytes()),source_lock_sha256=sha((ROOT/'sources.lock.json').read_bytes()),
                  tokenizer='o200k_base',reserved_output=1024,total_input_output_limit=16384)
    (run/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    rows=[dict(trial=0,task_id=t,arm=a,evidence=evidence) for t in ('direction','stale_document') for a in ('flat_search','architecture_documents_paths')]
    (run/'transcripts.jsonl').write_text(''.join(canonical(r)+'\n' for r in rows),encoding='utf-8')
    requests=export(run,tmp_path/'handoff');results=[]
    for q in requests:
        oracle=tasks[q['task_id']]['oracle']
        # Explicit mock result to test file interchange; never a model artifact.
        answer=dict(status=oracle['status'],facts=oracle['facts'],paths=oracle['paths'],scope=evidence['scope'],explanation='TEST FIXTURE ONLY',
                    citations=[{k:c[k] for k in ('path','start','end')} for c in oracle['citations']])
        results.append(dict(eval_id=q['eval_id'],model='test-model',provider_request_id='test-only-not-provider',prompt_sha256=q['prompt_sha256'],
                            usage=dict(input_tokens=100,output_tokens=20),answer=answer))
    results[1]['usage']['output_tokens']=99999
    results[2]['prompt_sha256']='wrong';results.pop()
    file=tmp_path/'mock-results.jsonl';file.write_text(''.join(canonical(r)+'\n' for r in results),encoding='utf-8')
    report=score(tmp_path/'handoff',file,'test-model')
    assert [r['status'] for r in report['outcomes']]==['recorded','identity_or_budget_failed','identity_or_budget_failed','missing_result']
    assert report['outcomes'][0]['grade']['passed']
    with pytest.raises(ValueError,match='already exists'):score(tmp_path/'handoff',file,'test-model')
    file.write_text(canonical(results[0])+'\n'+canonical(results[0])+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='Duplicate'):score(tmp_path/'handoff',file,'test-model')
