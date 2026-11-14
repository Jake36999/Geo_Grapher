# Operator guide

Use the reviewed wheel and a disposable catalog while reviewing these feature branches. No 0.2.0 release has been built from merged main yet.

```powershell
uvx --from C:/QA/geo_grapher-0.1.1-py3-none-any.whl geographer serve-graphs `
  --catalog C:/QA/catalog.sqlite --transport http --port 8790 `
  --browse-root C:/QA/browse
```

Open the loopback URL printed by the server. Use a free port; do not replace an existing listener. This is a local application, not a remotely authenticated multi-user service. The HTTP transport validates Host/Origin and JSON requests; native local API clients without an Origin are supported. That guard is not a sandbox against a hostile local process with filesystem access.

## Serving and scope

| Flag | Purpose |
|---|---|
| `--catalog` | Graph catalog; alternatively `GEOGRAPHER_CATALOG` |
| `--transport stdio\|http` | MCP stdio or local HTTP workspace |
| `--port` | Local HTTP port |
| `--browse-root DIR` | Repeatable directory allow-list; absent means no picker |
| `--graph-id ID` | Repeatable connection allow-list; alternatively `GEOGRAPHER_GRAPHS` |
| `--tools` | `papers`, `code`, `lead`, `cross`, `all`, or explicit tool names |
| `--max-result-chars` | Complete agent-result cap, including code and paper results; alternatively `GEOGRAPHER_MAX_RESULT_CHARS` |
| `--ui-origin` | Compatibility viewer redirect to a validated loopback HTTP origin |

Stdio stdout is reserved for MCP. Preserve errors and receipts separately. UI composition does not merge stores. Prefer labels returned by discovery in agent calls; maintain canonical graph IDs in connection configuration.

## Catalog and backups

The catalog records graph labels, heads, profiles and paths to independent code/paper SQLite databases, plus overlap decisions, bridges, proposals and lineage records. Published snapshot facts stay immutable; query analyses and catalog state can still change. Source roots are also needed for later folder operations and re-ingestion.

Before upgrading, stop the server you own and take a coordinated backup of the catalog, every referenced code/paper database, relevant source/configuration, and `.cursor-secret` sidecars. For a live read-only copy use SQLite’s backup API, not a lone filesystem copy that omits WAL contents. Per-file live backups are not a cross-database transaction; use a quiet/stopped service for a coherent upgrade backup. Keep signing-key bytes private and never put provider keys in reports. Preserve the original path mapping or update a restored catalog deliberately on a copy.

Opening a newer catalog can apply additive initialization even when the intent is only to view it. Test migration on a backup and retain the old package and backup together.

## QA retention

`scripts/qa_cleanup.py` keeps the newest two eligible copies per scenario. It defaults to dry-run; `--apply` performs validated deletion. It operates only in an explicitly marked managed root, organised as `root/scenario/run`:

```json
{"schema_version":1,"kind":"geographer-disposable-qa-root"}
```

Save that as `.geographer-qa-root.json`. Each run needs `qa-copy.json`:

```json
{"schema_version":1,"disposable":true,"scenario":"browser","created_at":"2026-11-13T10:00:00Z","state":"complete"}
```

Mark a running copy `active`; only `complete` or `failed` copies with timezone-aware timestamps are eligible. Stop the server before marking completion. Remove only known test-owned junction entries during teardown, never their targets; copies still containing reparse points remain protected.

```powershell
python scripts/qa_cleanup.py --root D:/QA/qa-workspaces
python scripts/qa_cleanup.py --root D:/QA/qa-workspaces --apply
```

Run cleanup before every browser cycle. Plans are rechecked before deletion; stale or forged plans fail. Any `phase67-gates` path, frozen wheel, unmarked copy, active copy, reparse point or questionable path is preserved. Legacy gate-directory QA copies are deliberately outside automatic retention. The cleanup does not delete result JSON, screenshots or traces stored outside managed copies.

## Verification and evaluation limits

Run `scripts/verify.ps1`, the installed-wheel preset smoke and the relevant real-store browser/security configuration. Keep each attempt under a new result path. Run cold latency only on a quiet machine and retain every sample. Wave-4 C14 still requires all ToolSet samples below three seconds; the proposed median/max rule has not replaced it.

Wave-4 code evaluation is closed after its final registered cycle. Preserve `wave4-code-evaluation-final.json`, all seals, raw results and cost receipts. No cleanup or operator retry should reopen that cycle. Merging, versioning, tagging and pushing require the owner’s separate approval.
