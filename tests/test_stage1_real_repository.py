"""Independent real-source checks; reads a pinned archive, never its working tree."""
import ast
import json
import subprocess
from pathlib import Path

import pytest

from geographer.source import Repository
from geographer.pipeline import ingest
from geographer.store import SnapshotStore

TOOLSET = Path('D:/Aletheia_project/DEV_TOOLS/ToolSet')
COMMIT = 'f8bc1ec4c54884293dace635275e95c685b03371'


@pytest.mark.integration
@pytest.mark.skipif(not (TOOLSET / '.git').exists(), reason='Pinned local ToolSet repository unavailable')
def test_pinned_toolset_stage1(tmp_path):
    before = subprocess.run(['git','-C',str(TOOLSET),'status','--porcelain'],check=True,capture_output=True).stdout
    repo = Repository.from_git(TOOLSET, 'ToolSet', COMMIT, ('aletheia_toolchain','local_tool_assist_mcp'))
    assert repo.revision == COMMIT
    assert 'aletheia_toolchain/code_intelligence/audit_graphify_graph.py' not in repo.files
    with SnapshotStore(tmp_path/'toolset.sqlite') as store:
        report = ingest(store, [repo])
        assert report['status'] == 'complete'
        assert report['parse_failures'] == {'ToolSet': []}
        assert report['counts']['relationships'] > 1000
        assert not store.validate(report['snapshot_id'])
        graph = store.graph(report['snapshot_id'])
        # Independent ast oracle: unshadowed uniquely defined module functions.
        oracles = {}
        for path, data in repo.files.items():
            if not path.endswith('.py'): continue
            module = ast.parse(data, type_comments=True)
            definitions = {}
            for n in module.body:
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    definitions.setdefault(n.name,[]).append(n)
            sites = {}
            for fn in [n for ns in definitions.values() for n in ns]:
                locally_bound = {n.id for n in ast.walk(fn) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
                locally_bound |= {n.arg for n in ast.walk(fn) if isinstance(n,ast.arg)}
                for n in ast.walk(fn):
                    if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id not in locally_bound and len(definitions.get(n.func.id,[]))==1:
                        target = definitions[n.func.id][0]
                        if not target.decorator_list:
                            sites[(n.lineno,n.col_offset)] = (target.name,target.lineno)
            oracles[path] = sites
        scored = 0
        for rel in graph.relationships.values():
            if rel.subtype!='calls' or rel.resolution_status!='exact':continue
            evidence=next(e for e in graph.evidence.values() if e.relationship_id==rel.relationship_id)
            details=json.loads(evidence.details_json)
            target=graph.entities[rel.target_subject_id]
            source=graph.entities[rel.source_subject_id]
            if source.rel_path!=target.rel_path:continue
            # Evidence site stores line; callee text selects same-name oracle sites.
            matches=[v for (line,col),v in oracles.get(source.rel_path,{}).items()
                     if line==evidence.start_line and v[0]==details.get('callee')]
            if matches:
                assert (target.qualified_name.rsplit('.',1)[-1],target.start_line) in matches
                scored+=1
        assert scored > 100
        (tmp_path/'report.json').write_text(json.dumps({**report,'independent_same_file_calls_scored':scored},indent=2))
    after = subprocess.run(['git','-C',str(TOOLSET),'status','--porcelain'],check=True,capture_output=True).stdout
    assert before == after
