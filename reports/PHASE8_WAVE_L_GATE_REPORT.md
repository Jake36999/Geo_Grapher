# Phase 8 Wave L — OWNER STOP L

Date: 2026-11-14. Scope: Part B, L1–L5, of `2026-11-14-library-setup-CODEX-PROMPT.md`. No real-library setup, paid call, merge, push or tag was performed. This report records a feature candidate, not a release or a live-pilot pass.

## Candidate and isolation

| Repository | Baseline | Local feature branch | Product commit |
|---|---|---|---|
| Geo-Grapher | main `a6ad30f5bce11b3d2306b3091ea55eebf32c53f7` | `codex/phase8-wave-l-geographer` | `495d68945eab3c89482c726fcfe877d1c14e223b` |
| Librarian | master `fd070b1` | `codex/phase8-wave-l-librarian` | `54f17b5a143c450fd5f6bb3d4258d4bce818bc40` |

Worktrees and all new bulk artifacts are under `G:/Libraries/_qa/phase8-wave-l-20261114/`. The original checkouts and parked branches were not edited. Claude's prompt and new scoping reports were read, not staged or changed.

Initial tracked-checkout estimate: 38,448,619 bytes. Initial G free: 142,784,770,048 bytes. The first 4 GiB planning allowance was revised as repeated full suites retained independent fixtures; G still had 135,409,373,184 bytes free near the final checks, far above the required 5 GiB. No old D: QA copies were deleted. Four tokenizer cache aliases generated during setup were moved, with SHA256 verification, into the G: cache; original tokenizer assets remain byte-identical. See `evidence/tokenizer-cache-relocation.json`.

## What L1–L5 deliver

| Item | Implementation and evidence |
|---|---|
| L1 | Native attach planning and compare-and-apply share a metadata inventory with the installed Geo wheel through CLI stdin. Both plans carry the native survey fingerprint. No second planning walk; changed group members and incomplete surveys refuse application. Disabled mode has an explicit regression test. `tests/test_wave_l_shared_survey.py`, `tests/test_folder_review.py`, Geo `tests/test_wave_l_inventory.py`. |
| L2 | Native **Staging → Folders** shows counts, bytes, purpose, reasons, graph and a visibly unaccepted draft. Acceptance is person-only. Actual shared graphs retain independent repository namespaces; existing owned project graphs can be selected by unique label. Unchanged complete snapshots are reused. Accepted child overrides affect indexing, watching and writes; attached projects always stay read-only. Changed cards re-stage. Excluding an empty group hides its graph without deleting snapshots. `tests/test_folder_review.py`, Geo `tests/test_folder_groups.py`, `ui/folders-smoke.mjs`. |
| L3 | Conservative suggestions cover third-party folder patterns, nested Git, licence presence, PDF dominance and bulk data; binary/backup/log, empty-folder, sidecar, test-result and superseded graphify paths are excluded. Reasons remain visible; no suggestion accepts itself. Nested Git ownership is marked unconfirmed without reading remote URLs, which can contain credentials. Geo `tests/test_wave_l_inventory.py`. |
| L4 | Bronze external strata; preflight `PLAN_SCOPE` for tier-3 tasks; scoped Clerk configurations exclude third-party graphs; server and flat-call profile enforcement; graph-qualified provenance on final agent hits, packets and federation; answer scope flags; reference-only owner-decided bridges; typed read-only refusal in native tools and writer. Five installed-wheel no-model fixture checks pass. Geo `tests/test_wave_l_third_party.py`, native `tests/test_wave_l_plan_scope.py`, `qualification-frozen/results.json`. |
| L5 | Path-only refusal before survey counting, extraction and ingestion, including explicit credential-directory roots. Direct file intake, project reads, public vault paths, static scans, Git ingestion and paper entrypoints are guarded. Git lists metadata then fetches approved blobs, replacing its whole-tree archive. Fixtures contain synthetic data only. Both `tests/test_wave_l_credentials.py` modules. |

The existing v1.1 normative contracts and W3-5 firewall were not changed. Provenance is added to routing/agent projections and task packets rather than changing strict v1.1 node schemas.

## Final verification

| Check | Result | Retained evidence |
|---|---|---|
| Geo complete backend suite | 802 passed, 2 skipped; 13 warnings | `evidence/geo-full-fifth.txt` |
| Librarian complete suite, neutral F:/uv-data | 2,279 passed, 2 skipped, 5 deselected | `evidence/native-full-fifth.txt` |
| Geo frontend typecheck and build | passed | `evidence/geo-typecheck.txt`, `evidence/geo-frontend-build.txt` |
| Geo frontend unit suite | 16 passed | `evidence/geo-unit.txt` |
| Geo browser suite, disposable stores | 17 passed | `evidence/geo-browser-first.txt`, `evidence/geo-browser-results.json` |
| Native UI typecheck/build | passed | `evidence/native-ui-build-second.txt` |
| Native broad browser smoke | 56 checkpoints passed, first and frozen-candidate runs | `evidence/native-ui-smoke-first.txt`, `evidence/native-ui-smoke-final.txt` |
| Folders browser journey, frozen native code | passed: draft, metadata, grouped suggestion, acceptance, reload persistence, stale refusal, re-survey retention | `evidence/folders-browser-frozen.txt`, `evidence/browser-frozen/trace.zip` |
| Installed-wheel presets and size caps | 28/28 calls on first, intermediate and reviewed wheels | `evidence/presets-first.json`, `evidence/presets-final.json`, `evidence/presets-reviewed.json` |
| Installed-wheel L4(a)–(e), frozen code | 5/5 passed; 2 graphs; 0 packet calls/0 model calls on rejected plan | `qualification-frozen/results.json`, `qualification-frozen/accepted-cards.json` |

The fixture has two supported source files (one own, one third-party), two accepted cards, two graphs and one synthetic `Frank.env` refusal. The source files remain in the disposable attached source tree; graph and native state stay inside the fixture library on G:.

The Folders screenshot descriptions are explicitly scripted QA drafts: no paid Clerk drafting is claimed. Production drafting requires separate approval and the existing qualified Clerk route; it sends only bounded inventory metadata.

## First results and failures — retained, not replaced

| First result | Resolution / preserved row |
|---|---|
| Geo credential RED: 4 failed; native credential RED: 2 failed | Guards implemented; subsequent credential and survey checks pass. |
| Two initial GREEN commands referenced nonexistent test filenames: zero tests collected | Actual commands corrected; both original logs retained. |
| Geo inventory RED: 4 failed; native shared-inventory RED: 1 failed, 1 disabled-mode pass | Shared inventory and explained suggestions implemented. |
| Three original workspace assertions failed because PDFs now get a separate partition | Expected partition/file/graph counts updated deliberately. |
| Geo boundary RED: 5 failed; native scope RED: 2 failed | Boundaries implemented. Missing worktree tokenizer assets and frontend build also caused 12 failures in the first broader attempt; prerequisites repaired. |
| Folder review RED: 5 failed; child-card RED: 1 failed | Native staged review and inherited child cards implemented. |
| Geo full first: 43 failed, 725 passed, 2 skipped, 21 errors | All failures/errors traced to CRLF conversion of 11 source-locked fixtures; exact Git blobs restored, source lock and oracle answers unchanged. Follow-up: 79 passed, 2 skipped. `.gitattributes` now pins these fixtures and tokenizer weights to LF. |
| Native first complete suite: 2,268 passed, 2 skipped, 5 deselected | Earlier candidate, preserved as its own result. |
| Geo second complete suite: 798 passed, 2 skipped | Earlier candidate, preserved. |
| Direct side-effect, empty-size, scoped-config, root-refusal, final-answer and readonly RED cases | Separate failing logs retained before each fix. |
| First broad native structure run: 1 failed, 60 passed | Existing `.env.example` expectation removed because credential-like templates must now be refused before reading; environment names from safe source code remain available. |
| First browser command used button instead of the existing tab role | Locator corrected. The next RED correctly failed on missing Folders; implementation then passed. Both rows retained. |
| First two-graph qualification: second acceptance failed with duplicate immutable snapshot | Added failing idempotency test; complete matching snapshots now reuse their identity. |
| Second qualification: installed package was imported under another interpreter prefix, so bundled resources were unavailable | Harness corrected to run under the installed wheel's own interpreter; no product resource workaround. |
| Third qualification: final flat-search projection stripped provenance | Added RED final-projection test and re-annotated after projection, before token/cap counting. Later qualification passes all five points. |
| Native second complete suite: 2,275 passed, 2 skipped, 5 deselected; Geo third: 799 passed, 2 skipped; Geo fourth: 801 passed, 2 skipped | Each is a separate earlier-candidate row. |
| Accepted-child scope tests: 2 failed | Index, watcher and deepest accepted access now agree; typed `FOLDER_READ_ONLY` registered rather than relying on an exception containing the string. |
| Stale other-group member test: failed before fix | All accepted members are checked before any new application; no silent re-ingest of changed accepted folders. |
| Native third/fourth full runs interrupted at approximately 63% / 9% | These were superseded during the new boundary fixes, not reported as completed passes; raw partial logs retained. |

All logs live under the G: evidence directory. Earlier Phase 6–7 reports, result rows and verdicts remain untouched. No new evaluation cycle was run.

## Reproduce (PowerShell)

Use new output directories each time, preserving first results. Set `TEMP` and `TMP` to the G: QA temp directory, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUTF8=1`, and `UV_CACHE_DIR`/npm cache to the G: QA cache.

```powershell
# Geo backend, from the Geo G: worktree
$env:PYTHONPATH='G:/Libraries/_qa/phase8-wave-l-20261114/geographer/src;G:/Libraries/_qa/phase8-wave-l-20261114/geographer'
$env:TIKTOKEN_CACHE_DIR='G:/Libraries/_qa/phase8-wave-l-20261114/geographer/assets/tiktoken'
& 'F:/uv-data/Geo_Grapher/output/wheel-env/Scripts/python.exe' -m pytest tests -q --ignore=tests/node_modules -p no:cacheprovider --basetemp=G:/Libraries/_qa/phase8-wave-l-20261114/temp/geo-repeat

# Native full suite: neutral directory, absolute test path
Set-Location F:/uv-data
$env:PYTHONPATH='G:/Libraries/_qa/phase8-wave-l-20261114/librarian/src'
& 'D:/Librarian_V2/.venv/Scripts/python.exe' -m pytest G:/Libraries/_qa/phase8-wave-l-20261114/librarian/tests -q -p no:cacheprovider --basetemp=G:/Libraries/_qa/phase8-wave-l-20261114/temp/native-repeat

# Cross-repository no-model gate, from the Geo worktree, under the installed interpreter
& G:/Libraries/_qa/phase8-wave-l-20261114/installed-wheel-env/Scripts/python.exe scripts/qa_wave_l.py --base G:/Libraries/_qa/phase8-wave-l-20261114/qualification-repeat --wheel-python G:/Libraries/_qa/phase8-wave-l-20261114/installed-wheel-env/Scripts/python.exe
```

Browser fixture: run native `tests/folder_review_demo.py` with `WAVE_L_WHEEL_PYTHON` naming that installed interpreter, then native `ui/folders-smoke.mjs <printed-url> <new-G-artifacts-dir> <printed-source>`. Full native smoke: `node run-smoke.mjs` from its UI directory, with `LIBRARIAN_SMOKE_PYTHON=D:/Librarian_V2/.venv/Scripts/python.exe`. Geo browsers used the retained `G:/Libraries/_qa/phase8-wave-l-20261114/geo-playwright.config.cjs` wrapper because the original config assumes a checkout-local Python environment.

Reviewed wheel: `G:/Libraries/_qa/phase8-wave-l-20261114/wheel-reviewed/geo_grapher-0.2.0-py3-none-any.whl`.

SHA256: `1d587a598b6fe7bbffd7fad4b92a1c3f839d5a8c4693f76382f453bbe4dc1aad`.

## Demo

- Staged cards: `G:/Libraries/_qa/phase8-wave-l-20261114/evidence/browser-frozen/folders-staged.png`.
- Persisted acceptance: `G:/Libraries/_qa/phase8-wave-l-20261114/evidence/browser-frozen/folders-accepted.png`.
- Stale refusal: `G:/Libraries/_qa/phase8-wave-l-20261114/evidence/browser-frozen/folders-stale.png`.
- Operator guide: native `docs/WAVE_L_FOLDER_REVIEW.md`.

## Limits and owner stop

This is a static ingestion/review boundary. PDF assignments do not claim PDF extraction or original-page verification; those continue through the existing approved paper workflows. Model descriptions were tested with scripted endpoints, not a paid route. Free-prose scope checking detects explicit current-system framing, not every semantic paraphrase. Refusal counts include directory boundaries whose private contents are never enumerated.

Claude's newly added `PHASE8_FINAL_STEPS_SCOPE_20261114.md` and `PHASE8_REVIEW_GAPS_AND_LIBRARIAN_INTEGRATION_20261114.md` describe broader work: authorship declarations, untrusted-turn closure, hidden conversions, original-page checks, complete native indexing of attached own content, domain gates and DIK/intake consolidation. Those are review context, not an owner-approved expansion of this task. Wave L does not claim to complete them. Resolve that sequencing before real-library ingestion.

Spend: **$0**. No qualification bypass, lead binding, hosted embedding, live pilot, merge, push or tag.

**OWNER STOP L:** review this candidate and its limitations. Approval is required before Part C; the newer access-model roadmap should be reconciled first. Still-needed real-library choices include the research folder and the exclusive assignment of `network_management` folders. No Part C folders or stores have been created.
