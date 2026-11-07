"""Independent graph stores, scoped retrieval, overlap decisions and display hosting."""
import asyncio,json,os,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest
from starlette.testclient import TestClient
from geographer.graph_catalog import GraphCatalog,CollisionReview
from geographer.graph_router import GraphRouter
from geographer.graph_server import create_graph_http
from geographer.source import Repository
from geographer.tokens import TokenCounter


def import_graph(catalog,root,label,text='Research graph methods.'):
    root.mkdir(exist_ok=True,parents=True);(root/'README.md').write_text(text,encoding='utf-8')
    return catalog.import_project(root,Repository.from_directory(root,label),label=label)


@pytest.fixture
def hub(tmp_path):
    catalog=GraphCatalog(tmp_path/'catalog'/'catalog.sqlite');first=import_graph(catalog,tmp_path/'a','A')
    router=GraphRouter(catalog)
    yield catalog,router,first
    router.close();catalog.close()


def request(graph,query='research'):
    return dict(schema_version='1.1',request_id='test',snapshot_id=graph['ingestion']['snapshot_id'],
        budget=dict(limit_tokens=8192,tokenizer='o200k_base',allow_byte_fallback=False),
        query=query,mode='documentation',repo_ids=[],kinds=[],limit=5,cursor=None)


def test_second_graph_does_not_change_first_scores_or_aliases(hub,tmp_path):
    catalog,router,first=hub;gid=first['graph_id'];req=request(first)
    before=router.query(gid,'search_entities',req)
    second=import_graph(catalog,tmp_path/'b','B','Research graph methods. '*50)
    after=router.query(gid,'search_entities',req)
    assert before==after
    a=catalog.graph(gid);b=catalog.graph(second['graph_id'])
    assert a['code_database']!=b['code_database']
    assert before['graph_id']==gid and before['routing_budget']['used_tokens']==TokenCounter().count(before)<=8192
    wrong=router.query(second['graph_id'],'search_entities',req)
    assert 'error' in wrong['result']


@pytest.mark.parametrize('graph_id',[None,'','all','g_000000000000000000000000'])
def test_graph_required_and_no_all_fallback(hub,graph_id):
    _,router,first=hub
    with pytest.raises(ValueError):router.query(graph_id,'search_entities',request(first))


def test_nested_root_review_and_explicit_child_module(hub,tmp_path):
    catalog,_,first=hub;child=tmp_path/'a'/'component';child.mkdir();(child/'README.md').write_text('Component notes')
    repo=Repository.from_directory(child,'component');plan=catalog.plan_root(child)
    assert plan['collisions'][0]['relation']=='inside_existing_root'
    with pytest.raises(CollisionReview):catalog.import_project(child,repo)
    assert len(catalog.graphs())==1
    with pytest.raises(ValueError):catalog.import_project(child,repo,decision='keep_separate',expected_plan='stale')
    second=catalog.import_project(child,repo,decision='child_module',expected_plan=plan['plan_id'])
    assert len(catalog.graphs())==2
    bridges=catalog.bridges([first['graph_id'],second['graph_id']]);assert len(bridges)==1 and bridges[0]['kind']=='child_module'
    assert catalog.bridges([first['graph_id']])==[]


def test_parent_root_collision_keep_separate(hub,tmp_path):
    catalog,_,first=hub;root=tmp_path
    plan=catalog.plan_root(root);assert plan['collisions'][0]['relation']=='contains_existing_root'
    second=catalog.import_project(root,Repository('parent','r',{'note.md':b'Parent-only source'}),decision='keep_separate')
    assert catalog.bridges([first['graph_id'],second['graph_id']])==[]


def test_identical_reimport_reuses_graph_and_snapshot(hub,tmp_path):
    catalog,_,first=hub
    again=catalog.import_project(tmp_path/'a',Repository.from_directory(tmp_path/'a','A'))
    assert again['graph_id']==first['graph_id'] and again['ingestion']['status']=='reused'
    assert again['ingestion']['snapshot_id']==first['ingestion']['snapshot_id']


def test_explicit_federation_keeps_graph_envelopes_and_token_bound(hub,tmp_path):
    catalog,router,first=hub;second=import_graph(catalog,tmp_path/'b','B')
    result=router.federated_search([first['graph_id'],second['graph_id']],'research',limit_tokens=4096)
    assert result['ranking']=='independent_per_graph_no_global_rank'
    assert result['used_tokens']==TokenCounter().count(result)<=4096
    assert {r['graph_id'] for r in result['results']}|{r['graph_id'] for r in result['omitted']}=={first['graph_id'],second['graph_id']}
    with pytest.raises(ValueError):router.federated_search([],'research')


def test_federation_keeps_healthy_graphs_when_one_store_is_missing(hub,tmp_path):
    catalog,router,first=hub;second=import_graph(catalog,tmp_path/'b','B')
    with catalog.connection:catalog.connection.execute('UPDATE graphs SET code_database=? WHERE graph_id=?',(str(tmp_path/'missing.sqlite'),second['graph_id']))
    result=router.federated_search([first['graph_id'],second['graph_id']],'research',limit_tokens=8192)
    by_graph={r['graph_id']:r for r in result['results']}
    assert 'result' in by_graph[first['graph_id']]
    assert by_graph[second['graph_id']]['error']['code']=='GRAPH_UNAVAILABLE'
    assert result['used_tokens']==TokenCounter().count(result)<=8192


def test_federation_budget_drops_largest_envelope_regardless_of_order(hub,tmp_path,monkeypatch):
    catalog,router,first=hub;second=import_graph(catalog,tmp_path/'b','B')
    small,large=first['graph_id'],second['graph_id']
    envelopes={small:dict(graph_id=small,result=dict(text='small '*200)),large:dict(graph_id=large,result=dict(text='large '*3000))}
    monkeypatch.setattr(router,'query',lambda gid,operation,req:envelopes[gid])
    for order in ([small,large],[large,small]):
        result=router.federated_search(order,'research',limit_tokens=2048)
        assert [o['graph_id'] for o in result['omitted']]==[large]
        assert [r['graph_id'] for r in result['results']]==[small]


def test_catalog_stays_writable_during_ingest_and_rechecks_overlaps(hub,tmp_path,monkeypatch):
    import sqlite3
    import geographer.graph_catalog as module
    catalog,_,_=hub;original=module.ingest;root=tmp_path/'c';inner=root/'inner'
    inner.mkdir(parents=True);(root/'README.md').write_text('Third graph',encoding='utf-8');(inner/'README.md').write_text('Inner',encoding='utf-8')
    def during(store,repos,**kwargs):
        # Another writer must be able to take the catalog write lock mid-ingest.
        other=sqlite3.connect(catalog.path,timeout=0.2,isolation_level=None)
        try:other.execute('BEGIN IMMEDIATE');other.execute('ROLLBACK')
        finally:other.close()
        # Another process registers a nested root; this import's plan is now stale.
        monkeypatch.setattr(module,'ingest',original)
        elsewhere=GraphCatalog(catalog.path)
        try:elsewhere.import_project(inner,Repository.from_directory(inner,'inner'))
        finally:elsewhere.close()
        return original(store,repos,**kwargs)
    monkeypatch.setattr(module,'ingest',during)
    with pytest.raises(CollisionReview):catalog.import_project(root,Repository.from_directory(root,'C'))
    assert catalog.plan_root(root)['existing_graph_id'] is None and catalog.plan_root(root)['requires_review']


def test_decision_made_before_a_concurrent_registration_is_not_reused(hub,tmp_path,monkeypatch):
    import geographer.graph_catalog as module
    catalog,_,_=hub;original=module.ingest;root=tmp_path/'d';first_inner=root/'one';second_inner=root/'two'
    for path in (first_inner,second_inner):path.mkdir(parents=True);(path/'README.md').write_text(path.name,encoding='utf-8')
    catalog.import_project(first_inner,Repository.from_directory(first_inner,'one'))
    plan=catalog.plan_root(root)
    def during(store,repos,**kwargs):
        monkeypatch.setattr(module,'ingest',original)
        elsewhere=GraphCatalog(catalog.path)
        try:elsewhere.import_project(second_inner,Repository.from_directory(second_inner,'two'))
        finally:elsewhere.close()
        return original(store,repos,**kwargs)
    monkeypatch.setattr(module,'ingest',during)
    # keep_separate was reviewed against one nested root; a second appeared mid-ingest.
    with pytest.raises(ValueError,match='changed during ingestion'):
        catalog.import_project(root,Repository.from_directory(root,'D'),decision='keep_separate',expected_plan=plan['plan_id'])
    assert catalog.plan_root(root)['existing_graph_id'] is None


def test_per_graph_paper_ids_and_homonyms_never_share_state(hub,tmp_path):
    from pipeline import stage3_build_db as db
    from pipeline.artifacts import write_json
    import sqlite3
    catalog,router,first=hub;second=import_graph(catalog,tmp_path/'b','B')
    for graph,meaning in [(first,'Electromagnetic field'),(second,'Anthropological field study')]:
        path=tmp_path/(graph['graph_id']+'.papers.sqlite');conn=sqlite3.connect(path);conn.executescript(db.DDL)
        artifact=tmp_path/'paper.json';write_json(artifact,dict(file_path='paper.pdf',metadata=dict(title=meaning,authors=['Author']),sections=[dict(heading='Results',position=0,text=meaning,claims=[dict(text=meaning,claim_type='finding')],concepts=[dict(name='field',definition=meaning,concept_type='term')])]))
        db.load_nodes_file(artifact,conn);conn.commit();conn.close();catalog.attach_papers(graph['graph_id'],path)
        if graph is first:before=router.query(first['graph_id'],'paper_search_documents',{'query':'field'})
    assert router.query(first['graph_id'],'paper_search_documents',{'query':'field'})==before
    def query(index):
        graph=first if index%2==0 else second
        return router.query(graph['graph_id'],'paper_get_concept',{'name':'field'})
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(query,range(12)))
    for i,result in enumerate(results):assert result['result']['matches'][0]['definition']==('Electromagnetic field' if i%2==0 else 'Anthropological field study')
    with pytest.raises(ValueError):catalog.attach_papers(second['graph_id'],catalog.graph(first['graph_id'])['paper_database'])


def test_catalog_http_children_keep_independent_api_paths(hub,tmp_path):
    catalog,router,first=hub;second=import_graph(catalog,tmp_path/'b','B')
    with TestClient(create_graph_http(router),base_url='http://127.0.0.1:8774') as client:
        assert client.get('/collection/').status_code==200
        assert len(client.get('/api/graphs').json()['graphs'])==2
        for graph in (first,second):
            prefix='/graphs/'+graph['graph_id']
            bootstrap=client.get(prefix+'/api/v1/bootstrap');assert bootstrap.status_code==200
            assert len(bootstrap.json()['snapshots'])==1
            result=client.post(prefix+'/api/v1.1/search_entities',json=request(graph))
            assert result.status_code==200 and 'error' not in result.json(),result.text
        assert client.get('/graphs/unknown/api/v1/bootstrap').status_code==404


def test_real_scoped_stdio_and_missing_graph_error(hub):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    catalog,_,first=hub
    async def check():
        params=StdioServerParameters(command=sys.executable,args=['-m','geographer','serve-graphs','--catalog',str(catalog.path),'--transport','stdio'],env={**os.environ,'PYTHONPATH':str(Path('src').resolve())})
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as session:
                await session.initialize();listing=await session.list_tools();assert any(t.name=='list_graphs' for t in listing.tools)
                assert not any(t.name.startswith('paper_') for t in listing.tools)
                await session.list_tools()  # Repeated schema discovery is safe.
                result=await session.call_tool('search_entities',{'graph_id':first['graph_id'],'request':request(first)})
                assert not result.isError and result.structuredContent['graph_id']==first['graph_id'] and not result.content
                invalid=await session.call_tool('search_entities',{'request':request(first)})
                assert invalid.isError and invalid.structuredContent['error']['code']=='INVALID_GRAPH_REQUEST'
    asyncio.run(check())


def test_bridge_decision_persists_without_merging_stores(hub,tmp_path):
    catalog,_,first=hub;second=import_graph(catalog,tmp_path/'b','B')
    bid=catalog.add_bridge(first['graph_id'],'root',second['graph_id'],'root','reference','Explicit reference only',[{'source':'operator review'}])
    other=GraphCatalog(catalog.path)
    try:assert other.bridges([first['graph_id'],second['graph_id']])[0]['bridge_id']==bid
    finally:other.close()
    assert catalog.graph(first['graph_id'])['code_database']!=catalog.graph(second['graph_id'])['code_database']


def test_real_paper_graph_routing_over_stdio(hub,tmp_path):
    import sqlite3
    from pipeline import stage3_build_db as db
    from pipeline.artifacts import write_json
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    catalog,_,first=hub;path=tmp_path/'papers.sqlite';conn=sqlite3.connect(path);conn.executescript(db.DDL)
    artifact=tmp_path/'paper.json';write_json(artifact,dict(file_path='one.pdf',metadata=dict(title='Project specific paper',authors=[]),sections=[dict(heading='Methods',position=0,text='Local field meaning',claims=[],concepts=[dict(name='field',definition='Local meaning',concept_type='term')])]))
    db.load_nodes_file(artifact,conn);conn.commit();conn.close();catalog.attach_papers(first['graph_id'],path)
    async def check():
        params=StdioServerParameters(command=sys.executable,args=['-m','geographer','serve-graphs','--catalog',str(catalog.path),'--transport','stdio'],env={**os.environ,'PYTHONPATH':str(Path('.').resolve())+os.pathsep+str(Path('src').resolve())})
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as session:
                await session.initialize();listing=await session.list_tools();assert any(t.name=='paper_get_concept' for t in listing.tools)
                result=await session.call_tool('paper_get_concept',{'graph_id':first['graph_id'],'request':{'name':'field'}})
                assert not result.isError and result.structuredContent['result']['matches'][0]['definition']=='Local meaning'
    asyncio.run(check())


def test_graph_identity_collision_never_overwrites_an_existing_store(tmp_path,monkeypatch):
    monkeypatch.setattr('geographer.graph_catalog.digest',lambda *args:'0'*64)
    catalog=GraphCatalog(tmp_path/'registry'/'catalog.sqlite')
    try:
        first=import_graph(catalog,tmp_path/'first','First')
        with pytest.raises(ValueError,match='identity collision'):import_graph(catalog,tmp_path/'second','Second')
        assert len(catalog.graphs())==1 and catalog.graph(first['graph_id'])['label']=='First'
    finally:catalog.close()


def test_catalog_never_modifies_an_existing_project_store(hub):
    catalog,_,first=hub
    import sqlite3
    path=catalog.graph(first['graph_id'])['code_database']
    before=sqlite3.connect(path).execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    with pytest.raises(ValueError,match='not a graph catalog'):GraphCatalog(path)
    after=sqlite3.connect(path).execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    assert before==after


def test_misregistered_database_cannot_be_routed_under_another_graph(hub,tmp_path):
    catalog,_,first=hub;second=import_graph(catalog,tmp_path/'b','B')
    # Simulate a damaged/mistaken registry while respecting its UNIQUE paths.
    a=catalog.graph(first['graph_id']);b=catalog.graph(second['graph_id'])
    with catalog.connection:
        catalog.connection.execute('UPDATE graphs SET code_database=? WHERE graph_id=?',(str(tmp_path/'unused.sqlite'),first['graph_id']))
        catalog.connection.execute('UPDATE graphs SET code_database=? WHERE graph_id=?',(a['code_database'],second['graph_id']))
    fresh=GraphRouter(catalog)
    try:
        with pytest.raises(ValueError,match='ownership'):fresh.service(second['graph_id'])
    finally:fresh.close()


def test_one_missing_store_does_not_break_other_graph_discovery(hub,tmp_path):
    catalog,router,first=hub;second=import_graph(catalog,tmp_path/'b','B')
    with catalog.connection:catalog.connection.execute('UPDATE graphs SET code_database=? WHERE graph_id=?',(str(tmp_path/'missing.sqlite'),second['graph_id']))
    rows={r['graph_id']:r for r in router.summary()['graphs']}
    assert rows[first['graph_id']]['availability']=='available'
    assert rows[second['graph_id']]['availability']=='unavailable' and rows[second['graph_id']]['entity_count'] is None


def test_cli_collision_review_precedes_source_traversal(hub,tmp_path,monkeypatch):
    from geographer.cli import main
    catalog,_,_=hub;child=tmp_path/'a'/'component';child.mkdir()
    manifest=tmp_path/'input.json';manifest.write_text(json.dumps(dict(version=1,repositories=[dict(repo_id='child',path=str(child))])))
    monkeypatch.setattr('geographer.project_inputs.load_workspace_manifest',lambda *args:pytest.fail('Source traversal must follow root review'))
    monkeypatch.setattr(sys,'argv',['geographer','ingest-graphs','--catalog',str(catalog.path),'--manifest',str(manifest)])
    with pytest.raises(SystemExit) as exc:main()
    assert exc.value.code==2 and len(catalog.graphs())==1
