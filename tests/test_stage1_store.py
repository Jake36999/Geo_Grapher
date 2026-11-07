import json
import sqlite3
import pytest

from geographer.store import PublicationError, SnapshotStore


@pytest.mark.parametrize("corruption", ["evidence", "depth", "lifting", "endpoint", "hyperedge"])
def test_publication_rejects_corruption(extract, corruption):
    graph, store, report = extract({"a.py": 'def f():\n """documentation"""\n pass\ndef g(): f()\n'}, publish=False)
    sid = report["snapshot_id"]
    c = store.connection
    if corruption == "evidence":
        c.execute("DELETE FROM evidence")
    elif corruption == "depth":
        c.execute("UPDATE entities SET depth=depth+1 WHERE kind='function'")
    elif corruption == "lifting":
        c.execute("UPDATE entities SET ancestors_binary_lifting_json='[\"missing\"]' WHERE kind='function'")
    elif corruption == "endpoint":
        c.execute("UPDATE relationships SET source_id=source_subject_id")
        # Source g may be a leaf; use known documented nonleaf target f instead.
        c.execute("UPDATE relationships SET target_id=target_subject_id")
    else:
        c.execute("UPDATE documentary_incidences SET fragment_id=entity_id")
    c.commit()
    with pytest.raises(PublicationError):
        store.publish(sid)
    assert c.execute("SELECT status FROM snapshot_sets").fetchone()[0] == "building"


def test_direct_sql_constraints_and_snapshot_immutability(extract):
    graph, store, report = extract({"a.py": "def f(): pass\nf()\n"})
    assert store.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    for statement in ["UPDATE entities SET qualified_name='tampered'", "DELETE FROM evidence", "UPDATE snapshot_sets SET status='building'"]:
        with pytest.raises(sqlite3.IntegrityError):
            with store.connection:
                store.connection.execute(statement)
    with SnapshotStore() as fresh:
        with pytest.raises(sqlite3.IntegrityError):
            fresh.connection.execute("INSERT INTO snapshot_sets VALUES ('x','bad','building','now','{}')")


def test_failed_build_is_not_queryable(extract):
    _, store, report = extract({"a.py": "pass"}, publish=False)
    with pytest.raises(ValueError, match="unpublished"):
        store.graph(report["snapshot_id"])


def test_reproducible_graph_and_preserved_snapshot_content(extract):
    files = {"a.py": "def f(): pass\ndef g(): f()\n", "notes.md": "f and g\n"}
    g1, s1, r1 = extract(files)
    g2, s2, r2 = extract(dict(reversed(list(files.items()))))
    assert r1["snapshot_id"] == r2["snapshot_id"]
    a, b = s1.export(r1["snapshot_id"]), s2.export(r2["snapshot_id"])
    a["tables"]["snapshot_sets"][0].pop("created_at")
    b["tables"]["snapshot_sets"][0].pop("created_at")
    assert a == b


def test_disjoint_merge_preserves_original_facts(extract):
    from dataclasses import asdict
    g1, s1, r1 = extract({'a.py': 'def f(): pass\ndef g(): f()\n'}, repo_id='first')
    g2, s2, r2 = extract({'a.py': 'def f(): pass\ndef g(): f()\n'}, repo_id='second')
    with SnapshotStore() as merged:
        sid=merged.merge([(s1,r1['snapshot_id']),(s2,r2['snapshot_id'])])
        result=merged.graph(sid)
        for original in [g1,g2]:
            for rid,r in original.relationships.items():
                assert asdict(result.relationships[rid])==asdict(r)
            for eid,e in original.evidence.items():
                assert asdict(result.evidence[eid])==asdict(e)
        assert not merged.validate(sid)
