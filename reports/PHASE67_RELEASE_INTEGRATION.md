# Phase 6–7 release integration record

## F1 implementation and free pre-integration checks — 2026-11-14

The five owner rulings are recorded in the master plan's **Release owner decision log**. Quality evaluation is closed; all checks here are free and no new paid cycle is authorised. Prior result rows remain unchanged.

### Owner parking and clean master

The re-inspected inventory matched exactly: 13 modified tracked and 5 untracked paths, original Librarian master `c4eb76ff1c2b78346fd7743dadda5d6b170427b5`. All 18 pre-cleanup files were backed up with SHA256 before mutation. The 17 non-delegation files were committed **unreviewed**, from that exact master, on `wip/pre-phase67-release-2026-11-14`:

| Area | Files | Commit |
|---|---:|---|
| ui-wave reports | 3 | `47dacf5310eedf38c77e55355a20be1cb13cf0ea` |
| ui | 1 | `c8b3d4d3b4aee1cb33b19e49e8dcd8d20e5ff91e` |
| src | 7 | `db3aa4ce71461e4bfa87e6c280408b3c98d090d5` |
| tests | 5 | `b568a73fcc7590dc8b8f54967dfcc1790560811d` |
| untracked transcript | 1 | `610b4496a6af314d660da7fe936e1f087bf2dc5b` |

Every commit is labelled **“WIP, unreviewed, owner-parked; ownership not verified”**. Raw Git blobs were staged without text filters; all **17/17 Git-blob SHA256 values and parked working-file SHA256 values match the pre-cleanup bytes**. No review, merge or rebase of this parked branch was performed. It is frozen at `610b4496…` and must remain untouched.

Only after this proof were the 12 tracked original paths restored and the five backed-up untracked originals removed. Git initially reported empty-diff modified statuses after restoration; only independently verified HEAD-equivalent bytes were re-added to refresh index metadata, leaving **no staged changes**. The delegation file was preserved separately until its tested commit existed, then restored to HEAD too. Original master is now **clean, still at c4eb76f**, with no merge or push.

Manifests: `PHASE67_F1_PRE_CLEANUP_MANIFEST.json`, `PHASE67_F1_PARKING_MANIFEST.json`, `PHASE67_F1_MASTER_CLEANUP.json`, `PHASE67_F1_MASTER_CLEAN.json`. The first captures every original SHA256 and backup path; the second independently hashes Git blob contents before cleanup. No parked code is included in integration.

### Isolated delegation controls — awaiting its own merge approval

Branch **`codex/phase67-delegation-controls`**, based directly on master c4eb76f, commit **`9f3a0d826f6078524f4da5aae8d2489e4f55cb8b`**. The captured owner change was applied only after **10 RED tests** for unchanged defaults, all seven effort levels, `--no-thinking`, and a no-network dry run. The committed source matches the captured change under the repository's LF text normalisation. No unrelated original-master work was included.

| Check | Result | First evidence |
|---|---|---|
| New control tests before change | **10 failed** | `output/f1-delegation-controls-red.log` |
| Four delegation/validation modules after change | **88 passed** | `output/f1-delegation-modules-green.log` |
| Full committed-master-based Librarian suite | **2,149 passed / 2 skipped / 5 deselected** | `output/f1-delegation-full-suite.log` |

This is a separate master-based candidate, not the wave-4 feature suite. No live provider compatibility/qualification is claimed. **Do not merge this branch without owner approval.**

### Firewall and deferred pilot

W3-5 now applies Ψ = 0.25 unless `shared_citation == 1` or `neighbour_jaccard >= 0.2`, retaining all score weights. Before implementation, boundary checks gave **2 failed / 4 passed**; afterward the bridge suite gives **18 passed**. Citation bypass, just-below/exactly-at/just-above Jaccard 0.2, no support and the observed weak-neighbour regime are covered. Evidence: `output/f1-firewall-boundaries-red.log`, `output/f1-firewall-green.log`. The wave-3 first scores are not rescored or rewritten.

The draft release Known Limitations now records the owner-accepted six-task pilot deferral: live coordination, verification and timing remain **unvalidated**. No role probe, pilot, production-lead paid question or substitution was run. C14's prospective three-cold-sample ruling is recorded; the quiet-machine verification wiring belongs to release hardening and is not claimed implemented here.

### Free release checks before F2

| Check | Current result | Comparison / limit |
|---|---|---|
| Default lexical-only dev30 offline recall@8 | Questions **18/30**; recorded queries **36/102**; recommended style **48/102**; runtime **36→38/102** | Matches the prior lexical/L1 results. |
| Optional local Model2Vec dev30 offline recall@8 | Questions **27/30**; queries **69/102**; recommended **93/102**; runtime **52→82/102** | Matches the final measured retrieval candidate; optional channel remains local-only and off by default. |
| Original five through Librarian + installed wheel | **5/5 natural queries return a target; 5/5 source ranges; 5/5 task packets** | No model answers generated. Known development target IDs select the source/packet conformance fixture, so this is not proof of autonomous answer selection or accuracy. No exact-identifier fallback was needed. |
| Current wave-4 scripted recovery / step-limit tests | **32 passed** | Includes the inverted FP4-off pin and explicit on/off mechanism tests; `output/f1-fp4-off-scripted-tests.log`. |
| Installed-wheel actual no-model preflight | **PASS**, default FP4 **off**, temperature **0.2** | No override supplied; `output/f1-default-off-dry.log`. Zero paid calls, including protocol-answer guard and real MCP calls. |

Machine-readable first outputs: `PHASE67_F1_OFFLINE_LEXICAL_FIRST.json`, `PHASE67_F1_OFFLINE_SEMANTIC_FIRST.json`, `PHASE67_F1_ORIGINAL5_NOMODEL_FIRST.json`. Pre-integration wheel: `output/phase67-release/f1/dist/geo_grapher-0.1.1-py3-none-any.whl`, SHA256 **`6dcff054b5a1d3f4743209fada19479c94765d5bdff96ec30e522165e00b5545`**. This is not the final merged 0.2.0 release artifact or F2's merged-mains cross-repository exit check.

The measured quality rows remain **wave-4 12/15 PASS**, **held-out v2 70/75 = 93% (CI 85–97%)**, **development 13/15 = 87%**, and the **registered final-cycle gate FAIL**. The measured configuration had FP4 on; the release default is off at Librarian `737ea28`. Free checks show no retrieval/tool-contract regression and verify the changed default; they do **not** measure fresh live answer accuracy or real-usage representativeness. No further paid check was needed or attempted.

F1 decisions, parking, isolated flags and pre-F2 free checks are now complete. F2 proceeds by rebase/testing only. Every merge, tag and push remains separately owner-controlled.

## F2 Librarian integration candidates — OWNER STOP before merges

The original master remains **clean at c4eb76f**. Backup refs preserve survey `70ffe38` and pre-rebase wave 4 `737ea28` (`codex/phase67-survey-pre-rebase-20261114`, `codex/phase67-wave4-pre-rebase-20261114`). The parked branch remains **610b4496…**, with all 17 raw Git blobs checked again against the pre-cleanup SHA256 values. Neither the parked branch nor the separate delegation-controls branch is an ancestor of either integration candidate.

| Candidate / attempt | Commit | Full-suite result | Evidence |
|---|---|---|---|
| Survey rebased onto current master | **70ffe386d75d787861bc1067fb840c9fd0651964** | **2,143 passed / 2 skipped / 5 deselected** | `output/f2-survey-full-suite-first.log` |
| Wave 4 on survey, first launch context | **db55b891daddad0d6bf8a5ef2444c5a1f3125e3a** | **2 failed / 2,223 passed / 2 skipped / 5 deselected** | `output/f2-wave4-on-survey-full-suite-first.log` |
| Same wave-4 candidate, neutral launch directory | **db55b891daddad0d6bf8a5ef2444c5a1f3125e3a** | **2,225 passed / 2 skipped / 5 deselected** | `output/f2-wave4-on-survey-full-suite-neutral.log` |

Survey's rebase was already up to date. Wave 4's 22 commits rebased cleanly onto survey, with no conflict resolutions or product edits. Comparing the old wave-4 tree to the new one shows **only** `src/resource_librarian/deploy_survey.py` and `tests/test_deploy_survey_geo_grapher.py`; the FP4-off policy and temperature 0.2 are preserved and checked from the committed source.

The first wave-4 suite was launched inside a worktree beneath the Geo-Grapher repository's pre-existing `.librarian` directory. Two global CLI tests (`test_rules_and_capabilities`, `test_doctor_never_shows_key_values`) discovered that ambient library and failed. Both focused cases passed from **F:/uv-data**, then the entire unchanged candidate passed from that neutral directory. No test expectations or product code were changed, and no ambient-library cleanup/takeover was attempted. The initial complete failing run is retained, not replaced. For this nested worktree, run the suite from outside any library with an absolute test path and the explicit source `PYTHONPATH`.

`PHASE67_F2_LIBRARIAN_CANDIDATES.json` records exact commit/tree hashes, backup refs, log hashes, absence of excluded branch ancestry, master cleanliness and the committed code-research policy. Delegation remains separately tested at **9f3a0d8** (88 focused module tests; full 2,149 passed), not silently included in the survey/wave-4 suite results.

**STOP — explicit owner decisions required before any merge.** Requested actions and their order are in `PHASE67_F2_MERGE_APPROVAL.md`. No merge, push, tag or paid evaluation was performed. Geo scratch integration, its full verify/preset/browser/wheel checks, merged-mains cross-repository smoke and F3/F4 remain pending the staged owner approvals. The six-task live pilot remains deferred and unvalidated.

## Owner-approved Librarian merges — 2026-11-14

The owner approved A, B, C conditionally on a throwaway merge/test first. `codex/phase67-librarian-premerge-20261114` was created from **c4eb76f** and merged all three approved hashes in order with `--no-ff`. Its full suite ran from neutral **F:/uv-data**, outside `.librarian` ancestry: **2,235 passed / 2 skipped / 5 deselected**, `output/f2-librarian-combined-premerge-full.log`. No master mutation preceded this pass.

Tested integration commit **baac8307efe3373abe30b5cf1a70e60de911072c**, tree **f6479caaf040da4dcfb066befd22e8ca3ba974c7**. Master then received the approved `--no-ff` merges:

| Approval | Source | Master merge commit |
|---|---|---|
| A | survey 70ffe38 | **5499993c49e9792a4def9c56a260ca91c21cf6db** |
| B | wave 4 db55b89 | **7c5391996d075792fffa10107ab95852b5e9e87e** |
| C | delegation controls 9f3a0d8 | **8ea7c45ae814fed35a1f71ecaac6ec307ad9b31f** |

Master is clean at **8ea7c45…**, and its tree is **identical** to the tested integration tree. The throwaway worktree and branch were removed only after that proof. Its Git log, test log, tested hashes and merge evidence remain in `PHASE67_F2_LIBRARIAN_THROWAWAY_LOG.txt`, `PHASE67_F2_LIBRARIAN_PREMERGE.json`, `PHASE67_F2_LIBRARIAN_MERGED.json` and `PHASE67_F2_LIBRARIAN_THROWAWAY_CLEANUP.json`. No push or tag.

The parked WIP remains frozen at **610b4496…**. It overlaps wave 4 in `agent_runtime.py`, `loop.py`, `mcp_client.py` (including line-ending churn in the latter); un-parking requires an owner-performed manual merge. Both pre-rebase backup refs remain in place until after release. The two cwd-sensitive CLI tests remain unchanged; the Known Limitations/follow-ups record requires a later self-containment fix.

Geo-Grapher scratch integration now proceeds. Its merge to main still requires the next explicit OWNER approval.
