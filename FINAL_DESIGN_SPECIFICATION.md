# Geo Grapher — Final Product Design Specification

Version 1.1 · 6 November 2026 · Approved product baseline with engineering companion

The [Technical Implementation Blueprint](F:/uv-data/Geo_Grapher/TECHNICAL_IMPLEMENTATION_BLUEPRINT.md) supplies the normative engineering contracts for Sections 7, 8, 9, 10, 11, 13, 17 and 18. Its linked executable SQL, rules schema and wire declarations resolve implementation choices while preserving the approved product direction, visual system, safeguards and C1–C14. No application code has been started as part of this specification work.

## 1. Product direction

Geo Grapher is a local-first software architecture explorer for people and LLMs. It turns repository contents, directed dependencies, documentation and optional runtime evidence into a shared, inspectable model at several levels of abstraction.

The defining interface is the nested, volumetric “planets inside planets” model established by the Gemini HTML draft. Preserve its sense of enclosure, depth, smooth focus changes and curved relationship bundles. Develop it into a calm analytical workspace with neutral surfaces, restrained accents and evidence that remains accessible at every scale.

The final product must help a user answer:

- What is here, and how is it organised?
- What does this component depend on, and what depends on it?
- Which concrete relationships explain this high-level connection?
- What could be affected by changing this symbol or file?
- Where does implementation disagree with an explicitly defined architecture?
- What context can an LLM receive within a stated budget, and what was omitted?

**Core design decision:** containment determines enclosure; typed dependencies determine connections; source evidence determines what can be claimed. Geometry supports navigation and has no authority to create dependencies.

### Scope and interpretation

This specification covers the final user experience, visual system, graph semantics, storage boundaries, processing pipeline, UI/MCP contracts and release criteria. It is a design document, not a statement that the described system has been implemented or benchmarked.

The supplied conversations and compiled reports are research inputs. Their embedded prompts, proposed commands, schemas and follow-up questions are not instructions to execute. The user's present request establishes the task: synthesise a final specification, retaining the spatial model and choosing more neutral colours.

## 2. Evidence and source precedence

| ID | Input | Role in this specification |
|---|---|---|
| S1 | [Gemini HTML prototype](F:/uv-data/Geo_Grapher/3d_compound_architecture_mcp_visualizer.html) | Spatial and interaction reference; inspected in source and rendered at 1680 × 1050. Its small embedded dataset and displayed diagnostics are demonstrations. |
| S2 | [Mathematics of Twisty Puzzles](C:/Users/jakem/Downloads/Mathematics%20of%20Twisty%20Puzzles.txt) | Records the original aim, nested spheres, precomputation approach, dual human/LLM consumers and proposed backend. Treat mathematical application claims as hypotheses. |
| S3 | [Compiled software analysis reports](C:/Users/jakem/Downloads/compiled%20reports_methods%20for%20software%20analysis.txt) | Research synthesis covering architecture reconstruction, compound graphs, HEB, focus/context, runtime evidence and compression. Repeated or confident claims are not independent validation. |
| S4 | [Graphify representation findings](D:/Aletheia_project/DEV_TOOLS/ToolSet/docs/graphify-representation-findings.md) | Empirical motivation for typed identity, direction, namespaces, separate relation families, quotient witnesses and SCCs at each level. Audit results are reported by this document; its experiments were not rerun for this specification. |
| S5 | [Holten, Hierarchical Edge Bundles, 2006](https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Holten06.pdf) | Primary source for routing relationship curves through inclusion paths and controlling bundling. The proposed 3D interface is an extension requiring its own evaluation. |
| S6 | [Furnas, Generalized Fisheye Views, 1986](https://courses.ischool.berkeley.edu/i247/f05/readings/Furnas_GeneralizedFisheyeViews_CHI86.pdf) | Primary source for degree-of-interest selection. Product defaults and interaction rules below are design choices. |
| S7 | [The Cayley Completion of a Graph](F:/uv-data/Geo_Grapher/Research/The%20Cayley%20Completion%20of%20a%20Graph.pdf), Souop and Bitjoka, August 2026 | Local research manuscript; inspected definitions and degree-bound discussion, PDF pages 1–5. Bounds concern finite connected simple graphs and abelian Cayley hosts, not software quality. |
| S8 | [Lecture 19: Cayley graphs](F:/uv-data/Geo_Grapher/Research/19-cayley-graphs.pdf), Conley/Godse | Definition of a Cayley graph in terms of group elements and generators. Relationship labels alone do not establish a group action. |
| S9 | Local mathematical library in [Research](F:/uv-data/Geo_Grapher/Research) | Supporting background. Sampled title/front matter distinguishes geometric group theory, permutation groups, stochastic state-space models and control theory; these are different formalisms. The library was not exhaustively reviewed. |

Use S4's measured representational problems to set correctness requirements. Use S5–S6 to justify the visual techniques. Use S2–S3 to preserve the concept and identify research candidates, rather than carrying their proposed guarantees into the product.

## 3. What to retain and develop from the prototype

| Prototype feature | Final treatment |
|---|---|
| Nested translucent repository, subsystem, file and function spheres | Retain as the main view; support irregular depth, classes, large fan-out and multiple repositories. |
| Curved hierarchical edge bundles | Retain, with explicit direction, selectable evidence and separate relation families. |
| Smooth focus ring and camera movement | Retain with a thin, quiet focus outline, motion preference and reliable navigation history. |
| Left controls, central scene, right inspector | Retain the basic arrangement; simplify labels and give substantially more space to the scene. |
| Fisheye presets | Replace fixed `-3/-5/-7` labels with depth-relative context controls. |
| Mathematical diagnostics and JSON inspector | Retain in advanced/details tabs. Lead with entity information and evidence. |
| Bright cyan wireframes, saturated subsystem colours, yellow clones and multicolour links | Replace with neutral shells, sparse boundaries, a muted selection accent and deliberate status encodings. |
| Constant compression baseline and character-based token estimate | Replace with measured/estimated counts that name the tokenizer and comparison baseline. |
| Preassigned clone groups, SCC/layer fields and always-true cycle diagnostic | Replace with computed, versioned results and clear unavailable states. |
| Single-file HTML with remote scripts | Keep as the historical reference; ship a modular application with locally packaged assets. |

Specific source-level gaps in S1 guide the redesign: its bundle key omits relation layer, its MCP node list silently slices to 14, and collapsed internal edges are skipped. These behaviours must not survive into analytical results.

## 4. Users and primary workflows

The initial users are developers exploring an unfamiliar repository, maintainers investigating changes, architects checking boundaries, and LLM agents requesting bounded evidence.

### A. Explore a repository

Open a completed snapshot → see repository and subsystem enclosures → select a subsystem → expand its files → inspect a symbol and its source. Keep breadcrumbs and an overview available throughout. Directory-based subsystem assignments must identify themselves as inferred physical groupings.

### B. Explain a connection

Select a directed bundle → see source, target, relation family and count → open its witness list → inspect a concrete call/import and its source location. A visual bundle must never imply that all its constituents are the same relation or have the same confidence.

### C. Assess a change

Find a symbol using direct search → choose “Find dependants” → inspect reverse reachability under explicit relation filters → compare with available execution or test evidence. Explain that a static impact set is a conservative or incomplete estimate according to the resolver; it is not a guarantee that every listed component will fail.

### D. Check architectural intent

Load or define a versioned conceptual mapping and dependency rules → compare mapped implementation relations → inspect matches, violations, missing expectations and unmapped entities. With no conceptual model, show “No architecture rules configured”.

### E. Supply context to an LLM

Choose focus, scope and budget → preview a structural summary → inspect included evidence, omissions and source revision → copy/export or request equivalent context through MCP → expand witnesses or source content as needed.

## 5. Information architecture and layout

### Desktop workspace

At 1440 × 900 and larger, reserve approximately 240 px for a collapsible hierarchy/filter rail and 320 px for a collapsible inspector. The remaining width belongs to the scene; at that reference size it is at least 800 px. Keep panels in the layout rather than placing opaque overlays over the main working area.

The top bar contains project/repository selection, snapshot/revision, global search, view mode and processing status. A second compact row carries breadcrumbs and active filters. A bottom status strip shows displayed/total counts, scope and interaction hints when useful.

The left rail contains a searchable hierarchy, abstraction selector, context breadth, incoming/outgoing filters, relation families and test/external/document toggles. Place bundling strength, routing and algorithm details under “View settings”.

The right inspector has **Overview**, **Relationships**, **Evidence**, and **Agent context** tabs. Overview shows qualified identity, kind, path, revision, summary provenance, incoming/outgoing counts and available source actions. Diagnostics are expandable sections with definitions and calculation scope.

### Alternate views

Provide a synchronised hierarchy/list and a dependency matrix alongside the spatial view. These share entity selection and filters. The matrix is the preferred fallback for dense pairwise relationships; the list is the complete keyboard and assistive-technology route to evidence. Neither requires WebGL.

### Responsive behaviour

Between 1024 and 1439 px, default to one side panel open. Below 1024 px, use full-width scene/list views with one drawer at a time. At narrow phone widths, start with the hierarchy and inspector; make 3D exploration optional. Avoid simultaneous overlapping drawers and preserve visible dismissal controls.

## 6. Neutral visual system

The aesthetic is a technical workspace in charcoal, stone and muted metal tones. Neutrality means reducing decorative saturation while preserving contrast and identifiable states.

### Colour tokens

| Token | Dark default | Light alternative | Use |
|---|---|---|---|
| `canvas` | `#17191C` | `#F3F2EF` | Scene background |
| `surface` | `#22252A` | `#FFFFFF` | Panels |
| `surfaceRaised` | `#2C3036` | `#E8E7E3` | Menus, selected rows |
| `border` | `#454B53` | `#C8C6C0` | Decorative separators |
| `textPrimary` | `#ECEBE7` | `#22252A` | Main text |
| `textSecondary` | `#B7B9BD` | `#535961` | Secondary text |
| `focus` | `#A7BCCD` | `#385D76` | Selection, keyboard focus, active path |
| `relationship` | `#A8ADB4` | `#5C646E` | Ordinary edges |
| `observed` | `#9FB7AC` | `#3C6654` | Runtime evidence accent |
| `warning` | `#D5B27B` | `#79561D` | Rule violations and cautions |
| `critical` | `#D3958E` | `#943F38` | Confirmed high-severity rule findings |

These are initial design tokens. Validate text, focus and non-text contrast in actual composited UI states before release; transparency changes effective contrast. Decorative borders are not the sole boundary cue for interactive controls.

Subsystems use subtle slate, warm grey, sage-grey or taupe tints at low opacity. Their names and stable positions identify them. Do not assign a saturated rainbow to every subsystem or use the same colour channel for subsystem identity, direction, confidence and status.

### Materials and geometry

Use faint filled shells with a thin silhouette/outline. Remove the dense triangulated wireframe and starfield from the default view. Show an outer repository shell very faintly, with stronger boundaries only around the active enclosure and its immediate context. Geometry debug wireframes remain a developer setting.

Use soft lighting and limited shading to explain depth. Disable bloom, continuous pulsing, rotating scenes and glossy/emissive clone spheres by default. Shells should not obscure their contents; fade or cut away the front of the focused enclosure when entering it.

### Typography and spacing

Use a locally packaged sans serif for interface prose and a monospace for identifiers, source and numerical details. Target 14 px body text, 12 px secondary text, 16 px panel headings and a 20 px entity title. Use an 8 px spacing rhythm, 6–8 px corner radii and restrained shadows. Source, identifiers and JSON must be selectable and copyable.

### Relationship encoding

Ordinary dependency: neutral solid curve with a target arrow/taper when selected. Runtime observation: muted sage accent plus an “Observed” badge. Expected-only link: dashed curve plus “Expected” label. Rule violation: muted amber or red plus a warning glyph and text. Inferred/ambiguous relation: dotted treatment and an uncertainty badge.

At overview scale, direction can be summarised in the inspector. Hover/selection must reveal endpoint names and a clear source → target cue. Opposing directions use separated tracks or directional markers. Animation may aid inspection on demand, but direction must remain readable while paused.

## 7. Spatial model and navigation

Implementation contract: blueprint §4 defines radius accumulation, Fibonacci initialisation, bounded collision projection, feasible fallback and numerical tolerance.

### Enclosure hierarchy

A workspace contains repository enclosures. Within each repository, physical ownership forms a canonical tree: packages/directories, files, classes, functions, methods and members as applicable. Different languages may have different depths. `depth` records tree position; `kind` records entity meaning. Do not assume “file = depth 2”.

Conceptual subsystems are a separate versioned mapping. A user may choose a conceptual enclosure view, but it must disclose overlaps or unmapped entities. Cross-cutting roles remain overlays; avoid giving a canonical entity several ownership parents merely to fit a visual grouping.

### Packing and stability

Precompute positions from stable entity identifiers and a versioned layout seed. Use tetrahedral/Fibonacci starting arrangements where useful, followed by bounded collision correction. They are initialisation strategies, not guarantees of screen-space separation.

For parent `p` and child `i`, enforce `distance(c_i,c_p) + r_i <= r_p - padding`. For sibling spheres, enforce `distance(c_i,c_j) >= r_i + r_j + gap` within a declared numerical tolerance. If the set cannot fit, enlarge/repack the parent or aggregate children; do not hide overlap behind transparency.

Radius represents navigational capacity by default, using capped/log-scaled descendant counts. The legend must disclose its meaning. A metric-based size mode is explicit. Position and Euclidean distance do not represent semantic similarity or dependency distance unless a separate named layout says so.

Keep unchanged sibling positions stable across focus changes. Filtering fades or removes objects without rerunning global physics. Repacking after source changes should move affected regions first and expose a “Reframe” action.

### Focus and camera

Single click selects and updates the inspector. Double click or Enter enters/frames the entity; a distinct control expands its contents. Drag orbits, modified drag pans, and the wheel changes camera distance. Wheel zoom alone does not silently alter the semantic selection.

Offer explicit Expand/Collapse actions and optional automatic expansion with hysteresis to avoid repeated toggling near a distance threshold. Animate focus transitions over approximately 250–450 ms; use immediate transitions when reduced motion is selected.

Provide Back/Forward, Up, Home/overview, Fit selection, reset camera and a small orientation aid. Save entity IDs and view state, not pixel coordinates alone.

### Occlusion and labels

Prioritise selected entities, ancestors, immediate children and selected relationship endpoints. Resolve label collisions in screen space and limit secondary labels. Always retain the selected label in an anchored inspector if its scene label cannot fit.

Picking ignores decorative shells unless the user deliberately selects a container. Offer a disambiguation menu for overlapping candidates; do not always select the deepest hit. Hidden or fully occluded nodes must not intercept clicks.

## 8. Focus/context and abstraction semantics

Implementation contract: blueprint §3 defines the exact revealed-branch partition, residual membership, scope atoms, binary lifting and DOI; parent shells have no duplicate membership.

Keep three independent controls: **camera zoom**, **containment detail**, and **relationship scope**. A component connected by a call may be far away in the tree; tree proximity alone cannot determine analytical relevance.

Use the Furnas-style baseline `DOI(x|y) = -(distance_T(x,y) + depth(x))`. Every ancestor of `y` has score `-depth(y)`. The product's context control uses `k = -depth(y) - 2r`, where `r` is 0, 1 or 2 for Path, Nearby or Wider. This retains the selected spine at arbitrary depth; the prototype's fixed thresholds work only for particular focus depths. These are proposed defaults based on the tree formulation in [Furnas](https://courses.ischool.berkeley.edu/i247/f05/readings/Furnas_GeneralizedFisheyeViews_CHI86.pdf).

Pin the focus and its ancestor path. “All” is subject to a declared display budget and offers a list/export of undisplayed entities. Expand required dependency endpoints separately when the user asks for callers, callees or an impact path; disclose why those nodes appear.

### Fixed levels and mixed-detail views

For fixed-depth views, project an entity to its ancestor at the requested depth, or itself if shallower. For semantic views such as Files or Subsystems, use an explicit versioned grouping map rather than a raw depth number.

Mixed-detail rendering needs a partition of underlying entities into disjoint represented groups. Ancestor shells can remain as context, but must not simultaneously count all descendants while expanded descendant groups count those same entities again. Use explicit residual groups where only some children are expanded. Map each underlying endpoint to exactly one active representative.

A summary arc `A → B` exists only when underlying evidence projects to that ordered pair. Aggregate by snapshot, grouping/view, source, target, family, relation subtype and evidence category. Preserve parallel categories; status summaries contain counts for all states. Expected-only links live in a separate overlay and are never counted as implementation witnesses.

Retain internal-edge counts and drill-down for edges whose endpoints map to the same representative. Suppressing their visible self-loop must not delete recursion, internal cycles or evidence.

## 9. Relationship routing and inspection

Implementation contract: blueprint §4 defines Method 1, clamped knots, canonical opposing/parallel lanes and EdgeLens, including the limits of geometric separation guarantees.

Use the canonical inclusion path via the least common ancestor as a routing scaffold. For each curve, supply endpoint IDs and control-point IDs/positions. Bundling strength interpolates between the endpoint chord and the hierarchical control polygon. Start at `beta = 0.8`, then tune through user evaluation; do not label one value universally optimal. This routing approach follows [Holten](https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Holten06.pdf).

Use an endpoint-interpolating clamped spline of degree `min(3, N-1)`. The default routing policy may remove the LCA control point when the original path has more than three points; retain a three-point sibling path. Treat this as a legibility policy, not a proof that curves cannot overlap. Degenerate, coincident and parallel curves need stable offsets or selectable aggregation.

Local unbundling opens individual tracks around the selected entity or bundle without changing graph membership. Overview renders aggregated bundles; selection reveals constituent directions and relation types. Count and list every constituent even if rendering uses samples.

Use depth-aware rendering, constrained transparency and a separate selected-edge pass. Sorting curves by length may help, but does not solve transparency ordering in 3D. MIN/MAX blending is an optional experiment, not a required semantic encoding or a substitute for direction markers.

## 10. Canonical data model

Implementation contract: blueprint §2 and [executable SQLite DDL](F:/uv-data/Geo_Grapher/contracts/geographer.schema.sql) define strict tables, composite foreign keys, all indexes and publication invariants. The conceptual table below remains the product-level mapping.

Use sparse typed records, not a dense `|V| × |V| × K` tensor. Tensor/matrix views may be derived for particular analyses. Store geometry separately from source facts.

| Record | Required information |
|---|---|
| Repository / snapshot | Stable repository ID, revision, working-tree digest if relevant, extraction time, schema/extractor versions, completeness and parse failures. |
| Entity | Snapshot-qualified ID, repository, sort, language, kind, qualified name, relative path, source range, parent, depth, test/generated/vendor/external flags and content hash. |
| Relationship | ID, ordered endpoints, family, subtype, resolution status and links to evidence records. Permit parallel relationships and recursion. |
| Evidence | Extractor/version, source range or trace reference, revision, collection window, method, ambiguity and any justified confidence score. |
| Documentary attachment | Document/fragment identity, source location and incidence links to discussed entities. Retain multi-entity attachments without inflating dependency degree. |
| Similarity / clone class | Algorithm/version, normalisation policy, member IDs, candidate score and verification status. |
| Conceptual model | Model/version, component mappings, rules, required/allowed/forbidden relations and open/closed-world policy. |
| Projection / witness index | Grouping definition/version, typed endpoint groups, counts and a complete pageable mapping to underlying edge IDs. |
| Analysis result | Snapshot, scope, relation filter, algorithm/version, parameters, result and limitations. |
| Layout / saved view | Layout version, entity positions/radii, view filters, pins, expansion state and camera. |

Identity must distinguish repeated names, overloads and nested definitions. Use repository namespace plus language/kind/path/qualified signature and a disambiguator where needed. Keep immutable snapshot entity IDs distinct from inferred continuity across renames. Similar bodies never erase the identities of separate source occurrences.

Dependency direction is relation-specific and documented: caller → callee; importing entity → imported entity; subclass → base. Reverse traversal is a query option. Symmetric similarity and co-change relations are explicitly symmetric and excluded from directed dependency metrics by default.

Containment, static dependencies, runtime observations, documentation, similarity and history remain separate families. Test code is retained and classified; the default production architecture view excludes it while impact/test workflows can include it. External symbols are resolved by ecosystem/package/version and qualified identity where known; unresolved names retain local scope rather than being merged globally on spelling.

## 11. Analysis and evidence rules

Implementation contract: blueprint §§5–6 specifies AST normalisation, three-round directed WL, boundary-ratio denominators, bounded helper-tree contraction and scoped Cayley degree bounds. These deterministic computations are core Stage 1–3 outputs; experimental interpretations remain subject to the safeguards below.

### Deterministic structural analysis

Compute SCCs independently for each relevant quotient and relation filter. A quotient of an acyclic graph can contain cycles; never reuse a file-level acyclicity result at subsystem level. SCC membership is canonical for a fixed graph; stable IDs can hash sorted membership. Define DAG rank explicitly, for example longest-path distance from a source SCC, and display it separately from containment depth.

Merge repositories by namespace-preserving union, retaining all original internal facts. Add genuine resolved cross-repository dependencies as separately evidenced records. Restricting a merge to an original repository and its original internal facts must reproduce those facts exactly.

Degree and coupling counts specify relation family, direction and aggregation unit. Containment size must not inflate dependency centrality.

### Clones and similarity

Verified equal normalised ASTs may share an exact-normalised-AST class, with the normalisation policy disclosed. Equal bodies are not proof of equal behaviour in different bindings or environments. Verify hash matches against canonical representations.

WL hashes and neighbourhood similarity produce candidates, not proof of isomorphism, semantic equivalence or a permutation-group orbit. Rename the interface feature “Similar and duplicated code”. Preserve original members, callers and source locations when viewing a grouped clone class.

### Architectural conformance

Separate required, allowed and forbidden dependencies. An allowed edge need not exist. An unlisted edge is a violation only under an explicit closed-world rule; otherwise classify it as unclassified/unmapped.

Evaluate conformance on mapped endpoints, with rule and model versions attached. A required relation missing from a sufficiently analysed static scope is “Missing in analysed snapshot”. A relation absent from a runtime window is “Not observed in this window”; it is not proof of dead code or missing implementation. Report extraction gaps and partial mappings alongside findings.

### Runtime evidence

Store trace counts, duration, environment, sampling and instrumentation coverage. Sum counts/rates only over compatible scopes/windows. Do not average or maximise p95 values and label the result a combined p95; retain distributions/histograms or mark that aggregate unavailable.

Coverage can show that a test executed a symbol. It does not establish the caller → callee chain. Create observed call edges from suitable call traces, not from co-execution or a missed static-reachability prediction.

### Experimental mathematics

| Proposal from reports | Final design decision |
|---|---|
| Cayley completion as architectural debt | Compute the degree lower bound in the core pipeline and show it in a collapsible Advanced Diagnostics research panel. The manuscript's bound applies to each declared connected simple undirected component. Record removed loops, collapsed parallel edges and loss of direction. `n < 2` or `m = 0` is not applicable. A lower bound is not an exact completion distance and symmetry is not established as a software quality target. |
| `boundary(S) / size(S)` as Cheeger constant | Call a value for one chosen subsystem a boundary ratio. Define incoming/outgoing/undirected and weighted/count variants. A graph-wide minimum is a different calculation; spectral estimates must identify their assumptions. Low boundary ratio alone does not establish a latency bottleneck. |
| Automatic quasi-isometric skeleton | Use “structural summary” in production. Core helper-tree contraction follows the blueprint's bounded-diameter algorithm and reports its proved undirected hop-metric constants. Other grouping, budget omission and directed reachability do not inherit that certificate. Every QI result states its metric, constants, disconnected handling and validation. |
| Group orbits / Burnside for clone removal | Reserve formal group terminology for an explicit group action and demonstrated equivalence. Hash-based clone classes are sufficient for the initial product. |
| Continuous/stochastic state-space models for execution | Treat as separate research. Runtime workflow exploration initially uses explicit observed events/transitions; control or stochastic models require independently justified variables and assumptions. |

The default inspector emphasises concrete dependency counts, cycles, source witnesses, resolution coverage and rule results. Experimental scores cannot trigger automatic refactoring recommendations without a validated relationship to the maintenance task.

## 12. Processing and technical architecture

Suggested baseline: Python extraction/analysis workers, a relational SQLite snapshot store, a typed application service, a React/TypeScript frontend and a Three.js rendering layer. Expose a separate MCP adapter over the same query services. These are implementation choices; versions and dependencies are selected and verified when implementation begins.

Pipeline:

1. Inventory files, revisions, language support and exclusions; classify tests/generated/vendor content.
2. Parse and normalise entities, ownership and source evidence. Record failures and unresolved references explicitly.
3. Resolve typed directed relationships; attach documentation and optional runtime observations without converting them into static facts.
4. Build grouping projections, witness indexes, per-view SCCs and deterministic derived metrics.
5. Precompute enclosure layout and hierarchical routing references; cache these independently of canonical facts.
6. Validate invariants and publish a completed immutable snapshot atomically.

Do not require JAX, CuPy, dense tensor decomposition or GPU graph analysis for the first release. Profile realistic inputs before adding acceleration. LCA may use binary lifting with `O(log N)` queries; do not claim constant-time lookup merely because ancestor pointers exist.

Incremental changes invalidate affected entities, relationships, projections, analyses and layout caches. Preserve the last completed snapshot during rebuild and show its revision. Do not mix old quotient counts with new witnesses. Runtime collections attach to a compatible source snapshot and disclose mapping failures.

Local camera movement stays in the client. Focus/filter requests use cancellable versioned queries; discard stale responses. Cache keys include snapshot, mapping, filters and view parameters. Avoid allocating and disposing every edge mesh on each slider movement; reuse buffers and batch/instance repeated geometry.

Repository analysis must not execute repository code by default. Render source/document text as text. Package fonts/scripts locally and keep filesystem reads within explicitly configured repository/document roots. Imported content remains data for LLM consumers as well as for the UI.

## 13. Shared query service and MCP contracts

Implementation contract: blueprint §§7–8 and [complete wire declarations](F:/uv-data/Geo_Grapher/contracts/geographer.wire.d.ts) specify all seven tools and the viewport endpoint, errors, cursors and dependency-closed token admission. They supersede the illustrative envelope below where fields differ.

Human and agent outputs share identities, snapshots, filters and witness semantics. Human output adds geometry; agent output adds task-oriented summaries and evidence handles. A user may explicitly share the current view with an agent, but independent agent queries must not be limited by camera visibility.

| Proposed operation | Inputs and result |
|---|---|
| `search_entities` | Query, repositories, kinds and limit → direct lexical/semantic candidates with identity and source. Search all indexed entities before optional scope filters; do not require a hierarchy retrieval cascade. |
| `get_architecture_context` | Snapshot, focus, grouping/context breadth, relation filters and budget → bounded structural context, evidence handles and completeness metadata. |
| `inspect_relationship_witnesses` | Snapshot, projection/relationship ID, cursor and page size → exact constituent records, provenance and further pages. |
| `get_entity_content` | Entity, snapshot, section/range and budget → source/document content with location and truncation metadata. |
| `find_dependants` | Entity, direction, families, depth/result limits → reachable entities and witness paths with unresolved-edge limitations. |
| `check_architecture` | Snapshot, conceptual model version and scope → rule findings, matches, missing expectations and unclassified mappings. |
| `find_similar_code` | Entity, algorithm/match mode and cursor → exact-normalised matches or explicitly labelled similarity candidates. |

Every result includes schema version, snapshot/revision, effective parameters, coverage limitations and pagination/completeness fields. Invalid IDs, unavailable snapshots, invalid filters, budget-too-small and incomplete builds return structured errors rather than empty success results.

Budgeting uses deterministic priority: request metadata and omissions; focus/ancestors; explicitly requested relationships or paths; relevant rule findings; then ranked additional context and witness samples. If required evidence cannot fit, return handles and an explicit incomplete result. Never silently clip a node array or omit the endpoint definitions for included relationships.

Report actual serialised token counts using the configured tokenizer where available. Otherwise label an estimate and its method. Any savings comparison names the same task, source snapshot and baseline serialisation. Token reduction is a size measure, not proof of retained reasoning quality.

Example response envelope; identifiers are illustrative and the graph arrays are intentionally empty here:

```json
{
  "schema_version": "1.0",
  "snapshot_id": "snapshot-example",
  "revision": "revision-example",
  "query": {"focus_id": "repo:example/file:a.py/function:run", "families": ["static"]},
  "nodes": [],
  "relationships": [],
  "evidence_handles": [],
  "coverage": {"status": "partial", "limitations": ["dynamic dispatch unresolved"]},
  "budget": {"limit_tokens": 2000, "used_tokens": null, "count_method": "unavailable"},
  "completeness": {"truncated": true, "omitted_nodes": 24, "omitted_relationships": 37},
  "next_cursor": "opaque-cursor-example"
}
```

Source snippets, comments and document passages must be identified as quoted repository material, not agent instructions. The architecture query tools are read-only; future edit/run tools require a separate product design and authority model.

## 14. Accessibility, failure states and persistence

All analytical workflows must be possible through the hierarchy/list, relationship table and inspector without using the canvas. Provide visible keyboard focus, labelled controls, sensible tab order, keyboard selection/expansion and announced query/loading states. Use text, icons and line styles alongside colour. Respect reduced motion and allow camera controls to be remapped or operated through buttons.

Target WCAG 2.2 AA for the interface: validate relevant text and interactive non-text contrast, keyboard access, focus visibility and target size. Validate the chosen guidance against the current standard during implementation QA. The spatial canvas requires a task-equivalent accessible view, not a claim that a WebGL scene alone is accessible.

| State | Required behaviour |
|---|---|
| No data | Explain supported inputs and offer repository/snapshot selection. |
| Building | Show stage/progress and last completed snapshot if available. |
| Partial extraction | Show affected files/languages, unresolved counts and what analyses remain meaningful. |
| No matching results | Distinguish active filters from missing/unresolved data; offer clear filters. |
| No telemetry | Show static analysis normally; mark runtime fields unavailable. |
| No conceptual model | Disable conformance claims and offer model configuration. |
| GPU/context failure | Preserve selection and filters in the list/matrix fallback; allow renderer retry. |
| Failed/stale request | Preserve prior results with their revision and provide retry. |
| Snapshot mismatch | Require an explicit compatible snapshot or disclose unmapped evidence. |

Persist panel sizes, theme, camera, pins, selected entity, filters and expansion in a saved view associated with a snapshot. Restoring a view against a new snapshot resolves stable identities where possible and lists missing entities instead of silently selecting another.

## 15. Performance targets and measurement

These are acceptance targets to validate, not measured capabilities. Record browser, hardware, viewport, build, dataset and cold/warm cache state for every run.

Initial reference workload: 50,000 entities and 150,000 typed relationships in storage, a completed local snapshot, 1440 × 900 desktop viewport, integrated-GPU-class hardware. Start with a scene budget of 500 active representatives and 2,000 aggregated curves; adapt detail rather than attempting to draw the full repository at once.

| Interaction | Target |
|---|---|
| Local orbit/pan | Aim for 60 fps; sustain at least 30 fps on the declared reference configuration. |
| Selection feedback | Visible highlight within 100 ms, independent of inspector fetch. |
| Cached focus/filter query | p95 at most 300 ms for the reference workload. |
| Initial usable overview from completed local snapshot | At most 3 seconds on the reference configuration. |
| Inspector/witness first page | p95 at most 500 ms locally. |
| Repeated navigation | No unbounded heap/GPU growth over a recorded 10-minute session. |

Reduce curve tessellation, shell detail and secondary labels before discarding analytical facts. Always show displayed/total counts. An oversized “All” request must aggregate or paginate, preserving a complete query route.

Measure extraction time separately by language and resolver. Do not infer ingestion scalability from smooth rendering of the 53-node demonstration. Output-sensitive focus selection and incremental updates must be profiled on irregular, deep and high-fan-out trees; no unconditional logarithmic guarantee is assumed.

## 16. Verification and release criteria

| ID | Acceptance condition | Evidence required |
|---|---|---|
| C1 | Direction survives import, merge, export and reload. | Hand-authored/source-derived caller and import fixtures, including opposite directions. |
| C2 | Namespace and identity remain distinct. | Repeated names, overloads, nested functions, multiple repositories and external versions. |
| C3 | Every derived implementation arc has complete witnesses. | Compare direct leaf projection against staged projection; page through and reconcile counts. |
| C4 | Mixed-detail views do not double-count entities or edges. | Expand only part of a branch; verify residual groups and internal-edge counts. |
| C5 | Relation families and evidence remain separate. | Same endpoints with imports, calls, observations, expected links and documentation. |
| C6 | SCC analysis is level-specific. | A file-level DAG whose subsystem quotient cycles; singleton recursion fixture. |
| C7 | Focus works at arbitrary depth. | Root, shallow file, deeply nested method, irregular branches; all selected ancestors retained. |
| C8 | Layout meets containment/collision constraints. | Numeric checks at high fan-out and mixed radii; visual review from several camera angles. |
| C9 | Summaries disclose omissions and fit their budgets. | Token counts, tiny budgets, stable cursors, complete endpoint references and witness recovery. |
| C10 | Claims distinguish missing from unobserved. | Partial traces, missing instrumentation, incomplete parsing and open-world rules. |
| C11 | Accessible workflows match spatial workflows. | Keyboard-only and screen-reader review for explore, connection evidence and change impact. |
| C12 | Neutral styling remains legible. | Dark/light screenshots at desktop, laptop and narrow widths; contrast checks and paused/reduced-motion states. |
| C13 | Derived outputs are reproducible. | Same source/config produces the same semantic graph and stable analysis IDs across fresh processes; layout version/seed recorded. |
| C14 | Performance meets declared targets. | Recorded results on the reference workload and configuration. |

Evaluate usefulness with task-based comparison against flat search and a conventional dependency table/graph. Include locating an implementation, explaining a cross-subsystem link, distinguishing callers from callees, investigating an impact path, finding a quotient cycle and identifying a rule violation.

Measure answer correctness, time, evidence recovery and user orientation. For LLMs, compare correctness and evidence citation under equal token budgets, not just payload size. Runtime/test evidence can corroborate static impact predictions, but coverage alone cannot certify call-path correctness.

## 17. Delivery sequence

The blueprint §9 refines this sequence into executable engineering stages: deterministic AST/WL, boundary ratios, bounded QI and degree-asymmetry computations ship in core Stages 1–3; UI/hardening is Stage 4. The following milestones retain the product delivery intent.

1. **Representation foundation:** typed snapshot store, identity, containment, directed dependencies, witnesses, search and tests C1–C6. Exit when small fixture repositories and one real repository produce trustworthy structural answers.
2. **Spatial workspace:** neutral design tokens, stable nested packing, hierarchy/inspector, navigation, HEB, depth-relative context and list fallback. Exit after C7–C8 and initial accessibility/visual review.
3. **Agent context and analysis:** shared query layer, budgeted MCP output, content expansion, impact traversal, computed SCCs, explicit clone classes and conceptual conformance. Exit after C9–C10 and human/agent answer parity checks.
4. **Release hardening:** incremental rebuilds, saved views, matrix, large datasets, failure recovery and complete accessibility/performance review. Exit after all required criteria and documented limitations.
5. **Research extensions:** runtime streaming, alternative layouts, spectral summaries, stronger metric-compression methods and exact Cayley completion/edit solvers. The deterministic scoped diagnostics in blueprint Stages 1–3 are already core. Admit additional methods only with clear assumptions and task-based evidence.

The production baseline includes the spatial explorer, evidence-backed structural queries, document attachments, computed Advanced Diagnostics and a bounded read-only MCP interface. A live telemetry feed and further experimental solvers are optional; diagnostic interpretations retain the evidence limits in Section 11.

## 18. Decision traceability and remaining choices

| Decision | Basis |
|---|---|
| Preserve nested volumetric model; neutralise palette | User's stated preference; S1–S2. |
| Separate identity, containment, direction, families and provenance | S4 findings F1–F9 and requirements R1–R8. |
| Preserve exact projected witnesses and recompute SCCs per level | S4 §§6, 8 and 10; supported conceptually by S3. |
| Use HEB and focus/context with product-specific safeguards | S5–S6; S1 implementation inspection. |
| Keep direct search alongside structural navigation | S4 §7 retrieval/representation distinction. |
| Separate runtime non-observation from architectural absence | S3's static/dynamic distinction; conservative evidence policy specified here. |
| Treat clones, QI, Cayley and bottleneck interpretations cautiously | S2–S3 proposals compared with S7–S9 definitions and scope. |
| Precompute global geometry; keep local interaction responsive | S2 original direction; bounded-view implementation proposed here. |

Baseline choices are now locked by blueprint §§1 and 9: Python 3.11+ ast/symtable/import resolution with explicitly scoped exactness; tree-sitter fallback; strict geographer.rules.yaml validated by JSON Schema; tiktoken o200k_base/cl100k_base with a disclosed conservative offline fallback; MCP stdio and pinned Streamable HTTP/SSE; and a declared reference benchmark profile/fixture plan. Initial defaults remain one local workspace, static snapshots, dark neutral styling, CPU-based analysis and optional imported runtime data. Actual machine inventory and immutable benchmark revisions must be recorded before performance measurements; none are claimed here.
