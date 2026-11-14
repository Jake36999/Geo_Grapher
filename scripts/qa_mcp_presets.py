"""Exercise every preset tool through an exact installed wheel, without a model."""
import argparse,asyncio,json,os,sqlite3,tempfile
from contextlib import closing
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED={
 'papers':{'list_graphs','paper_search_documents','paper_get_document','paper_find_by_concept','paper_get_related','paper_get_section'},
 'code':{'list_graphs','search_entities','get_architecture_context','find_dependants','get_entity_content','check_architecture'},
 'lead':{'list_graphs','search_entities','get_architecture_context','get_entity_content','analyze_cross_graphs','compile_task_packet'},
 'cross':{'list_graphs','federated_search','list_bridges','analyze_cross_graphs','search_entities','get_entity_content'}}

def _paper_fixture(path):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE read_documents(id INTEGER PRIMARY KEY,title TEXT,authors TEXT,year INTEGER,venue TEXT,doi TEXT,abstract_summary TEXT,
      page_count INTEGER,file_path TEXT,primary_source_id INTEGER,source_count INTEGER,claim_count INTEGER,metadata_json TEXT NOT NULL);
    CREATE TABLE read_claims(id INTEGER PRIMARY KEY,section_id INTEGER,text TEXT,claim_type TEXT,doc_id INTEGER,source_ids_json TEXT);
    CREATE TABLE read_concepts(id INTEGER PRIMARY KEY,canonical_name TEXT,aliases TEXT,definition TEXT,concept_type TEXT,def_doc_id INTEGER,quality TEXT,original_ids_json TEXT);
    CREATE TABLE read_doc_concepts(doc_id INTEGER NOT NULL,concept_id INTEGER NOT NULL,edge_type TEXT NOT NULL,PRIMARY KEY(doc_id,concept_id,edge_type));
    CREATE TABLE sections(id INTEGER PRIMARY KEY,doc_id INTEGER,heading TEXT,section_type TEXT,position INTEGER,text TEXT,word_count INTEGER);
    CREATE TABLE corpus_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    INSERT INTO corpus_metadata VALUES('revision','rev-1');
    INSERT INTO read_documents VALUES(1,'Knowledge graphs','[]',2020,NULL,'10.1234/kg.2020',NULL,1,'a.pdf',1,1,1,'{"source_document_ids":[1]}');
    INSERT INTO read_documents VALUES(2,'Unrelated','[]',2021,NULL,NULL,NULL,1,'b.pdf',2,1,0,'{"source_document_ids":[2]}');
    INSERT INTO sections VALUES(5,1,'Entity linking','body',1,'...',1);
    INSERT INTO read_claims VALUES(3,5,'Knowledge graphs improve recall.','finding',1,'[1]');
    INSERT INTO read_concepts VALUES(1,'knowledge graph','["knowledge graphs"]','',NULL,1,'ok','[1]');
    INSERT INTO read_concepts VALUES(2,'entity linking','[]','',NULL,1,'ok','[2]');
    INSERT INTO read_concepts VALUES(3,'transformer','[]','',NULL,2,'ok','[3]');
    INSERT INTO read_doc_concepts VALUES(1,1,'defines');
    INSERT INTO read_doc_concepts VALUES(1,2,'mentions');
    INSERT INTO read_doc_concepts VALUES(2,3,'defines');
    """)
    con.commit(); con.close()


def make_fixture(base):
    """Small no-model CI catalog; real-store QA remains a separate gate."""
    from geographer.graph_catalog import GraphCatalog
    from geographer.source import Repository
    catalog_path=base/'catalog'/'catalog.sqlite'
    with closing(GraphCatalog(catalog_path)) as catalog:
        for label in ('librarian-v2','ToolSet','ai-research-papers'):
            root=base/label;root.mkdir()
            (root/'effort.py').write_text('def of():\n    """Graph research effort."""\n    return 1\n\ndef graph():\n    return of()\n',encoding='utf-8')
            row=catalog.import_project(root,Repository.from_directory(root,label),label=label)
            if label=='ai-research-papers':
                db=base/'papers.sqlite';_paper_fixture(db);catalog.attach_papers(row['graph_id'],db)
    return catalog_path

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
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path);p.add_argument('--wheel',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--max-chars',type=int,default=7500);a=p.parse_args()
    if a.out.exists():raise SystemExit('Use a new result path; preserve first attempts')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='geo-preset-gate-') as tmp:
        if a.catalog is None:a.catalog=make_fixture(Path(tmp))
        raise SystemExit(asyncio.run(run(a)))

if __name__=='__main__':main()
