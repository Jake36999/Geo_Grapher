# Code-agent benchmark: what stands between 12/15 and a reliable perfect score

Author: the lead agent of waves 1–3. Date: 2026-11-13. This plan is for the owner and Codex.

Evidence:
- `code-final-wave4-cycle-run{1,2,3}.json` and `code-final-wave4-cycle-delivery.json` (the coverage metadata);
- a local replay of the agents' exact queries through `agent_requests.call_code_connection` on frozen snapshot `snapshot:1703964f…` (branch `phase67-wave4`);
- the research library at `E:/Librarian research`, through doc-graph.

The wave 4 code gate is **closed and passed** (3/5, 5/5, 4/5 = 12/15). Nothing here reopens it. This is the plan for wave 5, or a post-release quality track.

## 1. Diagnosis: retrieval is already right; presentation is not

All three misses in the final cycle fall on **two questions**:

| Run | Question (marker) | What the evidence shows |
|---|---|---|
| 1 | External MCP bounds (`MAX_EXTERNAL_RESULT`) | **The constant was delivered** (`mcp_client.py:47`, hash-verified). The agent then followed `sandbox.CAPTURE_BYTES` and answered about that. |
| 1 | Fallback window (`DEFAULT_CONTEXT_TOKENS`) | **The constant was delivered** (`loop.py:139`, hash-verified). The answer described `route_policy` and `context_length`, and never named the constant. |
| 3 | Fallback window (`DEFAULT_CONTEXT_TOKENS`) | **Not opened.** The agent read `context_message`, `library_context` and `CONTEXT_HEADER` instead. |

When I replay the agents' own queries on the frozen snapshot, the right answer is already ranked high:

| Agent's query | Rank of the target |
|---|---|
| "loop fallback context window" | **`DEFAULT_CONTEXT_TOKENS` is #1** |
| "How does the loop choose its fallback context window" | **#1** |
| "MCP structured results bounding" | `MAX_EXTERNAL_RESULT` is #5 |
| "How are external MCP structured results bounded" | #3 |
| "Clerk run and check one task" | `run_one` is #5 |
| "delegate cap concurrent tier 1 helpers" | `HELPER_TOOLS` and `delegate` are #1–2 |

So the agent **saw the answer and didn't recognise it**. The cause is *information scent*: what a hit, or an opened entity, tells the agent about its relevance.

- **A search hit for a constant shows only its name.** For example, `summary: {signature: "DEFAULT_CONTEXT_TOKENS", doc_gist: null}`. That has no value, no comment and no usage. Beside `Loop.library_context` it gives the model no reason to prefer it.
- **Opening a constant returns one bare line.** `get_entity_content` returns lines 139–139: `DEFAULT_CONTEXT_TOKENS = 131_072`. But the comment block directly above it answers the question almost word for word ("…an unknown one gets 128k tokens, the common window of current hosted models…"), and the fallback itself is at `loop.py:578`: `bound = self.context_limit or DEFAULT_CONTEXT_TOKENS`. Likewise, `MAX_EXTERNAL_RESULT` is meaningful only through its use at `mcp_client.py:491-503` (`if structured and len(text) > MAX_EXTERNAL_RESULT`). The agent never sees either.
- **Sampling variance.** The harness passes no temperature, so the agent samples at the provider's default. A question that passes in two runs and fails in a third is the signature of a choice point the agent can flip either way. Better scent removes those choice points; temperature only narrows them.

This matches the research the library holds:
- **LILO** (doc:30): auto-documenting abstractions from their *usage context* makes them usable by a model, not just correct.
- **ReAct** (doc:84): agents correct course only as well as their observations inform them.
- **Reflexion** (doc:68): explicit self-review of what was missed changes the next action.
- **Indirect prompt injection** (doc:31): code comments are an attack surface, so any comment text surfaced to agents must stay marked as untrusted source data.

## 2. Product changes

These are general changes, not benchmark-specific, in priority order.

### P1. Hit cards with scent (Geo-Grapher, flat search responses)

For each hit, within a fixed per-hit budget of about 300 characters:
- **signature:** for constants, the assignment itself, `NAME = <value>`, truncated to 80 characters (`DEFAULT_CONTEXT_TOKENS = 131_072`). Functions keep their header.
- **doc_gist:** the first sentence of the docstring, or of the associated comment block. The comment-to-constant links already exist, from the continuation's comment mapper; they just aren't summarised.
- **why:** the matched field plus about 100 characters of matched text with the query terms in it, for example `comment: "…an unknown one gets 128k tokens, the common window…"`.
- **used_by**, for constants: a count plus the top 2 readers, as `qualified_name:line`, from static `reads` edges.

Oracle: on the frozen snapshot, the 6 replay queries above return the target with a non-null `doc_gist` or `why` that contains a query term. The response size stays within the per-preset cap.

### P2. Content with usage context (Geo-Grapher, `get_entity_content`)

For a **constant**, return, bounded to about 40 lines in total:
- the contiguous leading comment block;
- the assignment;
- up to 3 use sites, each as `enclosing_function: line` with that line ±1;
- `coverage` entries for every range (the existing metadata).

For a **function** shorter than about 60 lines, add `calls_constants`, listing the constants it reads with their values.

Comment and source text stays inside the existing source envelope, labelled as untrusted data, as the MCP instructions already say.

Oracle: opening `DEFAULT_CONTEXT_TOKENS` returns lines 133–139 plus `loop.py:578`. Opening `MAX_EXTERNAL_RESULT` returns 47 plus its use at 491. Every range is verified against the source by hash.

### P3. An answer self-check (Librarian `Loop`, the code-research role)

Before a final answer, make one tool-free check over the evidence ledger: "Which retrieved entity *directly defines* what the question asks? If it isn't cited, revise."

- It costs one model call, counted inside the existing step budget.
- It never adds citations the agent didn't retrieve.
- It's the Reflexion pattern applied within an episode, rather than across episodes.

Measure it as an A/B on the development set (§3). Keep it only if it helps.

### P4. A fixed, low temperature for the code-research role (product configuration)

Set the role's route default to temperature 0.2. Apply it **in production and in evaluation alike**; it isn't an evaluation-only setting. Record it in the route policy, and report results at the production setting only.

### P5. Small ranking nudges, only if P1–P2 leave misses

- A definition boost for constants whose comment contains a query term.
- A same-module boost when a query names a module ("loop" matches `loop.py`).

Each nudge needs a fixture, and must not reorder the existing exact-symbol priority.

## 3. Measurement that makes "perfect" mean something

A perfect score on the five frozen questions alone **would not be a valid claim**. Those questions have now been diagnosed in detail, so tuning against them is overfitting. Run this protocol:

1. **The development set** is the 5 existing questions. Use them for diagnosis and A/B tests only.
2. **A held-out set** of 25 new questions, built and **frozen before any of P1–P5 is implemented**:
   - **sampling:** a fixed seed over librarian-v2 and ToolSet:
     - 10 constants with comments;
     - 10 functions with docstrings;
     - 5 "how does X work" behaviours spanning 2–3 functions;
   - **writing:** a different model (or the owner) writes each question from the entity's documentation only, without its name. The marker is the defining identifier.
   - Store it hashed and sealed; no one reads the answers before the cycle.
3. **Gate:**
   - development set: 15/15 across 3 runs;
   - **held-out set:** ≥ 90% across 3 runs, with every run ≥ 85%;
   - 0 withheld, 0 wrong-graph calls, ≤ 8 calls per question;
   - all at the production temperature.
   
   Register it before running, as before.
4. **Report** misses with the coverage classification already built: `not_retrieved`, `retrieved_not_opened`, `delivered_not_used`. Each class points to a different lever: P5, P1 and P2/P3 respectively.

Cost: a 25-question held-out set × 3 runs is about 75 agent episodes, roughly $1.5–2.0 at the measured $0.025 per question. Set-building is a one-off $0.05. About $5 remains in the pool, so this fits once. No repeated cycles.

## 4. Expected effect, honestly

- **P1 and P2 directly address all three observed misses.** Two of them had the answer delivered without its meaning; one had the answer ranked #1 and skipped.
- **P3 addresses the case where the answer was delivered but not used.**
- **P4 reduces flip-flopping.**

I expect the development set to reach 15/15. I **cannot promise** the held-out set reaches 100%, and nobody should: a model still makes judgement errors on unseen questions. ≥ 90% held-out is the meaningful target. Any miss must be explained by its coverage class, not tuned away.

## 5. Order of work for Codex

1. Build and seal the held-out set (§3.2) **before** any product change. Commit the seal.
2. P1 and P2, with RED oracles first. Then full verify, the preset smoke (caps), and a real-store browser pass (unchanged).
3. P4, a route-policy setting, plus a Librarian test.
4. Development-set A/B: P1+P2 against P1+P2+P3, one run each. This is diagnostic only. Keep P3 only if it helps.
5. One registered cycle: the development set plus the held-out set, × 3 runs, at the production settings. Stop afterwards, whatever the result.
6. Report it in a new section of the gate report, with every row retained.

This is **wave 5 or quality-track work**. It doesn't block the F2 merges or the F3 release in the finalisation roadmap. The release notes should state the current code-agent result (12/15, closed) as it stands.
