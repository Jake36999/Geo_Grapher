# Live six-task pilot — FAIL, 2026-11-14

**The live pilot did not pass.** Two native lead calls failed before dispatch. A separately labelled, type-normalised execution of the real lead-authored plan then reached the Clerk: all four code contracts failed, and the two dependent tasks were skipped. No further paid attempt was run.

The owner explicitly approved Core recovery, a **$0.50 top-up**, **$0.40 total allowance with $2 reserve**, the role probes, scoped tool permissions and an experimental lead override. Seed-2.0-mini's endpoint was closed; the owner then explicitly approved **Gemma** as pilot lead. No model substitution was silent. The closed code-quality cycles were not reopened.

## Environment and readiness

- Resource-Library's actual Core, actual role routes and permission broker; an `explore` session in `map` phase.
- Installed **0.2.0 wheel**, SHA256 `4d903d7df0cb029e332b8bff1e076b122d40dabe8dfab765aaf7615bfcc4450d`; neither application repository's source changed.
- ToolSet graph `g_850b52af2916ae87854c9ada`, snapshot `snapshot:f5029b6bf601fcb2896a3c494e30dc306ced8624436d9334a9f9000931e1abee`, on a disposable database copy.
- Dedicated six-tool `lead` MCP server, exact graph scope, complete-result cap 7,500 characters. Direct six-packet preflight and actual Core discovery/packet preflight passed without a model.
- Code-research profile: temperature **0.2**, FP4 **off**. Effort temporarily 1. Native helper/Clerk qualification and profile gates remained enforced.

| Role probe (one run each) | Result |
|---|---|
| Gemma-4-26B-A4B-it / research_helper | L0 PASS; L1 proposal + continuation PASS, exact observed identity; fresh/screened during pilot |
| Qwen3.5-397B-A17B / clerk | L0 PASS; L1 proposal + continuation PASS, exact observed identity; fresh/screened during pilot |
| Seed-2.0-mini / research_helper for tier-1 review | L0 PASS; L1 unavailable, DeepInfra `InvalidEndpoint.ClosedEndpoint`; no manual retry |

Tier-1 review uses the lead model under the helper policy. After explicit owner approval, Gemma's existing helper qualification covered both helper tiers; Qwen remained Clerk. Gemma's lead use was an **experimental override**, never verified-lead evidence.

## All live attempts, retained separately

| Attempt | Observed result | Paid work |
|---|---|---|
| Native lead, first call | Malformed nested plan: `id/level/description/dependencies`, missing required fields. Operational guard raised `KeyError: tier`; no task dispatched. | 1 Gemma request, $0.00045428 usage estimate |
| Native lead, one documented-schema correction | Required field names present, but tiers were strings `"3"/"2"/"1"`; strict 4/1/1 check refused it. No task dispatched. | 1 Gemma request, $0.00066991 usage estimate |
| **Assisted execution**, separately registered | Only the six tier values were converted to integers in the real model-authored plan. No content, anchors or instructions changed. Native dispatch ran once: **4 failed / 2 skipped / 0 succeeded**. | 4 Qwen requests, $0.02419875 usage estimate |

The first correction supplied documented schema fields, not answer content. The second was deterministic type normalisation with no extra model call. **Neither is counted as an unassisted pass.** Original events, original arguments, corrected plan, both registrations and all receipts remain in `output/phase67-release/live-pilot-20261114/`.

## Actual six-task result

| Layer | Tasks | Result |
|---|---|---|
| 1 | `contract-1`…`contract-4`: configuration load, precedence, profile resolution, validation | **All failed:** `CLERK_FAILED: the model reached its output budget before returning text or a tool call` |
| 2 | `synthesis-1`, depends on all four contracts | **Skipped: DEPENDENCY_FAILED** |
| 3 | `review-1`, depends on synthesis | **Skipped: DEPENDENCY_FAILED** |

- Native dispatcher wall time: **130.531 s** (assisted controller: 130.562 s).
- Clerk contracts returned: **0/4**. All four Qwen receipts report **exactly 1,800 completion tokens**, the task's configured output ceiling.
- Citation verification: **0 verified / 0 unverified; rate undefined**, because no contract reached verification. This is not 100% verification or proof of zero unsupported claims.
- Dispatcher reports `stale: []`, but **no task succeeded**, so its final successful-result freshness check did not run. Do not count this as demonstrated stale-handling success.
- Direct no-model tier-2 preflight omitted **two upstream records** under its 1,800-token profile ceiling. Live synthesis never ran, so this is a separate coverage warning, not a measured live-synthesis outcome.
- No contract semantic spot-check was possible: no usable contract was returned. Live tier-2 synthesis/review, successful citation closure and successful end-to-end coordination remain unvalidated.

## Findings and next engineering work (no fixes or paid retests authorised here)

1. **P2 — agent-facing plan contract is underspecified.** The actual advertised schema is only `plan: {type: object}`. It does not expose nested keys or integer tier types. Native source requires exact `plan_id/server/tasks`, and each task's `task_id/tier/graph_id/anchors/instruction/depends_on`. Add a typed nested schema, valid examples and structured field errors; consider strictly bounded decimal-string coercion. Use RED regressions from these actual calls first. Do not attribute the interface gap solely to model ability.
2. **P2 — Clerk task budget/protocol compatibility.** Connectivity qualification passed, but the real `code_block_contract` task returned no usable text at 1,800 output tokens in all four cases. Investigate reasoning/output-budget handling with deterministic replay fixtures and role-specific representative tasks before deciding whether to alter reasoning settings or the cap. Receipts prove budget exhaustion; they do **not** expose enough internals to assign all tokens specifically to hidden reasoning. No cap was increased and no thinking switch was changed during this run.
3. **P2 coverage warning — bounded upstream delivery.** Inspect which records fit the tier-2 quarter-budget and how omissions should affect synthesis acceptance. Do not bypass the existing cap or silently claim all four contracts were delivered.
4. **Controller defect, separate from product findings.** The first malformed plan hit an operational guard's unchecked `tier` lookup before native validation could return `PLAN_SHAPE`. The as-executed guard is archived. After the run, a new free regression failed, then passed after adding a safe integer-tier shape check: **5 controller tests passed**. No live attempt was repeated for that repair. The earlier guard-startup registration mistake and its corrected free tests are also retained; neither is a model outcome.

The one-valid-plan guard and per-HTTP meter were operational instrumentation around the original registry boundary. Native ToolSpecs, profile/broker/phase checks and application code were unchanged. All six HTTP attempts (retries included if any) were admitted against a pre-reserved $0.34 pilot allowance; no request could consume the $2 pool reserve. Paid web search and other model routes were refused for this packet-only test.

Meter installation restarted only the Core launched for this work, after verifying no active turn, permission request, profile run, action or mutation. The first guard bootstrap failed before Core startup; its logs are retained. The corrected Core used the existing provider dispatch-gate hook and observed the native registry boundary rather than replacing native ToolSpecs. Its final shutdown was clean; no unrelated process was stopped.

## Spending and restoration

- Metered pilot HTTP usage estimate: **$0.02532294** (2 lead calls + 4 Clerk calls), calculated from returned token usage and recorded standard rates; this is not an invoice.
- Qualification billing usage is not exposed by Core. Three **$0.02** conservative holds remain, **$0.06 total**, rather than accepting Core's default evaluation cost of zero as proof of free calls. No historical uncertainty was released.
- Conservative total committed for this work: **$0.08532294**, below the approved **$0.40** allowance.
- Shared pool after the approved top-up and settlement: budget **$14.74739611**, committed **$12.33898379**, remaining **$2.40841232**. Required reserve preserved.

The temporary Core was shut down cleanly when idle. Original role bindings were restored exactly, the Gemma pilot-only override removed, original profile/effort and Ask mode restored, the six scoped tool permissions reset, and the temporary MCP entry removed. The QA copy is marked failed/protected by retention rules. Core was restarted normally and is running at **http://127.0.0.1:56192**.

The restored original lead is **Seed-2.0-mini**, whose endpoint remains unavailable; no permanent lead change was authorised. Removing temporary MCP tools changes qualification fingerprints. The restored Core therefore marks the helper/Clerk evidence stale/experimental for the restored registry; their fresh screening during the pilot remains recorded, and **no automatic paid requalification ran**. Queueing requalification is not executing it.

Machine-readable evidence and artifact SHA256 values: [PHASE67_LIVE_PILOT_RESULT_20261114.json](PHASE67_LIVE_PILOT_RESULT_20261114.json). Prior readiness and first rows remain unchanged. **No further paid pilot or benchmark run, no product-code fix, no tag and no push.** F4 owner acceptance remains pending; the release notes now disclose this failed pilot rather than calling it untested or passed.
