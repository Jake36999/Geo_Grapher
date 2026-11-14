# Phase 8 B0 — S1 closure prerequisite: OWNER STOP

2026-11-14. **Stopped as instructed: ordinary-session closure is not covered.** No S1 product fix or later B0 step has run. C0 approval, tokens decision and A1–A5 are recorded in the master decision log and the feature-branch access contract.

## First RED result

**3 failed / 1 passed in 1.18 s**, before any implementation change. The four cases use the real Registry.call boundary, session hooks and write_note in disposable fixture vaults. Each reads successfully twice, then attempts a canonical write to Notes/out.md. There is no network/model call and no real library write.

| Source | Session | More reading | Expected canonical write | Actual canonical write | Result |
|---|---|---|---|---|---|
| Known open-world reader (read_url with fixture fetcher) | Audited, executing contract | Allowed | Refuse COMPOSITION_REFUSED | Refused; no file | PASS |
| Same known open-world reader | Ordinary explore session | Allowed | Refuse COMPOSITION_REFUSED | **File created** | FAIL |
| Unknown external MCP-style result, wrapper untrusted=True | Audited, executing contract | Allowed | Refuse COMPOSITION_REFUSED | **File created** | FAIL |
| Same unknown external result | Ordinary explore session | Allowed | Refuse COMPOSITION_REFUSED | **File created** | FAIL |

The unknown external case registers a fixture ToolSpec through the real Registry.register boundary with the adapter's current default semantics: external=True, effect=read, open_world omitted. It does not connect a real external server or claim an end-to-end live MCP test. Its returned untrusted=True wrapper is intentionally the same flag the current adapter supplies. Registry state is restored by monkeypatch; the fixture cannot leak into another test or live Core.

Evidence: `G:/Libraries/_qa/phase8-b0-20261114/evidence/s1-closure-first.txt`. Test: `G:/Libraries/_qa/phase8-b0-20261114/librarian/tests/test_phase8_closure_boundary.py`. The first failing output is retained, not rerun into a claimed pass. A copy is committed beside this report as `PHASE8_B0_S1_CLOSURE_FIRST.txt`.

## Cause and required next work

- `src/resource_librarian/closure.py:331–332` returns None outside audited execute. The composition check at lines 388–390 therefore does not protect an ordinary session.
- `src/resource_librarian/mcp_client.py:448–458` registers external tools without open_world=True. Closure classifies read operations from that declaration, not the returned untrusted wrapper. Even the audited path therefore treats the unknown external fixture as a trusted read.
- Existing audited protection is contract-scoped history, not evidence of an ordinary-turn result boundary. It must not be relied on to claim the approved general publication guarantee.

On owner instruction to resume, implement A1 centrally: resolve result authorship at Registry.call/result envelopes and Geo's provenance projection, persist publication taint across the relevant ordinary/audited turn, default unknown external content to untrusted, and refuse canonical publication after it while allowing further reads and staged/person-reviewed work. Trusted Geo graph provenance must classify owner_created/generated as read and third_party as untrusted; an unknown server's self-assertion must not grant trust. Add ordinary/audited staging, person-review, resume/reset and mixed-provenance tests before relying on the new boundary. No per-tool duplication across 98 content tools.

This report requests review first, as required by the owner's conditional stop. It does not silently choose the lifetime/reset semantics of a new taint state or implement the fix while asking.

## Class triage at this stop

The complete companion table and per-tool JSON are in feature-branch `docs/access-s1-triage.md` and `docs/access-s1-triage.json`. Original C0 tables/rows remain unchanged. Conservative A includes nested/free-form/generated results and materialised content paths with possible text exposure; narrower metadata sub-results may later be split after source review. B now includes metadata reads excluded from C0's original text denominator; these are deliberately different metrics.

| Surface | A authorship conforms (S1) | A full access conforms (S4) | B authorship conforms (S1) | C person/control |
|---|---:|---:|---:|---:|
| Native, all 180 registrations | 0/90 | 0/90 | 0/12 | n/a, 78 |
| Geo, all 40 operations | 0/37 | 0/37 | 0/3 | n/a, 0 |
| Unknown external adapter, supplemental | 0/1 | 0/1 | — | — |

The supplemental Wave L folder survey/draft/accept and shared inventory metadata remain B pending canonical authorship propagation in S1/R. They are separate from the 180/40 registry/MCP totals. Unknown live external installations are not enumerated/certified. Existing L4/L5 protections are retained; no new full-conformance credit is claimed. **S1 acceptance is not met.**

## Decisions recorded, implementation deferred

- The contract/sweep are approved, including third-party-read taint for canonical publication, never a reading ban.
- Tier-3 allocation means **tokens**, clamped to the actual bound route's declared window minus measured prompt plus visible output and reasoning reserves. S4 must also bound/split deliverables against visible output: current Clerk 1,800 tokens was the pilot constraint. Effective route allocations are not yet measured or implemented.
- A5's unit mix is documented: 12% of a token context setting is applied as a character limit, with no explicit characters-per-token basis. Behavior remains unchanged pending S4.
- A4 generated-bundle hygiene is approved but not implemented because this prerequisite triggered the stop. The app.js FallbackParseError is **still present in the S0 QA snapshot**. It will be resolved by generated-output exclusion and ui/src TypeScript ingestion, not by claiming a parser fix.
- No conversion, grant, live graph refresh, model binding, qualification, paid dispatch, source-tree cleanup or later S2–S6/R/B2/Part C work was performed.

## Reproduction

Neutral working directory, fixture output on G, no model/network:

```powershell
Set-Location F:/uv-data
$env:PYTHONPATH = 'G:/Libraries/_qa/phase8-b0-20261114/librarian/src'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = 'G:/Libraries/_qa/phase8-b0-20261114/temp'
$env:TMP = $env:TEMP
& 'D:/Librarian_V2/.venv/Scripts/python.exe' -m pytest -q 'G:/Libraries/_qa/phase8-b0-20261114/librarian/tests/test_phase8_closure_boundary.py' --basetemp='G:/Libraries/_qa/phase8-b0-20261114/temp/s1-closure-repeat'
```

Use a new basetemp for further runs to retain the first fixtures. The test's three failures are deliberate regression specifications awaiting the owner review and implementation; the feature branch is not an all-green merge candidate. No full suite was run after this early mandatory stop. Prior C0 73/34 and Wave L results remain historical, separate results.

## Branches and next owner decisions

- Librarian: `codex/phase8-b0-librarian` **a8ab863**, C0 amendments + class triage + first RED tests; no runtime source change.
- Geo: `codex/phase8-b0-geographer` **cd3d938**, owner decision log; evidence follows as a separate commit.
- Both original mains and the approved Wave L foundations are unchanged. No merge, push or tag. **Spend $0.**

**OWNER:** review the uncovered ordinary/unknown-external closure paths and authorise resuming S1 with the central remedy above. The independent live-hub refresh proposal is in `PHASE8_B0_LIVE_REFRESH_PROPOSAL.md`; no live mutation has occurred.
