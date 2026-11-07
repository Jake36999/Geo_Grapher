# Spatial manipulation and unified graph navigation — 7 November 2026

All four requested changes are implemented in the shared workspace and the
reusable spatial panel. The graph data, scopes and source ownership are preserved.

## User controls

1. Hold the visible rim of a bubble. Drag to move its visible subtree in the
   camera-facing plane; wheel while holding to enlarge/shrink it. Unheld wheel
   input still zooms the camera.
2. Use Shift-drag, or enable **Box select** and drag, to draw a selection rectangle.
   Drag inside the dashed selection bounds to move the selected roots together.
   Held wheel input or **Size + / Size −** scales the group about its common centre.
   Arrow buttons move it with keyboard access. Escape cancels an active gesture
   or clears selection. **Reset layout** restores automatic packing.
3. The main collection opens **one shared canvas**, with a checkbox graph picker
   above it. Dedicated graph panels are optional. The first selected graph is
   central; five more use successive hexagonal neighbours. Further selections
   complete ring one and ring two, up to 19. **Centre** chooses a different central
   graph. Selection and order persist, including an intentionally empty selection.
4. Documentary bubble sizing uses represented line count as a bounded content
   proxy. High-fanout layouts use compact 3D shelves instead of the old long line.

Manual transforms are presentation state for the current view, not edits to the
canonical graph or persisted saved-view layout records. A parent selection applies
once to its descendants; selecting parent and child does not double-transform it.
Newly revealed children inherit their edited ancestor. Scaling is uniformly clamped
to 0.1–10 times the automatic radius. Manual moves can override automatic spatial
separation; reset restores the validated layout.

Curves follow edited endpoints. Shared endpoint transforms apply exactly to all
controls; differing transforms rebuild the chord/frame while retaining transverse
shape. Parallel/opposing track spacing remains positive. Declared bridges remain
a separate display layer and follow their root anchors. Render IDs stay qualified
by graph and snapshot; moving or overlapping bubbles does not mix query scopes.

## Screenshot issue reproduced and fixed

The live Librarian snapshot was opened at **src / Directories / All uncertainty /
Wider**, reproducing **362 displayed nodes and 257 curves**, matching the supplied
screenshot counts. Its representatives now span approximately **17.68 × 17.68 ×
30.69** units (longest/shortest span ratio **1.74**), rather than a near-1D chain.
No nodes or curves were removed to obtain the compact result.

This exposed a camera issue as well: fitting the tiny canonical `src` container
could put the camera inside large neighbouring representatives. Grouped modes
now fit the displayed groups, and hidden virtual workspace spheres no longer
inflate shared-scene framing. Toolbar/legend positioning responds to wrapped
controls; duplicate bottom instructions were removed.

For a separate deterministic fixture of 362 unit-radius siblings, compact fallback
has enclosing radius **13.51**, versus **398.45** for the old line helper. Packing
still checks 1e-4 containment and sibling separation. Documentary content sizing
changes neither dependency degree nor the subject graph.

![Librarian directory view after remediation](../output/spatial-controls/librarian-directories.png)

## Executed verification

| Check | Result | Evidence |
|---|---|---|
| Backend regression selection | **142 passed**, zero failures | `output/spatial-controls/tests.xml` |
| Dedicated Playwright suite | **10 passed**: two pure geometry/transform cases and eight browser flows | `output/spatial-controls/browser-results.json` |
| Shared dark / standalone light accessibility regions | Zero axe violations in tested regions | Playwright cases 2 and 10 |
| TypeScript and production build | Passed | `npm run build` |
| Real Librarian screenshot reproduction | Passed, 362 nodes / 257 curves / no page errors | `output/spatial-controls/live-reproduction.json` |
| Live graph composition and scoped searches | Passed on the existing three registered graphs | `output/spatial-controls/live-composition.json` |

Browser coverage includes actual rim pointer capture, held-wheel sizing, dragging,
Escape rollback, rectangular group selection, group wheel/drag and keyboard edits,
reset, single-canvas defaults, empty checkbox persistence, choosing the central
graph, standalone editing and existing merge/transport/UI behavior. Backend
coverage includes compact/variable-radius packing, six-graph separation, hex-ring
distances, documentary sizing without dependency changes, and prior graph/paper
isolation and publication tests.

The three live registrations were discovered from the existing catalog. The paper
corpus registration was added separately; this work did not ingest or merge it.
The preview was refreshed at [the local workspace](http://127.0.0.1:8774/collection/).
Other local server ports were left alone. Live screenshots are
`output/spatial-controls/shared-desktop.png` and `shared-1006.png`.

Reproduce the feature checks using:

```powershell
$env:PYTHONPATH='F:/uv-data/Geo_Grapher/src;F:/uv-data/Geo_Grapher'
./output/wheel-env/Scripts/python.exe -m pytest tests/test_spatial_interactions.py tests/test_graph_merge_composition.py tests/test_graph_catalog.py tests/test_project_isolation.py tests/test_stage4_geometry.py tests/test_paper_pipeline.py tests/test_paper_followup.py tests/test_stage1_store.py tests/test_stage3_transports.py tests/test_phase5_actor.py -q --junitxml=output/spatial-controls/tests.xml
npm run build
npx playwright test --config playwright.graphs.config.cjs
node scripts/qa-spatial-controls.cjs
node scripts/qa-independent-graphs.cjs
```

The live smoke scripts expect the named pilot registrations and read existing
snapshots; their API calls may populate derived query/layout caches. They do not
change original source facts. No paid inference, target application execution,
large repository ingestion, full release soak or human assistive-technology study
was run. The existing bundle-size advisory/test-client deprecation remains.

The maintained engineering description is
[workspace specification baseline 3](../GRAPH_WORKSPACE_SPECIFICATION.md), with
the additive [workspace contract](../contracts/graph-workspace.d.ts).
