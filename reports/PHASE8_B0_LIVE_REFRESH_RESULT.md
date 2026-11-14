# Phase 8 live native graph refresh — published and queried

2026-11-14. Executed under the owner's explicit S1/live-refresh approval and subsequent confirmation that F: space was freed. **Spend $0.** No merge, push, tag, model dispatch or role-binding change.

## Result

Live `librarian-v2`, graph `g_1bbebca16afc45c39b2f2f8a`, now has **33,100 entities**, previously **424**. The live MCP listing confirms the count and new head. Search and source-content reads succeeded against the same head; this is live evidence, not only a disk check.

```text
before snapshot:f2bce47cb554c2304bd1e148d8cc1f6e5aa8363c5588cd3bc9912a90351695bc
after  snapshot:099f17a010c8bbfb9690fbc2f6cdb1e4fffafd99c303116ad66cd06c6e59d2d5
source fd070b1f20bd90fef9a200f9bcbc5f0624d409f4 (native master, not unmerged B0)
```

Persistent store:
`G:/Libraries/_geo-hub/librarian-v2-20261114-a4-first/graphs/g_1bbebca16afc45c39b2f2f8a/code.sqlite`.

This location is **live-backed, never disposable QA**. Its `LIVE_BACKED.md` marker, `build-plan.json`, `publication.json` and `catalog-before-publication.sqlite` record the state and previous binding. Both old/new snapshots are readable in the copied store. The original F: store remains untouched and retained. Other graph bindings were not changed; publication used a compare-and-swap on the native graph's old snapshot, store path and profile, refusing any concurrent change.

## A4 and coverage

Generated-bundle exclusion was tested before the build: Geo directory/Git selection tests plus publication guards **6 passed**; native source-survey/content-walk exclusion also has RED-first coverage. The broader Geo projection/A4/L4 targeted run passed **18 tests**. The Geo backend suite subsequently passed **816, 2 skipped** before the four new refresh tests were added; this is not the final S6 suite count.

The immutable selection is `src` plus `ui/src`: **159 files, 3,042,815 bytes**. New-snapshot entities for generated `src/resource_librarian/ui/app.js`: **0**. Its previous FallbackParseError is resolved **by exclusion, not a parser fix**; historical snapshots retain their original evidence.

Stage 3 completed in **64.97 s**. One distinct source parse failure remains: `ui/src/settings.ts`, `FallbackParseError` (Tree-sitter syntax errors; no complete fallback facts published). This is a source TypeScript coverage limitation, not a generated-bundle failure, and has not been hidden or fixed. Do not claim complete syntax extraction of every selected file. The graph is static extraction, not observed execution.

The refreshed profile records the accepted internal code purpose/stratum: own-current, owner_created, current/gold/code. This refresh does not deploy the unmerged B0 runtime access-policy changes.

## Space and safety

Before publication, F had **13,767,663,616 bytes** free at the recorded preflight (above 5 GiB); G had over 123 GB free before build. The native original store was 30,691,328 bytes. Build artifacts totalled **556,486,819 bytes**, below the approved **4 GiB G:** bound. Catalog backup/build work stayed on G. Publication changed only the small existing F: catalog binding, within the separate **1 MiB** headroom allowance. Reserve was rechecked by the publishing helper.

No files/snapshots/stores were deleted. No source credential bodies were fetched: Git paths were filtered before blob reads. The first RED run for the new publication helper had **4 failures** before implementation; its GREEN run had **6 passes** including A4 selection. All first results are retained.

## Hub coordination and live evidence

Port 8765 had no listener. Started the existing main checkout's server using its pinned wheel environment, **without changing main code**, PID **34888** (venv launcher; actual listener may be its child):

```powershell
# PYTHONPATH points to F:/uv-data/Geo_Grapher/src;F:/uv-data/Geo_Grapher
& 'F:/uv-data/Geo_Grapher/output/wheel-env/Scripts/python.exe' -u -m geographer serve --database 'F:/uv-data/Geo_Grapher/output/toolset.sqlite' --catalog 'F:/uv-data/Geo_Grapher/output/named-graphs/catalog.sqlite' --transport http --port 8765
```

Launched hidden via Start-Process; logs/PID live beside the persistent build. Tokenizer/temp caches are on G. No previously running hub was killed or replaced.

At `http://127.0.0.1:8765/graph-hub/mcp`, initialized an MCP session and called:

1. `list_graphs({})` — native count 33,100 and exact new head; other graphs still available.
2. `search_entities(graph_id='librarian-v2', query='resource_librarian.closure.operation_class', limit=3)` — source-backed closure.py match at lines 250–267, source revision fd070b1 and exact new head. The exact match ranked second; no ranking tuning was done.
3. `get_entity_content(graph_id='librarian-v2', entity_id=<returned canonical closure id>)` — source text and exact new head, no tool error.

All three calls succeeded. The SDK/server logs include an AnyIO ClosedResourceError during client disconnect; it did not make either query fail. Retained the log and verified the follow-up content call rather than treating a process start as proof of service visibility.

Evidence root: `G:/Libraries/_qa/phase8-b0-20261114/evidence/`:

- `live-refresh-red.txt`, `live-refresh-green.txt`, `live-refresh-build-first.txt`, `live-refresh-publication-first.txt`.
- `live-hub-query-first.json` and `.txt`, decoded `live-hub-listing-payload.json` / `live-hub-search-payload.json`.
- `live-hub-content-first.json` and `.txt`.

Prior S0 navigation snapshot (29,380 entities, generated app.js included) remains a separate historical result on G under `_qa`. It has not been overwritten or rescored. Continue S1–S6 on feature branches; combined merges still require the STOP S6 owner approvals.
