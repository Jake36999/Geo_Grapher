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
