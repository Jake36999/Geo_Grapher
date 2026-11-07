# V4 outcomes and bounded repair stage — 7 November 2026

The saved V4 inputs/results reproduce **8/12 one-shot passes**: Llama-3.3-70B 1/4, Meta-Llama-3.1-405B 4/4 and Qwen3-Coder-480B 3/4. All request hashes match; each public requested endpoint is representable. All three models now return the correct stale-document flat path. The V3 enum defect is fixed. These are two small development tasks with one trial per arm/model, not a model ranking or full release-acceptance result.

Audit: `output/phase5/round4-recorded-audit.json`. Original request/response files, score artifacts and oracle requirements are unchanged. No paid call ran in this follow-up.

## What remains

The four failed answers concern answer discipline rather than a newly observed extraction/identity failure:

| Model / task | Public validation issue |
|---|---|
| 70B direction / graph | Adds a second-hop callee outside the requested direct-call target |
| 70B stale document / flat | No explicit documentary assessment and no original document citation |
| 70B stale document / graph | Missing declared provenance label and original document citation |
| 480B stale document / flat | Missing declared `basis:source` provenance label |

The existing validator caught three. The 70B stale-flat answer exposed a gap: document citation checks were triggered by selection of `document:stale`, so omitting the assessment label bypassed them. The validator now follows the **public documentary task requirement**, independently of whether that particular conclusion was selected. Answer status requires an explicit assessment namespace and original documentary citation. It does not supply a hidden verdict or automatically insert `document:stale`; if the conclusion is undetermined, the actor may abstain. The namespace requirement is explicit in new V4.1 prompt contracts and also derives from the existing documentary flag on archived V4 prompts.

All four failed answers are now caught by oracle-free public validation. None of the eight passing answers needs a repair. A public validation pass still does not establish independent answer correctness, which remains a separate rubric check.

## Implemented repair stage

`evaluation.prepare_repairs` prepares at most one additional request for an answer with repairable validation issues. It reads only original prompts, responses, usage and public validators; it does not call the grader or consult expected answer labels to choose/fill repairs. Missing original source, exhausted budgets or an already-recorded repair block another attempt. No answer field is silently filled in or rewritten.

For these direct-call/source tasks, `evaluation.repair_context` retains **every original source record verbatim**, the original question, snapshot/filter/model/runtime scope, public identity metadata, prior answer and validation issues. It omits non-source graph/rules envelopes and discloses their counts/kinds. This reduces redundant retransmission; it fetches no new source or graph evidence. Other task kinds keep full original context. The same policy is used by the opt-in process repair loop and by the external-harness handoff.

Each repair receives only the **remaining** original 16,384-token local/provider cap and remaining original 1,024-token output reservation. Parent request/answer counts and reported provider usage are charged first. The importer checks both cumulative ledgers, pins the model, verifies the unchanged parent result receipt and labels scores as a separate `bounded_repair` stage. A mismatch, excess, or missing result is not accepted. Model execution and provider spend enforcement remain the user's harness responsibility.

## Prepared requests — do not rerun the twelve one-shot cases

Root: `output/phase5/actor-v4-repairs-20261107/`.

| Packet | Additional requests | Local request tokens | Remaining total cap | Remaining output cap |
|---|---:|---:|---:|---:|
| `70b/requests.jsonl`: direction / graph | 1 | 3,034 | 6,532 | 759 |
| `70b/requests.jsonl`: stale / flat | 1 | 3,321 | 13,198 | 758 |
| `70b/requests.jsonl`: stale / graph | 1 | 3,320 | 6,224 | 775 |
| `500b/requests.jsonl`: stale / flat | 1 | 3,250 | 13,229 | 706 |
| `300b/requests.jsonl` | **0** | — | — | — |

Every packet fits the local preflight including its remaining output reservation and framing margin. Provider tokenization/framing can differ; actual reported usage must also remain within that remaining cap. These are prepared requests, not successful repaired answers. Preserve parent artifacts and use the model pinned in each request. In particular, **do not reset the repair's output limit to 1,024 or grant a fresh 16,384-token budget**.

Regeneration (offline):

```powershell
& './output/wheel-env/Scripts/python.exe' -m evaluation.prepare_repairs --directory output/phase5/actor-contract-v4-final-20261107 --output NEW_REPAIR_DIRECTORY
```

The existing user-owned runner can consume each model packet using its ordinary `prompt`, `response_format`, `max_output_tokens` and result format. It must retain the different request hash and all usage. Score returned repairs separately:

```powershell
& './output/wheel-env/Scripts/python.exe' -m evaluation.handoff score --handoff output/phase5/actor-v4-repairs-20261107/70b --results ACTUAL_70B_REPAIR_RESULTS.jsonl --model meta-llama/Llama-3.3-70B-Instruct
```

Use the `500b` directory and exact Qwen model ID for its one request. The 405B packet is empty; it needs no additional call. Keep **8/12** as the one-shot result. Any later post-repair result must report both attempts' cost/tokens and be distinguished from initial accuracy. No post-repair success, superiority, deployment or acceptance closure is claimed here.

## Verification

**98 targeted offline tests pass** in 17.38 seconds (`output/actor-round4-regressions.log`), covering the missing-assessment bypass, source-preserving compaction, oracle-free selection, no retry for valid/blocked/exhausted/already-repaired cases, pinned model/parent receipt checks, and cumulative scoring. Existing feasibility, source/claim, wire/budget and MCP transport checks remain included. The single warning is the existing Starlette TestClient deprecation. All four prepared packet hashes, original receipt hashes and remaining-budget reservations were also verified. No full browser suite, large benchmark or live model study was run.
