# Wave 4 review and direction to acceptance

Reviewer: the lead agent of waves 1–3. Date: 2026-11-12.

Reviewed:
- `reports/PHASE67_WAVE4_GATE.md`;
- `reports/PHASE67_WAVES1_3_TAKEOVER_ASSESSMENT.md`;
- the wave 4 ledger (rulings W4-1…W4-9);
- the benchmark result files under `output/phase67-gates/wave4/`;
- the live `lead`-preset MCP tool schemas on `phase67-wave4`.

The branches stay unmerged until the gates below pass.

## 1. Verdict on the work so far

**The engineering is sound and the reporting is exemplary.** Specifically:
- Packets, route bounds, Clerk contracts, the DAG dispatcher, impact and conformance analyses are all implemented and tested.
- The test counts are 642 backend tests, 17 browser tests and 2,181 Librarian tests.
- First results were kept, not replaced by better repeats.
- The qualification gate was respected, not bypassed.
- Spending stayed inside the pool.
- A genuine pre-existing defect was found and fixed: the Librarian coerced `$ref` objects to strings.
- The rulings W4-2 (explicit start and roles) and W4-4 (federation floor under profiles) are reasonable. Keep them.

**The acceptance gaps are of three different kinds, and each needs a different response:**

| Gap | Kind | Who closes it |
|---|---|---|
| Code benchmark 0/5 | **A product defect in the agent-facing tool surface** (§2). It isn't mainly model weakness. | Codex: engineering work, then a pre-registered re-run |
| Papers at 1M: 6/7 | A measurement-protocol question. The document was retrieved; the answer cited others. | The owner decides the protocol (§3.4), then Codex runs it once |
| Leakage: 1/29 prior-knowledge | **Not a criterion failure.** Plan Step 2's criterion is 0 cross-graph leaks, and that was **met** (0/29). | Record it; the answer-discipline fix belongs to the wave 5 backlog |
| Six-task live pilot | Blocked on real role qualification | The owner qualifies the routes (§3.5); then Codex runs the pilot |

## 2. Diagnosis: why the code benchmark is 0/5

The evidence is in `bench-1m-code-inline-schema.json`:
- **10–11 of every question's 12 tool calls returned errors.**
- **Nothing was retrieved from any graph** in any of the 5 questions: `retrieved` is empty for every graph.
- All 5 questions stopped at `max_steps`.

The agent never got one successful code query. Meanwhile the same model scored 7/7 on paper tools, which take simple arguments.

The `lead` preset's code tools expose the **raw wire request** as the MCP input:

| Tool | Required `request` fields | Schema size |
|---|---|---|
| `search_entities` | 10: `schema_version, request_id, snapshot_id, budget, query, mode, repo_ids, kinds, limit, cursor` | 2.3 KB |
| `get_entity_content` | 11 (adds `context_mode, start_line, end_line, …`) | 2.1 KB |
| `get_architecture_context` | 11, including a full `filter` object and `qi` | 5.5 KB |

An agent has to discover a `snapshot_id`, invent a `request_id`, build a nested `budget` object that obeys the profile ceiling, and send explicit nulls and empty lists. Every one of these is protocol plumbing the server already knows how to fill in. This is a usability defect in Geo-Grapher's MCP surface, and the wire contract is right to stay strict for programmatic clients. The fix is an agent-facing layer in front of it, not a better model.

## 3. Work to reach acceptance, in order

### 3.1 An agent-facing request shape for the code tools (Geo-Grapher)

Do this first.

- **Accept flat, minimal arguments.** Alongside the existing `{graph_id, request}` form, accept the arguments directly:
  - `search_entities(graph_id, query, kinds?, limit?)`;
  - `get_entity_content(graph_id, entity_id, start_line?, end_line?)`;
  - `get_architecture_context(graph_id, focus_id, radius?, pins?)`.
- **Fill everything else server-side:**
  - `schema_version` = latest;
  - `request_id` = a deterministic digest of the call;
  - `snapshot_id` = the graph's current snapshot;
  - `budget` = the connection profile's ceiling;
  - `mode`, `filter`, `grouping`, `qi` and `cursor` = documented defaults.
  
  The fully specified `request` form stays and keeps strict validation. A call is one form or the other, never mixed.
- **Clamp the budget to the profile ceiling; don't reject it.** A request for 4096 tokens under an 1800 ceiling should run at 1800, and the response should say `budget_clamped_to: 1800`. Rejecting it only cost a model a step and taught it nothing.
- **Make errors actionable.** On a validation error, return the field path, what was wrong, and a minimal valid example call for that tool, all within about 400 characters. Today's errors are raw jsonschema or pydantic text.
- **Keep the advertised schemas small.** Expose only the flat arguments in the `lead` and `code` presets. Target: each code tool's `inputSchema` ≤ 1,200 characters (compare 2.1–5.5 KB today).
- **Oracle tests** (write these RED first):
  - each code tool succeeds from its minimal flat call against a fixture graph;
  - an over-ceiling budget is clamped and reported;
  - a bad call's error contains the minimal example;
  - the strict `request` form is unchanged (all existing contract tests still pass);
  - the advertised schema size stays within the target.
- **The same applies to `compile_task_packet` and `analyze_cross_graphs`.** Their schemas are already small; just confirm that defaults fill everything that isn't essential.

### 3.2 Make the benchmark diagnosable (harness)

`tool_errors` is only a count today, so the failure couldn't be read from the results. For each tool call, record:
- the tool name;
- the arguments, truncated to about 600 characters;
- the error code and message, truncated to about 300 characters;
- whether the call succeeded.

Add a per-question summary of the top error reasons. Keep the existing files untouched; this applies only to new runs.

### 3.3 Re-run the code benchmark with a criterion fixed beforehand

Write the criterion into the gate report **before** running:
- ≥ 4/5 markers;
- 0 withheld results;
- 0 wrong-graph calls;
- ≤ 8 tool calls per question on average.

Use the same model as before (Qwen3-Coder-480B), so the comparison isolates the tool-surface fix. Keep the earlier three runs and this one as separate rows; don't take a best-of.

If it still fails, the per-call log from §3.2 decides the next fix. Allow at most one further engineering iteration plus one re-run before escalating to the owner.

Optionally, add one clearly labelled run on the Librarian's configured production lead route, if it is qualified.

### 3.4 The papers result at 1M (6/7): the owner decides the protocol

The miss was answer-side: doc:108 was retrieved but not cited. Present the owner with these options:
- **(a) Score retrieval and answer separately**, with the criterion "retrieval 7/7 and answer ≥ 6/7". This matches what Geo-Grapher actually controls. The current run passes it.
- **(b) Three fresh runs**, all of which must score 7/7. This is stricter and costs about $0.6 more.
- **(c) Accept 6/7 as within run-to-run noise**, and record it.

Recommendation: (a). The model's citation choice isn't a Geo-Grapher property.

Whatever is chosen, run it once, and record both the original and the new result.

### 3.5 The live six-task pilot: owner action, then Codex runs it

The pilot needs the Resource-Library `research_helper` route (`google/gemma-4-26B-A4B-it`) and the Clerk route (`Qwen/Qwen3.5-397B-A17B`) qualified, with a live Core. Codex should:
1. Write the exact owner steps into the gate report: how to start the Resource-Library Core, the qualification command for each role, the expected evidence files, and the estimated cost. Then stop and wait for the owner.
2. Once the routes are qualified, run plan Step 3 as specified: 4 tier-3 block contracts, 1 tier-2 synthesis and 1 tier-1 review on ToolSet. Record the waves, the clerk citation-verification rate, the stale count, the wall time and the cost.

One caveat to note: Qwen3.5-397B **timed out** during wave 2 testing. If it times out as the Clerk, report that as a finding. Don't swap the route without owner approval.

### 3.6 Leakage

Record the probe result as **passing the plan criterion**: 0/29 cross-graph leaks. Keep reporting the prior-knowledge 1/29 separately, as is done now; it's correct not to pool it.

Put the answer-discipline remedy in the wave 5 backlog, not in this gate: abstain when the corpus lacks the subject, and make that a Librarian answer-contract test.

## 4. Testing the application (beyond the unit suites)

The suites prove the components work. These checks prove the application works as a user meets it.

### 4.1 Automated end-to-end, through the installed wheel

Build the wheel, install it with `uvx`, and run against copies of the gate stores:
- **Per-preset MCP smoke.** For `papers`, `code`, `lead` and `cross`, with no model:
  - list the tools;
  - make each tool's minimal call (from §3.1) and require success;
  - make one deliberately bad call and require an actionable error;
  - check that every result stays within `max_result_chars`.
  
  Commit it as `scripts/qa_mcp_presets.py`.
- **A real-store browser pass** (Playwright, against copies of ToolSet and librarian-v2 rather than the tiny fixture):
  - open the spatial view with directed QI and assert the qi groups render;
  - box-select and prune, and assert the derived graph appears and the source snapshot is unchanged;
  - open bridge review on a code pair and decide one candidate;
  - add a folder (a copy of a small project under `--browse-root`), ingest one partition, and assert the new graph appears.
  
  Assert no console errors, and delete everything created in `afterAll`.
- **Latency regression** (C14): cold `get_architecture_context` under 3.0 s on ToolSet for both QI algorithms. Record librarian-v2 too, without gating on it (it's a known carried item).

### 4.2 Manual exploratory pass, for the owner

About 20 minutes. Codex should write this as a checklist in the gate report.

1. Start `geographer serve-graphs --catalog <a copy> --browse-root <a scratch folder>` and open the workspace.
2. Switch graphs, toggle directed QI, open a block, and check that the labels and role badges make sense.
3. Add a folder: browse, preview, untick one partition, ingest, and watch the job finish.
4. Prune a selection, then confirm the original graph is untouched.
5. Review two bridge candidates, accept one with a rationale, and check its state in `list_bridges`.
6. In the Librarian, ask one code question on the `lead` preset with the production lead route, and check that it cites `graph-label/entity:` handles that open in the UI.

### 4.3 Negative tests worth adding

- Picker paths: `..`, a UNC path, a junction, an absolute path outside the root (all exist; keep them in the browser pass).
- A stale cursor after a re-ingest, for every cursor-bearing tool.
- A graph deleted while the Librarian holds a lease on it.
- An over-ceiling budget, an unknown graph label, and a wrong-graph entity ID.

## 5. Process notes

- Keep doing what you're doing: first results are permanent, re-runs are new rows, criteria are fixed before runs, and nothing is merged while a gate is open.
- Budget: about $6.19 of the $10 pool remains. The §3.3 re-run costs roughly $0.3 and an optional paper protocol (b) about $0.6, so there's room. Record the actual cost after each run.
- When §3.1–3.3 pass and the owner has ruled on §3.4 and §3.5, run the full verify plus the full Librarian suite. Then update the gate report with the new rows and a final verdict, and ask the owner before merging either branch.
