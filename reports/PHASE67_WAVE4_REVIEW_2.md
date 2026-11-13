# Wave 4 second review and direction

Reviewer: the lead agent of waves 1–3. Date: 2026-11-13.

This review covers `4498b08` and `68516f9` on `phase67-wave4`, and `reports/PHASE67_WAVE4_GATE.md` §§9–12. Evidence checked:
- `code-frontdoor-run1.json` and `code-frontdoor-run2.json`, including the `per_call` records;
- the librarian-v2 gate store;
- `contraction.py` and `graph_router.py` at the branch tip.

## 1. Verdict

Good work, honestly reported:
- The front door removed the protocol barrier completely. Run 1 had **0 tool errors** and 4.6 calls per question, down from about 12 calls with 10–11 errors each.
- The paper option (a) and the leakage dispositions were applied correctly.
- The real-store browser QA found genuine gaps rather than declaring success.
- Keep the evidence discipline exactly as it is: frozen criteria, retained first results, no best-of scores, and stopping at the escalation point.

The open failures all have **specific, fixable product causes**, which I've confirmed in the evidence. None of them is evidence that the approach is wrong. In priority order:

| # | Failure | Root cause (verified) | Fix |
|---|---|---|---|
| 1 | Code benchmark at 3/5 and 2/5 | **Module-level constants aren't indexed.** The librarian-v2 store has no entity for `HELPER_TOOLS` (`tools/delegate.py:17`), `MAX_EXTERNAL_RESULT` (`mcp_client.py:47`) or `DEFAULT_CONTEXT_TOKENS` (`loop.py:139`). The kinds present are class, function, method, file, fragment, `scope_atom`, `external_symbol`, and so on; there is no constant or variable kind. The two questions that missed in **both** runs ask about such constants. The hits came via a function that happens to use the name. | §2.1 |
| 2 | Run 2's 7 rejected calls | **Wire aliases leak into the flat responses.** The agent passed `n7990` (a view-local node alias) as `entity_id` four times. It also invented `entity:<graph_id>:n7990`, and mistyped the 24-hex graph ID once. | §2.2 |
| 3 | Preset smoke: `federated_search` returns 20,098 characters against a 7,500 cap | `GraphRouter.federated_search` never applies the connection character cap. `_fit` runs only inside `query()`. It's the same class of bug as `analyze_cross_graphs` had in wave 3. | §2.3 |
| 4 | Preset smoke: minimal `get_architecture_context` and `find_dependants` return `BUDGET_TOO_SMALL` on real stores | The minimal *required* payload (ancestors, representative and their node summaries) exceeds 7,500 characters on real graphs, so the packer refuses rather than degrading. | §2.3 |
| 5 | C14: tree-balls 3.1–3.7 s on ToolSet (wave 3 measured 2.77–2.84 s) | `contract_helpers` base64-decodes and `ast.parse`s **every Python file in the snapshot on every QI query** to find `__all__`, with no cache (`contraction.py:31-42`). | §2.4 |
| 6 | Directed-QI UI is missing | The wave 3 plan wired the algorithm into the API, but never added a spatial control. That's a real gap and was correctly flagged. | §2.5 |
| 7 | Six-task pilot is blocked | Role qualification. That's the owner's action (§4); the commands in gate report §10 are correct and ready. | owner |

## 2. Engineering direction

Write a RED oracle first for each item, then fix it, then run the full verify.

### 2.1 Index module- and class-level constants

This is the highest-value fix.

- Extract module-level and class-level assignments as entities of a new **additive v1.1 kind `constant`**:
  - `Name = …` and `Name: T = …`, where the name is UPPER_CASE or the value is a literal, frozenset, tuple or dict;
  - optionally all module-level names, behind a switch.
- Each constant gets:
  - a qualified name, such as `src/resource_librarian/tools/delegate.py.HELPER_TOOLS`;
  - an exact line span;
  - its parent file;
  - documentary fragments from an adjacent comment or docstring;
  - static `reads` edges from the functions that reference it (the symtable already resolves these names).
- Contract work: add the kind to `contracts/v1.1/geographer.wire.d.ts` and regenerate with `npm run contracts -- 1.1`. The frozen 1.0 enum must not change; for 1.0 clients, map the kind to `fragment` or omit it.
- Check all of these still behave:
  - **Fingerprints:** a constant gets a span hash; its body hash can be the value's AST.
  - **Drift:** a changed constant value is a `BODY_REFACTOR`; for `CONTROL_GUARD` contracts the tier stays NOOP.
  - **Labels and role badges:** they shouldn't change.
  - **Directed contraction:** constants are not callable, so they're never in blocks.
- Oracles:
  - `search_entities(graph_id, "HELPER_TOOLS")` returns the constant first, with its `cite_as`;
  - `get_entity_content` on it returns exactly its lines;
  - re-ingest the wave 2 drift fixture and confirm no new MISSING or UNKNOWN regressions;
  - check the entity-count and ingest-time overhead on librarian-v2 and record it.

### 2.2 Flat responses: canonical identifiers only

- In flat-form responses, **emit no view-local aliases** (`n…` or `w…`). Every node carries `entity_id` and `cite_as` only. Aliases remain in the strict form, for programmatic clients.
- Accept the **graph label** (`librarian-v2`) wherever a `graph_id` is accepted (`router.resolve` already does this). Make `list_graphs` show the label first, and tell agents in the tool description to prefer labels. This removes the error class where a 24-hex ID gets mistyped.
- If an `entity_id` isn't found but it matches an alias from a recent search on this connection, resolve it. If that's ambiguous, return the error with **the correct `entity_id` and `cite_as`**, not a generic template. Make that a bounded, per-connection LRU, deterministic, and without any cross-graph lookup.

### 2.3 Every MCP result honours `max_result_chars`

- `federated_search`: apply the character cap by dropping whole per-graph hits, the lowest utility first, then whole graph envelopes. Report `omitted` with the reason `size_limit`, and add a pinning test at 7,500.
- `get_architecture_context` and `find_dependants` in flat form should **degrade, not refuse**:
  - drop the optional node summary fields (signature and doc gist) first;
  - then cut `context_radius` to 0;
  - then return ancestors as IDs plus labels only.
  
  Report every degradation in a `degraded:` list. Keep `BUDGET_TOO_SMALL` for the strict form, and for the case where the focus node alone won't fit.
- Add a **cross-cutting test**: every tool in every preset, run on the real-store QA copy, must stay within 7,500 characters. Make `scripts/qa_mcp_presets.py` gate on this; it is already the right shape.

### 2.4 Tree-balls latency

- Compute the `__all__` export and protection scan **once per snapshot** and cache it in the service context, keyed by `(snapshot_id, filter digest)`. Better still, persist it at stage 3 as an analysis record, because it depends only on the source bytes.
- Profile one cold ToolSet query (with `cProfile`, as in wave 3) before and after. Record both, and re-run `qa_wave4_latency.py` on a quiet machine. Target: tree-balls under 3.0 s cold on ToolSet.
- Consider applying the same caching to the directed path's `contract_view` inputs (the SCC condensation per snapshot and filter).

### 2.5 A directed-QI control in the spatial UI

- In the spatial toolbar, add a **QI toggle with an algorithm choice**: Off, Helper balls, Directed. It only applies to atomic grouping, and it must be disabled with an explanation otherwise.
- Pass `qi: {enabled, max_diameter: 2, algorithm}` in the frame request.
- Render `qi` group nodes as enclosures that can be expanded. Show the certificate's block count, and when directed, the phrase "reachability preserved (existential)".
- Make the real-store browser QI test (which already exists and fails intentionally) pass on ToolSet: directed shows more than 1 block, and toggling back to Off restores the atomic frame. It needs no console errors and must finish within the existing timing budget.

## 3. Re-running the code benchmark

The owner authorises a new registered cycle. The earlier one-iteration rule applied to the *previous* product state. §2.1–2.2 change the product on the basis of evidence, so a new cycle is legitimate and is not a best-of.

Register this in the gate report **before** running:
- the same frozen 5 questions, 5 markers and model (Qwen3-Coder-480B), the 1M declared window, the library-scoped `lead` preset and the 12-step limit;
- **three independent runs**, all reported (5 questions is too few for one run to be stable: run 1 and run 2 differed by 1 marker on an unrelated change);
- pass if **each run ≥ 3/5 and the total across the three runs ≥ 12/15**, plus 0 withheld, 0 wrong-graph calls, and ≤ 8 calls per question on average across all runs;
- per-call logs as now.

If it fails, stop and escalate, with the per-call evidence and your diagnosis. Estimated cost is about $0.5 (runs 1 and 2 cost $0.09 and $0.18), and about $5.9 remains in the pool.

Also run, and **label as not gating**, one question on the owner's production lead route, once that route is qualified.

## 4. Owner actions (for the user, not Codex)

1. **Qualify the Resource-Library roles.** Use gate report §10, which is reviewed and correct, at about $0.01 for L1 on both roles:
   - start the Host;
   - run L0 for both roles (free);
   - then run L1 with `--confirm-spend`;
   - check `--status`, which should show `screened` and `fresh: true` for both;
   - leave the Core running.
   
   If the Clerk (`Qwen3.5-397B`) times out, as it did in my wave 2 test, report that. Don't swap the model silently; decide on a replacement Clerk route separately.
2. **The 20-minute hands-on checklist** in gate report §11. Run it after §2.5 lands, so the directed-QI step can pass.
3. **The decision on the bridge firewall (W3-5)** is still open.

## 5. Order of work for Codex

1. §2.3, the cap fixes. They are small, self-contained and unblock the preset smoke.
2. §2.4, latency caching.
3. §2.1 and §2.2, constants and identifier hygiene, with full verify and the Librarian suite.
4. §3, the registered three-run benchmark cycle.
5. §2.5, the directed-QI UI, plus the real-store browser pass.
6. After the owner reports both roles screened: the six-task pilot (plan Step 3).
7. Update gate report §12 with the new rows, keeping all prior rows. Then the full verify plus the Librarian suite, and **ask the owner before merging either branch**.
