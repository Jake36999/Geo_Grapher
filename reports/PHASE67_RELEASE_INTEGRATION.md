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
