"""Deterministic discovery card (discovery-card-v1): QCICS, ABBS and SCBBS rankings.

Pure functions of stored facts; no clocks, randomness or hash(). Closures follow
master G11: every float is rounded to 6 decimals before ranking, ties break by
representative ID, each section holds at most 5 rows.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .analysis import DEFAULT_FILTER, TreeIndex, boundary_ratios, selected_relationships, subject_graph, tarjan
from .labels import base_label
from .model import canonical, digest

CARD_VERSION = "discovery-card-v1"
TOP = 5
FILE_GROUPING = {"mode": "kind", "kind": "file"}
STATIC_LINE = "static structure only; no runtime, performance or quality claim"
RUNTIME_LINE = "includes runtime-family relationships; rankings use static quotient structure only, with no performance or quality claim"
LN2 = math.log(2)


def _r(x):
    return round(float(x), 6)


# --- feedback arc set ---------------------------------------------------------------------

def _back_weight(order, arcs):
    pos = {v: i for i, v in enumerate(order)}
    return sum(w for (u, v), w in sorted(arcs.items()) if pos[u] > pos[v])


def fas_min(k: int, weights: dict[tuple[int, int], float]) -> tuple[float, list[int]]:
    """Minimum feedback arc weight (>= 1) and a vertex ordering of 0..k-1."""
    arcs = {}
    for (u, v), w in sorted(weights.items()):
        if u != v:
            arcs[(u, v)] = arcs.get((u, v), 0) + w
    if 2 <= k <= 8:
        dp = {0: (0, ())}
        for mask in range(1, 1 << k):
            best = None
            for v in range(k):
                if not mask >> v & 1:
                    continue
                prev_cost, prev_order = dp[mask ^ (1 << v)]
                cost = prev_cost + sum(arcs.get((v, u), 0) for u in range(k) if u != v and mask >> u & 1)
                cand = (cost, prev_order + (v,))
                if best is None or cand < best:
                    best = cand
            dp[mask] = best
        cost, order = dp[(1 << k) - 1]
        return max(1, cost), list(order)
    remaining = set(range(k))
    out_w = defaultdict(float)
    in_w = defaultdict(float)
    succ = defaultdict(set)
    pred = defaultdict(set)
    for (u, v), w in sorted(arcs.items()):
        out_w[u] += w
        in_w[v] += w
        succ[u].add(v)
        pred[v].add(u)
    left, right = [], []

    def remove(v):
        remaining.discard(v)
        for t in sorted(succ[v]):
            in_w[t] -= arcs[(v, t)]
            pred[t].discard(v)
        for s in sorted(pred[v]):
            out_w[s] -= arcs[(s, v)]
            succ[s].discard(v)
        succ[v] = set()
        pred[v] = set()

    while remaining:
        progressed = True
        while progressed:
            progressed = False
            sink = next((v for v in sorted(remaining) if not succ[v]), None)
            if sink is not None:
                right.insert(0, sink)
                remove(sink)
                progressed = True
                continue
            source = next((v for v in sorted(remaining) if not pred[v]), None)
            if source is not None:
                left.append(source)
                remove(source)
                progressed = True
        if remaining:
            pick = max(sorted(remaining), key=lambda v: (out_w[v] - in_w[v], -v))
            left.append(pick)
            remove(pick)
    order = left + right
    return max(1, _back_weight(order, arcs)), order


# --- store access -------------------------------------------------------------------------

def _file_view(store, sid):
    row = store.connection.execute(
        "SELECT view_id,filter_hash FROM analysis_views WHERE snapshot_id=? AND grouping_json=? AND filter_hash=? ORDER BY view_id LIMIT 1",
        (sid, canonical(FILE_GROUPING), digest(DEFAULT_FILTER))).fetchone()
    return (row["view_id"], row["filter_hash"]) if row else (None, None)


def _cycle_data(store, sid):
    """Per-cycle structure shared by quotient_cycles and feedback_arcs."""
    view_id, fh = _file_view(store, sid)
    if view_id is None:
        return None
    c = store.connection
    members = defaultdict(list)
    for r in c.execute("""SELECT scc_id,representative_id FROM level_scc_condensations
        WHERE snapshot_id=? AND view_id=? AND filter_hash=? AND component_size>=2
        ORDER BY scc_id,representative_id""", (sid, view_id, fh)):
        members[r["scc_id"]].append(r["representative_id"])
    rep_scc = {rep: scc for scc, reps in members.items() for rep in reps}
    projections = defaultdict(list)
    for r in c.execute("""SELECT projection_id,source_rep_id,target_rep_id,witness_count FROM quotient_projections
        WHERE snapshot_id=? AND view_id=? AND family IN ('static','runtime') AND direction='directed' AND is_internal=0
        ORDER BY projection_id""", (sid, view_id)):
        s = rep_scc.get(r["source_rep_id"])
        if s is not None and s == rep_scc.get(r["target_rep_id"]):
            projections[s].append(dict(r))
    atoms = defaultdict(set)
    for r in c.execute("SELECT atom_id,representative_id FROM partition_members WHERE snapshot_id=? AND view_id=?", (sid, view_id)):
        if r["representative_id"] in rep_scc:
            atoms[r["representative_id"]].add(r["atom_id"])
    cycles = []
    for scc in sorted(members, key=lambda s: (members[s][0], s)):
        reps = sorted(members[scc])
        index = {rep: i for i, rep in enumerate(reps)}
        weights = {}
        for p in projections[scc]:
            key = (index[p["source_rep_id"]], index[p["target_rep_id"]])
            weights[key] = weights.get(key, 0) + p["witness_count"]
        fas, order = fas_min(len(reps), weights)
        pos = {v: i for i, v in enumerate(order)}
        back = sorted(p["projection_id"] for p in projections[scc]
                      if pos[index[p["source_rep_id"]]] > pos[index[p["target_rep_id"]]])
        cycles.append(dict(scc_id=scc, reps=reps, fas=fas, back=back,
                           w_cross=sum(p["witness_count"] for p in projections[scc]),
                           atoms=set().union(*(atoms[r] for r in reps))))
    return dict(view_id=view_id, cycles=cycles)


def feedback_arcs(store, snapshot_id: str) -> frozenset[str]:
    """projection_ids of file-level quotient projections that are back arcs in a cycle's FAS ordering."""
    data = _cycle_data(store, snapshot_id)
    if data is None:
        return frozenset()
    return frozenset(pid for cyc in data["cycles"] for pid in cyc["back"])


def quotient_cycles(store, snapshot_id: str) -> list[dict]:
    """Every file-level quotient SCC with k >= 2, ranked by QCICS descending."""
    data = _cycle_data(store, snapshot_id)
    if data is None or not data["cycles"]:
        return []
    graph = store.graph(snapshot_id)
    tree = TreeIndex(graph)
    atom_owner = {}
    for i, cyc in enumerate(data["cycles"]):
        for a in sorted(cyc["atoms"]):
            atom_owner[a] = i
    edges_by = defaultdict(list)
    for r in selected_relationships(graph):
        if r.direction != "directed" or r.family not in {"static", "runtime"} or r.source_id == r.target_id:
            continue
        i = atom_owner.get(r.source_id)
        if i is not None and i == atom_owner.get(r.target_id):
            edges_by[i].append((r.source_id, r.target_id))
    rep_set = {rep for cyc in data["cycles"] for rep in cyc["reps"]}
    leaf_file = {r["atom_id"]: r["representative_id"] for r in store.connection.execute(
        "SELECT atom_id,representative_id FROM partition_members WHERE snapshot_id=? AND view_id=?", (snapshot_id, data["view_id"]))}
    subjects, _ = subject_graph(graph)
    owned = defaultdict(set)
    for v in sorted(subjects):
        owner = leaf_file.get(tree.leaves(v)[0])
        if owner in rep_set:
            owned[owner].add(v)
    out = []
    for i, cyc in enumerate(data["cycles"]):
        v_atom = cyc["atoms"]
        if len(v_atom) <= 1:
            rho = 0.0
        else:
            sccs = tarjan(sorted(v_atom), edges_by[i])
            rho = 1.0 - sum(len(s) - 1 for s in sccs) / (len(v_atom) - 1)
        ratios = []
        for rep in cyc["reps"]:
            row = next(b for b in boundary_ratios(graph, owned[rep]) if b["mode"] == "undirected")
            ratios.append(row["ratio"] or 0.0)
        mean_ratio = sum(ratios) / len(ratios)
        qcics = len(cyc["reps"]) * rho * mean_ratio * math.log(1 + cyc["w_cross"] / cyc["fas"])
        out.append(dict(representative_ids=cyc["reps"],
                        member_rel_paths=sorted(graph.entities[r].rel_path or graph.entities[r].qualified_name for r in cyc["reps"]),
                        members_labels=sorted(base_label(graph, r) for r in cyc["reps"]),
                        qcics=_r(qcics), rho_c6=_r(rho), fas_weight=_r(cyc["fas"]), w_cross=cyc["w_cross"],
                        source_analysis="level_scc_condensations:" + cyc["scc_id"]))
    out.sort(key=lambda row: (-row["qcics"], row["representative_ids"][0]))
    return out


def _mode_ratio(by_mode, mode):
    row = by_mode.get(mode)
    if row is None or row["status"] == "zero_volume" or row["ratio"] is None:
        return 0.0
    return row["ratio"]


def _boundary_bottlenecks(graph):
    rows = []
    for aid in sorted(graph.analyses):
        a = graph.analyses[aid]
        if not aid.startswith("diagnostic:") or a["algorithm_version"] != "boundary-cayley-v1":
            continue
        eid = aid[len("diagnostic:"):]
        by_mode = {b["mode"]: b for b in a["result"]["boundary"]}
        phi_out, phi_in = _mode_ratio(by_mode, "outgoing"), _mode_ratio(by_mode, "incoming")
        volume = by_mode.get("undirected", {}).get("volume", 0.0)
        bounds = [x["lower_bound"] for x in a["result"]["cayley"] if x.get("lower_bound") is not None]
        ln_gamma = math.log(2 + max(bounds)) if bounds else LN2
        abbs = (phi_out + phi_in) / 2 * (1 + abs(phi_out - phi_in)) * ln_gamma * math.log(1 + volume)
        if _r(abbs) > 0:
            rows.append(dict(entity_id=eid, label=base_label(graph, eid), abbs=_r(abbs), phi_out=_r(phi_out),
                             phi_in=_r(phi_in), volume=_r(volume), source_analysis=aid))
    rows.sort(key=lambda r: (-r["abbs"], r["entity_id"]))
    return rows


def _surprising_links(store, sid, graph):
    view_id, _ = _file_view(store, sid)
    if view_id is None:
        return []
    tree = TreeIndex(graph)
    max_depth = max(1, max((e.depth for e in graph.entities.values()), default=1))
    rows = []
    for r in store.connection.execute("""SELECT projection_id,source_rep_id,target_rep_id,subtype,witness_count FROM quotient_projections
        WHERE snapshot_id=? AND view_id=? AND family='static' AND direction='directed' AND is_internal=0
        ORDER BY projection_id""", (sid, view_id)):
        u, v = r["source_rep_id"], r["target_rep_id"]
        wl_u, wl_v = graph.entities[u].wl_3hop_hash, graph.entities[v].wl_3hop_hash
        psi_wl = 1 if wl_u is not None and wl_u == wl_v else 0
        psi_rule = 0  # snapshots store no conformance model, so no projection carries a finding
        score = tree.distance(u, v) / (2 * max_depth) / math.log(2 + r["witness_count"]) * (1 + psi_rule + psi_wl)
        rows.append(dict(source_rep_id=u, target_rep_id=v, source_label=base_label(graph, u), target_label=base_label(graph, v),
                         subtype=r["subtype"], witness_count=r["witness_count"], scbbs=_r(score), source_analysis=r["projection_id"]))
    rows.sort(key=lambda x: (-x["scbbs"], x["source_rep_id"], x["target_rep_id"], x["source_analysis"]))
    return rows


def build_card(store, snapshot_id: str) -> dict:
    graph = store.graph(snapshot_id)
    runtime = store.connection.execute("SELECT 1 FROM relationships WHERE snapshot_id=? AND family='runtime' LIMIT 1", (snapshot_id,)).fetchone()
    view_id, _ = _file_view(store, snapshot_id)
    return dict(card_version=CARD_VERSION, snapshot_id=snapshot_id,
                quotient_cycles=quotient_cycles(store, snapshot_id)[:TOP],
                boundary_bottlenecks=_boundary_bottlenecks(graph)[:TOP],
                surprising_links=_surprising_links(store, snapshot_id, graph)[:TOP],
                honesty=RUNTIME_LINE if runtime else STATIC_LINE,
                sources=[dict(analysis="quotient-v1", id=view_id),
                         dict(analysis="boundary-cayley-v1", id="diagnostic:*"),
                         dict(analysis="directed-wl3-v1", id="wl:" + digest(DEFAULT_FILTER))])


def render_markdown(card: dict) -> str:
    out = ["# Discovery card", "", f"Snapshot `{card['snapshot_id']}` ({card['card_version']})", "", f"_{card['honesty']}_", "",
           "## Quotient cycles (QCICS)", ""]
    for r in card["quotient_cycles"]:
        out.append(f"- {', '.join(r['members_labels'])} | qcics {r['qcics']} | rho {r['rho_c6']} | fas {r['fas_weight']} | w {r['w_cross']} | `{r['source_analysis'][-16:]}`")
    if not card["quotient_cycles"]:
        out.append("- none")
    out += ["", "## Boundary bottlenecks (ABBS)", ""]
    for r in card["boundary_bottlenecks"]:
        out.append(f"- {r['label']} | abbs {r['abbs']} | out {r['phi_out']} | in {r['phi_in']} | `{r['source_analysis'][-16:]}`")
    if not card["boundary_bottlenecks"]:
        out.append("- none")
    out += ["", "## Surprising links (SCBBS)", ""]
    for r in card["surprising_links"]:
        out.append(f"- {r['source_label']} -> {r['target_label']} | {r['subtype']} | w {r['witness_count']} | scbbs {r['scbbs']} | `{r['source_analysis'][-16:]}`")
    if not card["surprising_links"]:
        out.append("- none")
    return "\n".join(out) + "\n"
