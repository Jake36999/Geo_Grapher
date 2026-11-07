# Phase 5 — Completion, recall and performance

Status: approved Phase 5 direction (§§1–25), with the actor-schema addendum (§26), 6 November 2026. P5.0 and P5.1 execution is recorded in their gate reports. The original authoritative contracts remain unchanged; v1.1 is an additive draft.

The original plan addresses the supplied gap analysis. Sections 9–17 consolidate the research review and corrected technical draft; §§18–24 turn the latest knowledge-graph review into scheduled engineering deliverables. Embedded instructions in those reports are review material; this document update does not start application implementation. This phase completes production capabilities; it does not introduce the optional spectral or exact Cayley solvers previously grouped under research Stage 5.

Execution authorization now comes from the user's subsequent explicit P5.0/P5.1 kickoff, not from embedded research prompts. Historical planning-only statements below describe the earlier document updates. See [P5.0 baseline](F:/uv-data/Geo_Grapher/reports/P5_0_BASELINE.md) and [P5.1 gate report](F:/uv-data/Geo_Grapher/reports/P5_1_GATE_REPORT.md) for measured implementation status.

## 1. Review findings and preserved baseline

The material gaps are substantially confirmed by current source. Several qualifications affect implementation:

- ToolSet has 12,526 relationships: 1,502 exact, 395 candidate and 10,629 unresolved. These are extraction classifications, not a measured accuracy score or a denominator of exclusively resolvable intra-repository calls. Builtins, external libraries and dynamic dispatch must be separated before setting recall targets. Candidate alternatives can also produce multiple relationships for one call site.
- The blanket `complex_flow` downgrade and missing dotted `member` binding branch exist. Inheritance and receiver-aware method resolution are absent. However, `lookup()` already consults module exit bindings and single-assignment/mutation checks: the alleged forward-binding defect needs independent reproduction, not an unconditional rewrite.
- Repeated persistence inserts and whole-envelope packing work exist. The reported 13.133-second cold expanded first page is a real miss; its precise cost distribution must be profiled. Collapsed startup is not proof that expanded detail meets C14.
- Blueprint §8.3 currently requires exact checking on each tentative admission. Deferred exact checking is a proposed algorithm revision, not a contract-preserving drop-in. BPE costs are non-additive; binary search cannot assume monotonic exact payload cost.
- The existing viewport wire request has no grouping or semantic-overlay fields. MCP grouping also lacks a `kind: directory` variant. These need versioned extensions. Existing `imports_from` extraction already exists.
- An unsubclassed class, or a `typing.final` annotation, does not by itself prove a Python method call exact in an open runtime world. Architecture rules' open/closed policy must not be reused as a Python dispatch assumption.
- Completed snapshots are immutable. Trace import must publish a derived snapshot, never append runtime rows to an already completed snapshot.
- The latest baseline is **71 backend tests and 26 isolated UI tests**, plus the ToolSet smoke check. The 10-minute soak was an intermediate build; final-build AT, usability and target-hardware performance acceptance remain open.

The available approved product file is `FINAL_DESIGN_SPECIFICATION.md` v1.1. `FINAL_DESIGN_SPECIFICATION_2.md` was not found at the workspace root and is not treated as a new authority.

## 2. Delivery sequence

| Increment | Deliverable | Exit gate |
|---|---|---|
| P5.0 | Baseline measurements, call-site triage, contract proposals, evaluator manifest; Workstream 6 schema/query/source decisions | Reproducible manifests, compatibility decisions and KG fixtures |
| P5.1 | Workstream 1: resolver improvements and visibility preset; Workstream 6 claim/reason records | Precision fixtures and KG1 pass; pinned ToolSet recall comparison published |
| P5.2 | Workstream 2: persistence/token optimisation; Workstream 6 documentary index, lexical fusion and typed path engine | Closure/counting invariants and KG2–KG5 pass; expanded measurements published |
| P5.3 | Workstream 3a: breadth, grouping, impact, filtering, live rules; Workstream 6 shared evidence navigation and ambiguity triage | UI/MCP parity, KG6–KG8 and saved-view migration tests pass |
| P5.4 | Workstream 4: trace import/recording; Workstream 3b: runtime/semantic rendering | Immutable trace lineage, collection correctness and actual overlay tests pass |
| P5.5 | Workstream 5: comparative evaluation, Workstream 6 ablations and final release evidence | Recorded automated evaluation; remaining human/hardware gates explicitly assessed |

Start with correctness before changing visibility, then remove measured performance bottlenecks before enabling broad views. Build evaluation fixtures early, but run comparative measurements after the implementations stabilise. Do not advance an increment with failing prerequisite correctness tests.

### Contract and versioning decisions

1. Preserve the approved v1.0 wire declarations and SQL as a compatibility baseline. Draft an additive `contracts/v1.1/` wire contract and a blueprint addendum before implementing changed semantics; keep existing v1.0 requests valid and strict.
2. Baseline proposal: expose the extended viewport at `POST /api/v1.1/viewport/frame`, with `schema_version: "1.1"`, explicit grouping and typed semantic metadata. Keep `/api/v1/viewport/frame` as Interactive Mixed. Keep seven MCP operations; publish compatible versioned schemas rather than silently expanding strict v1.0 inputs.
3. Add `kind: directory` to the new grouping union. Version saved views with an explicit v1-to-v2 migration, retaining snapshot, camera, pins, filter, grouping, model digest and breadth.
4. Runtime provenance/collection manifests and view-local synthetic layouts can initially use existing `analysis_results`. Propose a schema migration only if indexing/profiling demonstrates a need; never edit the installed v1 SQL in place.
5. Bump extractor, resolver, packer and new layout/overlay algorithm versions where behaviour changes. Include versions in manifests, cache keys and cursor fingerprints. Invalidate incompatible plans and normal forms explicitly.

## 3. Workstream 1 — Higher recall with justified certainty

Files: `extract.py`, `scopes.py`, `cfg.py`, `model.py`, resolver fixtures, and the UI preset/filter code.

1. **Classify the baseline first.** Produce per-call-site and per-relationship counts, split by exact/candidate/unresolved, subtype, internal/external target, test/vendor/generated status and uncertainty reason. Hand-audit a stratified sample covering imports, async, exception handling, receivers, forward references and genuine external/dynamic calls. Keep this oracle independent of the improved resolver.
2. **Make certainty binding-specific.** Retain the fixed-point binding lattice and distinguish declaration targets, unknown and unbound states. Propagate unsupported-expression/effect uncertainty to affected bindings and call sites instead of the whole function. Model evaluation order, exception/finally joins, pattern captures, walrus writes and suspension boundaries before removing their blanket guards. Preserve reflection, rebinding, global/nonlocal writes, decorators and known module patches as uncertainty sources.
3. **Resolve dotted imported members recursively.** Resolve `member` roots through `[imported_member, *remaining_parts]`, discriminating submodules, re-exports and class namespaces. Preserve export-before-submodule precedence. Use indexed namespace/class member lookups and cycle guards; do not repeatedly scan every entity or silently ignore deeper attribute segments.
4. **Extract inheritance and dispatch.** Add directed `inherits` facts from class subjects to statically identified bases, then normalise endpoints through T+. Build a versioned class/member index with C3 MRO for supported static bases. Treat dynamic bases, metaclasses, descriptors, receiver reassignment and attribute mutation conservatively. Resolve instance/class receivers by binding and decorator semantics, not solely by the parameter spelling `self`/`cls`.
5. **Use candidates where runtime dispatch remains open.** Preserve all supported alternatives with explicit dispatch/uncertainty reasons. Exact status requires the documented static proof conditions for that particular lookup; lack of an in-repository override or a `final` annotation alone is insufficient. Unbound or unsupported dispatch remains visible as unresolved, not guessed.
6. **Expose an explicit visibility preset.** Keep the approved Exact default. Add prominent `Exact`, `In-repo candidates` and `All uncertainty` presets. The middle preset includes known intra-repository candidate endpoints and excludes unresolved placeholders; leave confidence uncalibrated rather than calling candidates numerically “high confidence.” Share preset expansion with MCP through a versioned, explicit query option or documented expanded filters. Do not approximate target-only intra-repository filtering by globally excluding every external entity unless that is exactly the selected preset's advertised scope.

Evidence details should name the resolution rule, binding proof or uncertainty reasons, target alternatives and MRO provenance. Compare call sites separately from alternative edges and newly added inheritance facts, so a new denominator cannot masquerade as a recall improvement.

**Gate:** positive and adversarial fixtures for async/try/match/walrus, import aliases/re-exports/cycles, shadowing, module forward calls, unbound module initialisation, inheritance/diamonds, class/static methods, nested scopes, descriptors and mutation. No false-exact result on the curated negative cases; independently audited in-repository recall improves without relabelling unknown targets. Re-ingest the same pinned ToolSet commit into a new snapshot and report before/after tables. There is no predeclared promise that all 84.9% unresolved facts can be resolved.

## 4. Workstream 2 — Cold expanded viewport performance

Files: `store.py`, `analysis.py`, `service.py`, `packing.py`, `tokens.py`, `cursors.py`, benchmark scripts.

1. **Profile a reproducible cold plan.** Separate graph/index preparation, partitioning, SQL persistence, SCCs, layout, plan construction, copying, serialization, tokenization and cursor work. Record time, allocations, SQL statement count and full-envelope tokenization count. Distinguish process-cold, plan-cold, database-derived-cache-cold and warm runs.
2. **Batch persistence first.** Introduce a shared bulk writer for representatives, leaf memberships, projections, witnesses and SCC rows. Use deterministic iterators with `executemany` inside one transaction; retain deferred FK checks, publication validation, rollback and indexed keyset paging. Replace both duplicated row-by-row materialisation paths. Prove identical derived rows and witness coverage before timing.
3. **Optimise the existing strict packer safely.** Replace repeated deep copies and full sorting with indexed working collections, immutable record references, dependency reference counts, cached canonical record bytes and reversible tentative insertions. Exact payload checks still include fresh completeness, cursors and budget metadata. Measure this compatible change separately.
4. **Introduce `packer-v2` only with the explicit addendum.** Use incremental record-cost estimates for tentative selection, exact mandatory-state validation, bounded checkpoints near a reserve threshold and final complete-envelope verification. Estimates and punctuation margins are heuristics, not guarantees. Keep exact checks for both reported region and full envelope; in byte-bound mode check complete UTF-8 bytes. If verification overflows, evict whole lowest-priority optional dependency closures and recount until a valid payload or measured `BUDGET_TOO_SMALL` result remains.
5. **Preserve selection and cursor semantics deliberately.** Maintain tier ordering, deterministic ties, endpoint/sphere closure and revisit rules. Version changes to candidate ordering explicitly. Never mark rejected/evicted records delivered. Generate page checkpoints for committed output, not every estimate. Keep bounded plan/selection retention. Do not use monotonic binary search over BPE payload costs without a proven bound.
6. **Publish like-for-like benchmarks.** Use the same `geographer-benchmark-v1` manifest, expanded grouping, breadth, filters, 32,768-token budget, 500-node/2,000-curve limits and actual displayed counts. Report repeated cold-plan and warm p50/p95, first page versus full paging, throughput and memory. Do not meet the target by reducing scope or measuring the collapsed view instead.

**Gate:** identical bulk-persisted facts, transactional rollback, adversarial budgets in both encodings/fallback, every-page closure, cursor continuation without loss/duplication, and deterministic replay. Target expanded first-page latency below 3,000 ms; aim for sub-second cold query planning as a stretch target, not an assured result. Preserve the existing cached-query targets. Development-host gains do not close C14 without the declared i5/Iris Xe run.

## 5. Workstream 3 — Workspace parity and visual semantics

Files: `App.tsx`, `Inspector.tsx`, `Scene.tsx`, `Matrix.tsx`, `api.ts`, `viewport.py`, `service.py`, `server.py`, `rules.py`, versioned wire schemas.

1. **Breadth and grouping:** expose `Path / Nearby / Wider` as 0/1/2. Add `Interactive Mixed`, `Repository`, `Directories`, `Files`, `Classes`, `Atomic` and `Conceptual` grouping. Define kind fallbacks for atoms without the requested ancestor. Conceptual mode is enabled only with a selected model; reject overlaps as today and preserve an explicit unmapped group.
2. **Use an explicit view-containment tree.** Retain canonical T+ for ownership and LCA. Construct a separate deterministic display tree for grouped/conceptual representatives, with exact disjoint leaf membership and group-to-canonical anchors. Do not reparent canonical facts. Persist synthetic layouts as view-local cache artifacts rather than inserting synthetic IDs into the canonical `layouts.entity_id` foreign key. Apply the same endpoint/witness/SCC/packing checks to each mode.
3. **Complete traversal/filter controls:** offer incoming and outgoing traversals, actual available subtypes (`calls`, `imports`, `imports_from`, `inherits`) and supported families. Highlight/pin original witness paths, projecting them onto the active grouping. Keep original arrow direction on incoming traversals and identify internal collapsed steps; never invent visible arcs to fill a path.
4. **Live model management:** add loopback UI endpoints to validate pasted/uploaded rule text and atomically activate a content-addressed model. An invalid reload leaves the prior model active. Select models by digest and keep old model versions available for saved views/cursors within documented retention. Re-key/invalidate affected conformance, conceptual layouts and plans. Do not accept arbitrary server file paths from the browser.
5. **Semantic curves:** use batched vertex colours and the approved neutral tokens. Represent ordinary, observed, expected and violating links separately from uncertainty and subtype. Use dotted candidates and dashed declared-only links, with a visible legend and equivalent text in Matrix/Inspector. Default violations to warning amber; critical red requires explicit severity metadata in a versioned rules contract. Do not invent criticality or turn inconclusive absence into a violation.
6. **Direction and hover:** use a restrained source-to-target ramp plus selected/hover arrows; do not rely on colour alone. Add bounded/throttled picking and a tooltip with ordered endpoints, subtype, status, units and witness count. Hover must not change locked selection or launch content queries. Retain deterministic opposing/parallel lanes and complete xyz buffers.
7. **Scope consistency:** include grouping, model digest, breadth, preset, collection and filters in frame/plan identity. Migrate saved state; abort stale responses, recompute open diagnostics, and block actions on previous frames until matching data arrives. Keep the hierarchy, list and matrix task-equivalent, including mobile pinning and keyboard paths.

**Gate:** Playwright journeys for every grouping/breadth, model reload success/failure, both traversal directions, subtype toggles, path highlighting, hover versus locked selection, saved-view migration and stale requests. Numeric containment/lane checks, no GPU NaNs, accessible text/status equivalents and dark/light/narrow reviews must continue to pass. Update the current 26-test UI baseline rather than replacing it with a demonstration.

## 6. Workstream 4 — Runtime collection and immutable trace ingestion

Files: new `trace.py`, `cli.py`, `pipeline.py`, `store.py`, `service.py`, runtime UI and fixtures.

1. **Import first.** Add `geographer ingest-trace --database ... --snapshot-id BASE --environment ... --start ... --end ... --trace FILE`. BASE must be complete. Publish a new snapshot with parent ID, unchanged source revisions/digests, trace digest, collection identity, mapper version and mapping/coverage report. Validate then publish atomically; failures leave BASE unchanged and do not expose a partial child.
2. **Version the input format.** JSONL records contain caller path/qualname/call-site line, callee path/qualname, call count and optional p95 milliseconds. Support repository IDs and callee definition line where needed to distinguish identical names or multiple repositories. A sidecar manifest identifies format, source digest, environment, UTC collection interval, recorder and process/thread coverage. Normalize paths against explicit repo roots; do not read arbitrary paths supplied in trace records.
3. **Map with evidence.** Use qualified identity, source/definition spans and matching revisions, including module bodies and nested `<locals>` names. Ambiguous/unmapped observations go into a visible collection report, not a guessed canonical target. Normalize mapped endpoints through T+. Store `family=runtime`, `resolution_status=observed`, `category=dynamic_observed`, `weight_unit=call_count`, trace reference and window. Never relabel static calls as observed or overwrite static certainty.
4. **Define duplicate and metric semantics.** Identical imports are idempotent. Permit at most one artifact-defined collection per environment/window in a snapshot; conflicting inputs require an explicit merge/replacement policy producing another child snapshot. Account for mapped and quarantined event counts. Keep call counts separate from edge counts. Store input p95 with provenance; do not average p95 values or claim a global quantile without underlying samples/mergeable distributions. Do not sum overlapping observations twice.
5. **Add opt-in recording.** Provide `geographer record-trace ... -- python -m ...` using `sys.setprofile` on Python 3.11, with a separately tested optional `sys.monitoring` backend on 3.12+. Recording is an explicit execution command; normal ingestion still never executes repository code. The wrapper must run the specified interpreter/command without shell interpolation, preserve exit status and restore prior hooks. Distinguish logical invocations from generator/coroutine resume segments, and execution time from wall duration; do not double-count resumes or call segment timing an end-to-end p95. Bound capture duration, buffered events and artifact size, recording truncation rather than silently dropping events. Record incomplete/crashed runs honestly. Support pytest through the wrapper first, then an opt-in pytest plugin; a coverage integration can add executed-line evidence but cannot infer call edges from line coverage alone.
6. **Expose collection selection.** Bootstrap lists collection IDs, environments, windows, source match and capture completeness. Enable runtime controls only with an available matching collection. Add `observed` status alongside the chosen static statuses when overlaying, and restore the static filter when disabling. Display units and observation coverage; no traces means unknown, and an unobserved call is not proof of absence.

**Gate:** base-snapshot immutability, publication rollback, deterministic mapping, multiple repos, duplicate imports, conflicting/overlapping collections, mismatched source, unknown/native frames, nested/decorated functions, recursive/async calls and exact window/environment filtering. Recorder and real pytest executions must produce recoverable observed witnesses. Thread/subprocess/async limitations must be in the collection manifest; no unsupported whole-process coverage claim.

## 7. Workstream 5 — Reproducible comparative evaluation

Files: new `evaluation/` task manifests, goldens, adapters, runner and reports; follow `reports/RELEASE_ACCEPTANCE.md`.

1. Create independent, source-verified goldens for the six approved tasks: implementation lookup, cross-subsystem explanation, callers versus callees, impact path, quotient cycle and rule violation. Include unsupported/ambiguous cases where abstention is correct. Bind each task to snapshot, source manifest, grouping, filters and model/collection digest. Do not generate the oracle solely from the implementation being evaluated.
2. Supply flat lexical search and a conventional directed table/graph baseline, plus the shared Geo Grapher service/MCP adapter. Give each arm equivalent source/evidence access and tool-call limits. Run deterministic task/grader smoke checks offline by default.
3. Add opt-in model adapters with a pinned model/configuration, prompt hash, seed where supported, bounded API spend and archived transcripts. Use equal total input/output budgets, accounting for tool wrappers and accumulated conversation as well as local payload budgets. Missing credentials or a skipped remote run must produce an explicit unverified result, never a fabricated score.
4. Grade answer correctness, direction, path validity, witness/citation recovery, scope disclosure and appropriate uncertainty. Record elapsed time, tokens, omissions and errors. Repeat model trials and report distributions; payload compression alone is not success. Treat normal-form/WL matches and undirected QI bounds according to their actual claims.
5. Prepare the same task protocol for human spatial-versus-search/table studies. Automated model tests do not establish human orientation or screen-reader usability.

**Gate:** reproducible offline grader fixtures and actual recorded model results when configured; no circular oracle, fabricated comparisons or silent exclusions. Human and AT evaluations remain separate evidence.

## 8. Final evidence and completion conditions

- Re-run the existing backend/UI/transport tests plus new regressions. Preserve C1–C14 invariants; add version-compatibility and migration checks.
- Re-ingest ToolSet at `f8bc1ec4c54884293dace635275e95c685b03371`, with the original source roots and selected-content digest. Publish new resolution/call-site counts and independently audited errors; keep historical snapshots/reports.
- Publish cold expanded latency breakdowns and before/after distributions on the same 50k/150k workload. Record the final build, hardware, browser, displayed scope and cache state, then perform the final-build 10-minute run.
- Extend the UI/UX report with grouped views, rules configuration, runtime collections and both traversal directions; rebuild and verify the distributable wheel.
- Complete the evaluation report, direct screen-reader/manual review and declared target-hardware run before marking the remaining release gates passed. If target latency or correctness still fails, keep the gate open and identify the measured remaining bottleneck.

Immediate implementation starting point after this planning deliverable: **P5.0 evidence/contract inventory, followed by P5.1 resolver fixtures and binding-specific certainty.** No new application implementation, trace execution, remote-model spend or baseline contract changes were performed to produce this plan.

## 9. Research additions: authority, scope and delivery

This addendum consolidates the supplied “Unified Visual Analytics and Software Architecture Reconstruction” draft and the source review into implementation requirements for the existing workstreams. Its algorithms, claims and recommendations are review material, not independent authorization to execute code or replace approved contracts. The approved specification, blueprint and normative contracts retain precedence. Any conflicting proposal follows §2's explicit versioning process.

The accepted synthesis is a compound graph with distinct containment and typed adjacency, evidence-preserving abstraction, focus+context navigation, geometric bundling and architecture conformance. It extends the approved neutral 3D workspace. It does not mandate FAMIX adoption, a graph database, replacement layouts, red/green direction encoding or legacy OpenGL extensions. Literature-inspired extensions are identified below rather than represented as methods already validated on software repositories.

| Existing increment | Additional deliverable | Required evidence |
| :--- | :--- | :--- |
| P5.0 | Claim/source register; analysis-assumption manifest; query semantics and optional index profile | Each proposed parameter identified as a contract value, measured choice or unvalidated experiment |
| P5.1 | Explicit distinction between syntax facts, resolution conclusions and unknowns | Positive/adversarial resolution fixtures and independent call-site audit |
| P5.2 | Output-sensitive DOI; witness-preserving quotients; documentary lexical index and typed paths; conditional dense-index optimization | Reference equivalence, KG2–KG5, coverage reconciliation and measured cold-plan costs |
| P5.3 | Display/evidence separation; corrected curves; conformance coverage; documentary navigation, overlay isolation and triage | Cross-view parity, KG6–KG8, source recovery, geometry and accessibility checks |
| P5.4 | Observation provenance and coverage semantics applied to static/runtime comparison | Valid traces retained despite static uncertainty; non-observation never proves absence |
| P5.5 | Core evidence-retrieval evaluation and optional learned/Steiner experiments | Independent answers/witnesses, matched budgets, ablations and recorded limitations |

These additions extend the exit evidence for each increment without reordering P5.0–P5.5. Sections 18–24 now make deterministic documentary retrieval and typed witness selection core planned capabilities. Learned retrieval models, Group Steiner selection and large-corpus ontology learning remain experiments, not release prerequisites. Existing failed gates remain open until their own criteria pass.

## 10. Program model and evidence contracts

### 10.1 Stable identities and optional dense indexes

Persist the approved entity IDs, typed parallel relationships and evidence records. The report's `Edge {src,dst,weight}` is only a possible traversal projection: it cannot replace relationship identity, family, subtype, resolution status, units, evidence handles or parallel witnesses.

If P5.2 profiling justifies compact indexes, build a deterministic snapshot-local bijection between sorted canonical entity IDs and dense offsets. Uint32 offsets are permitted only when the entity count fits the representation; reject overflow or select a wider representation explicitly. Dense offsets are internal implementation details and must never become durable API IDs, saved-view references or cursor identities. Version and digest the mapping with its snapshot.

Use a parent array and child offsets/IDs for containment. A parent lookup is O(1); arbitrary ancestry is not. Use the approved binary-lifting index for ancestor/LCA operations. Visiting an entire subtree costs O(number of visited vertices and tree edges), rather than O(the root's degree). If adjacency CSR is warranted, maintain outgoing and incoming indexes, with entries pointing back to original relationship IDs. Preserve parallel entries or an explicit witness list when aggregating. Publication validation still applies to the persistent store.

### 10.2 Claim semantics

1. **Syntax facts:** definitions, source spans and explicit AST constructs verified against a particular source artifact.
2. **Static analysis conclusions:** resolved or candidate targets with the applicable resolver rule, assumptions, binding state and unsupported effects. Deterministic execution of an analyzer does not itself establish a sound or complete result.
3. **Runtime observations:** witnessed events with source mapping, environment, interval and instrumentation coverage. They supplement static analysis without overwriting its results.
4. **Documentary assertions and semantic proposals:** source-linked statements, concept mappings or inferred relationships, retaining their origin and validation state. A verified documentation link proves the link, not the truth of the document's behavioural claim.

These are semantic distinctions over the existing typed records, not a requirement for four physical databases or a new enumeration in v1.0. Define any additional wire fields in the versioned addendum. Keep resolution status, numeric confidence, retrieval relevance and conformance severity separate. Do not assign automatic probability 1.0 to every static relation or invent calibrated confidence for candidates. Exact claims remain conditional on their documented static proof conditions.

Retain source digest/revision, method/version and witness handles for every published relationship. A model name alone is insufficient proposal provenance: include source evidence, prompt/configuration digest and model identifier when an experimental model is used. Canonical IDs continue to follow the approved identity rules; random UUIDs are not mandated by the research draft.

**Gate additions:** dense/canonical round trips, incoming/outgoing equivalence, parallel-edge recovery, and source/assumption recovery from Inspector and MCP. A valid runtime observation must survive even when its corresponding static target is unresolved. Unsupported analysis must yield disclosed uncertainty, not fabricated certainty or a publication-wide failure.

## 11. DOI selection, partitioning and bounded output

For canonical T+ with root depth zero, retain the approved equations:

\[
d_T(x,y)=depth(x)+depth(y)-2depth(LCA(x,y)),
\qquad DOI(x\mid y)=-(d_T(x,y)+depth(x)).
\]

Define `off_spine(x,y) = depth(x) - depth(LCA(x,y))`. Then

\[
DOI(x\mid y)=-depth(y)-2off\_spine(x,y),
\qquad DOI(x\mid y)\ge-depth(y)-2r\iff off\_spine(x,y)\le r.
\]

Use `r=0/1/2` for Path/Nearby/Wider. Constants -3/-5/-7 describe only a depth-three focus. Nearby includes immediate children of the focus as well as branches one step off the ancestor spine. Root proximity is a chosen navigation importance function, not a claim that root entities are semantically most relevant to every development question.

Build the root-to-focus spine once. For each spine vertex, enumerate non-spine child branches down to r edges from that attachment vertex; at the focus include all child branches to that depth. Each off-spine branch is visited once. With a prebuilt child index this candidate enumeration is O(depth(y) + number of emitted off-spine vertices), with O(depth(y)) also accounted for in the output spine. Do not claim this bound for an implementation that scans all entities or repeats arbitrary ancestor walks. Measure index preparation and partition/materialization separately.

DOI does not impose a node or token cap. A star can expose all children at Nearby, while Path can expose a long ancestor chain. Apply pins and requested witness paths, ancestor closure and the approved mixed-detail partition before final packing. Collapse optional branches atomically, preserve their residual membership, and regenerate affected projections. Mandatory context that cannot fit follows the approved measured budget error/continuation policy; it must not be silently truncated.

Raw DOI values need not remain unchanged when focus depth changes: even the root's value equals `-depth(y)`. Cache by focus/breadth and use exact invalidation. The normalized value `DOI(x|y)+depth(y)` is zero on the ancestor spine, including ancestors common to both foci; that property does not justify reusing every previous view or projection. Logarithmic compression/navigation claims from regular-tree examples are not universal bounds for repository hierarchies.

**Gate additions:** compare candidate sets against naive all-node DOI evaluation for root focus, uneven trees, long chains, high fan-out and all three breadth values. Check parent/child focus changes of different depths. Verify that capacity pressure preserves partition coverage and reports omitted/collapsed scope.

### 11.1 Quotient lifting retains all accepted evidence

Build the approved disjoint leaf partition Pi(E), including explicit residual groups, then assign exactly one `rep(u)` to every leaf. A visible parent shell does not also own the leaves represented by its expanded descendants. Nearest-visible-ancestor lifting is valid only when it gives precisely that same partition; it is not an alternative algorithm for partially expanded containers or conceptual grouping.

For each accepted leaf relationship `e=(u,v)`, resolve `a=rep(u)` and `b=rep(v)`. If `a!=b`, accumulate it once into the directed typed projection and retain its original relationship/witness identity. If `a==b`, accumulate it once into that representative's internal relationship summary and retain its witness. Do not discard it, count it on enclosing shells again, or merge opposing directions. Keep incompatible weight units in separate summaries.

For each filter and compatible weight unit, reconcile leaf accepted relationships against crossing plus internal projection witnesses. Count relationship IDs separately from one-to-many evidence records. Residual, conceptual and budget-induced grouping must pass the same reconciliation. A quotient cycle is a cycle in the projected graph; it does not by itself establish a matching executable leaf cycle.

## 12. Geometry and rendering corrections

Blueprint §4 remains the mathematical authority, including sphere-pack-v1, deterministic fallback stagger, Greville safety projection, opposing/parallel lanes and smoothstep EdgeLens. Containment paths route drawing geometry; call, dependency and runtime paths retain their own typed witnesses and direction. Moving control points, removing a geometric LCA, changing beta or applying a lens must not change any graph fact or evidence path.

For N distinct-endpoint control points after permitted LCA removal, use `p=min(3,N-1)`, `M=N-p-1` interior knots and the clamped vector:

\[
U=[\underbrace{0,\ldots,0}_{p+1},\;j/(M+1)\;(j=1,\ldots,M),\;\underbrace{1,\ldots,1}_{p+1}].
\]

There are `N+p+1` knots. Cubic endpoint multiplicity is four, not three. With N=2 use a linear curve; with N=3 use a quadratic. Preserve both endpoints. LCA removal requires original N0>3 and an interior LCA; never remove an endpoint when one entity is an ancestor of the other. Self-relationships use the existing self-loop geometry and internal summaries rather than a zero-length chord passed to the ordinary lane solver.

Apply Holten Method 1, followed by the approved Greville projection and deterministic transverse lanes. Beta=0 produces a straight shared base curve; distinct lanes may retain transverse separation. Beta=1 retains hierarchical influence but does not make the spline interpolate every control point. Keeping a three-point polygon avoids a particular degeneration; it does not guarantee separation of parallel/opposing relationships. Lanes remain necessary, including during EdgeLens changes.

Retain approved neutral relation/status colours and accessible patterns, legend and text equivalents. Literature red/green gradients are examples, not compulsory palette tokens. Use bounded source-to-target cues alongside arrows and text, rather than relying solely on hue. Do not impose a 50-segment minimum: retain the blueprint's sampling levels and test visual quality/performance on the declared viewport and hardware.

Use browser-supported Three.js/WebGL rendering. Do not copy fixed-function `GL_ALPHA_TEST` or `EXT_blend_minmax` calls as an application requirement. Min/max channel blending may be evaluated separately; its algebraic commutativity does not make an entire depth-tested, transparent 3D pipeline order independent. Sorting by curve length is also not depth sorting. If a length-based overlay pass is introduced, draw long curves before short curves when using source-over blending, then render selected/hover cues deliberately. Opacity must be finite, clamped and defined for zero length; the draft's unbounded `1/length` rule is rejected.

**Gate additions:** N=2/3/4+, knot counts, endpoint and interior-LCA cases, finite degenerate geometry, opposing/parallel lanes, lens continuity, no fact changes under geometric controls, readable direction without colour, and measured final-build performance. Control-point operation counts alone do not demonstrate a frame-rate improvement or an optimal layout. Retain the approved stable sphere workspace; new layouts require separate evidence and scope decisions.

## 13. Evidence retrieval and documentary context

The shared query service remains the single semantic implementation for UI, HTTP and the seven MCP operations. Define incoming/outgoing traversal over original directed relationship facts, with explicit family, subtype, resolution and runtime scope. Inclusion, similarity, inheritance and calls are different predicates. An arbitrary mixed-predicate walk is not automatically an execution path, and an edge in a call graph does not establish feasible end-to-end control flow.

Implement the deterministic bounded retrieval baseline in P5.2–P5.3, then evaluate it in P5.5 using the existing operations and source-verified tasks (§§20–24):

1. Identify candidate symbols/concepts, retaining ambiguous alternatives and lexical/source evidence.
2. Retrieve question-relevant directed relationships and documentary fragments with their original witnesses.
3. Apply only path templates whose predicates and direction match the task. Keep containment for orientation and documentary incidence for supporting context; neither contributes fictitious dependency degree.
4. Package endpoints, intermediate witnesses and scope metadata through the approved token packer. Report unavailable targets, unresolved links and budget omissions explicitly.
5. Compare this arm with the existing architecture context and flat baseline under matched total budgets, measuring correctness, witness recovery, latency and tokens. Include multi-file helpers, indirect dispatch, negative questions and conflicting/stale documentation.

Uniqorn-style Group Steiner evidence selection is an optional candidate-selection experiment, not an exact core query guarantee. It solves a costly connected-evidence problem under a chosen cost model, does not establish execution feasibility, and can connect alternative interpretations incorrectly. Any prototype must specify directed versus undirected selection, nonnegative costs, anchors/groups, approximation or search bounds, timeout, witness recovery and incomplete/disconnected outcomes. It must not invent a connection merely to return a tree. The draft's hybrid edge weights and thresholds are proposed experiments, not findings attributed to Uniqorn.

Document ingestion should retain stable fragment IDs, section/heading ancestry, source digests and source spans. A conceptual index links terms to these fragments and mapped code entities while preserving documentary hyperedges. It does not reparent canonical code or turn a textual association into a call edge. Expose supporting fragments in the Inspector and shared content/evidence workflow; version additional result fields explicitly.

Formal/documentary lexical fusion is a core planned baseline (§20). Dense fusion, synonym suggestions, learned concept classes and ontology completion remain optional proposal indexes after core correctness/performance. Use authoritative symbol lookup for exact names. Rank scores and reciprocal ranks are retrieval signals, not calibrated probabilities or proofs of identity. Evaluate false synonym merges and retain original identities; never merge code entities solely because their labels or embeddings are similar. Do not add pretrained weights, external calls or model spend as an implicit dependency of offline extraction.

## 14. Architecture conformance and uncertainty

Implement the approved rules model as a reflexion-style comparison between mapped conceptual components and extracted implementation relationships. Report convergences where expected dependencies have witnesses, divergences where implementation dependencies conflict with the model, and absences where required dependencies have no accepted witness. Keep unmapped entities as a separate coverage result. Under open-world policy, an unspecified dependency is not automatically forbidden; retain the approved require/allow/forbid and closed-world semantics.

An absent required dependency may be an inconclusive finding when mapping, parsing, resolution or relationship scope is incomplete. Disclose those limitations using the existing epistemic safeguards. Unobserved runtime calls do not prove a required dependency absent, and observed calls prove occurrence only within the recorded collection. Never automatically prune conceptual definitions, rewrite source boundaries or enlarge the rules schema because a comparison returned absence/divergence.

Validation mechanisms are claim-specific: source parsers/resolvers check supported static conclusions; trace validators check observations; schema checks validate record structure; conformance evaluates rules; and source review evaluates documentary/semantic claims. Schema validity alone does not establish a claim's truth. Retain the existing manual rules workflow and reviewable diffs; the research report does not introduce a new Lead Architect approval requirement for routine work already authorized by the user.

**Gate additions:** independent expected/forbidden/unmapped fixtures; open versus closed policy; incomplete extraction and mapping; runtime non-observation; and explicit separation between geometric routes, dependency witnesses and conformance findings.

## 15. Evaluation parameters and acceptance evidence

Preserve approved C1–C14 and the workstream gates. The supplied drafts do not establish universal values for candidate confidence, topic coherence, channel weights, three-hop limits, a 50-node cap, F1>=0.90, 40% improvement, ECE<=0.05 or 100% call resolution. Do not silently import them as release gates. Version experimental parameter settings and choose them using held-out task evidence. A status marked exact is not a learned probability; do not compute calibration error for categorical labels without a defined probability model and appropriate ground truth.

Measure extraction precision/recall on supported, independently labelled call sites and record abstention/unsupported coverage separately. Measure answer quality on task answers rather than substituting graph-extraction F1. Evidence attachment coverage measures availability of witnesses, not their correctness or sufficiency. Evaluate source fidelity and task sufficiency separately. Runtime non-observation must not supply negative labels for static possibility without a justified coverage protocol.

Retain the six approved comparative tasks and add cross-file helper recovery and ambiguous/disconnected evidence cases as variants. Compare core service, optional retrieval experiments and flat baseline with equivalent source access and total budgets. Ablate documentary context and connected-path selection before attributing gains to either. Record model/configuration and repeated trials; generated explanations and model grading alone are not an independent oracle.

Use Furnas's botanical ordering experiment as motivation, not a promised software navigation accuracy. Record Holten's evaluation as informal and its numerical settings as examples. Report whether a source supplies an empirical result, a conceptual framework or a proposed adaptation. No literature result closes target-hardware, human usability, assistive-technology or final-build soak gates for this application.

## 16. Source register and wider-folder findings

Maintain the following traceable starting register in P5.0. Capture the exact source artifact digest and inspected page/section for each adopted claim in the eventual implementation evidence. The supplied consolidated draft remains secondary synthesis; source support and local experiments determine whether a proposal is adopted.

| Source | Supported contribution and applicability |
| :--- | :--- |
| [Furnas, Generalized Fisheye Views](https://courses.ischool.berkeley.edu/i247/f05/readings/Furnas_GeneralizedFisheyeViews_CHI86.pdf) | DOI and focus+context; qualify regular-tree bounds and botanical-task results. Does not impose token caps or prove application usability. |
| [Holten, Hierarchical Edge Bundles](https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Holten06.pdf) | Hierarchy-guided spline geometry, Method 1 and conditional LCA removal. Greville safety projection and deterministic 3D lanes are blueprint extensions. |
| [Ducasse and Pollet, SAR taxonomy](https://fileserver-az.core.ac.uk/download/50073399.pdf) | Recovery processes, heterogeneous inputs and architectural comparison. Does not justify automatic ontology pruning or complete static resolution. |
| [Uniqorn](<E:/Librarian research/Unified question answering over RDF knowledge graphs.pdf>) | Connected evidence across structured facts and text. Optional task-specific retrieval experiment, with original witnesses retained. |
| [Exploratory search workflows](<E:/Librarian research/Exploratory search workflows on Knowledge Graphs.pdf>) | Iterative querying motivates preserved investigation context; student Wikidata workflows do not validate an IDE layout. |
| [Browsable Concept Index](<E:/Librarian research/An_Optimization_Approach_to_Automatic_Construction_of_Browsable_Concept_Index_for_Organizing_Online_Educational_Content.pdf>) | Concepts linked to supporting text segments; adapt to documentary navigation without fabricating program dependencies. |
| [PQL program analyzers](<E:/Librarian research/Design_of_flexible_static_program_analyzers_with_PQL.pdf>) | Program-query semantics separated from storage and UI; supports a single shared semantic service. |
| [Knowledge-based Infrastructure as Code](<E:/Librarian research/A knowledge-based approach for guided development of infrastructure as code.pdf>) | Task-specific matchmaking, validation, smell detection and completion with application/user evaluation; a relevant model for development-task acceptance. |
| [LLM-S2KG](<E:/Librarian research/applsci-16-04720.pdf>) | Document structure alongside semantic extraction; forestry-domain results motivate a documentary experiment, not resolver guarantees. |
| [APE entity matching](<E:/Librarian research/Examples for LLM-based Entity Matching.pdf>) | Human feedback on ambiguous examples; optional prioritization of semantic mapping reviews. |
| [Retry bug study](<E:/Librarian research/3694715.3695971.pdf>) | Static, model-assisted and dynamic approaches expose complementary failure modes; missing cross-file helper context motivates a concrete evaluation variant. |
| [Manufacturing process knowledge modeling](<E:/Librarian research/Systematic knowledge modeling and extraction method planning based on knowledge graph.pdf>) | Domain ontology, bootstrapped extraction and meta-path questions; motivates typed task templates with disclosed transfer limits. |

Other reviewed sources on ontology reuse, taxonomy mapping, multichannel classification, graph embeddings, governance and synonym-aware completion supply optional retrieval/provenance ideas. They do not establish that a particular method is “best” for code graphs. Keep model completion and learned matching outside the resolver's proof rules and evaluate them independently before expanding their authority.

## 17. Addendum completion checklist

- P5.0 source/assumption register identifies report proposals separately from approved contract values and reproduced measurements.
- P5.1 status/provenance checks demonstrate uncertainty preservation and valid runtime/static disagreement handling.
- P5.2 reference-equivalent DOI selection, disjoint residual partitions, crossing/internal witness reconciliation and cold-plan profiles are recorded.
- P5.3 corrected geometry and query/display separation pass across mixed and conceptual views; neutral accessible encodings and model coverage disclosure are preserved.
- P5.4 observation mapping and capture limitations appear in both UI and agent responses; non-observation remains unknown.
- P5.5 task variants, optional retrieval ablations and final acceptance evidence disclose scope, omissions and uncertainty without unsupported numerical promises.

This addendum is a planning deliverable. Implementation follows the sequence and authorization already specified for Phase 5; writing this addition does not itself execute the workstreams or alter the authoritative contracts.

## 18. Workstream 6 — Evidence retrieval and knowledge-graph design

**Recommendation:** expand the knowledge graph as an evidence-bearing program model with documentary navigation and question-specific retrieval. Preserve SQLite, canonical identities, typed parallel relationships, immutable snapshots, T+, the neutral spatial workspace and the seven shared operations. A new graph database, RDF conversion, FAMIX replacement or LLM extraction dependency is unnecessary for this increment.

The supplied reports offer useful patterns, but their appended corrections and source limitations qualify their claims. They do not authorize automatic execution, new approval hierarchies, ontology pruning or changed release gates. The approved engineering baseline remains authoritative; conflicting additions are proposals for the versioned addendum in §2.

| Capability | Phase 5 disposition | Delivery |
| :--- | :--- | :--- |
| Structured syntax/conclusion provenance and uncertainty reason codes | Core; extend resolver evidence | P5.0 design, P5.1 implementation |
| Heading/section/paragraph ancestry and source-linked document context | Core, deterministic, local | P5.0 fixtures, P5.2 extraction/indexing |
| Exact symbol lookup plus formal/documentary BM25 and rank fusion | Core, configurable lexical baseline | P5.2 service, P5.3 UI |
| Typed, bounded shortest-path witness selection between explicit anchors | Core; original dependency witnesses, explicit incomplete outcomes | P5.2 engine, P5.3 navigation |
| Conservative reachability pruning | Optional acceleration of the core engine; unpruned traversal is the reference | P5.2 only if profiling justifies it |
| Explainable ambiguity triage and versioned semantic-overlay records | Core plumbing and inspection; no learned generator required | P5.3 |
| Dense embeddings, APE-style active learning, synonym/ontology completion, Group Steiner retrieval | Optional separately versioned experiments | P5.5 experiments after core gates |

Proposed implementation boundaries: `claims.py` for evidence validation, `documents.py` for documentary structure, `retrieval.py` for lexical ranking and typed traversal, `overlays.py` for versioned noncanonical records. Names are implementation choices; avoid duplicating existing extractor, analysis, rules, content and packing semantics. Both human and agent clients use `QueryService`.

## 19. Claim provenance and uncertainty diagnostics

### 19.1 Versioned evidence details

P5.0 specifies and P5.1 validates `claim-details-v1` inside `evidence.details_json`. The record contains `claim_kind` (`syntax`, `static_conclusion`, `runtime_observation`, `documentary_assertion`), `producer` and `producer_version`, `reason_code`, sorted `additional_reason_codes`, `assumptions`, and references to the supporting source or collection. Semantic proposals have their separate overlay contract (§22), not a new v1 resolution status.

For static conclusions add `occurrence_id`, `syntax_kind`, expression/source span, resolver rule/version, binding proof or uncertainty state, and sorted alternative target IDs. An occurrence identifies one source expression under its snapshot/repository/artifact/span; alternative relationships share it. Source coordinates are one-based inclusive lines and zero-based half-open UTF-8 byte offsets, with conversion from AST/tokenizer coordinates tested for Unicode. Preserve original artifact digest and revision. If precise offsets are unavailable, disclose that limitation rather than inventing them.

Reason codes are a closed, versioned registry with documented proof conditions; additional reasons support combinations. Initial registry:

| Classification | Example codes and meaning |
| :--- | :--- |
| Proven static rule | `LEXICAL_UNIQUE_BINDING`, `UNAMBIGUOUS_IMPORT_MEMBER`, `STATIC_MRO_UNIQUE`; each requires its rule's complete assumptions, not merely a unique name |
| Candidate target | `CFG_BRANCH_REBOUND`, `POLYMORPHIC_MRO_CANDIDATE`, `DECORATOR_WRAPPED_BINDING`, `CLOSURE_CELL_MUTABLE`, `AMBIGUOUS_MODULE_ROOT`, `TREESITTER_SYNTACTIC_ONLY` |
| Unresolved cause | `EXTERNAL_PACKAGE_UNINDEXED`, `BUILTIN_SYMBOL`, `MISSING_RELATIVE_IMPORT`, `DYNAMIC_ATTR_DISPATCH`, `REFLECTIVE_CALL`, `DYNAMIC_EXPORT_STAR`, `UNSUPPORTED_ANALYSIS` |

Codes describe causes, not automatic status rules: a fallback parser may identify syntax without establishing any candidate target. Builtin/external classification needs positive binding/import evidence; a failed lookup alone establishes neither. Use `UNSUPPORTED_ANALYSIS` with an explicit construct when no narrower cause is established. An inheritance syntax occurrence is distinct from its resolved base-class conclusion. Do not apply static proof codes to traces. Runtime details reference mapper, environment, collection, coverage and mapping outcome as specified in §6.

Completed historical snapshots remain unchanged. Generate new reason records during re-ingestion; legacy records lacking structured details are displayed as `legacy_reason_unavailable`, never retroactively assigned a proof. Reason summaries count distinct occurrences separately from alternative relationships and evidence multiplicity.

### 19.2 Authority, confidence and utility

Keep the existing `exact/candidate/unresolved/observed/declared` statuses and existing families. Do not import the report's incompatible `inferred` status or equate exact with probability 1.0. Nullable numeric confidence remains uncalibrated unless an independently evaluated probability model exists. Retrieval utility is a separate query-specific ordering signal.

Preserve the Exact default and explicit candidate preset. Within an enabled scope, prioritize requested witness paths and task relevance before unrelated optional imports; status remains visible on every selected relationship. This ranking requires a versioned selection policy under §4, not a silent change to approved admission order. Semantic proposals never become resolvable calls merely by ranking highly or receiving a reviewer acceptance.

Expose reason distribution, unsupported constructs and source/assumption handles in the Advanced Inspector and shared response metadata. Unknown target locality is its own bucket; distinguish known internal targets, proven external targets and internal callers with unknown targets.

## 20. Hierarchical documentation and two-channel local retrieval

### 20.1 Documentary structure without changing code topology

Baseline representation: retain canonical `document` and `fragment` entities and existing documentary hyperedges. Build a separate versioned documentary tree `T_D` in `analysis_results`, with namespaced section IDs and references to canonical paragraph/comment/docstring fragment IDs. A section is documentary metadata, not a new canonical entity kind or a reparenting of code. P5.0 defines the metadata schema; create it only while a new snapshot is building. Search indexes are disposable sidecar caches keyed to the complete snapshot and documentary algorithm version.

`documentary-tree-v1` records `document_id`, `artifact_digest`, parser/version, and entries with `section_id`, `parent_section_id`, heading level/text, heading and section spans, ordered fragment IDs and source-span handles. Section IDs hash repository, path, artifact digest, heading occurrence and span; they are stable for identical artifacts, with no promise of cross-edit identity. Paragraph fragment IDs retain approved identity rules. Preserve occurrence order and duplicate headings explicitly.

Use a Markdown parser with recorded version: ATX and Setext headings form a stack by heading level; skipped levels attach to the nearest preceding shallower heading or document root. Heading-like text inside fenced/indented code blocks is not a heading. Preserve front matter and code examples as source content. Paragraphs attach to the innermost section. Plain text has one root section. Comments/docstrings retain lexical ownership, with any internal documentary headings represented only in T_D. Source spans recover original bytes, including line endings; normalize only the index text.

Document-to-code association provenance distinguishes lexical ownership, explicit qualified reference, ambiguous short-name mention, curated mapping and learned proposal. Existing `discusses/documents/rationale_for/cites` incidence roles remain; association method, ambiguity and supporting spans live in versioned derived metadata. Preserve all alternatives for duplicate short names. A matching token proves a mention, not a behavioural dependency or identity. Do not expand a heading into a blanket claim about every descendant symbol.

Adding T_D, search caches, concepts or proposal mappings must leave canonical code ownership, dependency degree, code-only WL/SCC/cut metrics and code-only partition membership unchanged. Make that scope explicit in tests and requests; document entities may appear in a separate documentary view. Mismatched/stale document digests are reported and excluded from claims of current implementation behaviour. Historical documentation remains inspectable with its revision.

### 20.2 Formal and informal search channels

`lexical-fusion-v1` runs locally without model weights:

1. Exact repository-qualified symbol/ID lookup runs first. Preserve case-sensitive identity lookup, ambiguity across repositories and qualified-name alternatives. Exact matches form a distinct result tier; fusion cannot demote them behind prose matches.
2. Formal channel indexes qualified names, paths, symbol kinds and actually extracted signature/parameter fields. Retain original tokens and emit deterministic camelCase, acronym-boundary and snake_case subtokens. Apply Unicode NFC and case-folding to search terms only. Do not change canonical identities or infer missing signatures.
3. Informal channel indexes paragraph text, docstrings, comments and ancestor heading text in separate fields using SQLite FTS5 BM25. Commit messages require separately ingested history provenance and are outside this baseline. Deduplicate heading contributions per fragment and cap returned supporting fragments per entity to avoid repeated prose dominating by count.
4. Convert each channel to a one-based entity rank: formal hits directly; informal fragment hits through documented incidences, retaining association uncertainty and source handles. An unlinked fragment remains a documentary hit, not an invented code association. Collapse multiple fragment hits to the best rank per entity before fusion.
5. For non-exact entity results use `score(e) = gamma/(k+rank_formal(e)) + (1-gamma)/(k+rank_informal(e))`; a missing channel contributes zero. Proposed initial configuration is `gamma=0.8`, `k=60`, explicitly an engineering starting point requiring ablation. FTS5's lower-is-better BM25 convention must be converted to ranks correctly. Sort ties by canonical entity ID.
6. Return channel ranks, matched fields, fragment/evidence handles, association basis and effective configuration; never present the fusion score as confidence. Reuse endpoint-closed token packing for graph context, with independent limits on search candidates, index work and evidence expansion.

FTS5 availability is checked at startup; a missing extension produces an explicit feature-unavailable result while exact symbol lookup remains usable. Index builds use atomic replacement and versioned invalidation, never silently query another snapshot. Benchmark index build time, storage, cold/warm queries and document-heavy repositories separately from the existing code-only viewport benchmark.

The RRF family is supported by [Cormack, Clarke and Buettcher's original publication](https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/). Applying weighted fusion to these two code/document channels and selecting gamma are Geo Grapher design proposals, not results established by that paper or by patent-classification studies.

## 21. Typed witness paths and conservative pruning

### 21.1 Bounded deterministic baseline

Define `typed-bridge-v1` over original subject-level directed relationships, preserving their canonical relationship IDs, normalized T+ endpoints and evidence. Resolve UI focus and pins to explicit subject anchors; containers represent sets of descendants rather than a fictitious callable container. Expand these sets under documented resource limits and report uncovered anchors. Do not interpret reachability in a quotient or QI summary as proof of a leaf-level path.

1. Validate snapshot, filter, family/status/subtype scope, collection and a versioned path template. Return unresolved symbol alternatives before choosing an interpretation; multiple name matches do not silently become simultaneous mandatory anchors.
2. Process explicit ordered source/target pairs deterministically. For a focus with multiple pins, search focus-to-pin paths in sorted pin order. This baseline does not optimize all anchor pairs or promise a globally minimum connected subgraph.
3. Run bounded BFS on the product of the subject graph and the template's finite-state machine. Each original relationship costs one hop; sort neighbours by target subject and relationship ID, preserving parallel alternatives. Track `(subject, template_state, hop_count)` states and predecessor witnesses. Do not prune longer visits using a shorter visit in an incompatible template state.
4. Proposed operational defaults: maximum 4 relationship hops per pair, 8 anchor pairs and 20,000 state expansions per request, recorded in the plan fingerprint. These are configurable starting limits, not literature-derived quality gates. Enforce cancellation/deadline independently; if exceeded, return a partial/search-limited result rather than claiming disconnection. Record all effective bounds.
5. Recover the first deterministic shortest accepted witness path for each pair and union by relationship ID. Preserve ordered steps per path even when paths share edges. The union may be disconnected; do not add synthetic dependencies to connect it. More path alternatives require an explicitly bounded later option.
6. Attach endpoint/intermediate definitions, evidence handles, uncertainty reasons and selected documentary context. Admit a requested path as an atomic optional dependency closure under the packer, or mark it omitted/continueable. If explicitly mandatory context cannot fit, return the measured budget error. Never call an endpoint-closed but truncated path a complete witness.

Core templates are deliberately narrow:

| Template | Accepted relations and interpretation |
| :--- | :--- |
| `CALL_CHAIN_WITH_HELPERS` | One or more forward `calls` relationships; evidence for a static possible call chain or observed call adjacency, never whole-path execution feasibility |
| `INHERITANCE_AND_OVERRIDES` | Forward `inherits` traversal plus separately identified member/MRO evidence; an override is not invented as an edge where no supported fact exists |
| `BOUNDARY_CROSSING_WITNESSES` | Selected forward dependency predicates with an explicit transition across configured component membership; report unmapped memberships separately |

Store template predicate sets, states/transitions and acceptance conditions as versioned service configuration. Runtime and static edges remain separate scopes by default. An explicit combined view labels mixed provenance; aggregated runtime edges alone cannot prove that all steps occurred in the same invocation/session. Retry/exception questions additionally retrieve helper definitions and source/CFG evidence; the current call model does not manufacture exception-handler or data-flow facts.

Incoming traversal preserves original source/target direction. An explicitly requested undirected explanatory bridge may traverse a relationship backwards, but every step retains its original arrow and a `traversal_reversed` flag. Containment routes, documentation incidences and similarity links appear as separately labelled supporting context and never satisfy a call-chain template.

Result outcomes distinguish `found`, `no_path_within_scope`, `hop_limit_reached`, `search_limit_reached`, `ambiguous_anchor`, `unavailable_anchor`, `cancelled` and `omitted_by_budget`. Only an exhausted relevant search establishes no path in the selected extracted scope; it does not prove no runtime execution path. State completion per anchor pair, independently of response-page completeness.

### 21.2 Safe reachability acceleration

The supplied reachability-pruning review concerns inexact subgraph matching; no paper-specific reduction theorem or speedup is adopted here. Use optional exact reachability checks solely as implementation accelerators. Build SCC/DAG indexes for the same snapshot and an equal or broader accepted relationship scope. A proven unreachable pair in that supergraph can be rejected; a reachable pair does not prove the typed template matches. For bounded paths, prune only with a proven lower bound greater than the remaining hop allowance.

Include snapshot, direction, scope, template and index version in index/cache identity. An absent/stale index falls back to unpruned BFS. Approximate embeddings, candidate similarity, incomplete runtime observations and geometry cannot supply hard negative pruning. Every accelerated implementation must match the unpruned oracle on exhaustive small graphs and representative queries, including cycles, parallel edges, candidates and stale indexes. Do not claim applicability of the named research algorithm without examining its original assumptions and reproducing them.

Group Steiner selection remains optional. [Uniqorn's primary publication](https://pure.mpg.de/rest/items/item_3347391_3/component/file_3635886/content) uses weighted, undirected context graphs with groups of anchors; adapting that approach to directed software dependencies is separate research. A future prototype must retain original typed witnesses and measure task benefit against this simpler BFS-union baseline.

## 22. Semantic overlays, concept mappings and ambiguity triage

### 22.1 Overlay record and lifecycle

Use a versioned `semantic-overlay-v1` envelope with `overlay_id`, `base_snapshot_id`, content/configuration digest, producer/version, creation time, provenance references and records. Each record has a stable overlay-local ID, typed concept/mapping/proposal kind, referenced canonical entity/fragment IDs, a proposed predicate, rationale, support handles, optional retrieval scores and a review state (`proposed`, `accepted_as_annotation`, `rejected`, `superseded`). Review decisions record author, timestamp and reason in append-only revisions. Model-based records additionally identify model, prompt/configuration digest and input artifacts.

Persist prototypes as namespaced `analysis_results` artifacts without editing completed canonical tables. Validate snapshot ownership, artifact references and every claimed support handle. If indexed review/history requirements exceed that cache contract, propose a separate overlay-store migration under §2 before implementation. A human assertion becomes a reviewed annotation, not an exact parser conclusion; changing extracted certainty requires new qualifying evidence and a newly published analysis snapshot. Model suggestions cannot overwrite static or observed relationships.

Concept mappings may overlap; they are not automatically a disjoint conceptual grouping. Only a selected validated rules model can drive the approved disjoint component view, with Unmapped retained. Overlay selection/revision appears in view and cursor fingerprints. Reject or explicitly remap stale cross-snapshot references. Disabling overlays must reproduce the same canonical dependency metrics and exact symbol lookup.

### 22.2 Review queue

`ambiguity-triage-v1` presents grouped unresolved/candidate call sites and unmapped component subjects with explainable reasons. Keep three separate queues: known intra-repository candidate targets, internal callers with unknown target locality, and unmapped conceptual membership. External/builtin cases remain inspectable but are not counted as missed internal connectivity without evidence.

Initial ordering is a deterministic tuple: explicit focus/pin or requested-path relevance first, then involvement in a witnessed component-boundary dependency, then descending distinct incident relationship count, then canonical subject/span ID. Count topology in the declared original fact scope; exclude documentary/proposal edges and avoid multiplying a call site's importance by its candidate alternatives. Unknown callee degree is unavailable, not a fabricated zero or guessed hub score. Explain each sorting component in the UI. Page results; an initial top-10 display is a UI default, not an acceptance threshold.

Review actions can open source, alternatives, assumptions, document context and current mapping rules; accept/reject a semantic annotation; or prepare a rules-model diff. They do not silently edit source, merge symbols, reparent T+ or promote candidate calls to exact. Preserve focus/pins and investigation history when moving from overview to symbol to source to documentation to a refined query. Learned active-learning ordering is an optional comparison against this transparent baseline.

## 23. Shared service, wire compatibility and token closure

P5.0 drafts the following additions in `contracts/v1.1/` and a blueprint addendum; no new fields are silently inserted into strict v1.0 schemas. Keep seven MCP operations and a single query implementation:

| Existing operation | Proposed KG extension |
| :--- | :--- |
| `search_entities` | Explicit symbol/document/hybrid intent, formal/documentary rank explanations, scoped document hits and ambiguity alternatives |
| `get_architecture_context` | Explicit anchors, typed-path template/bounds, documentary inclusion, overlay revision and per-pair outcomes |
| `inspect_relationship_witnesses` | Claim/reason metadata and ordered original steps; original evidence remains recoverable |
| `get_entity_content` | Documentary section breadcrumbs, exact fragment source spans and source freshness |
| `find_dependants` | Existing direction/scope plus typed witness-path recovery and completeness; no relabelling incoming arrows |
| `check_architecture` | Mapping coverage, claim-scope limitations, Unmapped triage references and model digest |
| `find_similar_code` | Preserve AST/WL diagnostics; any documentary or learned similarity is a separately named/versioned signal |

The versioned viewport carries selected path IDs, current semantic/documentary scope and provenance summaries; source/evidence details stay lazy and pageable. Hierarchy, Matrix, Inspector and 3D must agree on selection and witnesses. Breadcrumbs identify documentary versus canonical ownership. A disconnected result is shown honestly and remains navigable through accessible lists. No hover action triggers an implicit model request or changes the locked Inspector.

Packing works on bundles of actual output records. A path bundle includes all steps, endpoint/intermediate node definitions and recoverable witness references; a document hit includes fragment definition, source handle and enough labelled ancestry to identify its section. Deduplicate shared records by stable ID and reference-count them across bundles. Full ancestry expansion is optional and budgeted; returning a breadcrumb is not a promise that the entire ancestor document was serialized. Documentary hyperedges and overlay links follow equivalent endpoint/reference closure, without being serialized as dependency relationships.

Every serialized relationship still has both endpoint definitions in `nodes`. Apply final complete-envelope verification, exact/fallback accounting, whole-bundle eviction and committed-page cursor rules from §4. Distinguish evidence handles from embedded evidence content and disclose lazy content. Pagination never reports a withheld path as delivered. Bind cursors to snapshot, filter, template/bounds, retrieval and packer versions, document-index digest, overlay/rules revision, tokenizer and budget. Expired plans use the existing explicit error behavior, never a silently recomputed different query.

## 24. KG acceptance evidence and delivery checklist

These additional gates test the new planned capabilities and preserve C1–C14; they do not assert that any implementation already passes.

| Gate | Required evidence | Increment |
| :--- | :--- | :--- |
| KG1 — Claims | Structured reasons and source/assumption recovery; Unicode spans; alternatives counted by call site; valid runtime/static disagreement; legacy details disclosed | P5.1, extended P5.4 |
| KG2 — Documents | Nested/skipped/duplicate headings, fenced examples, plain text, stale artifacts, ambiguous mentions and exact source round trips; code topology/metrics unchanged by T_D | P5.2 |
| KG3 — Search | Exact qualified lookup stays first; duplicated names stay ambiguous; deterministic ranks, missing-channel/FTS behavior and duplicate-fragment control; independently labelled documentary relevance | P5.2 |
| KG4 — Typed paths | BFS/FSM oracle agreement; directed/reverse flags; cycles, parallel candidates, disconnected anchors, limits and boundary mappings; no LCA/quotient/telemetry union treated as execution proof | P5.2 |
| KG5 — Pruning | Accelerated/unpruned equality and stale-index fallback; if no pruning index is enabled, record the reference engine as baseline rather than claiming a pruning speedup | P5.2 |
| KG6 — Overlay isolation | Versioned decisions and replay; stale references rejected; annotations never promote facts; overlay on/off canonical metrics and identities match | P5.3 |
| KG7 — Triage and journeys | Stable per-occurrence ordering with visible reasons; unknown locality separated; overview → symbol → source → documents → re-query retains focus/pins and has keyboard/list parity | P5.3 |
| KG8 — Wire/budget | Strict v1 compatibility and v1.1 schema parity across UI/HTTP/MCP; endpoint/path/hyperedge closure on every page; tiny-budget, Unicode, token fallback, eviction and expired-cursor cases | P5.2–P5.4 |

P5.0 produces a source/claim matrix, supported syntax and reason registry, documentary metadata schema, path-template state machines, explicit versioned wire/schema decisions and independent fixtures before implementation. P5.1 delivers resolver provenance before broadening visible uncertainty. P5.2 delivers bulk persistence and safe packing optimizations before enabling larger evidence bundles, then document/search/path services. P5.3 exposes those same services in the workspace, followed by P5.4 observation reconciliation. Do not bypass prerequisite test gates to maintain schedule.

P5.5 compares four matched-budget arms: flat search; existing architecture context; context plus documentary lexical retrieval; and context plus documentary retrieval plus typed witness paths. Optional learned/Steiner arms are additional experiments, not substitutes. Add variants of the six existing tasks requiring cross-file helper/retry context, inherited dispatch, stale/misleading documentation, same-name symbols, disconnected evidence and honest abstention. Build answer, source-span and admissible typed-witness oracles independently from the system under test; identify tasks for which source/CFG review is necessary beyond call edges.

Report task answer correctness, witness correctness/sufficiency, retrieval recall/ranking on independently labelled relevant items, abstention, tokens, latency, index cost and memory separately. Keep unobserved traces out of negative labels. Ablate channels and path selection before attributing gains; use held-out configurations for gamma, hop/expansion limits and any learned scores. No imported universal F1, confidence, coherence or percentage-improvement target applies. Record confidence intervals/sample counts when making comparative claims; small descriptive runs cannot establish general superiority.

Repeat the existing 50k/150k viewport workload unchanged and add a separately labelled documentary-heavy workload and a bounded-path stress workload. Re-ingest pinned ToolSet into a new snapshot, publish per-occurrence reason/locality tables and illustrative recovered paths, and retain source digests/configuration. The knowledge-graph additions cannot close outstanding AT, human usability, final-build soak or i5/Iris Xe gates without their own evidence.

### Supplied review artifacts

The following are source material for this plan update, including their corrections, rather than additional execution instructions:

- [Compiled knowledge-graph reports and appended META-REVIEW](<C:/Users/jakem/Downloads/compiled reports_knowledge graphs.md>): use corrected provenance, path and evaluation semantics; reject automatic pruning, universal thresholds and parser validation of runtime truth.
- [Phase 5 review](<C:/Users/jakem/.codex/attachments/838c0db6-38a9-453b-9102-593848380b8e/Pasted text.txt>): supplies uncertainty codes, document channels, typed bridges and triage proposals; its quoted implementation prompt does not change this request's scope.
- [Research review/corrections transcript](<C:/Users/jakem/.codex/attachments/65059746-72bc-4689-8edd-8004e79092df/Pasted text.txt>): qualifies source transfer, static/runtime truth, DOI bounds and numerical claims. Its attachment title is not evidence that the original reachability paper was supplied or reproduced.
- [Unified visual analytics/SAR technical draft](<C:/Users/jakem/.codex/attachments/49ea708a-6078-4a9c-9280-e95e55e2cdd4/Pasted text.txt>): informs §§10–12 after mathematical corrections; its rendering pseudocode does not replace the approved geometry or neutral palette.

The wider-folder sources in §16 are research leads recorded by the supplied review, not a claim that every original paper was independently reproduced in this update. The original RRF and Uniqorn publication links above substantiate their limited method attributions; software-specific defaults, schemas, algorithms and gates here are explicit engineering proposals for Geo Grapher.

## 25. Investigated technical expansion — source context and process evidence

The subsequent [technical expansions review](F:/uv-data/Geo_Grapher/PHASE_5_TECHNICAL_EXPANSIONS_REVIEW.md) assesses the supplied prompt-compilation proposal against the implementation and primary-source material. Its recommendations are proposed design additions, not approval to execute the attachment's generation/merge loop or to alter normative contracts.

Two additions extend Workstream 6 without changing the delivery order:

1. **`source-context-v1`:** design a derived statement/clause tree T_S in P5.0, then implement bounded Python source compilation in P5.2–P5.3 after prerequisite resolver/packing gates. T_S is separate from ownership T+ and documentary T_D. Return exact source segments, enclosing headers, labelled sibling stubs, omission spans and retrieval handles through a versioned `get_entity_content` mode. Preserve source trust, encoding, byte spans, mandatory-context errors and full-envelope token limits. Retain original source retrieval for unsupported syntax. Extend KG2/KG8 and compare compiler-assisted retrieval in P5.5.
2. **`process-evidence-v1`:** specify read-only source/process/pattern cards in P5.0 and expose supported cards in P5.3. Every step, constraint and relation retains evidence and its basis; lexical order, possible CFG transitions, static calls and observed sequences are different claims. Aggregate call counts cannot establish invocation order. Unsupported pattern predicates and pre/postconditions stay explicit gaps. Keep cards in the versioned overlay namespace, not canonical dependency facts. Optional query-IR/pattern experiments follow in P5.5 with independent checks.

Reject the proposed interpretation of geometric β as textual aggregation: use existing partition/grouping, typed rollups and explicit detail policies. Fixed -3/-5/-7 thresholds are depth-specific examples; DOI does not guarantee a bounded token footprint. Do not add mandatory FAMIX/Datalog engines, infer semantic completeness from ancestry, promote static conclusions using partial traces, or claim deterministic LLM reasoning/process replication.

Any optional remediation evaluation must have explicit iteration/time/token bounds, independent functional and conformance validation, and a nonconverged outcome. No automatic merge follows from conformance. Full execution/replay of extracted processes requires a separately scoped runner design; it is not a Phase 5 dependency introduced by this research attachment. The companion review records source limitations, implementation gaps and counterexample regressions in detail.

## 26. Approved actor representation — P5.0 schema and staged delivery

The actor-facing representation must combine immediate semantic grounding with measured full-envelope efficiency. The additive [v1.1 declarations](F:/uv-data/Geo_Grapher/contracts/v1.1/geographer.wire.d.ts) and [actor-schema addendum](F:/uv-data/Geo_Grapher/contracts/v1.1/ACTOR_SCHEMA.md) lock the following design obligations:

- Remove initial per-edge witness cursors, duplicate canonical node IDs, inherited node revisions and context-only AST/WL fingerprints. Keep signed continuation cursors, on-demand diagnostics and recoverable canonical identities through deterministic scoped aliases. Alias mappings themselves count toward the budget.
- Give atomic nodes source-extracted signatures and bounded doc gists. Give every rolled-up container, including collapsed files/classes, represented-leaf-owner kind counts and up to five explainably ranked exemplars. Never manufacture a missing docstring or conflate leaf-kind counts with overlapping ancestor counts.
- Ground each typed projection with up to three original witness previews and a complete primary-reason breakdown. Previews for W<=3 are complete when that summary is returned; bundle closure/omission follows the packer. Completeness means equality of witness ID sets, not merely matching lengths, and does not imply complete evidence content or execution feasibility.
- Define T_S content as exact enclosing headers, verbatim focal segments and optional sibling stubs, with explicit omission/continuation metadata. Oversized mandatory source remains subject to measured budget errors; a ten-percent source footprint is not a guarantee.

P5.0 delivers declarations, generated schemas, semantic validation requirements and baseline cost measurements. P5.1 delivers resolver/claim improvements and shared visibility presets. P5.2–P5.3 implement the v1.1 serializer, complete-envelope bundle packing, shared serving, previews and source folding; the current served API remains strict v1.0 until that versioned work passes its gates. Do not claim that schema drafting already provides v1.1 runtime density gains.

Measure fixed-set schema costs separately from adaptive page density and task round trips, in both encodings and byte-bound fallback. Treat ~5x density and ~60–90 tokens per item as goals, not observed properties. The P5.0 ablation measured 36.3% savings for the specified removable metadata on one fixed response; useful descriptors and previews must be included before reporting a final v1.1 gain. Preserve independent correctness, witness/endpoint closure and C1–C14/KG1–KG8.

## Execution status — 6 November 2026

P5.0 and P5.1 are implemented with recorded baseline, resolver/provenance and visibility fixtures. P5.2 now implements bulk projection persistence, incremental admission with final exact accounting, orthogonal documentary/source context, local lexical fusion, bounded typed bridges, grounded actor records and scoped aliases. The additive v1.1 HTTP/MCP service is operational; the earlier statement that serving awaits implementation describes the P5.0/P5.1 state. See [P5.2 engineering evidence](reports/P5_2_GATE_REPORT.md) for measured density, latency, limitations and reproduction.

P5.3 now connects v1.1 actor frames and evidence navigation to the workspace: three breadths, all grouping modes, subtype/static-family filters, bidirectional impact and original path projection, live versioned rules, semantic curve styles/hover, source/document cards, review overlays and occurrence triage. Saved version-1 views migrate missing grouping/model fields; invalid conceptual-model restores leave the active view intact. Shared MCP content and optional architecture review queues use the same read implementation. See [P5.3 evidence](reports/P5_3_GATE_REPORT.md) and [workspace contract](contracts/v1.1/WORKSPACE_ADDENDUM.md).

P5.4 now implements immutable, validated runtime child snapshots, the strict JSONL/manifest contract, explicit bounded `sys.setprofile` recording, an opt-in pytest plugin, positive/static disagreement provenance, read-only MCP collection resources and workspace collection selection with saved-window checks. Native/external/shutdown coverage and ambiguous mappings remain explicit. Optional `sys.monitoring` is not enabled or claimed verified. See [P5.4 evidence](reports/P5_4_GATE_REPORT.md) and the [runtime contract](contracts/v1.1/RUNTIME_ADDENDUM.md).

P5.5 now delivers the source-locked independent task/grader fixtures, five-arm offline retrieval comparison in both tokenizers, separate documentary/path stress evidence, pinned ToolSet re-ingestion, a four-response actual isolated subagent pilot and an oracle-free interchange for the user's DeepInfra-connected harness. See [P5.5 evidence](reports/P5_5_GATE_REPORT.md) and [evaluation protocol](evaluation/README.md). Per the user's latest instruction, larger model tests are shelved. The pilot preserves a missing document citation and an explicitly versioned grader correction; it is not a superiority study or pinned-provider whole-prompt acceptance. Source/document selection and cold derived-cache viewport preparation remain remediation items.

P5.5/release acceptance remains open for user-harness model outputs, human/AT review, target-device C14 and final-build soak. The runtime proof uses actually executed owned fixtures; no ToolSet application workload or invented real-user telemetry is claimed. Development-host smoke results do not close those external gates. No full release acceptance is implied.

7 November 2026: the Librarian/Claude follow-up is addressed by [MCP grounding remediation](reports/MCP_GROUNDING_REMEDIATION.md): explicit production tool guidance, original-document reservation within the existing source/budget caps, absolute line presentation, public task-scoped vocabulary, oracle-free source/path checks and one opt-in cumulative-budget repair. Four corrected prompts are ready for the user-owned harness. Larger studies remain shelved; historic failures are preserved and no model accuracy improvement is claimed without a new recorded run.

The next recorded three-model round is reviewed in [Actor round 2](reports/ACTOR_ROUND_2_REVIEW.md). Original results remain 2/12; all stale-document graph inputs contain the original document. Contract v3 makes provenance, file/subject identity and requested paths explicit, adds source-derived section anchors and audited provider-schema adaptation with full local validation retained. Four new user-harness prompts are prepared; provider mode negotiation and the next actual outcomes remain unverified. No new paid calls or large tests were launched.

The V3 follow-up records 7/12 but exposed an implementation defect: the flat stale-document path enum excluded its public requested target. [Actor round 3](reports/ACTOR_ROUND_3_REVIEW.md) preserves that diagnosis and the historical failures. V4 supplies snapshot identity closure, a pre-provider feasibility gate and direct-call-scoped fact/path consistency without changing source slots or weakening the rubric. The new four-request handoff is prepared; fresh provider outcomes and external acceptance remain open. The old flat/graph comparison is not treated as a fair capability result.

The recorded V4 round now reproduces 8/12 with feasible identities (405B 4/4 on these two development tasks). [Actor round 4](reports/ACTOR_ROUND_4_REVIEW.md) retains that one-shot outcome, closes a public documentary-assessment validation bypass and prepares only four optional repairs: three for 70B, one for 480B. Repair context preserves original source/scope, fetches no new evidence and shares parent token/output limits. Parent receipts, models and cumulative budgets are checked on import; post-repair outcomes remain unverified until returned by the user's harness. No new paid calls or release-acceptance claim is made.
