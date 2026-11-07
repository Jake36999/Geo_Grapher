"""Run with installed `python -I`: exercise both runtime CLI entry points."""
import json,subprocess,sys,tempfile
from pathlib import Path
import geographer
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.service import QueryService
from geographer.analysis import DEFAULT_FILTER
from geographer.model import digest
from geographer.tokens import TokenCounter
from geographer.resources import resource_root

def main():
    with tempfile.TemporaryDirectory(prefix='geographer-wheel-runtime-') as directory:
        root=Path(directory);source=root/'app.py';source.write_bytes(b'def target(): return 1\ndef run(): return target()\nrun()\n')
        database=root/'runtime.sqlite';trace=root/'calls.jsonl'
        with SnapshotStore(database) as store:
            base=ingest(store,[Repository('r','rev',{'app.py':source.read_bytes()})],stage=3)['snapshot_id'];before=digest(store.export(base))
        command=[sys.executable,'-I','-m','geographer','record-trace','--database',str(database),'--snapshot-id',base,'--repo-root','r='+str(root),'--environment','installed','--output',str(trace),'--',sys.executable,'-I',str(source)]
        captured=subprocess.run(command,shell=False,capture_output=True,text=True);assert captured.returncode==0,captured.stdout+captured.stderr
        imported=subprocess.run([sys.executable,'-I','-m','geographer','ingest-trace','--database',str(database),'--snapshot-id',base,'--trace',str(trace)],shell=False,capture_output=True,text=True)
        assert imported.returncode==0,imported.stdout+imported.stderr;report=json.loads(imported.stdout);sid=report['snapshot_id']
        with SnapshotStore(database) as store:
            assert before==digest(store.export(base)) and not store.validate(sid)
            assert report['mapped_call_count']==2 and report['quarantined_call_count']==0
            service=QueryService(store);focus=next(e.entity_id for e in service._context(sid)['g'].entities.values() if e.qualified_name=='app.py.run')
            q=dict(schema_version='1.1',request_id='installed-runtime',snapshot_id=sid,budget=dict(limit_tokens=8192,tokenizer='o200k_base',allow_byte_fallback=False),
                focus_id=focus,grouping={'mode':'atomic'},context_radius=2,filter={**DEFAULT_FILTER,'families':['runtime'],'resolution_statuses':['observed'],
                'runtime_window':{**report['window'],'environment':'installed'}},pins=[],qi={'enabled':False,'max_diameter':2},cursor=None)
            response=service.query('get_architecture_context',q);assert 'data' in response,response
            assert response['data']['relationships'] and TokenCounter().count(response)<=8192
            assert (resource_root()/'contracts/v1.1/geographer.trace.schema.json').is_file()
            assert (resource_root()/'contracts/v1.1/RUNTIME_ADDENDUM.md').is_file()
            print(json.dumps(dict(package=geographer.__file__,status='passed',mapped_calls=report['mapped_call_count'],base_unchanged=True,tokens=TokenCounter().count(response))))
if __name__=='__main__':main()
