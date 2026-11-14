"""Minimal agent calls use the strict engine without exposing protocol plumbing."""
import asyncio,json,os,sys
from pathlib import Path
import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from test_task_packets import packet_world


def run_mcp(world, check, preset='lead'):
    cat,_,gid,_=world
    async def go():
        params=StdioServerParameters(command=sys.executable,args=['-m','geographer','serve-graphs',
            '--catalog',str(cat.path),'--transport','stdio','--tools',preset,'--graph-id',gid,'--max-result-chars','7500'],
            env={**os.environ,'PYTHONPATH':str(Path('src').resolve())})
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as session:
                await session.initialize();await check(session,gid)
    asyncio.run(go())


def test_three_minimal_calls_and_small_schemas(packet_world):
    async def check(s,gid):
        listing=(await s.list_tools()).tools
        for tool in listing:
            if tool.name in {'search_entities','get_entity_content','get_architecture_context'}:
                assert len(json.dumps(tool.inputSchema))<=1200
                assert 'request' not in tool.inputSchema['properties']
        found=await s.call_tool('search_entities',dict(graph_id=gid,query='f',kinds=['function']))
        assert not found.isError,found.structuredContent
        entity=found.structuredContent['entities'][0]
        assert entity['cite_as'].startswith('code/entity:')
        eid=entity['entity_id']
        content=await s.call_tool('get_entity_content',dict(graph_id=gid,entity_id=eid))
        assert not content.isError,content.structuredContent
        assert 'def f' in json.dumps(content.structuredContent)
        arch=await s.call_tool('get_architecture_context',dict(graph_id=gid,focus_id=eid))
        assert not arch.isError,arch.structuredContent
        for out in (found,content,arch):assert len(json.dumps(out.structuredContent,ensure_ascii=False))<=7500
    run_mcp(packet_world,check)


def test_code_preset_minimal_calls(packet_world):
    async def check(s,gid):
        listing=(await s.list_tools()).tools
        for tool in listing:assert len(json.dumps(tool.inputSchema))<=1200
        found=await s.call_tool('search_entities',dict(graph_id=gid,query='f',kinds=['function']))
        assert not found.isError,found.structuredContent
        eid=found.structuredContent['entities'][0]['entity_id']
        for op,args in [('find_dependants',dict(entity_id=eid)),('check_architecture',{})]:
            out=await s.call_tool(op,dict(graph_id=gid,**args))
            assert not out.isError,out.structuredContent
        assert not (await s.call_tool('list_graphs',{})).isError
    run_mcp(packet_world,check,preset='code')


def test_clamp_errors_and_strict_form(packet_world):
    cat,_,gid,ids=packet_world
    async def check(s,gid):
        out=await s.call_tool('search_entities',dict(graph_id=gid,query='f',profile='tier2_forager',limit_tokens=4096))
        assert not out.isError,out.structuredContent
        assert out.structuredContent['budget_clamped_to']==1800
        bad=await s.call_tool('search_entities',dict(graph_id=gid,query=5))
        assert bad.isError
        error=bad.structuredContent['error']
        assert error['field']=='query' and 'example' in error and len(error['message'])<=400
        mixed=await s.call_tool('search_entities',dict(graph_id=gid,query='f',request={}))
        assert mixed.isError and 'mix' in mixed.structuredContent['error']['message'].lower()
        req=dict(schema_version='1.1',request_id='strict',snapshot_id=cat.graph(gid)['snapshot_id'],
            budget=dict(limit_tokens=4096,tokenizer='o200k_base',allow_byte_fallback=False),
            query='f',mode='lexical',repo_ids=[],kinds=[],limit=5,cursor=None)
        strict=await s.call_tool('search_entities',dict(graph_id=gid,request=req))
        assert not strict.isError,strict.structuredContent
        wrong=await s.call_tool('get_entity_content',dict(graph_id=gid,entity_id='entity:nope'))
        assert wrong.isError and wrong.structuredContent['error']['example']
        recovery=wrong.structuredContent['error']
        assert recovery['choices'] and recovery['example']['entity_id'] in ids.values()
        retry=await s.call_tool('get_entity_content',recovery['example'])
        assert not retry.isError and retry.structuredContent['coverage']
    run_mcp(packet_world,check)


def test_natural_language_search_includes_original_documentation(packet_world,tmp_path):
    from geographer.source import Repository
    from geographer.agent_requests import call_code
    cat,router,_,_=packet_world
    root=tmp_path/'natural';root.mkdir()
    (root/'m.py').write_text('def calculate(x):\n    """Validate the orchard harvest."""\n    return x\n',encoding='utf-8')
    gid=cat.import_project(root,Repository.from_directory(root,'natural'),label='natural')['graph_id']
    out=call_code(router,'search_entities',dict(graph_id=gid,query='orchard harvest'))
    assert out['entities']
    assert any('calculate' in e['qualified_name'] for e in out['entities'])


def test_recovery_context_uses_standard_mcp_metadata_without_larger_tool_schema(packet_world):
    async def check(s,gid):
        metadata={'geographer/recovery':dict(episode_id='metadata-fixture',question='f',mode='defer',remaining_steps=3)}
        out=await s.call_tool('search_entities',dict(graph_id=gid,query='unmatched_xyz'),meta=metadata)
        assert not out.isError,out.structuredContent
        assert out.structuredContent['recovery_pending'][0]['pattern']=='FP1'
        assert out.structuredContent['entities']==[]
        metadata['geographer/recovery']['mode']='auto'
        fixed=await s.call_tool('search_entities',dict(graph_id=gid,query='unmatched_xyz'),meta=metadata)
        assert not fixed.isError,fixed.structuredContent
        assert fixed.structuredContent['recovery_steps_consumed']==1
        assert fixed.structuredContent['entities']
        assert len(json.dumps(fixed.structuredContent,ensure_ascii=False))<=7500
    run_mcp(packet_world,check)
