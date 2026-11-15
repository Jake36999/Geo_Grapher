"""Typed snapshot-bound bridge endpoints and reviewed proposals (master G4; wave 3 Task 4)."""
import json
import sqlite3

import pytest

from geographer.bridges import normalise, parse_ref, score_candidate


@pytest.mark.parametrize('citation,neighbours,expected',[
    (0,0.0,0.1125),
    (0,1/32,0.1140625),
    (0,0.199999,0.1225),
    (0,0.2,0.49),
    (0,0.200001,0.49),
    (1,0.0,0.8),
])
def test_owner_firewall_requires_citation_or_threshold_neighbourhood(citation,neighbours,expected):
    score=score_candidate(dict(alias_overlap=1.0,shared_citation=citation,neighbour_jaccard=neighbours))
    assert score==pytest.approx(expected,abs=0.00000051)
from geographer.graph_catalog import GraphCatalog
from geographer.source import Repository

CODE = {"kg.py": "def entity_linking(text):\n    return text\n\n"
                 "def knowledge_graph(text):\n    \"\"\"See https://doi.org/10.1234/kg.2020 for the model.\"\"\"\n    return entity_linking(text)\n"}


def paper_db(path):
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE read_documents(id INTEGER PRIMARY KEY,title TEXT,authors TEXT,year INTEGER,venue TEXT,doi TEXT,abstract_summary TEXT,
      page_count INTEGER,file_path TEXT,primary_source_id INTEGER,source_count INTEGER,claim_count INTEGER,metadata_json TEXT NOT NULL);
    CREATE TABLE read_claims(id INTEGER PRIMARY KEY,section_id INTEGER,text TEXT,claim_type TEXT,doc_id INTEGER,source_ids_json TEXT);
    CREATE TABLE read_concepts(id INTEGER PRIMARY KEY,canonical_name TEXT,aliases TEXT,definition TEXT,concept_type TEXT,def_doc_id INTEGER,quality TEXT,original_ids_json TEXT);
    CREATE TABLE read_doc_concepts(doc_id INTEGER NOT NULL,concept_id INTEGER NOT NULL,edge_type TEXT NOT NULL,PRIMARY KEY(doc_id,concept_id,edge_type));
    CREATE TABLE sections(id INTEGER PRIMARY KEY,doc_id INTEGER,heading TEXT,section_type TEXT,position INTEGER,text TEXT,word_count INTEGER);
    CREATE TABLE corpus_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    INSERT INTO corpus_metadata VALUES('revision','rev-1');
    INSERT INTO read_documents VALUES(1,'Knowledge graphs','[]',2020,NULL,'10.1234/kg.2020',NULL,1,'a.pdf',1,1,1,'{"source_document_ids":[1]}');
    INSERT INTO read_documents VALUES(2,'Unrelated','[]',2021,NULL,NULL,NULL,1,'b.pdf',2,1,0,'{"source_document_ids":[2]}');
    INSERT INTO sections VALUES(5,1,'Entity linking','body',1,'...',1);
    INSERT INTO read_claims VALUES(3,5,'Knowledge graphs improve recall.','finding',1,'[1]');
    INSERT INTO read_concepts VALUES(1,'knowledge graph','["knowledge graphs"]','',NULL,1,'ok','[1]');
    INSERT INTO read_concepts VALUES(2,'entity linking','[]','',NULL,1,'ok','[2]');
    INSERT INTO read_concepts VALUES(3,'transformer','[]','',NULL,2,'ok','[3]');
    INSERT INTO read_doc_concepts VALUES(1,1,'defines');
    INSERT INTO read_doc_concepts VALUES(1,2,'mentions');
    INSERT INTO read_doc_concepts VALUES(2,3,'defines');
    """)
    con.commit(); con.close()


@pytest.fixture
def hub_with_code_and_papers(tmp_path):
    catalog = GraphCatalog(tmp_path / "cat" / "catalog.sqlite")
    code_root = tmp_path / "code"; code_root.mkdir()
    for name, text in CODE.items():
        (code_root / name).write_text(text, encoding="utf-8")
    code_gid = catalog.import_project(code_root, Repository.from_directory(code_root, "code"), label="code")["graph_id"]
    paper_root = tmp_path / "papers"; paper_root.mkdir(); (paper_root / "README.md").write_text("# papers\n", encoding="utf-8")
    paper_gid = catalog.import_project(paper_root, Repository.from_directory(paper_root, "papers"), label="papers")["graph_id"]
    paper_db(tmp_path / "papers.sqlite"); catalog.attach_papers(paper_gid, tmp_path / "papers.sqlite")
    from geographer.store import SnapshotStore
    with SnapshotStore(catalog.graph(code_gid)["code_database"]) as store:
        eid = next(e.entity_id for e in store.graph(catalog.graph(code_gid)["snapshot_id"]).entities.values()
                   if e.qualified_name.endswith("knowledge_graph"))
    yield catalog, code_gid, paper_gid, eid
    catalog.close()


def test_parse_ref_grammar():
    assert parse_ref("doc:12#claim:3") == ("claim", {"doc": 12, "claim": 3})
    assert parse_ref("doc:12#section:4") == ("section", {"doc": 12, "section": 4})
    assert parse_ref("doc:7") == ("doc", {"doc": 7}) and parse_ref("concept:2") == ("concept", {"concept": 2})
    assert parse_ref("root") == ("root", {}) and parse_ref("entity:entity:ab12") == ("entity", {"entity": "entity:ab12"})
    for bad in ("doc:0", "doc:x", "entity:", "claim:3", "../x", "doc:01", "doc:1#claim:0", "entity:a/../b", "entity:..", "", "Root"):
        with pytest.raises(ValueError, match="BRIDGE_REF_INVALID"):
            parse_ref(bad)


def test_add_bridge_binds_snapshot_and_rejects_unresolved(hub_with_code_and_papers):
    catalog, code_gid, paper_gid, eid = hub_with_code_and_papers
    bid = catalog.add_bridge(paper_gid, "doc:1#claim:3", code_gid, f"entity:{eid}", "reference", "Paper describes it", [{"note": "t"}])
    b = catalog.bindings(bid)
    assert b["target"]["snapshot_id"] == catalog.graph(code_gid)["snapshot_id"] and json.loads(b["target"]["fingerprint_json"])["signature_hash"]
    assert b["source"]["paper_read_model"] == "rev-1" and json.loads(b["source"]["fingerprint_json"])["claim_text_sha256"]
    for bad_source in ("doc:999", "doc:1#claim:999", "doc:2#claim:3", "doc:1#section:999", "concept:99"):
        with pytest.raises(ValueError, match="BRIDGE_ENDPOINT_UNRESOLVED"):
            catalog.add_bridge(paper_gid, bad_source, code_gid, f"entity:{eid}", "reference", "x", [{"n": 1}])
    with pytest.raises(ValueError, match="BRIDGE_ENDPOINT_UNRESOLVED"):
        catalog.add_bridge(paper_gid, "doc:1", code_gid, "entity:entity:nope", "reference", "x", [{"n": 1}])
    with pytest.raises(ValueError, match="BRIDGE_REF_INVALID"):
        catalog.add_bridge(paper_gid, "../doc", code_gid, "root", "reference", "x", [{"n": 1}])
    assert len(catalog.bridges([paper_gid, code_gid])) == 1  # failed adds left nothing behind


def test_root_bridges_still_valid_and_bound(hub_with_code_and_papers):
    catalog, code_gid, paper_gid, _ = hub_with_code_and_papers
    bid = catalog.add_bridge(code_gid, "root", paper_gid, "root", "reference", "Operator reference", [{"source": "test"}])
    b = catalog.bindings(bid)
    assert b["source"]["snapshot_id"] == catalog.graph(code_gid)["snapshot_id"] and b["source"]["fingerprint_json"] == "{}"


def test_legacy_bridges_get_bindings_on_open(tmp_path, hub_with_code_and_papers):
    catalog, code_gid, paper_gid, _ = hub_with_code_and_papers
    bid = catalog.add_bridge(code_gid, "root", paper_gid, "root", "reference", "Operator reference", [{"source": "test"}])
    with catalog.connection:
        catalog.connection.execute("DELETE FROM bridge_bindings")  # simulate a catalog written before bindings
    path = catalog.path; catalog.close()
    reopened = GraphCatalog(path)
    try:
        assert set(reopened.bindings(bid)) == {"source", "target"}
    finally:
        reopened.close()
    catalog.connection = __import__("sqlite3").connect(path)  # fixture teardown closes this


def test_homonym_firewall_penalises_name_only_match():
    assert score_candidate({"alias_overlap": 1.0, "shared_citation": 0, "neighbour_jaccard": 0}) == 0.1125
    assert score_candidate({"alias_overlap": 1.0, "shared_citation": 1, "neighbour_jaccard": 0.5}) == 0.9
    assert score_candidate({"alias_overlap": 0.5, "shared_citation": 0, "neighbour_jaccard": 1}) == 0.425
    with pytest.raises(ValueError):
        score_candidate({"alias_overlap": 2})


def test_normalise_splits_code_names():
    assert normalise("knowledge_graph") == normalise("KnowledgeGraph") == "knowledge graph"


def test_proposals_never_auto_merge_and_accept_creates_bridge(hub_with_code_and_papers):
    catalog, code_gid, paper_gid, eid = hub_with_code_and_papers
    props = catalog.propose_bridges(paper_gid, code_gid, kind="reference")
    assert catalog.bridges([paper_gid, code_gid]) == []  # nothing created by proposing
    assert props and all(p["score"] >= 0.30 and p["status"] == "pending" for p in props)
    top = props[0]
    assert top["source_ref"] == "concept:1" and top["target_ref"] == f"entity:{eid}"
    assert top["features"]["shared_citation"] == 1 and top["features"]["neighbour_jaccard"] > 0
    assert not any(p["source_ref"] == "concept:3" for p in props)  # no name match at all
    out = catalog.review_proposal(top["proposal_id"], "accept", "Reviewed: same concept")
    bridges = catalog.bridges([paper_gid, code_gid])
    assert len(bridges) == 1 and out["status"] == "accepted" and out["bridge_id"] == bridges[0]["bridge_id"]
    assert json.loads(bridges[0]["evidence_json"])[0]["proposal_id"] == top["proposal_id"]
    with pytest.raises(ValueError, match="PROPOSAL_ALREADY_DECIDED"):
        catalog.review_proposal(top["proposal_id"], "reject", "changed my mind")
    assert catalog.bridge_state(out["bridge_id"]) == "accepted"


def test_reject_records_decision_and_creates_nothing(hub_with_code_and_papers):
    catalog, code_gid, paper_gid, _ = hub_with_code_and_papers
    props = catalog.propose_bridges(paper_gid, code_gid, kind="reference")
    out = catalog.review_proposal(props[0]["proposal_id"], "reject", "Homonym")
    assert out["status"] == "rejected" and out["bridge_id"] is None and catalog.bridges([paper_gid, code_gid]) == []
    assert catalog.proposals([paper_gid, code_gid], "rejected")[0]["decision_rationale"] == "Homonym"
    again = catalog.propose_bridges(paper_gid, code_gid, kind="reference")  # re-proposing keeps the decision
    assert next(p for p in again if p["proposal_id"] == out["proposal_id"])["status"] == "rejected"


def test_review_validates_inputs(hub_with_code_and_papers):
    catalog, code_gid, paper_gid, _ = hub_with_code_and_papers
    pid = catalog.propose_bridges(paper_gid, code_gid, kind="reference")[0]["proposal_id"]
    for decision, rationale in (("merge", "x"), ("accept", ""), ("accept", " ")):
        with pytest.raises(ValueError):
            catalog.review_proposal(pid, decision, rationale)
    with pytest.raises(ValueError):
        catalog.propose_bridges(paper_gid, paper_gid, kind="reference")
    with pytest.raises(ValueError):
        catalog.propose_bridges(paper_gid, code_gid, kind="child_module")


def test_deleting_a_graph_removes_bindings(hub_with_code_and_papers):
    catalog, code_gid, paper_gid, eid = hub_with_code_and_papers
    bid = catalog.add_bridge(paper_gid, "doc:1", code_gid, f"entity:{eid}", "reference", "x", [{"n": 1}])
    catalog.delete_graph(code_gid)
    assert catalog.bindings(bid) == {}


def test_cite_key_matches_doi_forms():
    from geographer.bridges import cite_key
    assert cite_key("https://doi.org/10.1234/KG.2020.") == cite_key("10.1234/kg.2020") == cite_key("doi: 10.1234/kg.2020") == "10.1234/kg.2020"
    assert cite_key("https://example.org/x") == "https://example.org/x"


def test_http_propose_list_and_decide(hub_with_code_and_papers):
    from starlette.testclient import TestClient
    from geographer.graph_router import GraphRouter
    from geographer.graph_server import create_graph_http
    catalog, code_gid, paper_gid, _ = hub_with_code_and_papers
    client = TestClient(create_graph_http(GraphRouter(catalog)), base_url="http://127.0.0.1:8774")
    made = client.post("/api/graphs/bridge-proposals", json={"graph_a": paper_gid, "graph_b": code_gid, "kind": "reference"})
    assert made.status_code == 200 and made.json()["proposals"]
    listed = client.get(f"/api/graphs/bridge-proposals?graph_ids={paper_gid},{code_gid}").json()["proposals"]
    pid = listed[0]["proposal_id"]
    assert client.post(f"/api/graphs/bridge-proposals/{pid}", json={"decision": "accept", "rationale": ""}).status_code == 400
    ok = client.post(f"/api/graphs/bridge-proposals/{pid}", json={"decision": "accept", "rationale": "Reviewed"})
    assert ok.status_code == 200 and ok.json()["bridge_id"]
    assert client.post(f"/api/graphs/bridge-proposals/{pid}", json={"decision": "reject", "rationale": "x"}).status_code == 409
    assert len(client.post("/api/graphs/bridges", json={"graph_ids": [paper_gid, code_gid]}).json()["bridges"]) == 1
    assert client.get("/api/graphs/bridge-proposals?graph_ids=").status_code == 400
