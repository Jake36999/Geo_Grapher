import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore

ROOT = Path(__file__).resolve().parents[1]


def fp(tmp_path, files, stage=3, db=None):
    """Ingest files at stage 3; return (store, sid, {qualname: fingerprint row})."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8", newline="")
    repo = Repository.from_directory(tmp_path, "repo")
    store = SnapshotStore(db if db is not None else ":memory:")
    sid = ingest(store, [repo], stage=stage)["snapshot_id"]
    rows = store.fingerprints(sid) or {}
    graph = store.graph(sid)
    named = {}
    for eid, row in rows.items():
        qn = graph.entities[eid].qualified_name
        named[qn.removeprefix("repo.").replace(".py.", ".")] = row
    return store, sid, named


def drop_table_copy(store, dest, table):
    target = sqlite3.connect(str(dest))
    store.connection.backup(target)
    for (name,) in target.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE ?", (f"immutable_{table}_%",)).fetchall():
        target.execute(f"DROP TRIGGER {name}")
    target.execute(f"DROP TABLE {table}")
    target.commit()
    target.close()


def test_cosmetic_edit_keeps_signature_guard_and_ast(tmp_path):
    a = fp(tmp_path / "a", {"m.py": "def f(x):\n    # c1\n    if x > 1:\n        return g(x)\n\ndef g(y):\n    return y\n"})[2]
    b = fp(tmp_path / "b", {"m.py": "def f(x):\n    # c2 changed\n    if x > 1:\n        return g(x)\n\ndef g(y):\n    return y\n"})[2]
    for k in ("signature_hash", "ts_guard_hash", "ast_body_hash", "exact_out_edges_hash"):
        assert a["m.f"][k] == b["m.f"][k]
        assert a["m.f"][k] is not None
    assert a["m.f"]["span_sha256"] != b["m.f"]["span_sha256"]


def test_local_rename_keeps_guard_hash_but_guard_change_does_not(tmp_path):
    base = fp(tmp_path / "a", {"m.py": "def f(x):\n    if x > 1:\n        return x\n"})[2]["m.f"]
    renamed = fp(tmp_path / "b", {"m.py": "def f(z):\n    if z > 1:\n        return z\n"})[2]["m.f"]
    changed = fp(tmp_path / "c", {"m.py": "def f(x):\n    if x >= 1:\n        return x\n"})[2]["m.f"]
    assert base["ts_guard_hash"] == renamed["ts_guard_hash"] and base["ts_guard_hash"] != changed["ts_guard_hash"]
    assert base["signature_hash"] != renamed["signature_hash"]  # parameter name is part of the signature


def test_decorator_change_changes_signature(tmp_path):
    a = fp(tmp_path / "a", {"m.py": "def f():\n    pass\n"})[2]["m.f"]
    b = fp(tmp_path / "b", {"m.py": "import functools\n@functools.cache\ndef f():\n    pass\n"})[2]["m.f"]
    assert a["signature_hash"] != b["signature_hash"]


def test_unparseable_file_and_non_code_entities_get_no_crash(tmp_path):
    store, sid, fps = fp(tmp_path, {"bad.py": "def (:\n", "ok.py": "class C: pass\n", "README.md": "# t\n"})
    assert "ok.C" in fps and fps["ok.C"]["ast_body_hash"] is None
    assert fps["ok.C"]["signature_hash"] is not None and fps["ok.C"]["span_sha256"] is not None
    kinds = {r[0] for r in store.connection.execute(
        "SELECT e.kind FROM entity_fingerprints f JOIN entities e USING(snapshot_id, entity_id)")}
    assert kinds <= {"function", "method", "class"}


def test_fingerprints_are_immutable_after_publish(tmp_path):
    store, sid, _ = fp(tmp_path, {"m.py": "def f():\n    pass\n"})
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        store.connection.execute("DELETE FROM entity_fingerprints WHERE snapshot_id=?", (sid,))


def test_old_store_reports_not_computed(tmp_path):
    store, sid, _ = fp(tmp_path / "src", {"m.py": "def f():\n    pass\n"}, db=tmp_path / "new.sqlite")
    copy = tmp_path / "old.sqlite"
    drop_table_copy(store, copy, "entity_fingerprints")
    reopened = SnapshotStore(copy)  # re-creates an empty addendum table
    assert reopened.fingerprints(sid) is None


def test_addendum_idempotent_on_reopen(tmp_path):
    store, sid, fps = fp(tmp_path / "src", {"m.py": "def f():\n    pass\n"}, db=tmp_path / "s.sqlite")
    path = Path(store.connection.execute("PRAGMA database_list").fetchone()[2])
    second = SnapshotStore(path)  # concurrent open while `store` is still open
    assert second.fingerprints(sid) == store.fingerprints(sid) and len(fps) == 1


def test_guard_kinds_and_elif_and_nested_defs():
    import ast
    from geographer.fingerprints import guard_clauses
    src = ("def f(a, b):\n    if a:\n        pass\n    elif b:\n        pass\n    while a:\n        pass\n"
           "    for i in b:\n        pass\n    assert a\n    y = [i for i in b if i]\n    z = a if b else 1\n"
           "    try:\n        pass\n    except KeyError:\n        pass\n    with open(a) as h:\n        pass\n"
           "    match a:\n        case 1 if b:\n            pass\n"
           "    def inner():\n        if a:\n            pass\n")
    node = ast.parse(src).body[0]
    clauses = guard_clauses(node, {"a", "b", "i", "y", "z", "h"}, src.split("\n"))
    assert [c[0] for c in clauses] == ["if", "elif", "while", "for_iter", "assert", "comp_if", "ifexp",
                                       "except_type", "with_item", "match_case_guard"]
    assert all(c[1] == 0 for c in clauses)


def test_span_sha256_uses_inclusive_lines_and_stored_endings():
    import hashlib
    from geographer.fingerprints import span_sha256
    raw = b"a\r\nb\r\nc\nd\n"
    assert span_sha256(raw, 2, 3) == hashlib.sha256(b"b\r\nc\n").hexdigest()


CHILD = r"""
import sys, tempfile, pathlib
sys.path.insert(0, r'%s')
from tests.test_fingerprints import fp
from geographer.model import canonical
d = pathlib.Path(tempfile.mkdtemp())
rows = fp(d, {"m.py": "def f(x):\n    if x > 1:\n        return g(x)\n\ndef g(y):\n    return y\n\nclass C:\n    def m(self):\n        return f(1)\n"})[2]
sys.stdout.write(canonical(rows))
"""


def test_fingerprints_deterministic_across_processes():
    outs = []
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]))
        outs.append(subprocess.run([sys.executable, "-c", CHILD % str(ROOT)], env=env, capture_output=True, check=True).stdout)
    assert outs[0] and outs[0] == outs[1]
    assert set(json.loads(outs[0])) >= {"m.f", "m.g", "m.C", "m.C.m"}


def test_merge_carries_fingerprints(tmp_path):
    s1, sid1, _ = fp(tmp_path / "a", {"m.py": "def f(x):\n    if x:\n        return 1\n"})
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "n.py").write_text("def h():\n    pass\n")
    s2 = SnapshotStore()
    sid2 = ingest(s2, [Repository.from_directory(tmp_path / "b", "other")], stage=3)["snapshot_id"]
    target = SnapshotStore()
    merged = target.merge([(s1, sid1), (s2, sid2)], stage=3)
    rows = target.fingerprints(merged)
    assert len(rows) == len(s1.fingerprints(sid1)) + len(s2.fingerprints(sid2))
    for eid, row in s1.fingerprints(sid1).items():
        assert rows[eid]["signature_hash"] == row["signature_hash"] and rows[eid]["ts_guard_hash"] == row["ts_guard_hash"]
        assert rows[eid]["span_sha256"] == row["span_sha256"]
