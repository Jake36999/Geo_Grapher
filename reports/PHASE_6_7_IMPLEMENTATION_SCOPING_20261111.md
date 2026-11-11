# Phase 6–7 implementation scoping — 11 November 2026

Review of the Gemini-led research chain (the transcript *Branch • Autonomous Geo-Grapher
Ingestion and Orchestration Workflow* and the reports it produced), checked against the
code as it is today in Geo-Grapher, Librarian V2 and Custom_Agent_Forge, followed by a
scope for implementing each upgrade.

## Verdict

- **The research found the right gaps.** Discovery reports, readable labels, legible edges,
  graph lifecycle controls, staleness of derived artifacts, directed contraction that
  keeps reachability, and tier-aware context are all real needs. Most of the corrections
  Gemini made between rounds were correct too: no B-spline β in text, no global BM25
  rescaling, never downgrading static facts from traces, keeping the epistemic cost
  ordering and the existing Cayley bound.
- **The specs are not ready to implement as written.**
  - None of the reference code exists, but each spec builds on the previous spec's
    unwritten code as if it were in the repo.
  - The Librarian and Agent Forge they describe differ from the real ones in ways that
    change the design.
  - Most "measured" results come from synthetic fixtures, not from these repositories.
- **Recommendation:** treat the seven documents as a **design catalogue, not a
  specification.** Implement in five waves:
  - lead with the user-visible wins (labels, edge colours, discovery card, graph
    lifecycle);
  - then the fingerprint substrate everything else needs;
  - bind every Librarian-side piece to primitives the Librarian already has;
  - make Custom_Agent_Forge an optional, later consumer, not the Tier 2–3 engine.
- **Rough size:** about 23 upgrade items. Waves 1–4 come to roughly 9–12 weeks of
  focused work, and wave 5 is optional research. The estimates are rough and assume the
  current agent-plus-review pace.

## 1. What was reviewed

| Document | Content | Gates it defines |
|---|---|---|
| Branch transcript (Gemini) | Reviews of each round, correction prompts, patches | — |
| Autonomous Ingestion & Orchestration Workflow.md | Original 8 research prompts, partition model (P1–P7, Graph 8), working-memory graph | — |
| Librarian and Geo-Grapher Architecture Research.md | Agent 1 (code-grounded) and Agent 2 (literature-grounded) reports | — |
| Phase 6 Architecture & Math Spec.md (+ 4-bug addendum) | 8 tracks: lineage/sieve, PC-MCKP, WF-OCQP packer, trace v2, grounding, EIG triage, foraging controller, discovery cards | P6-G1…G8 |
| Cross-Graph Analysis Engine Specification | diff, bridge impact, theory conformance, clones/homonyms, `analyze_cross_graphs` | P6-CG1…CG5 |
| Multi-Tier Graph Mining & RAL Spec.pdf | Tier packing profiles, Agent Forge adapter, graph→DAG compiler, lenses, firewall, dossier + SFT | MT-G1…G6 |
| Geo-Grapher 3D Spherical Layout.pdf (150 pp: 2 agents + synthesis + a Phase 7 draft) | Labels, radial/angular layout, Kabsch port rotation, R*Tree + sqlite-vec | SP-G1…G5 |
| Phase 7 Architecture Specification.pdf | Lead plan DAG, happy-path onboarding, edge chromatics, lifecycle | P7-G1…G5 |
| Phase 7 Code Remediation Addendum part 1.pdf | Replaces the six Phase 7 stubs | re-certifies P7, SP |

Also checked: the three repository dumps, and the live code in `F:\uv-data\Geo_Grapher`,
`D:\Librarian_V2` and `F:\knowledge_compiler_engine (DAG Engine)`, the local Agent Forge.

## 2. The system today (verified 11 Nov)

### 2.1 What the specs assume versus what exists

| Spec assumes | Reality |
|---|---|
| `snapshot_entity_fingerprints` with six hashes per entity | Entities carry `ast_body_hash` (py-ast-v1, symtable-scoped, `normalize.py`) and `wl_3hop_hash` (directed-wl3-v1, `analysis.py:416`). Signature text exists as a `declaration-v1` analysis row. There is **no** `signature_hash`, `ts_guard_hash`, `exact_out_edges_hash` or fingerprints table. |
| `.librarian/stm/`, `.librarian/ltm/`, `.librarian/epistemic_lineage.sqlite` | None of these exist. The Librarian has a **staging airlock** (`staging.py`) → six-step **promotion** (`promote.py`), **DIK records** with origin labels `observed / source-stated / model-produced` (`dik.py`), `provenance.py` and the evidence store. |
| Partitions P1–P7 with trust tiers; quantule_mapper at 128.86 MB | The catalog holds **4 graphs** (`librarian-v2`, `timeline-mapping`, `ai-research-papers`, `ToolSet`), has **no** role/stratum/trust-tier column, and has **0 bridges**. The partition volumes are from the planning document, not from a real ingest. |
| GraphCatalog bridges as a live traversal layer | `add_bridge` exists; the table is empty; there is no authoring UI (roadmap Phase F). |
| Librarian phases `phase1_discovery … phase4_repair`, `max_steps = 12`, a `ForagingController` | The phases are `session, frame, map, need, search, judge, synthesise, check-out` plus the audited round `manage → preflight (admit_contract) → execute → audit → reduce`. `turn_steps` runs **12–80** by effort level (`effort.py`). Outside tools are read-only, offered in research phases only, at most **6 per server and 8 in total**. |
| A universal 1,800-token / 7,380-char clamp | Librarian: `MAX_EXTERNAL_RESULT = 8_000` chars (`mcp_client.py:47`), and `result_handles.py` can reopen oversized reads by `ref:`. Geo-Grapher: `--max-result-chars` (7,500 on Librarian connections) and a federation budget of 2,048–32,768 tokens. |
| `analyze_cross_graphs` as "one more tool" | The hub presets `papers` and `code` are **exactly 6 tools each** (`graph_router.py:21`), which is the Librarian's per-server cap. A seventh tool has to replace one or get its own preset. |
| Agent Forge `branching_contracts.py` = conditional DAG fan-out | Pydantic schemas for **SFT branch-trace training records**. Its own docstring says DAG runtime contracts live elsewhere (`contracts.py`). |
| `ral_amplifier.py` = generic critique-and-refine loop | A Claude-API script that turns OCR chemistry extracts into 80–150-word explanations, then applies quality gates. |
| `pipeline_firewall.py` = general epistemic firewall | Required SFT fields plus domain-specific forbidden tokens. |
| `graph_interface.py` = adapter to plug Geo-Grapher into | A 49-line abstract base class (`active`, `ready`, `add_nodes`, …). |
| `dag_runtime.py` = reusable DAG engine | A 3,702-line monolith (v5.3) with its own node lifecycle `CREATED → VALIDATED → SCORED → ACCEPTED / REJECTED / REROLL` and global seeding, built around SFT skill payloads. |
| Python 3.11 opcodes: "150 is RESUME, use 86" | On 3.11.3, `YIELD_VALUE = 86` and `RESUME = 151`. The patch is right to use `opcode.opmap`, but the number it stated was still wrong. |
| SQLite 3.46.1, numpy available | Bundled SQLite is **3.40.1**. R*Tree works and extension loading is enabled. `sqlite-vec` is not installed. numpy is in system Python but is **not a declared dependency**: `geometry.py` is pure Python. |
| 17 V4.1 grounding checks | `evaluation/grounding.py` emits 20 distinct codes. The ones the specs care about (`EXTRA_PATH`, `DIRECT_PATH_LENGTH`, `MISSING_ASSESSMENT`, `SOURCE_NOT_DELIVERED`, …) all exist. |
| Legend "Position is not similarity"; grey edges | Confirmed at `App.tsx:1829`. Edges are 1-px `LineBasicMaterial` with per-vertex colour ramps (`Scene.tsx:189`). Packing is a golden-spiral start plus a collision solver (`geometry.py:111`). |
| Documentary edges distinguish "designs/specifies" from "reviews/audits" | `documentary_incidences.role` is `discusses / documents / rationale_for / cites`. Review and audit are not represented. |

### 2.2 Baseline worth building on

- **Geo-Grapher:**
  - 44 modules and about 460 KB of Python. Last gate: 367 backend tests plus 12 browser
    checks, via `scripts/verify.ps1`.
  - Already has: immutable snapshot store with triggers; deterministic SCC layering
    (`level_scc_condensations`, `dag_rank`); quotient projections; `helper_tree_balls_v1`
    (currently `directed_reachability_preserved = False`); packer-v2 (additive, exact
    o200k); `review_queue` (ambiguity-triage-v1); CFG resolver with candidate reason
    codes; `source-context-v1`; `setprofile` trace recorder; `GraphCatalog` with collision
    review; `GraphRouter` with leases; federated search; reviewed merges; a 4-frame shared
    scene; `cite_as` handles.
- **Librarian:**
  - Closed-registry YAML workflows and pipelines with pinned definitions and append-only
    run logs (`workflows.py`).
  - Read-only tier 1/tier 2 helper agents (`tools/delegate.py`).
  - Lens packs (`lenses.py`, `lens_packs.py`); `deploy_survey.py` (Create / Adopt / Attach);
    domain profiles that already suggest `geo-grapher`.
- **Agent Forge:** worth borrowing as patterns:
  - the node lifecycle with REROLL;
  - the Omega validator's partial/final split;
  - the adversarial lens as an orthogonal second score that is recorded, not used to
    block.

## 3. Problems that cut across the whole spec set

1. **Stacked unwritten code.**
   - The 3D-layout synthesis states that the repositories "provide complete source
     implementations" of `AdditiveWFOCQPPacker`, `ZeroMutationPy311Recorder`,
     `solve_fas_min_deterministic`, `CrossGraphAnalysisEngine`, `GraphToDAGCompiler`
     and others.
   - Searched across all three repos: **none** of the 14 names checked exist. That
     includes `spatial_vector_layout`, `semantic_label_enricher`, `edge_chromatics`,
     `workspace_lifecycle`, `lead_plan_compiler` and `CHECKPOINT_INTERVAL`. "onboarding"
     appears only as an unrelated word in the Librarian.
   - Each later spec's "verified" claims therefore rest on earlier specs' proposals.
2. **Synthetic evidence presented as measurement.**
   - Examples: P6-CG1 aligns "Legacy CuPy vs Current JAX" partitions that don't exist,
     and SP-G2's Spearman ρ = −0.93 comes from a 24-node fixture. P6-G3's U = 17,767 and
     SP-G5's 0.535 ms are the same kind of figure.
   - Treat every number as a design target and re-measure on real graphs (ToolSet,
     librarian-v2, ai-research-papers).
3. **Parallel re-implementation (the most dangerous item).**
   - The Phase 7 addendum's `onboarding.py` ships its own `ast.parse` extractor, its own
     "py-ast-v1" normaliser, its own WL-3 hasher, and its own `graphs`/`bridges` DDL on the
     catalog connection. Adopting it would:
     - produce hashes **labelled py-ast-v1 that differ from `extract.py`'s** (silent
       identity drift across every diff and sieve);
     - bypass the stage pipeline and the snapshot immutability triggers;
     - bypass `plan_root` collision review;
     - conflict with the real `graphs` table (`root_key UNIQUE`, `code_database UNIQUE`).
   - Rule for all new work: call `extract` / `ingest` / `GraphCatalog`, never copy them.
4. **An invented Librarian.**
   - stm/ltm folders, the lineage database, phase names, the 12-step limit and the
     `ForagingController` are all fictional.
   - Every Librarian-side item has to be re-derived from real primitives (mapping in §4,
     items U2, U10 and U20).
5. **Misread Agent Forge.** The Multi-Tier spec's central idea, re-pointing Agent Forge at
   Geo-Grapher, assumes modules do jobs they don't (§2.1). The port would be large and
   reuse little.
6. **Many unconfigured constants.**
   - Weights like 0.40, 1.06 and 1.14, ψ_vol's 0.25, τ = 2.5, κ's temperature and the
     radial bands 0.42/0.72 are reasonable defaults.
   - They belong in configuration with calibration tests, not in wire contracts or gate
     pass criteria.
7. **Scope.** The specs end with 29 gates and about 15 new modules across three repos. A
   gate should check behaviour on real graphs. Matching the fixture numbers the spec
   generated is not a pass criterion.

**What to keep:**
- the five-tier sieve and hop-bounded soft quarantine;
- argument-order invariance in federation;
- directed contraction under order-convexity and port-to-port witness completeness;
- bottom-up additive expansion, which matches `PACKING_ADDENDUM.md`;
- separating delivered evidence from answer paths;
- hash-bucket diffs in O(N) and the catalog-level clone join;
- the homonym firewall with no automatic merging;
- one mode-parameterised cross-graph tool and tier-scoped packing profiles;
- the discovery card with the permitted/forbidden overclaim matrix;
- the two-regime deterministic FAS;
- minimal-distinguishing-ancestor labels;
- tangential projection, so angle stays independent of radius;
- eigenvalue tie-breaking, the `ON CONFLICT DO UPDATE` upsert and parent-rotation
  propagation;
- WCAG contrast-floor colour stops;
- `backup()`-based copy and the Windows-safe delete sequence.

## 4. Scope by upgrade

Effort: **S** ≈ 1–2 days, **M** ≈ 3–7 days, **L** ≈ 2–4 weeks. Each item lists what it builds on, what to build, what to change or drop from the spec, dependencies, and a real-repo acceptance check.

### Phase 6 core

**U1. Entity fingerprints and the five-tier sieve** — M
- **Builds on:** `ast_body_hash`, `wl_3hop_hash`, `declaration-v1`, `cfg.py`, exact
  relationships.
- **Build:**
  - Add `span_sha256`, `signature_hash` (canonical declaration header plus decorators),
    `ts_guard_hash` (ordered CFG guard skeleton) and `exact_out_edges_hash` (sorted exact
    out-relationships with reason codes).
  - Store them as an immutable per-snapshot table in the snapshot schema, plus a pure
    `classify_drift(base, new, contract) → tier 0–5`.
- **Change from spec:**
  - The fingerprints live in each snapshot store, keyed by snapshot, not in a
    `.librarian` database.
  - The store hard-fails on `user_version != 1`, so this needs a **schema migration
    path**.
- **Accept:** scripted edits on a ToolSet copy (comment, local rename, body refactor,
  signature change, neighbour-only change) each land in the expected tier, with
  byte-identical output across fresh processes.

**U2. Lineage and staleness for derived artifacts** — M (Geo-Grapher) + S (Librarian)
- **Builds on:** U1, catalog bridges, discovery cards (U9).
- **Build:**
  - An append-only justification and ledger store in `catalog.sqlite`.
  - Hop-1 DNF evaluation, then bounded hop-2…8 soft quarantine, written in Python over
    small sets.
  - Gemini's Bug-3 corrections built in: whole-clause conjunction, and states read from
    the current sweep.
  - Start with bridges and discovery cards only.
- **Change from spec:**
  - No `.librarian/stm|ltm`.
  - The Librarian reads bridge and card state through a tool and maps it onto DIK
    status/origin. The recursive CTE is optional.
- **Accept:** P6-G2 rewritten on two real snapshots. A neighbour-only edit causes 0
  demotions; a signature edit demotes hop 1 and quarantines hop 2+.

**U3. Provenance-calibrated federated selection (PC-MCKP)** — S
- **Builds on:** `federated_search` (largest-envelope-first omission today).
- **Build:**
  - Per-graph role, trust tier and modality.
  - Intent classifier, ψ_vol and local rank signal.
  - Exhaustive subset search: 8 graphs give at most 256 subsets, so no DP is needed.
- **Change from spec:** the tier and modality fields are new catalog data (decision D2).
- **Accept:** every permutation of the real 4-graph catalog selects the same set; the
  ranking stays `independent_per_graph_no_global_rank`.

**U4. Hub-penalised traversal and stratum-entropy centrality** — S–M, deferred
- **Builds on:** merged graphs and TypedBridge costs.
- **Build:** read-time cost terms only, never edge rewrites.
- **Change from spec:** this only matters once a merged graph mixes a noisy transcript
  stratum with curated ones. None does today.
- **Accept:** when a merged graph with a transcript stratum exists.

**U5. Directed contraction (WF-OCQP) and additive expansion in packer-v2** — L
- **Builds on:** `level_scc_condensations`, `helper_tree_balls_v1`, packer-v2.
- **Build:**
  - A new Stage 3 view algorithm: single-entry dominator branchings, single-exit
    post-dominator branchings, and twins, over the condensation DAG, bounded to one
    containment parent.
  - Invariants I and II checked per block.
  - The packer admits the spine plus representatives, then expands by κ from a max-heap
    with periodic exact o200k checks and rollback.
- **Change from spec:**
  - Keep `helper_tree_balls_v1` alongside the new view, selectable, until the new one
    proves itself.
  - Dominators come from the iterative Cooper–Harvey–Kennedy method on the DAG.
- **Accept:**
  - Property tests on random DAGs: no false reachability, and every quotient path has a
    witness.
  - `directed_reachability_preserved = true`.
  - C14 latency (≤ 3 s cold) holds on ToolSet-scale frames.

**U6. Runtime trace v2** — M (part a) + M (part b, optional)
- **Builds on:** `recording.py` (`setprofile`), `trace.py`, the trace schema.
- **Build:**
  - (a) Activation IDs, caller→callee 2-grams, and SUSPENDED/resumed coroutine frames
    (opcodes via `opcode.opmap`). New schema fields stay optional, including `p95_ms`
    (Gemini Bug 4).
  - (b) Ball–Larus path IDs via `settrace` scoped to target functions only.
- **Change from spec:** measure overhead before turning (b) on by default; never rewrite
  the AST.
- **Accept:** P6-G5 on a real async fixture; `source_match` stays true; overhead is
  reported.

**U7. Separating evidence context from answer paths** — S
- **Builds on:** `grounding.py`, `transport_schema.py`, `anchor_identities`.
- **Build:**
  - Multi-hop helper context lands only in evidence records.
  - `answer.paths` stays within the requested (focus, pin) pairs.
  - Anchor identities are always emitted.
- **Change from spec:** mostly tests. Do it before U5 and U13 add multi-hop context.
- **Accept:** P6-G6 on the existing evaluation tasks.

**U8. Ambiguity triage ranking (EIG surrogate)** — S–M
- **Builds on:** `review_queue`, `dag_rank`.
- **Build:**
  - O(1) ranking from SCC data plus a bounded reverse-reachability check.
  - Module batch discount.
  - Tier C becomes Librarian staging items.
- **Change from spec:** Tier B (trace-resolved) waits for U6.
- **Accept:** 500 items ranked in under 15 ms, deterministically.

**U9. Discovery card and Markdown/Obsidian export** — M
- **Builds on:** SCCs, boundaries, conformance, the Cayley diagnostic.
- **Build:**
  - QCICS, ABBS and SCBBS scores.
  - Two-regime FAS: exact bitmask DP for ≤ 8 nodes, Eades–Lin–Smyth with canonical
    ties above that.
  - The overclaim matrix.
  - Markdown output plus an MCP resource.
- **Change from spec:** keep `analysis.py`'s Cayley formula. This closes gaps #1 and #2 in
  the Graphify comparison report.
- **Accept:**
  - Byte-identical cards across processes on ToolSet and librarian-v2, at about 1k tokens.
  - Every number traces to a stored analysis row.

**U10. Tier-aware context for the Librarian** (Phase 6 Track 7 and Multi-Tier Tracks 1 and 6) — M across both repos
- **Builds on:** the federation budget, `--max-result-chars`, Librarian `result_handles`,
  `PHASE_TOOL_HINTS`.
- **Build:**
  - A Geo-Grapher `profile` parameter: leaf 1,200, forager 1,800, lead 32k–128k.
  - A path for large lead envelopes past the 8,000-char external cap: a `ref:` handle the
    lead can reopen, or a per-model cap (decision D4).
  - Envelope signals surfaced as phase hints.
- **Change from spec:** no `ForagingController` and no invented phases; work with the
  Librarian's real phases and effort-scaled `turn_steps`.
- **Accept:** a Tier-1 lead finishes the 5-question benchmark in fewer tool calls with
  equal facts, 0 withheld and 0 leaks.

### Cross-graph analysis

**U11. Cross-graph diff and clone join** — M
- **Builds on:** U1.
- **Build:**
  - `diff_graphs` with hash-bucketed passes (Gemini Defect 2 built in).
  - The five alignment classes.
  - A catalog-level clone join over a derived fingerprint index keyed by `snapshot_id`.
- **Change from spec:** useful straight away for snapshot-to-snapshot diffs and
  ToolSet ↔ librarian-v2 clones; no bridges needed.
- **Accept:** a diff of two real snapshots matches the scripted edits; output is O(N) and
  deterministic.

**U12. Bridge authoring and candidate scorer** — M
- **Builds on:** `add_bridge`, aliases, paper citations.
- **Build:**
  - Scorer: alias overlap + shared citations + neighbourhood Jaccard, with a disjoint
    penalty.
  - Proposals go to review, either Librarian staging or the Geo-Grapher UI.
  - Authoring requires a rationale and evidence.
- **Change from spec:** never merge automatically. This is the prerequisite for U13,
  because there are 0 bridges today.
- **Accept:** the homonym probes ("field", "model", "node") produce no accepted-tier
  proposals; reviewed bridges persist.

**U13. Bridge-coupled impact and theory conformance** — M–L
- **Builds on:** U12, U2, U7.
- **Build:**
  - Product-graph Dijkstra with separate intra-graph and bridge steps and a stratum
    transition cost.
  - The four conformance states.
- **Change from spec:** needs a real pilot, e.g. ai-research-papers ↔ a code graph with at
  least 10 reviewed bridges.
- **Accept:** P6-CG2 and P6-CG3 on that pilot.

**U14. The `analyze_cross_graphs` tool and its packer** — S–M
- **Builds on:** U11 (and U13 for those modes).
- **Build:**
  - One mode-parameterised operation.
  - Items admitted as dependency-closed bundles (Gemini Defect 1).
  - `omitted_graphs` and anchor identities always present (Defect 3).
- **Change from spec:** a new `cross` preset, or swap it into `code` (6-tool cap).
- **Accept:** P6-CG5 under the 7,500/8,000-char caps.

### Multi-tier mining

**U15. Tier 2–3 graph mining** — S spike, then M–L
- **Builds on:** Librarian workflows, `delegate.py` helpers, U10, U20.
- **Build:**
  - Mining as Librarian workflows: tier-2 helpers on the notes model, fed Geo-Grapher
    task packets.
  - Borrow the Agent Forge node lifecycle and REROLL, Omega-style final checks, and the
    adversarial lens as a recorded second opinion.
- **Change from spec:**
  - **Do not** make Agent Forge's `dag_runtime` the engine (§2.1).
  - The SFT flywheel becomes an optional export from accepted trajectories later.
- **Accept:** a mined summary reaches the vault only through staging plus a person's
  review, and goes stale correctly through U2.

### Enrichment and spatial layout

**U16. Semantic display labels and disambiguation** — S–M
- **Builds on:** `documents.py` headings, entity qualnames, roles.
- **Build:**
  - Deterministic labels: heading path, minimal distinguishing ancestor prefix for `main`
    or `__init__`, and a role badge from AST and degree features.
  - Stored as derived per-snapshot rows.
- **Change from spec:** no model on the first pass; a Tier-3 fallback can come later.
  This is the best visible win, so do it first.
- **Accept:** 0 `Documentation - line N` labels and 0 duplicate visible labels within one
  parent on ToolSet, checked in Playwright.

**U17. Affinity-aware sibling layout** (radial coreness, angular affinity) — M
- **Builds on:** `pack_siblings` and the existing collision solver.
- **Build:**
  - Replace the golden-spiral start with a spectral start (eigenvalue tie-break) and
    radial bands by coreness.
  - Tangential relaxation, with the existing hard-sphere solver as the final constraint.
  - New legend text.
- **Change from spec:** needs numpy (decision D1) or a small pure-Python power iteration.
- **Accept:**
  - On ToolSet: 0 overlaps, and a measured coreness↔radius rank correlation, with its
    threshold set after the first run.
  - Identical digest across processes and input orders; C14 latency held.

**U18. Port-facing rotations (Kabsch/SO(3))** — M, deferred
- **Builds on:** U17, `Scene.tsx` transforms, `curves.ts`.
- **Build:** parent-rotation propagation, plus world-space port ends for curves.
- **Change from spec:** moderate value, real frontend complexity. Do it after U17 shows a
  benefit.
- **Accept:** curves don't twist inside rotated parents (visual check plus a numeric
  port-alignment report).

**U19. Spatial index** — S (R*Tree); vectors deferred
- **Builds on:** layouts and the bundled SQLite.
- **Build:** an R*Tree of node bounding boxes for region and box-select queries, which
  pruning (U23) needs.
- **Change from spec:**
  - Defer `sqlite-vec`: embeddings are the Librarian's job, per the Graphify report.
  - Reject DuckDB/Kùzu for now.
- **Accept:** box-select query under 5 ms on ToolSet.

### Phase 7

**U20. Lead-compiled plan DAG** — M (Geo-Grapher) + M–L (Librarian)
- **Builds on:**
  - Librarian: the audited round (`admit_contract` → execute → audit → reduce),
    workflows and helpers.
  - Geo-Grapher: packer and anchors.
- **Build:**
  - Geo-Grapher:
    - a cross-modal anchor resolver over entity IDs, `doc:` / `claim:` / `concept:`
      handles and bridges;
    - `compile_task_packet`, splitting the budget 25% instruction, 55% anchors, 20%
      boundary ports;
    - callee-first ordering hints from quotient call edges.
  - Librarian: the plan as an admitted contract with a pre-dispatch validator (cycles,
    missing anchors).
- **Change from spec:** this replaces the invented `.librarian/stm` dependency slots with
  the round's own artifacts.
- **Accept:** P7-G1 on a real plan over ToolSet: no task exceeds its packet budget, and
  bad plans are rejected before dispatch.

**U21. Happy-path deployment** — M (Geo-Grapher) + S–M (Librarian)
- **Builds on:** `load_workspace_manifest`, `plan_root`, `import_project`, `deploy_survey`,
  profiles.
- **Build:**
  - `geographer init-workspace`: hygiene sieve and archetype classifier → a manifest
    preview.
  - Then collision review → one graph per partition → U16 labels → U9 card.
  - On the Librarian side, Adopt/Attach proposes graphs and a person approves them.
- **Change from spec:** **reject the addendum's `onboarding.py` extractor and DDL**
  (§3.3); "partitions" are ordinary catalog graphs with a role.
- **Accept:** P7-G2 on three real roots: a code repo, a paper folder, and a mixed vault.

**U22. Edge chromatics** — M
- **Builds on:** relationship `family` / `subtype` / `resolution_status`, documentary
  roles, the vertex-colour line pipeline.
- **Build:**
  - Backend classifier for family and runtime status.
  - Palette with a contrast floor; alpha taper along t.
  - Dash and dot patterns via a line-distance attribute and a small shader on the existing
    line segments.
  - Hover/pin dimming and time-uniform animation.
  - Tubes for hovered or pinned chains only.
- **Change from spec:** "designs vs reviews" needs a typed documentary role. Today's roles
  are `discusses / documents / rationale_for / cites`, so add `reviews`, or classify by
  rule and say so in the legend.
- **Accept:** a contrast ≥ 4.5:1 unit test, a Playwright screenshot check, and frame time
  held at current curve counts.

**U23. Graph lifecycle UI and API** — M–L
- **Builds on:** `GraphCatalog`, `GraphRouter` leases, `import_project`.
- **Build:**
  - (a) Copy via `backup()` into a new `graph_id` with a synthetic root key.
  - (b) Delete: release leases, WAL checkpoint, unlink with retries, bridge states via U2.
  - (c) An active-set toggle.
  - (d) Prune by **deriving a new graph** (re-ingest with excludes, or filter at view
    level), not by editing an immutable snapshot.
  - (e) A directory picker via a localhost-only browse endpoint over allow-listed roots.
- **Change from spec:** the catalog has no delete, copy or rename today, and import is
  CLI-only. Build (a)–(c) in wave 1.
- **Accept:** P7-G4 and P7-G5 on real stores on Windows; immutability triggers never fire.

## 5. Sequencing

```
Wave 0  decisions register (½–1 day)
Wave 1  visible wins            U16 labels · U22 chromatics · U9 card+export · U3 PC-MCKP · U23a–c lifecycle · U7
Wave 2  substrate               U1 fingerprints (+migration) · U21 init-workspace · U11 diff/clones · U19 R*Tree
Wave 3  structure               U5 WF-OCQP+packer · U12 bridges · U2 lineage · U14 tool · U23d–e prune/picker
Wave 4  Librarian integration   U10 tier profiles · U20 plan DAG · U13 impact/conformance pilot
Wave 5  optional research       U17/U18 layout · U6 trace v2 · U8 triage · U15 tier 2–3 mining · U4 hubs
```

Key dependencies:
- U1 → U2, U11, U12.
- U12 → U13.
- U7 → U5, U13.
- U10 → U15, U20.
- U19 → U23d.
- U17 → U18.
- U6 → U8 Tier B.

- **Wave 0:** an *accepted decisions register* that becomes the single source of truth.
  It should hold:
  - the corrections that survived (1A–1F, the cost ordering, the Cayley bound, additive
    packing);
  - the decisions in §6;
  - a line marking all Gemini reference code as non-normative.
- **Wave 1 (about 2 weeks)** changes what you see on screen and in agent answers without
  any new substrate.
- **Waves 2–3 (about 5–7 weeks)** carry the algorithmic weight. U5 alone is the largest
  item.
- **Wave 4 (about 2–3 weeks)** spans the Librarian repo and needs its own test suite as a
  gate (2,147 tests at last run).

**Gate policy.**
- Every gate runs on the real catalog graphs or on small checked-in fixtures built from
  them.
- The spec's numbers are targets, not pass criteria.
- `scripts/verify.ps1` (full pytest, typecheck, build, Playwright) stays the gate for
  every report, as Phase A required.

## 6. Decisions needed

1. **D1. numpy** as a declared dependency, for the spectral start and Kabsch, or a small
   pure-Python eigen-solver.
2. **D2. Catalog schema:** add `role`, `trust_tier` and `modality` per graph. U3, U4 and
   U21 need it.
3. **D3. Where lineage lives:** `catalog.sqlite` (recommended: catalog-scoped,
   Geo-Grapher-owned, readable by the Librarian through tools) or a Librarian-side store.
4. **D4. Large lead envelopes:** Librarian `ref:` result handles (recommended: no cap
   change) or a per-model external-result cap.
5. **D5. Agent Forge's role:** pattern donor and optional SFT export (recommended), or the
   Tier 2–3 engine.
6. **D6. Tool surface:** a new `cross` preset (recommended) or swapping into `code`.

## 7. Spec fixes to carry forward

**From Gemini's reviews, still valid:**
- the conjunctive-clause staleness check;
- `p95_ms` stays optional;
- the V4.1 envelope lives in the harness, not the wire contract;
- itemised cross-graph packing with `omitted_graphs`;
- hash-bucket diffs;
- the `ON CONFLICT DO UPDATE` upsert;
- the eigenvalue tie-break and parent-rotation propagation;
- contrast-clamped colour stops;
- replacing the 1-D prune stub, `fork_new_graph`, and the pre-delete staleness sweep.

**Found in this review and not caught by Gemini:**
- the stacked unwritten code (§3.1);
- the parallel extractor and DDL in the addendum (§3.3);
- the Librarian and Agent Forge mismatches (§2.1);
- the snapshot `user_version` migration U1 needs;
- the 6-tool preset ceiling;
- the 8,000-char external cap, the real blocker for Tier-1 envelopes;
- the missing review/audit documentary role;
- the wrong opcode number in the trace patch.
