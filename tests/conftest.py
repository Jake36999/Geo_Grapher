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
