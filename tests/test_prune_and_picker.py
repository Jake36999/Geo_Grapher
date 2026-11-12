"""Derived-graph pruning, the guarded directory picker and the ingest job API (wave 3 Task 7; master G8, G13)."""
import subprocess
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from geographer.graph_server import create_graph_http
from geographer.store import SnapshotStore
from test_graph_catalog import hub, import_graph  # noqa: F401


def test_derive_graph_excludes_paths_and_leaves_source_untouched(hub, tmp_path):
    catalog, router, first = hub
    gid = first["graph_id"]
    root = Path(catalog.graph(gid)["root_path"])
    (root / "keep.py").write_text("def keep():\n    return 1\n", encoding="utf-8")
    (root / "skip").mkdir(); (root / "skip" / "x.py").write_text("def x():\n    pass\n", encoding="utf-8")
    from geographer.source import Repository
    catalog.import_project(root, Repository.from_directory(root, "A"), label="A")
    src = catalog.graph(gid)
    out = catalog.derive_graph(gid, exclude_rel_paths=["skip"], label="A pruned")
    after = catalog.graph(gid)
    assert after["snapshot_id"] == src["snapshot_id"] and after["profile_json"] == src["profile_json"]
    derived = catalog.graph(out["graph_id"])
    assert derived["root_key"] == "derived:" + out["graph_id"] and derived["label"] == "A pruned"
    import json
    profile = json.loads(derived["profile_json"])
    assert profile["graph_kind"] == "derived" and profile["derived_from"] == gid and {"skip", "skip/*"} <= set(profile["exclude_globs"])
    with SnapshotStore(derived["code_database"]) as s:
        sid = derived["snapshot_id"]
        assert not s.connection.execute("SELECT 1 FROM entities WHERE snapshot_id=? AND rel_path LIKE 'skip/%'", (sid,)).fetchone()
        assert s.connection.execute("SELECT 1 FROM entities WHERE snapshot_id=? AND rel_path='keep.py'", (sid,)).fetchone()
    again = catalog.derive_graph(gid, exclude_rel_paths=["skip"], label="A pruned")
    assert again["graph_id"] == out["graph_id"]  # deterministic id; re-deriving refreshes, never duplicates


def test_derive_graph_validates(hub):
    catalog, router, first = hub
    for bad in ([], ["../x"], ["/abs"], ["C:/x"], [""]):
        with pytest.raises(ValueError):
            catalog.derive_graph(first["graph_id"], exclude_rel_paths=bad, label="x")
    with pytest.raises(ValueError):
        catalog.derive_graph(first["graph_id"], exclude_rel_paths=["a"], label="")


@pytest.fixture
def picker_client(hub, tmp_path):
    catalog, router, first = hub
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "proj").mkdir(); (ws / "proj" / "m.py").write_text("def m():\n    return 1\n", encoding="utf-8")
    (ws / "docs").mkdir(); (ws / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (ws / "file.txt").write_text("x", encoding="utf-8")
    outside = tmp_path / "outside"; outside.mkdir()
    made = subprocess.run(["cmd", "/c", "mklink", "/J", str(ws / "junction"), str(outside)], capture_output=True)
    client = TestClient(create_graph_http(router, browse_roots=[ws]), base_url="http://127.0.0.1:8774")
    client.junction = made.returncode == 0
    return client, ws


@pytest.mark.parametrize("path", ["..", "C:/Windows", "\\\\server\\share", "{root}/../..", "{root}/junction", "{root}/file.txt", "{root}/missing"])
def test_fs_list_refuses_outside_roots(picker_client, path):
    client, root = picker_client
    if "junction" in path and not client.junction:
        pytest.skip("junction creation not permitted")
    assert client.get("/api/fs/list", params={"path": path.format(root=root)}).status_code == 403


def test_fs_list_lists_dirs_only(picker_client):
    client, root = picker_client
    body = client.get("/api/fs/list", params={"path": str(root)}).json()
    assert body["dirs"] == sorted(body["dirs"]) and all((root / d).is_dir() for d in body["dirs"])
    assert "file.txt" not in body["dirs"] and {"proj", "docs"} <= set(body["dirs"])
    assert client.get("/api/fs/list", params={"path": str(root / "proj")}).json()["dirs"] == []
    assert client.get("/api/fs/roots").json()["roots"] == [str(root.resolve())]


def test_picker_disabled_without_browse_roots(hub):
    catalog, router, first = hub
    client = TestClient(create_graph_http(router), base_url="http://127.0.0.1:8774")
    assert client.get("/api/fs/list", params={"path": "."}).status_code == 403
    assert client.get("/api/fs/roots").json()["roots"] == []


def wait_job(client, job_id, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        body = client.get(f"/api/workspace/jobs/{job_id}").json()
        if body["state"] in ("done", "failed"):
            return body
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_ingest_preview_then_execute_job(picker_client):
    client, root = picker_client
    plan = client.post("/api/workspace/ingest-preview", json={"root": str(root)}).json()
    assert plan["plan_version"] == "workspace-init-v1" and plan["partitions"]
    keys = [p["key"] for p in plan["partitions"]]
    job = client.post("/api/workspace/ingest-execute", json={"plan_id": plan["plan_id"], "approved_keys": keys}).json()
    done = wait_job(client, job["job_id"])
    assert done["state"] == "done" and done["reports"]
    labels = {g["label"] for g in client.get("/api/graphs").json()["graphs"]}
    assert len(labels) >= 2


def test_ingest_preview_refuses_paths_outside_roots(picker_client, tmp_path):
    client, root = picker_client
    assert client.post("/api/workspace/ingest-preview", json={"root": str(tmp_path / "outside")}).status_code == 403
    assert client.post("/api/workspace/ingest-execute", json={"plan_id": "0" * 64, "approved_keys": []}).status_code == 400


def test_second_job_while_running_is_409(picker_client, monkeypatch):
    import threading
    from geographer import workspace_init
    client, root = picker_client
    gate = threading.Event()
    real = workspace_init.apply
    monkeypatch.setattr(workspace_init, "apply", lambda *a, **k: (gate.wait(10), real(*a, **k))[1])
    plan = client.post("/api/workspace/ingest-preview", json={"root": str(root)}).json()
    body = {"plan_id": plan["plan_id"], "approved_keys": [plan["partitions"][0]["key"]]}
    first = client.post("/api/workspace/ingest-execute", json=body)
    second = client.post("/api/workspace/ingest-execute", json=body)
    gate.set()
    assert first.status_code == 200 and second.status_code == 409 and second.json()["error"] == "JOB_RUNNING"
    wait_job(client, first.json()["job_id"])


def test_prune_endpoint_creates_derived_graph(hub, tmp_path):
    catalog, router, first = hub
    root = Path(catalog.graph(first["graph_id"])["root_path"])
    (root / "skip").mkdir(); (root / "skip" / "x.py").write_text("def x():\n    pass\n", encoding="utf-8")
    client = TestClient(create_graph_http(router), base_url="http://127.0.0.1:8774")
    bad = client.post(f"/api/graphs/{first['graph_id']}/prune", json={"exclude_rel_paths": ["../x"], "label": "p"})
    assert bad.status_code == 400
    ok = client.post(f"/api/graphs/{first['graph_id']}/prune", json={"exclude_rel_paths": ["skip"], "label": "A pruned"})
    assert ok.status_code == 200 and catalog.graph(ok.json()["graph_id"])["label"] == "A pruned"
