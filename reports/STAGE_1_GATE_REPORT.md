# Stage 1 — C1, C2, C5 gate report

6 November 2026. Status: **passed for the declared static-analysis subset**.

Command: `.venv/Scripts/python.exe -m pytest -q --basetemp output/stage1-gates-final`

Result: 27 tests passed. Twelve parser deprecation warnings originate from invalid escape sequences in the pinned input's string literals; the repository was neither imported nor modified.

The first real ingestion used a Git archive of ToolSet commit `f8bc1ec4c54884293dace635275e95c685b03371`, source roots `aletheia_toolchain` and `local_tool_assist_mcp`. The integration fixture verifies the working tree's before/after status is unchanged and uncommitted audit files are absent from the snapshot.

| Item | Result |
|---|---:|
| Selected-content manifest digest | `e50bcf9c66d7cbf4e2d0ef15b1274f3ba918197abaee87e508f7f1f0e365261e` |
| Entities, including structural/documentary/synthetic records | 16,569 |
| Typed directed relationships | 12,526 |
| Evidence records | 12,526 |
| Documentary incidence memberships | 5,070 |
| Exact relationships | 1,502 |
| Candidate relationships | 395 |
| Unresolved relationships | 10,629 |
| Parse failures | 0 |
| Independently scored exact same-file calls | 226 |
| Direction/target mismatches in that scored subset | 0 |
| Ingestion elapsed time in this run | 16.7578 seconds |

C1 fixtures cover caller→callee orientation, opposite repository namespaces, cross-repository imports/re-exports, parallel call sites, disjoint snapshot merge, export and reload. C2 fixtures cover qualified identity, repeated names, scoped unresolved references, compiler-scope joins and immutable snapshot content. C5 fixtures keep documentary hyperedges out of dependency degree, separate imports from calls, preserve one-to-many evidence, classify ambiguous dispatch and retain test flags by path segments.

Publication rejects missing evidence, broken ancestor caches, invalid depth, nonleaf endpoints and invalid documentary incidences. The database executes the approved DDL unchanged with foreign keys enabled; completed canonical facts are immutable. JavaScript tree-sitter fallback is tested as candidate-only, with grammar version and binary/source digest recorded.

This does not establish completeness of Python dynamic dispatch, impact predictions or later-stage analysis/rendering. Most dependencies in the selected real corpus remain unresolved (including external calls); they are retained with provenance. No C14 performance acceptance or later-stage gate is claimed by this report.
