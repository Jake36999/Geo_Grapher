# Multi-graph features integrated into the original main workspace

7 November 2026. This supersedes the separate collection dashboard and the
subsequent main-page substitution. The original `App` is now the only viewer UI.

The main page remains **http://127.0.0.1:8765/**, with its original header,
repository snapshots, search, hierarchy, navigation, scope/filter controls,
3D/list/matrix buttons, inspector, evidence, investigation, diagnostics, rules,
saved views and layout-editing controls. The toolbar adds **Active graph** and
**Graphs**. Checked graphs appear through those same three representation modes;
there is no second dashboard, separate detail page or iframe.

Selecting a foreign list/matrix/spatial item activates its graph and carries its
original snapshot, canonical records and quotient/witness context into the
existing inspector. The active view mode, visual settings and camera are retained
across this activation. Search/hierarchy/coverage remain scoped to the active
graph. Source namespaces, statistics and evidence remain independent; the joint
render collections are not an analysis graph. Matrix cells between distinct graph
views do not invent dependencies. Declared bridges remain a separate overlay.

Existing main controls apply context radius, abstraction and relationship filters
to foreign frames. The active graph's repository-ID filter is not applied to a
different graph. Loading blocks edits against geometry that is about to change.
Scoped render addresses still include graph/snapshot/local ID. Saved views remain
graph scoped, preserve the original ToolSet storage key, and additionally restore
checked graph IDs/order. Physical merge review remains available inside Graphs.

ToolSet's existing database is registered in the catalogue without re-extraction,
copying its facts or changing its original entity/repository IDs. The registered
route shares the original service (rules, handles and query state), with borrowed
store lifetime managed separately. This makes ToolSet selectable alongside the
other three existing registrations. It does not merge them or ingest new sources.

Old `/legacy/`, `/collection/` and graph-specific HTML URLs redirect into the same
root UI; graph-specific API paths remain functional. Original ToolSet `/api/v1`,
`/api/v1.1` and MCP contracts remain intact. Graph MCP remains `/graph-hub/mcp`.
The unused collection/tile components have been removed.

## Verification

- **149 backend tests passed** across the main service, graph routing, store
  registration, graph composition/merge, geometry, original snapshot publication,
  project/paper isolation, transport and actor contracts.
- **12 Playwright checks passed**, including original-shell preservation,
  joint list/matrix/spatial views, correct inspector graph activation, main
  filters reaching foreign graph requests, graph selection/centring, saved views,
  graph-scoped search, merge review, legacy links, spline transforms and actual
  rim/group editing. The tested full application accessibility scan and the
  light-theme editing region had zero axe violations.
- **Production TypeScript/Vite build passed.**
- **Live main-page check passed** with ToolSet and the three other registrations,
  original hierarchy/inspector visible, no iframe, same-page representation
  switching, and zero JavaScript page errors.
- The supplied Librarian scenario still reproduces **362 nodes / 257 curves**
  in the integrated page, with compact 3D packing (span ratio **1.74**).

Evidence: `output/integrated-workspace/tests.xml`, `browser-results.json`,
`live-browser.json`, `live-main.png`, `live-matrix.png`, and the retained
`output/spatial-controls/live-reproduction.json`.

```powershell
$env:PYTHONPATH='F:/uv-data/Geo_Grapher/src;F:/uv-data/Geo_Grapher'
./output/wheel-env/Scripts/python.exe -m geographer serve --database output/toolset.sqlite --catalog output/named-graphs/catalog.sqlite --transport http --port 8765
npx playwright test --config playwright.graphs.config.cjs
node scripts/qa-main-workspace.cjs
node scripts/qa-spatial-controls.cjs
```

No paid trials, application execution or large re-ingestion was performed. This
is focused implementation/regression evidence, not a full release/AT or target
hardware acceptance study. Existing test-client/bundle-size advisories remain.
