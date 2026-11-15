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
        assert data == {"library_name": "Parallax", "librarian_url": "http://127.0.0.1:52206/"}
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
