"""No-model smoke of the optional semantic extra through an exact wheel."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(args):
    with sqlite3.connect(args.catalog.resolve().as_uri()+'?mode=ro',uri=True) as c:
        gid,path,sid=c.execute('SELECT graph_id,code_database,snapshot_id FROM graphs WHERE label=?',(args.graph,)).fetchone()
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as c:
        eid,name=c.execute("SELECT entity_id,qualified_name FROM entities WHERE snapshot_id=? AND kind='function' ORDER BY entity_id LIMIT 1",(sid,)).fetchone()
    env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
    launch=['--python',str(args.python.resolve()),'--refresh-package','geo-grapher','--from',str(args.wheel.resolve())+'[semantic]',
        'geographer','serve-graphs','--catalog',str(args.catalog.resolve()),'--transport','stdio','--tools','code',
        '--graph-id',gid,'--max-result-chars','7500','--semantic-model',args.model,'--semantic-cache',str(args.cache.resolve())]
    params=StdioServerParameters(command='uvx',args=launch,env=env)
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as session:
            await session.initialize();tools=(await session.list_tools()).tools
            assert len(json.dumps(next(t.inputSchema for t in tools if t.name=='search_entities')))<=1200
            metadata={'geographer/recovery':dict(episode_id='installed-wheel-smoke',question=name,mode='defer',remaining_steps=3)}
            result=await session.call_tool('search_entities',dict(graph_id=gid,query=name),meta=metadata)
            assert not result.isError,result.structuredContent
            body=result.structuredContent
            assert body['entities'][0]['entity_id']==eid and body['result']['data']['semantic']['namespace']
            assert all(h['match'] in {'lexical','semantic','both'} for h in body['result']['data']['hits'])
            assert len(json.dumps(body,ensure_ascii=False))<=7500
            opened=await session.call_tool('get_entity_content',dict(graph_id=gid,entity_id=eid),meta=metadata)
            assert not opened.isError,opened.structuredContent
            assert opened.structuredContent['coverage']
            assert len(json.dumps(opened.structuredContent,ensure_ascii=False))<=7500
            value=dict(wheel_sha256=hashlib.sha256(args.wheel.read_bytes()).hexdigest(),launch=launch,search=True,content=True,
                minimal_schema=True,canonical_ids=True,semantic_namespace=body['result']['data']['semantic']['namespace'],within_cap=True,paid_calls=0)
    with args.out.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
    print(json.dumps(value))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('wheel','catalog','cache','python','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--graph',default='librarian-v2');p.add_argument('--model',required=True);args=p.parse_args()
    if args.out.exists():raise SystemExit('Preserve first optional-extra smoke result')
    asyncio.run(run(args))

if __name__=='__main__':main()
