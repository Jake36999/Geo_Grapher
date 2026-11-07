# Physical graph merge and shared detailed scene — 7 November 2026

Implemented both previously deferred capabilities. The unrelated Librarian and
Timeline samples remain separate; physical merge execution was tested only on
disposable synthetic graphs/corpora.

## Delivered behavior

- **Reviewed physical merge:** UI plan/review/acknowledgement/execute workflow,
  matching CLI commands and local HTTP endpoints. Plans pin published source
  heads, namespace ownership, paper revisions and original-row digests. Stale
  plans, destination identity collisions and overlapping namespaces are rejected.
- **Preservation and publication:** a new destination retains canonical code
  IDs, original facts/evidence, documentary trees and declarations. LCA, WL,
  boundary/Cayley analysis, helper contraction and standard quotient views are
  rebuilt through Stage 3. Each generation has separate database files; catalog
  registration/head switching follows validation and source revalidation.
  Original graphs are retained. Receipts are protected by immutable SQL triggers.
  Failed generations cannot add snapshots to the previous live destination.
- **Paper union:** original rows are copied with remapped local IDs, manifests,
  page provenance, source-reviewed aliases/nonidentity links and annotation
  archives. Document and concept origins are explicit. Equal titles/DOIs and
  homonymous concepts remain distinct across source origins. FTS/read tables are
  rebuilt with a persisted origin-scoped policy. Archived source rows and their
  record hashes remain unchanged. Query caches/vectors are not copied.
- **Shared scene:** up to four independent detailed viewport frames in one
  Three.js canvas, with stable disjoint transforms, graph/snapshot-qualified
  render addresses, per-graph focus and reset, Path/Nearby/Wider, fit-all,
  hover/picking and scope-labelled selection. Existing clamped spline/lane
  geometry is reused. Declared bridges are a separate dashed amber layer,
  capped at 100 displayed links, and never enter dependency metrics.
- **Accessible alternatives:** labelled per-graph focus controls and dedicated
  graph panes preserve keyboard access to the existing hierarchy/list/matrix.
  Partial frame failures leave healthy graph detail available.
- **Loading fix:** search controls wait for snapshot bootstrap. A real delayed
  bootstrap test proves early input cannot be silently cleared during loading.

Specification: [workspace baseline 2](../GRAPH_WORKSPACE_SPECIFICATION.md).
Additive declarations: [workspace contract](../contracts/graph-workspace.d.ts).
Approved v1.0/v1.1 inner query contracts remain unchanged.

## Executed verification

| Check | Result | Evidence |
|---|---|---|
| Backend regression selection | **133 passed**, zero failures | `output/graph-merge/tests.xml` |
| Dedicated Playwright suite | **5 passed**, zero flaky/skipped tests | `output/graph-merge/browser-results.json` |
| Accessibility | Zero axe violations in the tested shared-scene region | Browser test `shared detail stays graph scoped…` |
| TypeScript / production frontend | `npm run build` passed | Current `frontend/dist` |
| Real two-project browser smoke | Passed; zero page errors | `output/graph-merge/pilot-browser.json` |
| Desktop / 1006×884 layouts | Inspected screenshots | `output/graph-merge/pilot-desktop.png`, `pilot-1006.png` |

Backend coverage includes source-fact noninterference, idempotence, stale plans,
source changes during building, rejected identity/namespace collisions, paper
homonyms/duplicate-title separation, original archive grounding, CLI execution,
generation refresh in cached/mounted services, corrupt-graph fault isolation and
relationship endpoint closure. Browser checks cover transformed spline/lane
equivalence and collision-free render addresses, local focus, bridge visibility,
review acknowledgement, rejected stale execution, successful destination creation,
responsive controls and snapshot-loading behavior.

The live smoke expanded `src.resource_librarian` through the shared keyboard
focus control while Timeline remained independently scoped:

| Graph | Visible records | Dependency curves | Scene-budget omissions |
|---|---:|---:|---|
| Librarian bounded sample | 17 | 2 | 0 spheres / 0 curves |
| Timeline bounded sample | 8 | 0 | 0 spheres / 0 curves |

Timeline is documentary-only in this sample, so zero dependency curves is
expected. These are **bounded previous samples**, not complete project ingestions
or a claim that every source relationship is visible under the exact-only filter.

The refreshed preview is [the local collection](http://127.0.0.1:8774/collection/).
Only its verified graph-hub process was replaced; other local listeners were
left alone. The live catalog still has the original two independent graphs.

## Reproduction

```powershell
$env:PYTHONPATH='F:/uv-data/Geo_Grapher/src;F:/uv-data/Geo_Grapher'
./output/wheel-env/Scripts/python.exe -m pytest tests/test_graph_merge_composition.py tests/test_graph_catalog.py tests/test_project_isolation.py tests/test_paper_pipeline.py tests/test_paper_followup.py tests/test_stage1_store.py tests/test_stage4_geometry.py tests/test_stage3_transports.py tests/test_phase5_actor.py -q --junitxml=output/graph-merge/tests.xml
npm run build
npx playwright test --config playwright.graphs.config.cjs
node scripts/qa-independent-graphs.cjs
```

The Playwright suite owns a temporary fixture/catalog on port 8775. The last
command is a read-only smoke of the existing bounded preview on port 8774 and
expects its two named pilot graphs. It is not a generic catalog acceptance test.

## Practical boundaries

Merging is a namespace-preserving fact union. It does not re-resolve imports
across projects, create new concept equivalences, infer bridges or rewrite original
project files. Intentional comparison inside the derived graph uses that new
graph's statistics; original retrieval statistics remain local. Its current
generation is exposed in live discovery; prior generation files and receipts
remain retained. Unregistered interrupted files are retained for inspection/retry,
without automatic cleanup. This local workspace is not multi-tenant authorization.

No full four-project ingestion, paid model trials, new extraction/embedding calls,
target application execution or large soak/performance study was performed.
The existing Three.js bundle-size advisory and Starlette test-client deprecation
remain; neither caused a failed build/test. The old full-browser release suite
was not rerun in this pass. These results cover the scoped feature regression,
not final product-wide release acceptance.
