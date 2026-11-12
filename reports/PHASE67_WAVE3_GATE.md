# Phase 6–7 Wave 3 gate (structure)

Branch `phase67-wave3`, gate run 2026-11-12. Originals were only read:
- the Librarian source used for the staleness pilot is a scratch copy;
- the paper database is a copy under `output/phase67-gates/wave3/`;
- ToolSet and librarian-v2 measurements reuse the wave 2 gate catalog.

Wave 3 shipped:
- T1, path-atomicity guards;
- T2, `directed-helper-condensation-v1`;
- T3, directed QI with additive block packing and the κ′ anomaly boost;
- T4, typed snapshot-bound bridges with reviewed proposals;
- T5, `lineage-v1` staleness;
- T6, `analyze_cross_graphs` and the `cross` preset;
- T7, derived-graph pruning, the guarded directory picker and the ingest UI.

The gate found one product gap, fixed before this report (§3). It also found one tuning weakness, listed for the owner (§2).

## 1. Directed contraction on ToolSet

Each figure below is from a cold, fresh process, 3 repetitions.

`get_architecture_context` takes atomic grouping, `context_radius` 2 and `qi.enabled`. The focus is the first first-party function.

| Algorithm | Query s (rep 1 / 2 / 3) | Process s, incl. imports and store open | Blocks (members) | `directed_reachability_preserved` |
|---|---|---|---|---|
| `helper_tree_balls_v1` | 2.844 / 2.770 / 2.768 | 3.97 / 4.14 / 3.89 | 2 (4) | false |
| `directed-helper-condensation-v1` | 2.088 / 2.087 / 2.088 | 3.21 / 3.21 / 3.20 | 112 (459) | **true** (`existential_member_reachability`) |

Directed certificate:
- 191 candidates, 112 accepted;
- rejected: `overlaps_accepted` 69, `ports_incomplete` 9, `protected` 1;
- no `not_convex` and no `creates_cycle` rejections.

C14 (3.0 s cold query): both algorithms meet it on ToolSet. librarian-v2 is still slower, at 4–5.7 s warm. That time is the pre-existing QI partition persistence and actor preparation, which helper mode pays too (11 s cold). It is carried forward (§6).

**Property check on 50 real sub-DAGs.** Each sub-DAG is drawn from ToolSet with seed 20261112: the SCC condensation of exact static calls between functions of 1–4 random files, 1–42 vertices. The results:
- acyclic quotient in all 50;
- existential member reachability in all 50;
- every quotient arc witnessed in all 50;
- 119 blocks formed in total.

## 2. Bridge pilot: ai-research-papers → librarian-v2

The pilot ran `propose_bridges(kind='reference')` in 1.33 s and stored only 2 proposals at ≥ 0.30:

| Score | Features (alias / citation / neighbours) | Paper endpoint | Code endpoint | Hand review |
|---|---|---|---|---|
| 0.456 | 1.0 / 0 / 0.031 | doc:109 §468 "Taxonomy" (*Advances in LLM-Assisted Combinatorial Optimization*) | `src/resource_librarian/tools/taxonomy.py` (file) | **reject**: homonym |
| 0.455 | 1.0 / 0 / 0.023 | the same section | `src/resource_librarian/taxonomy.py` (file) | **reject**: homonym |

**Precision at ≥ 0.30: 0 of 2.** The plan asked for 10 reviewed proposals. Only 2 exist because the paper corpus's concept and section names rarely match code names exactly.

**Finding (tuning, owner decision).** The homonym firewall (Ψ = 0.25) applies only when the citation and neighbour features are *both* zero. Here one shared generic neighbour name, a Jaccard of 1/32, lifted a pure name match from 0.1125 to 0.456. The code follows master G4 exactly; the weakness is in the rule.

Proposed amendment: apply Ψ unless `shared_citation = 1` or `neighbour_jaccard ≥ 0.2`. Under it, both proposals fall to ≈ 0.11 and are not stored. This needs a ruling, so it is not applied.

**Staleness pilot** (master G5). An operator-declared bridge links `concept:1` ("semantic knowledge graphs skg") to `entity:…taxonomy.py.propose` in the scratch copy. An external note depends on that bridge. Each edit below was followed by a re-ingest:

| Edit | Sweep result | Bridge | Note |
|---|---|---|---|
| end-of-line comment on the signature | no change | accepted | accepted |
| new keyword parameter `gate_pilot: bool = False` | 2 passes | **demoted_contestable** | **suspect_stale** |
| revert to the original bytes | — | accepted | accepted |

After the revert, both were re-accepted without the justification being rewritten. The ledger holds 8 append-only rows across both pilot runs.

A side observation from the first attempt: my scripted "cosmetic" edit broke the signature's syntax, so the function disappeared from the snapshot. The sweep demoted the bridge, which is the correct HARD outcome for a vanished endpoint.

## 3. `analyze_cross_graphs` under `--max-result-chars 7500`

**Gap found and fixed.** As first built, `analyze_cross_graphs` ignored the per-connection character cap that `GraphRouter._fit` enforces for the other tools. A Librarian-sized client would have withheld over-size results. It now re-packs under a proportionally smaller token budget until the serialised result fits. Items still drop whole and the cursor still resumes. A pinning test pages every mode under the cap and checks that every item is delivered exactly once.

| Mode | Graphs | Pages | Items delivered / total | Largest result, chars | Withheld (> 7500) |
|---|---|---|---|---|---|
| evolution_diff | librarian-v2 × survey worktree | 400 (cap of the gate loop) | 2,348 / 3,037 | 7,038 | **0** |
| clone_candidates | ToolSet × librarian-v2 | 36 | 278 / 278 | 7,081 | **0** |
| bridge_candidates | ai-research-papers × librarian-v2 | 1 | 2 / 2 | 2,357 | **0** |

At 7,500 characters a page carries about 6 evolution items, so a full 3,037-item diff needs about 500 pages. A capped client should read `header.counts` first and page only what it needs.

## 4. Verification

| Check | Result |
|---|---|
| `./scripts/verify.ps1` | exit 0: backend 625 passed (189 s); frontend typecheck, build and unit ok; browser 17 passed |

## 5. DeepInfra spend

Pool `geo-grapher`: **$0.480 of $10** committed across waves 2 and 3. Wave 3's share was about $0.15:
- drafts: T2 and T5 by Qwen3-Coder-480B; DeepSeek-V4-Pro overran its output budget on both (ruling W3-4);
- reviews: T2 through T7 by Qwen3-Coder.

Model output was treated as a proposal throughout:
- **T2:** the lead rewrote the dominators, subtree generation and quotient update.
- **T5:** the lead rewrote `sweep`.
- **Reviews:** of the 24 findings across T2–T7, one minor finding was valid. The rest were false or style.

## 6. Carried forward

- **Bridge firewall threshold** (§2): needs an owner ruling.
- **QI partition persistence and actor preparation** dominate librarian-v2 latency (4–5.7 s). The cause sits outside the contraction, which takes 0.19 s.
- **G6 invariant II rejects parallel twins** (ruling W3-2). A weaker witness-pairing condition could admit them.
- **No stage-3 `qi-directed:` materialisation** (ruling W3-3).
- **The `external` artifact kind** is registered by tests and the pilot only. Librarian registration is in the wave 5 backlog.
