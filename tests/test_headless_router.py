"""Local graph queries must not load a network transport to read a cursor key."""
import os
from pathlib import Path
import subprocess
import sys


def test_open_graph_service_without_mcp_or_http_transport(tmp_path):
    script = '''
import importlib.abc
from pathlib import Path
import sys
class NoTransport(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'geographer.server' or fullname.split('.')[0] in {'mcp', 'starlette'}:
            raise AssertionError('Headless graph open imported transport: ' + fullname)
sys.meta_path.insert(0, NoTransport())
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.source import Repository
root = Path(sys.argv[1]); project = root / 'project'; project.mkdir()
(project / 'main.py').write_text('def run(): return 1\\n')
catalog = GraphCatalog(root / 'catalog.sqlite')
graph = catalog.import_project(project, Repository.from_directory(project, 'headless'), label='headless')
router = GraphRouter(catalog)
try:
    service = router.service(graph['graph_id'])
    assert service.projects()['snapshots']
finally:
    router.close(); catalog.close()
'''
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'src')}
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
