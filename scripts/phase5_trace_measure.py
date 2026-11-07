"""Persistent P5.4 evidence from explicitly executed, owned Python fixture code."""
from __future__ import annotations
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.model import digest
from geographer.incremental import build_digest
from geographer.recording import record_command
from geographer.trace import read_artifacts,ingest_trace
from geographer.service import QueryService
from geographer.analysis import DEFAULT_FILTER
from geographer.tokens import TokenCounter

def main():
    output=ROOT/'output/phase5';fixture=output/'p54-fixture';fixture.mkdir(parents=True,exist_ok=True)
    files={'core.py':b'''import asyncio
def step(value): return value+1
def generate():
 for value in range(4): yield step(value)
async def helper():
 await asyncio.sleep(0)
 return step(1)
def thread_work():
 for value in range(3): step(value)
''','main.py':b'''import asyncio,threading
from core import generate,helper,thread_work
def run():
 list(generate())
 asyncio.run(helper())
 worker=threading.Thread(target=thread_work)
 worker.start()
 worker.join()
run()
'''}
    for name,raw in files.items():(fixture/name).write_bytes(raw)
    with SnapshotStore(output/'p54-runtime.sqlite') as store:
        prior=[r['snapshot_id'] for r in store.connection.execute("SELECT snapshot_id,config_json FROM snapshot_sets WHERE status='complete'") if json.loads(r['config_json']).get('implementation_digest')==build_digest() and not json.loads(r['config_json']).get('parent_snapshot_id')]
        base=prior[-1] if prior else ingest(store,[Repository('runtime-fixture','fixture-v1',files)],stage=3)['snapshot_id']
        before=digest(store.export(base));started=time.perf_counter()
        recorded=record_command(store,base,{'runtime-fixture':fixture},'p54-actual-capture',output/'p54-calls.jsonl',[sys.executable,str(fixture/'main.py')])
        assert recorded['exit_code']==0,recorded
        raw,manifest=read_artifacts(recorded['trace']);result=ingest_trace(store,base,raw,manifest);sid=result['snapshot_id']
        assert before==digest(store.export(base));assert not store.validate(sid)
        service=QueryService(store);ctx=service._context(sid);focus=next(e.entity_id for e in ctx['g'].entities.values() if e.qualified_name=='main.py.run')
        q=dict(schema_version='1.1',request_id='runtime-measure',snapshot_id=sid,budget=dict(limit_tokens=16384,tokenizer='o200k_base',allow_byte_fallback=False),
            focus_id=focus,grouping={'mode':'atomic'},context_radius=2,filter={**DEFAULT_FILTER,'families':['runtime'],'resolution_statuses':['observed'],
                'runtime_window':{**result['window'],'environment':result['environment']}},pins=[],qi={'enabled':False,'max_diameter':2},cursor=None)
        response=service.query('get_architecture_context',q);assert 'data' in response,response
        (output/'p54-context.json').write_text(json.dumps(response,indent=2),encoding='utf-8')
        result.update(implementation_digest=build_digest(),capture=recorded,base_unchanged=True,publication_validation=store.validate(sid),
            elapsed_seconds=time.perf_counter()-started,response_nodes=len(response['data']['nodes']),response_relationships=len(response['data']['relationships']),
            response_full_tokens=TokenCounter().count(response),workload='Owned fixture: generator, coroutine, thread; no ToolSet application workload was executed')
        (output/'p54-runtime-metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
def toolset():
    from phase5_measure import TOOLSET,COMMIT
    output=ROOT/'output/phase5';repository=Repository.from_git(TOOLSET,'ToolSet',COMMIT,('aletheia_toolchain','local_tool_assist_mcp'))
    with SnapshotStore(output/'p54-toolset.sqlite') as store:
        prior=[r['snapshot_id'] for r in store.connection.execute("SELECT snapshot_id,config_json FROM snapshot_sets WHERE status='complete'") if json.loads(r['config_json']).get('implementation_digest')==build_digest()]
        sid=prior[-1] if prior else ingest(store,[repository],stage=3)['snapshot_id']
        result=dict(snapshot_id=sid,implementation_digest=build_digest(),commit=COMMIT,source_digest=repository.content_digest,
            counts={table:store.connection.execute('SELECT count(*) FROM '+table+' WHERE snapshot_id=?',(sid,)).fetchone()[0] for table in ('entities','relationships','evidence')},
            relationship_statuses=dict(store.connection.execute('SELECT resolution_status,count(*) FROM relationships WHERE snapshot_id=? GROUP BY resolution_status',(sid,))),
            publication_validation=store.validate(sid),runtime_workload_executed=False)
        (output/'p54-toolset-metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':toolset() if '--toolset' in sys.argv else main()
