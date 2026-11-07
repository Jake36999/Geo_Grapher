# Independent project graphs and composed workspaces — baseline 4

This is the project-level storage/routing boundary agreed on 7 November 2026.
The existing v1.1 code-query contracts remain the inner query protocol.

## Main page and original client compatibility

The original workspace is served at `http://127.0.0.1:8765/`, with graph selection
integrated into its existing header and 3D/list/matrix controls. Its navigation,
filters, search, hierarchy, inspector, diagnostics and saved views remain there.
Start the combined service
with `serve --database output/toolset.sqlite --catalog
output/named-graphs/catalog.sqlite --transport http --port 8765`.
`/collection/` is an alias redirect to `/`, retaining query parameters.

The original ToolSet API and `/mcp` (including its v1.1 route) retain their
single-store contracts. `/legacy/`, `/collection/` and graph-specific HTML URLs
redirect to the main page; they are not separate UIs. Graph-scoped APIs stay at
`/api/graphs` and `/graphs/{graph_id}/`; their MCP endpoint is
`/graph-hub/mcp`. Both MCP session lifecycles run in the same main service.
The former standalone 8774 viewer is retired in the current local deployment.
An optional `serve-graphs --ui-origin` compatibility listener can redirect its
viewer while retaining API/MCP clients, but is not required or running here.

The main database is registered as an existing store using its published snapshot,
original repository namespaces and original entity IDs. Registration changes only
catalog metadata, with no source re-ingestion or physical merge. The main service
is shared with its graph route so configured rules, handles and query state remain
consistent. Router shutdown does not close a borrowed caller-owned store.

**Active graph** scopes search, hierarchy, inspector and coverage. **Graphs**
selects the display set for all three existing representations. Selecting a
foreign node/relationship activates its graph and passes its original snapshot,
source records and view/witness context to the existing inspector. Renderers use
qualified display IDs. Cross-graph matrix cells do not invent dependencies;
declared bridges never enter dependency cells or source degree. The combined
display does not create a synthetic analysis/snapshot envelope.

Context breadth, grouping, relation filters, theme, bundling and lens controls
remain the existing main controls. Foreign frames receive the applicable filter
and grouping, without inheriting another graph's repository-ID filter. View mode
and visual settings stay stable when the active graph changes. Source focus is
remembered per graph and immutable snapshot. Saved views remain project scoped
and additionally restore `graph_ids`; the original main project's storage key
is preserved. Loading a new display set prevents edits against stale geometry.

## Storage and identity

One resolved project root owns one `graph_id`, an independent canonical SQLite
snapshot store, and optionally an independent paper-corpus SQLite database.
`GraphCatalog` contains registrations, overlap decisions and declared bridges;
it does not contain a union of project entities/concepts or a global search index.

The initial identity is `g_` plus the first 24 hexadecimal characters of
`digest(normcase(resolve(root_path)))`. Identity collisions are rejected before
touching an occupied store. Source graph IDs namespace canonical repository IDs.
A local address is always interpreted with its graph and version:

```typescript
type CodeAddress = { graph_id: string; snapshot_id: string; entity_id: string };
type PaperAddress = { graph_id: string; corpus_revision: string; local_id: string };
```

Moving a root currently requires a separately reviewed registration/migration;
path-derived identity is not a claim of Git/project equivalence. Historical
combined snapshots remain intact and are not silently converted.

Each graph computes its own lexical/FTS statistics, alias materializations,
SCC/WL diagnostics, contractions, cursor plans and HMAC handles. Adding a separate
graph must not alter an existing graph's results. Tests exercise this property
for code search and paper retrieval; it is not a proof of every LLM inference.

## Agent contract

The scoped hub exposes `geographer://graphs` and `list_graphs` for discovery.
Code operations retain their v1.1 request/response schemas inside this wrapper:

```typescript
interface ScopedRequest<T> { graph_id: string; request: T }
interface ScopedCodeResponse<T> {
  graph_id: string;
  result: T;
  routing_budget: { limit_tokens: number; used_tokens: number };
}
interface ScopedPaperResponse<T> { graph_id: string; result: T }
interface GraphError {
  graph_id?: string;
  error: { code: 'INVALID_GRAPH_REQUEST' | 'GRAPH_BUDGET_TOO_SMALL' | 'GRAPH_UNAVAILABLE'; message: string };
}
```

Actual tool request JSON Schemas are served by MCP `tools/list`, using the
approved inner schemas. `graph_id` is required; no wildcard/all-graph/default
fallback exists on the hub. A snapshot from another store or an alias/handle
from another graph cannot resolve through the selected graph's service. Store
ownership is checked before opening it for queries. A catalog path cannot
silently initialize graph-catalog tables inside an existing project database.

Code tools keep their existing names. Optional paper tools are prefixed
`paper_` (`paper_search_documents`, `paper_get_document`, etc.) and require a
corpus attached to that graph. The source-checkout paper extension is optional;
the scoped code server uses pinned MCP 1.30.0. Paper databases may not be shared
between graph registrations, including aliases of the same physical file.
Context-local routing prevents concurrent requests from changing a process-global
paper database path. Existing standalone servers retain their configured single
store for compatibility; they are not an all-graph hub.

Code-response token caps include the graph wrapper. Paper requests retain their
documented row/character bounds; no exact paper-envelope token guarantee is added
implicitly. Source assertions remain untrusted data and are not tool instructions.

## Deliberate federation

`federated_search` requires 2–8 distinct `graph_ids`, a query, optional search mode,
and a 2,048–32,768 `limit_tokens` cap. It currently compares canonical code/document
search results. Each graph is searched independently with a bounded allocation:

```typescript
interface FederatedSearch {
  graph_ids: string[];
  query: string;
  mode?: 'lexical' | 'documentation' | 'hybrid';
  limit_tokens?: number;
}
interface FederatedResults {
  graph_ids: string[];
  results: ScopedCodeResponse<unknown>[];
  omitted: { graph_id: string; reason: 'full_graph_envelope_omitted_by_budget' }[];
  ranking: 'independent_per_graph_no_global_rank';
  tokenizer: 'o200k_base';
  used_tokens: number;
}
```

There is no global BM25/RRF normalization and no graph union. Packing retains or
omits a whole valid graph envelope, preserving node/relationship endpoint closure.
The final serialized response is counted exactly, including omission metadata.
When over budget, the largest envelope is omitted first (ties: the later one), so
the outcome does not depend on argument order. An inner query error remains
explicit; a graph whose store cannot be opened yields its own `GRAPH_UNAVAILABLE`
entry while the other graphs' results are kept. Missing results are not fabricated.
Cross-graph similarity/impact/conformance and paper-specific federation are not
implemented as automatic traversals. Agents can make separate explicitly scoped
queries and keep their origins attached.

## Root collisions and bridge decisions

`plan-graph` / `GraphCatalog.plan_root` identifies exact root reuse, a new root
inside an existing root, and a new root containing an existing graph root.
Resolve/case normalization handles physical path aliases before comparison.
An overlapping import without a recorded/explicit decision stops before importing
that graph and returns `COLLISION_REVIEW_REQUIRED`, the paths/relations, a plan
digest and choices. `expected_plan` rejects stale decisions. Registrations reserve
the catalog writer transaction while committing the new head/decision.

Supported choices are:

- `keep_separate`: independent stores, aliases and retrieval statistics; no bridge.
- `child_module`: independent stores plus an operator-declared root/module bridge.

An exact re-import can reuse its existing graph/snapshot. Source changes publish
a new immutable snapshot. Physical merging is a separate reviewed operation,
described below. No graph
is automatically merged because its root is nested, its concepts match, or it
contains the same DOI/title. Source copies in overlapping roots can remain in
both independent stores; this baseline is not exclusive filesystem ownership or
an automatic extraction of a child subtree from historical parent snapshots.
Batch CLI imports commit per project and report any graphs completed before a
later collision; they are not an atomic multi-store migration.

Bridge records have scoped source/target graph IDs and local references, kind
(`child_module`, `reference`, `concept_equivalence`, `document_identity`), rationale,
operator-supplied evidence JSON and creation time. They are assertions, not
resolver-verified equivalence or runtime facts. `list_bridges(graph_ids)` only
returns bridges whose two endpoints were selected. Bridge display/lookup never
changes aliases, degrees, shortest paths, IDF or similarity in either graph.

## Alias policy

“Universal” aliases are reusable reviewed policy templates, not global concept
identities. Each graph materializes its own policy. A domain-local policy can be
applied with `pipeline.maintain refresh --alias-policy PATH`, using the required
backup and existing validation. Matching strings in different graphs remain
homonyms by default; a bridge requires an explicit assertion with provenance.
Sharing an original source does not make two projects' interpretations identical.
Embedding/LLM proposals never merge nodes automatically. No paid confirmation
or embedding inference is part of this implementation.

## Display composition

The original main workspace renders up to nineteen independent detailed clusters
in its spatial view, with synchronized list and matrix views. There are no tiled
or iframe applications. Each graph API request is bound by
`/graphs/{graph_id}/`, an API scope rather than another viewer. Saved views
are namespaced by graph. `POST /api/graphs/frame` requests 1–19 explicitly selected
graph frames. Each graph computes its own mixed-detail partition, quotient and
geometry, with a maximum of 120 nodes / 200 curves and a 32,768-token inner frame
cap. Incomplete frames expose their omitted counts. A failed graph returns a
per-frame error while healthy frames remain available. Unknown graph IDs reject
the whole request before any frame queries.

Selection order defines placement. The first graph occupies `(0,0,0)` and the
next five occupy successive hexagonal neighbours. A seventh closes the first
hexagonal ring; additional graphs occupy ring two. Axial coordinates `(q,r)` map
to `(7(q+r/2),0,7 sqrt(3)r/2)`. Rings start at `(k,0)` and take k steps in each
direction `(0,-1),(-1,0),(-1,1),(0,1),(1,0),(1,-1)`.
Each local workspace sphere is uniformly scaled to radius 2.5, with a minimum
gap of 2 between automatic graph enclosures. Control points, centres, sphere radii and lane spacing use the same
uniform transform. Unit normal/binormal vectors and knot parameters are unchanged.
Spline evaluation therefore commutes with this transform, including lane offsets.
Position is a display choice; equal enclosure radii are not equal graph size or
semantic similarity.

GPU IDs are JSON tuples `[graph_id,snapshot_id,kind,local_id]`, with an external
mapping back to scoped origin addresses. Flattened renderer collections are
**not** a query envelope or analysis graph. Picking cannot send a render ID to a
canonical query. Double-click and keyboard selectors focus a graph locally;
Path/Nearby/Wider, fit-all, per-graph reset and selection metadata are available.
Source focus state is keyed by graph **and snapshot**, and aborted/stale fetches
cannot replace a newer composition. The original main controls provide 3D/list/matrix access.
Graph checkboxes persist the selected order, including a deliberately empty
selection. A graph card's **Centre** action moves it to the initial slot without
changing its identity. There is no implicit all-graph agent query when the UI shows many graphs.

### Direct layout editing and content sizing

Every spatial panel supports holding a visible sphere rim to drag it in the
camera-facing plane. While held, mouse-wheel movement scales that selection.
Without a held layout gesture, wheel input retains camera zoom. Shift-drag or
the **Box select** toolbar mode creates a rectangular selection of visible
representatives. Dragging inside its dashed bounds moves the selection; held
wheel input or **Size + / Size −** scales it around its shared bounds centre.
Arrow buttons provide keyboard movement. Escape cancels the current gesture or clears selection;
**Reset layout** clears manual edits. Ordinary unmodified drags still orbit.

Selections reduce to roots so choosing a parent and its child never applies an
edit twice. Containment descendants receive the same affine transform; newly
revealed descendants inherit their nearest edited ancestor. Scaling is uniformly
clamped so each node remains within 0.1–10 times its automatic radius. Display
edits do not change source ownership, evidence, metrics or graph membership.
They are session/view presentation state, not persisted in saved-view records.
Manual moves can override automatic spatial separation/containment; Reset layout
restores the verified packed positions.
Grouped abstraction modes fit the displayed scene rather than zooming into a
small canonical focus container surrounded by unrelated displayed representatives.
Hidden virtual workspace spheres do not influence shared-scene camera framing.

For an affine endpoint transform shared by both ends of a curve, all controls
and lane spacing receive that transform exactly. For different endpoint edits,
controls preserve their transverse deviation from the old chord, scaled by the
mean endpoint scale, around the new chord. The normal/binormal frame is rebuilt.
Endpoints therefore remain exact and relation tracks remain separated. Declared
bridge endpoints follow their display root anchors in a separate overlay.

The primary bounded Fibonacci/projection solver is retained. On work-limit
exhaustion it now uses **compact-content-v2** radius-aware 3D shelves rather than
the old one-dimensional line. Diameters include `gap+0.01` clearance; rows/layers
advance by their maximum padded diameter. A deterministic transverse stagger
of at most 0.001 avoids collinearity in small/uneven fallback sets, while the
clearance preserves separation. The enclosing radius is recomputed exactly and
validated to 1e-4. The legacy line helper remains available for compatibility;
the workspace no longer chooses it as the packing fallback.

Collapsed code groups retain capped logarithmic membership sizing. Documentary
nodes additionally use `max(leaf_count, 1+floor(max(0,end_line-start_line)/12))`
as their display-content count. Terminal containers with counts above one use
`1+0.35 ln(1+min(count,10000))` for radius. This is an explicit content proxy,
not dependency degree or scientific importance. Layout cache keys/seeds include
the new geometry policy so old line arrangements are not reused.

Declared bridges are a separate dashed amber display layer, with rationale/evidence
available below. No bridges are inferred from proximity. Selection controls and
standalone links provide keyboard access independently of WebGL. This first
workspace iteration is not a multi-tenant authorization boundary or a target
hardware/memory release acceptance result.

## Operations

```powershell
python -m geographer ingest-graphs --manifest profile.json --catalog output/graphs/catalog.sqlite --report ingestion.json
python -m geographer plan-graph --catalog output/graphs/catalog.sqlite --root D:/Project/component
# After an explicit overlap decision:
python -m geographer ingest-graphs --manifest component.json --catalog output/graphs/catalog.sqlite --on-overlap keep_separate
python -m geographer attach-graph-papers --catalog output/graphs/catalog.sqlite --graph-id g_ID --database PROJECT_PAPERS.sqlite
python -m geographer serve-graphs --catalog output/graphs/catalog.sqlite --transport http --port 8774
python -m geographer serve-graphs --catalog output/graphs/catalog.sqlite --transport stdio
```

Profiles use the existing version-1 repository selection format. The new command
imports each entry separately and does not share `resolution_group` across stores.
Use the pinned project environment. The prior `ingest-workspace` remains available
for deliberately combined/legacy analysis and is no longer the recommended
default for unrelated projects. Root imports currently use the CLI/library; a
graph-import/collision wizard is not implemented. Physical merge review and
execution are available in the main **Graphs** menu and CLI below.

## Reviewed physical merge

`contracts/graph-workspace.d.ts` specifies the additive workspace envelopes.
`POST /api/graphs/merge/plan` accepts 2–8 distinct graph IDs and a destination label
of 1–120 characters. A deterministic plan pins published source heads, namespace
ownership, paper corpus revisions and digests of original paper/provenance/
annotation rows. The destination is `g_` + the first 24 hex characters of
`digest('derived-merge-v1', sorted(source_graph_ids), trimmed_label)`.

`POST /api/graphs/merge/execute` requires that plan's digest. The UI presents the
source list and preservation/semantic policies, with a review acknowledgement
before execution. Source changes, unreviewed plans and overlapping repository
namespaces are rejected (HTTP409). There is no automatic filesystem/root merge.
The equivalent CLI workflow is:

```powershell
python -m geographer plan-graph-merge --catalog CATALOG.sqlite --graph-id g_A --graph-id g_B --label "Related modules" --report plan.json
python -m geographer merge-graphs --catalog CATALOG.sqlite --graph-id g_A --graph-id g_B --label "Related modules" --plan-id REVIEWED_DIGEST --report receipt.json
```

Execution creates a new derived graph: source registrations, original snapshots,
paper databases and project files remain intact. Canonical entity/repository IDs,
typed parallel relationships, evidence, documentary incidences and source analysis
records survive. The virtual workspace is unified and binary lifting rebuilt.
WL, boundary/Cayley diagnostics, helper contractions and standard quotient views
are recomputed through Stage 3. Source-local cursor plans/handles/layouts are not
reused, and no cross-project imports or synonym equivalences are invented.

Attached paper corpora are physically copied into a new corpus with remapped
integer IDs. Document paths and concept keys are origin-namespaced. Matching
DOIs/titles and homonyms from different origins remain separate. Source-reviewed
concept equivalences, exclusions and nonidentity relations survive within their
origin. Original documents, sections, claims, manifests/page provenance and
annotation archives are retained. Document/concept/annotation origins are explicit;
archived annotation records and their original record hashes remain unchanged.
Read tables and FTS are rebuilt with a persisted origin-scoped alias policy;
query caches and embedding indexes are not copied or recomputed.

Each plan writes separate `code-PLAN.sqlite` and optional `papers-PLAN.sqlite`
generation files. Publication validates the code snapshot and paper foreign keys/
integrity, then rechecks source heads/revisions in the catalog writer transaction.
Only then does the catalog head switch and an immutable merge receipt register.
An interrupted/stale build is not registered and cannot change a previous live
destination. Unregistered files are retained for inspection/retry; this is not
automatic cleanup or a distributed transaction across source stores. An identical
current plan is idempotent. Subsequent approved plans retain prior generation
files; live UI discovery exposes the current destination generation. In-flight
requests may finish against their pinned previous generation.

Long building work does not hold the catalog routing lock. Cached services and
mounted child applications are keyed by graph plus generation path. Derived
graphs declare their owner repository namespaces; ordinary graphs retain the
single-owner check. Merging intentionally computes read statistics within the
new destination, without changing any source graph's retrieval statistics.

For the current source checkout (the earlier installed wheel is not this build):

```powershell
$env:PYTHONPATH='F:/uv-data/Geo_Grapher/src;F:/uv-data/Geo_Grapher'
& 'F:/uv-data/Geo_Grapher/output/wheel-env/Scripts/python.exe' -m geographer serve-graphs --catalog F:/uv-data/Geo_Grapher/output/named-graphs/catalog.sqlite --port 8774
```

The demonstrated preview already occupies that port; do not start a second
listener there. Connect the test harness to its `/mcp` endpoint. The pilot's paper
corpora are deliberately unattached, so use the existing configured paper service
for those trials until project ownership is explicitly assigned.
