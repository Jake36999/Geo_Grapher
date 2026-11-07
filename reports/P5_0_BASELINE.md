# P5.0 — baseline and additive actor schema

6 November 2026. Status: baseline/schema gates passed; P5.1 may begin. v1.1 runtime serving belongs to subsequent increments and is not represented as complete here.

The pinned ToolSet archive was re-ingested without executing its source or modifying its worktree. Revision: `f8bc1ec4c54884293dace635275e95c685b03371`; selected-content digest: `e50bcf9c66d7cbf4e2d0ef15b1274f3ba918197abaee87e508f7f1f0e365261e`. Snapshot publication validation passed with zero parse failures. Ingestion took 14.4292 seconds on this development host.

| Baseline measure | Count |
| :--- | ---: |
| All relationships | 12,526 |
| Exact / candidate / unresolved relationships | 1,502 / 395 / 10,629 |
| Distinct emitted Python call sites, identified by AST spans | 11,486 |
| Exact known-internal call sites | 1,221 |
| Candidate known-internal call sites | 366 |
| Unresolved sites, target locality unknown | 9,899 |

These are classification counts, not accuracy/recall estimates. Imports and future inheritance edges are excluded from the call-site denominator; alternative targets are counted once per occurrence. An unresolved external-symbol placeholder does not prove that its target is external. Baseline details do not have structured reason codes, which are disclosed as legacy unavailable. Full reproducible manifests and occurrence lists: `output/phase5/baseline-triage.json`; reproduction: `output/wheel-env/Scripts/python.exe scripts/phase5_measure.py baseline`.

The historical 8,132-token observation did not record an exact focus/request in the gate report. A fresh reproducible request is therefore recorded in `output/phase5/context-baseline.json`, using the existing Stage 3 snapshot, file grouping, Nearby breadth, 8,192 tokens, and deterministic focus `aletheia_toolchain/_quarantine/manifest_doctor.py`. It returned 9 nodes and 7 relationships in **8,122 whole-envelope o200k_base tokens**. Removing duplicate node IDs, node AST/WL hashes, repeated node revisions and initial edge cursors from that same response reduced its measured whole-envelope count to **5,171 tokens**, a 36.3% reduction. This ablation retains primary canonical IDs, other handles and original budget metadata; it is a cost experiment, not a valid served response or final v1.1 result. It does not substantiate 70% removable overhead or a 5x density gain. Previews will add useful semantic cost; later aliasing and actual packing need separate measurement.

P5.0 deliverables: `contracts/v1.1/geographer.wire.d.ts`, generated strict schemas, `contracts/v1.1/ACTOR_SCHEMA.md`, source/claim register and independent adversarial fixture requirements. All seven operations and the viewport retain versioned declarations. The draft removes duplicate IDs/node fingerprints/initial edge cursors and defines summaries, group previews, witness/reason previews, aliases and three-tier source folding. Semantic cross-field invariants, disclosure on truncation and continuation behavior are specified in the addendum.

Validation: original baseline **71 tests passed**, including pinned real ingestion, using the isolated environment with MCP 1.30.0. Three new P5.0 contract tests passed; the v1.1 TypeScript declarations type-check, generated schemas match their source digest, and both approved specifications plus all four original contracts retain their original hashes. The global interpreter's incompatible MCP 2.x was detected during collection; no source migration was made to accommodate that unrelated environment.

No parser/resolver upgrade was required to measure this baseline. P5.1 comparisons must use the identical pinned input, independent fixtures, source/claim assumptions and the same occurrence measurement script. Actual actor-schema serving, token packing changes and full UI grouping/source folding remain P5.2–P5.3 work.
