# Phase 6-7 wave 1 gate report

Branch `phase67-wave1`. Measured on copies of the real catalog and the four graph stores under
`output/phase67-gates/wave1/` (made with sqlite3 `backup()` from read-only handles; `code_database` and
`paper_database` re-pointed in the copied catalog; originals never opened for write). No product code was changed.

Method notes:

- Frames: `viewport_frame` schema 1.1, `sphere-affinity-v1` unless stated, `node_budget` 120, `curve_budget` 200, `seed` `view-v1`, `beta` 0.8, default filter, `grouping` file (`kind=file`) and atomic.
- Root frames focus the repository (context radius 1). Because the root frames of ToolSet contain no fragment nodes at all, the label, badge and documentary-link metrics also use "document-focus" frames: the 5 documents with the most fragments in each graph, context radius 2. Tables below aggregate root + 5 document frames (6 frames per cell).
- Layout diagnostics (bands, cosines) were captured by wrapping `geometry.pack_siblings_affinity` and calling `geometry.layout_bands` on the captured inputs. Overlap is the sibling sphere penetration > 1e-4 recomputed from the frame spheres.
- Latency: one fresh Python process per sample (no in-process layout or service cache), 3 repetitions. The time covers `GraphRouter.acquire` (opens the store, builds the service context) plus the `viewport_frame` query, on a copy that already holds the persisted analysis views.

## 1. Brief items (ToolSet and librarian-v2)

### 1.1 Label quality

| Graph | View | Frames | Labelled nodes | `Documentation · line` labels | Duplicate labels per parent | Labels needing snippet or number | of which snippet | of which number | Path-prefix disambiguation | Plain |
|---|---|---|---|---|---|---|---|---|---|---|
| ToolSet | file | 6 | 512 | 0 | 0 | 489 (95.5%) | 396 | 93 | 2 | 21 |
| ToolSet | atomic | 6 | 504 | 0 | 0 | 404 (80.2%) | 316 | 88 | 26 | 74 |
| librarian-v2 | file | 2 | 192 | 0 | 0 | 168 (87.5%) | 166 | 2 | 0 | 24 |
| librarian-v2 | atomic | 2 | 169 | 0 | 0 | 102 (60.4%) | 100 | 2 | 0 | 67 |

Duplicate counting is over (parent, display_label) among labelled nodes. Frame-wide duplicate labels across different parents: 2 in ToolSet atomic, 0 elsewhere (allowed, only per-parent uniqueness is required). The share is high because the sample is fragment-heavy documentation frames; ToolSet root frames have no fragment nodes (17/43 labelled nodes, 0 snippets or numbers).

### 1.2 Role badges (non-synthetic nodes in the same frames)

| Graph | View | none | Spec | Entry | Util | Gate | IO | Core | Schema |
|---|---|---|---|---|---|---|---|---|---|
| ToolSet | file | 44 | 499 | 0 | 0 | 0 | 0 | 0 | 0 |
| ToolSet | atomic | 86 | 414 | 24 | 6 | 3 | 1 | 1 | 0 |
| librarian-v2 | file | 220 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| librarian-v2 | atomic | 164 | 0 | 0 | 9 | 1 | 3 | 2 | 0 |

### 1.3 `sphere-affinity-v1` diagnostics

| Graph | View | Layout calls (K>=2) | Sibling pairs | Overlaps (> 1e-4) | `packing.max_violation` | Fallback parents |
|---|---|---|---|---|---|---|
| ToolSet | file | 34 | 24,342 | 0 | 9.89e-5 | 0 |
| ToolSet | atomic | 43 | 17,422 | 0 | 9.96e-5 | 0 |
| librarian-v2 | file | 4 | 9,042 | 0 | 8.95e-5 | 0 |
| librarian-v2 | atomic | 16 | 4,483 | 0 | 9.82e-5 | 0 |

Mean `r_norm` per band (sibling count in brackets):

| Graph | View | core | mantle | crust | core < mantle < crust |
|---|---|---|---|---|---|
| ToolSet | file | 0.1774 (76) | 0.4973 (57) | 0.9467 (563) | yes |
| ToolSet | atomic | 0.1416 (49) | 0.4664 (26) | 0.9492 (564) | yes |
| librarian-v2 | file | 0.0500 (2) | none (0) | 0.9500 (115) | yes (two bands only) |
| librarian-v2 | atomic | 0.1342 (16) | 0.5145 (15) | 0.9500 (200) | yes |

Mean cosine between sibling centre vectors (local offsets), affine pairs (affinity > 0) vs zero-affinity pairs:

| Graph | View | Affine cosine (pairs) | Zero cosine (pairs) | Affine > zero | Calls where affine > zero |
|---|---|---|---|---|---|
| ToolSet | file | -0.0496 (412) | -0.0115 (26,917) | NO | 7/12 |
| ToolSet | atomic | -0.0806 (207) | -0.0109 (26,327) | NO | 3/6 |
| librarian-v2 | file | -0.9962 (1) | -0.0114 (4,914) | NO (1 pair) | 0/1 |
| librarian-v2 | atomic | -0.2632 (26) | -0.0132 (8,100) | NO | 1/5 |

Root-frame-only sample (context radius 1) for ToolSet: file -0.0141 vs -0.0581 (361 / 672 pairs), atomic -0.0421 vs -0.1462 (166 / 152 pairs): affine > zero holds there. librarian-v2 root-only: file -0.9962 (1 pair) vs -0.0114, atomic -0.1682 (22) vs -0.0159: does not hold. See defect D1.

### 1.4 Cold frame latency (extra item 1, limit 3.0 s, C14)

Seconds, fresh process, three repetitions (rep1 / rep2 / rep3):

| Graph | View | `sphere-affinity-v1` | `sphere-pack-v1` | Nodes / curves (affinity) |
|---|---|---|---|---|
| ToolSet | file | 2.307 / 2.303 / 2.259 | 2.210 / 2.191 / 2.190 | 23 / 33 |
| ToolSet | atomic | 2.151 / 2.138 / 2.140 | 2.088 / 2.064 / 2.083 | 49 / 39 |
| librarian-v2 | file | 1.184 / 1.190 / 1.170 | 1.120 / 1.102 / 1.113 | 111 / 0 |
| librarian-v2 | atomic | 1.125 / 1.122 / 1.109 | 1.165 / 1.187 / 1.152 | 77 / 21 |

Worst `sphere-affinity-v1` ToolSet case: 2.307 s (limit 3.0 s). Affinity overhead against pack: about +0.05 to +0.10 s on ToolSet. Almost all the time is store open plus context build (the same for both layouts).

### 1.5 Documentary links and curve families

| Graph | View | Documentary links | Link families | Link roles | Curves | Curve families | Runtime status |
|---|---|---|---|---|---|---|---|
| ToolSet | file | 68 | doc_describes 62, doc_rationale 6 | discusses 56, documents 6, rationale_for 6 | 33 | hierarchy 23, call_or_data 10 | exact 33 |
| ToolSet | atomic | 138 | doc_describes 91, doc_rationale 47 | discusses 48, documents 43, rationale_for 47 | 45 | hierarchy 21, call_or_data 24 | exact 45 |
| librarian-v2 | file | 0 | none | none | 0 | none | none |
| librarian-v2 | atomic | 0 | none | none | 24 | call_or_data 24 | exact 24 |

(ToolSet root-frame-only: file 33 curves = hierarchy 23 + call_or_data 10; atomic 39 curves = hierarchy 21 + call_or_data 18; 0 documentary links in all root frames and in every librarian-v2 frame.) `doc_cites`, `catalog_bridge`, `violation` and non-`exact` runtime statuses do not occur in these samples.

### 1.6 Discovery card (extra item 2, limit 1,100 tokens)

Tokens counted with `geographer.tokens.TokenCounter` (o200k_base) over the Markdown from `python -m geographer discovery-report --store ... --out ... --json ...`.

| Graph | Markdown tokens | Markdown bytes | QCICS section | ABBS section | SCBBS section | Header and rest | JSON tokens |
|---|---|---|---|---|---|---|---|
| ToolSet | 485 | 1,147 | 16 tok, 0 rows | 210 tok, 5 rows | 195 tok, 5 rows | 64 tok | 1,778 |
| librarian-v2 | 114 | 303 | 16 tok, 0 rows | 17 tok, 0 rows | 16 tok, 0 rows | 65 tok | 230 |

Both below 1,100. Each section holds at most 5 rows. librarian-v2 has no cycles, bottlenecks or surprising links at file granularity (6 files), so every section reads `none`.

### 1.7 Federation selection (5 queries, 4 graphs, 4,096 and 8,192, all 24 permutations)

`GraphRouter.federated_search(permutation, query, limit_tokens=...)` called for each of the 24 orderings of the four graph IDs. Compared everything except the echoed `graph_ids`: `results`, `omitted`, `used_tokens`, `selection`. Mismatches across permutations: **0 of 240 cells** (every cell identical). Graphs: A = ai-research-papers, L = librarian-v2, T = ToolSet, M = timeline-mapping.

| Query | Budget | Tiers (A / L / T / M) | Utility (A / L / T / M) | used_tokens | Omitted reasons |
|---|---|---|---|---|---|
| graph retrieval token efficiency | 4096 | omit x4 | 0 / 0 / 0 / 0 | 365 | no_relevant_hits x4 |
| graph retrieval token efficiency | 8192 | full / full / full / omit | 2519 / 1647 / 582 / 0 | 4,278 | M no_relevant_hits |
| sqlite snapshot store | 4096 | omit x4 | 0 x4 | 365 | no_relevant_hits x4 |
| sqlite snapshot store | 8192 | full / omit / full / omit | 1693 / 0 / 582 / 0 | 2,546 | L, M no_relevant_hits |
| Paul Warburg | 4096 | omit x4 | 0 x4 | 365 | no_relevant_hits x4 |
| Paul Warburg | 8192 | full / omit / omit / full | 853 / 0 / 0 / 3302 | 2,727 | L, T no_relevant_hits |
| manifest validation workflow | 4096 | omit x4 | 0 x4 | 365 | no_relevant_hits x4 |
| manifest validation workflow | 8192 | full / full / full / omit | 2519 / 830 / 2819 / 0 | 4,174 | M no_relevant_hits |
| librarian vault resource | 4096 | omit x4 | 0 x4 | 365 | no_relevant_hits x4 |
| librarian vault resource | 8192 | full x4 | 2519 / 2451 / 1718 / 3302 | 6,516 | none |

Every response has `ranking='independent_per_graph_no_global_rank'` and `selection.method='pc-mckp-v1'`. At 4,096 with four graphs every query returns nothing, although the same queries return hits at 8,192 and at 4,096 with two graphs (for example Paul Warburg over A and M at 4,096 returns both `full`, used_tokens 2,301). See defect D2.

### 1.8 Federated-search consumers (extra item 3, read only)

Failed graphs now appear only in `omitted` with reason `GRAPH_UNAVAILABLE` (not in `results`).

| Script | Reads `federated_search` results? | Contract exposure | Verdict |
|---|---|---|---|
| `scripts/librarian_harness.py` | No. No call, no parse of `results`/`omitted`/`selection`. "federated" is only a probe kind: the prompt (lines 70-72) tells the model to use `list_graphs` and query each graph with `paper_search_documents`. It reads `body['result']['results']` of a single-graph `paper_search_documents` call (line 233). | none | Still works, unaffected |
| `scripts/eval_graph_leakage.py` | No. Same pattern: federated probes expose per-graph `paper_*` tools with a `graph` enum (`tool_defs`); attribution is parsed from the model's answer text (`federated_attribution`). | none | Still works, unaffected |

Only other consumer of the federated tool in the tree is `graph_server.py`, which passes the router result through unchanged.

## 2. Pass or fail per criterion

| # | Criterion | Result |
|---|---|---|
| 1 | `Documentation · line` labels = 0 (file and atomic, both graphs) | PASS (0 in all 4 cells) |
| 2 | Duplicate visible labels per parent = 0 | PASS (0 in all 4 cells) |
| 3 | Share needing snippet or number reported | PASS (recorded, 60% to 96% in fragment-heavy frames) |
| 4 | Role badge distribution reported | PASS (recorded) |
| 5 | Affinity overlaps = 0 | PASS (0 of 55,289 sibling pairs, max_violation < 1e-4) |
| 6 | Mean `r_norm` core < mantle < crust | PASS (ToolSet, librarian-v2 atomic; librarian-v2 file has two bands only) |
| 7 | Mean affine-pair cosine > zero-affinity cosine | FAIL (see D1; holds only on ToolSet root frames) |
| 8 | Cold affinity frame latency <= 3.0 s (C14) | PASS (max 2.307 s ToolSet file) |
| 9 | Documentary link count reported | PASS (ToolSet 68 file / 138 atomic; librarian-v2 0) |
| 10 | Curve family distribution reported | PASS (recorded) |
| 11 | Discovery card tokens <= 1,100 | PASS (485 ToolSet, 114 librarian-v2) |
| 12 | Federation: 5 queries x 4 graphs x {4096, 8192}, every permutation identical | PASS (0 mismatches in 240 cells) for permutation invariance; but see D2 for 4,096 content |
| 13 | Federation consumers still work with the new contract | PASS (neither script reads `federated_search`) |
| 14 | `scripts/verify.ps1` exits 0 | PASS (exit 0) |

## 3. `scripts/verify.ps1`

`powershell -ExecutionPolicy Bypass -File scripts/verify.ps1` exited 0. Backend: 455 passed, 13 warnings. Playwright: 14 passed.

```
backend (full suite)   ok (112s)
frontend typecheck     ok (2s)
frontend build         ok (3s)
browser suite          ok (21s)
```

## 4. Defects found (recorded, not fixed)

- **D1. Affinity layout does not draw affine siblings closer on real graphs.** Mean cosine between sibling centre vectors is lower for affine pairs than for zero-affinity pairs in all four ToolSet and librarian-v2 cells when document-focus frames are included (ToolSet file -0.050 vs -0.012, atomic -0.081 vs -0.011; librarian-v2 atomic -0.263 vs -0.013), and per call affine > zero in only 11 of 24 calls. It holds only on ToolSet root frames. Caveats: librarian-v2 has very few affine pairs (1 to 26) and many parents with K = 2 or 3, where the force layout places siblings antipodally, which dominates the mean. Needs a decision on whether the criterion should be pair-count weighted and K >= 4 only, or the force term in `pack_siblings_affinity` strengthened.
- **D2. Federation at 4,096 tokens with four graphs returns nothing and mislabels why.** `per_graph = max(512, (limit - 1000) // n)` gives 774 tokens, below the 793-token minimum for a successful `search_entities` envelope. The graph router wraps the response as `{graph_id, result:{error:BUDGET_TOO_SMALL}}`, so the `'error' in envelope` test in `federated_search` never fires. The envelope counts as "no hits" and every graph is reported `no_relevant_hits` (used_tokens 365 of 4,096). Same queries return hits at 8,192, so the reason is wrong and 3,700 tokens go unused.
- **D3 (observation, minor).** In fragment-heavy documentation frames 17% of ToolSet atomic labels (88 of 504) still fall back to ` (n)` numbering after the snippet step. No documentary links appear in any librarian-v2 frame, and no `doc_cites`, `catalog_bridge`, `violation` or non-exact runtime status occurs in any sampled frame, so those paths are not exercised on real data.
