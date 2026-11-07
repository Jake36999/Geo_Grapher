import asyncio
import copy
import json
from pathlib import Path
import sys
import pytest

from starlette.testclient import TestClient

from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.service import QueryService
from geographer.server import create_http_app


def seed(store):
    return ingest(store,[Repository('r','revision',{'a.py':b'def f(): pass\nf()\n'})],stage=2)['snapshot_id']


def request(sid):
    return dict(schema_version='1.0',request_id='transport-test',snapshot_id=sid,budget=dict(limit_tokens=8192,tokenizer='o200k_base',allow_byte_fallback=False),
                query='f',mode='lexical',repo_ids=[],kinds=['function'],limit=20,cursor=None)


def sse_json(response):
    if response.headers.get('content-type','').startswith('application/json'):return response.json()
    return json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith('data: ')))


@pytest.mark.parametrize('version',['1.0','1.1'])
def test_streamable_http_sse_protocol_and_wire_parity(version):
    with SnapshotStore() as store:
        sid=seed(store);svc=QueryService(store,secret=b'x'*32)
        with TestClient(create_http_app(svc),base_url='http://127.0.0.1:8765') as client:
            endpoint='/mcp' if version=='1.0' else '/mcp/v1.1'
            headers={'accept':'application/json, text/event-stream'}
            initialized=client.post(endpoint,headers=headers,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{
                'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'fixture','version':'1'}}})
            assert initialized.status_code==200,initialized.text
            assert sse_json(initialized)['result']['protocolVersion']=='2025-11-25'
            headers.update({'mcp-session-id':initialized.headers['mcp-session-id'],'mcp-protocol-version':'2025-11-25'})
            client.post(endpoint,headers=headers,json={'jsonrpc':'2.0','method':'notifications/initialized'})
            tools=sse_json(client.post(endpoint,headers=headers,json={'jsonrpc':'2.0','id':2,'method':'tools/list'}))['result']['tools']
            assert len(tools)==7 and all(t['annotations']['readOnlyHint'] for t in tools)
            payload=request(sid)
            payload['schema_version']=version
            called=client.post(endpoint,headers=headers,json={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'search_entities','arguments':payload}})
            result=sse_json(called)['result']
            assert result['content']==[]
            (svc.wire11 if version=='1.1' else svc.wire).validate('search_entities','response',result['structuredContent'])
            api='/api/v1.1' if version=='1.1' else '/api/v1'
            http=client.post(api+'/search_entities',json=payload)
            assert http.status_code==200
            assert http.json()==result['structuredContent']
            assert client.post(api+'/search_entities',json=payload,headers={'host':'hostile.example'}).status_code==421
            if version=='1.1':
                focus=next(e.entity_id for e in svc._context(sid)['g'].entities.values() if e.kind=='function')
                content={k:v for k,v in payload.items() if k in {'schema_version','request_id','snapshot_id','budget'}}
                content.update(entity_id=focus,content_kind='source',context_mode='source-context-v1',context_radius=1,
                    start_line=None,end_line=None,cursor=None,include_investigation=True)
                observed=sse_json(client.post(endpoint,headers=headers,json={'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'get_entity_content','arguments':content}}))['result']
                assert observed['isError'] is False
                assert observed['structuredContent']==client.post(api+'/get_entity_content',json=content).json()
                assert observed['structuredContent']['data']['investigation']['algorithm_version']=='process-evidence-v1'


@pytest.mark.parametrize('version',['1.0','1.1'])
def test_stdio_sdk_round_trip(tmp_path,version):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    database=tmp_path/'stdio.sqlite'
    with SnapshotStore(database) as store:sid=seed(store)
    async def run():
        params=StdioServerParameters(command=sys.executable,args=['-m','geographer','serve','--database',str(database),'--schema-version',version],
            env={'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                initialized=await session.initialize()
                assert initialized.protocolVersion=='2025-11-25'
                tools=await session.list_tools();assert len(tools.tools)==7
                payload=request(sid);payload['schema_version']=version
                result=await session.call_tool('search_entities',payload)
                assert result.isError is False
                assert result.content==[]
                assert result.structuredContent['schema_version']==version
                assert result.structuredContent['data']['hits']
    asyncio.run(run())
