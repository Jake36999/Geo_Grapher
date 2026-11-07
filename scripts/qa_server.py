"""Isolated real extraction/query service for browser acceptance tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.pipeline import ingest
from geographer.server import serve
from geographer.recording import record_command
from geographer.trace import read_artifacts,ingest_trace
import sys

def main():
    root=Path('output/qa');root.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix='browser-',dir=root) as directory:
        db=Path(directory)/'fixture.sqlite'
        with SnapshotStore(db) as store:
            for version in (1,2):
                sources={'core/logic.py':f'def transform(value):\n    return value + {version}\n'.encode(),
                    'ui/runner.py':('from core.logic import transform\ndef run(data):\n'+''.join('    result = transform(data)\n' for _ in range(24))+'    return result\n').encode(),
                    'api/entry.py':b'from ui.runner import run\ndef handle(data): return run(data)\n',
                    'docs/guide.md':b'# Pipeline\nThe run function uses transform.\n',
                    'tests/test_logic.py':b'from core.logic import transform\ndef test_transform(): return transform(2)\n',
                    'ui/tests/test_runner.py':b'from ui.runner import run\ndef test_runner(): return run(1)\n',
                    'bad/broken.py':b'def broken(:\n',
                    'unknown.py':b'factory().dispatch()\n'}
                sources.update({f'extras/item{i:02}.py':f'def helper_{i:02}(): return {i}\n'.encode() for i in range(14)})
                result=ingest(store,[Repository('qa',f'fixture-v{version}',sources)],stage=3)
            materialized=Path(directory)/'recorded-source';materialized.mkdir()
            for rel,raw in sources.items():
                path=materialized/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            parent=result['snapshot_id']
            for environment,runs in [('qa-observed-a',3),('qa-observed-b',2)]:
                output=Path(directory)/(environment+'.jsonl')
                command=[sys.executable,'-c',f'import sys; sys.path.insert(0,{str(materialized.resolve())!r}); from ui.runner import run; [run(2) for _ in range({runs})]']
                capture=record_command(store,parent,{'qa':materialized},environment,output,command)
                if capture['exit_code']!=0:raise RuntimeError('QA observation command failed')
                raw,manifest=read_artifacts(output);parent=ingest_trace(store,parent,raw,manifest)['snapshot_id']
        rules=Path(directory)/'geographer.rules.yaml'
        rules.write_text('''version: "1.0"
world_policy: open
components:
  - id: ui
    selectors:
      - repo_id: qa
        path_glob: "ui/**"
  - id: core
    selectors:
      - repo_id: qa
        path_glob: "core/**"
rules:
  - id: no_ui_core
    type: forbid
    source: ui
    target: core
    rationale: "Fixture boundary violation: UI must use the API."
''',encoding='utf-8')
        serve(db,'http',[rules],port=8771)

if __name__=='__main__':main()
