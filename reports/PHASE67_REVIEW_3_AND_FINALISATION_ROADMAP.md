# Wave 4 third review, and the Phase 6–7 finalisation roadmap

Reviewer: the lead agent of waves 1–3. Date: 2026-11-13. This review covers `16a0c59…79d5606` on `phase67-wave4`, gate report §§13–16, and the `code-continuation-cycle-run{1,2,3}.json` per-call logs.

## Part A: Review

### A1. Verdict

This is excellent engineering and evidence work. Everything Review 2 asked for landed, each piece with a RED oracle first:
- constants indexed: +968 entities on librarian-v2, +3.1% entities, about +15% ingest;
- flat responses with canonical identifiers only;
- character caps on every tool, with flat degradation;
- export-scan caching, plus a stage-3 analysis;
- the directed-QI control in the UI, including an affinity bug it exposed and fixed.

Codex then found and fixed four more real defects without being asked:
- a transport import on headless opens;
- unstemmed full-text search;
- constant comments attached only from their last line;
- the packer dropping the top-ranked hit by utility-per-byte.

All of them shipped with fixtures. The real-store browser pass is 5/5, the preset smoke is 28/28, and C14 passes. The evidence discipline is still exemplary: sealed inputs, a commit before each dispatch, no fourth run, and all rows retained.

### A2. The code cycle: 12/15, failing only the per-run floor

| Condition | Result |
|---|---|
| Aggregate ≥ 12/15 | **PASS (12)** |
| Each run ≥ 3/5 | **FAIL**: run 1 scored 2/5 |
| 0 wrong-graph, 0 withheld, ≤ 8 calls per question | PASS (0, 0, 5.8) |

Runs 2 and 3 each scored 5/5, so the product and model can answer every question. I checked run 1's per-call log. **Two of its three misses produced no answer at all:**

| Run 1 miss | What happened | Cause |
|---|---|---|
| Clerk / `run_one` | 12 steps, no answer | **The Librarian loop returns nothing at `max_steps`**, even after relevant code was retrieved |
| Fallback window / `DEFAULT_CONTEXT_TOKENS` | It retrieved the right constant, then 2 bad IDs, then 12 steps with no answer | The same as above, plus **ID-error recovery still returns a placeholder example** (`"<entity_id>"`) instead of real choices |
| Concurrency / `lead_agents` | Answered at step 4; described the thread pool and missed the upstream cap | Model answer completeness. Content delivery is unverified because `tool_text` isn't saved |

So the run-to-run instability isn't retrieval. It's two concrete product behaviours:
1. Exhausting the step budget throws away gathered evidence instead of producing a best-effort answer.
2. A recoverable ID error offers no actual recovery path.

Both are cheap and generic, and neither is a benchmark-specific tweak.

### A3. Further direction (wave 4 close-out)

1. **A final answer at the step limit** (Librarian, `Loop`):
   - When the next step would exceed `max_steps`, make one final model call with tools disabled: "answer from the evidence gathered; say what is missing".
   - Mark the answer `completed_at_step_limit: true`.
   - Never invent citations; the existing citation checks still apply.
   - Write a RED oracle using a scripted provider that keeps calling tools.
2. **ID errors with real choices** (Geo-Grapher front door):
   - For "entity_id is not in this graph snapshot", return up to 3 real candidates, each with `entity_id`, `qualified_name` and `cite_as`.
   - Candidates come from this connection's recent search results, by prefix or qualified-name similarity, else from an exact-name lookup.
   - The bound is ≤ 400 characters, deterministic, and never crosses graphs.
   - Fall back to the template only when there is nothing to offer.
3. **Response-coverage metadata**, as Codex itself proposed. Every flat content and search response carries bounded `coverage: [{entity_id, start_line, end_line, truncated, sha256}]`, and the harness saves it. Future misses can then be split into "not delivered" and "delivered but not used", without storing full tool text.
4. **The final wave 4 cycle.** I recommend the owner authorises **one** last registered cycle after items 1–3, with the identical frozen protocol (3 runs, each ≥ 3/5, total ≥ 12/15, …). It costs about $0.45, and about $5.09 remains in the pool. Declare in the registration that **this is the last code cycle for wave 4.** If it fails, the owner chooses between:
   - accepting wave 4 with a "code agent stability" limitation, evidenced by 12/15 plus the diagnosis;
   - moving the code-agent target to wave 5.
   
   There's no cycle after that either way.
5. **C14 robustness.** It passes with 25 ms of headroom. The earlier current-store run failed at 3.75 s, the same code on a different snapshot and moment. The rule stays as it is for wave 4. For the future, make C14 "median of 3 cold samples < 3.0 s and max < 3.5 s" (record this as a proposal, not a retroactive rescore), and put "librarian-v2 QI latency (6–11 s)" in the wave 5 performance work.
6. **Disk hygiene.** F: filled during QA. Add a `scripts/qa_cleanup.py` that removes disposable QA copies older than the newest two per scenario, and never touches `output/phase67-gates/wave*/` originals or the frozen wheels. Run it before each browser cycle.

### A4. Owner actions, still pending

These don't depend on Codex:
- **Qualify the Resource-Library roles** (gate §10). The Core has been stopped at every check. This alone blocks the six-task pilot and the production-lead question.
- **The 20-minute hands-on checklist** (gate §11). The directed-QI UI is now in, so every step can pass.
- **Rulings:**
  - the bridge-firewall threshold (W3-5);
  - authorising the final wave 4 code cycle (A3.4);
  - the C14 future rule (A3.5).

## Part B: Finalisation roadmap (Phase 6–7 features)

The goal is merged, released, documented, owner-accepted Phase 6–7 features in both repositories. Each stage has an exit criterion; don't start a stage before the previous one exits, except where marked as parallel.

### F0. Close wave 4 acceptance

1. Implement A3.1–A3.3, plus verify and the Librarian suite.
2. Run the final registered code cycle (A3.4), if authorised.
3. The owner qualifies the roles. Then run the **six-task live pilot** (plan Step 3): 4 tier-3 block contracts, 1 tier-2 synthesis and 1 tier-1 review on ToolSet. Record the waves, the clerk verification rate, the stale count, the wall time and the cost. Then run the one non-gating production-lead code question.
4. Write the gate report §17 with a final verdict per criterion.

**Exit:** every wave 4 criterion is PASS, or carries an owner-accepted limitation in writing.

### F1. Owner decisions (in parallel with F0)

- **W3-5, the bridge firewall:** apply the proposal (Ψ unless citation, or neighbour Jaccard ≥ 0.2), or keep G4 as written.
- **The Librarian master's mixed-owner uncommitted files** (W2-7): their owners commit them or set them aside. This has to happen before any Librarian merge.
- **Commit `delegate_deepinfra.py`'s `--reasoning-effort` / `--no-thinking` flags** (74 tests pass).
- **The C14 future rule** (A3.5).

**Exit:** every decision is written into the master plan's decision log.

### F2. Integration and merge

The order matters:
1. **Librarian:**
   - rebase `geo-grapher-survey` (`70ffe38`) onto current master and run the full suite;
   - merge it;
   - rebase `geo-grapher-wave4` onto that, run the full suite, and merge.
2. **Geo-Grapher:**
   - merge `phase67-wave4` into `main` (`--no-ff`);
   - re-run `scripts/verify.ps1` and `scripts/qa_mcp_presets.py` on the merged `main`;
   - rebuild the wheel.
3. **Cross-repo check:** run the through-Librarian smoke, a no-model search → packet with the installed wheel, on both merged mains. **The owner must approve each merge.** Push only on the owner's instruction.

**Exit:** both mains are green, and the installed-wheel smoke passes from merged code.

### F3. Release hardening

- **Version and contracts:**
  - bump `geo-grapher` from 0.1.1 to **0.2.0**;
  - freeze `contracts/v1.1` (declare it stable; later changes go to v1.2);
  - record the contract digests in the release notes.
- **Migration notes:**
  - the new catalog tables (`bridge_bindings`, `bridge_proposals`, `artifact_*`, `revision_ledger`) auto-create on open, and legacy bridges get bound;
  - the constants, FTS and documentary changes need a **re-ingest** to produce new snapshots (old snapshots stay readable and immutable);
  - the stage-3 export analysis only applies to new snapshots.
- **Documentation:**
  - **A user guide:** directed QI and what "existential reachability" means; bridge review and states; prune by derivation; Add folder and `--browse-root`; drift reports; cross-graph analysis.
  - **An agent and MCP guide:** the presets (`papers`, `code`, `lead`, `cross`), flat call forms, `cite_as`, cursors, size caps, and the errors to expect.
  - **An operator guide:** `serve-graphs` flags, the catalog layout, backups, and the QA cleanup.
- **Security pass:** a focused review of the HTTP surface: the picker, ingest jobs, prune, the proposal routes, and the CSRF/origin guard. It must run against a real local server, not just a read-through.
- **Performance budgets in CI:** keep C14 (with the F1 rule) and the preset size caps as checks in `verify.ps1`. Gate the latency step behind a quiet-machine flag, so it doesn't flake.
- **Changelog:** waves 1–4 features, the known limitations from F5, and the rulings index.

**Exit:** the 0.2.0 wheel is built from the merged main, the docs are reviewed by the owner, and the security findings are fixed or accepted.

### F4. Owner acceptance

- The owner runs the 20-minute checklist on the 0.2.0 wheel against a fresh copy of real stores.
- The owner asks 3 real questions through the Librarian production route: one paper, one code, one cross-graph. Each answer must cite handles that open in the UI.
- The owner signs off the release notes, including the known limitations.

**Exit:** a written sign-off, plus a tag `geo-grapher-v0.2.0`, pushed when the owner says.

### F5. Carried into wave 5 (known limitations; listed in the release notes)

| Area | Item | Source |
|---|---|---|
| Answer discipline | Abstain when the corpus lacks the subject (the Warburg probe; prior-knowledge 1/29) | wave 4 §4 |
| Performance | librarian-v2 QI 6–11 s cold, from partition persistence and actor preparation; C14 headroom | waves 3–4 |
| Code agents | Stability beyond the final cycle; response-coverage–driven retrieval tuning; Clerk ranking | wave 4 |
| Bridges | Firewall threshold, if not done in F1; proposal recall (concept and section names rarely match code names) | wave 3 |
| Contraction | G6 invariant II rejects parallel twins: a weaker witness-pairing condition | W3-2 |
| Clones | A size floor and lambda exclusion for `clone_candidates` | wave 2 |
| Workspace init | Excluding git-ignored tool and vault folders; a `reports` role | wave 2 |
| Lineage | Librarian `external` artifact registration (read-only constraint) | wave 3 |
| Cross-graph UX | Large evolution diffs (3,037 items at about 6 per 7.5 KB page): lead with `header.counts` and filters | wave 3 |
| Parsing | The optional JavaScript parser failure on `ui/app.js`; the `server/discover` compatibility warning | wave 4 |

### Budget

$5.09 remains in the `geo-grapher` pool. F0 needs about $0.45 for the final cycle, about $0.01 for qualification, and the pilot's own estimate, which Codex should state before running it. Nothing else in this roadmap needs paid model calls, except optional DeepInfra drafts and reviews (cents each).
