"""Disposable real-store browser service. Cleanup endpoint exists only in this harness."""
import json,os
from pathlib import Path
import uvicorn
from starlette.responses import JSONResponse
from starlette.routing import Route
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.graph_server import create_graph_http

root=Path(os.environ.get('QA_REAL_ROOT','output/phase67-gates/wave4/application-r1')).resolve()
port=int(os.environ.get('QA_REAL_PORT','8786'))
catalog=GraphCatalog(root/'catalog.sqlite')
router=GraphRouter(catalog)
baseline={r[0] for r in catalog.connection.execute('SELECT graph_id FROM graphs')}
proposals={r[0] for r in catalog.connection.execute('SELECT proposal_id FROM bridge_proposals')}
app=create_graph_http(router,port=port,browse_roots=[root/'browse'])

async def cleanup(request):
    # Only rows created during this run in the disposable copy are removed.
    with catalog.lock:
        for (pid,) in catalog.connection.execute('SELECT proposal_id FROM bridge_proposals').fetchall():
            if pid not in proposals:catalog.connection.execute('DELETE FROM bridge_proposals WHERE proposal_id=?',(pid,))
        catalog.connection.commit()
    remaining=[r[0] for r in catalog.connection.execute('SELECT graph_id FROM graphs')]
    out={'extra_graphs':sorted(set(remaining)-baseline),'baseline_preserved':baseline<=set(remaining)}
    (root/'cleanup.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    return JSONResponse(out)

app.router.routes.insert(0,Route('/__qa/cleanup',cleanup,methods=['POST']))
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=port,log_level='warning')
