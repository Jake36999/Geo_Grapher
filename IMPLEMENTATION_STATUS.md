# Implementation status

Authoritative baseline: FINAL_DESIGN_SPECIFICATION.md v1.1, TECHNICAL_IMPLEMENTATION_BLUEPRINT.md v1.0 and the four normative contracts. They have not been changed during implementation.

- Stage 1 C1/C2/C5: passed; see reports/STAGE_1_GATE_REPORT.md.
- Stage 2 C3/C4/C6/C13: passed; see reports/STAGE_2_GATE_REPORT.md.
- Stage 3 C9/C10: passed; see reports/STAGE_3_GATE_REPORT.md.
- Stage 4: implemented and automated checks pass. Release acceptance remains open for direct screen-reader/manual accessibility review, comparative usability/LLM studies and performance on the specified i5/Iris Xe hardware. See reports/STAGE_4_GATE_REPORT.md and reports/RELEASE_ACCEPTANCE.md; C11/C12/C14 are not declared fully passed.

UI/UX follow-up: 26 isolated Playwright journeys, 71 backend tests and the real ToolSet browser smoke pass after remediation. Fixes include scope-bound frames/diagnostics, camera retention/framing, keyboard/modal flows, recovery paths, stale search/context, matrix layout and finite GPU buffers. See reports/UI_UX_QA_REMEDIATION.md. Run `npm run test:ui` for the isolated regression; its database and rules are generated under output/qa without changing ToolSet or the authoritative contracts.

Source is in src/geographer; tests use pytest; uv.lock pins Python dependencies. The local Graphify copy was inspected as substitute/reference material without importing its graph model as source truth. Source extraction uses ast/symtable and an explicit conservative CFG resolver; tree-sitter JavaScript is tested as a candidate-only fallback.

Output databases/reports are under output/ (ignored). The pinned ToolSet working tree was not modified. Its Git archive is read at f8bc1ec4c54884293dace635275e95c685b03371. Ready workspace database: output/toolset.sqlite; historical Stage 3 database: output/stage3-toolset.sqlite. The local service uses port 8765; a distributable wheel is in output/distributions.

The TypeScript wire declarations are the source for runtime schemas. Run `npm run contracts` after an approved declaration change. Generated JSON Schema is in contracts/generated; strict Pydantic models are constructed from it. Token assets are already cached and checksum verified.

Stage 4 engineering notes: pack the active mixed-detail display tree and explicit residuals (all raw leaf membership remains exact), rather than drawing each unresolved reference. Keep geometry seed tied to expansion state so filters fade groups without re-running global physics. The user requires a tiny deterministic yz-stagger in the feasible line fallback; recompute enclosing radius so containment still holds. The approved viewport request lacks a cursor field, while its response can be paginated; an auxiliary UI-only paging transport may carry that cursor without changing the normative request. Every page must independently preserve endpoint/sphere closure. MCP retains exactly seven tools.
