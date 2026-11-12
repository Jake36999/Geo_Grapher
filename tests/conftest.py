import copy

import pytest

from geographer.analysis import DEFAULT_FILTER
from geographer.service import QueryService

from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.pipeline import ingest


@pytest.fixture
def extract():
    stores = []
    def run(files, repo_id="repo", others=(), publish=True, resolution_group=None):
        repo = Repository(repo_id, "fixture-revision", {p: s.encode() if isinstance(s, str) else s for p, s in files.items()},resolution_group=resolution_group)
        store = SnapshotStore()
        stores.append(store)
        report = ingest(store, [repo, *others], publish=publish)
        return store.graph(report["snapshot_id"], published_only=publish), store, report
    yield run
    for store in stores:
        store.close()


def calls(graph):
    return [(graph.entities[r.source_subject_id].qualified_name,
             graph.entities[r.target_subject_id].qualified_name, r.resolution_status)
            for r in graph.relationships.values() if r.subtype == "calls"]


@pytest.fixture
def extract_markdown(extract):
    def run(text, line, name="README.md"):
        graph, _, _ = extract({name: text})
        fid = next(e.entity_id for e in sorted(graph.entities.values(), key=lambda e: e.entity_id)
                   if e.kind == "fragment" and e.start_line == line)
        return graph, fid
    return run


@pytest.fixture
def extract_python(extract):
    def run(src, fragment_of):
        graph, _, _ = extract({"m.py": src})
        fid = next(e.entity_id for e in sorted(graph.entities.values(), key=lambda e: e.entity_id)
                   if e.kind == "fragment" and graph.entities[e.parent_id].qualified_name.rsplit(".", 1)[-1] == fragment_of)
        return graph, fid
    return run


@pytest.fixture
def extract_module(extract):
    def run(src, qualname):
        from geographer.analysis import prepare_analysis
        graph, _, _ = extract({"m.py": src})
        prepare_analysis(graph)
        eid = next(e.entity_id for e in sorted(graph.entities.values(), key=lambda e: e.entity_id)
                   if e.qualified_name.replace(".py.", ".", 1).endswith(qualname) and e.kind in {"function", "method", "class"})
        return graph, eid
    return run


def viewport_request(sid,focus,budget=32768):
    return dict(schema_version='1.0',request_id='viewport-test',snapshot_id=sid,budget=dict(limit_tokens=budget,tokenizer='o200k_base',allow_byte_fallback=False),
        focus_id=focus,revealed_ids=[],pins=[],context_radius=2,filter=copy.deepcopy(DEFAULT_FILTER),layout_version='sphere-pack-v1',seed='view-v1',beta=.8,
        edge_lens=dict(enabled=False,center=[0,0,0],radius=5.,strength=.8),node_budget=100,curve_budget=200,
        viewport=dict(width_px=1440,height_px=900,device_pixel_ratio=1),camera=dict(eye=[0,0,100],target=[0,0,0],up=[0,1,0],fov_y_degrees=45,near=.01,far=10000))


@pytest.fixture
def frame_for(tmp_path):
    stores=[]
    def run(grouping,curve_budget=200,**overrides):
        repo=Repository('r','rev',{'app.py':b'def helper():\n    return 1\n\ndef run():\n    return helper()\n',
                                    'README.md':b'Use `run` here.\n'})
        store=SnapshotStore(tmp_path/('s%d.db'%len(stores)));stores.append(store)
        sid=ingest(store,[repo],stage=3)['snapshot_id']
        svc=QueryService(store,secret=b'x'*32);ctx=svc._context(sid)
        root=next(e.entity_id for e in ctx['g'].entities.values() if e.kind=='repository')
        req=viewport_request(sid,root)
        req.update(schema_version='1.1',grouping=grouping,curve_budget=curve_budget)
        req.update(overrides)
        result=svc.query('viewport_frame',req)
        assert 'error' not in result,result
        run.svc=svc;run.result=result
        return result['data']
    yield run
    for store in stores:store.close()
