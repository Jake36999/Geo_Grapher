# Stage 3 — C9 and C10 gate report

6 November 2026. Status: **passed; Stage 4 may proceed**.

The complete regression run passed 59 tests, including the pinned real-repository Stage 1 ingestion, in 24.86 seconds. Thirteen warnings concern source-literal escapes in the input corpus and a Starlette test-client deprecation; none are hidden test failures.

Stage 3 ingested the same ToolSet commit and selected-content digest into snapshot `snapshot:ed93250fab60c8f52a23ff1fd87ef296ec5e37ef16cbce3d316336a5e0e891f9`, with zero parse failures. Ingestion, analysis, default helper contraction caching and publication took 29.9814 seconds. The complete store validation passed.

Both public encoding files are vendored in `assets/tiktoken/`, checked against their official SHA-256 values. Tests disable network retrieval and compare local counters with the official encodings. Adversarial budgets exercise both encodings, full-envelope accounting, endpoint closure and the separate byte-bound fallback. Unsupported/missing weights with fallback disabled return a structured error. Errors for impossible budgets report the measured minimum rather than a silent clipped graph.

All seven operations validate against generated JSON Schemas and strict Pydantic models derived from the unchanged approved TypeScript contract. Input tests reject extra fields, stringified numbers, boolean counts, duplicate filters and excessive UTF-8 IDs. Tool results preserve immutable snapshot source ranges, qualify exact-normalised matches, and keep WL matches as candidates.

Actual `helper_tree_balls_v1` code was checked on all 145 labelled trees of orders 2–5, with all finite-pair distance inequalities verified. Rule tests cover strict YAML, YAML 1.2 scalar behaviour, overlap/conflict rejection, bounded regex mapping, open-world interpretation and missing-required results becoming inconclusive under incomplete evidence. Missing telemetry is not silently treated as an absent architectural dependency.

Cursors are HMAC signed, snapshot/query bound, retained in bounded LRU/TTL plans and tested for tampering, changed scope, expiration and eviction. Evidence pagination accumulates delivered evidence IDs without repeating previous pages. Handle bodies are stored as derived snapshot cache artifacts, so memory-cache eviction does not break already returned evidence references.

The official MCP v1 SDK is locked at 1.30.0, advertising protocol 2025-11-25. Both stdio and Streamable HTTP/SSE passed actual protocol round trips. MCP emits structuredContent once, with no duplicate JSON text block. HTTP and MCP returned identical query envelopes, and Host/Origin checks cover the local HTTP service.

A real ToolSet file-level context returned seven node definitions and eight relationships in **8,132 total envelope tokens** under an 8,192-token budget. Reported budgeted-region count was 8,034; the separate admission guard includes the report overhead. The first query took 2.2083 seconds and two repeated queries with changed request IDs took 12.2 ms and 12.0 ms on the development host. These are observations, not C14 acceptance on the specified integrated-GPU profile.
