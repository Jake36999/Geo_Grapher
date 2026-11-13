# Migration preparation for 0.2.0

This is a feature-branch migration guide, not notice that 0.2.0 is released. Back up and test a copy first. F2 integration and owner approval must precede the release build.

## Additive catalog initialization

`GraphCatalog` validates that the database is a catalog, then creates missing tables/indexes/triggers and binds legacy bridges. The Phase 6–7 additions include `bridge_bindings`, `bridge_proposals`, `artifact_justifications`, `artifact_states` and the append-only `revision_ledger`. Existing unbound bridges receive source/target bindings on open. Do not point `--catalog` at an arbitrary SQLite database or a per-graph snapshot store.

This is an initialization migration, not a destructive rewrite or graph merge. Retain the pre-open backup for rollback. Opening with an old executable after a new additive migration is not a supported rollback strategy: old schema allow-lists may reject newer tables. Restore the matching backup/package pair instead.

Creating a legacy binding does not establish current validity or equivalence; inspect its snapshot and lineage state after migration.

## What needs a new snapshot

| Change | Required action |
|---|---|
| Module/class constant entities, fingerprints and static reads | Re-ingest the source to create a new immutable snapshot |
| Full adjacent constant-comment associations | Re-ingest; old documentary incidences are unchanged |
| Persisted stage-3 export/protection analysis | Stage-3 ingestion writes it for the new snapshot; older snapshots use the service’s bounded lazy fallback |
| Porter FTS and query-word handling | Restart/use the new service so its query-time lexical index rebuilds; this alone does **not** require re-ingestion |
| Flat IDs, real error choices and coverage metadata | Use the new server/adapter; old readable snapshots retain their facts |
| Librarian final-at-step-limit behavior | Use the feature-worktree runtime after its approved integration; this is separate from indexing |

The roadmap grouped FTS with re-ingestion changes. The implementation builds the lexical index per service context, so re-ingestion is required for the new source/documentary facts, not merely for the tokenizer. Neither query ranking nor a new adapter silently adds constants to an old snapshot.

Re-ingest only an approved source revision/profile and preserve the original snapshot as evidence. Keep repository namespaces, source roots and include/exclude rules consistent when comparing before/after. A changed extractor version can change relationship occurrence IDs and snapshot-bound QI group IDs; compare semantic edges and member sets rather than treating those identifiers alone as drift. Canonical entity IDs and source provenance remain independently inspectable.

## Verification after migration

1. Confirm labels, source revisions, graph heads and profile filters on the copy.
2. Check constants by exact name, their original line spans and reads; inspect parse failures instead of assuming every language was indexed.
3. Run the installed-package preset smoke and a no-model search → content/packet through Librarian.
4. Exercise directed QI, Off restoration, prune, Add folder and bridge review against real-store copies.
5. Check lineage and bridge states after head changes; retain old cursors/results as historical evidence, not active continuations.

The frozen v1.0 contracts remain unchanged; legacy presentation maps emitted constants to `fragment`. Stable v1.1 declaration, 0.2.0 version bump and release digests are pending the approved merged-main release process. Future post-freeze wire changes belong in v1.2.
