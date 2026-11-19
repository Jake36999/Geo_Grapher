# Changelog

## Unreleased

- UI: one top bar, a canvas tool rail, a zoom slider, and a right panel with Inspect, Graphs and **Build** modes.
- Build mode: Add a folder (with a folder map and a Copy as ASCII text version), Combine graphs and Link graphs now live in the Build tab. The ingest review is a wide sheet that shows how the folder was read down to the depth it is split into separate graphs.
- Ingest policy: a source with no licence file is labelled "cited, not published as our own work" and still ingested and copied like any other. It is a label, never a gate. See [the ingestion policy](docs/INGESTION_POLICY.md).
- Build mode, operators: **Keep only or remove** (select on the canvas, press the scissors, then choose in the Build tab; the counts of what stays and what is dropped come first), **Compare graphs** (what two graphs share and what only one has; read-only), and **Link graphs** (declare a link between two graphs from the whole graph, the selected item or a typed reference, and take it back). See [Build operators](docs/BUILD_OPERATORS.md).
- Ingest review: the role the scan guessed for a part can be corrected in the sheet. A correction changes the label and the stratum, never what is read.
- Each graph has its own accent colour, shown beside its name and on its enclosure when several graphs are shown; it can be changed and is remembered for the browser.
- Threads: each relationship family is one neon colour (dark theme) that fades away from the node it leaves, so direction reads from the fade and never from a blend of two colours. A link declared between two graphs now behaves like every other thread: the same single-colour fade, and hovering it shows who it joins, how, and why, with the end bubbles ringed and the other threads dimmed.
- API: `POST /api/graphs/{id}/derive-preview`, `POST /api/graphs/{id}/prune` accepts `keep_rel_paths`, `POST /api/graphs/compare`, `POST /api/graphs/links`, `DELETE /api/graphs/links/{bridge_id}`, and `role_overrides` on `POST /api/workspace/ingest-execute`.

## 0.2.0 — prepared 2026-11-14, awaiting owner acceptance

Phase 6–7 waves 1–4 and the closed code-quality track are integrated locally. No release tag or push has occurred.

- Wave 1: readable labels, role badges, edge styling, affinity layout, discovery cards and calibrated federation.
- Wave 2: snapshot fingerprints and drift reports, notebook ingestion, folder/workspace onboarding, independent-graph evolution diffs and clone candidates.
- Wave 3: directed helper contraction with certificates and additive expansion; reviewed snapshot-bound bridges, proposal decisions and lineage; prune by derivation; guarded Add folder; bounded cross-graph reports.
- Wave 4: six-tool presets, tiered cited task packets, route-aware result bounds, Clerk/dispatch contracts, bridge impact and theory conformance. Directed QI is exposed in the spatial UI.
- Quality track: flat calls with server defaults/clamping, constant indexing and usage context, canonical IDs and actionable errors, whole-envelope size caps, response coverage, multi-query lexical search, bounded recovery and optional local semantics. Librarian returns a guarded best-effort answer at the step limit.
- Shipped code-research defaults: temperature 0.2, FP4 self-check off. Optional `geo-grapher[semantic]` uses local Model2Vec; FastEmbed is separately optional. Semantics are off by default; source is never sent to hosted embedding services.
- Prospective owner rulings: stronger homonym firewall (Ψ = 0.25 unless shared citation = 1 or neighbour Jaccard ≥0.2; weights unchanged), and C14 median of three fresh-process samples <3.0 s, maximum <3.5 s. Historical scores are unchanged.
- Release hardening: v1.1 stable with byte digests; future contract changes go to v1.2. Free verification builds the wheel and checks all presets/caps; latency requires `-QuietMachine`.

Measured results remain separate: wave-4 gate **12/15 PASS**; held-out v2 **70/75 = 93% (95% CI 85–97%)**; development **13/15 = 87%**. The registered final-cycle gate **FAIL** stands on its under-powered development-perfection condition. FP4 was enabled in that measured configuration and switched off afterward; the default local semantic channel is also off. These results do not establish 93% accuracy for shipped defaults or real-usage questions, which remain untested.

The initially deferred six-task pilot was attempted on 2026-11-14 and **failed**: two native plan-protocol failures, then four Clerk output-budget failures and two dependency skips in a labelled assisted execution. Successful coordination and citation closure remain unvalidated. See [release notes and Known Limitations](docs/phase67/RELEASE_0_2_DRAFT.md), [migration](docs/phase67/MIGRATION_0_2.md), [rulings](docs/phase67/RULINGS_INDEX.md), and [F4 acceptance](reports/PHASE67_F4_OWNER_ACCEPTANCE.md).
