# Phase 6–7 Wave 3: Structure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship six things:
- directed contraction that provably preserves reachability, packed additively;
- typed, snapshot-bound bridges with reviewed candidates;
- staleness tracking for bridges and discovery cards;
- one mode-parameterised cross-graph MCP tool;
- pruning by derivation;
- a directory picker with ingest preview in the UI.

**Architecture:**
- **Directed contraction:**
  - a new Stage 3 / query-time algorithm next to `helper_tree_balls_v1`, built
    on the corrected theorem (master G6);
  - packing reuses `GreedyPacker`'s tiers: block summaries form tier 1 and
    member expansions tier 2, with utility κ.
- **Bridges, proposals and lineage** are catalog tables.
- **The cross-graph tool** wraps wave 2's `cross_graph.py` behind one operation
  in a new `cross` preset.
- **Pruning** creates a derived graph and never edits a snapshot.

**Tech Stack:** Python 3.11.3, SQLite 3.40.1, Starlette, React, pytest, Playwright.

**Spec:** `docs/superpowers/plans/2026-11-11-phase6-7-00-master.md`. Its Part B
definitions G1, G3, G4, G5, G6, G8, G12 and G13 and decisions D3 and D6 are
normative here. Background: the scoping report's U2, U5, U7, U12, U14 and
U23d–e.

## Global Constraints

The master Global Constraints apply. In particular:
- New catalog tables go into both `DDL` and the allowed table set in
  `GraphCatalog.__init__` (`graph_catalog.py:52`).
- `papers` and `code` stay at 6 tools.
- `cross` is the new 6-tool preset of D6.
- Contraction never changes `relationships` rows.

Branch: `git switch -c phase67-wave3`.

## Review Focus

1. **Contraction near the focus.** The protected spine (focus, its ancestors,
   pins, bridge endpoints) is never inside a block, even when it would make a
   perfect dominator subtree (Task 2).
2. **A bridge whose endpoint graph is re-ingested with that entity deleted.**
   The bridge becomes `demoted_contestable`; it is not deleted and not silently
   kept as accepted. A bridge pointing at a graph deleted by wave 1 Task 6 is
   removed by delete. Artifacts that depended on it become `suspect_stale`
   (Task 5).
3. **Cyclic upstream dependencies between artifacts.** A cards ↔ notes cycle
   must terminate within 8 passes with a deterministic result (Task 5).
4. **Directory picker path traversal:** `..`, absolute paths outside allowed
   roots, UNC paths, symlinks and junctions. Every one of these is refused with
   403 (Task 7).
5. **Cross-graph tool output over budget.** Items are dropped whole, endpoint
   closure holds, and `omitted_items` counts what was cut (Task 6).

---

### Task 1: Path atomicity under contraction (U7 guard)

**Files:**
- Modify:
  - `tests/test_path_contract_feasibility.py` (extend);
  - `src/geographer/service.py` (only if a test fails): path steps must always
    reference atomic relationship IDs.
- Test: `tests/test_path_contract_feasibility.py::test_path_steps_stay_atomic_when_qi_enabled`

**Interfaces:**
- Invariant: for every `PathResult.steps[i].relationship_id`, a row exists in
  `relationships` for the snapshot. Steps never use projection IDs or group IDs.
- `anchor_identities` is emitted for every focus or pin anchor, even when the
  outcome is `no_path_within_scope`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_path_steps_stay_atomic_when_qi_enabled(service_with_helpers):
    svc, sid, req = service_with_helpers  # fixture with private helpers so helper_tree_balls_v1 forms groups
    req["qi"] = {"enabled": True, "max_diameter": 2}; req["path_request"] = PATH_REQ
    data = svc.query("get_architecture_context", req)["data"]
    ids = {r[0] for r in svc.store.connection.execute("SELECT relationship_id FROM relationships WHERE snapshot_id=?", (sid,))}
    assert data["paths"] and all(s["relationship_id"] in ids for p in data["paths"] for s in p["steps"])

def test_anchor_identities_present_on_no_path(harness_task_disconnected):
    envelope = harness_task_disconnected()
    assert envelope["evidence"]["scope"]["anchor_identities"] and envelope["answer_contract"]["requested_paths"]
```

- [ ] **Step 2:** Run the tests. If they pass, keep them as guards and commit.
  If they fail, fix `service.py` path assembly so it uses
  `quotient_witness_map` atoms.
- [ ] **Step 3: Commit:** `test(paths): atomic path steps and anchor identities under contraction`.

---

### Task 2: Directed contraction algorithm (`directed-helper-condensation-v1`, master G6)

**Files:**
- Create: `src/geographer/contraction_directed.py`
- Test: `tests/test_contraction_directed.py`

**Interfaces:**
- Produces:
  - `dominators(vertices: list[str], succ: dict[str, list[str]], roots: list[str]) -> dict[str, str | None]`,
    the immediate dominator of each vertex, with roots mapped to None. This is
    Cooper–Harvey–Kennedy over a virtual source joined to `roots`, in reverse
    post-order, with all lists sorted.
  - `is_convex(block: set[str], succ, pred, rank: dict[str, int]) -> bool`,
    the master G6 rank-bounded check.
  - `ports_complete(block: set[str], succ, pred) -> bool`: every entry port
    reaches every exit port inside the block.
  - `contract_directed(vertices: list[str], edges: list[tuple[str, str]], parent: dict[str, str], protected: set[str], max_depth: int = 3, *, candidates: list[set[str]] | None = None, ports_check: bool = True) -> Contraction`.
    - `candidates` replaces the generators (tests only).
    - `ports_check=False` skips invariant II (tests only). Production calls
      never pass it, and a test asserts the service never does.
    
    The return type is:

    ```python
    @dataclass(frozen=True)
    class Contraction:
        membership: dict[str, str]      # vertex → block representative (min member id)
        blocks: dict[str, tuple[str, ...]]  # representative → sorted members
        semantics: str = "existential_member_reachability"
        certificate: dict = field(default_factory=dict)  # {candidates, accepted, rejected:{reason:n}}
    ```

  - Rejection reasons:
    `{'not_convex','ports_incomplete','crosses_parent','protected','singleton','creates_cycle'}`.
    `creates_cycle` should never occur; count it if it does.

- [ ] **Step 1: Write the failing tests.**

```python
from geographer.contraction_directed import dominators, is_convex, contract_directed

def test_gemini_counterexample_blocks_are_not_both_accepted():
    # D: a→b, c→d ; candidates {a,d} and {b,c} are each convex in D but together form a quotient 2-cycle.
    # Neither is port-complete either, so inject them and check the convexity order alone with ports_check=False.
    edges = [("a","b"),("c","d")]
    c = contract_directed(["a","b","c","d"], edges, parent={v: "p" for v in "abcd"}, protected=set(),
                          candidates=[{"a","d"},{"b","c"}], ports_check=False)
    assert len(c.blocks) == 1 and c.certificate["rejected"].get("not_convex") == 1
    assert is_acyclic(quotient_edges(c, edges))

def test_dominators_diamond():
    idom = dominators(["r","x","y","z"], {"r":["x","y"],"x":["z"],"y":["z"],"z":[]}, ["r"])
    assert idom == {"r": None, "x": "r", "y": "r", "z": "r"}

def test_convexity_rejects_reentry():
    succ = {"a":["y"],"y":["b"],"b":[]}; pred = {"a":[],"y":["a"],"b":["y"]}; rank = {"a":0,"y":1,"b":2}
    assert not is_convex({"a","b"}, succ, pred, rank) and is_convex({"a","y","b"}, succ, pred, rank)

def test_protected_vertices_never_contracted():
    c = contract_directed(["r","h1","h2"], [("r","h1"),("h1","h2")], parent={"r":"p","h1":"p","h2":"p"}, protected={"h1"})
    assert all("h1" not in m for m in c.blocks.values())

def test_property_no_false_reachability_and_witnessed_arcs():
    for seed in range(300):
        vertices, edges, parent = random_dag(random.Random(seed))
        c = contract_directed(vertices, edges, parent, protected=set())
        q = quotient_edges(c, edges)
        assert is_acyclic(q), seed
        members = lambda X: c.blocks.get(X, (X,))
        for (A, B) in reachable_pairs(q):
            assert any(reaches(edges, u, v) for u in members(A) for v in members(B)), seed
        for (A, B) in q:
            assert any((u, v) in set(edges) for u in members(A) for v in members(B)), seed

def test_contraction_is_deterministic_under_input_order():
    vertices, edges, parent = random_dag(random.Random(7))
    baseline = contract_directed(vertices, edges, parent, protected=set())
    for seed in range(10):
        rng = random.Random(seed); v2, e2 = vertices[:], edges[:]; rng.shuffle(v2); rng.shuffle(e2)
        assert contract_directed(v2, e2, parent, protected=set()) == baseline
```

  Write these small helpers in the test file:
  - `quotient_edges(c, edges)`: map edges through `c.membership` and drop
    self-loops;
  - `is_acyclic`;
  - `reachable_pairs`;
  - `reaches(edges, u, v)`;
  - `random_dag(rng)`: 4–30 vertices `v00…`, edges only from a lower to a
    higher index with p = 0.15, and each vertex's parent drawn from `p0…p3`.

  Test-local `random` only generates inputs. Analyses never use it (master G12).
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3: Implement per master G6.**
  - Generate candidates per `T⁺` parent: dominator subtrees of depth ≤
    `max_depth`, post-dominator subtrees, and twin classes.
  - Order them by `(min member id, size desc)`.
  - Accept sequentially against the current quotient. Recompute `rank` as
    longest-path order of the current quotient after each acceptance; Q is
    small, so this is O(|Q|+|E_Q|) per acceptance.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(contraction): directed helper condensation with corrected convexity theorem`.

---

### Task 3: Wire directed contraction into queries and packing

**Files:**
- Modify:
  - `src/geographer/service.py:432-441`: `qi.algorithm` selects
    `contract_helpers` or `contract_directed`;
  - `src/geographer/store.py:405-409`: also materialise the directed variant at
    stage 3 as analysis `qi-directed:<digest(DEFAULT_FILTER)>`.
- Modify: `contracts/v1.1/geographer.wire.d.ts`:
  - `GetArchitectureContextRequest.qi` gains `algorithm?: 'helper_tree_balls_v1' | 'directed-helper-condensation-v1'`;
  - `QIReport.mode` adds `'directed-helper-condensation-v1'`;
  - `QIReport.directed_reachability_preserved` widens to `boolean`;
  - `QIReport` adds `semantics?: 'existential_member_reachability'`.
  
  Then run `npm run contracts`.
- Test: `tests/test_contraction_directed_service.py`

**Interfaces:**
- Consumes: `contract_directed` (Task 2).
- Packing:
  - every block becomes a tier-1 `Unit('block:'+rep, 1, utility=κ, records=<summary node + boundary witnesses>)`;
  - its members become tier-2 units `Unit('block-member:'+eid, 2, utility=κ(block), …)`.
- κ:

  ```
  κ(B) = round(exp(0.5 · DOI_max(B)) · (1 + boundary_witness_count(B)) / max(1, T_atomic(B) − T_summary(B)), 6)
  ```

  - `DOI_max(B)` uses `ctx['tree'].doi(member, focus)` (existing).
  - T values are `TokenCounter` counts of each unit's records.
  - **Anomaly boost.** The utility used for both the block unit and its member
    units is `κ'(B) = round(κ(B) · (1 + 2·V(B) + 1·F(B)), 6)`:
    - `V(B) = 1` if any member is an endpoint of a conformance violation for
      the request's `review_model_digest`, else 0. Violations come from the same
      rules evaluation `check_architecture` uses; with no digest, `V = 0`.
    - `F(B) = 1` if any member is the source or target subject of a relationship
      witnessing one of `discovery.feedback_arcs(store, sid)` (wave 1), mapped
      through `quotient_witness_map`, else 0.
    - Per-snapshot sets are cached in `ctx` as `ctx['anomaly_subjects'] = {'fas': set, 'violations': {digest: set}}`.
    - The effect is that blocks touching a violation or a feedback-arc witness
      outrank equal-DOI blocks, so their members expand to atomic first.
- Consumes: `discovery.feedback_arcs` (wave 1 Task 7).
  - `GreedyPacker` already admits tiers additively with exact checkpoints, so no
    packer change is needed.

- [ ] **Step 1: Write the failing tests.**

```python
def test_directed_qi_reports_preserved_reachability(service_with_helpers):
    svc, sid, req = service_with_helpers
    req["qi"] = {"enabled": True, "max_diameter": 2, "algorithm": "directed-helper-condensation-v1"}
    qi = svc.query("get_architecture_context", req)["data"]["qi"]
    assert qi["mode"] == "directed-helper-condensation-v1" and qi["directed_reachability_preserved"] is True
    assert qi["semantics"] == "existential_member_reachability"

def test_old_algorithm_unchanged_by_default(service_with_helpers):
    svc, sid, req = service_with_helpers; req["qi"] = {"enabled": True, "max_diameter": 2}
    assert svc.query("get_architecture_context", req)["data"]["qi"]["mode"] == "helper_tree_balls_v1"

def test_anomaly_boost_expands_feedback_arc_block_first(service_with_two_blocks_one_in_cycle):
    # fixture: two contractible helper blocks with equal DOI from the focus; block X's members witness the
    # b.py→a.py back arc of a ping-pong file cycle, block Y's do not; budget fits exactly one block expansion
    svc, sid, req, x_members, y_members = service_with_two_blocks_one_in_cycle
    ids = {n["id"] for n in svc.query("get_architecture_context", req)["data"]["nodes"]}
    assert x_members <= ids and not (y_members & ids)

def test_kappa_boost_formula():
    from geographer.contraction_directed import boosted_kappa
    assert boosted_kappa(1.5, violation=True, feedback=True) == 6.0
    assert boosted_kappa(1.5, violation=False, feedback=True) == 3.0
    assert boosted_kappa(1.5, violation=False, feedback=False) == 1.5

def test_block_summaries_admitted_before_members_under_tight_budget(service_with_helpers):
    svc, sid, req = service_with_helpers
    req["qi"] = {"enabled": True, "max_diameter": 2, "algorithm": "directed-helper-condensation-v1"}
    req["budget"]["limit_tokens"] = 1200
    data = svc.query("get_architecture_context", req)["data"]
    ids = {n["id"] for n in data["nodes"]}
    assert any(i.startswith("block:") for i in ids)  # summaries present
    assert data["completeness"]["truncated"] in (True, False)  # envelope valid either way; validate with svc.wire11
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Put
  `boosted_kappa(kappa: float, *, violation: bool, feedback: bool) -> float` in
  `contraction_directed.py`. Write the fixture
  `service_with_two_blocks_one_in_cycle` with explicit sources: `a.py` and
  `b.py` ping-pong at file level, each holding a private-helper chain, plus a
  matching helper chain in `c.py` outside any cycle. Choose the budget by
  measuring the two expansions' token costs in the fixture. Add
  `test_cold_latency_within_c14`: on the ToolSet
  gate copy (skip if absent), a cold `get_architecture_context` with the
  directed algorithm finishes in under 3.0 s. Mark it `@pytest.mark.integration`.
- [ ] **Step 4:** Run the tests, `tests/test_phase5_contracts.py` and the full
  suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(qi): directed contraction option with additive block expansion`.

---

### Task 4: Typed bridge endpoints, bindings and reviewed candidates (master G4; U12)

**Files:**
- Create: `src/geographer/bridges.py`, holding endpoint parsing/resolution and
  candidate scoring.
- Modify: `src/geographer/graph_catalog.py`:
  - `DDL`: add `bridge_bindings` and `bridge_proposals`, and add both to the
    allowed set;
  - `add_bridge`: validate and bind;
  - new `propose_bridges`, `review_proposal` and `bridge_state`.
- Modify:
  - `src/geographer/graph_server.py`: `GET /api/graphs/bridge-proposals?graph_ids=…`
    and `POST /api/graphs/bridge-proposals/{id}` with
    `{decision: 'accept'|'reject', rationale}`;
  - `frontend/src/BridgeReview.tsx` (new): a panel modelled on
    `GraphMergeReview.tsx`.
- Test: `tests/test_bridges.py`, `tests/browser-graphs/bridge-review.spec.cjs`

DDL:

```sql
CREATE TABLE IF NOT EXISTS bridge_bindings(
 bridge_id TEXT NOT NULL REFERENCES bridges(bridge_id) ON DELETE CASCADE,
 side TEXT NOT NULL CHECK(side IN ('source','target')),
 graph_id TEXT NOT NULL, ref TEXT NOT NULL, snapshot_id TEXT, paper_read_model TEXT,
 fingerprint_json TEXT NOT NULL CHECK(json_valid(fingerprint_json)),
 PRIMARY KEY(bridge_id, side)) STRICT;
CREATE TABLE IF NOT EXISTS bridge_proposals(
 proposal_id TEXT PRIMARY KEY, source_graph TEXT NOT NULL, source_ref TEXT NOT NULL,
 target_graph TEXT NOT NULL, target_ref TEXT NOT NULL, kind TEXT NOT NULL,
 score REAL NOT NULL, features_json TEXT NOT NULL CHECK(json_valid(features_json)),
 status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected')),
 decided_at TEXT, decision_rationale TEXT) STRICT;
```

**Interfaces:**
- Produces:
  - `parse_ref(ref: str) -> tuple[str, dict]`, where the kind is one of
    `entity, doc, claim, section, concept, root`. Bad input raises
    `ValueError('BRIDGE_REF_INVALID')`.
  - `resolve_ref(catalog, graph_id, ref) -> dict`, returning
    `{snapshot_id | paper_read_model, fingerprint_json}`. It raises
    `ValueError('BRIDGE_ENDPOINT_UNRESOLVED')`.
  - `score_candidate(features: dict) -> float`:

    ```
    0.45·alias_overlap + 0.35·shared_citation + 0.20·neighbour_jaccard
    ```

    The score is multiplied by `Ψ = 0.25` when both `shared_citation` and
    `neighbour_jaccard` are 0 (the homonym firewall), then rounded to 6
    decimals. Each feature is in [0,1]:
    - `alias_overlap`: Jaccard of normalised name + alias sets, from each
      graph's alias policy (`concept_aliases.json`);
    - `shared_citation`: 1 if the endpoints cite the same DOI or URL, else 0;
    - `neighbour_jaccard`: Jaccard of the normalised names of 1-hop neighbours.
  - `GraphCatalog.propose_bridges(graph_a: str, graph_b: str, *, kind: str, limit: int = 50) -> list[dict]`:
    candidates come from concept and section names in paper graphs and entity
    names in code graphs; proposals scoring below 0.30 are not stored.
  - `GraphCatalog.review_proposal(proposal_id: str, decision: str, rationale: str) -> dict`:
    on accept it calls `add_bridge` with evidence `[{'proposal_id':…, 'features':…}]`.
  - `GraphCatalog.bridge_state(bridge_id) -> str`, read from wave 3 Task 5's
    `artifact_states`, default `'accepted'`.
- `add_bridge` keeps its signature. Existing `'root'` refs stay valid.

- [ ] **Step 1: Write the failing tests.**

```python
def test_parse_ref_grammar():
    assert parse_ref("doc:12#claim:3") == ("claim", {"doc": 12, "claim": 3})
    for bad in ("doc:0", "doc:x", "entity:", "claim:3", "../x"):
        with pytest.raises(ValueError, match="BRIDGE_REF_INVALID"): parse_ref(bad)

def test_add_bridge_binds_snapshot_and_rejects_unresolved(hub_with_code_and_papers):
    catalog, code_gid, paper_gid, eid = hub_with_code_and_papers
    bid = catalog.add_bridge(paper_gid, "doc:1", code_gid, f"entity:{eid}", "reference", "Paper describes it", [{"note": "t"}])
    row = catalog.connection.execute("SELECT * FROM bridge_bindings WHERE bridge_id=? AND side='target'", (bid,)).fetchone()
    assert row["snapshot_id"] == catalog.graph(code_gid)["snapshot_id"] and json.loads(row["fingerprint_json"])["signature_hash"]
    with pytest.raises(ValueError, match="BRIDGE_ENDPOINT_UNRESOLVED"):
        catalog.add_bridge(paper_gid, "doc:999", code_gid, f"entity:{eid}", "reference", "x", [{"n": 1}])

def test_homonym_firewall_penalises_name_only_match():
    assert score_candidate({"alias_overlap": 1.0, "shared_citation": 0, "neighbour_jaccard": 0}) == 0.1125
    assert score_candidate({"alias_overlap": 1.0, "shared_citation": 1, "neighbour_jaccard": 0.5}) == 0.9

def test_proposals_never_auto_merge_and_accept_creates_bridge(hub_with_code_and_papers):
    catalog, code_gid, paper_gid, _ = hub_with_code_and_papers
    props = catalog.propose_bridges(paper_gid, code_gid, kind="reference")
    assert catalog.bridges([paper_gid, code_gid]) == []          # nothing created by proposing
    out = catalog.review_proposal(props[0]["proposal_id"], "accept", "Reviewed: same concept")
    assert len(catalog.bridges([paper_gid, code_gid])) == 1 and out["status"] == "accepted"
```

  Browser test: open the review panel, accept one proposal with a rationale,
  then assert the bridge count is 1 and there are no console errors.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
  - Bindings use wave 2's `SnapshotStore.fingerprints` for `entity:` refs.
  - Claim refs bind `{"claim_text_sha256": sha256(claim text)}` from the paper
    database.
- [ ] **Step 4:** Run the tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(bridges): typed snapshot-bound endpoints and reviewed proposals`.

---

### Task 5: Lineage and staleness sweep (`lineage-v1`, master G5, D3)

**Files:**
- Create: `src/geographer/lineage.py`
- Modify:
  - `src/geographer/graph_catalog.py`:
    - `DDL` and the allowed set gain `artifact_justifications`,
      `artifact_states` and `revision_ledger`;
    - `import_project`, after publishing a changed `snapshot_id`, calls
      `lineage.sweep(self, graph_id, old_sid, new_sid)`;
    - `add_bridge` registers each bridge as an artifact with one clause
      `[(source endpoint, contract), (target endpoint, contract)]`, where the
      contract is `CONTROL_GUARD_INVARIANT` for `entity:` refs and
      `STRICT_BYTE_SPAN` for claim refs;
    - `delete_graph` (wave 1) also sweeps, so dependants of removed bridges
      become `suspect_stale`.
  - `src/geographer/discovery.py`: `register_card(catalog, graph_id, card)`
    records the card as an artifact. Its premises are the entities in each row,
    with contract `TOPOLOGICAL_WL3`.
- Test: `tests/test_lineage.py`

DDL:

```sql
CREATE TABLE IF NOT EXISTS artifact_justifications(
 artifact_id TEXT NOT NULL, clause_id TEXT NOT NULL,
 premise_id TEXT NOT NULL,  -- digest(premise_kind, graph_id, ref, upstream_id)
 premise_kind TEXT NOT NULL CHECK(premise_kind IN ('ground','upstream')),
 graph_id TEXT, ref TEXT, contract TEXT, baseline_snapshot_id TEXT, baseline_json TEXT, upstream_id TEXT,
 CHECK((premise_kind='ground' AND graph_id IS NOT NULL AND ref IS NOT NULL AND contract IS NOT NULL AND upstream_id IS NULL)
    OR (premise_kind='upstream' AND upstream_id IS NOT NULL AND graph_id IS NULL)),
 PRIMARY KEY(artifact_id, clause_id, premise_id)) STRICT;
CREATE INDEX IF NOT EXISTS justifications_by_ground ON artifact_justifications(graph_id, ref) WHERE premise_kind='ground';
CREATE INDEX IF NOT EXISTS justifications_by_upstream ON artifact_justifications(upstream_id) WHERE premise_kind='upstream';
CREATE TABLE IF NOT EXISTS artifact_states(
 artifact_id TEXT PRIMARY KEY, artifact_kind TEXT NOT NULL CHECK(artifact_kind IN ('bridge','discovery_card','external')),
 state TEXT NOT NULL CHECK(state IN ('accepted','provisional_reanchored','suspect_stale','demoted_contestable')),
 updated_at TEXT NOT NULL) STRICT;
CREATE TABLE IF NOT EXISTS revision_ledger(
 event_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, graph_id TEXT, old_snapshot_id TEXT, new_snapshot_id TEXT,
 prior_state TEXT NOT NULL, next_state TEXT NOT NULL, hop INTEGER NOT NULL, rationale_json TEXT NOT NULL CHECK(json_valid(rationale_json)),
 recorded_at TEXT NOT NULL) STRICT;
CREATE TRIGGER IF NOT EXISTS ledger_append_only_u BEFORE UPDATE ON revision_ledger BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_append_only_d BEFORE DELETE ON revision_ledger BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;
```

**Interfaces:**
- Produces:
  - `register(catalog, artifact_id: str, kind: str, clauses: list[list[dict]]) -> None`,
    where a premise dict is `{'graph_id','ref','contract'}` or `{'upstream_id'}`;
  - `sweep(catalog, graph_id: str, old_sid: str | None, new_sid: str) -> dict`,
    returning `{changed: {artifact_id: (prior, next)}, passes: int, unknown: [artifact_id]}`;
  - `state(catalog, artifact_id) -> str`.
- Consumes:
  - wave 2's `drift.resolve`, `drift.tier` and `drift.OUTCOME`;
  - `SnapshotStore.fingerprints`.
- `GraphRouter.bridges(graph_ids)`, and therefore `list_bridges`, adds
  `state` to each bridge row, so the Librarian can read staleness through a
  read-only tool.
- The `external` artifact kind is reserved. The Librarian admits only read-only
  outside tools, so registering Librarian artifacts here is in the wave 5
  backlog.

- [ ] **Step 1: Write the failing tests.** Fixture: a code graph with `f` and
  `g`, a paper graph, and a bridge `paper:doc:1 → entity:f`. A discovery card
  depends on `f`, and an external note depends upstream on the bridge.

```python
def test_neighbour_only_edit_causes_no_demotion(lineage_world):
    w = lineage_world(); w.edit("g body only"); out = w.reingest()
    assert out["changed"] == {} or all(nxt in ("accepted", "provisional_reanchored") for _, nxt in out["changed"].values())

def test_signature_edit_demotes_hop1_and_quarantines_hop2(lineage_world):
    w = lineage_world(); w.edit("f signature"); out = w.reingest()
    assert state(w.catalog, w.bridge_id) == "demoted_contestable" and state(w.catalog, "note:1") == "suspect_stale"

def test_second_clause_keeps_artifact_accepted(lineage_world):
    w = lineage_world(note_clauses=[["bridge"], ["card"]]); w.edit("f signature"); w.reingest()
    assert state(w.catalog, "note:1") == "suspect_stale"   # card also depends on f ⇒ both clauses fail
    w2 = lineage_world(note_clauses=[["bridge"], ["unrelated_card"]]); w2.edit("f signature"); w2.reingest()
    assert state(w2.catalog, "note:1") == "accepted"

def test_restoring_the_signature_re_accepts_without_rewrite(lineage_world):
    w = lineage_world(); w.edit("f signature"); w.reingest(); w.revert(); w.reingest()
    assert state(w.catalog, w.bridge_id) == "accepted" and state(w.catalog, "note:1") == "accepted"

def test_cycle_terminates_deterministically(lineage_world):
    w = lineage_world(upstream_cycle=True); w.edit("f signature"); out = w.reingest()
    assert out["passes"] <= 8 and out == lineage_world(upstream_cycle=True).edit_and_reingest("f signature")

def test_old_store_without_fingerprints_is_unknown(lineage_world):
    w = lineage_world(new_store_without_fingerprints=True); out = w.reingest()
    assert w.bridge_id in out["unknown"] and state(w.catalog, w.bridge_id) == "accepted"

def test_ledger_is_append_only(lineage_world):
    w = lineage_world(); w.edit("f signature"); w.reingest()
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        w.catalog.connection.execute("DELETE FROM revision_ledger")
```

  `lineage_world` is a test-file helper class with `edit(kind)`, `reingest()`,
  `revert()` and the flags shown. Write it in full, with explicit source edits.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3: Implement the master G5 algorithm.**
  - Use a working map seeded from `artifact_states`.
  - Hop-1 runs first, then hop ≥ 2 in passes (cap 8).
  - Write states and ledger rows in one transaction.
- [ ] **Step 4:** Run the tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(lineage): snapshot-driven staleness for bridges and cards`.

---

### Task 6: `analyze_cross_graphs` and the `cross` preset (D6; U14)

**Files:**
- Modify:
  - `src/geographer/graph_router.py`:
    - `TOOL_PRESETS['cross']`, as in master D6;
    - an `analyze_cross_graphs(graph_ids, mode, *, limit_tokens=4096, cursor=None)`
      router method;
    - its tool registration.
  - `src/geographer/graph_server.py`: tool schema and description.
  - `src/geographer/cross_graph.py`:
    `pack_items(header: dict, bundles: list[dict], limit_tokens: int, counter) -> dict`.
- Test: `tests/test_analyze_cross_graphs.py`

**Interfaces:**
- `mode ∈ {'evolution_diff','clone_candidates','bridge_candidates'}`.
  `bridge_impact` and `theory_conformance` arrive in wave 4 and are rejected
  until then with `MODE_NOT_AVAILABLE`.
- Graph count:
  - `evolution_diff`: exactly 2 graphs;
  - the other modes: 2–8 graphs.
- Response:

  ```
  {engine_version:'cross-graph-v1', mode, graph_ids (sorted), ranking:'independent_per_graph_no_global_rank',
   omitted_graphs:[{graph_id, reason}], scope_anchor_identities:[{graph_id, snapshot_id, id, qualified_name, basis:'snapshot_identity_only'}],
   header:{counts...}, items:[...], omitted_items:int, next_cursor:str|None, used_tokens, limit_tokens}
  ```

- `pack_items`:
  - admits each bundle `{item, nodes}` whole, in input order;
  - re-counts the exact envelope every 16 admitted items and at the end;
  - on overflow, pops the last admitted item.
  
  The header carries only counts, never item lists. This is Gemini Defect 1,
  fixed.
- Each item cites endpoints as `cite_as: '<graph_label>/entity:<id>'` or
  `'<graph_label>/doc:N'`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_cross_preset_has_six_tools():
    assert len(TOOL_PRESETS["cross"]) == 6 and "analyze_cross_graphs" in TOOL_PRESETS["cross"]

def test_evolution_diff_fits_budget_and_is_endpoint_closed(router_two_graphs_many_entities):
    router, a, b = router_two_graphs_many_entities
    out = router.analyze_cross_graphs([b, a], "evolution_diff", limit_tokens=1800)
    assert out["graph_ids"] == sorted([a, b]) and out["used_tokens"] <= 1800 and out["omitted_items"] > 0
    node_ids = {(n["graph_id"], n["id"]) for n in out["nodes"]}
    assert all((e["graph_id"], e["id"]) in node_ids for it in out["items"] for e in it["endpoints"])

def test_unavailable_modes_and_wrong_counts_rejected(router_two_graphs_many_entities):
    router, a, b = router_two_graphs_many_entities
    with pytest.raises(ValueError, match="MODE_NOT_AVAILABLE"): router.analyze_cross_graphs([a, b], "bridge_impact")
    with pytest.raises(ValueError): router.analyze_cross_graphs([a], "clone_candidates")

def test_cursor_resumes_without_duplicates(router_two_graphs_many_entities):
    router, a, b = router_two_graphs_many_entities
    first = router.analyze_cross_graphs([a, b], "evolution_diff", limit_tokens=1800)
    second = router.analyze_cross_graphs([a, b], "evolution_diff", limit_tokens=1800, cursor=first["next_cursor"])
    assert not ({canonical(i) for i in first["items"]} & {canonical(i) for i in second["items"]})

def test_respects_connection_allow_list(router_two_graphs_many_entities):
    ...  # router with allowed={a}: analyze([a,b]) raises the existing permit error
```

  Write the last test in full, reusing the allow-list setup from
  `tests/test_graph_catalog.py::test_allow_list_makes_other_graphs_unreachable_on_that_connection`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3: Implement.** The cursor is
  `digest(mode, graph_ids, snapshot_ids)[:16] + ':' + offset`. A cursor whose
  digest doesn't match the current snapshots → `STALE_CURSOR`.
- [ ] **Step 4:** Run the tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(mcp): analyze_cross_graphs and cross tool preset`.

---

### Task 7: Prune by derivation, directory picker and ingest preview UI (master G8, G13; U23d–e)

**Files:**
- Modify: `src/geographer/graph_catalog.py`:
  `derive_graph(source_graph_id: str, *, exclude_rel_paths: list[str], label: str) -> dict`.
- Modify: `src/geographer/graph_server.py`:
  - `GET /api/fs/list?path=` (directories only);
  - `POST /api/workspace/ingest-preview` with `{root}` → a `workspace_init.scan` plan;
  - `POST /api/workspace/ingest-execute` with `{plan_id, approved_keys}` → `{job_id}`;
  - `GET /api/workspace/jobs/{job_id}` → `{state, reports, error}`;
  - `POST /api/graphs/{graph_id}/prune` with `{exclude_rel_paths, label}` → a
    derived graph.
- Modify: `src/geographer/cli.py`: `serve-graphs --browse-root DIR` (repeatable;
  default: none, which disables the picker).
- Create: `frontend/src/WorkspaceIngest.tsx` (picker → preview table with
  partition toggles → apply → progress).
- Modify:
  - `frontend/src/Workspace.tsx`: an **Add folder…** button;
  - `frontend/src/Scene.tsx`: a box-select that collects visible node IDs →
    **Prune selection…**.
- Test: `tests/test_prune_and_picker.py`, `tests/browser-graphs/ingest-and-prune.spec.cjs`

**Interfaces:**
- `derive_graph`:
  - `new_id = 'g_' + digest('derived-v1', source_graph_id, sorted(exclude_rel_paths))[:24]`;
  - `root_key = 'derived:' + new_id`;
  - profile `{graph_kind:'derived', derived_from, exclude_globs, owner_repo_ids:[new_id], stratum: <source stratum>}`;
  - re-ingests `root_path` with the source profile's globs plus
    `exclude_rel_paths` turned into globs (`p` and `p/*`).
  - It skips overlap review, because it is explicitly derived; the profile says
    so. The source graph is unchanged.
- Box-select maps the selected node IDs to `source.rel_path` client-side and
  dedupes them. Group nodes contribute their members' paths via the
  `membership_handle` the client already loads.
- `/api/fs/list`:
  - resolves `path` with `Path.resolve(strict=True)`;
  - refuses with 403 unless the resolved path `is_relative_to` one of the
    `--browse-root`s and has no reparse point on the way. Check each component
    with `os.lstat` `st_file_attributes & 0x400`.
  - Returns `{path, dirs: [name…] sorted}`: at most 500 entries, never files,
    never contents.
- Jobs run in one worker thread. One job at a time; a second request gets 409
  `JOB_RUNNING`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_derive_graph_excludes_paths_and_leaves_source_untouched(hub, tmp_path):
    catalog, router, first = hub
    root = Path(catalog.graph(first["graph_id"])["root_path"]); (root / "skip").mkdir(); (root / "skip" / "x.py").write_text("def x(): pass\n")
    src_sid = catalog.graph(first["graph_id"])["snapshot_id"]
    out = catalog.derive_graph(first["graph_id"], exclude_rel_paths=["skip"], label="A pruned")
    assert catalog.graph(first["graph_id"])["snapshot_id"] == src_sid
    with SnapshotStore(catalog.graph(out["graph_id"])["code_database"]) as s:
        assert not s.connection.execute("SELECT 1 FROM entities WHERE rel_path LIKE 'skip/%'").fetchone()

@pytest.mark.parametrize("path", ["..", "C:/Windows", "\\\\server\\share", "{root}/../..", "{root}/junction"])
def test_fs_list_refuses_outside_roots(picker_client, path):
    client, root = picker_client
    assert client.get("/api/fs/list", params={"path": path.format(root=root)}).status_code == 403

def test_fs_list_lists_dirs_only(picker_client):
    client, root = picker_client
    body = client.get("/api/fs/list", params={"path": str(root)}).json()
    assert body["dirs"] == sorted(body["dirs"]) and all((root / d).is_dir() for d in body["dirs"])

def test_ingest_preview_then_execute_job(picker_client):
    client, root = picker_client
    plan = client.post("/api/workspace/ingest-preview", json={"root": str(root)}).json()
    job = client.post("/api/workspace/ingest-execute", json={"plan_id": plan["plan_id"], "approved_keys": [p["key"] for p in plan["partitions"]]}).json()
    assert wait_job(client, job["job_id"])["state"] == "done"
```

  The `picker_client` fixture builds a hub with `browse_roots=[tmp_path/'ws']`
  and creates a directory junction (`mklink /J`, skipped if not permitted).
  Browser test: Add folder → choose `ws` → toggle off one partition → apply →
  the new graphs appear; box-select two nodes → prune → a derived graph appears.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests, typecheck, build and the browser suite.
  Expected: PASS.
- [ ] **Step 5: Commit:** `feat(workspace): derived-graph pruning, guarded directory picker and ingest UI`.

---

### Task 8: Wave 3 gate

**Files:**
- Create: `reports/PHASE67_WAVE3_GATE.md`

- [ ] **Step 1: Run on the ToolSet gate copy.**
  - Run directed contraction and record the block count, the rejected-reason
    histogram, cold `get_architecture_context` latency for both algorithms, and
    `directed_reachability_preserved`.
  - Re-run the Task 2 property test against 50 random real sub-DAGs drawn from
    ToolSet (seeded).
- [ ] **Step 2: Bridge pilot.**
  - Propose `reference` bridges from `ai-research-papers` to `librarian-v2`.
  - Hand-review 10, accepting or rejecting each, and record the precision of
    proposals scoring ≥ 0.30.
  - Edit one bridged function's signature in a scratch copy, re-ingest, and
    record the state transitions.
- [ ] **Step 3:** Run `analyze_cross_graphs` in each mode through the hub under
  `--max-result-chars 7500`. Expected: 0 withheld by a Librarian-sized client.
- [ ] **Step 4:** Run `./scripts/verify.ps1`. Expected: exit 0.
- [ ] **Step 5: Commit:** `docs: wave 3 gate report`.
