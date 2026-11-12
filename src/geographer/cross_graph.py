"""Cross-graph fingerprint diff, quotient-cycle delta and catalog clone join."""
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

import sqlite3

from geographer.discovery import quotient_cycles
from geographer.store import SnapshotStore


CLASSES = (
    "EXACT_AST_SURVIVOR",
    "CONTRACT_PRESERVING_REFACTOR",
    "TOPOLOGICAL_ROLE_ANALOG",
    "SIGNATURE_OR_GUARD_DRIFT",
    "STRATUM_EXCLUSIVE"
)


def diff_rows(
    rows_a: dict[str, dict],
    rows_b: dict[str, dict]
) -> dict:
    """Diff entity rows across two graphs."""
    unmatched_a = dict(rows_a)
    unmatched_b = dict(rows_b)
    pairs = []
    class_counts = defaultdict(int)

    passes = [
        ("EXACT_AST_SURVIVOR", lambda r: (r["kind"], r["ast_body_hash"])),
        ("CONTRACT_PRESERVING_REFACTOR", lambda r: (r["kind"], r["signature_hash"], r["ts_guard_hash"])),
        ("TOPOLOGICAL_ROLE_ANALOG", lambda r: (r["kind"], r["wl_3hop_hash"])),
        ("SIGNATURE_OR_GUARD_DRIFT", lambda r: (r["kind"], r["qualified_name"].split(".")[-1]))
    ]

    for cls, key_fn in passes:
        bucket_a = defaultdict(list)
        bucket_b = defaultdict(list)

        for eid, row in unmatched_a.items():
            try:
                key = key_fn(row)
                if None not in key:
                    bucket_a[key].append(eid)
            except (KeyError, AttributeError):
                continue

        for eid, row in unmatched_b.items():
            try:
                key = key_fn(row)
                if None not in key:
                    bucket_b[key].append(eid)
            except (KeyError, AttributeError):
                continue

        for key in sorted(bucket_a.keys(), key=repr):
            if key in bucket_b and len(bucket_a[key]) == 1 and len(bucket_b[key]) == 1:
                eid_a = bucket_a[key][0]
                eid_b = bucket_b[key][0]
                
                pairs.append({
                    "class": cls,
                    "entity_a": eid_a,
                    "entity_b": eid_b,
                    "qualified_name_a": unmatched_a[eid_a]["qualified_name"],
                    "qualified_name_b": unmatched_b[eid_b]["qualified_name"]
                })
                
                del unmatched_a[eid_a]
                del unmatched_b[eid_b]
                class_counts[cls] += 1

    for eid_a in unmatched_a:
        class_counts["STRATUM_EXCLUSIVE"] += 1
    for eid_b in unmatched_b:
        class_counts["STRATUM_EXCLUSIVE"] += 1
        
    pairs.sort(key=lambda p: (CLASSES.index(p["class"]), p["entity_a"], p["entity_b"]))
    
    return {
        "classes": {k: v for k, v in class_counts.items() if v > 0},
        "pairs": pairs,
        "exclusive_a": sorted(unmatched_a.keys()),
        "exclusive_b": sorted(unmatched_b.keys())
    }


def quotient_cycle_delta(
    cycles_a: list[dict],
    cycles_b: list[dict]
) -> dict:
    """Compute delta between quotient cycle sets."""
    entries = []
    counts = defaultdict(int)
    
    set_a = [set(c["member_rel_paths"]) for c in cycles_a]
    set_b = [set(c["member_rel_paths"]) for c in cycles_b]
    
    candidates = []
    for i, paths_a in enumerate(set_a):
        for j, paths_b in enumerate(set_b):
            intersection = len(paths_a & paths_b)
            union = len(paths_a | paths_b)
            if union > 0:
                jaccard = intersection / union
                if jaccard >= 0.5:
                    candidates.append((jaccard, i, j, paths_a, paths_b))
                    
    candidates.sort(key=lambda x: (-x[0], tuple(sorted(x[3])), tuple(sorted(x[4]))))
    
    matched_a = set()
    matched_b = set()
    
    for _, i, j, paths_a, paths_b in candidates:
        if i not in matched_a and j not in matched_b:
            matched_a.add(i)
            matched_b.add(j)
            
            qcics_a = round(cycles_a[i]["qcics"], 6)
            qcics_b = round(cycles_b[j]["qcics"], 6)
            
            if qcics_b < 0.95 * qcics_a:
                state = "COUPLING_REDUCED"
            elif qcics_b > 1.05 * qcics_a:
                state = "COUPLING_INCREASED"
            else:
                state = "INVARIANT"
                
            entries.append({
                "state": state,
                "rel_paths_a": sorted(paths_a),
                "rel_paths_b": sorted(paths_b),
                "qcics_a": qcics_a,
                "qcics_b": qcics_b
            })
            counts[state] += 1
    
    for i in range(len(cycles_a)):
        if i not in matched_a:
            entries.append({
                "state": "CYCLE_DISSOLVED",
                "rel_paths_a": sorted(set_a[i]),
                "rel_paths_b": None,
                "qcics_a": round(cycles_a[i]["qcics"], 6),
                "qcics_b": None
            })
            counts["CYCLE_DISSOLVED"] += 1
            
    for j in range(len(cycles_b)):
        if j not in matched_b:
            entries.append({
                "state": "CYCLE_INTRODUCED",
                "rel_paths_a": None,
                "rel_paths_b": sorted(set_b[j]),
                "qcics_a": None,
                "qcics_b": round(cycles_b[j]["qcics"], 6)
            })
            counts["CYCLE_INTRODUCED"] += 1
            
    entries.sort(key=lambda e: (e["state"], e["rel_paths_a"] or e["rel_paths_b"]))
    
    return {
        "entries": entries,
        "counts": {k: v for k, v in counts.items() if v > 0}
    }


def diff_graphs(catalog, graph_a: str, graph_b: str) -> dict:
    """Diff two graphs in a catalog."""
    def load_graph(gid):
        row = catalog.graph(gid)
        store = SnapshotStore(row["code_database"])
        try:
            fps = store.fingerprints(row["snapshot_id"])
            if fps is None:
                raise ValueError(f"FINGERPRINTS_NOT_COMPUTED: {gid}")
            entities = store.graph(row["snapshot_id"]).entities
            cycles = quotient_cycles(store, row["snapshot_id"])
            return fps, entities, cycles
        finally:
            store.close()
            
    fps_a, entities_a, cycles_a = load_graph(graph_a)
    fps_b, entities_b, cycles_b = load_graph(graph_b)
    
    valid_kinds = {"function", "method", "class"}
    
    rows_a = {}
    for eid, fp in fps_a.items():
        if eid in entities_a and entities_a[eid].kind in valid_kinds:
            entity = entities_a[eid]
            rows_a[eid] = {
                "kind": entity.kind,
                "qualified_name": entity.qualified_name,
                "ast_body_hash": fp.get("ast_body_hash"),
                "signature_hash": fp.get("signature_hash"),
                "ts_guard_hash": fp.get("ts_guard_hash"),
                "wl_3hop_hash": fp.get("wl_3hop_hash"),
                "rel_path": entity.rel_path,
                "start_line": entity.start_line
            }
            
    rows_b = {}
    for eid, fp in fps_b.items():
        if eid in entities_b and entities_b[eid].kind in valid_kinds:
            entity = entities_b[eid]
            rows_b[eid] = {
                "kind": entity.kind,
                "qualified_name": entity.qualified_name,
                "ast_body_hash": fp.get("ast_body_hash"),
                "signature_hash": fp.get("signature_hash"),
                "ts_guard_hash": fp.get("ts_guard_hash"),
                "wl_3hop_hash": fp.get("wl_3hop_hash"),
                "rel_path": entity.rel_path,
                "start_line": entity.start_line
            }
            
    diff_result = diff_rows(rows_a, rows_b)
    delta = quotient_cycle_delta(cycles_a, cycles_b)
    
    diff_result.update({
        "graph_a": graph_a,
        "graph_b": graph_b,
        "quotient_cycle_delta": delta
    })
    
    return diff_result


def clone_pairs(catalog, graph_ids: list[str], limit: int = 200) -> dict:
    """Find clone pairs across multiple graphs."""
    if not (2 <= len(graph_ids) <= 8) or len(set(graph_ids)) != len(graph_ids):
        raise ValueError("Invalid graph_ids: must be 2-8 distinct IDs")
        
    conn = sqlite3.connect(":memory:", uri=True)
    try:
        graph_ids = sorted(graph_ids)
        pairs = []
        
        for i, gid in enumerate(graph_ids):
            row = catalog.graph(gid)
            db_path = "file:" + Path(row["code_database"]).resolve().as_posix() + "?mode=ro"
            conn.execute(f"ATTACH DATABASE ? AS g{i}", (db_path,))
            
            count = conn.execute(
                f"SELECT COUNT(*) FROM g{i}.entity_fingerprints WHERE snapshot_id = ?", 
                (row["snapshot_id"],)
            ).fetchone()[0]
            
            if count == 0:
                raise ValueError(f"FINGERPRINTS_NOT_COMPUTED: {gid}")
                
        for i, j in combinations(range(len(graph_ids)), 2):
            gid_i, gid_j = graph_ids[i], graph_ids[j]
            row_i = catalog.graph(gid_i)
            row_j = catalog.graph(gid_j)
            sid_i, sid_j = row_i["snapshot_id"], row_j["snapshot_id"]
            
            # AST match
            ast_matches = conn.execute(f'''
                SELECT e1.entity_id, e2.entity_id
                FROM g{i}.entity_fingerprints ef1
                JOIN g{i}.entities e1 ON ef1.entity_id = e1.entity_id
                JOIN g{j}.entity_fingerprints ef2 ON ef1.ast_body_hash = ef2.ast_body_hash
                JOIN g{j}.entities e2 ON ef2.entity_id = e2.entity_id
                WHERE ef1.snapshot_id = ? AND ef2.snapshot_id = ?
                  AND ef1.ast_body_hash IS NOT NULL AND ef2.ast_body_hash IS NOT NULL
                  AND e1.kind = e2.kind AND e1.kind IN ('function', 'method', 'class')
            ''', (sid_i, sid_j)).fetchall()
            
            matched_entities = set(ast_matches)
            for eid1, eid2 in ast_matches:
                pairs.append({
                    "graph_a": gid_i,
                    "entity_a": eid1,
                    "graph_b": gid_j,
                    "entity_b": eid2,
                    "match": "py-ast-v1"
                })
                
            # Signature+guard match (excluding AST matches)
            sig_guard_matches = conn.execute(f'''
                SELECT e1.entity_id, e2.entity_id
                FROM g{i}.entity_fingerprints ef1
                JOIN g{i}.entities e1 ON ef1.entity_id = e1.entity_id
                JOIN g{j}.entity_fingerprints ef2 ON ef1.signature_hash = ef2.signature_hash 
                                                  AND ef1.ts_guard_hash = ef2.ts_guard_hash
                JOIN g{j}.entities e2 ON ef2.entity_id = e2.entity_id
                WHERE ef1.snapshot_id = ? AND ef2.snapshot_id = ?
                  AND ef1.signature_hash IS NOT NULL AND ef2.signature_hash IS NOT NULL
                  AND ef1.ts_guard_hash IS NOT NULL AND ef2.ts_guard_hash IS NOT NULL
                  AND e1.kind = e2.kind AND e1.kind IN ('function', 'method', 'class')
            ''', (sid_i, sid_j)).fetchall()
            
            for eid1, eid2 in sig_guard_matches:
                if (eid1, eid2) not in matched_entities:
                    pairs.append({
                        "graph_a": gid_i,
                        "entity_a": eid1,
                        "graph_b": gid_j,
                        "entity_b": eid2,
                        "match": "signature+guard"
                    })
                    
        for i in range(len(graph_ids)):
            conn.execute(f"DETACH DATABASE g{i}")
            
        pairs.sort(key=lambda p: (0 if p["match"] == "py-ast-v1" else 1, 
                                  p["graph_a"], p["entity_a"], p["graph_b"], p["entity_b"]))
                                  
        return {
            "pairs": pairs[:limit],
            "truncated": len(pairs) > limit
        }
        
    finally:
        conn.close()

