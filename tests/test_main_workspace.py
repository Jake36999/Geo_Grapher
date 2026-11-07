"""The main origin owns the viewer without breaking original code clients."""
from starlette.testclient import TestClient
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.graph_server import create_graph_http,create_main_workspace
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.pipeline import ingest


def test_main_root_shared_viewer_retains_original_api_and_legacy_ui(tmp_path):
    root=tmp_path/'project';root.mkdir();(root/'a.py').write_text('def run(): return 1\n',encoding='utf-8')
    catalog=GraphCatalog(tmp_path/'catalog.sqlite')
    imported=catalog.import_project(root,Repository.from_directory(root,'Project'),label='Project')
    router=GraphRouter(catalog)
    try:
        with TestClient(create_main_workspace(router.service(imported['graph_id']),router),base_url='http://127.0.0.1:8765') as client:
            home=client.get('/',follow_redirects=False)
            assert home.status_code==200 and 'name="geographer-workspace" content="integrated"' in home.text
            assert 'name="geographer-primary-graph"' in home.text
            assert client.get('/collection/?debug',follow_redirects=False).headers['location']=='/?debug'
            original=client.get('/api/v1/bootstrap').json()
            assert original['snapshots'][0]['snapshot_id']==imported['ingestion']['snapshot_id']
            assert len(client.get('/api/graphs').json()['graphs'])==1
            assert client.get('/legacy/',follow_redirects=False).headers['location']=='/?graph='+imported['graph_id']
            assert client.get('/graphs/'+imported['graph_id']+'/?debug',follow_redirects=False).headers['location']=='/?graph='+imported['graph_id']+'&debug='
            assert client.get('/graphs/'+imported['graph_id']+'/api/v1/bootstrap').status_code==200
            frames=client.post('/api/graphs/frame',json={'graphs':[{'graph_id':imported['graph_id']}]}).json()
            assert 'frame' in frames['frames'][0]
            for path in ('/mcp','/graph-hub/mcp'):
                response=client.post(path,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'main-origin-test','version':'1'}}},headers={'Accept':'application/json, text/event-stream'})
                assert response.status_code==200,response.text
    finally:router.close();catalog.close()


def test_old_viewer_origin_redirects_without_redirecting_its_api(tmp_path):
    catalog=GraphCatalog(tmp_path/'catalog.sqlite');router=GraphRouter(catalog)
    try:
        with TestClient(create_graph_http(router,port=8774,ui_origin='http://127.0.0.1:8765'),base_url='http://127.0.0.1:8774') as client:
            for path in ('/','/collection/'):
                response=client.get(path,follow_redirects=False)
                assert response.headers['location']=='http://127.0.0.1:8765/'
            assert client.get('/api/graphs').status_code==200
    finally:router.close();catalog.close()


def test_existing_main_store_is_registered_without_reextracting_or_rewriting_ids(tmp_path):
    path=tmp_path/'original.sqlite'
    with SnapshotStore(path) as store:
        sid=ingest(store,[Repository('Original','revision',{'a.py':b'def run(): return 1\n'})],stage=3)['snapshot_id']
        before=store.export(sid)
        catalog=GraphCatalog(tmp_path/'catalog.sqlite');router=GraphRouter(catalog)
        try:
            service=store_service(store)
            with TestClient(create_main_workspace(service,router),base_url='http://127.0.0.1:8765') as client:
                data=client.get('/api/graphs').json()['graphs'];assert len(data)==1
                assert data[0]['label']=='Original' and data[0]['repo_ids']==['Original']
                assert data[0]['graph_kind']=='registered_store'
                assert router.service(data[0]['graph_id']) is service
                assert catalog.register_existing_store(path)==data[0]['graph_id']
                assert store.export(sid)==before
                frames=client.post('/api/graphs/frame',json={'graphs':[{'graph_id':data[0]['graph_id'],'grouping':{'mode':'atomic'},'context_radius':2}]}).json()
                assert 'error' not in frames['frames'][0]
                assert all(n['repo_id'] in {'Original','@workspace'} for n in frames['frames'][0]['frame']['nodes'])
        finally:router.close();catalog.close()
        assert store.connection.execute('SELECT count(*) FROM snapshot_sets').fetchone()[0]==1


def store_service(store):
    from geographer.service import QueryService
    return QueryService(store)
