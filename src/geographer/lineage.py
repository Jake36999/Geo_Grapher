"""Lineage tracking for artifact staleness relative to code snapshots."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from geographer.bridges import parse_ref, resolve_ref
from geographer.drift import OUTCOME, resolve, tier
from geographer.model import canonical, digest
from geographer.store import SnapshotStore

if TYPE_CHECKING:
    from geographer.graph_catalog import GraphCatalog

STATES = ("accepted", "provisional_reanchored", "suspect_stale", "demoted_contestable")
KINDS = ("bridge", "discovery_card", "external")
CONTRACTS = ("STRICT_BYTE_SPAN", "AST_ALPHA_INVARIANT", "CONTROL_GUARD_INVARIANT", "TOPOLOGICAL_WL3")
NOOP, REANCHOR, SUSPECT, HARD, UNKNOWN = "NOOP", "REANCHOR", "SUSPECT", "HARD", "UNKNOWN"
OK = "OK"
CLAUSE_VALUE_ORDER = {HARD: 0, SUSPECT: 1, UNKNOWN: 2, REANCHOR: 3, OK: 4}  # OK last (best)


def bridge_clause(bindings: list[tuple[str, dict]]) -> list[dict]:
    """Make a clause from bridge bindings."""
    clause = []
    for side, b in bindings:
        ref = b["ref"]
        contract = "STRICT_BYTE_SPAN" if "#claim:" in ref else "CONTROL_GUARD_INVARIANT"
        clause.append({
            "graph_id": b["graph_id"],
            "ref": ref,
            "contract": contract,
            "baseline_snapshot_id": b["snapshot_id"],
            "baseline_json": b["fingerprint_json"],
        })
    return clause


def register(catalog: GraphCatalog, artifact_id: str, kind: str, clauses: list[list[dict]]) -> None:
    """Register an artifact with justification clauses."""
    if not isinstance(artifact_id, str) or not 0 < len(artifact_id) <= 300:
        raise ValueError("Invalid artifact_id")
    if kind not in KINDS:
        raise ValueError("Invalid kind")
    if not clauses or not all(clauses):
        raise ValueError("Invalid clauses")

    # Validate premises
    for clause in clauses:
        for premise in clause:
            if "upstream_id" in premise:
                if not isinstance(premise["upstream_id"], str) or not premise["upstream_id"]:
                    raise ValueError("Invalid upstream_id")
            elif all(k in premise for k in ("graph_id", "ref", "contract")):
                try:
                    parse_ref(premise["ref"])
                except ValueError as e:
                    if "BRIDGE_REF_INVALID" in str(e):
                        raise ValueError("Invalid ref") from e
                if premise["contract"] not in CONTRACTS:
                    raise ValueError("Invalid contract")
            else:
                raise ValueError("Invalid premise")

    # Transaction handling
    own_transaction = not catalog.connection.in_transaction
    try:
        if own_transaction:
            with catalog.lock:
                catalog.connection.execute("BEGIN IMMEDIATE")

        now = datetime.now(timezone.utc).isoformat()

        # Register artifact state
        catalog.connection.execute("""
            INSERT OR IGNORE INTO artifact_states(artifact_id, artifact_kind, state, updated_at)
            VALUES (?, ?, 'accepted', ?)
        """, (artifact_id, kind, now))

        # Register justifications
        for ci, clause in enumerate(clauses):
            clause_id = f"c{ci:03d}"
            for premise in clause:
                if "upstream_id" in premise:
                    premise_id = digest("upstream", None, None, premise["upstream_id"])
                    catalog.connection.execute("""
                        INSERT OR IGNORE INTO artifact_justifications(
                            artifact_id, clause_id, premise_id,
                            premise_kind, upstream_id
                        ) VALUES (?, ?, ?, 'upstream', ?)
                    """, (artifact_id, clause_id, premise_id, premise["upstream_id"]))
                else:
                    graph_id, ref = premise["graph_id"], premise["ref"]
                    premise_id = digest("ground", graph_id, ref, None)
                    if "baseline_snapshot_id" not in premise:
                        premise["baseline_snapshot_id"] = catalog.graph(graph_id)["snapshot_id"]
                    if "baseline_json" not in premise:
                        premise["baseline_json"] = "{}"
                    catalog.connection.execute("""
                        INSERT OR IGNORE INTO artifact_justifications(
                            artifact_id, clause_id, premise_id,
                            premise_kind, graph_id, ref, contract, baseline_snapshot_id, baseline_json
                        ) VALUES (?, ?, ?, 'ground', ?, ?, ?, ?, ?)
                    """, (
                        artifact_id, clause_id, premise_id,
                        graph_id, ref, premise["contract"],
                        premise["baseline_snapshot_id"], premise["baseline_json"]
                    ))

        if own_transaction:
            catalog.connection.commit()
    except Exception:
        if own_transaction:
            catalog.connection.rollback()
        raise


def state(catalog: GraphCatalog, artifact_id: str) -> str:
    """Get artifact state."""
    row = catalog.connection.execute(
        "SELECT state FROM artifact_states WHERE artifact_id = ?", (artifact_id,)
    ).fetchone()
    return row["state"] if row else "accepted"


def sweep(catalog: GraphCatalog, graph_id: str, old_sid: str | None, new_sid: str | None) -> dict:
    """lineage-v1 sweep after ``graph_id`` moved from ``old_sid`` to ``new_sid`` (None: the graph was deleted).

    Hop-1 artifacts (a ground premise in ``graph_id``) are re-evaluated from their best clause; then
    all-upstream artifacts iterate to a fixpoint (≤ 8 passes) over the working map. One transaction.
    """
    with catalog.lock:
        rows = catalog.connection.execute(
            "SELECT artifact_id,clause_id,premise_kind,graph_id,ref,contract,baseline_snapshot_id,baseline_json,upstream_id "
            "FROM artifact_justifications ORDER BY artifact_id,clause_id,premise_id").fetchall()
        initial = {r["artifact_id"]: r["state"] for r in catalog.connection.execute("SELECT artifact_id,state FROM artifact_states")}
    working = dict(initial)
    clauses: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        clauses[r["artifact_id"]][r["clause_id"]].append(dict(r))
    hop1 = sorted(a for a, cs in clauses.items() if any(p["premise_kind"] == "ground" and p["graph_id"] == graph_id for c in cs.values() for p in c))
    upstream_only = sorted(a for a, cs in clauses.items() if all(p["premise_kind"] == "upstream" for c in cs.values() for p in c))

    current: dict[str, str | None] = {}
    def current_sid(gid):
        if gid not in current:
            try:
                current[gid] = catalog.graph(gid)["snapshot_id"]
            except ValueError:
                current[gid] = None  # graph deleted
        return current[gid]

    stores: dict[tuple[str, str, str], tuple | None] = {}
    def drift_data(gid, base, new):
        key = (gid, base, new)
        if key not in stores:
            with SnapshotStore(catalog.graph(gid)["code_database"]) as store:
                fb, fn = store.fingerprints(base), store.fingerprints(new)
                if fb is None or fn is None:
                    stores[key] = None
                else:
                    be, ne = store.graph(base).entities, store.graph(new).entities
                    stores[key] = (fb, fn, be, ne, resolve(fb, fn, be, ne))
        return stores[key]

    def ground(p) -> str:
        gid, ref = p["graph_id"], p["ref"]
        if current_sid(gid) is None and not _exists(catalog, gid):
            return HARD
        kind, parts = parse_ref(ref)
        if kind == "root":
            return NOOP
        if kind == "entity":
            base, new = p["baseline_snapshot_id"], current_sid(gid)
            if not base or not new:
                return UNKNOWN
            if base == new:
                return NOOP
            data = drift_data(gid, base, new)
            if data is None:
                return UNKNOWN
            fb, fn, be, ne, mapping = data
            eid = parts["entity"]
            if eid not in be:
                return UNKNOWN
            cp, rule = mapping[eid]
            if cp is None:
                t = "MISSING"
            elif fn.get(cp) is None or fb.get(eid) is None:
                t = "UNKNOWN"
            else:
                t = tier(fb[eid], fn[cp], be[eid].start_line, ne[cp].start_line, rule == "unique_ast")
            return OUTCOME[t][p["contract"]]
        try:
            resolved = resolve_ref(catalog, gid, ref)
        except ValueError:
            return HARD
        if kind == "claim":
            before = json.loads(p["baseline_json"] or "{}").get("claim_text_sha256")
            return NOOP if before and before == json.loads(resolved["fingerprint_json"]).get("claim_text_sha256") else HARD
        return NOOP

    ground_cache: dict[tuple, str] = {}
    def clause_value(premises) -> str:
        values = []
        for p in premises:
            if p["premise_kind"] == "upstream":
                values.append(OK if working.get(p["upstream_id"], "demoted_contestable") == "accepted" else SUSPECT)
            else:
                key = (p["graph_id"], p["ref"], p["contract"], p["baseline_snapshot_id"], p["baseline_json"])
                if key not in ground_cache:
                    ground_cache[key] = ground(p)
                values.append({NOOP: OK}.get(ground_cache[key], ground_cache[key]))
        for v in (HARD, SUSPECT, UNKNOWN, REANCHOR):
            if v in values:
                return v
        return OK

    unknown, best, hop_of = set(), {}, {}
    to_state = {OK: "accepted", REANCHOR: "provisional_reanchored", SUSPECT: "suspect_stale", HARD: "demoted_contestable"}
    for aid in hop1:
        value = max((clause_value(ps) for _, ps in sorted(clauses[aid].items())), key=CLAUSE_VALUE_ORDER.__getitem__)
        best[aid] = value; hop_of[aid] = 1
        if value == UNKNOWN:
            unknown.add(aid)
        else:
            working[aid] = to_state[value]

    passes = 0
    bad = ("suspect_stale", "demoted_contestable")
    for index in range(8):
        if not upstream_only:
            break
        passes = index + 1; moved = False
        for aid in upstream_only:
            cs = [ps for _, ps in sorted(clauses[aid].items())]
            if all(any(working.get(p["upstream_id"], "demoted_contestable") in bad for p in ps) for ps in cs):
                nxt = "suspect_stale"
            elif any(all(working.get(p["upstream_id"], "demoted_contestable") == "accepted" for p in ps) for ps in cs):
                nxt = "accepted"
            else:
                nxt = working.get(aid, "accepted")
            if working.get(aid) != nxt:
                working[aid] = nxt; hop_of[aid] = 2 + index; moved = True
        if not moved:
            break

    changed = {a: (initial.get(a, "accepted"), working[a]) for a in sorted(working) if working[a] != initial.get(a, "accepted")}
    if changed:
        now = datetime.now(timezone.utc).isoformat()
        with catalog.lock:
            owned = not catalog.connection.in_transaction
            try:
                if owned:
                    catalog.connection.execute("BEGIN IMMEDIATE")
                for aid, (prior, nxt) in changed.items():
                    catalog.connection.execute("UPDATE artifact_states SET state=?,updated_at=? WHERE artifact_id=?", (nxt, now, aid))
                    n = catalog.connection.execute("SELECT count(*) FROM revision_ledger WHERE artifact_id=?", (aid,)).fetchone()[0]
                    catalog.connection.execute("INSERT INTO revision_ledger VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (digest("lineage-v1", aid, graph_id, old_sid, new_sid, prior, nxt, n), aid, graph_id, old_sid, new_sid,
                         prior, nxt, hop_of.get(aid, 2), canonical({"best": best.get(aid), "passes": passes}), now))
                if owned:
                    catalog.connection.commit()
            except BaseException:
                if owned:
                    catalog.connection.rollback()
                raise
    return {"changed": changed, "passes": passes, "unknown": sorted(unknown)}


def _exists(catalog, gid) -> bool:
    try:
        catalog.graph(gid)
        return True
    except ValueError:
        return False
