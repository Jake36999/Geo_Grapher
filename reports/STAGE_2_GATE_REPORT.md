# Stage 2 — C3, C4, C6, C13 gate report

6 November 2026. Status: **passed on fixtures and the pinned ToolSet snapshot**.

The non-integration suite has 36 passing tests after Stage 2 additions. The previously passed real-repository Stage 1 integration remains available as a separate marked test. Stage 2 also ingested ToolSet commit `f8bc1ec4c54884293dace635275e95c685b03371` and published snapshot `snapshot:410eb735b7fdf23cd85584f09cba68cc028630e9a4f2395b7f50cdc17ec0f360` after full validation.

| Persisted result | Count |
|---|---:|
| Atomic, file and repository analysis views | 3 |
| Quotient projections, including internal edges | 601 |
| Exact witness-map memberships across views | 1,560 |
| Per-view SCC membership rows | 15,464 |
| Cached three-round directed WL hashes | 671 |
| Validation problems | 0 |
| End-to-end Stage 2 ingestion in this run | 26.8827 seconds |

The witness-map count spans three filtered views; it is not the total raw relationship count. The default production filter selects exact static facts and excludes test/generated/vendor entities. Unresolved facts remain retained in the underlying snapshot.

C3 checks direct versus staged projection, preservation of each raw occurrence, witness paging, internal counts and indexed keyset queries. C4 exhaustively checks 25 legal expansion states on an irregular tree, synthetic residual membership and ancestor shells without double counting. C6 checks a file DAG whose quotient cycles, longest-path ranks, recursion and an iterative 5,001-vertex traversal without recursion-limit dependence. C13 compares canonical exports plus all derived view tables in fresh processes with different PYTHONHASHSEED values.

Metrics fixtures independently check directed/undirected degree-volume denominators, zero-volume results, loop/parallel projection losses and per-component Cayley bounds. WL fixtures check synchronous refinement, edge direction, type and multiplicity; hashes remain similarity candidates.

These gates do not claim dynamic-dispatch completeness, QI certificates, token-packing correctness, accessibility or rendering performance. Those belong to subsequent stages.
