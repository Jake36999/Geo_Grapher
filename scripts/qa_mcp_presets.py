"""Exercise every preset tool through an exact installed wheel, without a model."""
import argparse,asyncio,json,os,sqlite3
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED={
 'papers':{'list_graphs','paper_search_documents','paper_get_document','paper_find_by_concept','paper_get_related','paper_get_section'},
 'code':{'list_graphs','search_entities','get_architecture_context','find_dependants','get_entity_content','check_architecture'},
 'lead':{'list_graphs','search_entities','get_architecture_context','get_entity_content','analyze_cross_graphs','compile_task_packet'},
 'cross':{'list_graphs','federated_search','list_bridges','analyze_cross_graphs','search_entities','get_entity_content'}}

async def run(a):
    with sqlite3.connect(a.catalog.resolve().as_uri()+'?mode=ro',uri=True) as c:
        c.row_factory=sqlite3.Row;graphs=[dict(r) for r in c.execute('SELECT * FROM graphs')]
    code=next(g for g in graphs if g['label']=='librarian-v2');paper=next(g for g in graphs if g['label']=='ai-research-papers')
    other=next(g for g in graphs if g['label']=='ToolSet')
    with sqlite3.connect(Path(code['code_database']).resolve().as_uri()+'?mode=ro',uri=True) as c:
        eid=c.execute("SELECT entity_id FROM entities WHERE snapshot_id=? AND kind='function' AND rel_path LIKE '%effort.py' ORDER BY CASE WHEN qualified_name LIKE '%.of' THEN 0 ELSE 1 END,entity_id LIMIT 1",(code['snapshot_id'],)).fetchone()[0]
    with sqlite3.connect(Path(paper['paper_database']).resolve().as_uri()+'?mode=ro',uri=True) as c:
        doc=c.execute('SELECT id FROM read_documents ORDER BY id LIMIT 1').fetchone()[0]
        section=c.execute('SELECT id FROM sections WHERE doc_id=? ORDER BY id LIMIT 1',(doc,)).fetchone()
        concept=c.execute('SELECT canonical_name FROM read_concepts ORDER BY id LIMIT 1').fetchone()[0]
    cgid,pgid=code['graph_id'],paper['graph_id'];pair=[cgid,other['graph_id']]
    cases={'list_graphs':{},'search_entities':dict(graph_id=cgid,query='effort'),
        'get_entity_content':dict(graph_id=cgid,entity_id=eid),'get_architecture_context':dict(graph_id=cgid,focus_id=eid),
        'find_dependants':dict(graph_id=cgid,entity_id=eid),'check_architecture':dict(graph_id=cgid),
        'compile_task_packet':dict(graph_id=cgid,anchors=['entity:'+eid],instruction='Describe ports.'),
        'analyze_cross_graphs':dict(graph_ids=pair,mode='clone_candidates'),
        'federated_search':dict(graph_ids=pair,query='graph'),'list_bridges':dict(graph_ids=pair),
        'paper_search_documents':dict(graph_id=pgid,request={'query':'graph'}),
        'paper_get_document':dict(graph_id=pgid,request={'title':f'doc:{doc}'}),
        'paper_get_related':dict(graph_id=pgid,request={'title':f'doc:{doc}'}),
        'paper_get_section':dict(graph_id=pgid,request={'title':f'doc:{doc}',**({'section_id':section[0]} if section else {})}),
        'paper_find_by_concept':dict(graph_id=pgid,request={'concept':concept})}
    results=[]
    for preset,expected in EXPECTED.items():
        env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
        params=StdioServerParameters(command='uvx',args=['--refresh-package','geo-grapher','--from',str(a.wheel.resolve()),
            'geographer','serve-graphs','--catalog',str(a.catalog.resolve()),'--transport','stdio','--tools',preset,
            '--max-result-chars',str(a.max_chars)],env=env)
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as s:
                await s.initialize();tools=(await s.list_tools()).tools
                assert {t.name for t in tools}==expected
                for tool in tools:
                    out=await s.call_tool(tool.name,cases[tool.name]);body=out.structuredContent
                    size=len(json.dumps(body,ensure_ascii=False))
                    result=dict(preset=preset,tool=tool.name,success=not out.isError,characters=size,
                        schema_characters=len(json.dumps(tool.inputSchema)),error=body.get('error') if isinstance(body,dict) else None)
                    results.append(result);a.out.write_text(json.dumps(results,indent=2),encoding='utf-8')
                name='paper_get_document' if preset=='papers' else 'search_entities'
                bad=await s.call_tool(name,{'graph_id':pgid if preset=='papers' else cgid,**({'request':{}} if preset=='papers' else {'query':17})})
                e=bad.structuredContent.get('error',{})
                results.append(dict(preset=preset,tool=name,negative=True,success=bad.isError and bool(e.get('example')) and len(e.get('message',''))<=400,
                    error=e,characters=len(json.dumps(bad.structuredContent,ensure_ascii=False))))
                a.out.write_text(json.dumps(results,indent=2),encoding='utf-8')
    failed=[r for r in results if not r['success'] or r['characters']>a.max_chars]
    print(json.dumps(dict(calls=len(results),failed=failed),indent=2))
    return bool(failed)

def main():
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--wheel',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--max-chars',type=int,default=7500);a=p.parse_args()
    if a.out.exists():raise SystemExit('Use a new result path; preserve first attempts')
    a.out.parent.mkdir(parents=True,exist_ok=True);raise SystemExit(asyncio.run(run(a)))

if __name__=='__main__':main()
