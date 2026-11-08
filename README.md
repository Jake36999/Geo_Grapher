# Geo Grapher

An evidence-backed local repository explorer with a neutral nested 3D workspace, synchronised hierarchy/list/matrix, source and witness inspection, mathematical diagnostics and seven read-only MCP tools. The unchanged approved [blueprint](TECHNICAL_IMPLEMENTATION_BLUEPRINT.md), [product specification](FINAL_DESIGN_SPECIFICATION.md) and four normative contracts remain authoritative.

Stages 1–3 passed their gates in sequence. Stage 4 is implemented; hardware, screen-reader and comparative usability acceptance remain open. See [implementation status](IMPLEMENTATION_STATUS.md) and [Stage 4 evidence](reports/STAGE_4_GATE_REPORT.md).

Use Python 3.11+, Node 22.12+ and the lockfiles. The verified host uses Python 3.11.3 and Node 24.13.0:

```powershell
uv sync --locked --extra test --extra treesitter
npm ci
npm run build
uv run geographer serve --database output/toolset.sqlite --catalog output/named-graphs/catalog.sqlite --transport http --port 8765
```

Open [the main workspace](http://127.0.0.1:8765/). The original workspace now includes an **Active graph** selector and a **Graphs** checklist in its existing toolbar. Its existing **3D space / List / Matrix** buttons show the selected graphs; search, hierarchy, coverage and inspector stay scoped to the active graph. Selecting an item from another graph activates that graph in the same page. There are no separate collection/detail viewer pages or iframes. Old viewer URLs redirect to `/`. ToolSet's existing snapshot is registered without re-ingestion or identifier changes, and its original API/MCP routes remain unchanged. Scoped graph MCP is `/graph-hub/mcp`. Startup prepares the original published index; omit `--catalog` to run only the single-store workspace. Saved views retain their original snapshots and now also save graph selection.

On this host, system Python carries MCP 2.x, which the servers do not support (the CLI exits with instructions). Restart the local servers under the pinned environment, and run the full release gate before reporting results, with:

```powershell
./scripts/start-servers.ps1          # main workspace :8765 + graph hub :8774 (logs/PIDs in output/logs)
./scripts/verify.ps1                 # full pytest + typecheck + build + Playwright; -Live adds the :8765 smoke
```

The repository tracks the system only: papers, corpora, graph stores, outputs and logs are ignored (see `.gitignore`).

For another ingestion, use a fresh database:

```powershell
uv run geographer ingest --repo D:/Aletheia_project/DEV_TOOLS/ToolSet --repo-id ToolSet --revision f8bc1ec4c54884293dace635275e95c685b03371 --source-root aletheia_toolchain --source-root local_tool_assist_mcp --database output/new-toolset.sqlite --report output/new-toolset.json --stage 3
```

The CLI archives the immutable commit, ignoring uncommitted files. Omit `--revision` for a content-digested directory. Input code is parsed, never imported/executed. Stages 1/2/3 add extraction, analysis and helper contraction respectively; spatial layouts are derived lazily. Duplicate immutable build IDs are rejected. For changed revisions in the same database, `--previous-snapshot SNAPSHOT_ID` reuses verified unchanged normal forms only when source, grammar and normalizer build match. Bindings/imports, documents and derived graphs rebuild conservatively. Reports list changed/added/removed files and reuse. This is partial content-addressed reuse, not a fully incremental resolver or sublinear rebuild guarantee.

Optional tree-sitter adapters provide JavaScript/JSX/TypeScript/TSX syntactic **candidates**. Missing/unsupported adapters produce explicit coverage failures. Bundled Graphify source was reviewed as substitute/reference material; its graph model and label-only resolution are not source truth.

MCP protocol is pinned to `2025-11-25` through SDK 1.30.0. For stdio, configure the project directory and `uv run geographer serve --database output/toolset.sqlite --transport stdio`. HTTP mode also exposes Streamable HTTP/SSE at `http://127.0.0.1:8765/mcp`. Both use the seven approved operations and identical envelopes. The normative viewport route is `POST /api/v1/viewport/frame`; auxiliary UI-only `/api/v1/viewport/page` carries `{request,cursor}` without changing the approved request or adding an MCP tool. Evidence/membership handles are available as MCP resources `geographer://handle/<percent-encoded handle>`.

The service binds to loopback; assets/fonts and checksum-verified token weights are local. `TIKTOKEN_CACHE_DIR` can override the directory containing the two named `.tiktoken` files; `geographer cache-tokenizers` explicitly restores them. Exact accounting checks whole envelopes. Permitted byte fallback admits against the full UTF-8 byte bound; byte/4 is only an estimate. Runtime overlays are unavailable without measured collections. Load architecture rules with `--rules path/to/geographer.rules.yaml` to enable conformance checks.

The additive actor service is available at `/api/v1.1/{operation}` and `/mcp/v1.1`, or with `serve --schema-version 1.1` for stdio. The workspace uses v1.1 frames with Path/Nearby/Wider breadth and mixed, repository/directory/file/class, atomic and conceptual grouping. Configure rules by pasting or uploading YAML; invalid reloads preserve the prior model. Inspector supports incoming/outgoing impact, original witness-path highlighting, grounded previews, and an Investigate tab for folded source, documentary hierarchy, bounded bridges and review annotations. Search intent selects symbols, code/documents or documentary retrieval. Agent context defaults to the compact counted v1.1 response, with v1.0 compatibility selectable.

Reuse returned aliases by passing `data.identity_scope` as `alias_scope`; omit it for canonical IDs. `identity_mode="canonical_map"` includes referenced full IDs. `get_entity_content` accepts `context_mode="source-context-v1"` and `include_investigation=true`; architecture context can include a bounded `review_queue`. Architecture diagnostics are opt-in. Both encodings count the complete response, including previews, scope handles and continuations. Reviewed annotations remain separate from extracted facts. See the [actor contract](contracts/v1.1/ACTOR_SCHEMA.md) and [workspace addendum](contracts/v1.1/WORKSPACE_ADDENDUM.md).

Runtime recording is explicit: `geographer record-trace --database DB --snapshot-id BASE --repo-root repo_id=LOCAL_ROOT --environment dev --output calls.jsonl -- python -m application`. Import the finalized artifact with `geographer ingest-trace --database DB --snapshot-id BASE --trace calls.jsonl`; it validates the sidecar/source match and publishes an immutable child. Python APIs and an opt-in pytest plugin are available. The workspace can select observation windows and toggle sage runtime curves while retaining static uncertainty. MCP collection discovery uses `geographer://runtime-collections/{snapshot_id}`. Counts remain positive observations, and incomplete/missing capture is disclosed. See the [runtime contract](contracts/v1.1/RUNTIME_ADDENDUM.md) for exact format, limits, supported execution modes and source/process/thread/async boundaries.

Verification and packaging:

```powershell
uv run --extra test --extra treesitter pytest -q
npm run typecheck
npm run test:ui
npm run test:browser
uv build --wheel --out-dir output/distributions
```

`npm run test:ui` builds the current frontend and starts an isolated two-snapshot fixture on port 8771. It requires the project's Python environment and installed Microsoft Edge; results and screenshots are in `output/qa/`. The separate ToolSet smoke workflow (`test:browser`) requires the local service on port 8765 and records `output/browser/`. See the [UI/UX remediation report](reports/UI_UX_QA_REMEDIATION.md). The wheel bundles contracts, schemas, offline encodings and the built frontend; resource loading was checked in a separate virtual environment. Build the frontend before another wheel. Browser dependency/font notices are served at `/THIRD_PARTY_NOTICES.txt`.

Generate the explicit 50k-entity/150k-relationship fixture using `uv run python scripts/benchmark_dataset.py`, serve it on port 8766, then use `npm run benchmark:http` and `npm run benchmark:browser` (10-minute session). Record preparation, cache state, displayed counts and GPU. Development-host results cannot establish acceptance on the specified i5/Iris Xe hardware. Automated accessibility scans also do not replace the remaining [release acceptance review](reports/RELEASE_ACCEPTANCE.md).

The independent research-paper corpus is a source-checkout extension, separate
from immutable code snapshots. See [paper operations](pipeline/README.md) for
bounded MCP cards, provenance, read models, offline maintenance and opt-in
annotations. The [corpus/viewer review](reports/CORPUS_AND_VIEWER_REMEDIATION_20261107.md)
records the verified research claims, applied cleanup and viewer repair.

For unrelated roots, use one independent graph per project, with explicit source
profiles. `geographer inspect-project --repo PATH --report inventory.json`
provides a bounded metadata inventory. `geographer ingest-graphs --manifest
profile.json --catalog output/graphs/catalog.sqlite --report ingestion.json`
ingests each declared project into its own store. A profile has `version: 1` and a
`repositories` array containing `repo_id`, `path`, optional `source_roots`,
`include_globs`, `exclude_globs`, `max_files` and `max_total_bytes`. Use a stable,
unique project label; graph identity is registered from its resolved root.
Overlaps produce a decision plan before that graph is imported. Use
`--on-overlap keep_separate` or `child_module` only after reviewing it. No graph
or alias is merged automatically. The legacy `ingest-workspace` command remains
available for explicitly combined analysis; `resolution_group` applies only
there and must describe a real shared import environment, never a common topic.

Run `geographer serve-graphs --catalog output/graphs/catalog.sqlite --port 8765`
for the integrated workspace with graph-scoped APIs. The same command
with `--transport stdio` serves agent tools. Start at `geographer://graphs` or
`list_graphs`, then send `{graph_id, request}`. Cross-graph comparison is an
explicit `federated_search`; rankings and aliases stay local. See the
[independent graph specification](GRAPH_WORKSPACE_SPECIFICATION.md) for exact
routing, collision and display boundaries. Existing single-store endpoints and
`geographer://projects` remain available for compatibility.
The collection supports Path/Nearby/Wider focus per graph and separate declared
bridge overlays. Its checkbox graph picker places the first graph centrally and
others on hexagonal rings in one canvas (up to 19). Its original list, matrix,
hierarchy and inspector are used in the same page. Hold a bubble rim to drag it,
or wheel while holding to resize. Use
Shift-drag / **Box select** to move or scale a group; keyboard size/move buttons
and **Reset layout** are also available. High-fanout layouts use compact 3D
fallback packing, and documentary bubble sizes account for represented content.
These edits are presentation state and preserve graph ownership. To deliberately
combine related projects, use **Create a
physically merged graph**, review the pinned sources, then create the reviewed
destination. CLI equivalents are `plan-graph-merge` and `merge-graphs --plan-id`.
Original graphs remain intact; documents and concept homonyms retain their
source origins. The [workspace contract](contracts/graph-workspace.d.ts) defines
the additive endpoints. Run `npx playwright test --config
playwright.graphs.config.cjs` for the disposable graph-workspace browser fixture.
The [assessment and bounded two-project pilot](reports/PROJECT_ISOLATION_ASSESSMENT_20261107.md)
explain current coverage, remaining artifact/domain-model gaps and verification.
