# Independent project roots and explicit comparison

This describes the earlier combined-snapshot policy, retained for explicit
combined/legacy analysis. Independent projects now default to separate graph
stores and a display-only composition; see `GRAPH_WORKSPACE_SPECIFICATION.md`
at the checkout root. Existing inner v1.1 request/response schemas remain valid.

Independent repositories are separate identity/containment namespaces. Their
repository nodes are siblings beneath the synthetic workspace root, never
children of the first ingested repository. The workspace is a virtual layout
frame, not an imported project. This does not change the canonical tree/LCA or
SQLite schemas.

New multi-project ingestion isolates Python import resolution and documentary
symbol mentions by repository by default. Repositories deliberately participating
in one import environment may declare the same nonempty `resolution_group`.
This opts that group into the existing cross-repository resolver, including
ambiguity handling. It never merges repository ownership or entity IDs.
Repository IDs must be unique. The workspace manifest rejects duplicate and
nested physical roots; use source roots inside one project instead.

The existing `repo_ids` field of `search_entities` and `find_similar_code` must
be nonempty when a snapshot contains multiple repositories. Unknown IDs are
invalid. A caller explicitly lists all desired IDs to compare projects. Empty
lists retain their existing meaning for a single-repository snapshot. This
is a narrower safety policy on existing request fields, not a new wire shape.

Project-focused architecture context does not automatically sweep another
project's descendants into the DOI neighborhood. Explicit pins, workspace-root
queries and explicit linked import environments remain deliberate comparison
paths. Viewports retain each top-level project root; automatic detail follows
the focused project. The UI starts multi-project snapshots at the workspace,
renders independent repository clusters, scopes search to one project by default,
labels cross-project results, and offers an explicit all-project selection.

MCP discovery resource `geographer://projects` lists at most 32 published
snapshots with repository IDs, revisions, canonical root IDs, selected-file
counts and profile indicators. Its scope is configured supported input files,
not every artifact on disk. Historical snapshots without isolation metadata
are labelled `legacy_shared_namespace`; immutability prevents retroactive
correction. Re-ingest with explicit profiles to use isolated resolution.

Directory profiles use case-sensitive POSIX-relative fnmatch patterns (where
`*` can span `/`), source roots, include/exclude lists, and hard file/byte limits.
Over-budget profiles fail instead of silently publishing a truncated selection.
Input content is digested; it is not a Git-wide or filesystem-wide atomic view.
Native PDFs and experimental/binary formats are not implied to have been indexed.

These are retrieval and analysis boundaries, not access-control/tenant isolation
or a guarantee about an LLM's reasoning. Original repository text remains
untrusted documentary content. Identical text or normalized ASTs do not establish
semantic equivalence or scientific truth. The independent research-paper store
still requires a separate database/server per project when isolation is needed.
