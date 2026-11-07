# P5.4 — immutable observations and runtime collection workspace

6 November 2026. Core P5.4 implementation is complete: trace import, explicit bounded recording, opt-in pytest capture, runtime/static provenance and collection controls. Original specifications, four original normative contracts and the canonical SQLite schema remain unchanged. Optional Python 3.12+ `sys.monitoring` is not implemented or claimed tested; the verified backend is `sys.setprofile` on Python 3.11.3.

## Delivered behavior

- Strict `python-call-trace-v1` JSONL and sidecar validation checks SHA-256, source revisions/digests, UTC windows, positive finite counts/latency inputs, namespaces and resource limits. Duplicate JSON keys, raw rows and normalized call-site aliases cannot silently double counts. Input p95 remains producer-reported and is never averaged.
- Source mapping uses stored source identities, exact qualified names, caller spans and callee definition/decorator lines. Nested `<locals>` names and Windows paths are supported. Unknown/ambiguous/native/outside-root observations are quarantined with reconciled record and call totals; trace rows cannot trigger file reads or code execution.
- Import publishes a new child in one immediate SQLite transaction, preserving canonical IDs/source/static facts, regenerating standard static rollups where applicable, validating publication and committing complete status atomically. Injected validation failure leaves no partial child. Identical imports are idempotent; conflicting/overlapping same-environment collections require a separate explicit policy and are rejected in a combined snapshot.
- `record-trace` explicitly executes a supplied Python command without shell interpolation. The recorder verifies indexed source/cache digests before/after execution, covers declared Python callable activations and new threads, counts generator/coroutine first activation once, restores hooks and preserves normal/failing exit status. Limits, hook replacement, source mismatch and hard exits are disclosed. Module/class definition frames are not mislabelled constructor/function calls. Native/external/subprocess/shutdown work is excluded; no segment-derived end-to-end timing is invented.
- Pytest works through the wrapper or an explicit `-p geographer.pytest_trace` plugin. Neither ordinary ingestion nor plugin installation automatically runs code or starts profiling. Static/runtime comparison is line-level evidence; actual monkeypatch observations can disagree with static exact targets without rewriting either claim.
- Bootstrap and read-only MCP resources expose matching collection windows, units, coverage, counts and lazy quarantine reports. Zero mapped facts remain a known collection with explicit limitations, not proof of absence. The seven query tools remain read-only and retain full-envelope counting/closure.
- Workspace Runtime overlay selects a matching environment/window, adds observed status without losing static uncertainty, renders sage parallel tracks, exposes actual witness/call units and restores static scope when disabled. Saved windows validate availability; switching to source-only snapshots drops stale runtime scope. The analysis badge distinguishes static, combined and observation modes. Conformance continues to compare exact static facts.

The executable schema is `contracts/v1.1/geographer.trace.schema.json`; full semantics, CLI/plugin/API examples, bounds and limitations are in [RUNTIME_ADDENDUM.md](../contracts/v1.1/RUNTIME_ADDENDUM.md).

## Verification and artifacts

The suite includes **159 backend tests**, with **18 dedicated runtime cases**. These cover immutable lineage, full-child rollback, idempotence, conflict/overlap handling, count reconciliation, multiple repositories, Windows case/root handling, nested/decorated/module callers, generator/coroutine resumes, threads, failed/hard exit, hook restoration/replacement, byte/time limits, source mismatch/output protection, actual pytest wrapper/plugin executions, runtime window filtering in both wire versions, actual monkeypatch disagreement, empty mapped results, and HTTP/MCP collection/resource recovery. Original Stage 1–4, P5.0–P5.3, baseline hash, token and transport fixtures remain included.

The browser suite includes **38 journeys**: prior 35 plus actual recorded-collection overlay/units, saved environment/window/evidence recovery, and source-only snapshot transition. QA startup executes owned fixture code, records two real observation collections and imports them using the production pipeline. Successful telemetry/extraction is not mocked. Existing dark/light/narrow and axe checks remain; manual screen-reader and target-device acceptance remain separate.

Visual inspection caught and corrected a stale STATIC ANALYSIS badge and an uncertainty caption that treated observed status as a candidate. Runtime evidence is now labelled separately. The runtime screenshot is `output/qa/p54-runtime-overlay.png`; environment and browser evidence are under `output/qa/`. Expected request-cancellation resets can appear in server logs; browser JavaScript/console assertions remain required.

Final command logs: `output/phase5-pytest-p54-final.log` (**159 passed in 53.09 seconds**), `output/phase5-browser-p54-final.log` (**38 passed in 49.6 seconds**), `output/phase5-runtime-metrics-p54.log`, and `output/phase5-toolset-metrics-p54.log`. TypeScript checking and the original-contract hash guards pass. The 13 backend warnings are the existing TestClient and parsed-source escape deprecations; the frontend retains its bundle-size advisory. These runs include concurrent development-host work and are not performance distributions.

The rebuilt wheel installs successfully. `python -I scripts/phase5_runtime_package_smoke.py` imports the installed package and exercises installed `record-trace` and `ingest-trace` subprocesses, rather than checkout imports. It publishes **two mapped calls**, confirms the complete base export is unchanged, validates the child, checks bundled schema/runtime documentation, and retrieves observed architecture context in **1,473 full-envelope o200k tokens** within an 8,192-token request. Logs: `output/phase5-wheel-p54.log`, `output/phase5-wheel-install-p54.log`, and `output/phase5-wheel-smoke-p54.log`.

## Preserved actual capture

`scripts/phase5_trace_measure.py` materializes and explicitly executes owned source containing a generator, coroutine and thread, verifies sources and ingests the finalized artifact. Persistent evidence is `output/phase5/p54-calls.jsonl`, its manifest, `p54-runtime.sqlite`, `p54-runtime-metrics.json` and `p54-context.json`.

| Measure | Result |
| :--- | ---: |
| Logical activations captured | 12 |
| Unique input rows | 7 |
| Mapped rows / call count | 5 / 10 |
| Quarantined rows / call count | 2 / 2 |
| Resume segments excluded from call counts | 5 |
| Published v1.1 context | 20 nodes / 5 relationships |

The two unmapped caller entries correspond to async/thread framework boundaries outside the indexed source. They are retained as uncertainty rather than attributed to a guessed source caller. The base export digest is identical before/after import and publication validation has no failures. Full-envelope context tokens and exact build/snapshot/trace digests are recorded in the JSON artifact; they can vary with content-addressed identifiers. The artifacts match backend implementation digest `47f391df7d7d8adac859098443e669a6b8496c7d0effa7a132010cfce5d34d8f`. Elapsed time is a development-host smoke sample, not a controlled benchmark or C14 result. No latency quantile was collected.

`scripts/phase5_trace_measure.py --toolset` re-ingests commit `f8bc1ec4c54884293dace635275e95c685b03371` with the original roots and source digest `e50bcf9c66d7cbf4e2d0ef15b1274f3ba918197abaee87e508f7f1f0e365261e`. The validated static snapshot still contains **16,137 entities, 12,754 relationships and 12,754 evidence records**: 2,063 exact, 439 candidate, 10,252 unresolved. `p54-toolset-metrics.json` records the exact implementation/snapshot digest and `runtime_workload_executed=false`. No ToolSet application was executed and no ToolSet runtime-recall improvement is claimed.

## Boundaries and remaining work

Coverage describes indexed Python callable activations, not all processes, native execution, task causality, invocations that never activated, or source-wide non-observation. Profiling has overhead and retains bounded frame state; equivalence to uninstrumented timing/behavior is not established. Imported third-party manifests remain producer assertions. Line-only runtime records cannot resolve every same-line AST occurrence. Forced parent termination may prevent finalization. No monitoring backend, distributed tracing adapter, inferred call graph from line coverage, automatic overlapping-collection merge or quantile merge is claimed. Windows verification does not establish a native POSIX-fork execution test; the implementation carries PID isolation guards.

P5.5 comparative evaluation is next. Equal whole-prompt budgets, independent answer/witness oracles and actual model transcripts remain unverified. Human orientation/AT studies, target i5/Iris Xe performance and final-build soak remain open in `RELEASE_ACCEPTANCE.md`; this increment does not imply external publication or full release readiness.
