# F2: merge approvals and outcomes

## Current OWNER STOP — Geo-Grapher integration

2026-11-14: A, B and C below were approved and completed after the required combined throwaway test. Librarian master is clean at **8ea7c45**; its tree equals the tested integration tree. Combined suite: **2,235 passed / 2 skipped / 5 deselected**. The throwaway branch was deleted; its log remains. Parked WIP and both pre-rebase backup branches remain preserved.

**Requested approval:** merge `codex/phase67-geo-integration-20261114` into Geo-Grapher `main` with `--no-ff`. Main remains **0f12dfa**. The scratch merge is **7ec2c4b**, followed by test-only fixture repair **5250e8f** and the evidence-record commit containing this request; no production code changed after the scratch merge. See the final reported branch tip for the exact approval target.

| Check | Result |
|---|---|
| Backend first attempt (retained) | 761 passed / 1 fixture failure / 1 superseded timing case deselected |
| Backend after fixture-only repair | **764 passed / 1 timing case deselected** |
| Frontend | Typecheck and build PASS; **16 unit tests** |
| Standard browser suite | **17 passed** |
| Installed-wheel presets | **28/28 passed**; largest response 7,326 / 7,500 characters |
| Fresh real-store browser journeys | **5/5 passed**; no extra graphs, baseline preserved, test junction removed |
| Prospective C14, 3 fresh installed-wheel processes | **2.496, 2.603, 2.637 s**; median 2.603 < 3.0; max 2.637 < 3.5; PASS |

The timing case was operationally replaced, not silently dropped: the old test applies the superseded single-sample rule. This run used the owner's approved rule with explicit `--quiet-machine`, the identical ToolSet snapshot/focus, the same wheel and three independent database backups/processes. All first samples are retained. Permanent quiet-flag wiring is still F3 work.

The integration wheel is still **0.1.1**, SHA256 **e1b31be4a5258c050c526ae3d3bd54a1dc8a8248f200176465a326c700316373**. The 0.2.0 version, stable-contract declaration, final guides/security pass and release build remain F3. Both-merged-mains installed-wheel search→packet follows this merge approval. F4 requires owner acceptance. The live six-task pilot remains deferred and unvalidated. No paid evaluation, tag or push occurred.

Evidence: `PHASE67_F2_GEO_INTEGRATION.json`, `PHASE67_F2_GEO_PRESETS_FIRST.json`, `PHASE67_F2_GEO_C14_FIRST.json`, `PHASE67_F2_GEO_C14_HARNESS.txt`, `PHASE67_F2_GEO_REAL_COPY.json` and the append-only integration report.

## Historical Librarian approval request — completed

2026-11-14 · **OWNER STOP. Nothing below has been merged or pushed.**

Original **D:/Librarian_V2 master is clean at c4eb76f**. Please approve or decline each action separately; approval of one does not imply the others.

| Approval | Proposed `--no-ff` merge into Librarian master | Validation |
|---|---|---|
| **A — first** | `geo-grapher-survey` **70ffe386d75d787861bc1067fb840c9fd0651964** | Rebase onto current master was up to date; **2,143 passed**. |
| **B — after A** | `geo-grapher-wave4` **db55b891daddad0d6bf8a5ef2444c5a1f3125e3a** | Rebased onto A, no conflicts; **2,225 passed**. FP4 off, temperature 0.2. |
| **C — separately, after B if approved** | `codex/phase67-delegation-controls` **9f3a0d826f6078524f4da5aae8d2489e4f55cb8b** | Ten new tests were RED first; **88 delegation/validation tests**, full master-based suite **2,149 passed**. |

All three passing full suites also recorded **2 skipped / 5 deselected**. The wave-4 first full run had **2 failures / 2,223 passes** from an ambient-library working directory; the unchanged candidate then passed from neutral **F:/uv-data**. The first result and both logs are retained in the [integration record](F:/uv-data/Geo_Grapher/reports/PHASE67_RELEASE_INTEGRATION.md).

C was tested separately against master, not already combined with B. If approved, the combined Librarian suite will be run after that merge before advancing. No further paid check is needed.

**Excluded:** `wip/pre-phase67-release-2026-11-14` is frozen at **610b4496…**. Its five commits remain WIP, unreviewed and ownership-unverified. All **17/17 raw Git-blob SHA256 values** match the pre-cleanup contents. It is not part of A, B or C and will not be merged, rebased, edited or pushed.

**Already complete:** prospective firewall (18 bridge tests after RED boundaries); master cleanup and byte manifests; free offline retrieval checks; original-five no-model target/source/packet checks **5/5 each**; scripted FP4-off checks **32 passed**; actual default-off no-model preflight. Historical quality rows are unchanged and no new answer-accuracy measurement is claimed.

**Next after the approved Librarian merges:** Geo-Grapher scratch integration and its verify, installed presets, real-store browser checks and wheel rebuild; then another OWNER stop before merging to main. The installed-wheel no-model search→packet check on both merged mains follows that approval. F3/F4 hardening and owner acceptance remain subsequent stages. Never push; tags and pushes require separate owner instruction.
