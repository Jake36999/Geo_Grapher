# F2: Librarian merge approvals requested

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
