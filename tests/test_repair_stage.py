"""Public answer gating and bounded repair exports; all responses here are mocks."""
import copy
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.harness import ROOT,load_suite,model_prompt,sha
from evaluation.grounding import validate_actor_answer
from evaluation.repair_context import build_repair_prompt
from evaluation.prepare_repairs import prepare
from evaluation.handoff import score
from geographer.model import canonical
from geographer.tokens import TokenCounter


@pytest.fixture
def recorded(tmp_path):
    suite,files,_=load_suite();task=next(t for t in suite['tasks'] if t['id']=='stale_document')
    scope=dict(snapshot_id='TEST_SNAPSHOT',filter='exact_static_calls',grouping='atomic',model_digest='TEST_RULES',runtime_collection=None)
    evidence=dict(scope=scope,records=[dict(kind='source',path=p,start=1,end=len(b.decode().splitlines()),text=b.decode())
        for p,b in files.items() if p in {'app/ui.py','app/service.py','guide.md'}])
    evidence['records'].append(dict(kind='service',operation='TEST_ONLY',envelope={'data':{'nodes':[],'padding':'fixture '*500}}))
    prompt=model_prompt(task,evidence,sorted({f for t in suite['tasks'] for f in t['oracle']['facts']}))
    good=dict(status='answer',facts=['document:stale','immediate_callee:app/service.py.process','basis:source'],
        paths=[['app/ui.py.submit','app/service.py.process']],citations=[dict(path='guide.md',start=6,end=9),dict(path='app/ui.py',start=7,end=7)],
        scope=scope,explanation='TEST ONLY; not an actual model response')
    bad=copy.deepcopy(good);bad['facts'].remove('basis:source')
    request=dict(eval_id='0/stale_document/flat_search',task_id='stale_document',arm='flat_search',prompt=prompt,
        prompt_sha256=sha(canonical(prompt).encode()),tokenizer='o200k_base',max_output_tokens=1024,total_input_output_limit=16384)
    result=dict(eval_id=request['eval_id'],prompt_sha256=request['prompt_sha256'],model='TEST_MODEL',provider_request_id='TEST_PARENT_NOT_PROVIDER',
        usage=dict(input_tokens=1000,output_tokens=100),answer=bad)
    directory=tmp_path/'original';(directory/'handoff').mkdir(parents=True);(directory/'results/test-model').mkdir(parents=True)
    raw=(canonical(request)+'\n').encode();(directory/'handoff/requests.jsonl').write_bytes(raw)
    manifest=dict(protocol='deepinfra-handoff-v1',requests_sha256=sha(raw),task_manifest_sha256=sha((ROOT/'tasks.json').read_bytes()),
                  source_lock_sha256=sha((ROOT/'sources.lock.json').read_bytes()))
    (directory/'handoff/manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    result_path=directory/'results/test-model/results.jsonl';result_path.write_text(canonical(result)+'\n',encoding='utf-8')
    return directory,result_path,request,result,good


def test_missing_assessment_and_document_citation_are_detected_even_without_stale_fact(recorded):
    _,_,request,_,good=recorded;answer=copy.deepcopy(good)
    answer['facts'].remove('document:stale');answer['citations']=answer['citations'][1:]
    # Old V4 requests lack the new namespace list; their public documentary flag
    # already establishes the need for an explicit assessment and document cite.
    prompt=copy.deepcopy(request['prompt']);prompt['answer_contract'].pop('required_answer_namespaces')
    issues=validate_actor_answer(answer,prompt)
    assert {'MISSING_ASSESSMENT','DOCUMENT_CITATION'}<={i['code'] for i in issues}
    assert all(i['retryable'] for i in issues)
    answer['status']='abstain'
    assert not {'MISSING_ASSESSMENT','DOCUMENT_CITATION'}&{i['code'] for i in validate_actor_answer(answer,prompt)}


def test_compaction_keeps_every_source_byte_and_scope_and_discloses_omissions(recorded):
    _,_,request,result,_=recorded;prompt=request['prompt'];before=copy.deepcopy(prompt)
    repaired=build_repair_prompt(prompt,result['answer'],validate_actor_answer(result['answer'],prompt))
    assert prompt==before and repaired['evidence']['scope']==prompt['evidence']['scope']
    assert repaired['evidence']['records']==[r for r in prompt['evidence']['records'] if r['kind']=='source']
    assert repaired['repair_context']['omitted_record_count']==1
    assert repaired['repair_context']['omitted_kinds']=={'service':1}


def test_preparation_uses_no_oracle_and_shares_original_budgets(recorded,tmp_path,monkeypatch):
    directory,_,_,result,_=recorded
    def forbidden(*a,**k):raise AssertionError('Oracle/grader must not be used to prepare repairs')
    monkeypatch.setattr('evaluation.harness.load_suite',forbidden);monkeypatch.setattr('evaluation.harness.grade',forbidden)
    report=prepare(directory,tmp_path/'repairs');assert report['models'][0]['repair_requests']==1
    child=json.loads((tmp_path/'repairs/test-model/requests.jsonl').read_text())
    counter=TokenCounter();ledger=child['budget_ledger'];remaining=child['total_input_output_limit']
    assert ledger['first_local_tokens']+remaining<=16384
    assert sum(ledger['first_provider_usage'].values())+remaining<=16384
    assert max(ledger['first_answer_local_tokens'],result['usage']['output_tokens'])+child['max_output_tokens']<=1024
    assert counter.count(child)+child['max_output_tokens']+256<=remaining
    assert child['model']=='TEST_MODEL' and child['repair_index']==1


@pytest.mark.parametrize('reason',['valid_answer','output_exhausted','already_repaired','missing_document'])
def test_planner_does_not_retry_everything(recorded,tmp_path,reason):
    directory,path,_,result,good=recorded
    if reason=='valid_answer':result['answer']=good
    elif reason=='output_exhausted':result['usage']['output_tokens']=1024
    elif reason=='already_repaired':result['repair_index']=1
    else:
        # This is a retrieval gap in the original request, not a repairable guess.
        q=json.loads((directory/'handoff/requests.jsonl').read_text())
        q['prompt']['evidence']['records']=[r for r in q['prompt']['evidence']['records'] if r.get('path')!='guide.md']
        q['prompt_sha256']=sha(canonical(q['prompt']).encode());result['prompt_sha256']=q['prompt_sha256']
        raw=(canonical(q)+'\n').encode();(directory/'handoff/requests.jsonl').write_bytes(raw)
        m=json.loads((directory/'handoff/manifest.json').read_text());m['requests_sha256']=sha(raw)
        (directory/'handoff/manifest.json').write_text(json.dumps(m))
    path.write_text(canonical(result)+'\n',encoding='utf-8')
    report=prepare(directory,tmp_path/'repairs')
    assert report['models'][0]['repair_requests']==0
    expected=dict(valid_answer='no_repair_needed',output_exhausted='budget_blocked',already_repaired='repair_limit_requires_review',missing_document='retrieval_blocked')[reason]
    assert report['models'][0]['outcomes'][0]['status']==expected


@pytest.mark.parametrize('fault',['none','wrong_model','cumulative_limit'])
def test_repair_import_reports_separate_stage_and_enforces_parent_ledgers(recorded,tmp_path,fault):
    directory,_,_,_,good=recorded;prepare(directory,tmp_path/'repairs');child_dir=tmp_path/'repairs/test-model'
    q=json.loads((child_dir/'requests.jsonl').read_text())
    if fault=='cumulative_limit':
        q['budget_ledger']['original_total_limit']=100
        raw=(canonical(q)+'\n').encode();(child_dir/'requests.jsonl').write_bytes(raw)
        m=json.loads((child_dir/'manifest.json').read_text());m['requests_sha256']=sha(raw)
        (child_dir/'manifest.json').write_text(json.dumps(m))
    result=dict(eval_id=q['eval_id'],prompt_sha256=q['prompt_sha256'],model='OTHER' if fault=='wrong_model' else 'TEST_MODEL',
        provider_request_id='TEST_CHILD_NOT_PROVIDER',usage=dict(input_tokens=500,output_tokens=100),answer=good)
    result_path=tmp_path/'MOCK-results.jsonl';result_path.write_text(canonical(result)+'\n',encoding='utf-8')
    report=score(child_dir,result_path,result['model'])
    assert report['evaluation_stage']=='bounded_repair'
    if fault=='none':
        outcome=report['outcomes'][0];assert outcome['accepted'] and outcome['grade']['passed'] and not outcome['grounding_issues']
        assert outcome['cumulative_budget']['provider_tokens']==1700
        assert outcome['cumulative_budget']['local_tokens']<=16384
    else:assert report['outcomes'][0]['status']=='identity_or_budget_failed'


def test_repair_import_rejects_changed_parent_receipt(recorded,tmp_path):
    directory,parent,_,_,good=recorded;prepare(directory,tmp_path/'repairs')
    child_dir=tmp_path/'repairs/test-model';q=json.loads((child_dir/'requests.jsonl').read_text())
    result=dict(eval_id=q['eval_id'],prompt_sha256=q['prompt_sha256'],model='TEST_MODEL',provider_request_id='TEST_CHILD',
                usage=dict(input_tokens=500,output_tokens=100),answer=good)
    result_path=tmp_path/'MOCK-results.jsonl';result_path.write_text(canonical(result)+'\n',encoding='utf-8')
    parent.write_text(parent.read_text(encoding='utf-8')+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='Original result receipt changed'):score(child_dir,result_path,'TEST_MODEL')
