"""Run with an installed environment's `python -I` to verify wheel resources."""
import json
from pathlib import Path
import geographer
from starlette.testclient import TestClient
from geographer.source import Repository
from geographer.pipeline import ingest
from geographer.store import SnapshotStore
from geographer.service import QueryService
from geographer.server import create_http_app
from geographer.resources import resource_root
from geographer.tokens import TokenCounter

def main():
    rules='version: "1.0"\nworld_policy: open\ncomponents:\n  - id: ui\n    selectors: [{repo_id: r, path_glob: "ui.py"}]\n  - id: core\n    selectors: [{repo_id: r, path_glob: "core.py"}]\nrules: []\n'
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'ui.py':b'from core import f\ndef run(): return f()\n','core.py':b'def f(): return 1\n'})],stage=3)['snapshot_id']
        service=QueryService(store);g=service._context(sid)['g'];focus=next(e.entity_id for e in g.entities.values() if e.qualified_name=='ui.py.run')
        with TestClient(create_http_app(service),base_url='http://127.0.0.1:8765') as client:
            activated=client.post('/api/workspace/rules',json={'snapshot_id':sid,'text':rules});assert activated.status_code==200,activated.text
            annotation=client.post('/api/workspace/annotation',json={'snapshot_id':sid,'entity_id':focus,'text':'Installed review smoke'});assert annotation.status_code==200,annotation.text
            request=dict(schema_version='1.1',request_id='wheel-smoke',snapshot_id=sid,budget=dict(limit_tokens=32768,tokenizer='o200k_base',allow_byte_fallback=False),
                entity_id=focus,content_kind='source',context_mode='source-context-v1',context_radius=1,start_line=None,end_line=None,cursor=None,
                include_investigation=True,overlay_id=annotation.json()['overlay_id'])
            response=client.post('/api/v1.1/get_entity_content',json=request);assert response.status_code==200,response.text
            data=response.json();assert data['data']['investigation']['overlay']['records'][0]['text']=='Installed review smoke'
            assert data['data']['source_context']['focal_complete'] and TokenCounter().count(data)<=32768
            assert not store.validate(sid)
            root=resource_root();assert (root/'contracts/v1.1/WORKSPACE_ADDENDUM.md').is_file()
            assert client.get('/').status_code==200
            print(json.dumps(dict(package=geographer.__file__,resources=str(root),status='passed',schema_version=data['schema_version'],tokens=TokenCounter().count(data))))
if __name__=='__main__':main()
