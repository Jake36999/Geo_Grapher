"""Read-only paper MCP transport smoke test (run with the pinned project Python)."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT=Path(__file__).resolve().parents[1]


async def check(executable,database):
    params=StdioServerParameters(command=executable,args=[str(ROOT/'pipeline/mcp_doc_graph.py')],
        env={**os.environ,'GEOGRAPHER_DOC_GRAPH_DB':str(database),'GEOGRAPHER_DOC_ALLOW_ANNOTATIONS':'0'})
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            listing=await session.list_tools()
            assert len(listing.tools)==10 and all(t.outputSchema for t in listing.tools)
            async def call(name,args):
                result=await session.call_tool(name,args)
                assert not result.isError and result.structuredContent is not None and not result.content,(name,result)
                return result.structuredContent
            status=await call('get_corpus_status',{})
            assert status['read_model_current'] and not status['server']['sources_changed_since_start']
            search=await call('search_documents',{'query':'retrieval augmented generation','limit':3})
            assert search['results'],'Expected fixture topic missing from real corpus'
            title=search['results'][0]['id']
            claims=await call('get_document',{'title':title,'detail':'claims','claim_limit':1})
            if claims['claims']:await call('get_claim',{'title':title,'claim_id':claims['claims'][0]['content_handle'],'max_chars':200})
            await call('get_annotations',{'title':title})
            outline=await call('get_outline',{'title':title})
            await call('get_section',{'title':title,'section_id':outline['sections'][0]['id'],'max_chars':200})
            await call('get_concept',{'name':'knowledge graph'})
            await call('find_by_concept',{'concept':'knowledge graphs','limit':3})
            await call('get_related',{'title':title,'limit':3})
            stale=await session.call_tool('get_document',{'title':title,'expected_revision':'old-revision'})
            assert stale.isError and stale.structuredContent['error']['code']=='STALE_CORPUS'
            invalid=await session.call_tool('get_related',{'title':title,'limit':-1})
            assert invalid.isError and invalid.structuredContent['error']['code']=='INVALID_REQUEST'
            return dict(executable=executable,tools=10,structured_only=True,all_operations_passed=True,invalid_limit_rejected=True)


async def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--python',action='append',dest='executables')
    ap.add_argument('--database',type=Path,default=ROOT/'pipeline/work/doc_graph.db')
    ap.add_argument('--output',type=Path,default=ROOT/'output/paper-audit/mcp-transport.json')
    args=ap.parse_args();results=[]
    for executable in args.executables or [sys.executable]:results.append(await check(executable,args.database.resolve()))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))


if __name__=='__main__':asyncio.run(main())
