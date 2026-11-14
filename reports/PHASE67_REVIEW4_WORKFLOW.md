# Review 4: recovery-based code research

The owner approved local-only semantic search, a paired FP4 A/B over all 30 development questions, a **$6.50 hard workflow spending cap**, and an additional **$0.25** to retain at least **$2**. No merge or push is authorised. Prior scores and first attempts remain untouched. Wave 4 stays closed at 12/15 and the v1 quality cycle stays closed at its original frozen results.

## Budget and order

`PHASE67_REVIEW4_BUDGET_ESTIMATE.json` records the $6.48155369 estimate based on the prior 90 episodes / 541 completed HTTP attempts, with three additional recovery calls on each enabled episode. It includes generation/two-reviewer provision, 60 A/B episodes, 30 pilot episodes and the 90-episode final cycle. This is an estimate, not an invoice bound.

`PHASE67_REVIEW4_BUDGET_APPROVAL.json` records the owner's subsequent explicit approval. The ledger's spendable lifetime ceiling is **$14.24739611** (starting commitment $7.74739611 plus $6.50), against **$16.25** funded. **$2.00260389** is explicitly reserved outside that spendable ceiling. No fictional API/reservation call was added. The original ledger was backed up before the explicit ceiling update. An estimate above $6.50 requires another owner decision.

Order remains: free measurement fixes; blind reviewed v2 seal; offline tooling and repaired development baseline; L1 then L2 with RED tests/offline/full checks; agent recovery and valid A/B; one registered diagnostic pilot; one registered final cycle and stop. Release preparation may proceed in parallel but no integration approval is inferred.

## Step 1 — measurement and dispatch readiness

- `review4-measurement-red.log`: structured withheld fixture failed before the fix.
- `review4-measurement-green.log`: 4 coverage/structured-code fixtures pass. The detector uses the parsed error code and does not inspect source literals; historical rows are unchanged.
- `review4-readiness-tests.log`: missing, failed, mismatched and stale readiness evidence blocks dispatch.
- Paid `provider_for` now requires an in-process no-model ticket tied to actual evaluator inputs. Main executes the preflight before loading credentials. Unqualified legacy modes fail closed instead of making paid calls.
- `review4-preflight-single-first.log` and `review4-preflight-batch-first.log`: actual installed-wheel list/search/source calls through Loop/Registry and the batch path pass, including graph switching across librarian-v2 and ToolSet. All scripted provider calls use 0.2; zero paid calls.

Preflight receipts remain under `output/phase67-gates/review4/preflights/`. Source/schema/runtime/wheel and question-file hashes invalidate tickets when changed. Each future paid candidate must run again through this free gate. No product source has changed at this point.

## Step 2 — held-out v2 sealed before product work

`PHASE67_HELDOUT_V2_SEAL.json`, SHA256 **`ccb0e6c0ea8380a68e94e9f8571339143572243f7a2b872289e020e33145f02d`**, seals **25** reviewed items. The audit confirms **25/25** two-reviewer approvals, meaningful own documentation, validated question wording and baseline top-20 identifiability; **zero overlap** with v1 entities/support and zero overlap with nine checked original-development/application entities. The lead has not opened v2 questions, keys or selected identities. The rules retain 10 constants, 10 functions, five behaviours; graph balance is 14 Librarian / 11 ToolSet after the disclosed pre-generation quota adjustment.

`PHASE67_HELDOUT_V2_CONSTRUCTION.md` records all rejected and regenerated attempts, output-budget and format failures, key-rule repairs, provenance and construction allocation. JSON container recovery preserves exact id/question strings, rather than discarding repeated keys or rewriting wording. Every accepted item must still pass both reviewers. Static adjacency alone and incidental rule-ID mentions are not sufficient equivalence evidence.

The accepted set passed `audit_heldout_v2.py`: all private artifact hashes match and both product source trees retain SHA256 **`60596057669e6f80bc6534116a5aea3ab0f849d431e906c245891293dca7ee99`** from before construction. No product source changed. Twelve measurement/eligibility/container/dispatch fixtures pass (`review4-measurement-seal-tests.log`). All raw construction attempts and rejected-item decisions remain under the private `review4/heldout-v2` directory.

The refined cost design is `RECOVERY_DESIGN.md`: shared deterministic search/source remedies, at most three executable recovery steps, and at most two additional paid calls (one shared revision and one step-limit synthesis). The revised estimate with a $0.35 construction allowance is **$6.26253291**, inside the owner-approved $6.50 cap. Proving that model-call bound is a precondition for agent paid dispatch; the $2 reserve and lifetime spendable ledger ceiling are unchanged.
# Step 3 — frozen development baseline (2026-11-13)

The committed read-only evaluator reproduces the review exactly on the unchanged v1 reference: question-text recall@8 **13/25**, recorded-agent recall@8 **33/102**, and any-agent-query hit **18/25**. This validates the replay before product changes. Rankings are raw candidates, not a claim that eight cards survive the wire-size cap.

The repaired 30-item development set scores **18/30** for question text and **36/102** for recorded queries at rank 8. The pre-product equal-weight RRF comparator (verbatim question plus each recorded guess) reaches **48/102**. These remain below the offline targets (90% question text; 75% agent queries). No model calls occurred.

Four disclosed repairs are recorded in `data/eval/code-research/repair-record.json`; original frozen keys, raw rows and prior scores are retained. The original Clerk target is the module function `clerk.py.run_one`, as recorded in the snapshot. The offline tool blocks sealed v2 by path and content hashes, validates snapshot IDs, opens canonical databases read-only, and refuses result-file replacement. Three evaluator tests pass.

First baseline files: `PHASE67_OFFLINE_V1_BASELINE.json` and `PHASE67_OFFLINE_DEV30_BASELINE.json`. The proposed RRF comparator is explicitly labelled as a proposal; it is not yet the product recommended strategy.

## Step 4 — L1 first offline result

RED evidence: `output/review4-l1-red.log`, all five new oracles fail on the sealed baseline. First GREEN: 17 source-card/front-door/fusion tests pass. Product multi-query RRF uses bounded 200-candidate pools, exact matches retain priority, duplicate queries are ignored, and single-query ranks are unchanged. Guidance requests the verbatim question and up to two guesses. Weak observations contain confidence metadata and two bounded deterministic hints from snapshot documentation.

First offline L1 row (`PHASE67_OFFLINE_DEV30_L1_FIRST.json`): question recall@8 **18/30**, unchanged; recommended verbatim-plus-guess **48/102**, up from the agent-only **36/102**. FP1 simulation fires **47/102**, recovers to **45/102**; **3/36** originally correct searches trigger (8.33% false-trigger rate conditional on originally correct; 3/47 of triggers). The first simulation uses documentation overlap; this must be aligned to the precise delivered `doc_gist`/`why` detector before enabling recovery. It is explicitly a simulation, not a claim of live episode recovery. FP2 awaits L2. Both offline targets remain unmet. Full verification, installed-wheel preset smoke and the Librarian suite are in progress; no paid agent dispatch is authorised by this result alone.

### L1 detector corrections and retained rows

The first full verify passed: **722 backend tests**, frontend typecheck/build/unit checks and **17 browser tests**. The first installed-wheel preset smoke passed **28/28**. The unchanged Librarian suite is still running.

A sixth RED oracle proved that full documentation outside the delivered card could suppress a legitimate weak-hit signal. The detector now computes overlap from the same bounded `doc_gist` and `why` fields as the client sees, across the top eight hits. In offline replay, those cards use the actual agent query for their match explanation, while overlap is assessed against the original question. This avoids granting the simulation a better observation than the real client.

Two additional first result files are retained separately: `PHASE67_OFFLINE_DEV30_L1_PREVIEW.json` is the intermediate original-question-card simulation (**33** triggers, **39/102** after recovery); `PHASE67_OFFLINE_DEV30_L1_DELIVERED.json` uses the actual-query cards (**32** triggers, **38/102** after recovery). Both have **1/36** false triggers among originally correct queries. Raw recommended multi-query recall remains **48/102**, with **18/30** question-text recall. These modest recovery gains are reported as measured; they do not close the offline targets. A full verify and fresh installed-wheel smoke are being repeated for the corrected candidate. Future offline artifacts include product/evaluator source hashes.

## Step 4 — L2 first offline result and overhead

Core RED: five privacy/integrity/semantic oracles fail before `semantic.py` exists. Integration RED: the ingest hook and shared channel ranker fail before implementation. Core/front-door integration now passes nine semantic tests, plus source-card/fusion regression checks. Semantic extras remain off by default. Local model assets were explicitly provisioned once, without source input, at Hugging Face revision `bf8b056651a2c21b8d2565580b8569da283cab23`; file hashes are in `PHASE67_REVIEW4_SEMANTIC_MODEL.json`.

First L2 replay (`PHASE67_OFFLINE_DEV30_L2_FIRST.json`):

| View | Recall@8 |
| --- | --- |
| Lexical question text (retained comparator) | 18/30 (60%) |
| Local semantic + lexical question text | 27/30 (90%) |
| Lexical recorded agent queries | 36/102 (35.3%) |
| Local semantic + lexical agent queries | 69/102 (67.6%) |
| Agent queries plus simulated FP1 | 77/102 (75.5%) |
| Recommended verbatim question + agent guess, both channels | 93/102 (91.2%) |

FP1, starting from the enabled-channel agent result: **12/102** triggers, **2/69** false triggers conditional on originally correct retrieval (2.90%), **77/102** after recovery. Separately, FP2 simulated from lexical-only results: **32/102** triggers, **1/36** false triggers (2.78%), **53/102** after semantic recovery. These separate simulations are not added together or presented as episode success. Runtime scheduling/shared recovery accounting is still pending. Raw agent retrieval alone remains below 75%; guided retrieval and the FP1 simulation exceed it. Rankings are candidate ranks and do not establish capped delivery or answer quality.

Explicit read-only backfill (`PHASE67_REVIEW4_SEMANTIC_BUILD_FIRST.json`) encoded **3,879** Librarian and **2,420** ToolSet declarations, in **1.419 s** and **0.871 s** respectively (loaded-model population time). Derived storage was **25,075,712 bytes** after Librarian and **40,726,528 bytes** total after ToolSet. Both canonical store hashes were unchanged. Six representations report truncation. Controlled real-model ingestion overhead on a separate 100-declaration synthetic fixture is retained in `PHASE67_REVIEW4_SEMANTIC_OVERHEAD_FIRST.json`; it is not extrapolated to whole-repository ingest latency.

L1 corrected full verify passed **723 backend tests**, frontend checks and **17 browser tests**, with **28/28** installed-wheel preset checks. The first full Librarian run had **1 failed / 2,195 passed**: an existing SBOM test rebuilt its ZIP artifact between hashing and comparison, crossing a ZIP timestamp boundary. The fixture now reuses the same artifact (Librarian feature commit `0beed83`); its four SBOM tests pass, and the full suite is being repeated. First failing evidence is preserved in `output/review4-l1-librarian-full.log`. L2 full checks have not yet run.

### L1 closure and L2 runtime candidate

The corrected full Librarian run passed: **2,196 passed, 2 skipped, 5 deselected**, in 649.25 s (`output/review4-l1-librarian-corrected-full.log`). This closes L1's required verification after preserving the original failing SBOM row.

The L2 candidate now wires FP1/FP2 search remedies through standard MCP metadata, with deferred baseline evidence, connection/episode scope, once-per-pattern records and a shared local step charge for joint fusion. FP6 logs the existing real-candidate menu (zero extra executable steps) and resolves only after an offered ID is accepted. Four search-integration oracles and the FP6 logging oracle were RED before front-door wiring/logging, then passed. A real stdio MCP test verifies metadata transport without adding nested requirements to the model-facing schema. The agent-side shared ledger and receipts are still pending. The full L2 Geo verify and Librarian suite are in progress.

Controlled ingestion overhead first row: median **0.059 s** additional time per synthetic 100-declaration ingest, over three paired trials; derived storage **663,552 bytes** each. This uses a loaded real local model and is not a whole-repository latency claim. A local model load and inference passed with socket connection, send and address-resolution methods blocked. The first network-guard test setup failed because replacing the socket class broke SSL import; that invalid setup is retained separately and is not reported as network access. The encoder fingerprint now also pins Python version and architecture; the first namespace remains retained and a separately measured qualified namespace was explicitly built.

### Runtime replay and capped delivery

`PHASE67_OFFLINE_DEV30_L2_RUNTIME_FIRST.json` invokes the actual front-door recovery function in deferred then automatic mode. Raw recall@8 improves **52/102 → 82/102 (80.4%)**, with **38** extra local steps total and **at most one per query** (FP1/FP2 can share a step). FP1 triggers **38/102**, with **3/52** false triggers conditional on originally correct retrieval; FP2 triggers **32/102**, with **1/52** false triggers. Runtime confidence clears in 35 FP1 and 29 FP2 cases; those signals are not answer-correctness scores. The initial independent simulations remain unchanged.

Actual 7,500-character front-door delivery on disposable backups (`PHASE67_REVIEW4_SEMANTIC_DELIVERY_SECOND.json`) exposes **21/30** targets on the first page, below raw **27/30**. Most envelopes fit only 3–4 rich cards. A new failing oracle demonstrated that omitted candidates lacked actionable pagination. The fix adds bounded `offset` / `next_offset` pagination without changing rank, canonical IDs or source cards. With a fixed two-page bound applied to every question from response metadata, delivery reaches **27/30 (90%)**, every envelope stays within cap, and canonical hashes remain unchanged (`PHASE67_REVIEW4_SEMANTIC_DELIVERY_PAGINATION.json`). Requests never branch on answer keys. The first delivery-script setup failure is preserved separately; it made no search calls.

The exact installed wheel plus its optional semantic extra passed real stdio search/content, minimal-schema, metadata, provenance and cap checks (`PHASE67_REVIEW4_SEMANTIC_INSTALLED_FIRST.json`); default-off installed-wheel preset smoke passed **28/28**. Initial L2 full verification passed **738 backend tests**, frontend checks and **17 browser tests**. The L2 full Librarian run passed **2,196**, with 2 skipped and 5 deselected. After pagination, full backend verification had **738 passed / 1 failed**: the existing real-ToolSet cold directed-latency check measured **3.368 s** against 3.0 s while other local QA was running. That first failure is retained; a controlled isolated recheck and then a full verification are required, without relaxing the threshold.

### Step 4 verification closed

The isolated cold directed check passed without changing the 3 s threshold. The controlled full pagination candidate passed **739 backend tests**, frontend typecheck/build/unit checks and **17 browser tests** (`output/review4-l2-pagination-controlled-full-verify.log`). L2's full Librarian suite passed **2,196 tests**, with 2 skipped and 5 deselected; installed-wheel default-off preset smoke passed **28/28**, and the optional semantic-extra installed-wheel search/content smoke passed. The failed concurrent latency row remains preserved. First-page delivery is still explicitly **21/30**; the bounded two-page result is **27/30**. No answer-quality claim is inferred from either.

Step 5 begins with seven failing generic agent-recovery oracles on the isolated Librarian feature branch (`output/review4-agent-recovery-red.log`). The agent-side shared ledger, source-open/revision workflows, FP7 integration and first-draft reporting are not implemented yet. No paid A/B, pilot or final cycle has been dispatched.

### Step 5 implementation and pre-dispatch verification

The RED-first recovery candidate is now implemented on the isolated Librarian feature branch (`b66a4d6`). FP3 directly opens the highest-ranked relevant unopened source; FP4 detects a delivered defining identifier missing from the answer; FP7 supplies bounded tool-free synthesis at the ordinary limit. A shared episode ledger enforces at most three extra executable steps, at most two additional logical model invocations and once per pattern, including front-door receipts across connections. Joint FP3/FP4/FP5 revision consumes one invocation. Detector inputs are runtime metadata and question words, never answer keys. Revisions with unprovided entity citations or source lines are rejected. The actual initial draft and its availability status remain separate from the chosen final answer. Early recovery does not create a fictional no-recovery answer.

Seven initial RED oracles and subsequent rank, scope, failed-open, display and citation oracles preceded their fixes. The focused Librarian recovery/step-limit checks passed **27 tests**; its full suite passed **2,216**, with 2 skipped and 5 deselected (`output/review4-agent-librarian-full.log`). Geo full verification passed **747 backend tests**, frontend typecheck/build/unit checks and **17 browser tests** (`output/review4-agent-full-verify.log`). Another **15** focused measurement/protocol checks passed after adding the registration/scoring boundary fixtures. First unsuccessful real-wheel dry runs remain separate: they exposed rank selection and an already-opened top candidate, both repaired with failing tests first. Fresh OFF and ON actual installed-wheel dry runs now pass (`output/review4-readiness-final-ab-{off,on}.log`), with zero paid calls. Every paid phase must repeat the dry run against its frozen inputs before credentials are loaded.

The owner approved a **$6.50** workflow cap and **$0.25** top-up. The lifetime spendable ceiling is **$14.24739611**, preserving **$2.00260389** outside that ceiling. Actual workflow spending so far is **$0.26683144**, including construction and two engineering reviews; no paid A/B, pilot or final episode has run. The refined remaining planning estimate is **$5.91253291** (total actual-plus-estimate **$6.17936435**, below the cap). `review4_budgeted_harness.py` reserves and settles every HTTP attempt under this ceiling and records episode/HTTP receipts; the third no-network meter fixture passed with zero real ledger mutations. Interrupted/uncertain attempts retain their full reserve. Registration prevents phase redispatch, output replacement and candidate/snapshot drift.

The A/B uses the complete 30-question development set OFF then ON, unchanged questions/model/temperature/window/tools. Retain FP4 as the default recommendation only for at least one net additional correct answer and no additional wrong-graph or withheld event. The owner-requested pilot and final explicitly run all recoveries ON regardless of that default recommendation, with both facts reported. Scoring is frozen before dispatch: original five require all legacy markers; repaired development and sealed v2 require any registered equivalence marker. No post-run key edits, citation-based score overrides or replacement runs. Pattern resolution signals and answer correctness are reported separately.

Clarification on delivery experiments: 7,500 characters was the capped/default-window delivery QA configuration. The frozen paid protocol declares a 1,048,576-token loop window and retains its existing dynamic external result allowance (125,829 characters, with server packing below that). The public provider advertises a 262,144-token native window; retaining the frozen declaration is not a claim that hosted million-token requests were tested. Model/rates are recorded in `PHASE67_REVIEW4_MODEL_CARD.json`.

The same recovery candidate wheel also passed **5/5 real-store browser scenarios** (`output/qa-real/review4-agent-final-results.json`): directed ToolSet QI, prune preserving the source snapshot, actual code-pair bridge review, add-folder ingestion, and picker containment. Managed QA cleanup ran before preparing a fresh copy under `D:/Librarian_V2/tmp/geo-grapher-qa-workspaces/recovery/20261113-agent-final`. Browser teardown reports no extra graphs and all baseline graphs preserved. After the server stopped, the explicitly verified fixture junction was removed as a link entry and the copy marked complete. Original stores and benchmark inputs were not modified by browser QA. Migration/recovery documentation and the bounded F3 security delta are prepared on feature branches; no merge or push.


## Review 4 step 5 — closed 60-episode paired A/B

Both registered batches closed complete without replacement or resume. Registration SHA-256: `072a7da26431e261dba8e31576fd5212628aa9ec830ee76759bf15e23eefe2db`. Raw and scored first rows remain separate under `output/phase67-gates/review4/`.

| FP4 | Final correct | Actual eligible initial drafts correct | Tool calls | Errors | Wrong graph | Structured withheld | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| OFF | 23/30 | 27/30 | 158 | 0 | 0 | 0 | $0.8167936 |
| ON | 25/30 | 23/28 | 156 | 2 | 0 | 0 | $0.7806601 |

The two ON episodes with early recovery have no invented pre-recovery draft. Mean tool calls: **5.23/question**. FP4 meets the registered keep-default rule (+2 final correct, no additional wrong-graph/withheld); the difference is diagnostic evidence from one paired comparison, not a statistical reliability guarantee.

A material regression is preserved: OFF revisions turned four correct drafts into wrong finals; ON turned two into wrong finals. Inspection of these six development episodes shows XML-form tool requests returned as plain response text during a tool-free revision, despite `Reply.tool_calls` being empty. Such text was incorrectly accepted as an answer and sometimes marked runtime-resolved. No tool was actually executed from that XML. This exposes an answer-validation defect rather than missing retrieval. The diagnostic pilot will retain the registered all-ON candidate, after which its failures and this pattern receive deterministic offline recovery validation before final registration. The A/B is not rerun or rescored.

Pattern runtime resolved/triggered across both arms: FP1 **16/18**, FP2 **12/14**, FP3 **2/11**, FP4 **2/6**, FP5 **5/10**, FP6 **1/2**, FP7 **1/1**. These signals are not gold correctness or independent causal effects; `ab.summary.json` also records eligible wrong-to-right counts and final correctness for every pattern. Full answers and initial drafts remain private in `ab.scored.json`.

Workflow actual spend so far: **$1.86428514** ($0.26683144 before evaluation plus $1.5974537 A/B). Remaining pilot plus final planning estimate **$3.94168860**; actual-plus-remaining **$5.80597374**, within the approved $6.50 cap and protected reserve. One diagnostic pilot follows, 30 development questions, all recoveries ON, unchanged candidate and temperature 0.2. It is not a gate.
