# Review 4: the code-quality cycle, and the workflow to continue

Reviewer: the lead agent of waves 1–3. Date: 2026-11-13.

This review covers:
- `0655729…e448ac4` on `phase67-wave4`, and Librarian `d98cbbe`, `08b181e` and `7b47c68`;
- gate report §19;
- `output/phase67-gates/code-quality-track/final-heldout-run{1,2,3}-scored.json`;
- an offline replay of the held-out searches, which I ran: read-only, no model calls.

## 1. Verdict on the cycle

**The process was right, and the result is a real finding, not a failure of execution.**
- The seal came before product changes.
- The key stayed unread until all batches finished.
- There was one cycle and no tuning.
- Defects were disclosed rather than hidden: the invalid A/B, the false "withheld" counts, and 3 flawed held-out items.
- P1, P2 and P4 work as designed. The development set reached **15/15**, the target of the last plan.

**Held-out is 49/75 (65%), and the reason has moved.** In wave 4, the misses had the answer retrieved and skipped. Here, **25 of the 26 misses are `not_retrieved`**: the defining entity never appeared in anything the agent searched for. P1 and P2 fixed presentation; discovery is now the bottleneck.

Two process issues to fix permanently:
- **The A/B was invalidated by a harness setup error** (a profile without its `ProfileStore`), costing about $0.055. Rule: **every harness path must pass a no-model dry run before any paid dispatch.** The continuation already does this; make it mandatory.
- **The "withheld" detector matched a literal string** (`EXTERNAL_RESULT_TOO_LARGE`) inside returned source code. Fix it to read only structured error codes, never the payload text, and add a fixture for it.

## 2. New evidence: agents throw away the question's best words

Since the cycle is closed, the 25 held-out questions are now development material. I replayed every search the agents actually issued (102 distinct queries), plus each question's own text, against the registered snapshots, and checked whether the target appears in the top 8:

| Query source | Target in top 8 |
|---|---|
| **The question text, searched verbatim** | **13 / 25**, mostly at rank 1–3 |
| **The agents' own queries** | **33 / 102 (32%)** |
| At least one agent query hit, per question | 18 / 25 |

Examples:
- **heldout-02:** the question text finds `KEEP_RESULTS` at rank 1, but all 3 agent queries miss. Its score is 0/3, though this item also has a key defect (§3).
- **heldout-13:** the question text finds it at rank 1, while 1 of 7 agent queries hit.
- **heldout-12:** neither finds it. Its agent queries hit 0 of 10.

Two separate gaps follow:
1. **Query formulation (13 questions recoverable).** When the agents compress a natural-language question into keywords, they drop exactly the distinguishing phrases. Hybrid search already handles prose well, so the agent should use it.
2. **Vocabulary mismatch (12 questions miss even verbatim).** The questions paraphrase the docstring or comment ("returns everything readable rather than guessed" for `derive_axes`). Lexical matching with Porter stemming can't bridge that. This needs a **semantic channel**.

## 3. The measurement must be repaired before it's trusted

- **3 of the 25 items are defective,** as Codex disclosed:
  - Q02 asks for an implementation but keys a constant;
  - Q10's only documentation is separators;
  - Q16 asks for rule R005 but keys `rule_r005`.
- **Q04's question text is garbled** ("defines the whole the documented implementation…").
- **Single-identifier markers are brittle.** An answer naming the implementing function instead of its constant, or the reverse, is a valid answer scored as a miss.

So 49/75 is a frozen-key score, not an accuracy estimate. Codex was right to say so.

## 4. Workflow from here: offline first, paid last

The pool has **$2.25 left**, and one 90-episode cycle costs about $2.2. So nearly all the work must be **free and offline**, and the owner has to decide the budget for any final measurement (§4.5).

### 4.1 Free tools: build these first

- **`scripts/eval_retrieval_offline.py`.** Given a question file (question, graph, target entity IDs, and optionally recorded agent queries), report recall@1, @3 and @8 for:
  - (a) the question text;
  - (b) each recorded agent query;
  - (c) the product's recommended query strategy (from §4.2).
  
  Deterministic and read-only on the frozen snapshots. It's this review's replay, made a committed tool.
- **Development data:**
  - the 5 original questions, plus the 25 now-opened held-out questions with their keys **repaired** (§4.4);
  - all 102 recorded agent queries, as a realistic "agent-style" query set.
- **Targets:**
  - recall@8 ≥ 0.90 on question text;
  - ≥ 0.75 on agent-style queries;
  - development marker correctness unchanged.
  
  **No model calls during this phase.**

### 4.2 Lever L1: make the agent's search robust to its own query habits

This is the cheapest lever, with the highest expected yield.

- **Multi-query search.** `search_entities(graph_id, query, also?: [≤2 strings])` fuses up to 3 queries by reciprocal-rank fusion in one call, so it costs no extra steps. A single query is unchanged.
- **Tool guidance.** In the flat schema description and the MCP instructions, say: "Pass the user's question (or its key sentence) verbatim as `query`; add identifier guesses in `also`." This is a product interface change, valid for every client, and not specific to the benchmark.
- **Weak-hit signalling.** When the top hit's fused score falls below a calibrated threshold, add `low_confidence: true` and `try: [2 reformulation hints]`. The hints are derived deterministically: the most informative terms of the best three hits that are missing from the query. This is ReAct's "informative observations" applied to search.
- Measure each change with the offline tool. Keep it only if agent-style recall@8 rises and question-text recall doesn't fall.

### 4.3 Lever L2: an optional local semantic channel

- Mirror the Librarian's existing design (`resource_librarian/embed.py`): **`model2vec` static embeddings (pure numpy, local, deterministic)**, off by default, with `fastembed` (ONNX) as a higher-quality option. **Hosted embeddings must not be used for source code** without the owner's explicit approval, because that would send code to a third party.
- Embed one short text per entity at ingest. For a function: name split, signature, docstring, associated comment block and parent path. Store it as an immutable analysis keyed by `(snapshot, model id, text hash)`. For a constant, include the literal's text when it's a string; heldout-07's answer lives inside a string constant.
- Search fuses BM25 with cosine similarity by RRF. A query embedding computed locally at read time is allowed, by the same rule as in the Librarian: deterministic, not generative.
- This adds a dependency, so it needs an owner decision: an optional extra, `geo-grapher[semantic]`. Default off until the offline numbers justify it. Record the overhead in ingest time and store size.
- Measure on the offline tool; the target is the 12 questions that miss verbatim.

### 4.4 Measurement repair: held-out v2

This applies to any future paid evaluation.

- **Keys become equivalence sets:** the defining identifier, plus the implementing function or constant it's inseparable from, and the documented rule ID where relevant. Each is chosen by a rule written **before** generation.
- **Every item gets a two-reviewer check before sealing.** Reviewer A is the generator; reviewer B is a different model or the owner. Each confirms that the question is grammatical, answerable from the entity's own documentation, and unambiguous within the graph (run the offline search: the target must be identifiable by a human from the top 20).
- **Reject and regenerate before sealing,** never after. Record the rejection reasons.
- The size is 25 again. Use new seeds, so it shares no entities with v1.

### 4.5 One final paid measurement, owner-budgeted

Only when the offline targets in §4.1 are met:
- register the held-out v2 cycle exactly as before;
- seal the v2 set **before** the L1/L2 work starts, so the product can't adapt to it. The seal order is in §5.

Budget options for the owner:
- **(a) Raise the pool** by about $3. That allows held-out v2 at 25 × 3 runs plus dev at 5 × 3, about $2.3, with headroom for retries.
- **(b) Stay within $2.25,** with held-out v2 at 25 × 2 runs and dev at 5 × 1, about $1.6. It's statistically weaker; say so in the registration.

Pass marks to register:
- dev 5/5 per run;
- held-out v2 ≥ 85% overall and ≥ 80% per run;
- 0 wrong-graph, 0 withheld (by structured codes), ≤ 8 calls per question.

I'm proposing 85% rather than 90%, because v1 showed 65% with known key defects. Set the bar where a pass means something and a fail is diagnosable. The owner decides.

## 5. Order of work for Codex

1. **Fix the measurement tooling (free):**
   - make the withheld detector use structured codes only, with a fixture;
   - make a no-model dry run of every harness path a precondition for any paid dispatch.
2. **Build and seal held-out v2 (§4.4) now,** before any L1 or L2 work. That needs a small generation spend, about $0.05, plus the reviewer pass. Commit the seal.
3. **Build `scripts/eval_retrieval_offline.py`** (§4.1). Repair the v1 keys into the development set, record baseline numbers, and commit them.
4. **L1 (§4.2):** multi-query search, tool guidance, weak-hit hints. Write RED oracles, then offline measurement, then full verify and the preset smoke.
5. **L2 (§4.3):** only after the owner approves the optional dependency. Then offline measurement, plus ingest overhead.
6. **Stop** and report the offline results to the owner, with a budget recommendation (§4.5).
7. The paid cycle, only on explicit owner approval, then stop whatever the result.

All of this is post-release quality work. **It doesn't block** finalisation roadmap stages F1–F4 (owner decisions, merges, release hardening, acceptance), which can proceed in parallel. The release notes should state the current result: wave 4 gate passed 12/15; quality track dev 15/15, held-out v1 49/75 with disclosed item defects.

## 6. Owner decisions requested

1. Approve the optional local semantic channel (`geo-grapher[semantic]`, model2vec, local only)?
2. The budget for the final measurement: raise the pool by about $3 (option a), or stay within $2.25 (option b)?
3. The held-out v2 pass mark: 85% overall and 80% per run (proposed), or keep 90% and 88%?
4. Whether to proceed with F1–F4 (merges and release) in parallel with this quality track. Recommended: yes.

## 7. Owner decisions (2026-11-13) and the reliability approach

**Decisions:**
- **The L2 semantic channel is approved.** It ships as the optional, local-only extra `geo-grapher[semantic]`, using `model2vec` static embeddings (with `fastembed` optional). It is off by default. Source code is never sent to a hosted embedding service.
- **Budget:** the owner added $6, so **$8.25 is available** in the `geo-grapher` pool. Spending still goes through receipts and the ledger, every paid run is registered before dispatch, and a no-model dry run comes first.
- **F1–F4** (the release track) may proceed in parallel. Merging and pushing still need explicit owner approval.
- **The reliability approach changes.** Don't try to guarantee single-shot reliability. Instead, **identify the predictable failure patterns, detect each one at run time, and attach a bounded recovery or remedial workflow to it.** Success is measured end to end with recovery, and first-attempt success is still reported separately, for honesty.

### 7.1 The failure-pattern catalogue

Every pattern below was observed in this project's evidence:

| ID | Pattern | Evidence | Run-time detector | Recovery or remedy |
|---|---|---|---|---|
| FP1 | **Query compression**: the agent's keywords drop the question's distinguishing words | Agent queries hit 32% (33/102); the question text hits 13/25 | Low fused top-hit score, or no hit whose `doc_gist`/`why` shares ≥ 2 content words with the question | Re-search once, automatically, with the question (or its key sentence) verbatim plus the agent's terms; multi-query fusion |
| FP2 | **Vocabulary mismatch**: a paraphrase of the docs | 12/25 miss even verbatim | Lexical and semantic top-8 lists disagree; low lexical confidence | Semantic channel (L2). Return the fused list, with `match: lexical\|semantic\|both` per hit |
| FP3 | **Retrieved but not opened**: the answer is in the hits and skipped | Wave 4: the target at #1 and skipped | Final answer cites no entity whose gist overlaps the question, while a top-3 hit does | One bounded "check the top unopened candidate" step before answering |
| FP4 | **Delivered but not used**: the answer is in the opened source but missing from the answer | Wave 4 run 1 (×2); held-out Q16 run 3 | Self-check: does a delivered range define the asked-for thing that the answer doesn't name? | A revision pass (P3, re-tested **validly** this time) |
| FP5 | **Wrong granularity**: the answer names the function and not the constant, or the reverse | Q02 | The answer names an entity adjacent (reads or calls) to the defining entity | The answer contract names both the defining identifier and the place it's applied. In scoring, keys are equivalence sets (§4.4) |
| FP6 | **Invalid or mistyped IDs** | Waves 3–4 | A structured error code | Scoped ID recovery with real candidates (done in A3.2) |
| FP7 | **Step-limit exhaustion** | Wave 4 run 1 | `completed_at_step_limit` | Final synthesis from the evidence (done in A3.1). Also log which pattern consumed the steps |
| FP8 | **Measurement defects**: a harness profile error; substring detectors; garbled or mis-keyed items | §19 | No-model dry run; structured-code detectors; two-reviewer item checks | Block paid dispatch until they're clean (§5 step 1) |

### 7.2 How a recovery workflow must behave

- **Bounded.** At most one recovery action per pattern per episode, and recoveries share a budget of at most 3 extra steps per episode. Without that, recovery becomes unbounded retrying.
- **Deterministic triggers.** Detectors use structured signals (scores, overlaps, error codes, coverage records), never model judgement. Only FP4's self-check uses a model call, and it's counted in the step budget.
- **Logged.** Every episode records `recoveries: [{pattern, trigger_value, action, outcome: resolved|unresolved}]` in the receipt and the benchmark row.
- **No leakage.** Recovery never uses the answer key, the marker list or any benchmark-specific text. Each trigger and remedy must be valid for an arbitrary user question.
- **Placement:**
  - **search-side** remedies (FP1, FP2, FP6) live in Geo-Grapher's front door and work for every client;
  - **agent-side** remedies (FP3, FP4, FP7) live in the Librarian `code-research` role's loop.

### 7.3 Measurement with recovery

- **Offline first, at no cost.** Extend `eval_retrieval_offline.py` to simulate FP1 and FP2 recovery: for each recorded agent query, apply the detector and the re-search. Report recall@8 before and after recovery, plus the trigger rate and the false-trigger rate (how often a recovery fires when the original was already right).
- **One small paid diagnostic pilot** (about $0.5), before the final cycle: the 30 development questions (the 5 originals plus the 25 repaired v1), 1 run, all recoveries on. Its purpose is to measure trigger and recovery rates per pattern, and to find new failure patterns. It is not a gate. Any new pattern found is added to §7.1 with a detector and a remedy, then re-measured offline.
- **The final registered cycle** (about $3–3.5 with recovery steps): held-out v2 at 25 × 3 runs plus dev at 5 × 3. Register:
  - end-to-end success with recovery ≥ 85% overall and ≥ 80% per run;
  - dev 5/5 per run;
  - 0 wrong-graph, 0 withheld (by structured codes), ≤ 10 calls per question on average (the limit is raised from 8 to allow bounded recovery);
  - also report **first-attempt success** (before any recovery fires) and **per-pattern recovery rates**. These are not gated, but must be shown.
  
  Stop after this cycle, whatever the result.
- **Budget check:** about $0.05 for generation, $0.5 for the pilot and $3.5 for the final cycle, about $4.05 in total, against $8.25 available. Keep at least $2 in reserve. If the dry run estimates more than $5, stop and ask the owner.
