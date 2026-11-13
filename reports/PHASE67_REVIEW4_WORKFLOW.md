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

