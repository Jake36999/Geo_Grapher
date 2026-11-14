# Review 5: a scientific assessment of the code-quality programme

Reviewer: the lead agent of waves 1–3. Date: 2026-11-14.

Inputs:
- `PHASE67_REVIEW4_FINAL_RESULTS.md`;
- gate report §§19–Review 4;
- the offline series `PHASE67_OFFLINE_*`;
- the registered cycles of waves 4 and 5.

I also computed confidence intervals and gate-power figures myself (§4). **Registered verdicts stand as recorded; nothing here rescores them.**

## 1. What happened, in one paragraph

Across four registered measurements the code agent went:

| Measurement | Result |
|---|---|
| Wave 4 first | **0/5** |
| Wave 4 continuation | 12/15 |
| Held-out v1 | **49/75 (65%)** |
| Held-out v2 | **70/75 (93%)** |

That came at falling cost (calls per question went from 12 to 4.5) and with zero wrong-graph and zero withheld results throughout the last three cycles. The final cycle FAILED its registration **only** on the development condition "5/5 in every run" (it scored 5/5, 5/5, 3/5). The held-out conditions were passed with room to spare.

The gain came almost entirely from **better evidence before the first answer**: the agent-facing interface, constants, scent, multi-query and semantic search. **None of it came from post-answer recovery**, which rescued 0 drafts and harmed 2. The gate that failed was statistically mis-specified (§4), and I wrote that condition.

## 2. What worked: keep these as standing practice

| Practice | Evidence it earned its place |
|---|---|
| **Fix the interface before blaming the model** | Raw wire requests: 0/5 with 10–11 errors per question. Flat front door: 3/5 with 0 errors. That one change did more than any model choice. |
| **Diagnose from per-call evidence, not scores** | Every major lever came from reading per-call logs: unindexed constants, aliases, "retrieved but skipped", query compression. |
| **A free offline proxy before any paid run** | On dev30 recorded agent queries, recall@8 went from **36/102 → 48 (L1) → 69 (L2) → 82 (runtime recovery)**, and the recommended query style reached 93/102 (91%). The online held-out result, 93%, **matched the offline prediction**. The proxy was cheap and predictive; it's the most valuable tool built in this programme. |
| **Blinded, sealed sets, built before product changes** | v2 was sealed before L1 and L2. The lead never saw it. That's why 93% can be believed. |
| **Two-reviewer keys with equivalence sets** | v1's 4 defective items (16%) inflated the miss count. v2's construction rejected and regenerated items before sealing. |
| **A diagnostic pilot before the gate** | It discovered **FP9**, a pattern nobody had predicted, in which revisions proposed protocol or XML tool text. It was then detected offline (14 true detections and 76 true negatives), and it safely rejected 7 bad revisions in the final cycle. |
| **Mandatory no-model dry runs** | After the A/B that a harness setup error wasted, every paid path passed a real-tool dry run first. Zero further invalid runs. |
| **One cycle, then stop** | No best-of selection, no retuning between runs, and the first results kept. That's why the trend is credible. |
| **Spending discipline** | Review 4 spent $4.51 against a $6.50 cap; the final cycle cost $1.90 against an estimate of about $3.5. |

## 3. What didn't work, and why

### 3.1 Post-draft recovery added nothing, and FP4 was net harmful

| Pattern | Triggered | Final correct among triggered | Wrong→right |
|---|---:|---:|---:|
| FP3 (check an unopened candidate) | 8 | 7/8 | **0/7** |
| FP4 (self-check and revision) | 11 | 9/11 | **0/11**, plus **2 correct drafts regressed** |

These signals mostly fired on drafts that were **already correct**: 7 of FP3's 8 and 9 of FP4's 11. Their detectors had low precision, and a remedy applied to a correct answer can only make it worse. The two regressions turned correct drafts into "citation-only, fragmentary prose".

This matches a well-known finding: same-model self-correction without an *external* signal tends to degrade answers as often as it improves them. Reflexion's gains (doc:68) rely on feedback from the environment, not on self-assessment.

**The lesson:** a remedy has to *dominate* the original before it may replace it, and a detector's precision must be measured against gold labels before the remedy goes live.

### 3.2 Search-side recovery works, but it's credited in the wrong place

FP1 and FP2 act **before** the first draft, so "wrong→right among drafts = 0/15" can't credit them by construction. Their real effect shows up in the offline replay (+30 hits: 52→82) and in the 94.3% initial-draft accuracy. **Attribution must be measured at the stage where the remedy acts.**

### 3.3 Signals that are never "resolved" don't measure what matters

FP3 and FP4 show "resolved 0" in every episode, yet most of those episodes ended correct. These detectors don't correlate with correctness, so they're not yet *diagnostics*; they're noise generators.

### 3.4 The failing gate was mis-specified, and that was my error

"Development 5/5 in every run" across 3 runs means 15 consecutive successes. The probability of passing that, at a per-question reliability p, is p¹⁵:

| True per-question reliability | P(dev gate passes) | P(held-out ≥ 20/25 every run) |
|---|---:|---:|
| 0.90 | 0.21 | 0.90 |
| **0.933 (the measured held-out rate)** | **0.35** | **0.98** |
| 0.95 | 0.46 | ≈1.00 |
| 0.99 | 0.86 | ≈1.00 |

A system as good as this one measured **fails that gate about two times in three**. It demanded roughly 99% reliability from a 5-item set, which is closer to a coin toss than a measurement.

The development questions are also *harder* than held-out v2. `lead_agents` and `run_one` both have plausible adjacent mechanisms, such as a `ThreadPoolExecutor` cap and queue routing. Those two items account for all 4 development misses across this programme's last two cycles.

### 3.5 Scoring brittleness remains

`heldout-v2-25` named the class, the method, the file and the canonical citation in all three runs, but the marker required the contiguous `SessionStore._lines_through`. That's 3 of the 5 held-out misses. The registered score stands. Prospectively, though, the scorer should accept a qualified identity expressed in parts.

## 4. How confident should we be? (95% Wilson intervals)

| Measurement | Point estimate | 95% CI |
|---|---:|---|
| Held-out v1 (defective items included) | 49/75 = 65% | 54–75% |
| **Held-out v2** | **70/75 = 93%** | **85–97%** |
| Development (final cycle) | 13/15 = 87% | 62–96% |
| Initial drafts | 83/88 = 94% | 87–98% |

The v1 → v2 jump is real: the intervals don't overlap. It's **confounded**, though, because the product changed (L1, L2, recovery) *and* the instrument changed (repaired keys, a new item population). The offline series (§2) attributes most of it to retrieval: on the same 30 development questions, recorded-query recall went from 35% to 80%. A clean estimate of the measurement-repair share would need v1-repaired scored on the final product, which can be done offline at no cost (§6.3).

**Representativeness caveat.** Both held-out sets sample *documented* entities, so 93% is an estimate for "questions answerable from the code's own documentation". Real user questions may be vaguer. That's an untested population.

## 5. Decisions recommended to the owner

1. **Accept the code-agent capability for the release notes as measured:** "held-out v2 93% (CI 85–97%), development 87%, registered gate FAIL on a development-perfection condition shown to be under-powered". No further cycle is needed for release.
2. **Turn FP4 off, or change it to "dominance-only" (§6.2), before release.** It's the only component with measured harm. FP3 should stay off unless its precision is shown to be useful. Keep FP1, FP2, FP6, FP7 and FP9.
3. **Proceed with F1–F4** (the decisions, merges and release). The quality track no longer blocks anything.

## 6. Adjusting future improvement work

### 6.1 Gate design: power first

- Before registering a gate, **compute the probability that a system at the target reliability passes it**. Require ≥ 0.8 at the target, and ≤ 0.2 at an unacceptable level. The script is in this review's appendix method.
- Don't require perfection on small sets. Use **per-item persistence flags** instead: an item failing in ≥ 2 of 3 runs is a diagnostic finding, not an automatic gate failure.
- Report **Wilson intervals** next to every rate.

### 6.2 Remedies: do no harm

- A remedy may replace a draft **only if** the revision keeps every identifier and citation the draft had and adds the defining entity; otherwise the original is kept. In short: append, don't rewrite.
- **Measure detector precision against gold** on development data before enabling a remedy. Enable only if precision ≥ 0.5 and the offline or A/B net effect is > 0.
- Credit remedies at the stage where they act: search-side by retrieval recall, answer-side by draft→final transitions.

### 6.3 Attribution: offline ablation as standard

- For every candidate, run the offline suite with each lever toggled (L1, L2, FP1, FP2, pagination). It costs nothing, so always report the ablation table.
- Score **v1-repaired** offline on the final product, to separate product gains from instrument repair.

### 6.4 Measurement

- Make the scorer accept qualified identities written in parts. This applies prospectively only.
- Add a **distractor stratum**: questions whose answer has a plausible adjacent mechanism, like `lead_agents`. That's where the residual errors live.
- Add a **real-usage stratum**: questions drawn from the owner's actual Librarian sessions, reviewed and sealed. That tests representativeness.

### 6.5 Where to look next for accuracy

The remaining misses cluster in three places:
- **adjacent-mechanism confusion**, where the answer chooses a nearby mechanism over the direct one;
- **delivered but not used**;
- **mechanical scoring**.

The first two are answer-selection problems, not retrieval problems. The most promising lever is **contrastive evidence presentation**. When search finds several mechanisms for one concept (for example, two different caps), return them grouped, with the data-flow relation between them ("`lead_agents` bounds `asked`, which sets `max_workers`"), using the static reads/calls graph Geo-Grapher already has. Then the answer is chosen from an explicit comparison, rather than from whichever entity was opened first. Test it offline on the distractor stratum before spending anything.

## Appendix: the gate-power method

For a pass rule over n items and r runs, compute P(pass | p) analytically (binomial) at the target and failure values of p. Example: "≥ 20/25 per run × 3 runs" at p = 0.93 gives 0.98, and at p = 0.80 gives 0.23. It discriminates well, though a system at 0.80 still passes about one time in four; tighten to ≥ 21/25 if 0.80 must fail more reliably. "5/5 per run × 3 runs" gives 0.35 at p = 0.93 and 0.04 at p = 0.80, so it rejects good systems. Commit the calculation next to every registration.

## Decision record

- **2026-11-14: FP4 switched off by owner decision (§5.2).**
  - Librarian `geo-grapher-wave4` `737ea28` sets `code-research` `answer_self_check` to False and inverts the pinning test (RED, then GREEN). The full suite gives 2,221 passed, 2 skipped and 5 deselected, the same as the verified candidate.
  - Geo-Grapher `214d8cd` updates `docs/phase67/RECOVERY_DESIGN.md` and `AGENT_MCP_GUIDE.md`.
  - The FP4 mechanism and its explicit-opt-in tests remain.
  - **No paid evaluation was run on the changed default.** The released default therefore differs from the configuration measured in the final cycle. Based on that cycle, the expected effect is that the 2 FP4 regressions disappear, but this is unmeasured. Measure it, if wanted, with the offline and dev suite rather than a new paid cycle.
