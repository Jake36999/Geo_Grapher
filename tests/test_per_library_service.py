"""A library's Geo-Grapher, run by its Librarian Core (owner, 2026-11-15).

The Core starts `serve-graphs` per library on a port chosen at bind time, with a
per-library access token passed through the environment (never argv). Browser
UIs exchange the token once for an HttpOnly cookie; programs send a header.
With no token configured the server behaves exactly as before.
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

TOKEN = "t" * 43


def _client(tmp_path, **kw):
    from starlette.testclient import TestClient
    from geographer.graph_catalog import GraphCatalog
    from geographer.graph_router import GraphRouter
    from geographer.graph_server import create_graph_http
    catalog = GraphCatalog(tmp_path / "catalog.sqlite")
    app = create_graph_http(GraphRouter(catalog), **kw)
    return TestClient(app, base_url="http://127.0.0.1:8774"), catalog


def test_without_a_token_the_server_is_unchanged(tmp_path):
    client, catalog = _client(tmp_path)
    try:
        assert client.get("/api/graphs").status_code == 200
    finally:
        catalog.close()


def test_a_token_guards_every_route_including_the_ui_and_mcp(tmp_path):
    client, catalog = _client(tmp_path, access_token=TOKEN)
    try:
        for path in ("/api/graphs", "/", "/api/workspace/context"):
            assert client.get(path).status_code == 401, path
        assert client.post("/mcp", json={}).status_code == 401
        assert client.get("/api/graphs", headers={"X-Geo-Token": "wrong"}).status_code == 401
        assert client.get("/api/graphs", headers={"X-Geo-Token": TOKEN}).status_code == 200
    finally:
        catalog.close()


def test_the_browser_exchanges_the_launch_token_for_an_httponly_cookie(tmp_path):
    client, catalog = _client(tmp_path, access_token=TOKEN)
    try:
        opened = client.get(f"/?geo_token={TOKEN}", follow_redirects=False)
        assert opened.status_code == 303 and opened.headers["location"] == "/"
        cookie = opened.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie.replace("Strict", "strict")
        assert TOKEN not in opened.headers["location"]               # token leaves the URL
        assert client.get("/api/graphs").status_code == 200           # cookie now carried
        assert client.get(f"/?geo_token=wrong", follow_redirects=False).status_code == 401
    finally:
        catalog.close()


def test_context_names_the_library_and_a_loopback_librarian_url(tmp_path):
    client, catalog = _client(tmp_path, access_token=TOKEN, librarian_url="http://127.0.0.1:52206/",
                              library_name="Parallax")
    try:
        data = client.get("/api/workspace/context", headers={"X-Geo-Token": TOKEN}).json()
        assert data == {"library_name": "Parallax", "librarian_url": "http://127.0.0.1:52206/", "can_close": False,
                        "max_graphs": 3}
    finally:
        catalog.close()
    with pytest.raises(ValueError, match="loopback"):
        _client(tmp_path / "x", librarian_url="https://example.com/")


def test_serve_graphs_binds_port_zero_and_reports_it_in_a_ready_file(tmp_path):
    from geographer.graph_catalog import GraphCatalog
    GraphCatalog(tmp_path / "catalog.sqlite").close()
    ready = tmp_path / "ready.json"
    env = {**os.environ, "GEOGRAPHER_ACCESS_TOKEN": TOKEN,
           "PYTHONPATH": os.pathsep.join([str(Path(__file__).resolve().parents[1] / "src"),
                                          os.environ.get("PYTHONPATH", "")])}
    proc = subprocess.Popen([sys.executable, "-m", "geographer", "serve-graphs", "--catalog",
                             str(tmp_path / "catalog.sqlite"), "--transport", "http", "--port", "0",
                             "--ready-file", str(ready), "--librarian-url", "http://127.0.0.1:9/",
                             "--library-name", "Fixture"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(300):
            if ready.is_file():
                break
            time.sleep(0.1)
        info = json.loads(ready.read_text(encoding="utf-8"))
        # On Windows a venv python.exe is a launcher that starts the real interpreter as a
        # child, so the listener's pid may differ from proc.pid. The file reports the listener.
        assert info["port"] > 0 and isinstance(info["pid"], int) and info["pid"] > 0
        assert info["url"] == f"http://127.0.0.1:{info['port']}/"
        assert TOKEN not in ready.read_text(encoding="utf-8")         # the token is never written
        import urllib.request
        request = urllib.request.Request(info["url"] + "api/workspace/context",
                                         headers={"X-Geo-Token": TOKEN})
        with urllib.request.urlopen(request, timeout=10) as reply:
            assert json.loads(reply.read())["library_name"] == "Fixture"
    finally:
        proc.terminate()
        proc.wait(timeout=20)


def test_close_is_offered_only_to_a_library_service_and_runs_after_the_reply(tmp_path):
    """2026-11-17: a clean way to close Geo-Grapher from its own window."""
    closed = []
    client, catalog = _client(tmp_path, access_token=TOKEN, library_name="Parallax",
                              on_close=lambda: closed.append(True))
    try:
        head = {"X-Geo-Token": TOKEN}
        assert client.post("/api/workspace/close", json={}).status_code == 401          # token required
        assert closed == []
        assert client.get("/api/workspace/context", headers=head).json()["can_close"] is True
        reply = client.post("/api/workspace/close", json={}, headers=head)
        assert reply.status_code == 200 and reply.json()["closing"] is True
        assert closed == [True]
    finally:
        catalog.close()
    plain, catalog = _client(tmp_path / "standalone", access_token=TOKEN)
    try:
        assert plain.post("/api/workspace/close", json={}, headers={"X-Geo-Token": TOKEN}).status_code == 404
    finally:
        catalog.close()


def test_a_library_service_closed_from_its_window_exits_with_code_zero(tmp_path):
    from geographer.graph_catalog import GraphCatalog
    GraphCatalog(tmp_path / "catalog.sqlite").close()
    ready = tmp_path / "ready.json"
    env = {**os.environ, "GEOGRAPHER_ACCESS_TOKEN": TOKEN,
           "PYTHONPATH": os.pathsep.join([str(Path(__file__).resolve().parents[1] / "src"),
                                          os.environ.get("PYTHONPATH", "")])}
    proc = subprocess.Popen([sys.executable, "-m", "geographer", "serve-graphs", "--catalog",
                             str(tmp_path / "catalog.sqlite"), "--transport", "http", "--port", "0",
                             "--ready-file", str(ready), "--library-name", "Fixture",
                             "--parent-pid", str(os.getpid())], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(300):
            if ready.is_file():
                break
            time.sleep(0.1)
        info = json.loads(ready.read_text(encoding="utf-8"))
        import urllib.request
        request = urllib.request.Request(info["url"] + "api/workspace/close", data=b"{}", method="POST",
                                         headers={"X-Geo-Token": TOKEN, "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as reply:
            assert json.loads(reply.read())["closing"] is True
        assert proc.wait(timeout=30) == 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=20)


def test_create_catalog_lets_a_new_library_start_with_no_graphs_yet(tmp_path):
    """A library's first start happens before any folder is accepted."""
    catalog = tmp_path / "fresh" / "catalog.sqlite"
    ready = tmp_path / "ready.json"
    env = {**os.environ, "GEOGRAPHER_ACCESS_TOKEN": TOKEN,
           "PYTHONPATH": os.pathsep.join([str(Path(__file__).resolve().parents[1] / "src"),
                                          os.environ.get("PYTHONPATH", "")])}
    refused = subprocess.run([sys.executable, "-m", "geographer", "serve-graphs", "--catalog", str(catalog),
                              "--port", "0", "--ready-file", str(ready)], env=env, capture_output=True, timeout=120)
    assert refused.returncode != 0 and not catalog.exists()          # never created implicitly
    proc = subprocess.Popen([sys.executable, "-m", "geographer", "serve-graphs", "--catalog", str(catalog),
                             "--create-catalog", "--port", "0", "--ready-file", str(ready)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(300):
            if ready.is_file():
                break
            time.sleep(0.1)
        info = json.loads(ready.read_text(encoding="utf-8"))
        import urllib.request
        request = urllib.request.Request(info["url"] + "api/graphs", headers={"X-Geo-Token": TOKEN})
        with urllib.request.urlopen(request, timeout=10) as reply:
            assert reply.status == 200
        assert catalog.is_file()
    finally:
        proc.terminate()
        proc.wait(timeout=20)


def test_watch_parent_fires_when_the_parent_exits_and_not_before():
    from geographer.parent_watch import watch_parent
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    fired = threading.Event()
    cancel = watch_parent(parent.pid, fired.set)
    try:
        assert not fired.wait(1.0)                 # still alive: no exit
        parent.terminate()
        parent.wait(timeout=20)
        assert fired.wait(10.0)
    finally:
        cancel.set()
        if parent.poll() is None:
            parent.kill()


def test_watch_parent_can_be_cancelled():
    from geographer.parent_watch import watch_parent
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    fired = threading.Event()
    cancel = watch_parent(parent.pid, fired.set)
    cancel.set()
    parent.terminate()
    parent.wait(timeout=20)
    assert not fired.wait(2.0)


def test_serve_graphs_exits_when_its_parent_dies(tmp_path):
    from geographer.graph_catalog import GraphCatalog
    GraphCatalog(tmp_path / "catalog.sqlite").close()
    ready = tmp_path / "ready.json"
    env = {**os.environ, "GEOGRAPHER_ACCESS_TOKEN": TOKEN,
           "PYTHONPATH": os.pathsep.join([str(Path(__file__).resolve().parents[1] / "src"),
                                          os.environ.get("PYTHONPATH", "")])}
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    proc = subprocess.Popen([sys.executable, "-m", "geographer", "serve-graphs", "--catalog",
                             str(tmp_path / "catalog.sqlite"), "--transport", "http", "--port", "0",
                             "--ready-file", str(ready), "--parent-pid", str(parent.pid)], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(300):
            if ready.is_file():
                break
            time.sleep(0.1)
        assert ready.is_file()
        parent.terminate()
        parent.wait(timeout=20)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.2)
        assert proc.poll() is not None, "the service outlived its parent"
    finally:
        for p in (proc, parent):
            if p.poll() is None:
                p.kill()
