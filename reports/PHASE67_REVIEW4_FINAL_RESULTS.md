## Review 4 final cycle CLOSED — registered verdict FAIL

All six raw batches closed complete: **90/90** episodes. Registration and candidate hashes matched; the v2 seal was verified and its key first opened by the scorer after complete closure. No replacement run, question/key edit, source tuning or further paid dispatch follows. Prior rows, raw answers, first drafts, first failed checks, scoring files and receipts remain separate.

| Set | Run | Final correct | Eligible initial drafts correct | Tool calls/question | Errors | Wrong graph | Structured withheld | Ledger charge |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Held-out v2 | 1 | 24/25 | 24/25 | 4.08 | 0 | 0 | 0 | $0.4667396 |
| Original development | 1 | 5/5 | 5/5 | 5.60 | 0 | 0 | 0 | $0.1257292 |
| Held-out v2 | 2 | 22/25 | 23/24 | 4.20 | 1 | 0 | 0 | $0.4982047 |
| Original development | 2 | 5/5 | 4/4 | 6.20 | 0 | 0 | 0 | $0.1582648 |
| Held-out v2 | 3 | 24/25 | 24/25 | 4.12 | 0 | 0 | 0 | $0.4873735 |
| Original development | 3 | 3/5 | 3/5 | 6.60 | 0 | 0 | 0 | $0.1635422 |

**The mandatory original-development condition failed:** runs were **5/5, 5/5, 3/5 = 13/15**, requiring 5/5 every run. Held-out **24/25, 22/25, 24/25 = 70/75 (93.3%)** exceeds both its >=64/75 overall and >=20/25 per-run marks. Combined **83/90 (92.2%)** does not override the failed development condition. Wrong-graph and structured-code withheld are both **0**; mean tool calls **4.47** (402 total), below 10. There was one tool error, handled through FP6; errors were not an independent zero-error pass condition.

Eligible actual initial drafts score **83/88 (94.3%)**; two episodes recovered before producing an unrecovered draft and have no invented counterfactual. No eligible wrong draft became correct in this cycle; **two correct drafts regressed** after FP4 revisions. The two early-recovered episodes ended correct, so this must not be described as recovery improving overall accuracy from the first-attempt fraction.

| Pattern | Triggered | Runtime signal resolved | Final correct among triggered | Eligible wrong-to-right |
|---|---:|---:|---:|---:|
| FP1 | 15 | 12/15 | 13/15 | 0/15 |
| FP2 | 15 | 12/15 | 13/15 | 0/15 |
| FP3 | 8 | 0/8 | 7/8 | 0/7 |
| FP4 | 11 | 0/11 | 9/11 | 0/11 |
| FP5 | 3 | 0/3 | 3/3 | 0/3 |
| FP6 | 1 | 1/1 | 1/1 | 0/0 |
| FP7 | 1 | 0/1 | 1/1 | 0/0 |
| FP9 | 7 | 7/7 | 6/7 | 0/6 |

FP8 is the dispatch prerequisite rather than an answer remedy: all six paid paths passed their fresh real-tool no-model preflights before credentials/dispatch. Pattern signals are not gold answer correctness and co-occurring recoveries are not independent causal attribution. FP9 safely rejected seven protocol proposals; five eligible correct drafts were retained. FP4 met its earlier registered A/B keep rule but shows two harmful prose revisions here; its runtime signal remained unresolved. The configured policy is left unchanged after this final cycle.

Observed bounds across all 90 episodes: **maximum 3 extra executable steps**, **maximum 2 extra logical model invocations**, no repeated pattern in an episode. **489 HTTP attempts**, including **21 recovery HTTP attempts**, all completed with no uncertain reservations. Maximum observed provider prompt: **38,068 tokens**; the frozen million-token declaration is not a claim of hosted million-token testing.

Post-closure miss inspection (diagnosis only; no rescore):

- Development run 3, `dev-02`: target metadata and target content were recorded, but the answer omitted `lead_agents` and discussed adjacent concurrency mechanisms. `dev-03`: `run_one` appeared in target metadata but had no target source-body range recorded; the answer discussed adjacent queue/routing implementations. FP9 retained that incorrect draft when a later revision proposed XML tools.
- Held-out run 2, `heldout-v2-02` and `heldout-v2-17`: correct initial drafts became citation-only/fragmentary prose after FP4. Targets had recorded content. Citation identity validation alone did not preserve an adequate answer; the unresolved check still allowed replacement. No further fix or trial is made.
- `heldout-v2-25`, all three runs: the answer named `_lines_through`, `SessionStore`, the correct file and canonical citation, but placed class/method names separately. The sealed markers require contiguous `SessionStore._lines_through` (or its full qualified form). This is a mechanical scoring limitation; all three frozen misses remain misses. Even altering that interpretation would not repair the independent failed development gate.

Final cycle charge: **$1.8998540**. Entire Review 4 workflow ledger charge: **$4.50626474**, below the approved **$6.50** cap. Funded uncommitted pool: **$3.99633915**, including the protected **$2.00260389** reserve. These are registered-rate API-usage ledger charges, not an invoice claim. No uncertain HTTP charge remains in this final cycle.

Evidence: `PHASE67_REVIEW4_FINAL_REGISTRATION.json`, `PHASE67_REVIEW4_FINAL_SUMMARY.json`, `PHASE67_REVIEW4_FINAL_AUDIT.json`; private full rows and receipts under `output/phase67-gates/review4/`. Verified candidate: Geo source `af7ee5e`, Librarian `970fb23`, qualified wheel `1a687fd8…`. Full checks remain **757 Geo backend**, frontend checks, **17 browser**, **2,221 Librarian**, **28 preset**, and **5 real-store browser** passes.

**STOPPED as requested.** No new product changes, retries, additional cycles, merge, push, release or live Resource-Library qualification follow. F3 preparation remains on the feature branches; the live route qualification and release approvals remain separate owner prerequisites.
