# P5.3 — spatial workspace and shared investigation

6 November 2026. P5.3 implementation is complete for the approved workspace and backend scope. Runtime collection ingestion/selection remains P5.4; comparative model/human evaluation remains P5.5 or external release acceptance. The original engineering documents and four original contracts are unchanged.

## Implemented behavior

- All workspace frames use the v1.1 service. Path/Nearby/Wider breadth and mixed, repository, directory, file, class, atomic and conceptual grouping are selectable. Conceptual groups retain Unmapped. Canonical ownership remains T+; view-local display trees and geometry do not reparent facts or insert synthetic layout entity IDs.
- Grouped scene admission retains focused code before shallow unindexed external placeholders. v1.1 packing delivers connected bundles before unrelated spheres, including available enclosure paths. Full partitions/witnesses remain stored even when scene budgets omit groups. This fixes a real-repository first-page case that otherwise showed many placeholders and no connected code.
- Subtype and static-family filters, bidirectional impact and original witness-path projection are exposed. Incoming traversal keeps original arrows. Highlighted paths have accessible lists and disclose collapsed/internal or out-of-scope steps. Pins and saved grouping/model/breadth state survive restore; legacy saved views migrate defaults.
- Rules can be pasted or uploaded, validated against the snapshot, and selected by digest without rebuilding it. Invalid or overlapping models preserve the prior selection. Up to 32 model versions, including predecessor CLI-loaded models, persist for restart/saved-view recovery. Browser requests cannot select arbitrary server paths.
- Curves have batched vertex colours, a source-to-target ramp, dotted uncertainty, expected-only dashes and subtype patterns. Positive exact forbidden witnesses are warning amber; criticality is not invented. Hover highlights curves/endpoints and presents ordered text without changing locked Inspector selection or querying content. Matrix/Inspector provide textual equivalents.
- Inspector shows source-derived signatures/gists, group exemplars and witness previews. Investigate exposes exact folded source, omitted ranges, sibling stubs, documentary ancestry, syntax-only process cards, bounded call bridges, reason-coded triage and versioned review annotations. Search intent exposes local documentary/hybrid retrieval. Agent JSON defaults to the raw compact counted v1.1 envelope; v1.0 compatibility remains available.
- The same `process-evidence-v1` content is served over HTTP/MCP. Optional architecture `review_queue` uses the same occurrence-grouped triage engine as the workspace and includes subject/alternative definitions under final-envelope counting. Accepted annotations remain reviewed assertions, never upgraded dependency facts.

The [workspace addendum](../contracts/v1.1/WORKSPACE_ADDENDUM.md) records wire additions, explicit UI-action shapes, retention, source/claim limits, empty-family semantics, alias adaptation and artifact lifecycles. No additional MCP mutation tool or canonical schema migration was added.

## Verification

The final backend run passes **141 tests**, including all original Stage 1–4 and P5.0–P5.2 fixtures. New tests cover every grouping's partition/witness/containment invariants, model reload rollback and restart recovery, overlay decision replay and stale snapshot rejection, source/document reference closure, deterministic triage, shared actor queue budgets, positive-only warning classification, original path projection, filter-stable geometry and external-placeholder admission. HTTP/SSE tests compare shared process content with the identical HTTP response; stdio and strict v1 compatibility continue to pass. The original baseline hash guard passes after regenerating both contract versions.

The browser suite covers **35 journeys**: all prior 27 plus grouping/breadth/saved-scope migration, live rules success/failure, outgoing impact and path highlighting, folded source/review isolation, triage/documentary search, subtype/empty-family persistence, pinned typed bridges/document navigation, and narrow light-layout accessibility. Existing canvas interaction also verifies hover leaves selection locked and launches no API requests. New narrow-layout axe checks report no violations. These automated checks do not substitute for an actual assistive-technology session.

Visual inspection found a toolbar overflow introduced by additional controls; wrapping and fixed breadth-button layout corrected it. Captured desktop dark/light and narrow screenshots are `output/qa/p53-investigation-dark.png`, `p53-conceptual-light.png` and `p53-investigation-narrow.png`. Browser logs collect actual JavaScript/console/network evidence. Development environment is recorded in `output/qa/environment.json`; the test server extracts a real isolated two-snapshot fixture and does not mock successful graph analysis.

Commands/logs: `output/wheel-env/Scripts/python.exe -m pytest -q` with `PYTHONPATH=src` → `output/phase5-pytest-p53-final.log` (**141 passed in 36.84 s**); `npm run typecheck`; `npm run test:ui` → `output/phase5-browser-p53-final.log` (**35 passed in 39.2 s**); both contract generators; `scripts/phase5_workspace_measure.py` → `output/phase5-workspace-metrics-p53.log`. Existing warnings concern Starlette's TestClient deprecation, parsed ToolSet escape sequences and the frontend bundle-size advisory.

`uv build --wheel --out-dir output/distributions` rebuilds the distributable. After installation into the isolated environment, `python -I scripts/phase5_package_smoke.py` imports the installed package, validates/activates rules, records a review artifact, retrieves strict folded source with its investigation/overlay, checks exact offline token accounting and publication validation, and verifies bundled workspace contracts/frontend assets. All pass. Evidence: `output/phase5-wheel-p53.log`, `output/phase5-wheel-install-p53.log`, `output/phase5-wheel-smoke-p53.log`. The installed source path confirms this check does not rely on imports from the checkout.

## Pinned ToolSet smoke

Commit `f8bc1ec4c54884293dace635275e95c685b03371`, roots `aletheia_toolchain` and `local_tool_assist_mcp`, source digest `e50bcf9c66d7cbf4e2d0ef15b1274f3ba918197abaee87e508f7f1f0e365261e`.

Snapshot `snapshot:ddae1baa1d58ad24a5dd0c468b87511d4554b0db2996ce77b8312e723ed1d890`, implementation digest `17c99690cad6f8dc56dd8d3871717ca9b6670b2b5758ddf90341701b38f84641`: **16,137 entities; 12,754 relationships; 2,063 exact, 439 candidate, 10,252 unresolved**. Publication validation returns no failures. Counts match P5.2; this increment makes no further resolver-recall claim.

| First requested frame | Nodes | Curves | Full-envelope o200k tokens | Elapsed |
| :--- | ---: | ---: | ---: | ---: |
| Mixed, breadth 1 | 5 | 2 | 6,173 | 614 ms |
| Files | 20 | 36 | 32,241 | 1,416 ms |
| Classes | 51 | 35 | 32,167 | 1,847 ms |

The graph is preloaded; the requested frame plan/layout is cold. The first request includes initial local tokenizer setup. These are single development-host smoke samples on ToolSet, with 500/2,000 scene budgets, a 32,768-token limit and canonical-map export for UI use. They are **not** the 50k/150k C14 benchmark or a controlled latency distribution. Omitted representatives/curves and remaining pages are explicit; displayed counts are not total repository counts. Maximum measured packing violation stays below `1e-4`. Source, requests/results and exact counts are reproducible from `output/phase5/p53-workspace-metrics.json` and `p53-toolset.sqlite`.

## Gate interpretation and remaining boundaries

KG6 has artifact decision/replay, stale-reference and canonical-fact isolation evidence. KG7 has deterministic occurrence ordering, visible locality/reasons and actual source/document/re-query journeys with existing keyboard/list/matrix coverage. KG8 retains strict v1 compatibility, v1.1 HTTP/MCP parity and endpoint/reference/budget tests. Geometry, source truth and original C1–C14 safeguards remain tested; this does not mark all external acceptance gates closed.

Process cards expose direct syntax and call references, not inferred preconditions, runtime order or whole-path feasibility. Documentary associations can be ambiguous/stale assertions. Review retention is bounded by model/overlay limits and snapshot availability; accepted annotations do not edit rules, source or extracted confidence. Rules proposals become active only through explicit model validation/selection. Runtime collection workflows, final-build ten-minute soak, target i5/Iris Xe measurements, human orientation studies, screen-reader acceptance and independent LLM comparisons remain open.
