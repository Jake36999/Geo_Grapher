"""Offline regressions derived from the second recorded model round."""
import copy
import json
import sys
from pathlib import Path
import pytest
import jsonschema

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation.harness import load_suite,model_prompt
from evaluation.grounding import validate_actor_answer
from evaluation.transport_schema import compile_transport_schema


def prompt_and_answer():
    suite,files,_=load_suite();task=next(t for t in suite['tasks'] if t['id']=='stale_document')
    evidence=dict(scope=dict(snapshot_id='fixture',filter='exact_static_calls',grouping='atomic',model_digest='rules',runtime_collection=None),
        records=[dict(kind='source',path=p,start=1,end=len(b.decode().splitlines()),text=b.decode()) for p,b in files.items() if p in {'app/ui.py','app/service.py','guide.md'}])
    prompt=model_prompt(task,evidence,sorted({f for t in suite['tasks'] for f in t['oracle']['facts']}))
    answer=dict(status='answer',facts=['document:stale','immediate_callee:app/service.py.process','basis:source'],
        citations=[dict(path='guide.md',start=6,end=9),dict(path='app/ui.py',start=7,end=7)],
        paths=[['app/ui.py.submit','app/service.py.process']],scope=evidence['scope'],explanation='UNIT TEST, not model output')
    return prompt,answer


def test_public_provenance_is_required_even_for_minimal_answers():
    prompt,answer=prompt_and_answer();answer['facts'].remove('basis:source')
    assert any(i['code']=='MISSING_PROVENANCE' for i in validate_actor_answer(answer,prompt))
    assert prompt['answer_contract']['required_answer_facts']==['basis:source']
    assert 'basis:source_control_flow' not in prompt['shared_label_vocabulary']


def test_wrong_citation_subject_is_repairable_file_field_error():
    prompt,answer=prompt_and_answer();answer['citations'][1]['path']='app/ui.py.submit'
    assert any(i['code']=='CITATION_FILE_PATH' and i['retryable'] for i in validate_actor_answer(answer,prompt))


def test_public_anchor_contract_blocks_unrequested_extra_paths():
    prompt,answer=prompt_and_answer()
    answer['paths'].append(['app/service.py.process','app/ui.py.bypass'])
    assert any(i['code']=='EXTRA_PATH' for i in validate_actor_answer(answer,prompt))
    wire=compile_transport_schema(prompt)['response_format']['json_schema']['schema']
    assert wire['properties']['paths']['maxItems']==1
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(answer,wire)


def test_document_anchor_is_derived_from_heading_and_paragraph_not_oracle():
    prompt,_=prompt_and_answer();doc=next(r for r in prompt['evidence']['records'] if r['path']=='guide.md')
    assert dict(start=6,end=9,heading='Historical note — deliberately stale') in doc['section_citation_anchors']
    assert doc['section_anchors_complete']
    _,answer=prompt_and_answer();answer['citations'][0]['start']=8
    assert any(i['code']=='DOCUMENT_SECTION_CONTEXT' for i in validate_actor_answer(answer,prompt))


def test_transport_removes_uniqueitems_only_and_preserves_full_local_rule():
    prompt,answer=prompt_and_answer();before=copy.deepcopy(prompt)
    compiled=compile_transport_schema(prompt)
    assert prompt==before
    wire=compiled['response_format']['json_schema']['schema']
    assert 'uniqueItems' not in wire['properties']['facts']
    assert wire['properties']['facts']['maxItems']==30
    assert compiled['removed_constraints']==[dict(pointer='/properties/facts/uniqueItems',keyword='uniqueItems',value=True)]
    assert compiled['full_specialized_schema']['properties']['facts']['uniqueItems'] is True
    jsonschema.validate(answer,wire)
    answer['facts'].append('basis:source')
    jsonschema.validate(answer,wire)  # transport omission is explicit
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(answer,prompt['answer_schema'])


@pytest.mark.parametrize('fault',['prose_facts','citation_subject','file_path','unknown_source'])
def test_evidence_enums_stop_structurally_valid_wrong_values(fault):
    prompt,answer=prompt_and_answer();compiled=compile_transport_schema(prompt)
    if fault=='prose_facts':answer['facts']=['The document is stale.']
    elif fault=='citation_subject':answer['citations'][1]['path']='app/ui.py.submit'
    elif fault=='file_path':answer['paths'][0][0]='app/ui.py'
    elif fault=='unknown_source':answer['citations'][0]['path']='missing.md'
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(answer,compiled['response_format']['json_schema']['schema'])


def test_schema_keyword_walk_does_not_strip_property_names_or_enum_data():
    prompt,_=prompt_and_answer()
    prompt['answer_schema']['properties']['uniqueItems']={'type':'object','properties':{'uniqueItems':{'type':'boolean'}},'enum':[{'uniqueItems':True}]}
    wire=compile_transport_schema(prompt)['response_format']['json_schema']['schema']
    assert 'uniqueItems' in wire['properties']
    assert 'uniqueItems' in wire['properties']['uniqueItems']['properties']
    assert wire['properties']['uniqueItems']['enum']==[{'uniqueItems':True}]
    with pytest.raises(ValueError):compile_transport_schema(prompt,('required',))


def test_actual_saved_round_had_document_in_all_stale_graph_inputs():
    # Fixed historical inputs, not new provider calls. This guards the erroneous
    # review diagnosis without changing historical answers or grading thresholds.
    root=Path(__file__).resolve().parents[1]/'output/phase5/mcp-remediation-20261107'
    if not (root/'handoff/requests.jsonl').exists():pytest.skip('Local historical model artifacts unavailable')
    requests={r['eval_id']:r for r in map(json.loads,(root/'handoff/requests.jsonl').read_text(encoding='utf-8').splitlines())}
    for label in ('70b','300b','500b'):
        result_path=root/'results'/label/'results.jsonl'
        if not result_path.exists():pytest.skip('Local historical results unavailable')
        row=next(r for r in map(json.loads,result_path.read_text(encoding='utf-8').splitlines()) if r['eval_id']=='0/stale_document/architecture_documents_paths')
        request=requests[row['eval_id']]
        assert row['prompt_sha256']==request['prompt_sha256']
        assert any(r.get('kind')=='source' and r.get('path')=='guide.md' for r in request['prompt']['evidence']['records'])
