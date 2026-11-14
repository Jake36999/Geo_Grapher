# Phase 8 B0 — S0 graph refresh

2026-11-14. Completed on `codex/phase8-b0-geographer`, based on the approved, unmerged Wave L foundation. Implementation commit: `baf5735`. Native B0 baseline: `54f17b5`; native master pinned for this refresh: `fd070b1f20bd90fef9a200f9bcbc5f0624d409f4`.

## Result and limits

The QA/navigation copy of `librarian-v2` grew from **424 to 29,380 entities**, including **737 entities from staging.py**. The original catalog/stores and the master working tree were not modified. This is an explicit S0 maintenance refresh, not production library setup or an authorship classification decision.

| Graph copied for navigation | Before | After |
|---|---:|---:|
| librarian-v2 | 424 | 29,380 |
| ToolSet | 16,569 | Unchanged |
| ai-research-papers | 1,558 | Unchanged |
| timeline-mapping | 101 | Unchanged |

The stale native profile selected only seven paths. The replacement selects supported files under pinned master `src/`: **146 files, 3,035,864 bytes**. It does not claim a full docs/tests inventory or index Wave L/B0 source changes. Those changes were inspected directly on the feature branches.

The first refresh reached stage 3, status complete, in **61.4593 s**: 28,091 relationships/evidence records and 33,148 documentary incidences. Relationship statuses: 5,197 exact, 3,319 candidate, 19,575 unresolved. These are static extraction facts, not observed runtime execution.

**Partial extraction limitation:** `src/resource_librarian/ui/app.js` produced `FallbackParseError`: Tree-sitter reported syntax errors; no complete fallback facts were published for that file. The failure remains recorded; no parser/product fix was attempted before C0 review.

Graph ID remains `g_1bbebca16afc45c39b2f2f8a`. The old snapshot is retained:

```text
before snapshot:f2bce47cb554c2304bd1e148d8cc1f6e5aa8363c5588cd3bc9912a90351695bc
after  snapshot:4def37051a66c36d47ec14a73f8126d8278c599930828a35a01b9afd1c8fecfb
```

## Space, isolation and evidence

Source: `F:/uv-data/Geo_Grapher/output/named-graphs/catalog.sqlite`. Read-only SQLite backup copied all four graphs into `G:/Libraries/_qa/phase8-b0-20261114/navigation-first/`, rewriting paths only in that copied catalog. Source database payload: **879,534,080 bytes**. Pre-build allowance: **4,100,759,552 bytes** including 3 GiB index headroom; G retained much more than 5 GiB (133,738,721,280 bytes free at the closing check). Bulk stores, temp files and tokenizer caches stay on G.

Evidence root: `G:/Libraries/_qa/phase8-b0-20261114/`:

- `evidence/catalog-before.json`: first baseline.
- `evidence/s0-first.txt` and `navigation-first/s0-result.json`: first refresh, counts, parse failure and snapshot identities.
- `evidence/navigation-queries-first.json`, `navigation-first.txt`, `navigation-exact-followup.json`: graph navigation and exact source follow-ups.

Scoped native graph queries were followed by source witnesses for `closure.operation_class`, `registry._profile_tier` and `McpManager._make_fn`. Top-three fuzzy results did not always rank the exact identifier first; exact qualified/entity follow-ups were used without ranking changes. FolderReview is a feature-branch addition and was inspected there directly.

The copied paper graph also supplied LILO (`ai-research-papers`, `doc:30`) with four outline sections. Coverage is **legacy_unverified**: the stored excerpt has no verified PDF/page grounding. No original PDF was claimed, read or verified. Existing graphs lack the new canonical authorship/domain fields; this is an explicit pre-S1/B2 defect, not an implicit internal classification.

## Reproduction

Run from the Geo B0 worktree. The output directory must be new; do not overwrite the first result. The script rejects outputs outside `G:/Libraries/_qa/` and checks the free-space reserve.

```powershell
$env:TEMP = 'G:/Libraries/_qa/phase8-b0-20261114/temp'
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TIKTOKEN_CACHE_DIR = 'G:/Libraries/_qa/phase8-b0-20261114/cache/tiktoken'
$env:PYTHONPATH = 'G:/Libraries/_qa/phase8-b0-20261114/geographer/src;G:/Libraries/_qa/phase8-b0-20261114/geographer'
& 'F:/uv-data/Geo_Grapher/output/wheel-env/Scripts/python.exe' scripts/phase8_refresh_librarian.py --source-catalog 'F:/uv-data/Geo_Grapher/output/named-graphs/catalog.sqlite' --output 'G:/Libraries/_qa/phase8-b0-20261114/navigation-repeat' --repository 'D:/Librarian_V2' --revision fd070b1
```

No runtime product code changed for S0. The first stale-data baseline preceded the refresh; it is maintenance evidence, not a fabricated failing unit test. C0's new code has separate RED/GREEN evidence in its report. HTTP port 8765 was unavailable; navigation used local supported APIs against the isolated stores, without changing a service or model binding.

**Spend: $0. No paid dispatch, merge, push or tag.** Continue only through the C0 review boundary, then stop for the owner.
