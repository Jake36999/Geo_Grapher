# Phase 6–7 Wave 4: Librarian Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- Let a 1M-context lead model receive large Geo-Grapher envelopes in one call.
- Let it compile top-down task plans whose tasks run on the Librarian's real
  tier 1/2 helpers and tier 3 clerk, fed by Geo-Grapher task packets.
- Add bridge-impact and theory-conformance analysis.

**Architecture:** this wave rebinds Gemini's "LeadCompiledPlanDAG" onto
primitives the Librarian already has.
- **Lead:** owns the plan.
- **Core:** validates the plan and **fetches packets itself** through
  `McpManager`, so no model pastes packet text and helpers stay tool-free for
  graph access.
- **Execution by tier:**

  | Tier | Runs on |
  |---|---|
  | 1 | `delegate(tier=1)` |
  | 2 | `delegate(tier=2)` |
  | 3 | a new closed-shape clerk task |

- **Verification:** citations are checked deterministically against the packet.
  An LLM's word never closes a requirement (`closure.py`).
- **Result size:** external-result limits scale with the route's context window
  (master G7).

**Tech Stack:**
- Geo-Grapher: Python 3.11.3, MCP 1.30.
- Librarian V2: Python 3.11, MCP ≥ 2.2.
- pytest in both repos.

**Spec:** `docs/superpowers/plans/2026-11-11-phase6-7-00-master.md`. Its Part B
definitions G4, G5, G7 and G12 and decisions D4 and D6 are normative here.
Background: the scoping report's U10, U13 and U20.

## Global Constraints

The master Global Constraints apply, plus:
- **Librarian invariants that must hold:**
  - outside tools stay read-only, research phases only, ≤ 6 per server and ≤ 8
    in total;
  - helpers keep `HELPER_TOOLS` (no MCP);
  - clerk tasks stay unframed (`DATA_IS_UNFRAMED`);
  - helper counts obey `effort.py`: `lead_agents` 1–4, `tier2_agents` 3–12,
    `tier3_agents` 5–25;
  - structured results above the limit are withheld whole, never clipped.
- **Librarian test command:** `D:/Librarian_V2/.venv/Scripts/python.exe -m pytest tests -q`.
  The suite must stay green (2,147 + new).
- Librarian work goes on branch `geo-grapher-wave4` in `D:/Librarian_V2`; leave
  the pre-existing uncommitted files there untouched.
- Geo-Grapher work goes on branch `phase67-wave4`.

## Review Focus

1. **A route with no declared window.** It must fall back to 131,072 → 8,000
   chars. Behaviour for current users is unchanged (Task 2).
2. **A plan that is cyclic, references a missing anchor, or exceeds the effort
   caps.** It is refused before any packet fetch or helper start, with a
   precise reason (Task 4).
3. **A clerk answer that cites a handle not in its packet.** The citation is
   marked `unverified`, and the result cannot satisfy an authoritative
   requirement (Task 3).
4. **A graph re-ingested between packet fetch and plan completion.** Results
   carry their packet's `snapshot_id`. The Core re-checks it at reduce time and
   flags `STALE_SCOPE` (Task 4).
5. **A conformance check on a graph pair with zero reviewed bridges.** Return an
   empty finding set with `bridges_considered: 0` and a hint to review bridge
   proposals, never invented findings (Task 5).

---

### Task 1: Geo-Grapher tier profiles and `compile_task_packet` (G7; U10, U20)

**Files:**
- Modify:
  - `src/geographer/graph_router.py`:
    - profile ceilings in `query`, `federated_search` and
      `analyze_cross_graphs`;
    - the new `compile_task_packet`;
    - `TOOL_PRESETS['lead']`.
  - `src/geographer/graph_server.py`: the tool schema.
- Create: `src/geographer/task_packets.py`
- Modify: `contracts/v1.1/geographer.wire.d.ts`: `BudgetRequest` gains
  `profile?: 'tier3_leaf' | 'tier2_forager' | 'tier1_lead'`. Then run
  `npm run contracts`.
- Test: `tests/test_task_packets.py`

**Interfaces:**
- `PROFILE_CEILINGS = {'tier3_leaf': 1200, 'tier2_forager': 1800, 'tier1_lead': 32768}`.
  A `limit_tokens` above its profile ceiling raises
  `ValueError('BUDGET_EXCEEDS_PROFILE: …')`. Federation's upper bound becomes
  32,768 under every profile, which is unchanged.
- `TOOL_PRESETS['lead']` is
  `{'list_graphs','search_entities','get_architecture_context','get_entity_content','analyze_cross_graphs','compile_task_packet'}`
  (6 tools).
- `compile_task_packet(graph_id: str, anchors: list[str], instruction: str, *, profile: str = 'tier3_leaf', upstream: list[dict] = ()) -> dict` returns:

  ```
  {packet_version:'task-packet-v1', graph_id, graph_label, snapshot_id, profile, limit_tokens, used_tokens,
   instruction (≤ 25% budget, else INSTRUCTION_TOO_LONG),
   upstream:[{task_id, ref, inputs:[{name, cite}], outputs:[{name, cite}], cite, origin:'model_produced_citation_verified'}] (shares the 25%),
   anchors:[{ref, cite_as, kind, qualified_name, source:{rel_path,start_line,end_line}, text}] (55%),
   boundary:[{from, to, subtype, cite_as}] (20%),
   handles:[cite_as…]  // every citable handle in this packet, upstream cites included
  }
  ```

- **Upstream port contracts** (structured, not prose). Each input `upstream`
  record is `{task_id, ref, inputs, outputs, cite}`, built by the Librarian from
  a dependency task's verified answer (Task 4). Geo-Grapher re-validates each
  record against the graph before admitting it:
  - `ref` must parse (`parse_ref`) and resolve in `graph_id`'s current snapshot;
  - every `cite` (record-level and per input or output) must be a handle that
    resolves in `graph_id`. Items whose cite does not resolve are **dropped**,
    and the drop count is reported as `upstream_dropped`;
  - names are truncated to 80 chars;
  - records are admitted whole, in `(task_id, ref)` order, until the shared 25%
    budget is used; the rest are counted in `upstream_omitted`.
  
  Every admitted cite is added to `handles`. Upstream content stays labelled
  `origin:'model_produced_citation_verified'`: the cites are verified, the names
  are a model's reading.

- Anchors use the wave 3 `parse_ref` grammar. An unresolved anchor raises
  `ValueError('BRIDGE_ENDPOINT_UNRESOLVED: <ref>')`.
- Anchor text is the `get_entity_content` chunk text, in order. Boundary rows are
  the anchor's in- and out-relationships at radius 1, drawn from
  `get_architecture_context`.
- Slack moves forward: unused instruction budget goes to anchors, and unused
  anchor budget goes to boundary.
- Each section is filled with whole items; when one overflows, it is cut at the
  last item that fits.
- The packet is counted exactly with `TokenCounter`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_profile_ceiling_is_enforced_not_clamped(hub):
    catalog, router, first = hub
    req = request(first); req["budget"].update(limit_tokens=4000, profile="tier2_forager")
    with pytest.raises(ValueError, match="^BUDGET_EXCEEDS_PROFILE"):
        router.query(first["graph_id"], "search_entities", req)

def test_packet_respects_budget_split_and_lists_handles(hub_with_code):
    catalog, router, gid, eid = hub_with_code
    p = router.compile_task_packet(gid, [f"entity:{eid}"], "State the inputs and outputs of this function.", profile="tier3_leaf")
    assert p["used_tokens"] <= 1200 and p["anchors"][0]["cite_as"] in p["handles"]
    assert all(b["cite_as"] in p["handles"] for b in p["boundary"])

def test_packet_rejects_long_instruction_and_bad_anchor(hub_with_code):
    catalog, router, gid, eid = hub_with_code
    with pytest.raises(ValueError, match="^INSTRUCTION_TOO_LONG"):
        router.compile_task_packet(gid, [f"entity:{eid}"], "x " * 2000)
    with pytest.raises(ValueError, match="^BRIDGE_ENDPOINT_UNRESOLVED"):
        router.compile_task_packet(gid, ["entity:nope"], "Describe.")

def test_upstream_records_are_revalidated_and_cites_join_handles(hub_with_code):
    catalog, router, gid, eid = hub_with_code
    callee_cite = router.compile_task_packet(gid, [f"entity:{eid}"], "Describe.")["anchors"][0]["cite_as"]
    up = [{"task_id": "t1", "ref": f"entity:{eid}", "cite": callee_cite,
           "inputs": [{"name": "x", "cite": callee_cite}, {"name": "ghost", "cite": "nope/entity:zzz"}],
           "outputs": [{"name": "result", "cite": callee_cite}]}]
    p = router.compile_task_packet(gid, [f"entity:{eid}"], "Describe the caller.", upstream=up)
    rec = p["upstream"][0]
    assert [i["name"] for i in rec["inputs"]] == ["x"] and p["upstream_dropped"] == 1
    assert rec["origin"] == "model_produced_citation_verified" and callee_cite in p["handles"]

def test_lead_preset_has_six_tools():
    assert len(TOOL_PRESETS["lead"]) == 6

def test_packet_is_deterministic(hub_with_code):
    catalog, router, gid, eid = hub_with_code
    a = router.compile_task_packet(gid, [f"entity:{eid}"], "Describe.")
    b = router.compile_task_packet(gid, [f"entity:{eid}"], "Describe.")
    assert canonical(a) == canonical(b)
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(packets): tier profiles and compile_task_packet with lead preset`.

---

### Task 2: Route-aware external result limit (Librarian; G7, D4)

**Files (`D:/Librarian_V2`):**
- Modify: `src/resource_librarian/mcp_client.py:47, 480-505`:
  - add `external_result_limit(context_tokens: int | None) -> int`;
  - `McpManager.call(..., limit_chars: int | None = None)` uses it in place of
    the constant;
  - keep `MAX_EXTERNAL_RESULT = 8_000` as the floor, for compatibility.
- Modify: `src/resource_librarian/loop.py`, where outside tools are dispatched:
  pass `limit_chars=external_result_limit(<route context tokens>)`, taking the
  window the loop already resolves for context fitting (`loop.py:134-139`).
- Test: `tests/test_external_result_limit.py`

**Interfaces:**
- `external_result_limit(None) == 8000`.
- `external_result_limit(131_072) == 8000`.
- `external_result_limit(200_000) == 24_000`.
- `external_result_limit(1_048_576) == 125_829`.
- `external_result_limit(10_000_000) == 160_000`.

- [ ] **Step 1: Write the failing tests.**
  - The five values above.
  - An oversized structured result at 9,000 chars is withheld for a 128k route
    and passes for a 1M route.
  - A non-structured result is still clipped to the limit and flagged
    `truncated`.
  - The withheld payload reports the route-specific `limit_characters`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement exactly the G7 formula.
- [ ] **Step 4:** Run the full Librarian suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(mcp): external result limit scales with the route's context window`.

---

### Task 3: Clerk task `code_block_contract` (Librarian tier 3)

**Files (`D:/Librarian_V2`):**
- Modify: `src/resource_librarian/clerk.py`: add the task kind
  `code_block_contract`, built only from a `task-packet-v1` dict.
- Create: `src/resource_librarian/packet_checks.py`
- Test: `tests/test_clerk_code_block_contract.py`

**Interfaces:**
- `clerk.code_block_contract(packet: dict) -> Task`. The payload holds exactly:
  - `packet['instruction']`;
  - the anchors' and boundary rows' text with their `cite_as`;
  - a closed return shape:

    ```
    {"inputs":[{"name":str,"cite":str}], "outputs":[{"name":str,"cite":str}],
     "calls":[{"target":str,"cite":str}], "claims":[{"text":str ≤ 200,"cite":str}],
     "not_determinable":[str]}
    ```

  - the packet's **structured** `upstream` records, verbatim as
    `{ref, inputs, outputs, cite, origin}` data rows (drop `task_id`, which is a
    plan identifier, not data). This is how a wave-k clerk sees the verified
    input/output contracts of callees resolved in wave k−1.
  - The task receives no project, session, plan, brief, prose upstream or
    instruction other than `packet['instruction']`, so `DATA_IS_UNFRAMED` holds.
    Upstream rows are data about the code, like anchors. They are not framing
    about the catalogue's purpose.
  - The system prompt tells the clerk that upstream rows are other readers'
    citation-checked notes. It may cite their `cite` handles, and must not
    restate their names as fact without a cite.
- `packet_checks.verify_citations(answer: dict, packet: dict) -> dict` returns
  `{verified: [path…], unverified: [path…], closure_strength: 'bounded' | 'none'}`.
  - A citation is verified iff its `cite` is in `packet['handles']`.
  - `closure_strength='bounded'` only when every cite is verified and
    `not_determinable` is a list.
  - Register it as a deterministic verifier `packet.citation_resolves` in
    `closure.VERIFIERS` with strength `bounded`.

- [ ] **Step 1: Write the failing tests.**
  - A built task's payload contains no keys beyond the closed set. Assert it
    through the clerk's existing payload-introspection helper if it has one;
    otherwise assert the constructor signature accepts only `packet`.
  - An answer citing an absent handle yields `unverified` and
    `closure_strength='none'`.
  - An all-verified answer yields `bounded`.
  - The packet's upstream records appear in the payload as exactly the
    structured rows `{ref, inputs, outputs, cite, origin}`. No `task_id`, plan
    ID, session, brief or other field is added.
  - A clerk answer citing an upstream `cite` is `verified`, because Geo-Grapher
    put upstream cites in `handles`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement, following an existing clerk task (`inside` or
  `mechanics`) as the template.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(clerk): code_block_contract task over Geo-Grapher packets`.

---

### Task 4: `dispatch_plan`, a lead-compiled task DAG on real helpers (Librarian; U20)

**Files (`D:/Librarian_V2`):**
- Create: `src/resource_librarian/tools/plan_dispatch.py`
- Modify: `src/resource_librarian/agent_runtime.py` (`BUNDLES`): add
  `dispatch_plan` to `map` and `execute`. Both stay ≤ `MAX_BUNDLE_TOOLS = 12`;
  assert this in a test.
- Test: `tests/test_plan_dispatch.py`

**Interfaces:**
- Signature:

  ```
  @tool("dispatch_plan", tier="contribute", effect="read", ...)
  def dispatch_plan(ctx, plan: dict) -> dict
  ```

- `plan` shape:

  ```
  {"plan_id": str, "server": str,  // an enabled MCP server name exposing compile_task_packet
   "tasks": [{"task_id": str, "tier": 1|2|3, "graph_id": str, "anchors": [ref…] (1..8),
              "instruction": str, "depends_on": [task_id…]}] (1..32)}
  ```

- **Validation runs first and has no side effects.** Error codes:

  | Code | Condition |
  |---|---|
  | `PLAN_SHAPE` | the plan doesn't match the shape |
  | `PLAN_CYCLE` | Kahn's algorithm leaves nodes |
  | `PLAN_UNKNOWN_DEPENDENCY` | a `depends_on` names no task |
  | `PLAN_TOO_LARGE_FOR_EFFORT` | a single wave has more tier-1, tier-2 or tier-3 tasks than `effort.of(ctx)` allows: `lead_agents`, `tier2_agents`, `tier3_agents` |
  | `PLAN_SERVER_UNAVAILABLE` | `server` isn't enabled, or doesn't offer `compile_task_packet` |

- **Execution:**
  1. Compute waves with Kahn's algorithm. Within a wave, order tasks by
     `task_id`.
  2. Fetch the packet for each task in a wave through the Core:
     `McpManager.call(server, 'compile_task_packet', {graph_id, anchors, instruction, profile, upstream})`.
     - The profile per tier is `{1: 'tier1_lead', 2: 'tier2_forager', 3: 'tier3_leaf'}`.
     - `upstream` holds one **structured** record per dependency task:
       `{task_id, ref: <that task's first anchor>, cite: <that anchor's cite_as>, inputs: [verified], outputs: [verified]}`.
       It contains only items whose `cite` passed `verify_citations`. Prose
       claims are never forwarded. Geo-Grapher re-validates the records and
       truncates them to its 25% share (Task 1).
     - All tiers receive the same structured upstream. The clerk gets it as data
       rows (Task 3); helpers get it inside the packet JSON.
     - A packet fetch error marks that task `failed` and its dependants
       `skipped`.
  3. Run each wave:
     - tier 3 → clerk `code_block_contract(packet)`, in parallel up to the
       effort cap;
     - tiers 1/2 → `delegate(questions=[<brief>], tier=t)`. The brief is the
       instruction, the packet as fenced JSON, and the same closed return shape
       as Task 3.
  4. Verify each answer with `packet_checks.verify_citations`.
- **Result:**

  ```
  {"plan_id", "waves": [[task_id…]…],
   "results": {task_id: {"state": "ok"|"failed"|"skipped", "snapshot_id", "answer", "verification"}},
   "stale": [task_id…]}
  ```

  - `stale` lists tasks whose packet `snapshot_id` no longer equals the graph's
    current one, re-read through `list_graphs` at the end.
  - Nothing is written to the vault. The lead stages what it keeps through the
    normal `stage_artifact` / staging path.

- [ ] **Step 1: Write the failing tests.** Use a fake MCP manager and fake
  helper and clerk providers. Fixtures exist in `tests/test_external_bundles.py`
  and `tests/test_loop.py`; reuse their patterns.
  - A cycle → `PLAN_CYCLE`, with 0 packet fetches recorded.
  - A wave with 6 tier-1 tasks at effort level 1 → `PLAN_TOO_LARGE_FOR_EFFORT`.
  - A 3-task chain, `t3 → t2 → t1` by `depends_on`, produces 3 waves.
    - `t2`'s packet request carries exactly one structured upstream record
      built from `t1`'s answer, containing only `t1`'s verified inputs and
      outputs.
    - An unverified item in `t1`'s answer is absent from the record.
    - No `claims` text is forwarded.
  - A failed packet for `t1` → `t1: failed`, with `t2` and `t3` `skipped`.
  - Bundles `map` and `execute` contain `dispatch_plan` and stay ≤ 12.
  - A changed snapshot after dispatch → the task ID is in `stale`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(plans): dispatch_plan runs lead-compiled task DAGs on helpers and clerk`.

---

### Task 5: Bridge impact and theory conformance modes (Geo-Grapher; U13)

**Files:**
- Modify: `src/geographer/cross_graph.py`:
  - `bridge_impact(catalog, start: tuple[str, str], *, max_hops: int = 6, pinned_graphs: set[str] = frozenset()) -> dict`;
  - `conformance(catalog, theory_graph: str, code_graph: str) -> dict`.
- Modify: `src/geographer/graph_router.py` (`analyze_cross_graphs`): enable the
  modes `bridge_impact` and `theory_conformance`.
- Test: `tests/test_cross_graph_impact.py`

**Interfaces:**
- **`bridge_impact`:**
  - Dijkstra over states `(graph_id, entity_or_ref)`.
  - Intra-graph steps follow `find_dependants`' relation set, using the same
    service call. Each intra step costs 1.0, and a `candidate` relationship
    costs 1.10.
  - Bridge steps follow only bridges whose `state ∈ {'accepted','provisional_reanchored'}`.
    A bridge step costs 0.20 plus a stratum penalty: 2.50 if the target graph's
    `stratum.trust_tier == 'bronze_transcript'` and it isn't in `pinned_graphs`,
    else 0.
  - Ties break by `(cost, graph_id, ref)`.
  - Output: `{dependants: [{graph_id, ref, cost, path: [{kind: 'intra'|'bridge', from, to, id}]}], bridges_considered, max_hops}`.
- **`conformance`:** classify each theory-graph item (doc/claim/section) and
  each high-ABBS code entity. High ABBS means in the top 10, using the wave 1
  discovery scoring.

  | State | Condition |
  |---|---|
  | `VERIFIED_IMPLEMENTATION` | a reviewed bridge `reference` or `concept_equivalence` in state `accepted` reaches a code entity that exists in the current snapshot |
  | `SPECIFICATION_ABSENCE` | a theory item with **no** accepted bridge into the code graph |
  | `UNDOCUMENTED_DIVERGENCE` | a top-10 ABBS entity with no bridge and no documentary incidence |
  | `STALE_BRIDGE` | a bridge in state `suspect_stale` or `demoted_contestable` |

  Output: `{findings: [{state, theory_ref|null, code_ref|null, bridge_id|null, cite_as: [...]}], bridges_considered, hint|null}`.
  `hint` is set when `bridges_considered == 0`.

- [ ] **Step 1: Write the failing tests.** Fixture: a paper graph P, a code
  graph C (entity `f` called by `g`) and a `bronze_transcript` graph T. Bridges:
  - `P:doc:1#claim:1 → C:entity:f` (accepted);
  - `P:doc:1#claim:1 → T:doc:1` (accepted);
  - `T:doc:1 → C:entity:g` (accepted);
  - `P:doc:2 → C:entity:g` (demoted).
  
  Assertions:
  - From `P:doc:1#claim:1`, `C:f` is reached at cost 0.20 and `C:g` at cost 1.20
    (bridge, then the intra call `g → f` walked as a dependant).
  - The transcript route to `C:g` costs 0.20 + 2.50 + 0.20 = 2.90 and is not
    the chosen path.
  - With `pinned_graphs={T}` that route costs 0.40 and wins.
  - The demoted bridge is not traversed.
  - Conformance yields exactly one finding of each of the four states.
  - Zero bridges → `findings == []`, `bridges_considered == 0`, and `hint` set.
  - Results are deterministic across two processes.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(cross-graph): bridge impact and theory conformance modes`.

---

### Task 6: Wave 4 gate (end to end through the Librarian)

**Files:**
- Create: `reports/PHASE67_WAVE4_GATE.md`
- Modify: `scripts/librarian_harness.py`: add `--context-tokens N`, which sets
  `route_policy.context_tokens`, and `--preset lead|code|papers|cross`.

- [ ] **Step 1: Benchmark at three windows.** Run the existing 5-question
  benchmark three times through the Librarian loop with the `uvx`-installed
  build:
  - default window, preset `papers`;
  - `--context-tokens 1048576`, preset `papers`;
  - `--context-tokens 1048576`, preset `lead` against the `librarian-v2` code
    graph.
  
  Record facts found, tool calls per question, results withheld and wrong-graph
  calls. Expected: facts ≥ the previous 7/7 baseline, and 0 withheld.
- [ ] **Step 2:** Run the 29 leakage probes in library-scoped mode with the 1M
  window. Expected: 0 cross-graph leaks, which keeps the per-answer upper bound
  ~2.7% at n=108+29.
- [ ] **Step 3: Plan run.** In an `explore` session on ToolSet, have the lead
  compile and `dispatch_plan` a 6-task plan: 4 tier-3 block contracts, 1 tier-2
  synthesis and 1 tier-1 review.
  
  Record the waves, the clerk citation-verification rate, the stale count, wall
  time and cost.
- [ ] **Step 4:** Run `./scripts/verify.ps1` and the full Librarian suite.
  Expected: exit 0 for both.
- [ ] **Step 5: Commit** in both repos: `docs: wave 4 gate report`.
