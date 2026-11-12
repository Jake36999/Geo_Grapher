"""Cross-snapshot identity and drift classifier (master G3, as amended by ruling W2-5)."""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Literal, Optional, Tuple

from .model import Entity
from .store import SnapshotStore

Tier = Literal[
    "IDENTICAL",
    "LINE_SHIFT",
    "COSMETIC",
    "BODY_REFACTOR",
    "NEIGHBOUR_DRIFT",
    "CONTRACT_CHANGE",
    "MOVED",
    "MISSING",
    "UNKNOWN",
]
Outcome = Literal["NOOP", "REANCHOR", "SUSPECT", "HARD", "UNKNOWN"]
Contract = Literal[
    "STRICT_BYTE_SPAN",
    "AST_ALPHA_INVARIANT",
    "CONTROL_GUARD_INVARIANT",
    "TOPOLOGICAL_WL3",
]

OUTCOME: dict[Tier, dict[Contract, Outcome]] = {
    "IDENTICAL": {
        "STRICT_BYTE_SPAN": "NOOP",
        "AST_ALPHA_INVARIANT": "NOOP",
        "CONTROL_GUARD_INVARIANT": "NOOP",
        "TOPOLOGICAL_WL3": "NOOP",
    },
    "LINE_SHIFT": {
        "STRICT_BYTE_SPAN": "REANCHOR",
        "AST_ALPHA_INVARIANT": "NOOP",
        "CONTROL_GUARD_INVARIANT": "NOOP",
        "TOPOLOGICAL_WL3": "NOOP",
    },
    "COSMETIC": {
        "STRICT_BYTE_SPAN": "REANCHOR",
        "AST_ALPHA_INVARIANT": "NOOP",
        "CONTROL_GUARD_INVARIANT": "NOOP",
        "TOPOLOGICAL_WL3": "NOOP",
    },
    "BODY_REFACTOR": {
        "STRICT_BYTE_SPAN": "HARD",
        "AST_ALPHA_INVARIANT": "HARD",
        "CONTROL_GUARD_INVARIANT": "NOOP",
        "TOPOLOGICAL_WL3": "NOOP",
    },
    "NEIGHBOUR_DRIFT": {
        "STRICT_BYTE_SPAN": "NOOP",
        "AST_ALPHA_INVARIANT": "NOOP",
        "CONTROL_GUARD_INVARIANT": "NOOP",
        "TOPOLOGICAL_WL3": "SUSPECT",
    },
    "CONTRACT_CHANGE": {
        "STRICT_BYTE_SPAN": "HARD",
        "AST_ALPHA_INVARIANT": "HARD",
        "CONTROL_GUARD_INVARIANT": "HARD",
        "TOPOLOGICAL_WL3": "HARD",
    },
    "MOVED": {
        "STRICT_BYTE_SPAN": "REANCHOR",
        "AST_ALPHA_INVARIANT": "NOOP",
        "CONTROL_GUARD_INVARIANT": "NOOP",
        "TOPOLOGICAL_WL3": "SUSPECT",
    },
    "MISSING": {
        "STRICT_BYTE_SPAN": "HARD",
        "AST_ALPHA_INVARIANT": "HARD",
        "CONTROL_GUARD_INVARIANT": "HARD",
        "TOPOLOGICAL_WL3": "HARD",
    },
    "UNKNOWN": {
        "STRICT_BYTE_SPAN": "UNKNOWN",
        "AST_ALPHA_INVARIANT": "UNKNOWN",
        "CONTROL_GUARD_INVARIANT": "UNKNOWN",
        "TOPOLOGICAL_WL3": "UNKNOWN",
    },
}


def resolve(
    base: dict[str, dict],
    new: dict[str, dict],
    base_entities: dict[str, Entity],
    new_entities: dict[str, Entity],
) -> dict[str, tuple[str | None, str]]:
    """Map each base entity id to (new entity id or None, rule)."""
    qn_index: dict[tuple[str, str, str], list[str]] = {}
    for eid, ent in sorted(new_entities.items()):
        key = (ent.repo_id, ent.qualified_name, ent.kind)
        qn_index.setdefault(key, []).append(eid)

    ast_index: dict[tuple[str, str, str], list[str]] = {}
    new_ast_counts: Counter[str] = Counter()
    for eid, fp in sorted(new.items()):
        h = fp.get("ast_body_hash")
        if h is not None:
            ent = new_entities[eid]
            ast_index.setdefault((ent.repo_id, ent.kind, h), []).append(eid)
            new_ast_counts[h] += 1

    base_ast_counts = Counter(
        fp.get("ast_body_hash") for fp in base.values() if fp.get("ast_body_hash")
    )

    result: dict[str, tuple[str | None, str]] = {}
    for eid in sorted(base_entities):
        bent = base_entities[eid]

        if eid in new_entities:
            result[eid] = (eid, "same_id")
            continue

        qkey = (bent.repo_id, bent.qualified_name, bent.kind)
        if qkey in qn_index and len(qn_index[qkey]) == 1:
            result[eid] = (qn_index[qkey][0], "same_qualname")
            continue

        fp = base.get(eid)
        if fp is not None:
            h = fp.get("ast_body_hash")
            if (
                h is not None
                and base_ast_counts.get(h, 0) == 1
                and new_ast_counts.get(h, 0) == 1
            ):
                akey = (bent.repo_id, bent.kind, h)
                candidates = ast_index.get(akey, [])
                if len(candidates) == 1:
                    result[eid] = (candidates[0], "unique_ast")
                    continue

        result[eid] = (None, "none")
    return result


def tier(
    fb: dict | None,
    fn: dict | None,
    start_b: int | None,
    start_n: int | None,
    moved: bool,
) -> Tier:
    """Evaluate drift tier from two fingerprint rows and location info."""
    if fn is None:
        return "MISSING"
    if fb is None:
        return "UNKNOWN"
    if moved:
        return "MOVED"
    if (
        fb.get("signature_hash") != fn.get("signature_hash")
        or fb.get("ts_guard_hash") != fn.get("ts_guard_hash")
        or fb.get("exact_out_edges_hash") != fn.get("exact_out_edges_hash")
    ):
        return "CONTRACT_CHANGE"
    if fb.get("ast_body_hash") != fn.get("ast_body_hash"):
        return "BODY_REFACTOR"
    if fb.get("span_sha256") != fn.get("span_sha256"):
        return "COSMETIC"
    if start_b != start_n:
        return "LINE_SHIFT"
    if fb.get("wl_3hop_hash") != fn.get("wl_3hop_hash"):
        return "NEIGHBOUR_DRIFT"
    return "IDENTICAL"


def drift_report(
    store_a: SnapshotStore,
    sid_a: str,
    store_b: SnapshotStore,
    sid_b: str,
) -> dict:
    """Produce a drift report between two snapshots.

    Returns ``{counts: {tier: n}, entities: [{entity_id, counterpart, rule, tier}]}``
    sorted by ``entity_id``.
    """
    graph_a = store_a.graph(sid_a)
    graph_b = store_b.graph(sid_b)
    base_entities = graph_a.entities
    new_entities = graph_b.entities

    base_fp_raw = store_a.fingerprints(sid_a)
    new_fp_raw = store_b.fingerprints(sid_b)

    # If either snapshot has no fingerprint table at all (G1 absence), every
    # entity is UNKNOWN.
    if base_fp_raw is None or new_fp_raw is None:
        rows = [
            {"entity_id": eid, "counterpart": None, "rule": "none", "tier": "UNKNOWN"}
            for eid in sorted(base_entities)
        ]
        return {"counts": {"UNKNOWN": len(rows)}, "entities": rows}

    base_fp: dict[str, dict] = base_fp_raw
    new_fp: dict[str, dict] = new_fp_raw

    mapping = resolve(base_fp, new_fp, base_entities, new_entities)

    rows: list[dict] = []
    for eid in sorted(base_entities):
        counterpart, rule = mapping[eid]
        fb = base_fp.get(eid)
        fn = new_fp.get(counterpart) if counterpart else None
        start_b = base_entities[eid].start_line
        start_n = new_entities[counterpart].start_line if counterpart else None
        # G3 order 2: a counterpart that exists but has no fingerprint row is UNKNOWN, not MISSING.
        t = "UNKNOWN" if counterpart and fn is None else tier(fb, fn, start_b, start_n, rule == "unique_ast")
        rows.append(
            {
                "entity_id": eid,
                "counterpart": counterpart,
                "rule": rule,
                "tier": t,
            }
        )

    counts = dict(Counter(r["tier"] for r in rows))
    return {"counts": counts, "entities": rows}
