"""Disposable integration fixture. Never opens the user's project catalog."""
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.graph_server import create_graph_http
from geographer.source import Repository
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

with tempfile.TemporaryDirectory(prefix='geographer-merge-qa-',ignore_cleanup_errors=True) as directory:
    base=Path(directory);catalog=GraphCatalog(base/'catalog'/'catalog.sqlite')
    for name in ('Alpha','Beta'):
        root=base/name;root.mkdir()
        (root/'app.py').write_text('def helper():\n    """Project local helper."""\n    return 1\n\ndef entry():\n    return helper()\n',encoding='utf-8')
        (root/'README.md').write_text(name+' graph research documentation.',encoding='utf-8')
        catalog.import_project(root,Repository.from_directory(root,name),label=name)
    graph_ids=[g['graph_id'] for g in catalog.graphs()]
    catalog.add_bridge(graph_ids[0],'root',graph_ids[1],'root','reference','Synthetic QA reference, not a code dependency',[{'source':'test fixture'}])
    router=GraphRouter(catalog);app=create_graph_http(router,port=8775)
    async def advance(request):
        row=next(g for g in catalog.graphs() if g['label']=='Alpha')
        root=Path(row['root_path']);(root/'README.md').write_text('Advanced fixture generation.',encoding='utf-8')
        result=catalog.import_project(root,Repository.from_directory(root,'Alpha'),label='Alpha')
        return JSONResponse(result)
    app.router.routes.insert(0,Route('/__qa/advance',advance,methods=['POST']))
    try:uvicorn.run(app,host='127.0.0.1',port=8775,log_level='warning')
    finally:router.close();catalog.close()
