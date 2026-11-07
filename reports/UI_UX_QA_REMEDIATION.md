# UI/UX QA and remediation — 6 November 2026

P5.4 follow-up adds actual recorded collection windows, source-match/coverage inspection, sage runtime curves and saved runtime scope. The browser suite now has 38 journeys; the new three exercise production recording/import data rather than mocked successful telemetry. See [P5.4 evidence](P5_4_GATE_REPORT.md). Target-device, manual AT and full release acceptance remain open.

P5.3 follow-up: the workspace now uses v1.1 actor frames and shared investigation. The regression suite has grown to 35 journeys, covering grouping/breadth migration, live rules, both impact directions, source/document navigation, triage/review isolation and narrow accessibility. See [P5.3 gate evidence](P5_3_GATE_REPORT.md) for current results and limitations; the findings below retain their original historical measurements. Full-release external acceptance remains open.

**Local UI regression: pass. Full-release verdict: not ready; mandatory external acceptance remains open.**

Used the [Web App QA & Release Copilot](plugin://web-app-qa-release-copilot@openai-curated-remote) release-audit, Playwright, accessibility and responsive-review workflows. This was an authorized local review and implementation pass. No external deployment or publication was performed. The approved specifications and four normative contracts were preserved.

## Scope and evidence

The new Playwright suite starts its own loopback server on port 8771, extracting two immutable Python snapshots into an isolated temporary SQLite database. The fixture contains source, 24 distinct calls, test code, documentation, uncertain targets, an intentional parse failure and a real architecture-rule violation. Fault-path tests inject temporary HTTP failures or delay delivery of actual server responses; successful extraction, analysis, witnesses and conformance are not mocked. The existing ToolSet workflow runs separately against the pinned real repository snapshot on port 8765.

Environment: Windows x64, Ryzen 7 5800X, 31.9 GiB RAM, Node 24.13.0, Python 3.11.3, Microsoft Edge/Chromium 156.0.4314.58. The isolated suite records its actual environment in `output/qa/environment.json`. Browser checks collect JavaScript errors, unexpected console errors and external requests; expected HTTP error messages from deliberate outage tests are excluded from the console assertion. No direct screen-reader session or target-hardware performance benchmark was performed in this pass.

## Confirmed findings and remediation

All findings below are closed in the checked implementation. Severity P2 reflects degraded workflows with a workaround, rather than a claim of catastrophic data loss. The display-state issues did not modify canonical repository facts.

| ID | Severity | Finding and correction | Verification |
|---|---|---|---|
| UI-01 | P2 | Save dialog lacked an accessible name. Bound its heading and retained native modal focus return. | Named-dialog assertion, Escape/focus check and axe. |
| UI-02 | P2 | Mobile drawers did not move keyboard focus or dismiss with Escape. Added responsive focus management, dismissal and focus return. | Mobile keyboard journey. |
| UI-03 | P2 | Switching from 3D to Matrix before saving lost the spatial camera. Capture and retain it across representation changes and restore. | Save/reload regression plus real orbit/camera capture. |
| UI-04 | P2 | Bootstrap retry only retried the viewport and could not recover initial loading. Added a separate snapshot/bootstrap retry. | One failed bootstrap followed by the real service response. |
| UI-05 | P2 | Failed hierarchy requests lacked a direct retry. Added branch-specific retry and prevented aborted branch loads from changing newer state. | Failed hierarchy request, retry, recovered children. |
| UI-06 | P2 | Malformed saved settings passed validation and could produce invalid requests. Validate detail mode, typed panel/camera values and the complete filter shape. | Invalid persisted view rejected; valid pinned/snapshot-specific views still restore. |
| UI-07 | P2 | Revealing detail enlarged the enclosure without reframing. In the failing fixture camera distance was 7.54 while the 45-degree FOV required at least 12.71. Explicit detail changes now refit the camera. | Numeric camera/enclosure test through actual UI actions. |
| UI-08 | P2 | Old search matches remained actionable while a new query was pending. Clear results immediately, bind responses to query generations and support Escape. | Actual query response held while old matches must disappear. |
| UI-09 | P2 | Agent JSON from the previous budget remained copyable while replacement context loaded. Clear stale JSON/counts and disable copying until the new response arrives. | Delayed replacement context under a different budget. |
| UI-10 | P2 | The narrow matrix lacked its intended independent scroll container; controls could move out of view. Added bounded matrix scrolling, fixed controls, sticky headers and removed spatial-only chrome from List/Matrix. | Keyboard horizontal scrolling and visible controls at phone width. |
| UI-11 | P2 | Curve allocation rounded scalar capacity to a power of two, leaving an incomplete xyz tuple. Three.js reported NaN bounding spheres. Allocate complete vertices. | Strict console checks with rendered curves, actual canvas picking and orbiting. |
| UI-12 | P2 | A previous frame could be acted on during a pending scope change; the ToolSet witness action could disappear when the matching frame arrived. Bind frames to complete requested scope, make stale data inert, and keep retry available after dismissing an error. | Delayed-frame test, retry/dismiss paths and repeated ToolSet workflow. |
| UI-13 | P2 | Open diagnostics retained the old filter's values. In the fixture the outgoing ratio stayed 1.000 instead of changing to 25/27 = 0.926 when tests were included. Abort stale diagnostics and recompute against the current matching view. | Independent numeric before/after filter assertion. |

Additional improvements: distinguish snapshot choices by meaningful revision and snapshot suffix; expose pinning in the mobile inspector; explain an empty snapshot store and offer refresh; reset abandoned inspector loading state; label witness/evidence continuation accurately. These are covered by the new suite. Clipboard-denial behaviour was also verified without touching the user's clipboard.

The first isolated run had six confirmed defects and one incorrect test assumption: a continuation page can contain evidence for witnesses already displayed. The revised test requires all 24 witnesses and exhaustion of the continuation cursor, without demanding new witness cards on evidence-only pages. Locator/readiness issues in new tests were corrected rather than counted as application defects.

## Final checks

| Check | Result | Artifact |
|---|---|---|
| Isolated Playwright journeys | 26 pass, zero skipped/flaky/unexpected results | `output/qa/results.json`, `output/qa/browser-run.log` |
| Backend/contract regression | 71 pass; 13 existing parser/test-client warnings | `output/qa/backend-regression.txt` |
| Real ToolSet browser smoke | Pass; seven axe states, no JavaScript errors or external requests | `output/qa/toolset-browser-run.log`, `output/browser/workflows.json` |
| TypeScript and production assets | Pass as part of `npm run test:ui` | `output/qa/browser-run.log` |
| Isolated accessibility scans | Eight dark/light viewport states plus named save dialog: no violations | Playwright assertions/results |
| Responsive renders | 320×720, 390×844, 768×600, 1280×800; default journeys at 1440×900 | Eight PNGs under `output/qa/test-results/` |
| Packaging | Wheel rebuilt, reinstalled separately; installed frontend hash, SQLite, wire models and offline tokenizer verified | `output/distributions/geo_grapher-0.1.0-py3-none-any.whl`, `output/qa/wheel-install.log` |

Original failing evidence is retained under `output/qa/before/`, `before-agent/`, `before-gpu/`, `before-diagnostics/`, and `toolset-before.log`. Final passing tests cover real canvas picking/orbiting, source, diagnostics, conformance, 24-call evidence pagination, matrix/list routes, saved pins/camera/filter/theme/snapshot, empty state, clipboard failure, partial extraction, retries and stale requests. Screenshots support visual review; they are not treated as proof of every workflow.

Source/build hashes are recorded in `output/qa/build-digests.json`; the six approved baseline document/contract hashes were compared with the previous recorded baseline and are unchanged.

Reproduce with `npm run test:ui` (builds assets and starts the isolated server). The existing `npm run test:browser` remains the ToolSet smoke check and requires its local server on port 8765. Python regression: `uv run --extra test --extra treesitter pytest -q`.

## Remaining release work

No open P0/P1 finding was identified in this bounded functional review. That does not establish full release readiness: direct screen-reader/manual accessibility review, comparative human/LLM task evaluation and C14 performance on the declared i5/Iris Xe configuration remain unverified. The previously measured roughly 13-second cold expanded viewport request was not rebenchmarked or claimed fixed; changing local UI state and buffer allocation does not validate backend token-packing performance. A final-build target-hardware run and 10-minute resource check are still required.

See [the acceptance protocol](RELEASE_ACCEPTANCE.md). Owners: implementation/automated regression — this development pass; assistive-technology, participant studies and target-hardware verification — the corresponding release reviewers. No material limitation has been waived. Before an external release, retain versioned artifacts and rehearse rollback against immutable snapshots; that deployment exercise was outside this local pass.
