"""lineage-v1 (master G5): snapshot-driven staleness for bridges, cards and their dependants (wave 3 Task 5)."""
import sqlite3

import pytest

from geographer.graph_catalog import GraphCatalog
from geographer.lineage import register, state, sweep
from geographer.source import Repository

M_BASE = "def f(x):\n    return g(x)\n\ndef g(x):\n    return x\n"
EDITS = {
    "g body only": "def f(x):\n    return g(x)\n\ndef g(x):\n    return x + 1\n",
    "f signature": "def f(x, y=0):\n    return g(x)\n\ndef g(x):\n    return x\n",
    "f cosmetic": "def f(x):\n    return g(x)  # same code\n\ndef g(x):\n    return x\n",
    "f deleted": "def g(x):\n    return x\n",
}
N_BASE = "def h():\n    return 1\n"


class LineageWorld:
    """Code graph (m.py: f→g; n.py: h), a second code graph, a bridge other:root → entity:f, cards and notes."""

    def __init__(self, tmp_path, note_clauses=(("bridge",),), upstream_cycle=False, new_store_without_fingerprints=False, monkeypatch=None):
        self.tmp = tmp_path
        self.catalog = GraphCatalog(tmp_path / "cat" / "catalog.sqlite")
        self.root = tmp_path / "code"; self.root.mkdir()
        (self.root / "m.py").write_text(M_BASE, encoding="utf-8"); (self.root / "n.py").write_text(N_BASE, encoding="utf-8")
        self.code = self._import(self.root, "code")
        other = tmp_path / "other"; other.mkdir(); (other / "o.py").write_text("def o():\n    return 0\n", encoding="utf-8")
        self.other = self._import(other, "other")
        self.f, self.h = self.entity("m.py.f"), self.entity("n.py.h")
        self.bridge_id = self.catalog.add_bridge(self.other, "root", self.code, f"entity:{self.f}", "reference", "o documents f", [{"t": 1}])
        ground = lambda eid, contract: {"graph_id": self.code, "ref": f"entity:{eid}", "contract": contract}
        register(self.catalog, "card", "discovery_card", [[ground(self.f, "CONTROL_GUARD_INVARIANT")]])
        register(self.catalog, "unrelated_card", "discovery_card", [[ground(self.h, "CONTROL_GUARD_INVARIANT")]])
        names = {"bridge": self.bridge_id, "card": "card", "unrelated_card": "unrelated_card"}
        clauses = [[{"upstream_id": names[n]} for n in clause] for clause in note_clauses]
        if upstream_cycle:
            clauses = [clause + [{"upstream_id": "note:2"}] for clause in clauses]
            register(self.catalog, "note:2", "external", [[{"upstream_id": "note:1"}]])
        register(self.catalog, "note:1", "external", clauses)
        self.baseline_sid = self.catalog.graph(self.code)["snapshot_id"]
        if new_store_without_fingerprints:
            from geographer.store import SnapshotStore
            real = SnapshotStore.fingerprints
            monkeypatch.setattr(SnapshotStore, "fingerprints", lambda s, sid: real(s, sid) if sid == self.baseline_sid else None)

    def _import(self, root, label):
        return self.catalog.import_project(root, Repository.from_directory(root, label), label=label)["graph_id"]

    def entity(self, qualified_name):
        from geographer.store import SnapshotStore
        row = self.catalog.graph(self.code)
        with SnapshotStore(row["code_database"]) as store:
            return next(e.entity_id for e in store.graph(row["snapshot_id"]).entities.values() if e.qualified_name == qualified_name)

    def edit(self, kind):
        (self.root / "m.py").write_text(EDITS[kind], encoding="utf-8")
        return self

    def revert(self):
        (self.root / "m.py").write_text(M_BASE, encoding="utf-8")
        return self

    def reingest(self):
        result = self.catalog.import_project(self.root, Repository.from_directory(self.root, "code"), label="code")
        return result.get("lineage")

    def states(self):
        return {a: state(self.catalog, a) for a in (self.bridge_id, "card", "unrelated_card", "note:1")}


@pytest.fixture
def lineage_world(tmp_path, monkeypatch):
    made = []
    def make(**kw):
        w = LineageWorld(tmp_path / f"w{len(made)}", monkeypatch=monkeypatch, **kw); made.append(w); return w
    (tmp_path).mkdir(exist_ok=True)
    yield make
    for w in made:
        w.catalog.close()


def test_registration_starts_accepted(lineage_world):
    w = lineage_world()
    assert set(w.states().values()) == {"accepted"} and w.catalog.bridge_state(w.bridge_id) == "accepted"


def test_neighbour_only_edit_causes_no_demotion(lineage_world):
    w = lineage_world(); out = w.edit("g body only").reingest()
    assert out is not None and out["passes"] <= 8
    assert w.states()[w.bridge_id] == "accepted"
    assert "demoted_contestable" not in w.states().values()


def test_signature_edit_demotes_hop1_and_quarantines_hop2(lineage_world):
    w = lineage_world(); out = w.edit("f signature").reingest()
    assert state(w.catalog, w.bridge_id) == "demoted_contestable" and state(w.catalog, "note:1") == "suspect_stale"
    assert out["changed"][w.bridge_id] == ("accepted", "demoted_contestable")
    assert out["changed"]["note:1"] == ("accepted", "suspect_stale")
    assert state(w.catalog, "unrelated_card") == "accepted" and "unrelated_card" not in out["changed"]


def test_hop2_is_never_demoted(lineage_world):
    w = lineage_world(); w.edit("f deleted").reingest()
    assert state(w.catalog, w.bridge_id) == "demoted_contestable" and state(w.catalog, "note:1") == "suspect_stale"


def test_second_clause_keeps_artifact_accepted(lineage_world):
    w = lineage_world(note_clauses=[["bridge"], ["card"]]); w.edit("f signature").reingest()
    assert state(w.catalog, "card") == "demoted_contestable"
    assert state(w.catalog, "note:1") == "suspect_stale"   # card also depends on f, so both clauses fail
    w2 = lineage_world(note_clauses=[["bridge"], ["unrelated_card"]]); w2.edit("f signature").reingest()
    assert state(w2.catalog, "note:1") == "accepted"


def test_restoring_the_signature_re_accepts_without_rewrite(lineage_world):
    w = lineage_world(); w.edit("f signature").reingest()
    rows = w.catalog.connection.execute("SELECT * FROM artifact_justifications ORDER BY artifact_id,clause_id,premise_id").fetchall()
    out = w.revert().reingest()
    assert state(w.catalog, w.bridge_id) == "accepted" and state(w.catalog, "note:1") == "accepted"
    assert out["changed"][w.bridge_id] == ("demoted_contestable", "accepted")
    assert w.catalog.connection.execute("SELECT * FROM artifact_justifications ORDER BY artifact_id,clause_id,premise_id").fetchall() == rows


def test_cosmetic_edit_is_noop_for_guard_contract(lineage_world):
    w = lineage_world(); w.edit("f cosmetic").reingest()
    assert set(w.states().values()) == {"accepted"}


def test_cycle_terminates_deterministically(lineage_world):
    w = lineage_world(upstream_cycle=True); out = w.edit("f signature").reingest()
    w2 = lineage_world(upstream_cycle=True); out2 = w2.edit("f signature").reingest()
    assert out["passes"] <= 8 and out["passes"] == out2["passes"]
    notes = lambda o: {k: v for k, v in o["changed"].items() if k.startswith("note:")}
    assert notes(out) == notes(out2) == {"note:1": ("accepted", "suspect_stale"), "note:2": ("accepted", "suspect_stale")}


def test_old_store_without_fingerprints_is_unknown(lineage_world):
    w = lineage_world(new_store_without_fingerprints=True); out = w.edit("f signature").reingest()
    assert w.bridge_id in out["unknown"] and state(w.catalog, w.bridge_id) == "accepted"
    assert state(w.catalog, "note:1") == "accepted"


def test_ledger_rows_and_append_only(lineage_world):
    w = lineage_world(); w.edit("f signature").reingest(); w.revert().reingest()
    rows = w.catalog.connection.execute("SELECT artifact_id,prior_state,next_state,hop FROM revision_ledger ORDER BY recorded_at,event_id").fetchall()
    bridge_rows = [tuple(r)[1:] for r in rows if r[0] == w.bridge_id]
    assert bridge_rows == [("accepted", "demoted_contestable", 1), ("demoted_contestable", "accepted", 1)]
    assert any(r[0] == "note:1" and r[3] >= 2 for r in rows)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        w.catalog.connection.execute("DELETE FROM revision_ledger")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        w.catalog.connection.execute("UPDATE revision_ledger SET hop=9")


def test_unchanged_reingest_does_not_sweep(lineage_world):
    w = lineage_world()
    assert w.reingest() is None  # identical bytes reuse the snapshot: no sweep, no ledger rows
    assert w.catalog.connection.execute("SELECT count(*) FROM revision_ledger").fetchone()[0] == 0


def test_deleting_a_graph_quarantines_dependants_of_removed_bridges(lineage_world):
    w = lineage_world()
    out = w.catalog.delete_graph(w.other)
    assert w.bridge_id in out["bridges_removed"] and state(w.catalog, "note:1") == "suspect_stale"


def test_router_bridges_carry_state(lineage_world):
    from geographer.graph_router import GraphRouter
    w = lineage_world(); w.edit("f signature").reingest()
    rows = GraphRouter(w.catalog).bridges([w.other, w.code])
    assert [r["state"] for r in rows] == ["demoted_contestable"]


def test_register_validates_premises(lineage_world):
    w = lineage_world()
    for bad in ([[]], [], [[{"graph_id": w.code, "ref": "entity:x"}]], [[{"upstream_id": ""}]], [[{"graph_id": w.code, "ref": "../x", "contract": "TOPOLOGICAL_WL3"}]]):
        with pytest.raises(ValueError):
            register(w.catalog, "bad", "external", bad)
    with pytest.raises(ValueError):
        register(w.catalog, "bad", "nonsense", [[{"upstream_id": "card"}]])


def test_sweep_is_callable_directly_and_idempotent(lineage_world):
    w = lineage_world(); w.edit("f signature").reingest()
    sid = w.catalog.graph(w.code)["snapshot_id"]
    again = sweep(w.catalog, w.code, sid, sid)
    assert again["changed"] == {}


def test_hop1_artifact_with_a_demoted_upstream_is_quarantined_not_demoted(lineage_world):
    w = lineage_world()
    register(w.catalog, "mixed", "discovery_card",
             [[{"graph_id": w.code, "ref": f"entity:{w.h}", "contract": "CONTROL_GUARD_INVARIANT"}, {"upstream_id": w.bridge_id}]])
    w.edit("f signature").reingest()
    assert state(w.catalog, w.bridge_id) == "demoted_contestable" and state(w.catalog, "mixed") == "suspect_stale"


def test_edited_claim_text_demotes_a_claim_bound_bridge(tmp_path, lineage_world):
    from test_bridges import paper_db
    w = lineage_world()
    papers = tmp_path / "papers"; papers.mkdir(); (papers / "README.md").write_text("# p\n", encoding="utf-8")
    pgid = w.catalog.import_project(papers, Repository.from_directory(papers, "papers"), label="papers")["graph_id"]
    paper_db(tmp_path / "p.sqlite"); w.catalog.attach_papers(pgid, tmp_path / "p.sqlite")
    bid = w.catalog.add_bridge(pgid, "doc:1#claim:3", w.code, f"entity:{w.h}", "reference", "claim about h", [{"t": 1}])
    sid = w.catalog.graph(pgid)["snapshot_id"]
    assert sweep(w.catalog, pgid, sid, sid)["changed"] == {}  # unchanged claim text
    con = sqlite3.connect(tmp_path / "p.sqlite"); con.execute("UPDATE read_claims SET text='Edited.' WHERE id=3"); con.commit(); con.close()
    out = sweep(w.catalog, pgid, sid, sid)
    assert out["changed"][bid] == ("accepted", "demoted_contestable")


def test_register_card_tracks_card_entities(lineage_world):
    from geographer.discovery import register_card
    w = lineage_world()
    card = dict(card_version="discovery-card-v1", snapshot_id=w.catalog.graph(w.code)["snapshot_id"],
                boundary_bottlenecks=[dict(entity_id=w.f)], surprising_links=[], quotient_cycles=[])
    aid = register_card(w.catalog, w.code, card)
    assert aid.startswith("card:") and state(w.catalog, aid) == "accepted"
    w.edit("f signature").reingest()
    assert state(w.catalog, aid) == "demoted_contestable"
