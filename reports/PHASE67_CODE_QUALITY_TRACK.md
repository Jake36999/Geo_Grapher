# Post-wave-4 code-research quality track

This is the separately authorised quality track from `PHASE67_CODE_AGENT_PERFECT_SCORE_PLAN.md`, not a new wave-4 release gate. Wave 4 remains closed and passed at **12/15**. No merge or push is authorised. All previous gate rows and raw attempts remain intact.

## 1. Blind held-out set: sealed before product changes

Commit `0655729` seals 25 questions and keys, with seed **20261113**, against the two immutable snapshots listed in `PHASE67_CODE_QUALITY_HELDOUT_SEAL.json`. The baseline product commit is `d670d20`. Quotas are 10 constants with comments, 10 documented functions, and 5 behaviours involving an entry and 1–2 exact documented callees; 13 librarian-v2 and 12 ToolSet questions. Eligibility excludes tests/generated/vendor/external entities, duplicate or trivial identifiers, the five development markers, and documentation containing those markers. Sampling did not inspect benchmark answers. The implementing lead has not read the selected identifiers, questions or key.

The independent writer received only associated documentation, with defining and supporting identifiers redacted. The answer key was produced mechanically from the sampled canonical entities, not by the author. Raw private artifacts are retained under `output/phase67-gates/code-quality-track/`; their hashes, author model and receipt are committed in the seal. These files must remain unavailable to product workers and fixtures until the final cycle. Automated format/identifier checks do not establish semantic question quality; no human semantic review is claimed.

| Set-building attempt | Outcome | Cost / receipt |
|---|---|---|
| Initial wrapper invocation | Rejected safe-ID task argument before provider dispatch; sample retained unchanged | No provider call |
| GLM-5.3-Flash | Output budget exhausted without question text; raw response and receipt retained | $0.00303790 reserved charge; `20261113T133424-c13531e4` |
| MiMo-V2.6-Flash, same sample and redacted packet | 25 question fields; two mechanical JSON-key repairs and one automatic identifier anonymization, preserving question meaning; sealed | $0.00059836; `20261113T133512-0c9c4d6e` |

Pool commitment after set building: **$5.47175031 / $10**, approximately **$4.52825** remaining. The existing cap applies to all development and final calls, including retries. No budget increase is implied.

## 2. P1/P2 evidence

`code-quality-p1p2-red.log`: four new source-grounded integration tests failed on the baseline. Fixtures cover value/comment/match/reader cards, CRLF-preserving source hashes, cross-file usage, explicitly requested ranges, short-function constants, untrusted comment content and a tight envelope cap. Existing single-line constant assertions now request that exact line explicitly.

First replay, `development-scent-oracles.json`: **2/8**. Retained, not replaced. It revealed cap retries changing the search candidate pool and a replay assumption that the first entity was the requested definition. Neither is treated as a model failure.

| Local check | Retained outcome |
|---|---|
| Four new initial oracles | 4 RED before implementation |
| Initial full verify (`verify1`) | 694 backend, frontend and 17 browser checks passed; later replay still exposed missing real-graph behaviour |
| Replay 2 | 5/8; exposed candidate read omission and cap loss of fifth-ranked hits |
| Replay 3 / 4 / final | 8/8 each; hashes checked against snapshot bytes |
| Compact projection full verify (`verify-final`) | 1 failed / 695 passed: node citation handle compatibility regression |
| Citation correction full verify (`verify-final2`) | 697 backend, frontend 16 unit/typecheck/build, 17 browser passed |
| Long reader-name oracle | RED, then GREEN; bounds preserve the function-name suffix |
| Final full verify (`verify-final3`) | **698 backend, frontend 16 unit/typecheck/build, 17 browser passed** |
| Exact installed wheel, every preset | **28/28**, no model; full envelope <=7,500 characters |
| Exact installed wheel, real-store browser | **5/5**: ToolSet directed QI, prune preserving source, real-code bridge review, add-folder/partition, path refusals |

The P1/P2 wheel is `output/phase67-gates/code-quality-track/quality-dist/geo_grapher-0.1.1-py3-none-any.whl`, SHA256 **`159877aea26a3f1c678652bb804fea4edb0a3339f75ee0fa40a6c21004b000e6`**. Preset evidence is `preset-smoke.json`; browser evidence is `output/qa-real/results-quality-p1p2.json`. QA retention cleanup ran before testing. The disposable copy is complete, its five original graphs preserved and extra graphs removed; only its verified test-owned junction entry was removed after the server stopped, with its target preserved.

Cards use snapshot assignments/comments/docs, matched text and bounded reader names. Constants open with leading comments plus up to three static read sites, <=40 source lines; short functions expose bounded constants/value descriptors. Exact explicit ranges retain their old meaning. Source and comment content is marked untrusted. Candidate reads remain explicitly **candidate**, including the existing fallback-window read edge. No static candidate is promoted to an exact dependency. Every contextual range has an exact UTF-8 hash and source location. Optional context is dropped with omission metadata when necessary.

Search now fits a compact projection of one materialized candidate pool, retaining a prefix of its original ranking. No P5 ranking change was made. The internal 32k materialization cap does not expand the output profile: a tier-3 regression verifies the complete recounted result remains <=1,200 tokens even when a caller requests the lead budget. An independent DeepInfra review (`20261113T135353-c0cf32eb`, $0.00202690) raised four unsubstantiated findings about internal budgeting, cached results and truncation. They were rejected against the output-profile regression, whole-envelope recount and explicit truncation metadata; its raw review remains retained.

## 3. Development self-check A/B protocol (before dispatch)

One run of the original five with P1/P2/P4 and self-check disabled, then one run with the same product and self-check enabled. Same approved Qwen3-Coder-480B route, production temperature **0.2**, 1,048,576-token declared window, library-scoped lead preset and ordinary 12-step budget. This is diagnostic, not the final cycle. Keep P3 only if it increases the number of correct development markers, with no withheld or wrong-graph calls, no newly invented citations, and mean tool calls <=8. A tie does not justify retaining an extra call. Retain both rows and all HTTP receipts. No repeated A/B.

## 4. Final-cycle protocol (registration pending tested candidate)

Exactly one final quality-track cycle: original five and sealed held-out 25, each run three times independently, **90 episodes** total. The exact tested wheel, Librarian source, harness, frozen snapshot IDs, question/key hashes and production route policy will be registered before dispatch. No product changes between runs. The implementing lead must not inspect held-out episodes or keys until all three held-out runs finish. Scoring follows collection, not feedback during implementation.

Development requires **15/15**. Held-out requires **at least 68/75**, with **at least 22/25 in each run** (integer equivalents of >=90% aggregate and >=85% per run). Both require zero withheld, zero wrong-graph calls and mean tool calls <=8. Defining-identifier markers are the registered answer criterion; source/citation delivery remains separate evidence. Misses will be classified from coverage as `not_retrieved`, `retrieved_not_opened`, or `delivered_not_used`, with unknown/clipped evidence explicitly disclosed.

Stop after this cycle whatever the outcome. No extra run, question replacement, ranking tuning, merge or push follows without a new user request. The passed wave-4 release result remains unchanged.

Diagnostic P3 A/B OFF: `{"calls": 14, "correct": 0, "cost_usd": 0.028890999999999993, "enabled": false, "self_check_rejected": 0, "tool_errors": 14, "total": 5, "withheld": 0, "wrong_graph": 0}`.

Diagnostic P3 A/B ON: `{"calls": 10, "correct": 0, "cost_usd": 0.026502999999999992, "enabled": true, "self_check_rejected": 0, "tool_errors": 10, "total": 5, "withheld": 0, "wrong_graph": 0}`.

Diagnostic A/B decision: **do not retain P3** under the predeclared criterion. No repeat A/B.

### Diagnostic validity and corrective action

The two rows above are **invalid for comparing P3 effectiveness**, not product/model answer-quality measurements. All **24 tool calls were refused**: the harness selected `agent_profile=code-research` without supplying its `ProfileStore`, so Registry correctly reduced the caller to consult. The implementing lead introduced this setup error. No graph evidence reached either arm. The costs, raw attempts and numerical rows remain unchanged; neither 0/5 is presented as a valid model score.

There is no repeat A/B under the one-run-per-arm instruction. P3 therefore has **no valid demonstrated benefit** and was reverted in Librarian commit `7b47c68`; P4 remains in `d98cbbe`. This is an inconclusive diagnostic, not evidence that self-checking is ineffective.

The harness now supplies the same vault-backed `ProfileStore` as the application. `profile-access-smoke.json` proves actual installed-wheel list/search/content calls through `Harness.run` and Registry: **3/3 successful**, four scripted provider calls all at **0.2**, **zero paid calls**, with actual source coverage. The first smoke invocation's isolated-import error and corrected smoke log are both retained. An independent **25-question synthetic offline batch** also passes graph switching, fresh workspaces, unscored collection and refusal to overwrite the first output, without opening any held-out artifact. Seven coverage/one-shot tests pass. Supplemental constant-card IDs are logged separately from source delivery to avoid claiming they were absent merely because their source was not opened.

Pool commitment after set building, review and the invalid A/B: **$5.52917121 / $10**, **$4.47082879** remaining. The uncertain first GLM author call retains its conservative reserved charge; it is not recorded as a successful accepted output. The repaired MiMo author output is marked partial, and the unsupported independent review findings are rejected in the delegation ledger.

### Final candidate validation before registration

The P4-only Librarian runtime passes its **full suite: 2,196 passed, 2 skipped, 5 deselected**, in 605.98 seconds (`output/code-quality-librarian-full.log`). No product source changed during that suite. P3 is absent from the resulting source. The existing guarded step-limit synthesis remains; no extra self-check call is enabled.

Geo Grapher retains the exact P1/P2 wheel and its complete 698-test/frontend/browser verification above. Later evaluation-harness changes have **9/9 focused tests** for bounded source provenance, supplemental cards, exact range hashes, one-shot execution, delayed key reads and partial-run closure. The synthetic blind batch passes 25/25 without a model. A delivery-verifier smoke independently reconstructs the already captured development constant's two returned ranges from immutable SQLite source bytes: **2 verified, 0 invalid**, including its definition line. The actual HTTP A/B receipts all recorded temperature 0.2; the final runner will reject any batch with a different observed temperature.

Final scope is **P1 + P2 + P4**, no P3 and no P5. The final cycle is the one authorised cycle, not a retry of wave 4 or of the invalid diagnostic. Its six raw batches remain separate; scored held-out files are additional artifacts, never replacements. Coverage-based miss classifications describe canonical-entity/card retrieval and hash-verified returned source separately, and explicitly mark clipped/invalid evidence as unknown.

## Registered single final quality-track cycle

Registration: `reports/PHASE67_CODE_QUALITY_FINAL_REGISTRATION.json`, SHA256 `23981aadedb4757f63be580b9b2117768e46817c41b912daafdf494e6d79af6a`. This is the only authorised quality-track cycle: dev 15/15; held-out >=68/75 and >=22/25 per run; zero wrong-graph/withheld; mean calls <=8. 90 episodes, three runs each, at the registered production profile. No product changes, replacement questions or extra cycle; stop whatever the result.
