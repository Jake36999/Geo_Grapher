# Waves 1–3 takeover assessment — 2026-11-12

Assessment at Geo Grapher main `0f12dfa` (handover follows merge `ffec32b`). The checkout was clean. This is an engineering readiness assessment for wave 4, not a new release acceptance.

## Evidence and verdict

The three gate reports, master definitions, wave plans, progress rulings and selected implementation/tests were inspected. Waves 1–3 provide a usable foundation for wave 4. The earlier gates include meaningful negative cases and real-source copies, and record corrections rather than hiding failed first attempts.

| Wave | Evidence | Remaining limits |
|---|---|---|
| 1 | Labels, roles, documentary links, discovery, graph lifecycle, layout and permutation-invariant federation. Gate-discovered affinity and federation errors were fixed and remeasured. | Affinity acceptance uses the documented F20 population (non-core, K ≥ 4); qualifying samples are small. Unexercised curve families remain coverage gaps. |
| 2 | Six drift edits exercised; UNKNOWN versus MISSING defect fixed. Workspace planning, notebooks, clone/diff evidence and Librarian survey tests recorded. | Trivial lambda/constructor clone matches; ignored tooling/vault folders in residual partitions. Survey commit `70ffe38` is not merged into Librarian master. |
| 3 | 50 real sub-DAG property checks, snapshot-bound bridges, signature edit/revert lineage pilot, bounded cross-graph pages and browser coverage. Post-publication sweep failure handling was corrected. | Bridge precision was 0/2 and only two proposals existed versus ten requested; the full evolution diff stopped at 400 pages (2,348/3,037 items). Librarian QI latency remains 4–5.7 seconds. |

Do not describe the three waves as universally accepted: these gate and coverage limitations remain real. None requires changing G4 or merging another owner's work to implement wave 4. Conformance must use reviewed bridges and must return no invented findings where there are none.

## Role and approach

Codex is the implementation lead: write and validate oracle tests/specifications, integrate coupled code, adjudicate draft/review output, run full checks and record measured gate results. DeepInfra workers draft self-contained modules; DeepInfra reviewers supply concrete, quote-supported findings. Their output is a proposal, never an authority.

Use pool `geo-grapher` with its existing $10 ceiling, through the receipt-producing delegation script. Opening spend was $0.49162395. A Qwen3-Coder second-reader assessment cost $0.0096174 (`20261112T193142-591cfe49`). It reported no new concrete source defect; its clone finding pointed to the wrong report and paraphrased its purported quote. The underlying clone limitation is independently supported by the wave 2 report, not by that attribution.

Geo Grapher branch: `phase67-wave4`. Librarian branch: `geo-grapher-wave4` in an isolated worktree based on master `c4eb76f`; its original checkout is dirty with others' work and remains untouched. The handover's historical instructions are subordinate to the user's current request. Its stale copied wave-2 branch/attribution instructions are not applied literally. Do not merge the survey branch, commit others' files or change the G4 firewall without owner direction.

Fresh baseline verification (`scripts/verify.ps1`) exited 0: 626 backend tests, 17 browser tests, frontend typecheck/build/unit checks passed. Backend 195.98 seconds, browser 24.2 seconds. Full output: `output/wave4-baseline-verify.log`. No product source was edited during this run.

## Subsequent cross-repository finding

Wave 4's through-Librarian code benchmark found an integration gap the baseline suites did not exercise: Librarian treated a request described by a local JSON Schema `$ref` as text, corrupting valid request objects before the MCP call. This was reproduced with a failing oracle and fixed on the isolated Librarian branch. Geo Grapher now also exposes concrete request fields to function-call clients. A no-model, installed-wheel search/packet smoke succeeds; the cheap code model still fails its behavioral benchmark. This limits the original readiness verdict: waves 1–3 were a usable implementation substrate, not proof of end-to-end Librarian code-agent usability. See the wave 4 gate report for measured limitations.
