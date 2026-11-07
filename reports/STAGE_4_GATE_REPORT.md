# Stage 4 evidence and remaining acceptance

6 November 2026. **Implementation delivered; release acceptance remains open.** Stages 1–3 passed their gates before Stage 4. The approved baseline documents and four normative contracts remain unchanged.

Implemented: deterministic sphere packing with transverse fallback stagger; clamped spline/Greville lanes and smoothstep EdgeLens; independently closed viewport pages; neutral React/Three.js workspace; hierarchy/list/matrix; source/witness/evidence continuation; impact, similarity, conformance and computed diagnostics; saved camera/scope/pins/panel settings; conservative cache reuse/invalidation; structured failures and renderer fallback. Initial repository rollups reuse precomputed exact quotient witnesses. Nearby detail is explicit, while internal counts remain complete.

The final full Python run passes **71 tests**. Fixtures cover high fan-out/mixed radii, forced fallback and non-collinearity, epsilon 1e-4 containment/separation, clamped endpoints, preserved three-point LCAs, opposing lanes, Greville monotonicity, lens behaviour, per-page endpoint/sphere closure, and filter-coordinate stability. Root/file/deep method-inner-function focus retains every selected ancestor. An output-sensitive ancestor/descendant traversal implements the exact DOI threshold; independent LCA/DOI checks still pass.

Browser journeys pass without JavaScript errors or external requests. Seven axe scans have zero violations: dark overview, source evidence, matrix, light inspector, laptop, phone list and phone hierarchy. Journeys exercise keyboard hierarchy entry, search, source, incoming impact, diagnostics, witnesses, agent JSON, save/restore and WebGL failure. This verifies scripted workflows, not complete WCAG conformance. The current [W3C WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/) was consulted. Direct screen-reader review remains pending.

The final ToolSet ingestion uses the approved commit/roots and selected-content digest `e50bcf9c66d7cbf4e2d0ef15b1274f3ba918197abaee87e508f7f1f0e365261e`. It published 16,569 entities, 12,526 relationships/evidence records and 5,070 documentary memberships, with zero parse failures, in 18.0311 seconds. Counts retain 1,502 exact, 395 candidate and 10,629 unresolved facts. `output/toolset.sqlite` is ready; `output/toolset.json` records its immutable build. Historical Stage 1–3 reports retain original snapshots/measurements. The ToolSet working tree was not modified.

The reference fixture has exactly 50,000 entities and 150,000 typed relationships, each with evidence; store validation passes. It is an explicit synthetic storage/layout workload, not an extraction oracle. Its repository quotient is precomputed before browser measurement, as for normal Stage 3 ingestion.

An intermediate expanded-view soak recorded 601,175 ms, 116 post-GC samples, 102 spheres, 601 curves, three GPU geometries and four draw calls. The sampled lower FPS percentile stayed near 59. Heap rose from 9.22 MB to a plateau near 10.6 MB (maximum 10.68 MB); GPU geometry count stayed constant through repeated List/3D teardown/remount. This predates final shell/startup refinement and is developmental evidence, not final-build C14 acceptance. Raw data: `output/browser/expanded-reference-soak.json`.

That expanded overview took 18,630 ms and failed the 3-second target. Collapsed startup, quotient/index reuse and output-sensitive DOI traversal reduced a later browser measurement to **2,035 ms** for a usable collapsed overview (two spheres, zero external curves; internal typed counts preserved). The server prepared its immutable graph and both encoders before HTTP readiness; browser/viewport plan were cold. Backend preparation is separate from browser latency. This does not claim a two-second expanded scene.

The final expanded viewport first page took 13,133 ms with a cold plan, then warm p95 was 82 ms. The first witness page took 465 ms, then warm p95 was 38 ms. Cold expanded detail remains a material latency limitation. Full distributions are separately recorded in `output/browser/http-performance.json`; cached plans are not conflated with cold builds. Runs use Windows 11, Ryzen 7 5800X, 31.9 GiB, 1440×900/DPR1, Edge Chromium 156.0.4314.58 and ANGLE/Radeon RX 5500 XT. The specified i5-1235U / 16 GiB / Iris Xe target was unavailable.

| Gate | Status |
|---|---|
| C7 | Automated root/file/deep focus and ancestor checks pass. |
| C8 | Numeric geometry fixtures pass; dark/light spatial screenshots reviewed. |
| C11 | Scripted keyboard/evidence/impact and semantic checks pass; screen-reader review open. |
| C12 | Seven scans and desktop/laptop/phone screenshots pass; complete manual contrast/focus review open. |
| C14 | Reference storage, HTTP timing and developmental soak measured; target hardware and final-build acceptance open. |

Comparative user/LLM results have not been fabricated. Run [the remaining acceptance protocol](RELEASE_ACCEPTANCE.md) before declaring all release gates passed. No Stage 5 research feature or live telemetry feed was introduced.
