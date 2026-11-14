# Phase 8 B0 — C0 access contract and owner stop

2026-11-14. **OWNER STOP C0: ready for review, before S1 or any access-policy fix.** Updated setup prompt and Part A0 vocabulary take precedence over the older scope document. Wave L is the approved foundation and remains unmerged.

## Review artifacts

| Artifact | Feature-branch location |
|---|---|
| Normative contract, tier table, examples and open decision | `G:/Libraries/_qa/phase8-b0-20261114/librarian/docs/access-model.md` |
| Complete per-tool sweep, actors, tiers, authorship, status and proposed fix | `G:/Libraries/_qa/phase8-b0-20261114/librarian/docs/access-conformance-sweep.md` |
| Native explicit declarations | `G:/Libraries/_qa/phase8-b0-20261114/librarian/docs/tool-access-declarations.json` |
| Geo explicit declarations | `G:/Libraries/_qa/phase8-b0-20261114/geographer/docs/tool-access-declarations.json` |
| Permanent-note template | `G:/Libraries/_qa/phase8-b0-20261114/librarian/docs/library-notes/Content authorship.md` |
| Master owner-decision log | `G:/Libraries/_qa/phase8-b0-20261114/geographer/docs/superpowers/plans/2026-11-11-phase6-7-00-master.md` |

The requested native document is prepared on the feature branch, rather than changing `D:/Librarian_V2` master before merge approval. The permanent note is a template for later approved library setup; it has not been written into live libraries.

## Pre-fix conformance baseline

| Surface | Reviewed | Potential content | Fully conforms | Metadata/control n/a |
|---|---:|---:|---:|---:|
| Native registry | 180 | 98 | **0/98** | 82 |
| Geo MCP | 40 | 38 | **0/38** | 2 |

This measures the **new full Part A0 contract**, including explicit authorship handling. It does not claim that every existing permission boundary fails. Wave L already enforces scoped Clerk configurations, direct third-party graph PLAN_SCOPE checks, graph-qualified provenance, reference-only owner-approved bridges and read-only attached roots. Those partial controls remain recorded in the sweep; they cannot establish full authorship conformance by themselves.

All registrations were reviewed, including potential nested tool results, drafts, plans, materialised content paths and optional paper annotation. Geo's 40 operations comprise seven canonical operations (shared v1.0/v1.1 implementation), 22 scoped operations and 11 standalone-paper operations. Wrappers are counted separately because they change exposure. Native consult/contribute/curate authority is distinguished from model tiers 1/2/3; actor columns record profile/bundle limits, the helper allow-list, worker payloads and the absence of registry tools for Scribe.

The supplemental sweep covers Wave L folder survey/draft/accept HTTP routes, shared inventory, reviewed graph application, generated MCP configurations, the dynamic MCP adapter, read-only guards, dispatch preflight, bridges and credential refusals. Supplemental paths are not pooled into the MCP/registry denominator. No connected Core was used to enumerate live external MCP installations; the generic adapter is explicitly divergent, not a certification of unknown tools.

Fix labels point to S1 authorship/closure, S2/S3 hidden/full conversions, S4 bounded targets and grants, S5 use rollups, S6 attachment indexing, S6b model-card reconciliation and R native-pipeline integration. **None of those product fixes has started.**

## Contract and settled owner decisions

- The vocabulary is `owner_created | generated | third_party`. Accepting generated work does not relabel quoted third-party spans. `own` is only the old shorthand.
- Third-party/unlicensed means others' work studied and cited, never silently incorporated as our own regardless of repository licence.
- A third-party read marks the turn untrusted **for canonical publication**. Reading remains available; resulting writes go through staging/person review. Ordinary and audited closure must both be tested at S1 before implementation.
- Tiers 1/2 may receive scoped one-off raw grants; tier 3 must locate bounded targets. Actual route windows minus prompt/output/reasoning reserves clamp the budgets. The existing result cap is retained. No grant mechanism or model binding was changed at C0.
- `internal` covers owner_created/generated; `external` covers third_party. Unsupported/unclassifiable catalogue objects are not graphed; a graph without a domain is a flagged defect.
- Original 06-Papers PDFs will be supplied later. They remain catalogue_only without verified original pages; internal documentation work continues.
- Graphify is retired; persistent source graphs are permitted. Keep its application/modifications, exclude its outputs later, delete nothing.
- The research folder is `E:/Librarian research`. D4 colours and exclusive network_management assignments remain decisions for later stops.

## RED/GREEN and regression evidence

Evidence directory: `G:/Libraries/_qa/phase8-b0-20261114/evidence/`. Every first result remains present.

| Check, in execution order | First result | Final result / action |
|---|---|---|
| Native access declaration tests | 3 failed before implementation (`native-access-red.txt`) | Guard implemented; final regression includes 4 new guard tests |
| Geo access declaration tests | 3 failed before implementation (`geo-access-red.txt`) | Guard implemented; final regression includes 5 new guard tests |
| First inventory build | Native MCP 2.x could not import Geo's MCP 1.x server | Separate existing interpreters used; no dependency changes |
| Initial scoped discovery | 18 operations found; FastMCP public manager omitted 22 protocol tools | New protocol-handler test failed (1 failed/3 passed); discovery fixed to actual ListToolsRequest handler |
| Native regression first | 1 failed / 71 passed: external registration test fixture omitted external=True | Corrected fixture, no Registry production change; intermediate 72 passed retained |
| Final native targeted regression | — | **73 passed in 23.09 s** (`native-c0-regression-final.txt`) |
| Geo targeted regression first | — | **34 passed in 5.12 s** (`geo-c0-regression-first.txt`) |
| Final auditors | — | Native 180/98 content, Geo 40/38 content; both report problems=[] |

The guards fail on undeclared new tools, including an injected real scoped-protocol tool and an externally registered native tool. Native source/schema fingerprints invalidate stale reviews after implementation/tier changes. These are automatic pytest tests with no wildcard approval. They prove **declaration coverage**, not runtime policy enforcement or full conformance. Runtime dynamic tools still need per-install policy declarations when that surface is wired.

No runtime product modules were changed by C0. The targeted regressions cover declaration guards plus native Registry/MCP/dispatch/folder review and Geo credential/inventory/third-party/folder grouping. Full suites/browser checks were not rerun for this documentation/CI step. Wave L's 802 Geo / 2,279 native passes remain historical results, not new C0 measurements; S6 requires fresh full suites.

## Reproduction commands

Use a neutral directory for native tests, outside any `.librarian`. All disposable output is on G; select a fresh basetemp directory if rerunning. Commands below use the existing native MCP 2.x interpreter and the separately pinned Geo MCP 1.30 environment. They make no model calls.

```powershell
Set-Location F:/uv-data
$env:TEMP = 'G:/Libraries/_qa/phase8-b0-20261114/temp'
$env:TMP = $env:TEMP
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TIKTOKEN_CACHE_DIR = 'G:/Libraries/_qa/phase8-b0-20261114/cache/tiktoken'
$env:PYTHONPATH = 'G:/Libraries/_qa/phase8-b0-20261114/librarian/src'
& 'D:/Librarian_V2/.venv/Scripts/python.exe' -m pytest -q 'G:/Libraries/_qa/phase8-b0-20261114/librarian/tests/test_access_declarations.py' 'G:/Libraries/_qa/phase8-b0-20261114/librarian/tests/test_registry.py' 'G:/Libraries/_qa/phase8-b0-20261114/librarian/tests/test_mcp.py' 'G:/Libraries/_qa/phase8-b0-20261114/librarian/tests/test_plan_dispatch.py' 'G:/Libraries/_qa/phase8-b0-20261114/librarian/tests/test_folder_review.py' --basetemp='G:/Libraries/_qa/phase8-b0-20261114/temp/native-repeat'
& 'D:/Librarian_V2/.venv/Scripts/python.exe' 'G:/Libraries/_qa/phase8-b0-20261114/librarian/scripts/audit_tool_access.py'

Set-Location 'G:/Libraries/_qa/phase8-b0-20261114/geographer'
$env:PYTHONPATH = 'G:/Libraries/_qa/phase8-b0-20261114/geographer/src;G:/Libraries/_qa/phase8-b0-20261114/geographer'
& 'F:/uv-data/Geo_Grapher/output/wheel-env/Scripts/python.exe' -m pytest -q tests/test_access_declarations.py tests/test_wave_l_credentials.py tests/test_wave_l_inventory.py tests/test_wave_l_third_party.py tests/test_folder_groups.py --basetemp='G:/Libraries/_qa/phase8-b0-20261114/temp/geo-repeat'
& 'F:/uv-data/Geo_Grapher/output/wheel-env/Scripts/python.exe' scripts/audit_tool_access.py
& 'D:/Librarian_V2/.venv/Scripts/python.exe' scripts/phase8_build_access_inventory.py --native-root 'G:/Libraries/_qa/phase8-b0-20261114/librarian' --geo-root 'G:/Libraries/_qa/phase8-b0-20261114/geographer' --geo-python 'F:/uv-data/Geo_Grapher/output/wheel-env/Scripts/python.exe'
```

The inventory builder reproduces the pre-fix census artifacts on these branches; it is not a post-fix policy certifier. S0 reproduction and graph evidence are in `PHASE8_B0_S0_REPORT.md`.

## Commits and owner decision

| Repository | Branch | C0/S0 commit | Foundation retained |
|---|---|---|---|
| Librarian | codex/phase8-b0-librarian | `869dad5` | `54f17b5` |
| Geo-Grapher | codex/phase8-b0-geographer | `baf5735` | `495d689`, `4e773a2` |

Original Geo main remains `a6ad30f`; native master remains `fd070b1`. No merge, push, tag, paid evaluation, model binding change, live-library ingest or credential read. Spend **$0**. These reports are separately committed as evidence after the implementation commits above. Prior result rows and Wave L history are retained.

**OWNER STOP C0 — requested decisions:**

1. Approve the contract and reviewed sweep before S1, including the third-party untrusted mark as a canonical-publication/staging boundary, not a reading ban?
2. Does the Clerk's intended 200k–500k bounded reading allocation mean **tokens or characters**? Route clamping applies either way.

No access-policy fixes proceed until this review is answered. Combined Wave L+B0 merges remain a later, separate STOP S6 approval for each repository.
