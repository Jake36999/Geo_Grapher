"""The Build tab's operators: a person's role override, keep-only and remove with preview counts, a read-only
comparison, and declared links that can be added and taken back (owner direction 2026-11-19)."""
import json
import sqlite3
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from geographer.cross_graph import compare_graphs
from geographer.graph_server import create_graph_http
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.workspace_init import ROLES, apply, role_policy, scan, validate_role_overrides
from test_graph_catalog import hub, import_graph  # noqa: F401
from test_wave_l_inventory import _tree_with_unlicensed_and_licensed_repos


def stratum(catalog, graph_id):
    return json.loads(catalog.graph(graph_id)["profile_json"])["stratum"]


# --- role override -------------------------------------------------------------------------------

def test_the_role_policy_is_one_source_for_the_scan_and_the_sheet(tmp_path):
    policy = role_policy()
    assert tuple(policy) == ROLES
    assert {r for r, p in policy.items() if p["publication"] == "reference"} == {"third_party", "external_reference", "research_docs"}
    assert {r for r, p in policy.items() if p["licence_applicable"]} == {"third_party", "external_reference"}
    assert scan(_tree_with_unlicensed_and_licensed_repos(tmp_path))["role_policy"] == policy


def test_an_overridden_role_changes_the_stratum_and_nothing_else(tmp_path, hub):
    catalog, router, first = hub
    (tmp_path / "tree").mkdir()
    plan = scan(_tree_with_unlicensed_and_licensed_repos(tmp_path / "tree"))
    suggested = next(p for p in plan["partitions"] if p["key"] == "vendor")
    assert suggested["role"] == "third_party" and suggested["stratum"]["trust_tier"] == "bronze"
    plain = apply(catalog, plan, approved_keys={"vendor"})[0]
    assert stratum(catalog, plain["graph_id"])["role"] == "third_party" and plain["role"] == plain["role_suggested"] == "third_party"
    changed = apply(catalog, plan, approved_keys={"vendor"}, role_overrides={"vendor": "current"})[0]
    # the person said it is their own work: the stratum follows, the folder is ingested the same way
    assert changed["graph_id"] == plain["graph_id"]
    assert changed["role"] == "current" and changed["role_suggested"] == "third_party"
    assert stratum(catalog, changed["graph_id"]) == {"role": "current", "trust_tier": "gold", "modality": "code"}


def test_an_override_only_applies_to_an_approved_part(tmp_path, hub):
    catalog, router, first = hub
    (tmp_path / "tree").mkdir()
    plan = scan(_tree_with_unlicensed_and_licensed_repos(tmp_path / "tree"))
    assert validate_role_overrides(plan, {"vendor"}, {"vendor": "legacy", "external": "docs"}) == {"vendor": "legacy"}
    report = apply(catalog, plan, approved_keys={"vendor"}, role_overrides={"vendor": "legacy", "external": "docs"})
    assert [r["key"] for r in report] == ["vendor"] and report[0]["role"] == "legacy"
    assert stratum(catalog, report[0]["graph_id"])["trust_tier"] == "bronze"


@pytest.mark.parametrize("bad", [["vendor"], {"nope": "current"}, {"vendor": "boss"}, {"vendor": 3}])
def test_a_bad_override_is_refused_before_anything_is_ingested(tmp_path, hub, bad):
    catalog, router, first = hub
    (tmp_path / "tree").mkdir()
    plan = scan(_tree_with_unlicensed_and_licensed_repos(tmp_path / "tree"))
    with pytest.raises(ValueError):
        apply(catalog, plan, approved_keys={"vendor"}, role_overrides=bad)
    assert len(catalog.graphs()) == 1  # only the fixture graph


def test_the_server_passes_overrides_and_refuses_bad_ones(tmp_path, hub):
    import time
    catalog, router, first = hub
    ws = tmp_path / "ws"; ws.mkdir()
    _tree_with_unlicensed_and_licensed_repos(ws)
    client = TestClient(create_graph_http(router, browse_roots=[ws]), base_url="http://127.0.0.1:8774")
    plan = client.post("/api/workspace/ingest-preview", json={"root": str(ws)}).json()
    body = {"plan_id": plan["plan_id"], "approved_keys": ["vendor"]}
    assert client.post("/api/workspace/ingest-execute", json={**body, "role_overrides": {"vendor": "boss"}}).status_code == 400
    assert client.post("/api/workspace/ingest-execute", json={**body, "role_overrides": {"ghost": "docs"}}).status_code == 400
    started = client.post("/api/workspace/ingest-execute", json={**body, "role_overrides": {"vendor": "docs"}})
    assert started.status_code == 200
    end = time.time() + 120
    while time.time() < end:
        job = client.get(f"/api/workspace/jobs/{started.json()['job_id']}").json()
        if job["state"] in ("done", "failed"):
            break
        time.sleep(0.2)
    assert job["state"] == "done" and job["reports"][0]["role"] == "docs" and job["reports"][0]["role_suggested"] == "third_party"


# --- keep only / remove, with preview counts -----------------------------------------------------

LIB = "def used():\n    return 1\n\ndef shared():\n    return used()\n"
APP = "from lib import shared\n\ndef main():\n    return shared()\n"
OTHER = "def other():\n    return 3\n"


@pytest.fixture
def project(tmp_path, hub):
    catalog, router, first = hub
    root = tmp_path / "proj"
    for rel, text in {"keep.py": LIB, "app/main.py": APP, "skip/x.py": OTHER, "skip/y.py": OTHER.replace("other", "another")}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    gid = catalog.import_project(root, Repository.from_directory(root, "P"), label="P")["graph_id"]
    return catalog, router, gid, root


def file_set(catalog, graph_id):
    row = catalog.graph(graph_id)
    with SnapshotStore(row["code_database"]) as s:
        return {r[0] for r in s.connection.execute("SELECT DISTINCT rel_path FROM entities WHERE snapshot_id=? AND kind='file'", (row["snapshot_id"],))}


def test_keep_only_makes_a_graph_of_just_those_paths_and_leaves_the_source_alone(project):
    catalog, router, gid, root = project
    before = catalog.graph(gid)
    out = catalog.derive_graph(gid, keep_rel_paths=["keep.py", "app"], label="Just the core")
    assert out["mode"] == "keep" and set(out["include_globs"]) == {"keep.py", "keep.py/*", "app", "app/*"}
    assert file_set(catalog, out["graph_id"]) == {"keep.py", "app/main.py"}
    assert catalog.graph(gid)["snapshot_id"] == before["snapshot_id"] and catalog.graph(gid)["profile_json"] == before["profile_json"]
    profile = json.loads(catalog.graph(out["graph_id"])["profile_json"])
    assert profile["graph_kind"] == "derived" and profile["derived_from"] == gid
    assert profile["derived_how"] == {"mode": "keep", "paths": ["app", "keep.py"]}
    again = catalog.derive_graph(gid, keep_rel_paths=["app", "keep.py"], label="Just the core")
    assert again["graph_id"] == out["graph_id"]  # the same selection refreshes, never duplicates


def test_keep_and_remove_of_the_same_paths_are_different_graphs(project):
    catalog, router, gid, root = project
    kept = catalog.derive_graph(gid, keep_rel_paths=["skip"], label="Only skip")
    removed = catalog.derive_graph(gid, exclude_rel_paths=["skip"], label="Without skip")
    assert kept["graph_id"] != removed["graph_id"]
    assert file_set(catalog, kept["graph_id"]) == {"skip/x.py", "skip/y.py"}
    assert file_set(catalog, removed["graph_id"]) == {"keep.py", "app/main.py"}


def test_a_derivation_is_one_mode_with_valid_paths(project):
    catalog, router, gid, root = project
    for kwargs in ({}, {"exclude_rel_paths": ["a"], "keep_rel_paths": ["b"]}, {"keep_rel_paths": []}, {"keep_rel_paths": ["../x"]},
                   {"keep_rel_paths": ["/abs"]}, {"keep_rel_paths": ["C:/x"]}, {"keep_rel_paths": [3]}):
        with pytest.raises(ValueError):
            catalog.derive_graph(gid, label="x", **kwargs)
        with pytest.raises(ValueError):
            catalog.derive_preview(gid, **kwargs)
    with pytest.raises(ValueError, match="label"):
        catalog.derive_graph(gid, keep_rel_paths=["keep.py"], label="")


def test_keep_only_refuses_a_graph_that_already_limits_what_it_includes(project):
    catalog, router, gid, root = project
    narrowed = catalog.derive_graph(gid, keep_rel_paths=["app"], label="App only")["graph_id"]
    with pytest.raises(ValueError, match="KEEP_UNSUPPORTED"):
        catalog.derive_graph(narrowed, keep_rel_paths=["app/main.py"], label="Narrower")
    with pytest.raises(ValueError, match="KEEP_UNSUPPORTED"):
        catalog.derive_preview(narrowed, keep_rel_paths=["app/main.py"])
    # removing paths from it is still fine
    assert catalog.derive_preview(narrowed, exclude_rel_paths=["app/main.py"])["mode"] == "exclude"


def test_the_preview_counts_match_what_the_derivation_makes(project):
    catalog, router, gid, root = project
    for kwargs in ({"keep_rel_paths": ["keep.py", "app"]}, {"exclude_rel_paths": ["skip"]}, {"keep_rel_paths": ["skip/x.py"]}):
        preview = catalog.derive_preview(gid, **kwargs)
        made = catalog.derive_graph(gid, label="check " + preview["mode"] + str(len(kwargs)), **kwargs)["graph_id"]
        assert preview["files"]["kept"] == len(file_set(catalog, made)) and preview["files"]["total"] == 4
        assert preview["files"]["removed"] == 4 - preview["files"]["kept"]
        assert preview["entities"]["kept"] + preview["entities"]["removed"] == preview["entities"]["total"]
        row = catalog.graph(made)
        with SnapshotStore(row["code_database"]) as s:
            in_files = s.connection.execute("SELECT count(*) FROM entities WHERE snapshot_id=? AND rel_path IS NOT NULL AND kind<>'directory'", (row["snapshot_id"],)).fetchone()[0]
        assert preview["entities"]["kept"] == in_files


def test_the_preview_counts_the_relationships_a_cut_would_drop(project):
    catalog, router, gid, root = project
    # app/main.py calls shared() in keep.py: keeping only keep.py drops that call, and nothing else crosses
    cut = catalog.derive_preview(gid, keep_rel_paths=["keep.py"])
    whole = catalog.derive_preview(gid, keep_rel_paths=["keep.py", "app", "skip"])
    assert whole["relationships"]["dropped"] == 0 and whole["files"]["removed"] == 0
    assert cut["relationships"]["dropped"] >= 1
    assert cut["relationships"]["kept"] + cut["relationships"]["dropped"] == whole["relationships"]["total"] == cut["relationships"]["total"]


def test_the_preview_names_paths_that_match_no_file_and_writes_nothing(project):
    catalog, router, gid, root = project
    graphs_before = len(catalog.graphs())
    preview = catalog.derive_preview(gid, keep_rel_paths=["keep.py", "nothing/here"])
    assert preview["unmatched_paths"] == ["nothing/here"] and preview["files"]["kept"] == 1
    assert len(catalog.graphs()) == graphs_before


def test_the_server_previews_and_derives_in_both_modes(project):
    catalog, router, gid, root = project
    client = TestClient(create_graph_http(router), base_url="http://127.0.0.1:8774")
    url = f"/api/graphs/{gid}"
    ok = client.post(f"{url}/derive-preview", json={"keep_rel_paths": ["keep.py"]})
    assert ok.status_code == 200 and ok.json()["mode"] == "keep" and ok.json()["files"]["kept"] == 1
    assert client.post(f"{url}/derive-preview", json={}).status_code == 400
    assert client.post(f"{url}/derive-preview", json={"keep_rel_paths": ["../x"]}).status_code == 400
    assert client.post("/api/graphs/g_unknown/derive-preview", json={"keep_rel_paths": ["a"]}).status_code == 400
    made = client.post(f"{url}/prune", json={"keep_rel_paths": ["keep.py"], "label": "Kept"})
    assert made.status_code == 200 and made.json()["mode"] == "keep" and catalog.graph(made.json()["graph_id"])["label"] == "Kept"
    still = client.post(f"{url}/prune", json={"exclude_rel_paths": ["skip"], "label": "Pruned"})
    assert still.status_code == 200 and still.json()["mode"] == "exclude"  # the earlier contract still holds
    assert client.post(f"{url}/prune", json={"label": "neither"}).status_code == 400


# --- compare ---------------------------------------------------------------------------------------

PING = {"a.py": "from b import g\n\ndef f():\n    return g()\n\ndef k():\n    return 1\n",
        "b.py": "from a import k\n\ndef g():\n    return 2\n\ndef h():\n    return k()\n"}
PONG = {"a.py": "from b import g\n\ndef f():\n    return g()\n\ndef k():\n    return 1\n",
        "b.py": "def g():\n    return 2\n\ndef h():\n    return 3\n\ndef brand_new(x):\n    return x * 7\n"}


def code_graph(catalog, root, label, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return catalog.import_project(root, Repository.from_directory(root, label), label=label)["graph_id"]


def test_compare_gives_counts_first_then_a_bounded_sample(tmp_path, hub):
    catalog, router, first = hub
    a = code_graph(catalog, tmp_path / "v1", "v1", PING)
    b = code_graph(catalog, tmp_path / "v2", "v2", PONG)
    out = compare_graphs(catalog, a, b)
    assert out["graph_a"] == a and out["graph_b"] == b and out["scope"] == "functions, methods and classes"
    assert out["matched"] >= 3 and out["classes"]["EXACT_AST_SURVIVOR"] >= 2  # f, g and k survive unchanged
    assert out["only_b"]["count"] >= 1 and any(item["name"].endswith("brand_new") for item in out["only_b"]["sample"])
    assert out["compared"]["a"] > 0 and out["compared"]["b"] > 0
    for entry in out["only_a"]["sample"] + out["only_b"]["sample"]:
        assert set(entry) == {"name", "kind", "rel_path", "line"}
    assert out["cycles"] == {"CYCLE_DISSOLVED": 1}
    small = compare_graphs(catalog, a, b, sample=1)
    assert all(len(v) <= 1 for v in small["pairs"].values()) and len(small["only_b"]["sample"]) <= 1
    assert small["only_b"]["count"] == out["only_b"]["count"]  # the count never depends on the sample
    with pytest.raises(ValueError):
        compare_graphs(catalog, a, a)
    with pytest.raises(ValueError):
        compare_graphs(catalog, a, b, sample=0)


def test_compare_changes_neither_graph(tmp_path, hub):
    catalog, router, first = hub
    a = code_graph(catalog, tmp_path / "v1", "v1", PING)
    b = code_graph(catalog, tmp_path / "v2", "v2", PONG)
    before = [catalog.graph(g)["snapshot_id"] for g in (a, b)]
    compare_graphs(catalog, a, b)
    assert [catalog.graph(g)["snapshot_id"] for g in (a, b)] == before and not catalog.bridges([a, b])


def test_the_server_compares_and_explains_missing_fingerprints(tmp_path, hub):
    catalog, router, first = hub
    a = code_graph(catalog, tmp_path / "v1", "v1", PING)
    b = code_graph(catalog, tmp_path / "v2", "v2", PONG)
    client = TestClient(create_graph_http(router), base_url="http://127.0.0.1:8774")
    ok = client.post("/api/graphs/compare", json={"graph_a": a, "graph_b": b})
    assert ok.status_code == 200 and ok.json()["matched"] >= 3
    assert client.post("/api/graphs/compare", json={"graph_a": a, "graph_b": a}).status_code == 400
    assert client.post("/api/graphs/compare", json={"graph_a": a}).status_code == 400
    assert client.post("/api/graphs/compare", json={"graph_a": a, "graph_b": "g_unknown"}).status_code == 400
    con = sqlite3.connect(catalog.graph(b)["code_database"])
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'immutable_entity_fingerprints_%'").fetchall():
        con.execute(f"DROP TRIGGER {name}")
    con.execute("DELETE FROM entity_fingerprints"); con.commit(); con.close()
    router.close()  # drop any cached read of the store
    missing = client.post("/api/graphs/compare", json={"graph_a": a, "graph_b": b})
    assert missing.status_code == 400 and "fingerprints" in missing.json()["error"]


# --- declared links ----------------------------------------------------------------------------------

@pytest.fixture
def two(tmp_path, hub):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / "b", "B", text="Other research notes.")
    return catalog, router, first["graph_id"], second["graph_id"]


def test_a_person_declares_a_link_and_takes_it_back(two):
    catalog, router, a, b = two
    snapshots = [catalog.graph(g)["snapshot_id"] for g in (a, b)]
    link = router.declare_link(a, "root", b, "root", "reference", "A cites B's notes")
    assert link["source_graph"] == a and link["target_graph"] == b and link["kind"] == "reference" and link["state"] == "accepted"
    assert json.loads(link["evidence_json"])[0]["declared_by"] == "operator"
    assert [x["bridge_id"] for x in router.bridges([a, b])] == [link["bridge_id"]]
    assert router.declare_link(a, "root", b, "root", "reference", "A cites B's notes")["bridge_id"] == link["bridge_id"]  # idempotent
    receipt = router.remove_link(link["bridge_id"])
    assert receipt == {"removed": link["bridge_id"], "source_graph": a, "target_graph": b}
    assert router.bridges([a, b]) == [] and not catalog.bindings(link["bridge_id"])
    with pytest.raises(ValueError, match="Unknown bridge_id"):
        catalog.bridge_state(link["bridge_id"])
    # the graphs themselves never changed
    assert [catalog.graph(g)["snapshot_id"] for g in (a, b)] == snapshots


def test_removing_a_link_also_clears_what_the_lineage_kept_for_it(two):
    catalog, router, a, b = two
    link = router.declare_link(a, "root", b, "root", "reference", "tracked")
    assert catalog.connection.execute("SELECT count(*) FROM artifact_states WHERE artifact_id=?", (link["bridge_id"],)).fetchone()[0] == 1
    router.remove_link(link["bridge_id"])
    for table in ("artifact_states", "artifact_justifications"):
        assert catalog.connection.execute(f"SELECT count(*) FROM {table} WHERE artifact_id=?", (link["bridge_id"],)).fetchone()[0] == 0
    with pytest.raises(ValueError, match="Unknown bridge_id"):
        router.remove_link(link["bridge_id"])


@pytest.mark.parametrize("kwargs", [
    dict(kind="child_module"), dict(kind="friend"), dict(rationale=""), dict(rationale="  "), dict(source_ref="../doc"),
    dict(source_ref="entity:missing-entity"), dict(target_ref="doc:1"), dict(target_graph="same"),
])
def test_a_bad_link_is_refused_and_changes_nothing(two, kwargs):
    catalog, router, a, b = two
    args = dict(source_graph=a, source_ref="root", target_graph=b, target_ref="root", kind="reference", rationale="why")
    args.update(kwargs)
    if args["target_graph"] == "same":
        args["target_graph"] = a
    with pytest.raises(ValueError):
        router.declare_link(**args)
    assert catalog.bridges([a, b]) == []


def test_the_server_declares_lists_and_removes_links(two):
    catalog, router, a, b = two
    client = TestClient(create_graph_http(router), base_url="http://127.0.0.1:8774")
    body = dict(source_graph=a, source_ref="root", target_graph=b, target_ref="root", kind="reference", rationale="Reviewed by hand")
    assert client.post("/api/graphs/links", json={**body, "rationale": ""}).status_code == 400
    assert client.post("/api/graphs/links", json={**body, "kind": "nonsense"}).status_code == 400
    assert client.post("/api/graphs/links", json={k: v for k, v in body.items() if k != "kind"}).status_code == 400
    made = client.post("/api/graphs/links", json=body)
    assert made.status_code == 200 and made.json()["state"] == "accepted"
    listed = client.post("/api/graphs/bridges", json={"graph_ids": [a, b]}).json()["bridges"]
    assert [x["bridge_id"] for x in listed] == [made.json()["bridge_id"]] and listed[0]["rationale"] == "Reviewed by hand"
    assert client.delete(f"/api/graphs/links/{made.json()['bridge_id']}").json()["removed"] == made.json()["bridge_id"]
    assert client.post("/api/graphs/bridges", json={"graph_ids": [a, b]}).json()["bridges"] == []
    assert client.delete(f"/api/graphs/links/{made.json()['bridge_id']}").status_code == 404
