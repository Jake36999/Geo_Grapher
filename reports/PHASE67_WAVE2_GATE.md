# Phase 6–7 Wave 2 gate (substrate)

Branch `phase67-wave2`. Gate run 2026-11-12. Originals were only read: graphs were built into
`output/phase67-gates/wave2/`, scratch copies went to the session scratchpad, and
`init-workspace` ran in plan mode only (`--plan-out -`, never `--apply`).

Work in wave 2: entity fingerprints (T1), the drift classifier (T2), `.ipynb` virtual source
(T2A), `init-workspace` (T3), the Librarian deploy-survey hook (T4, Librarian branch
`geo-grapher-survey`), cross-graph diff and the clone join (T5). The gate found one defect,
fixed in `13cdd8c` (§2).

## 1. Fingerprint overhead (re-ingest of ToolSet and librarian-v2)

Each graph was imported into a fresh catalog twice, from the same source profile:
- once with `main` (`a926d57`, wave 1, no fingerprints);
- once with `phase67-wave2`.

Each import is one cold run, so the timings are indicative.

Profiles:
- ToolSet: `D:/Aletheia_project/DEV_TOOLS/ToolSet`, roots `aletheia_toolchain` and `local_tool_assist_mcp`.
- librarian-v2: `D:/Librarian_V2`, roots `src` and `README.md`.

| Graph | Files | Entities | main (s) | wave 2 (s) | Δ time | Fingerprint rows | DB bytes main → wave 2 | Δ bytes |
|---|---|---|---|---|---|---|---|---|
| ToolSet | 121 | 17,230 | 25.31 | 27.18 | +7.4% | 2,017 | 194,478,080 → 196,915,200 | +1.25% |
| librarian-v2 | 149 | 27,953 | 64.47 | 69.12 | +7.2% | 2,911 | 444,715,008 → 447,901,696 | +0.72% |

Fingerprint rows are written for function, method and class entities only (G2).

## 2. Drift on six scripted edits

Method:
- Copy `src/geographer/` twice into a scratch area.
- In one copy, apply six byte-level edits to `labels.py`. Edits keep the checkout's CRLF line endings.
- Ingest both copies at stage 3 and run `drift_report`.

| Intended tier | Edit | Target result |
|---|---|---|
| MOVED | rename `_stem_parts` → `_stem_tokens` | `MOVED` (rule `unique_ast`) ✅ |
| CONTRACT_CHANGE | `snippet` gains `min_words:int=3` | `CONTRACT_CHANGE` ✅ |
| BODY_REFACTOR | `_start`: `.get('start_line') or 0` → `.get('start_line',0) or 0` | `BODY_REFACTOR` ✅ |
| COSMETIC | `_cache`: add a space and an inline comment | `COSMETIC` ✅ |
| LINE_SHIFT | two blank lines before `_is_spec` | `LINE_SHIFT` ✅ |
| NEIGHBOUR_DRIFT | seed: `_owner_name` calls `_plain` instead of `_name` | seed `BODY_REFACTOR`; 114 entities `NEIGHBOUR_DRIFT` ✅ |

Totals:

| Tier | Count |
|---|---|
| UNKNOWN | 7,170 |
| IDENTICAL | 487 |
| NEIGHBOUR_DRIFT | 114 |
| MISSING | 11 |
| BODY_REFACTOR | 2 |
| CONTRACT_CHANGE | 2 |
| COSMETIC | 2 |
| LINE_SHIFT | 1 |
| MOVED | 1 |

Every tier change that isn't an edit target has a cause:
- `disambiguate` → `CONTRACT_CHANGE`. It passes `_stem_parts` by reference, so its exact out-edge target changed. That is correct.
- `disambiguate.<lambda>` → `COSMETIC`. The rename sits on the lambda's line. Correct.
- 114 `NEIGHBOUR_DRIFT`. The seed is within 3 hops of these entities, mostly in `service` (22), `viewport` (16), `geometry` (14) and `analysis` (10). They are drift only, with no own-byte change.
- 11 `MISSING`. These are external call-site symbols (`len`, `any`, `' '.join`, …). They carry no fingerprint, and their qualified names are not unique, so rule (ii) cannot pair them.
- 7,170 `UNKNOWN`. These are entities with no fingerprint row: files, fragments and external symbols.

**Defect found and fixed (`13cdd8c`).** In the first run those 7,170 entities were reported
`MISSING`. That broke G3 order 2, which says that when either side has no fingerprint row the
tier is `UNKNOWN`. `drift_report` now returns `UNKNOWN` when a counterpart exists without a row,
and a pinning test covers it (RED before the fix, GREEN after). This also settles the minor issue
deferred from Task 2.

The first attempt also mislabelled two edits. Both were my mistakes, not product defects:
- The edited copy was written with LF while the checkout was CRLF. Every span hash changed, and all 20 functions read `COSMETIC`.
- The planned BODY edit changed a comprehension `if`. G2 counts a `comp_if` as a guard, so `CONTRACT_CHANGE` was the correct tier for it.

## 3. `init-workspace --plan-out -` on three roots

Plan mode wrote nothing. The temporary catalog was never created.

| Root | Archetype | Partitions (files) | Overlapping roots | Manual steps |
|---|---|---|---|---|
| `D:\Librarian_V2` | software_engineering | `docs` (39), `residual` (738) | none | none |
| `D:\Timeline-mapping` | notes_vault | `residual` (285) | none | 2 paper corpora (`outside sources`: 27 PDFs; `outside sources/books`: 1 PDF) |
| `F:\uv-data\Geo_Grapher` | software_engineering | `docs` (5), `residual` (299) | none | 1 paper corpus (`Research`: 18 PDFs) |

What the residual partitions exclude:
- **Librarian_V2:** `.git`, `.pytest_cache`, `.venv`, `build`, `obsidian/dist`, `obsidian/node_modules`, `ui/node_modules`, `tmp`, every `__pycache__`, `*.egg-info`, and five nested `reports/…/worktree-tmp/tmp` trees. It also excludes `docs`, which has its own partition.
- **Geo_Grapher:** `.git`, `.pytest_cache`, `.venv`, `build`, `dist`, `frontend/dist`, `node_modules`, `output`, `tmp`, every `__pycache__`, `*.egg-info`, and `docs`.
- **Timeline-mapping:** nothing to exclude. Its 4,077 `.json` files are reported as unsupported by suffix, not ingested.

Plan IDs: `451dfaedf90e…`, `9ee7a0daac1d…`, `1fe99d92087c…`. Plans are kept in the session scratchpad.

Observations (minor, wave 3 candidates):
- Geo_Grapher's residual still contains tool and workspace folders that are not source: `.superpowers/` (SDD ledgers), `.librarian/`, `About/` and `Indexes/` (the Librarian vault the owner opened here). They are git-ignored but not in `HYGIENE_DIRS`. A rule that excludes git-ignored directories, or an explicit list, would drop them.
- Librarian_V2's `reports/` (run artefacts) lands in `residual`. A `reports` role, or exclusion of run data under `reports/*/data`, would cut noise.

## 4. Clone report: ToolSet × librarian-v2

`clone-report --graph-ids <ToolSet>,<librarian-v2> --limit 5000` ran in 0.75 s. It found 278 pairs:
276 `signature+guard` and 2 `py-ast-v1`. The top 10 pairs in canonical order:

| # | Match | librarian-v2 | ToolSet |
|---|---|---|---|
| 1 | py-ast-v1 | `coordination.py DocumentLeases.view.<lambda>` (1 line) | `notebook_packager_v3.1.py build_notebook.<lambda>` (1 line) |
| 2 | py-ast-v1 | `deploy_survey.py survey.<lambda>` (1) | `workspace_packager_v2.4.py _traverse.<lambda>` (1) |
| 3 | signature+guard | `facts.py license_from_text.<lambda>#1` (1) | `build_vector_layer.py main.flush.<lambda>` (1) |
| 4 | signature+guard | `facts.py license_from_text.<lambda>#1` (1) | `audit_graphify_graph.py community_namespace.<lambda>` (1) |
| 5 | signature+guard | `facts.py license_from_text.<lambda>#1` (1) | `audit_graphify_graph.py nmi.<lambda>` (1) |
| 6 | signature+guard | `search.py _add_orientation.<lambda>#1` (1) | `semantic_slicer_v7.0.py WorkspacePackager._generate_text_output.<lambda>` (1) |
| 7 | signature+guard | `search.py _add_orientation.<lambda>#1` (1) | `audit_graphify_graph.py symbols.<lambda>` (1) |
| 8 | signature+guard | `search.py _add_orientation.<lambda>#1` (1) | `audit_graphify_graph.py community_namespace.<lambda>` (1) |
| 9 | signature+guard | `search.py _add_orientation.<lambda>#1` (1) | `audit_isolation.py check_label_ambiguity.<lambda>` (1) |
| 10 | signature+guard | `search.py _add_orientation.<lambda>#1` (1) | `export_subsystems.py main.<lambda>` (1) |

**Reading.** These two repos share no code, and the report agrees:
- 274 of the 278 pairs involve a one-line lambda, such as `lambda r: r[1]`.
- The other 4 are trivial `__init__` methods with the same header and no guards.
- No pair without a lambda spans 3 or more lines.

So the join is correct, but it has no size floor. For wave 3, add a minimum span (≥ 3 lines) and
exclude lambdas from `signature+guard` by default, or weight matches by hash rarity.

**Positive control.** The Librarian survey worktree (master `c4eb76f` plus the T4 commit) was
ingested as a third graph and compared with live librarian-v2, whose working tree is dirty:
- `clone-report` found 7,645 pairs, 3,003 of them `py-ast-v1`.
- `diff-graphs` gave:

  | Class | Count |
  |---|---|
  | EXACT_AST_SURVIVOR | 2,538 |
  | CONTRACT_PRESERVING_REFACTOR | 227 |
  | SIGNATURE_OR_GUARD_DRIFT | 18 |
  | TOPOLOGICAL_ROLE_ANALOG | 2 |
  | STRATUM_EXCLUSIVE | 247 (126 in A, 121 in B) |

  Quotient-cycle delta: 4 cycles `INVARIANT`, 1 `COUPLING_INCREASED`.

The refactor class is mostly made of classes: a class's AST hash covers its methods, and the live
tree carries uncommitted edits.

## 5. Verification

| Check | Result |
|---|---|
| `./scripts/verify.ps1` (full backend suite, frontend typecheck/build, browser suite) | exit 0: backend 541 passed (213 s); frontend typecheck, build and unit ok; browser 14 passed |
| Librarian full suite (`geo-grapher-survey` worktree, `70ffe38`) | exit 0: 2143 passed, 2 skipped, 5 deselected (756 s) |

## 6. DeepInfra spend (wave 2)

All drafting and review went through `delegate_deepinfra.py` (pool `geo-grapher`, $10 cap):
DeepSeek-V4-Pro and Qwen3-Coder-480B as drafters, Qwen3-Coder-480B as reviewer. Spend to date is
**$0.329**. The gate itself made no model calls.

## 7. Carried forward

- Clone join: add a size floor and lambda exclusion (§4).
- init-workspace: exclude git-ignored tool and vault folders, and add a `reports` role (§3).
- Owner decisions still open:
  - merge `geo-grapher-survey` into Librarian master;
  - commit the `--reasoning-effort` / `--no-thinking` flags in `delegate_deepinfra.py`;
  - the pre-existing uncommitted Geo-Grapher files on Librarian master (ruling W2-7).
