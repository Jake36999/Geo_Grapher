"""Positive observations, source mapping, immutable lineage and publication failures."""
import copy,hashlib,json
import sys
import pytest
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore,PublicationError
from geographer.trace import ingest_trace,source_manifest,collections

def artifact(store,sid,rows,*,start='2026-11-06T10:00:00Z',end='2026-11-06T10:01:00Z',environment='test'):
    raw=('\n'.join(json.dumps(r) for r in rows)+'\n').encode()
    return raw,dict(format_version='python-call-trace-v1',environment=environment,window=dict(start=start,end=end),sources=source_manifest(store,sid),repo_roots={},
        recorder=dict(name='fixture',version='1',backend='imported'),source_match=True,trace_sha256=hashlib.sha256(raw).hexdigest(),
        coverage=dict(complete=True,truncated=False,process_scope='fixture process',thread_scope='main only',async_scope='first activation only',limitations=['Positive observations only']))

def record(**overrides):
    return dict(caller_path='a.py',caller_qualname='run',caller_line=2,callee_path='b.py',callee_qualname='target',call_count=7,p95_ms=2.5,**overrides)

@pytest.fixture
def base():
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'a.py':b'from b import target\ndef run(): return target()\n','b.py':b'def target(): return 1\n'})],stage=3)['snapshot_id']
        yield store,sid

def test_import_is_a_validated_child_with_recoverable_counts_and_immutable_base(base):
    store,sid=base;before=store.export(sid);raw,manifest=artifact(store,sid,[record()]);result=ingest_trace(store,sid,raw,manifest)
    child=result['snapshot_id'];assert child!=sid and result['mapped_call_count']==7 and result['mapped_records']==1
    assert not store.validate(child) and store.export(sid)==before
    graph=store.graph(child);observed=[r for r in graph.relationships.values() if r.family=='runtime'];assert len(observed)==1
    assert observed[0].resolution_status=='observed' and observed[0].weight_unit=='call_count' and observed[0].weight==7
    evidence=next(e for e in graph.evidence.values() if e.category=='dynamic_observed')
    assert json.loads(evidence.details_json)['record']['p95_ms']==2.5 and evidence.trace_ref
    assert ingest_trace(store,sid,raw,manifest)['snapshot_id']==child
    assert ingest_trace(store,child,raw,manifest)['already_present']

def test_failed_publication_rolls_back_the_entire_child(base,monkeypatch):
    store,sid=base;raw,manifest=artifact(store,sid,[record()]);before=store.export(sid)
    monkeypatch.setattr(store,'validate',lambda _:['injected publication failure'])
    with pytest.raises(PublicationError):ingest_trace(store,sid,raw,manifest)
    assert store.connection.execute('SELECT count(*) FROM snapshot_sets').fetchone()[0]==1
    assert store.export(sid)==before

def test_quarantined_records_reconcile_counts_without_guessing_or_reading_paths(base):
    store,sid=base;row=record();row['callee_path']='../../outside.py';raw,manifest=artifact(store,sid,[row])
    report=ingest_trace(store,sid,raw,manifest)
    assert report['mapped_records']==0 and report['quarantined_records']==1 and report['quarantined_call_count']==7
    assert report['quarantine_reason_counts']=={'unsafe_or_outside_root_callee':1}
    assert report['input_call_count']==report['mapped_call_count']+report['quarantined_call_count']

def test_source_mismatch_duplicate_rows_and_overlapping_collections_are_rejected(base):
    store,sid=base;raw,manifest=artifact(store,sid,[record()]);wrong=copy.deepcopy(manifest);wrong['sources']['r']['revision']='other'
    with pytest.raises(ValueError,match='source revisions'):ingest_trace(store,sid,raw,wrong)
    duplicate,md=artifact(store,sid,[record(),record()])
    with pytest.raises(ValueError,match='Duplicate'):ingest_trace(store,sid,duplicate,md)
    child=ingest_trace(store,sid,raw,manifest)['snapshot_id']
    row=record();row['call_count']=8;changed,mc=artifact(store,child,[row])
    with pytest.raises(ValueError,match='Overlapping'):ingest_trace(store,child,changed,mc)
    later,ml=artifact(store,child,[record()],start='2026-11-06T10:01:00Z',end='2026-11-06T10:02:00Z')
    grandchild=ingest_trace(store,child,later,ml)['snapshot_id'];assert len(collections(store,grandchild))==2

def test_multiple_repo_ambiguity_is_quarantined_until_namespaces_are_explicit():
    with SnapshotStore() as store:
        files={'a.py':b'def run(): return target()\n','b.py':b'def target(): return 1\n'}
        sid=ingest(store,[Repository('one','r',files),Repository('two','r',files)],stage=3)['snapshot_id']
        row=record();row['caller_line']=1;raw,manifest=artifact(store,sid,[row]);result=ingest_trace(store,sid,raw,manifest)
        assert result['quarantine_reason_counts']=={'ambiguous_caller':1}
        row.update(caller_repo_id='one',callee_repo_id='two');raw,manifest=artifact(store,sid,[row]);result=ingest_trace(store,sid,raw,manifest)
        assert result['mapped_records']==1

def test_nested_decorated_and_module_sources_map_without_rewriting_static_claims():
    with SnapshotStore() as store:
        files={'a.py':b'def deco(f): return f\n@deco\ndef outer():\n def inner(): return 1\n return inner()\nouter()\n'}
        sid=ingest(store,[Repository('r','rev',files)],stage=3)['snapshot_id']
        rows=[dict(caller_path='a.py',caller_qualname='<module>',caller_line=6,callee_path='a.py',callee_qualname='outer',callee_definition_line=2,call_count=1),
              dict(caller_path='a.py',caller_qualname='outer',caller_line=5,callee_path='a.py',callee_qualname='outer.<locals>.inner',callee_definition_line=4,call_count=1)]
        raw,manifest=artifact(store,sid,rows);result=ingest_trace(store,sid,raw,manifest);assert result['mapped_records']==2

def test_real_recorder_deduplicates_generator_and_coroutine_resumes(tmp_path):
    from geographer.recording import record_command
    from geographer.trace import read_artifacts
    code='''import asyncio
def target(): return 1
def generator():
 yield target()
 yield target()
async def child():
 await asyncio.sleep(0)
 return target()
async def run():
 await child()
list(generator())
asyncio.run(run())
'''
    script=tmp_path/'main.py';script.write_text(code,encoding='utf-8')
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'main.py':script.read_bytes()})],stage=3)['snapshot_id']
        result=record_command(store,sid,{'r':tmp_path},'fixture',tmp_path/'calls.jsonl',[sys.executable,str(script)])
        assert result['exit_code']==0 and result['source_match']
        raw,manifest=read_artifacts(result['trace']);rows=[json.loads(line) for line in raw.splitlines()]
        assert sum(r['call_count'] for r in rows if r['callee_qualname']=='generator')==1
        assert sum(r['call_count'] for r in rows if r['callee_qualname']=='child')==1
        assert sum(r['call_count'] for r in rows if r['callee_qualname']=='target')==3
        assert manifest['statistics']['resume_segments_ignored']>=3
        assert all('p95_ms' not in r for r in rows)
        observed=ingest_trace(store,sid,raw,manifest);assert observed['mapped_records']>=4

def test_recorder_preserves_failed_exit_and_refuses_changed_source(tmp_path):
    from geographer.recording import record_command
    script=tmp_path/'fail.py';script.write_text('raise SystemExit(7)\n')
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'fail.py':script.read_bytes()})],stage=3)['snapshot_id']
        result=record_command(store,sid,{'r':tmp_path},'fixture',tmp_path/'failed.jsonl',[sys.executable,str(script)])
        assert result['exit_code']==7 and not result['coverage']['complete']
        script.write_text('raise SystemExit(0)\n')
        mismatch=record_command(store,sid,{'r':tmp_path},'fixture',tmp_path/'mismatch.jsonl',[sys.executable,str(script)])
        assert mismatch['exit_code']==2 and not mismatch['source_match']

def test_recorder_limits_are_explicit_and_pytest_wrapper_executes_real_tests(tmp_path):
    from geographer.recording import record_command
    from geographer.trace import read_artifacts
    code='def target(): return 1\ndef test_target():\n for _ in range(20): assert target()==1\n'
    test=tmp_path/'test_calls.py';test.write_text(code)
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'test_calls.py':test.read_bytes()})],stage=3)['snapshot_id']
        recorded=record_command(store,sid,{'r':tmp_path},'pytest',tmp_path/'pytest.jsonl',[sys.executable,'-m','pytest','-q','--rootdir',str(tmp_path),str(test)],max_seconds=20)
        raw,manifest=read_artifacts(recorded['trace']);assert recorded['exit_code']==0
        assert sum(json.loads(line)['call_count'] for line in raw.splitlines() if json.loads(line)['callee_qualname']=='target')==20
        assert ingest_trace(store,sid,raw,manifest)['mapped_call_count']>=20
        limited=record_command(store,sid,{'r':tmp_path},'pytest',tmp_path/'limited.jsonl',[sys.executable,'-m','pytest','-q','--rootdir',str(tmp_path),str(test)],max_seconds=20,max_events=3)
        assert limited['exit_code']==0 and limited['coverage']['truncated'] and 'logical_call_limit' in limited['coverage']['limitations']

@pytest.mark.parametrize('version',['1.0','1.1'])
def test_collection_window_queries_and_bootstrap_expose_real_observed_weights(base,version):
    from geographer.analysis import DEFAULT_FILTER
    from geographer.service import QueryService
    from geographer.server import create_http_app
    from geographer.tokens import TokenCounter
    from starlette.testclient import TestClient
    store,sid=base;raw,manifest=artifact(store,sid,[record()]);result=ingest_trace(store,sid,raw,manifest);child=result['snapshot_id']
    svc=QueryService(store);focus=next(e.entity_id for e in svc._context(child)['g'].entities.values() if e.qualified_name=='a.py.run')
    filters={**DEFAULT_FILTER,'families':['runtime'],'resolution_statuses':['observed'],'runtime_window':{**result['window'],'environment':'test'}}
    q=dict(schema_version=version,request_id='runtime',snapshot_id=child,budget=dict(limit_tokens=32768,tokenizer='o200k_base',allow_byte_fallback=False),
        focus_id=focus,grouping={'mode':'atomic'},context_radius=2,filter=filters,pins=[],qi={'enabled':False,'max_diameter':2},cursor=None)
    response=svc.query('get_architecture_context',q);assert 'data' in response,response
    assert response['data']['relationships'] and all(r['family']=='runtime' and r['aggregated_weight']==7 and r['weight_unit']=='call_count' for r in response['data']['relationships'])
    assert TokenCounter().count(response)<=32768
    invalid=svc.query('get_architecture_context',{**q,'filter':{**filters,'runtime_window':{**filters['runtime_window'],'environment':'missing'}}})
    assert invalid['error']['code']=='NOT_FOUND'
    with TestClient(create_http_app(svc),base_url='http://127.0.0.1:8765') as c:
        bootstrap=c.get('/api/v1/bootstrap').json();snapshot=next(s for s in bootstrap['snapshots'] if s['snapshot_id']==child)
        collection=snapshot['runtime_collections'][0];assert snapshot['telemetry_available'] and collection['mapped_call_count']==7
        assert c.get('/api/v1/handles/'+collection['report_handle']).json()['quarantine_complete']

def test_actual_monkeypatch_observation_can_disagree_with_static_exact_without_promotion(tmp_path):
    from geographer.recording import record_command
    from geographer.trace import read_artifacts
    files={'a.py':b'import b\ndef run(): return b.target()\n','b.py':b'def target(): return 1\n','c.py':b'def alternate(): return 2\n'}
    for path,raw in files.items():(tmp_path/path).write_bytes(raw)
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',files)],stage=3)['snapshot_id'];before=store.graph(sid)
        program=f'import sys; sys.path.insert(0,{str(tmp_path)!r}); import a,b,c; b.target=c.alternate; a.run()'
        recorded=record_command(store,sid,{'r':tmp_path},'patched',tmp_path/'patch.jsonl',[sys.executable,'-c',program])
        raw,manifest=read_artifacts(recorded['trace']);report=ingest_trace(store,sid,raw,manifest)
        assert report['static_comparison_record_counts'].get('differs_from_static_exact')==1
        after=store.graph(report['snapshot_id'])
        assert all(after.relationships[rid]==r for rid,r in before.relationships.items())
        assert any(json.loads(e.details_json).get('static_comparison',{}).get('outcome')=='differs_from_static_exact' for e in after.evidence.values())

def test_recording_thread_scope_hook_restore_and_hard_exit_are_honest(tmp_path):
    import threading
    from geographer.trace_runner import Recorder
    from geographer.recording import record_command
    from geographer.trace import read_artifacts
    prior=lambda *args:None;original=sys.getprofile();old_thread=threading.getprofile()
    try:
        sys.setprofile(prior);threading.setprofile(prior)
        recorder=Recorder(dict(repo_roots={'r':str(tmp_path)},max_seconds=5,max_events=100,max_bytes=8192))
        assert recorder.run(['-c','pass'])==0
        assert sys.getprofile() is prior and threading.getprofile() is prior
    finally:sys.setprofile(original);threading.setprofile(old_thread)
    files={'main.py':b'import threading\ndef target(): return 1\ndef work():\n for _ in range(3): target()\nt=threading.Thread(target=work)\nt.start()\nt.join()\n'}
    (tmp_path/'main.py').write_bytes(files['main.py'])
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',files)],stage=3)['snapshot_id']
        recorded=record_command(store,sid,{'r':tmp_path},'threads',tmp_path/'threads.jsonl',[sys.executable,str(tmp_path/'main.py')])
        raw,manifest=read_artifacts(recorded['trace']);assert recorded['exit_code']==0
        assert sum(json.loads(line)['call_count'] for line in raw.splitlines() if json.loads(line)['callee_qualname']=='target')==3
        hard=record_command(store,sid,{'r':tmp_path},'hard',tmp_path/'hard.jsonl',[sys.executable,'-c','import os; os._exit(9)'])
        assert hard['exit_code']==9 and not hard['source_match'] and not hard['coverage']['complete']

def test_windows_root_case_and_alias_duplicates_are_explicit(base):
    store,sid=base;row=record();row.update(caller_path='C:\\Repo\\A.py',callee_path='c:\\repo\\B.PY')
    raw,manifest=artifact(store,sid,[row]);manifest['repo_roots']={'r':'C:/repo'}
    assert ingest_trace(store,sid,raw,manifest)['mapped_records']==1
    other=record();other.update(caller_qualname='a.py.run',callee_qualname='b.py.target')
    raw,manifest=artifact(store,sid,[record(),other])
    with pytest.raises(ValueError,match='normalized call site'):ingest_trace(store,sid,raw,manifest)

def test_opt_in_pytest_plugin_records_and_imports_real_test_calls(tmp_path):
    import subprocess
    from geographer.trace import read_artifacts
    test=tmp_path/'test_plugin.py';test.write_bytes(b'def target(): return 2\ndef test_target(): assert target()==2\n')
    database=tmp_path/'plugin.sqlite';output=tmp_path/'plugin.jsonl'
    with SnapshotStore(database) as store:sid=ingest(store,[Repository('r','rev',{'test_plugin.py':test.read_bytes()})],stage=3)['snapshot_id']
    command=[sys.executable,'-m','pytest','-p','geographer.pytest_trace','--geographer-trace-output',str(output),'--geographer-trace-database',str(database),
        '--geographer-trace-snapshot',sid,'--geographer-trace-root','r='+str(tmp_path),'--rootdir',str(tmp_path),'-q',str(test)]
    run= subprocess.run(command,shell=False,capture_output=True,text=True)
    assert run.returncode==0,run.stdout+run.stderr
    raw,manifest=read_artifacts(output);assert manifest['recorder']['name']=='geographer-pytest'
    assert sum(json.loads(line)['call_count'] for line in raw.splitlines() if json.loads(line)['callee_qualname']=='target')==1
    with SnapshotStore(database) as store:assert ingest_trace(store,sid,raw,manifest)['mapped_call_count']>=1

def test_collection_discovery_and_report_are_shared_mcp_resources(base):
    from urllib.parse import quote
    from starlette.testclient import TestClient
    from geographer.server import create_http_app
    from geographer.service import QueryService
    from test_stage3_transports import sse_json
    store,sid=base;raw,manifest=artifact(store,sid,[record()]);result=ingest_trace(store,sid,raw,manifest);child=result['snapshot_id'];svc=QueryService(store)
    with TestClient(create_http_app(svc),base_url='http://127.0.0.1:8765') as client:
        endpoint='/mcp/v1.1';headers={'accept':'application/json, text/event-stream'}
        initialized=client.post(endpoint,headers=headers,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'trace-test','version':'1'}}})
        headers.update({'mcp-session-id':initialized.headers['mcp-session-id'],'mcp-protocol-version':'2025-11-25'})
        client.post(endpoint,headers=headers,json={'jsonrpc':'2.0','method':'notifications/initialized'})
        templates=sse_json(client.post(endpoint,headers=headers,json={'jsonrpc':'2.0','id':2,'method':'resources/templates/list'}))['result']['resourceTemplates']
        assert any(t['uriTemplate']=='geographer://runtime-collections/{snapshot_id}' for t in templates)
        listed=sse_json(client.post(endpoint,headers=headers,json={'jsonrpc':'2.0','id':3,'method':'resources/read','params':{'uri':'geographer://runtime-collections/'+quote(child,safe='')}}))
        collection=json.loads(listed['result']['contents'][0]['text'])[0]
        assert collection['mapped_call_count']==7 and collection['environment']=='test' and 'quarantine' not in collection
        recovered=svc.read_handle(collection['report_handle']);assert recovered['input_call_count']==7

def test_recorder_byte_time_and_profile_replacement_limits_are_disclosed(tmp_path):
    from geographer.recording import record_command
    from geographer.trace import read_artifacts
    file=tmp_path/'loop.py';file.write_bytes(b'import time\ndef target(): return 1\nfor _ in range(30): target(); time.sleep(.001)\n')
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'loop.py':file.read_bytes()})],stage=3)['snapshot_id']
        with pytest.raises(ValueError,match='overwrite indexed'):record_command(store,sid,{'r':tmp_path},'bad',file,[sys.executable,str(file)])
        timed=record_command(store,sid,{'r':tmp_path},'time',tmp_path/'timed.jsonl',[sys.executable,str(file)],max_seconds=.01)
        assert timed['exit_code']==0 and 'capture_duration_limit' in timed['coverage']['limitations']
        replaced=record_command(store,sid,{'r':tmp_path},'replacement',tmp_path/'replaced.jsonl',[sys.executable,'-c','import sys; sys.setprofile(None)'])
        assert replaced['exit_code']==0 and 'profile_hook_replaced' in replaced['coverage']['limitations']
        bounded=record_command(store,sid,{'r':tmp_path},'bytes',tmp_path/'bounded.jsonl',[sys.executable,str(file)],max_bytes=1024)
        raw,manifest=read_artifacts(bounded['trace']);assert len(raw)<=1024
        assert bounded['exit_code']==0

def test_zero_mapped_collection_is_queryable_but_never_proves_negative_coverage(base):
    from geographer.analysis import DEFAULT_FILTER
    from geographer.service import QueryService
    store,sid=base;row=record();row['callee_path']='missing.py';raw,manifest=artifact(store,sid,[row]);report=ingest_trace(store,sid,raw,manifest)
    svc=QueryService(store);g=svc._context(report['snapshot_id'])['g'];focus=next(e.entity_id for e in g.entities.values() if e.kind=='repository')
    q=dict(schema_version='1.1',request_id='zero',snapshot_id=report['snapshot_id'],budget=dict(limit_tokens=8192,tokenizer='o200k_base',allow_byte_fallback=False),
        focus_id=focus,grouping={'mode':'kind','kind':'file'},context_radius=1,filter={**DEFAULT_FILTER,'families':['runtime'],'resolution_statuses':['observed'],'runtime_window':{**report['window'],'environment':'test'}},pins=[],qi={'enabled':False,'max_diameter':2},cursor=None)
    response=svc.query('get_architecture_context',q);assert 'data' in response,response
    assert response['data']['relationships']==[]
    assert any('non-observation is not absence' in s for s in response['data']['coverage']['limitations'])
