import copy
import json
from pathlib import Path

import pytest

from geographer.analysis import DEFAULT_FILTER
from geographer.model import canonical
from geographer.pipeline import ingest
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.tokens import TokenCounter
from geographer.rules import ArchitectureRules


@pytest.fixture
def service():
    store=SnapshotStore()
    report=ingest(store,[Repository('repo','revision',{'lib.py':b'def _a(): return 1\ndef _b(): return _a()\ndef run(): return _b()\ndef same(): return 1\n',
         'ui.py':b'from lib import run\ndef display(): return run()\n','notes.md':b'run and display\n'})],stage=2)
    svc=QueryService(store,secret=b'x'*32)
    yield svc,report['snapshot_id']
    store.close()


def base(sid,limit=8192):
    return dict(schema_version='1.0',request_id='test-request',snapshot_id=sid,
                budget=dict(limit_tokens=limit,tokenizer='o200k_base',allow_byte_fallback=False))


def eid(svc,sid,name):
    return next(e.entity_id for e in svc._context(sid)['g'].entities.values() if e.qualified_name==name)


def valid(svc,operation,result,limit=8192):
    assert 'error' not in result,result
    svc.wire.validate(operation,'response',result)
    assert TokenCounter(result['budget']['tokenizer']).count(result)<=limit
    assert result['budget']['used_tokens']<=limit
    ids={n['id'] for n in result['data']['nodes']}
    assert all(r['source'] in ids and r['target'] in ids for r in result['data']['relationships']+result['data']['witnesses'])


def test_all_seven_queries_and_evidence_continuation(service):
    svc,sid=service
    search=svc.query('search_entities',{**base(sid),'query':'run','mode':'lexical','repo_ids':[],'kinds':['function'],'limit':20,'cursor':None})
    valid(svc,'search_entities',search)
    focus=eid(svc,sid,'lib.py.run')
    context_request={**base(sid),'focus_id':focus,'grouping':{'mode':'atomic'},'context_radius':1,'filter':copy.deepcopy(DEFAULT_FILTER),'pins':[],
                     'qi':{'enabled':False,'max_diameter':2},'cursor':None}
    architecture=svc.query('get_architecture_context',context_request)
    valid(svc,'get_architecture_context',architecture)
    assert architecture['data']['relationships']
    relation=architecture['data']['relationships'][0]
    inspection={**base(sid),'view_id':relation['view_id'],'projection_id':relation['id'],'relationship_id':None,
                'evidence_page_size':20,'evidence_cursor':None,'page_size':20,'cursor':relation['witness_cursor']}
    inspected=svc.query('inspect_relationship_witnesses',inspection)
    valid(svc,'inspect_relationship_witnesses',inspected)
    assert inspected['data']['witnesses']
    assert inspected['data']['evidence_handles']
    content=svc.query('get_entity_content',{**base(sid),'entity_id':focus,'content_kind':'source','start_line':None,'end_line':None,'cursor':None})
    valid(svc,'get_entity_content',content)
    assert 'def run' in ''.join(c['text'] for c in content['data']['chunks'])
    impact=svc.query('find_dependants',{**base(sid),'entity_id':focus,'direction':'incoming','filter':copy.deepcopy(DEFAULT_FILTER),
                                      'max_depth':8,'max_results':100,'cursor':None})
    valid(svc,'find_dependants',impact)
    assert any(n['qualified_name']=='ui.py.display' for n in impact['data']['nodes'])
    assert all(w['evidence_next_cursor'] is not None for w in impact['data']['witnesses'])
    for w in impact['data']['witnesses'][:1]:
        expanded=svc.query('inspect_relationship_witnesses',{**base(sid),'view_id':impact['data']['view_id'],'projection_id':None,'relationship_id':w['id'],
            'evidence_page_size':20,'evidence_cursor':w['evidence_next_cursor'],'page_size':20,'cursor':None})
        valid(svc,'inspect_relationship_witnesses',expanded)
        assert expanded['data']['evidence_handles']
    similar=svc.query('find_similar_code',{**base(sid),'entity_id':eid(svc,sid,'lib.py._a'),'mode':'exact_normalized_ast','repo_ids':[],'limit':20,'cursor':None})
    valid(svc,'find_similar_code',similar)
    assert similar['data']['matches']
    rule=ArchitectureRules(b'''version: "1.0"
world_policy: open
components:
  - id: ui
    selectors: [{repo_id: repo, path_glob: "ui.py"}]
  - id: library
    selectors: [{repo_id: repo, path_glob: "lib.py"}]
rules:
  - {id: ui_library, type: require, source: ui, target: library, rationale: "Use library"}
''')
    svc.rules[rule.digest]=rule
    checked=svc.query('check_architecture',{**base(sid),'model_digest':rule.digest,'scope_id':svc._context(sid)['tree'].root,
           'filter':copy.deepcopy(DEFAULT_FILTER),'include_satisfied':True,'page_size':100,'cursor':None})
    valid(svc,'check_architecture',checked)
    assert any(f['status']=='match' for f in checked['data']['findings'])


def test_cursor_resume_tamper_scope_and_budget_changes(service):
    svc,sid=service
    req={**base(sid),'query':'lib','mode':'lexical','repo_ids':[],'kinds':[],'limit':1,'cursor':None}
    first=svc.query('search_entities',req);valid(svc,'search_entities',first)
    cursor=first['data']['completeness']['next_cursor'];assert cursor
    second=svc.query('search_entities',{**req,'cursor':cursor,'limit':2,'budget':{**req['budget'],'limit_tokens':12000}})
    valid(svc,'search_entities',second,12000)
    assert not {h['node_id'] for h in first['data']['hits']} & {h['node_id'] for h in second['data']['hits']}
    assert svc.query('search_entities',{**req,'query':'different','cursor':cursor})['error']['code']=='INVALID_CURSOR'
    damaged=cursor[:-2]+('aa' if cursor[-2:]!='aa' else 'bb')
    assert svc.query('search_entities',{**req,'cursor':damaged})['error']['code']=='INVALID_CURSOR'


@pytest.mark.parametrize('mutator',[lambda q:q.update(unknown=True),lambda q:q['budget'].update(limit_tokens='8192'),
    lambda q:q.update(limit=True),lambda q:q.update(repo_ids=['a','a']),lambda q:q.update(request_id='界'*100)])
def test_strict_wire_validation(service,mutator):
    svc,sid=service
    req={**base(sid),'query':'run','mode':'lexical','repo_ids':[],'kinds':[],'limit':20,'cursor':None};mutator(req)
    result=svc.query('search_entities',req)
    assert result['error']['code']=='INVALID_REQUEST'


def test_qi_context_and_diameter_certificate(service):
    svc,sid=service
    req={**base(sid),'focus_id':eid(svc,sid,'lib.py.run'),'grouping':{'mode':'atomic'},'context_radius':2,'filter':copy.deepcopy(DEFAULT_FILTER),
         'pins':[],'qi':{'enabled':True,'max_diameter':2},'cursor':None}
    result=svc.query('get_architecture_context',req);valid(svc,'get_architecture_context',result)
    qi=result['data']['qi'];assert qi['A']==qi['B']+1
    assert qi['B']<=2 and qi['directed_reachability_preserved'] is False
    assert svc.read_handle(qi['membership_handle'])['groups']


def test_budget_tiny_and_byte_fallback(service,tmp_path):
    svc,sid=service
    req={**base(sid,256),'query':'lib','mode':'lexical','repo_ids':[],'kinds':[],'limit':20,'cursor':None}
    result=svc.query('search_entities',req)
    assert result['error']['code']=='BUDGET_TOO_SMALL'
    assert result['error']['minimum_tokens']>256
    svc.token_directory=tmp_path
    req['budget'].update(limit_tokens=8192,allow_byte_fallback=True)
    result=svc.query('search_entities',req)
    assert 'error' not in result,result
    assert result['budget']['guarantee']=='byte_bound'
    assert len(canonical(result).encode())<=8192


@pytest.mark.parametrize('encoding',['o200k_base','cl100k_base'])
def test_adversarial_budgets_always_count_full_envelope_and_close_endpoints(service,encoding):
    svc,sid=service
    focus=eid(svc,sid,'lib.py.run')
    for limit in [256,512,768,1024,1536,2048,4096,8192]:
        q={**base(sid,limit),'focus_id':focus,'grouping':{'mode':'atomic'},'context_radius':2,
           'filter':copy.deepcopy(DEFAULT_FILTER),'pins':[],'qi':{'enabled':False,'max_diameter':2},'cursor':None}
        q['budget']['tokenizer']=encoding
        response=svc.query('get_architecture_context',q)
        if 'error' in response:assert response['error']['code']=='BUDGET_TOO_SMALL'
        else:valid(svc,'get_architecture_context',response,limit)


@pytest.mark.parametrize('version',['1.0','1.1'])
def test_many_evidence_records_resume_cumulatively_without_duplicates(version):
    from dataclasses import replace
    from geographer.extract import PythonExtractor
    from geographer.analysis import materialize_view
    repo=Repository('r','v',{'a.py':b'def f(): pass\nf()\n'})
    extractor=PythonExtractor([repo]);g=extractor.extract();original=next(iter(g.evidence.values()))
    for i in range(11):g.evidence['evidence:extra'+str(i)]=replace(original,evidence_id='evidence:extra'+str(i))
    with SnapshotStore() as store:
        sid=store.begin([repo],{'stage':3});store.write_graph(sid,g,extractor.failures)
        vid,_=materialize_view(store,sid,g,{'mode':'atomic'});store.publish(sid)
        svc=QueryService(store,secret=b'x'*32)
        rid=next(iter(g.relationships))
        request={**base(sid),'view_id':vid,'projection_id':None,'relationship_id':rid,'evidence_page_size':2,
                 'evidence_cursor':None,'page_size':1,'cursor':None}
        request['schema_version']=version
        def validate(response):
            if version=='1.0':valid(svc,'inspect_relationship_witnesses',response)
            else:
                assert 'data' in response,response
                svc.wire11.validate('inspect_relationship_witnesses','response',response)
                assert TokenCounter().count(response)<=8192
                nodes={n['id'] for n in response['data']['nodes']}
                assert all(w['source'] in nodes and w['target'] in nodes for w in response['data']['witnesses'])
        first=svc.query('inspect_relationship_witnesses',request);validate(first)
        cursor=first['data']['witnesses'][0]['evidence_next_cursor'];seen=set()
        for _ in range(10):
            assert cursor
            response=svc.query('inspect_relationship_witnesses',{**request,'evidence_cursor':cursor})
            validate(response)
            ids={e['id'] for e in response['data']['evidence_handles']}
            assert ids and not ids&seen;seen|=ids
            cursor=response['data']['witnesses'][0]['evidence_next_cursor']
            if cursor is None:break
        assert len(seen)==12


def test_runtime_not_collected_is_not_silently_reported_as_absence(service):
    svc,sid=service
    filters={**copy.deepcopy(DEFAULT_FILTER),'families':['runtime'],'resolution_statuses':['observed'],
             'runtime_window':{'start':'2026-11-06T10:00:00Z','end':'2026-11-06T11:00:00Z','environment':'test'}}
    result=svc.query('find_dependants',{**base(sid),'entity_id':eid(svc,sid,'lib.py.run'),'direction':'incoming','filter':filters,'max_depth':5,'max_results':20,'cursor':None})
    assert result['error']['code']=='NOT_FOUND' and 'telemetry' in result['error']['message']
