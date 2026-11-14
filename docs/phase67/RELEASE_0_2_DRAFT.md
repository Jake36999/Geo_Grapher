# Geo-Grapher 0.2.0 — release notes for owner sign-off

Status: integrated on both mains and prepared locally for F4 acceptance. No tag or push. Geo merge 990f127 follows approved candidate 6c41756; Librarian master 8ea7c45 matches its tested integration tree. Release hardening begins at Geo 5c385b9; packaging completion is 82ff0aa. See the final release report for the exact wheel SHA256 and latest documentation commit.

## Release artifact and free checks

Wheel: `output/phase67-release/f3/verify-corrected/dist/geo_grapher-0.2.0-py3-none-any.whl`.

SHA256: **`4d903d7df0cb029e332b8bff1e076b122d40dabe8dfab765aaf7615bfcc4450d`**.

Final full verification: **775 backend, 16 frontend unit and 17 browser tests passed**, typecheck/build PASS, **28/28 installed-wheel preset/cap checks**. Prospective C14 first samples: **2.528, 2.480, 2.495 s**, median **2.495**, maximum **2.528** — PASS. Final live HTTP security **6/6** and real-store UI **5/5** passed on this exact wheel. Installed-wheel search→packet through Librarian master passed with **zero model calls**. Librarian's unchanged merged tree has **2,235 passed / 2 skipped / 5 deselected** from its neutral-directory pre-merge suite. All first failures and fixes remain in the integration record; they are not overwritten by these passes.

All **11 frozen contract files** and **78 runtime Python files** were checked byte-for-byte in the wheel. `uv lock --check --offline` passes after the lock metadata refresh. See [machine-readable release evidence](../../reports/PHASE67_F3_RELEASE_EVIDENCE.json). F4 acceptance remains pending.

## Features

Waves 1–4 add readable graph labels/roles and affinity layout; calibrated federation and discovery cards; snapshot fingerprints/drift, notebooks and folder onboarding; independent-graph diffs and clones; directed helper contraction and UI controls; reviewed snapshot-bound bridges and lineage; prune by derivation; six-tool presets and cited tiered packets; bounded cross-graph impact/conformance reports. The [changelog](../../CHANGELOG.md) separates the waves.

The quality track adds constant definitions/comments/usage, multi-query lexical search, optional local semantics, flat calls with server defaults and clamping, canonical IDs with valid error examples, whole-envelope caps, delivery coverage and bounded recovery. The merged Librarian runtime supplies route-aware bounds and best-effort answers at the step limit.

Shipped code-research defaults: **temperature 0.2; FP4 answer self-check off**. Existing customised profiles are not rewritten. Semantic search is **off by default**, separately installed as `geo-grapher[semantic]` (Model2Vec); FastEmbed is a separate optional local adapter. **Never send source to hosted embeddings.** No semantic model/cache is loaded without explicit configuration.

The prospective bridge firewall is **Ψ = 0.25 unless shared_citation == 1 or neighbour_jaccard >= 0.2**, weights unchanged. C14 prospectively requires **median(3 cold) <3.0 s and maximum <3.5 s**, same snapshot/wheel and fresh processes, behind `-QuietMachine`. No historical result was rescored.

## Measurements, exactly as registered

| Measurement | Result / interpretation |
|---|---|
| Wave-4 code gate | **3/5, 5/5, 4/5 = 12/15; PASS** |
| Later held-out v2 | **70/75 = 93%; 95% CI 85–97%** |
| Later development | **13/15 = 87%; 5/5, 5/5, 3/5** |
| Registered final quality-cycle gate | **FAIL**, on the under-powered development-perfection condition; verdict unchanged |
| Shipped default change after measurement | FP4 changed from on to **off**; no paid accuracy rerun |
| Real-usage questions | **Untested**; F4's three questions are owner acceptance, not a statistically powered evaluation |

The 93% configuration used optional local Model2Vec and FP4 on. It is not an accuracy claim for the default lexical-only, FP4-off release. Review 5 records FP4's **0 rescued / 2 degraded** drafts and representativeness/scoring limits. Free offline retrieval and original-five source/packet checks passed after the switch; those checks verify retrieval/contracts and scripted behaviour, not new autonomous answers. Every earlier first result remains in the gate/review reports.

## Stable contracts and migration

`contracts/v1.1` is **stable** for 0.2.0. Future wire/normative changes go to v1.2; v1.0 is unchanged. SHA256 values below hash exact LF bytes; the complete manifest ships in the wheel.

| Contract | SHA256 |
|---|---|
| `ACTOR_SCHEMA.md` | `c34839f8f789eac147ae64909a1ce16c32a522521059d316623a8c175f96b326` |
| `baseline-digests.json` | `a5218e0e90a53ce017b085240dc2bb6cad9c17dd48f06c2afcf827b9869c387a` |
| `FINGERPRINT_ADDENDUM.sql` | `ced7895361ab1ab1926ed2b016e16cdb88c243d392c28ddf7eb96f1e6ec04137` |
| `generated/geographer.wire.schema.json` | `cad2774ae4f2a7dc3a7f08ac541590a5dbc1c294c40876a3b2082591c4907183` |
| `geographer.trace.schema.json` | `45273ccceeb8b4ef9fc19d6b14067c4536f20f544dba273ab040028e05f292b8` |
| `geographer.wire.d.ts` | `cd167603c6165e4cb1d353f1bb963d9a2cb4f3e7e4cd042c108a1bd5abffa16e` |
| `PACKING_ADDENDUM.md` | `beac4359b74a13bd49db4e87016b45d339d869fcda2631ad5a6747e75ef90c9e` |
| `PROJECT_ISOLATION_ADDENDUM.md` | `b76752cb218e2fc29508fb9e01856e02f5a1d844a8eef2696346d29ea39bd966` |
| `RUNTIME_ADDENDUM.md` | `37fa271d26669b86401775fead9bf1738b4264e42ecf0d09ae5d174cb6c2fa8a` |
| `STABILITY.md` | `ddd8ccba39ce356e956233eeaf370ad4835986640db8462ceb9c93ff3ff4e970` |
| `WORKSPACE_ADDENDUM.md` | `6251c36a8d652d21f88823a1baf3078c061065fbf75649a3bc705505e6940a07` |

Manifest SHA256: `43f4f9201ccfe695e8e6b97f8a54dadaac01c22959ae166c0661541a3f3ca92e`.

Catalog tables auto-create on open, including bridge bindings/proposals and artifact lineage/ledger; legacy bridges are bound. Back up first. Re-ingest to obtain constants, comment mappings and stage-3 source facts, then rebuild/verify lexical and optional semantic indexes for those new snapshots. FTS rebuilds query-time; optional semantics require explicit local cache population, not a hosted service. Old published snapshots remain readable and keep their original facts. [Migration details](MIGRATION_0_2.md) distinguish source re-ingestion from derived-cache rebuilding and explain rollback.

## Known Limitations

| Area | Limitation / follow-up |
|---|---|
| Six-task live pilot | **Attempted 2026-11-14: FAIL.** Native lead plan shape/types failed; assisted execution returned **4 Clerk failures / 2 dependency skips**. No contracts reached verification; no successful end-to-end pilot is claimed. [Actual results](../../reports/PHASE67_LIVE_PILOT_20261114.md). |
| Accuracy scope | Registered final-cycle FAIL stands; FP4 changed after measurement. No real-usage population evidence; scoring brittleness and adjacent-mechanism confusion remain. |
| Answer discipline | Prior-knowledge slip 1/29 is outside the zero-cross-graph-leak criterion; missing-corpus abstention is wave-5 work. |
| Performance | Librarian-v2 QI historically 6–11 s cold; ToolSet prospective C14 does not certify every graph or target machine. |
| Parked Librarian WIP | Frozen at 610b4496, unreviewed. Overlaps `agent_runtime.py`, `loop.py`, `mcp_client.py`; the latter includes line-ending churn. Un-parking requires **owner manual merge**. Pre-rebase backups remain until after release. |
| CLI test isolation | `test_rules_and_capabilities` and `test_doctor_never_shows_key_values` discover a parent `.librarian`; use neutral test cwd and make them self-contained in a later change. |
| Bridges | Proposal recall limited by documentary/code name overlap; stronger firewall is now applied, not an open decision. |
| Contraction / clones | W3-2 parallel-twin restriction; clone size floor and lambda exclusion carried forward. |
| Workspace / lineage | Git-ignored tool/vault exclusions and reports role; read-only external Librarian artifact registration remain carried work. |
| Large results | Use header counts, filters and pagination for large evolution diffs; one envelope is not a complete report. |
| Parsing / compatibility | Optional JavaScript parser failure on `ui/app.js` and nonfatal `server/discover` warning remain recorded. |
| Recovery / semantics | Episode state bounded to 1,024 named episodes per connection; cache fingerprints must match and fail closed. Local Model2Vec measured; FastEmbed adapter not equivalently evaluated. |

See [rulings](RULINGS_INDEX.md), [Review 5](../../reports/PHASE67_REVIEW_5_SCIENTIFIC_ASSESSMENT.md), [integration evidence](../../reports/PHASE67_RELEASE_INTEGRATION.md) and [live security report](../../reports/PHASE67_F3_SECURITY.md). Local HTTP is single-user loopback, not a remotely authenticated multi-user service.

## Owner acceptance

Review the [20-minute 0.2.0 checklist and three production-route questions](../../reports/PHASE67_F4_OWNER_ACCEPTANCE.md). Sign off these notes and the known limitations. The six-task pilot has now failed; the owner must review that known limitation explicitly. The three questions do not replace successful six-task coordination. **A v0.2.0 tag and every push require separate explicit owner instruction.**
