"""Small, offline regressions for the Librarian-reported actor failures."""
import copy
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.harness import load_suite,model_prompt,retrieve,run_model
from evaluation.grounding import validate_actor_answer,validation_callback
from geographer.pipeline import ingest
from geographer.rules import ArchitectureRules
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.tokens import TokenCounter


def sample(stale=False,documents=True):
    suite,files,_=load_suite();task=next(t for t in suite['tasks'] if t['id']==('stale_document' if stale else 'direction'))
    evidence=dict(scope=dict(snapshot_id='fixture',filter='exact_static_calls',grouping='atomic',model_digest='rules',runtime_collection=None),records=[
        dict(kind='source',path=p,start=1,end=len(b.decode().splitlines()),text=b.decode())
        for p,b in files.items() if p.endswith('.py') or documents and p.endswith('.md')])
    prompt=model_prompt(task,evidence,sorted({f for t in suite['tasks'] for f in t['oracle']['facts']}))
    # These hand-authored expected fields are test fixtures, never repair inputs.
    answer=dict(status='answer',facts=['document:stale','immediate_callee:app/service.py.process','basis:source'] if stale else ['caller:app/service.py.process','callee:app/helpers.py.retry_save'],
        citations=[dict(path='app/ui.py',start=7,end=7),dict(path='guide.md',start=6,end=9)] if stale else [dict(path='app/service.py',start=8,end=8)],
        paths=[['app/ui.py.submit','app/service.py.process']] if stale else [['app/service.py.process','app/helpers.py.retry_save']],
        scope=evidence['scope'],explanation='TEST FIXTURE ONLY')
    return prompt,answer


def test_absolute_source_presentation_preserves_original_bytes_and_numbers():
    prompt,_=sample()
    record=next(r for r in prompt['evidence']['records'] if r['path']=='app/service.py')
    assert 'text' not in record and record['lines'][7]==dict(line=8,text='    return retry_save(value)\n')
    _,files,_=load_suite();assert ''.join(line['text'] for line in record['lines']).encode()==files['app/service.py']


@pytest.mark.parametrize('fault,code',[
    ('file_path','PATH_IDENTITY'),('import_line','CALL_SITE_CITATION'),
    ('unknown_fact','FACT_VOCABULARY'),('stale_scope','STALE_SCOPE'),('range','CITATION_RANGE')])
def test_oracle_free_validator_catches_reported_shapes(fault,code):
    prompt,answer=sample();assert not validate_actor_answer(answer,prompt)
    if fault=='file_path':answer['paths'][0][0]='app/service.py'
    elif fault=='import_line':answer['citations'][0].update(start=1,end=5)
    elif fault=='unknown_fact':answer['facts'].append('app/service.py.process')
    elif fault=='stale_scope':answer['scope']={**answer['scope'],'snapshot_id':'stale'}
    elif fault=='range':answer['citations'][0]['end']=999
    issues=validate_actor_answer(answer,prompt)
    assert any(p['code']==code for p in issues)
    if fault=='file_path':assert all(p['retryable'] for p in issues)
    assert code in validation_callback(prompt)(answer)


def test_original_document_missing_is_retrieval_gap_not_repairable_guess():
    prompt,answer=sample(stale=True,documents=False)
    issues=validate_actor_answer(answer,prompt)
    assert any(p['code']=='DOCUMENT_SOURCE_GAP' and not p['retryable'] for p in issues)
    prompt,answer=sample(stale=True)
    assert not validate_actor_answer(answer,prompt)
    answer['citations']=answer['citations'][:1]
    assert any(p['code']=='DOCUMENT_CITATION' for p in validate_actor_answer(answer,prompt))


def test_task_vocabulary_excludes_unrelated_rule_labels_without_oracle_values():
    prompt,answer=sample(stale=True)
    assert 'rule:no_ui_storage' not in prompt['shared_label_vocabulary']
    assert 'document:stale' in prompt['shared_label_vocabulary']
    answer['facts'].append('rule:no_ui_storage')
    assert any(p['code']=='FACT_TASK_SCOPE' for p in validate_actor_answer(answer,prompt))


def test_strings_and_comments_that_look_like_calls_do_not_ground_edges():
    prompt,answer=sample()
    source=next(r for r in prompt['evidence']['records'] if r['path']=='app/service.py')
    source['lines']=[dict(line=1,text='def process(value):\n'),dict(line=2,text='    # retry_save(value)\n'),dict(line=3,text='    return "retry_save(value)"\n')]
    source['end']=3;answer['citations']=[dict(path='app/service.py',start=2,end=3)]
    assert any(p['code']=='WITNESS_SOURCE_GAP' for p in validate_actor_answer(answer,prompt))


def test_imported_alias_can_ground_an_original_call_site():
    prompt,answer=sample()
    source=next(r for r in prompt['evidence']['records'] if r['path']=='app/service.py')
    lines=['from .helpers import retry_save as retry\n','\n','def process(value):\n','    return retry(value)\n']
    source['lines']=[dict(line=i+1,text=text) for i,text in enumerate(lines)];source['end']=4
    answer['citations']=[dict(path='app/service.py',start=4,end=4)]
    assert not validate_actor_answer(answer,prompt)


@pytest.mark.parametrize('limit',[8192,3000])
def test_document_intent_reserves_original_doc_without_raising_file_or_token_cap(limit):
    suite,files,_=load_suite();task=next(t for t in suite['tasks'] if t['id']=='stale_document')
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('evaluation','fixture',{p:b for p,b in files.items() if not p.endswith('.yaml')})],stage=3)['snapshot_id']
        model=ArchitectureRules(files['geographer.rules.yaml']);service=QueryService(store,rules=[model]);g=store.graph(sid);counter=TokenCounter()
        evidence,trace=retrieve(service,sid,model,g,files,task,'architecture_documents_paths',counter,limit)
        sources=[r for r in evidence['records'] if r['kind']=='source']
        assert 'guide.md' in {r['path'] for r in sources} and 'app/ui.py' in {r['path'] for r in sources}
        assert len(sources)<=3 and counter.count(evidence)<=limit
        assert trace['service_calls']<=3


def test_opt_in_repair_is_local_and_cumulative_budgeted(tmp_path):
    prompt,good=sample();bad=copy.deepcopy(good);bad['citations'][0].update(start=1,end=1)
    script=tmp_path/'mock_adapter.py';count=tmp_path/'count'
    script.write_text('import json,sys\nfrom pathlib import Path\nq=json.load(sys.stdin)\np=Path('+repr(str(count))+')\nn=int(p.read_text()) if p.exists() else 0\np.write_text(str(n+1))\n'
        +'answer='+repr(good)+' if n else '+repr(bad)+'\n'
        +'print(json.dumps(dict(model="mock",provider_request_id="TEST_ONLY",usage=dict(input_tokens=100,output_tokens=100),answer=answer)))\n',encoding='utf-8')
    config=dict(model='mock',configuration={},provider_spend_cap=.01)
    result=run_model([sys.executable,str(script)],config,prompt,TokenCounter(),16384,1024,max_repairs=1)
    assert len(result['attempts'])==2 and not result['validation_issues']
    assert result['cumulative_local_tokens']<=16384 and result['cumulative_provider_tokens']<=16384
    assert result['attempts'][0]['validation_issues'][0]['code']=='CALL_SITE_CITATION'


@pytest.mark.parametrize('reason',['missing_document','remaining_budget'])
def test_repair_never_reexecutes_when_retrieval_or_remaining_budget_blocks_it(tmp_path,reason):
    prompt,answer=sample(stale=reason=='missing_document',documents=reason!='missing_document')
    if reason=='remaining_budget':answer['citations'][0].update(start=1,end=1)
    marker=tmp_path/'calls';script=tmp_path/'mock_adapter.py'
    response=dict(model='mock',provider_request_id='TEST_ONLY',usage=dict(input_tokens=15000 if reason=='remaining_budget' else 100,output_tokens=100),answer=answer)
    script.write_text('import json,sys\nfrom pathlib import Path\njson.load(sys.stdin)\np=Path('+repr(str(marker))+')\np.write_text((p.read_text() if p.exists() else "")+"1")\nprint('+repr(json.dumps(response))+')\n',encoding='utf-8')
    result=run_model([sys.executable,str(script)],dict(model='mock',configuration={},provider_spend_cap=.01),prompt,TokenCounter(),16384,1024,max_repairs=1)
    assert marker.read_text()=='1'
    if reason=='missing_document':assert len(result['attempts'])==1 and any(not p['retryable'] for p in result['validation_issues'])
    else:assert len(result['attempts'])==2 and result['status']=='budget_rejected'


def test_mcp_tool_descriptions_explain_actual_evidence_workflow():
    import asyncio
    from mcp import types
    from geographer.server import create_server
    with SnapshotStore() as store:
        server=create_server(QueryService(store),wire_version='1.1')
        tools=asyncio.run(server._mcp_server.request_handlers[types.ListToolsRequest](types.ListToolsRequest(method='tools/list'))).root.tools
        by_name={t.name:t.description for t in tools}
        assert len(tools)==7 and 'fragment_ids' in by_name['search_entities']
        assert 'start_line' in by_name['get_entity_content'] and 'call expression' in by_name['get_entity_content']
        assert 'qualified names' in by_name['get_architecture_context']
