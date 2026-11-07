# P5.2 — projection performance and grounded actor retrieval

6 November 2026. This increment implements the P5.2 backend services and additive v1.1 actor contract. It does not complete P5.3 workspace integration, P5.4 telemetry, P5.5 comparative evaluations, or final release acceptance. The original specifications and four original contracts retain their baseline hashes.

## Delivered behavior

- Shared transactional bulk view persistence replaces per-row inserts. Canonical-key ordering improves index locality. The SQLite page-cache budget defaults to 64 MiB, with foreign keys and immutability checks retained. An existing ingestion rollup is reused only when the complete partition mapping matches.
- `packer-v2-incremental` estimates marginal record costs, checks exact envelopes at checkpoints and before delivery, and evicts whole optional units when necessary. Returned payloads are detached from working records. Endpoint/path witness closure, signed cursor scope, evidence pagination, byte-bound fallback, and final official BPE counting remain enforced.
- `documentary-tree-v1` adds an orthogonal structural Markdown/docstring hierarchy. `lexical-fusion-v1` combines formal and documentary FTS5 ranking while exact identifier matches retain first priority. Documentary mentions remain assertions rather than dependency edges.
- `typed-bridge-v1` performs bounded deterministic subject-graph/FSM BFS, with original directed witnesses, explicit reverse traversal, anchor coverage, budget omissions and honest search outcomes. Reference BFS is used; optional reachability pruning remains disabled.
- The additive actor service supplies source-derived signatures/gists, partition member previews, complete small-witness previews and reason counts. Compact aliases can be passed directly to later tools using `alias_scope=data.identity_scope`; canonical-map mode remains available for export. Persisted scope recipes survive memory-cache eviction.
- `source-context-v1` returns exact enclosing headers, a complete focal span, optional sibling stubs, and retrievable omitted ranges. T_S and T_D do not replace T+ ownership. Unsupported source trees explicitly fall back to source ranges. Oversized mandatory source produces a budget error.

All seven shared operations are served through `/api/v1.1/{operation}`, MCP Streamable HTTP/SSE `/mcp/v1.1`, and stdio selected with `--schema-version 1.1`. The protocol remains `2025-11-25`. Mixed frames are served at `/api/v1.1/viewport/frame`. Other viewport groupings are explicitly rejected pending P5.3. The existing React workspace and v1.0 API remain operational.

## Pinned ToolSet ingestion and density

Source: commit `f8bc1ec4c54884293dace635275e95c685b03371`; source roots `aletheia_toolchain` and `local_tool_assist_mcp`; source digest `e50bcf9c66d7cbf4e2d0ef15b1274f3ba918197abaee87e508f7f1f0e365261e`.

The current Stage 3 snapshot is `snapshot:72cbf9121395ab8ba1922694231977b45a3c6c20a496af343d31d96b63867e2b`, implementation digest `4b94271f910b435be3fde42524cca5b7956510bb351c35210bfc30c3089bbefa`. It contains 16,137 entities and 12,754 relationships: 2,063 exact, 439 candidate and 10,252 unresolved. Publication validation returns no failures. Relationship classifications match P5.1; documentary restructuring does not claim another resolver-recall improvement.

The same request shape, source and 8,192 o200k budget produce the following actual adaptive pages:

| Format | Nodes | Relationships | Complete witness previews | Whole-envelope o200k tokens | Fixed-envelope cl100k recount | JSON bytes |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| v1.0 | 10 | 7 | 0 | 7,925 | 8,229 | 18,069 |
| v1.1 compact | 13 | 16 | 12 | 7,939 | 7,856 | 28,259 |

These adaptive pages select different records. v1.1 diagnostics are opt-in, while v1.0 retains its original payload. Do not attribute the entire adaptive gain to alias encoding. More readable semantic content can increase bytes while using fewer BPE tokens. Complete previews cover relationship identities, not all evidence or runtime feasibility; avoided round trips have not been measured in independent tasks.

A separate identical-record-set format experiment retains the v1.0 record selection, adds actor descriptors/previews, and transforms identities. It measures 7,924 → 5,456 o200k tokens (31.1% reduction), and 8,220 → 5,435 cl100k tokens (33.9%). This is a cost artifact with an opaque sampled continuation, not a resumable public response. The fivefold density and 60–90 tokens/item goals remain unproven.

Pruning unreachable JSON Schema definitions reduces the seven MCP input schemas from 76,393 to 3,963 o200k tokens for v1.0, and from 90,533 to 4,435 for v1.1. These are input-schema measurements, separate from response budgets and total model prompt costs.

Artifacts: `output/phase5/p52-actor-metrics.json`, `p52-actor-1.0.json`, `p52-actor-1.1.json`, and `p52-toolset.sqlite`. Reproduce with `scripts/phase5_actor_metrics.py` using the pinned MCP 1.30.0 environment.

## Expanded viewport performance

The unchanged reference manifest has 50,000 entities and 150,000 relationships. Requests use breadth 1, expanded repository/files, scene budgets 500/2,000 and a 32,768-token limit. Graph and tokenizer are preloaded; the first layout/frame plan is cold. Actual output is 102 nodes and 13 curves, rather than a substituted collapsed scene.

| Development-host experiment | First request | Following warm requests | Derived SQL state |
| :--- | ---: | :--- | :--- |
| Intermediate bulk/compatible exact packer | 16,546 ms | See artifact | Rollups absent |
| Final incremental packer/locality/cache | 3,992 ms | 70–72 ms | Rollups absent |
| Ingestion rollup reuse | 1,116 ms | 68–69 ms | File quotient available; SQLite cache shrunk before timing |

All rows above are unprofiled. Outputs contain about 32.4k tokens. The intermediate comparison includes several combined optimizations and is not a clean isolated packer ablation. The historical Stage 4 13,133 ms measurement is a separate run. Profiling artifacts are retained separately and are not used as unprofiled speedup baselines.

The rollup-absent case still exceeds three seconds. These measurements exclude graph/tokenizer startup and do not establish C14 on the specified i5/Iris Xe hardware. Reproduce using `scripts/phase5_performance.py final-derived-cold` and `scripts/phase5_performance.py ingestion-rollup --precomputed`; artifacts are under `output/phase5/performance-*.json`.

## Gate evidence and remaining scope

Backend fixtures cover transaction rollback and projection/witness equivalence; deterministic documentary sections and dependency/WL noninterference; exact/subtoken/documentary retrieval; independently computed small-graph reachability; typed boundaries/directions/limits; source folding; actor previews; snapshot-bound aliases after cache eviction; both encodings and byte fallback; all seven operations; multi-page evidence and viewport closure; and actual v1.0/v1.1 HTTP/SSE and stdio parity. The original baseline hash guard passes.

KG2/KG3/KG5/KG6/KG8 have backend fixture evidence, not completed human task evaluations. The Markdown parser is an explicitly versioned structural subset, not a complete CommonMark implementation. Indexes are local, bounded by snapshot-context retention and rebuilt on demand. Unsupported dynamic resolution remains unsupported. The inheritance path template uses extracted `inherits` witnesses; it does not invent an override relationship where none is extracted. Runtime reconciliation and process-evidence ingestion remain P5.4. Optional pruning and learned retrieval are not enabled.

Final verification: **129 backend tests pass** (32.51 seconds), **27 browser tests pass** (25.9 seconds), and TypeScript type checking passes. The warnings are the existing Starlette TestClient deprecation and invalid-escape deprecations in parsed ToolSet source. Schema regeneration passes and the original baseline hash guard passes. Logs: `output/phase5-pytest-p52-final.log`, `output/phase5-browser-p52-final.log`, `output/phase5-actor-metrics-final.log`, and `output/phase5-performance-final-cold.log`.

The rebuilt wheel installs into the isolated environment. A Python `-I` smoke check imports its installed package, ingests a fixture, serves strict v1.1 HTTP search with offline exact counting, and verifies bundled v1.1 schemas and frontend assets. Logs: `output/phase5-wheel-p52.log` and `output/phase5-wheel-smoke-p52.log`. This confirms installed resource discovery rather than relying on the source checkout.

Human/assistive-technology reviews, target-device performance, final-build soak, and matched-budget LLM evaluation remain open in `RELEASE_ACCEPTANCE.md`.
