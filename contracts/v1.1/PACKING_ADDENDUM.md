# P5.2 packing and persistence addendum

The Phase 5 continuation authorizes the planned versioned optimization. Original wire/DDL remain unchanged. `packer-v2` changes admission implementation, not the whole-envelope budget or endpoint closure guarantee. Query fingerprints include its version, so earlier cursor plans cannot silently resume under a different selection algorithm.

Persistence uses one shared `executemany` path for all view kinds, under a savepoint that participates in an existing transaction. A failure rolls back the complete view. No published canonical facts are changed.

Member/witness streams use canonical primary-key order for index locality. SQLite uses a configurable 64 MiB page-cache budget (accepted range 1–256 MiB), with foreign keys and immutability triggers retained. A mixed partition can reuse an ingestion-time kind rollup only after its complete atom-to-representative map compares equal. Layout/frame plans are still generated for the actual request; no collapsed-view substitution is used in the expanded benchmark.

Packing shares immutable working records during selection and detaches the returned envelope once. Only witness pagination and scene/completeness metadata are copied on write. Cached selections are still rechecked for the current request ID, cursor and complete envelope.

Admission estimates sum cached official token costs of newly introduced dependency records. Recount the whole envelope every 16 accepted units or when an estimate approaches a 128-unit reserve; exact-check up to eight deferred candidates at the final boundary. Estimates are heuristics, not bounds. Official `encode_ordinary` counting remains authoritative for the mandatory state and final complete region/envelope. If verification fails, evict complete lowest-priority optional units and recheck. If no optional unit can be delivered, scan exact single-unit proposals before reporting a measured minimum, avoiding an empty non-progressing continuation. No private tokenizer API or network access is required.

Keep deterministic tier/utility/marginal-cost ranking and dependency revisit rules. Estimates do not establish monotonicity. Never use binary search over exact payload sizes. Preview generation of signed continuation strings does not commit page checkpoints; only the final accepted payload commits delivered IDs, including evidence continuation state. Units rejected/evicted remain pending and pageable. Both byte-bound and exact modes check final complete-envelope accounting units against the request limit.

Actor serialization may transform the complete selected graph before accounting; all alias bindings, descriptors, previews, lazy handles and continuation metadata count toward that exact final envelope. A requested path or complete small-witness preview is an indivisible unit. Error minimums are measured, and partial content remains explicitly incomplete. The source and documentary trust boundary is unchanged.

Benchmark unchanged expanded requests on the 50k/150k reference corpus, reporting actual returned nodes/curves, cold/warm state, profiled versus unprofiled measurements and development versus target hardware. A lower payload count alone does not close C14. Differential tokenizer tests, mutation isolation, rollback, every-page closure and cursor replay accompany the optimization.
