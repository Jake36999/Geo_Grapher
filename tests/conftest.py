import pytest

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
