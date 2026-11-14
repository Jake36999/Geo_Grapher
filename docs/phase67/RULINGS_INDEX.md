# Phase 6–7 rulings index

Historical rulings/results stay in their original reports. This index identifies current release decisions without rescoring them.

| Source | Release consequence |
|---|---|
| [Master D1–D6 and F1 decisions](../superpowers/plans/2026-11-11-phase6-7-00-master.md) | Base layout, graph strata, lineage, result ceilings, no Forge integration, presets; current owner amendments are in F1. |
| [Wave 1 gate](../../reports/PHASE67_WAVE1_GATE.md) | Layout/federation repairs and original visible-win evidence retained. |
| [Wave 2 gate](../../reports/PHASE67_WAVE2_GATE.md) | Fingerprints, drift, workspace/clone evidence and carried issues. W2-7 cleanup resolved only by frozen owner parking. |
| [Wave 3 gate](../../reports/PHASE67_WAVE3_GATE.md) | Directed contraction, bridges and bounded cross-graph evidence. W3-2 restriction remains; W3-5 prospectively amended by F1-1. |
| [Wave 4 gate](../../reports/PHASE67_WAVE4_GATE.md) | 12/15 PASS, zero cross-graph leakage, paper retrieval/answer scoring, all attempts and role qualification steps. |
| [Review 5](../../reports/PHASE67_REVIEW_5_SCIENTIFIC_ASSESSMENT.md) | Quality track closed; 93% held-out / 87% development as measured; registered FAIL stands. FP4 off after measurement; real usage untested. |
| [Integration record](../../reports/PHASE67_RELEASE_INTEGRATION.md) | RED/green evidence, byte manifests, owner-approved merges, free checks and stops. |

Owner rulings, 2026-11-14:

- F1-1 / W3-5: Ψ = 0.25 unless `shared_citation == 1` or `neighbour_jaccard >= 0.2`; unchanged weights. No historical rescore.
- F1-2 / W2-7: 17 original files byte-preserved on frozen `wip/pre-phase67-release-2026-11-14` at 610b4496. Owner manual merge required to un-park overlaps; never replay automatically. Keep pre-rebase backups until after release.
- F1-3: delegation reasoning controls separately tested and approved into master; defaults unchanged.
- F1-4: prospective C14 median(3 cold) <3.0 s, max <3.5 s; same snapshot/wheel, fresh processes, quiet-machine flag, every sample kept.
- F1-5: release with pilot deferred; live coordination, verification and timing unvalidated.
- Optional local semantics approved; no hosted source embeddings. Optional NumPy does not change the pure-Python base layout.
- F2: Librarian A/B/C approved after combined testing and merged. Geo scratch 6c41756 approved and merged at 990f127. No push authorised.
- F3 preparation authorised on merged mains; v1.1 stable for 0.2.0. F4 owner sign-off, tagging and pushing remain separate decisions.
