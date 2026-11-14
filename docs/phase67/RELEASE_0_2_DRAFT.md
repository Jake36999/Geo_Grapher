# Geo Grapher 0.2.0 — draft release notes

Status: feature-branch preparation. Version remains 0.1.1; no merge, stable-contract declaration, release tag or push is implied. The final wave-4 code cycle passed **3/5, 5/5, 4/5 = 12/15**. On 2026-11-14 the owner approved the F1 decisions and accepted the live pilot as a deferred, unvalidated release limitation. Integration, hardening and F4 owner acceptance remain pending. The later quality measurements and changed FP4 default must be recorded separately in the final notes (Review 5); the earlier wave-4 row is unchanged.

## Features prepared across waves 1–4

- Readable labels, role badges, edge styling, affinity layout, discovery cards and calibrated federation.
- Snapshot fingerprints and drift reports, notebook ingestion, folder onboarding, independent-graph diffs and clone candidates.
- Directed helper contraction, reviewed bridge proposals and lineage, prune by derivation and guarded Add folder workflows.
- Tiered task packets, route-aware external-result bounds, Clerk/dispatch contracts, bridge impact and theory conformance.
- Constant indexing, full comment-block support, stemmed lexical retrieval and preservation of ranked hits during packing.
- Agent-friendly flat calls, canonical citation identities, bounded recovery choices, response-delivery hashes/ranges and final-at-step-limit answers.

## Current contract digests

These are feature-branch digests, not the final release freeze. Recompute and verify them after approved integration:

| File | SHA256 |
|---|---|
| `contracts/v1.1/geographer.wire.d.ts` | `cd167603c6165e4cb1d353f1bb963d9a2cb4f3e7e4cd042c108a1bd5abffa16e` |
| `contracts/v1.1/generated/geographer.wire.schema.json` | `cad2774ae4f2a7dc3a7f08ac541590a5dbc1c294c40876a3b2082591c4907183` |

See [migration notes](MIGRATION_0_2.md) before opening a catalog or regenerating snapshots. See the [security report](../../reports/PHASE67_F3_SECURITY.md) for live-server evidence and the limits of that pass.

## Known limitations and wave-5 work

| Area | Evidence / follow-up |
|---|---|
| Live six-task pilot | **DEFERRED by owner decision, 2026-11-14.** Resource-Library role qualification remains outstanding. Live coordination, verification and timing are **unvalidated**; no passing pilot is claimed. |
| Parked Librarian WIP | `wip/pre-phase67-release-2026-11-14` remains frozen and unreviewed. It overlaps wave 4 in `agent_runtime.py`, `loop.py` and `mcp_client.py`; the last also contains line-ending churn. Un-parking requires a **manual merge by the owner**, not an automatic replay. |
| CLI test isolation | `test_rules_and_capabilities` and `test_doctor_never_shows_key_values` discover a parent `.librarian` folder. Run release tests from a neutral directory; make these tests self-contained in a later change. |
| Answer discipline | Prior-knowledge slip 1/29 remains; missing-corpus abstention needs the wave-5 answer contract |
| Code-agent quality | Final cycle 12/15 meets its registered gate, not perfect accuracy; further ranking/completion work uses the new delivery metadata |
| Performance | Librarian-v2 QI remains roughly 6–11 seconds cold; current C14 has little worst-sample headroom |
| C14 proposal | Future median-of-three <3.0 s and maximum <3.5 s is a proposal only; no retroactive rescore |
| Bridges | W3-5 firewall threshold remains an owner decision; candidate recall is limited by documentary/code naming overlap |
| Contraction and clones | W3-2 parallel-twin restriction; clone size floor/lambda exclusion remain carried work |
| Workspace initialization | Git-ignored tool/vault exclusions and a `reports` role remain carried work |
| Lineage | External Librarian artifact registration remains constrained by read-only integration |
| Large cross-graph results | Use counts, filters and paging; large evolution diffs do not fit one small envelope |
| Parsing / compatibility | Optional JavaScript failure on `ui/app.js` and nonfatal `server/discover` startup warnings remain recorded |

Rulings and evidence indexes: [master plan](../superpowers/plans/2026-11-11-phase6-7-00-master.md), [wave-4 gate](../../reports/PHASE67_WAVE4_GATE.md), [finalisation roadmap](../../reports/PHASE67_REVIEW_3_AND_FINALISATION_ROADMAP.md). No open ruling is changed by these notes.

## Release prerequisites

The owner has accepted deferral of the six-task pilot; it is no longer a release blocker, and it remains unvalidated. Role qualification and a running Core are still prerequisites for any later execution of it. Complete the F4 hands-on/real-question acceptance, obtain each F2 merge approval and review the final documents. Build 0.2.0 from the approved merged code, verify both repositories and the installed-wheel cross-repo path, freeze v1.1 and obtain release sign-off. Tagging and any push require separate owner instruction. Those release actions have not been performed.
