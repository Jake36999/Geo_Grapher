# F4 — 0.2.0 owner acceptance (prepared, not executed)

**OWNER STOP.** Review the [draft release notes](../docs/phase67/RELEASE_0_2_DRAFT.md), migration guide and Known Limitations. The [six-task pilot was attempted and failed](PHASE67_LIVE_PILOT_20261114.md); this checklist does not establish successful coordination. Role screening was fresh for the pilot configuration, and restoring the normal MCP registry invalidated its fingerprints. The three questions below are owner-run production-route acceptance, not another evaluation cycle. Codex has made no paid calls.

Exact reviewed wheel SHA256: **`4d903d7df0cb029e332b8bff1e076b122d40dabe8dfab765aaf7615bfcc4450d`**. Full artifact/test evidence is in [PHASE67_F3_RELEASE_EVIDENCE.json](PHASE67_F3_RELEASE_EVIDENCE.json).

## Fresh-copy preparation, before starting the 20-minute clock

Use PowerShell from `F:/uv-data/Geo_Grapher`. The source catalog below is the preserved real-store corpus used for application QA; all browser writes must target the new copy. Choose a free port (8790 below). If the destination already exists, choose a new destination: do not overwrite or delete it. Allow time and about 5 GB for the copy.

```powershell
Set-Location F:/uv-data/Geo_Grapher
$releaseWheel = 'F:/uv-data/Geo_Grapher/output/phase67-release/f3/verify-corrected/dist/geo_grapher-0.2.0-py3-none-any.whl'
$acceptRoot = 'D:/Librarian_V2/tmp/geo-grapher-qa-workspaces/owner/20261114-acceptance-0.2.0'
Get-FileHash -LiteralPath $releaseWheel -Algorithm SHA256
# Compare with PHASE67_F3_RELEASE_EVIDENCE.json before continuing.
uvx --from $releaseWheel python scripts/qa_cleanup.py --root D:/Librarian_V2/tmp/geo-grapher-qa-workspaces --apply
if ($LASTEXITCODE -ne 0) { throw 'QA retention check failed' }
uvx --from $releaseWheel python scripts/qa_real_store_prepare.py `
  --catalog D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/catalog.sqlite `
  --out $acceptRoot
if ($LASTEXITCODE -ne 0) { throw 'Copy preparation failed; preserve the attempt' }
# The preparation helper creates a picker-test junction. Remove only that link entry.
uvx --from $releaseWheel python -c "import os,sys,stat; from pathlib import Path; p=Path(sys.argv[1]); q=p/'browse/junction'; assert p.resolve()==p and q.parent.resolve()==p/'browse' and q.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT and q.resolve()==p/'outside-browse'; os.rmdir(q)" $acceptRoot
if ($LASTEXITCODE -ne 0) { throw 'Fixture link check failed' }
uvx --from $releaseWheel geographer serve-graphs `
  --catalog "$acceptRoot/catalog.sqlite" --transport http --port 8790 `
  --browse-root "$acceptRoot/browse" --max-result-chars 7500
```

Open **http://127.0.0.1:8790/**. This is the production HTTP surface, not the QA-only server with a cleanup route. The fresh unmarked owner copy is protected from automatic retention deletion. Stop the server you started when finished; preserve the copy and your findings. Do not point the command at canonical stores. No semantic flags are supplied: this exercises the default lexical-only configuration.

## 20-minute hands-on checklist

| Time | Action and acceptance evidence |
|---|---|
| 0–2 | Confirm 0.2.0 wheel hash and chosen disposable catalog. Open ToolSet, switch to Librarian, inspect labels, role badges and source details. Record selected snapshot IDs. |
| 2–6 | Spatial view → atomic grouping and exact static relationships. Try Helper balls, then Directed. Check rendered blocks and certificate, expand one block, inspect a directed witness, then switch Off and confirm restoration. Existential reachability does not mean every member reaches every member. |
| 6–10 | Add folder → `project` under the allowed browse root → preview → untick one partition → ingest. Observe the completed job and new graph. Confirm outside paths are refused and originals remain present. |
| 10–13 | Box-select a small ToolSet region and prune into a derived graph. Check its provenance, excluded region and unchanged source snapshot. |
| 13–16 | Select Librarian and its related survey worktree. Find bridge candidates; inspect source evidence. Accept only a justified candidate with rationale; reject an unrelated one. If none is justifiable, record that rather than creating a false accepted bridge. Inspect resulting state and repeat-decision refusal. |
| 16–20 | Through Resource-Library's normal production lead route, ask one question below. Open its cited handles/source; record actual omissions or failure. Other two questions can follow after the timed UI session. |

Record elapsed time, unexpected errors and any screenshots/handles privately. Automated passes do not replace this sign-off.

## Three questions through the Resource-Library production route

Use the existing **Resource-Library** configuration and its normal configured lead, not a benchmark model. The temporary Gemma pilot lead was restored afterward: the original Seed-2.0-mini route currently returns `InvalidEndpoint.ClosedEndpoint`. Select an available lead and verify qualification against the final MCP configuration before these owner questions; do not count a substituted route as the original one. Check Core status first; start the library through its usual UI/host if needed. Do not take over a live/stale lease automatically. Do not rebind providers or qualify helper routes as part of this checklist. For code, select `code-research` and confirm temperature **0.2**, FP4 **off**; customised profiles need explicit inspection. No helper delegation is needed.

Attach the exact 0.2.0 wheel through the library's MCP settings with a **stdio** server, `GEOGRAPHER_CATALOG` set to the fresh acceptance catalog, result cap 7500 and explicit allowed graphs. Choose the appropriate six-tool preset for each question. Preserve the existing production provider binding. The HTTP workspace uses the same catalog, so returned canonical handles can be checked against the same snapshots.

| Type / preset | Question | What to check |
|---|---|---|
| Paper / `papers`, ai-research-papers | “In LILO, what does documenting a learned library add beyond compressing code, and what evidence does the paper give for that benefit?” | Retrieve the actual LILO document (currently doc:30 in this copy), open claims/sections and cite the returned `ai-research-papers/doc:N` handle. Separate the paper's claims from inference; no invented experiment or prior-knowledge filler. |
| Code / `code`, librarian-v2 | “How does Librarian decide whether an MCP tool result is too large for the active route, and what does the user or agent receive when it is withheld?” | Open defining source and its caller, preserve canonical IDs/line spans, distinguish route context from character limits and cite source that directly supports the explanation. Inspect omissions and exact configuration; do not accept a nearby constant alone as proof. |
| Cross-graph / `cross`, librarian-v2 + ToolSet | “Compare how Librarian and ToolSet register and expose tools. Where are their boundaries similar, and where do they differ?” | Explicitly search both graphs, cite original source from each, keep graph labels separate, and avoid turning name overlap, a candidate bridge or proximity into a dependency/equivalence claim. A missing mechanism should be reported as missing. |

If a route is unavailable, record **blocked**; do not substitute another model or count a no-model fixture as a live answer. These owner questions may use the owner's normal provider budget. No agent-run paid check or additional benchmark cycle is authorised here.

## Owner record and release decision

- [ ] UI checklist completed; findings recorded.
- [ ] Paper, code and cross-graph questions completed or explicitly accepted as blocked limitations, with cited handles checked.
- [ ] Migration/backups and optional local-only semantic instructions reviewed.
- [ ] Known Limitations accepted, including the now-failed pilot, changed FP4 default after measurement, registered gate FAIL and untested real-usage population.
- [ ] Draft release notes approved, or requested edits listed.

Owner / date / decision: **pending**.

**No tag or push is included in this approval.** Instruct Codex separately if and when to create `geo-grapher-v0.2.0` and/or push specific branches/tags. Parked WIP stays frozen; keep pre-rebase backups until after release.
