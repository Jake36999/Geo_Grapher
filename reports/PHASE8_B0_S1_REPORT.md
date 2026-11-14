# Phase 8 B0 S1 — central authorship/publication boundary

2026-11-14. Owner-authorised continuation after the closure stop. **S1 implemented and verified; continue to S2, with the next owner stop still S6.** No merge/push/tag or paid dispatch.

## Candidate and results

| Repository | Candidate | Verification |
|---|---|---|
| Librarian | `188abac`, source-authority refinement `bccb67b` on codex/phase8-b0-librarian | Final full suite **2,329 passed / 2 skipped / 5 deselected**, 530.59 s |
| Geo-Grapher | `ff60250` on codex/phase8-b0-geographer | scripts/verify.ps1 exit 0: full backend, frontend typecheck/build/unit, browser, wheel, installed presets/caps |

Geo backend collection is 828; the successful full run has **826 passed / 2 skipped** (both skip markers in its progress). Browser JSON: **17 expected, 0 unexpected, 0 flaky**. Installed wheel: **28 preset/cap calls, no failures**. Quiet-machine C14 was deliberately not run while suites/builds were active; its prospective gate remains opt-in.

Wheel: `G:/Libraries/_qa/phase8-b0-20261114/verify-s1-first/dist/geo_grapher-0.2.0-py3-none-any.whl`, SHA256 **0870afe1b8f038a3d2bf85891955d9d833479538400e699cbff17cd1ef807739**. This is a feature candidate, not an approved merged release.

Native UI: free browser contract passed (purpose-derived authorship, no default for data/logs, explicit submission); TypeScript check/build passed. This is a focused fixture test, not the final S6 integrated demonstration.

## What changed

The policy lives once in native `access.py`, called by Registry.call before publication and at the result boundary, plus Geo's shared provenance projections. It was not copied into 98 tool bodies. Tool-specific metadata plumbing is limited to generated Application records, source-authority context for helpers, and the person-only checkpoint tool. Existing phase/scope/permissions remain independent gates.

- **T1:** after taint, every effect=vault_write, _PROMOTE/_PUBLISH class and project_edit is gated. Reads, staging and effect=write work state stay available. record_application remains allowed; its free text is stored as **generated**, with taint_sources in frontmatter. Its receipt remains class C; it is not scored as content.
- **T2:** source handles are persisted in session events. Turns, park/resume and branches retain them. New sessions start clear; legal rewind before the taint removes it, preserving existing rewind barriers. Exact-source person checkpoints clear it once. Legacy untrusted/open-world histories retain opaque handles on replay; legacy person calls are exempt. Sessionless helpers propagate source handles to their publication session without receiving its conversation or session tools.
- **T3:** COMPOSITION_REFUSED names sources and stage_artifact/staging. A fresh broker ask may authorise the exact publication, showing sources; Auto mode, old session grants and mode switches cannot release that review. Tainted project_edit includes the exact owner warning. A source-set change invalidates an in-flight approval. Person callers are unaffected. Checkpoint approval through the real person API applies the scoped clear; replayed/stale approvals cannot clear later sources.
- **T4:** unknown external MCP defaults to untrusted/open-world; an external self-assertion is ignored. Operator Geo authority is acceptance-digest-bound. Geo-owned provenance is projected centrally, including mixed/unclassified graphs. Unknown internal source authorship is flagged and cannot grant publication trust. A generated/owner-curated catalogue note does not prove ownership of the repository it describes: legacy read_source_file aliases remain explicitly unclassified; use typed Geo provenance for trusted own-code reads.
- Folder purposes derive the closed authorship vocabulary, and child overrides replace parent classification. data/logs require an explicit choice; exclude has none. Roots, cards, evidence metadata and DIK Data carry authorship; model-produced DIK is generated while retaining source_authorship. Authorship changes are bound into new evidence identities/integrity checks; old records remain readable.
- Geo canonical v1.x body schemas remain stable: MCP transport _meta.access carries provenance. Scoped/standalone paper projections carry source authorship; unclassified historical graphs are flagged. The native adapter preserves trusted transport metadata while retaining the existing content cap.
- The cap's unit mix is documented: 12% of a context setting in tokens is applied as a character cap. No behavior changed; S4 must state its explicit conversion basis and measure actual route allocations/output capacity.
- A4 excludes generated native UI JS/bundle/build outputs before source reads and indexing; TypeScript source remains selected. The approved live refresh is separately reported at PHASE8_B0_LIVE_REFRESH_RESULT.md.

## Per-class metric

These are **S1 authorship-boundary conformance**, not full S4 access conformance or a claim that every historical object already has resolved ownership. A truthful unclassified flag that cannot grant trust is required for undeclared legacy inputs; it is not silently counted as owner_created. The complete original C0 sweep and first class baseline remain in their reports/commits.

| Surface | A authorship boundary, S1 | A full access, due S4 | B authorship, S1 | C |
|---|---:|---:|---:|---:|
| Native shipped registry (181) | **90/90** | **0/90** | **12/12** | n/a (79) |
| Geo MCP operations (40) | **37/37** | **0/37** | **3/3** | n/a (0) |
| Unknown external adapter, supplemental | **1/1** | **0/1** | — | — |

The new native tool is clear_session_taint, person-only C. Existing C0 control/metadata declarations are preserved; their older whole-contract status is not repurposed as this new per-class metric. Unknown live external installations are not enumerated or individually certified. Supplemental Folders metadata carries generated description versus accepted source authorship; production drafting remains off pending the R qualification/provenance gate. Legacy unclassified graphs/aliases remain data defects to resolve through accepted cards/typed provenance, not fabricated classifications.

## First results retained

All evidence remains under `G:/Libraries/_qa/phase8-b0-20261114/evidence/`, including every failing first result. No historical result row was overwritten or rescored.

| Run | First result / outcome |
|---|---|
| Original closure prerequisite | 3 failed / 1 passed; triggered the owner stop |
| Owner-expanded T1–T4 RED | 11 failed / 1 passed |
| A4 RED | Geo 2 failed; native 1 failed |
| Geo authorship projection RED | 7 failed |
| Native authorship RED | 8 failed / 1 passed |
| Additional source, checkpoint, helper, legacy-replay and mixed-provenance guards | Individual RED artifacts retained; corresponding targeted GREEN runs passed |
| Geo full first | 1 failed / 51 passed / 1 skipped: added metadata exhausted a small envelope; fixed by avoiding redundant per-node unknown metadata |
| Geo full second | 1 failed / 91 passed / 1 skipped: missing feature-worktree frontend build; built it on G |
| Geo full third | 816 passed / 2 skipped, before remaining transport/refresh tests |
| Geo final full verify | Exit 0, 826 passed / 2 skipped; frontend/browser/wheel/presets all passed |
| Native full first | 1 failed / 7 passed / 1 skipped: person/control receipt shape |
| Native full second | 1 failed / 57 passed / 1 skipped: declaration guard correctly required review updates |
| Native full third | 1 failed / 93 passed / 1 skipped: old test iterated the new envelope as task buckets |
| Native full fourth | 13 failed / 2,292 passed / 3 skipped / 5 deselected; each inspected, with receipt assertions, rename preservation and fixture ownership corrected |
| Native regression of those cases | 150 passed / 1 skipped |
| Native full candidate 188abac | 2,327 passed / 2 skipped / 5 deselected |
| Source-authority RED then targeted GREEN | 2 failed, then 34 passed; catalogue authorship cannot promote original code |
| Native final bccb67b | **2,329 passed / 2 skipped / 5 deselected** |

Two diagnostic regression runs were terminated after waiting for person approval: unclassified source reads correctly triggered the new gate, exposing missing generated-note attribution/fixture ownership. The first browser smoke also had an incomplete fixture (missing bytes/file_counts); it was retained, corrected, then produced a real missing-control RED before implementation. A targeted command with a mistaken test_delegate.py path ran no tests; its corrected selections and the full suites are the evidence, not that command. No failure was relabelled a pass.

## Reproduction and artifacts

Native full suite from neutral F:/uv-data, PYTHONPATH set to the G: feature src, TEMP/TMP on G:

```powershell
& 'D:/Librarian_V2/.venv/Scripts/python.exe' -u -m pytest -q -o faulthandler_timeout=40 'G:/Libraries/_qa/phase8-b0-20261114/librarian/tests' --basetemp='G:/Libraries/_qa/phase8-b0-20261114/temp/s1-native-repeat'
```

Geo feature worktree, pinned MCP 1.30 environment, dependencies linked read-only for reuse, caches/temp on G:

```powershell
./scripts/verify.ps1 -GateOutput 'G:/Libraries/_qa/phase8-b0-20261114/verify-s1-repeat'
```

Use fresh output directories. Native evidence: `s1-full-native-final-first.txt`, `s1-full-native-source-origin.txt`. Geo step results: `verify-s1-first.txt`; full suite progress was also returned by the command session; collection cross-check `geo-s1-test-collection.txt`. Browser JSON: `geographer/output/integrated-workspace/browser-results.json`; installed preset evidence: `verify-s1-first/presets-first.json`. Native UI smoke artifacts: `ui-authorship-red*`, `ui-authorship-green`; model/network use was mocked.

**Spend $0.** Original masters and frozen Wave L/parked branches were not modified. Live data publication was the separately approved native snapshot refresh, not a merge or deployment of B0 runtime policy. S2 conversion RED preparation already shows the old sibling-write/cache problem; no S2 product change preceded this verified S1 candidate.
