# Phase 6–7 release: F1 owner decision sheet

2026-11-14 · **OWNER STOP — recommendations only; none enacted.** Quality evaluation is closed. No further paid cycle, qualification probe, merge, tag or push is authorised by this sheet.

| # | Recommendation | Evidence, trade-off and decision needed |
|---|---|---|
| **1 · W3-5 firewall** | **Apply Ψ unless `shared_citation == 1` or `neighbour_jaccard >= 0.2`.** Keep Ψ = 0.25 and score weights. | Both wave-3 proposals were homonyms: one generic shared neighbour bypassed the firewall (precision 0/2). Stronger filtering may reduce recall. Choose **apply amendment** or **retain G4**. RED boundary tests precede implementation. |
| **2 · W2-7 dirty master** | **Have the owning agents make focused commits for release work and set aside their remaining work themselves.** Require a clean master before any Librarian merge. | Current inventory: **13 modified tracked + 5 untracked files**, including item 3 below. [All 18 exact paths](F:/uv-data/Geo_Grapher/reports/PHASE67_F1_LIBRARIAN_DIRTY_FILES.md). Ownership cannot be inferred reliably from Git. Confirm **who will clear them and whether by commit or setting aside**. Codex will not stage, stash, revert or edit them. |
| **3 · Delegation flags** | **Approve a separate lead-owned commit of `--reasoning-effort` / `--no-thinking`, with focused free tests first.** | Defaults are unchanged; controls precede reservation. No flag tests were found in the three delegation modules inspected; historical “74 passed” does not cover them. Require unchanged-default, payload-mapping and no-network dry-run tests. Choose **owner commits with tests** or **owner sets aside**. |
| **4 · Future C14** | **Adopt median of 3 cold <3.0 s AND maximum <3.5 s, prospectively only.** | Three fresh processes, same snapshot/wheel, quiet-machine flag, all samples retained. Median reduces noise; maximum limits spikes. Choose **adopt prospectively** or **retain single-sample rule**. No historical rescore. |
| **5 · Resource-Library pilot** | **Release with the six-task live pilot explicitly deferred.** | Exact-role qualification and Core are required ([gate §10](F:/uv-data/Geo_Grapher/reports/PHASE67_WAVE4_GATE.md)). Live coordination, verification and timing remain unvalidated; no “pilot passed” claim. Choose **accept the known limitation** or **wait for qualification**. F4 acceptance remains required. |

**Verified branch state:** Geo `phase67-wave4` **317b874** (FP4-off documentation); Librarian master **c4eb76f** (dirty), survey **70ffe38**, wave 4 **737ea28** (FP4 default off, temperature 0.2). Both Librarian feature worktrees remain separate. No integration started.

**Tests:** F1 is read-only inspection/documentation: **0 new tests, 0 paid calls**. The lead records **2,221 passed / 2 skipped / 5 deselected** at `737ea28`, not rerun here. After F1, repeat free offline retrieval, original-five no-model source/packet checks and scripted FP4-off behavior; these cannot remeasure live answer accuracy. Preserve historical results: wave-4 gate 12/15 PASS; FP4-on v2 93% (CI 85–97%), development 87%, registered gate FAIL. The released default differs; real-usage questions remain untested.

Reply with decisions **1–5** (or approve recommendations and identify the file owners/cleanup plan for **2**). Decisions will then enter the master decision log. **F2 waits for those answers; every merge has its own later OWNER stop. Never push.**

Sources: [roadmap Part B](F:/uv-data/Geo_Grapher/reports/PHASE67_REVIEW_3_AND_FINALISATION_ROADMAP.md), [Review 5](F:/uv-data/Geo_Grapher/reports/PHASE67_REVIEW_5_SCIENTIFIC_ASSESSMENT.md), [wave-3 evidence §2](F:/uv-data/Geo_Grapher/reports/PHASE67_WAVE3_GATE.md).
