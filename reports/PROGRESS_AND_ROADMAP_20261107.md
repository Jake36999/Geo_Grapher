# Progress review and roadmap — 7 November 2026

Review of the multi-graph work (isolation → independent graphs → reviewed merge +
shared scene), with fixes applied during the review and the plan going forward.

## Where things stand

| Layer | State | Evidence |
|---|---|---|
| Paper corpus (AI/ML, 130 docs) | Working; `paper-tools-v3` | DeepInfra benchmark: 5/5 questions grounded in the corpus, 3.6 tool calls/query, $0.0065 per 5-question run (Qwen3-32B) |
| Project isolation | Import/mention indexes namespaced per root; search needs explicit scope | `python-ast-symtable-v3-isolated`; pilot showed 0 cross-project edges |
| Independent graphs | One root → one `graph_id`, its own store, aliases, statistics and handles; `graph_id` required on every MCP call | `GraphCatalog`, `GraphRouter`, `geographer://graphs` |
| Collision review | Nested or containing roots stop with `COLLISION_REVIEW_REQUIRED`; `keep_separate` / `child_module`; no automatic merging | `plan_root`, `import_project` |
| Reviewed physical merge | Builds a new derived graph; sources kept; homonyms and duplicate DOIs stay origin-scoped | `graph_merge.py`, `corpus_merge.py`, immutable receipts |
| Shared 3D scene | Up to 4 graph frames in one canvas, disjoint transforms, declared bridges as a separate layer | Preview on :8774 renders two sibling clusters, no console errors |
| Backend tests | **338 passed** (full suite, after the fixes below) | `pytest tests` |

## Issues found in this review

### Fixed

1. **Conceptual grouping regression** — `src/geographer/viewport.py`. The
   "keep automatic detail in the focused project" filter judged every group by its
   anchor's repository. Conceptual and Unmapped components are synthetic groups
   anchored at the workspace root (`@workspace`), so they were all filtered out and
   the frame fell back to structural nodes. Synthetic groups are now judged by the
   repositories of their member atoms, which keeps the isolation guarantee.
   It slipped through because the merge report's regression run was a selected
   subset that excluded `test_phase5_workspace.py`. The full suite caught it.
2. **Temp file leak in merges** — `pipeline/corpus_merge.py` left a
   `papers-building-*.sqlite.policy.json` beside every merged corpus. The policy
   is persisted in `corpus_metadata` and later refreshes read it from there, so
   the temp file is now removed after the build.

### Phase A — done (7 November 2026)

| # | Issue | Resolution |
|---|---|---|
| a | Router never released superseded merge generations. | `GraphRouter` now leases services (`acquire`/`release`/`lease`). A newer generation retires older ones, which close once their last in-flight request releases. The frame composer and mounted per-graph apps hold leases too; stale child apps are dropped. |
| b | `federated_search` aborted entirely if one store failed. | A failing graph now yields its own `GRAPH_UNAVAILABLE` entry; healthy results are kept. Spec updated. |
| c | Over-budget federation dropped the caller's last-listed graph. | Drops the largest envelope first (ties: the later one), independent of argument order. Spec updated. |
| d | `import_project` held the catalog write lock for the whole ingestion. | Ingestion runs outside the transaction; publication re-runs the overlap review in a short `BEGIN IMMEDIATE`. A root registered mid-ingest triggers `CollisionReview`, and a decision reviewed against an older plan is rejected as stale. |
| f | :8765 ran pre-isolation code. | Restarted on current code, along with the :8774 hub. Both must run under `output/wheel-env` (pinned MCP 1.30.0): system Python now has MCP 2.2.0, where `mcp.server.fastmcp` no longer exists, so `serve` / `serve-graphs` fail to start there. Logs: `output/logs/serve-87xx.*.log`. The standalone `doc-graph` server already has an MCP 2.x fallback and is unaffected. |
| g | AI paper corpus not registered as a graph. | Registered as `ai-research-papers` (`g_03a111af7e3130d797ab1772`), root `D:/Resource-Library/06-Papers`, indexing the 88 top-level Markdown papers (388 KB); `pipeline/work/doc_graph.db` (all 200 docs, including the 114 PDFs from `E:/Librarian research`) is attached. Manifest: `output/named-graphs/ai-papers.manifest.json`. |

Verification: **342 backend tests pass** (4 new: federation partial failure,
order-independent omission, writable catalog during ingest, stale decision
rejected); **Playwright multi-graph suite 5/5**.

**Benchmark through the hub** (same 5 questions, Qwen3-32B, real `paper_*` tools,
`graph_id` injected on every call, tool results capped at 8,000 chars):

| Metric | Hand-rolled tools (direct SQLite) | Scoped hub (real tools) |
|---|---|---|
| Grounded answers | 5/5 | 5/5 |
| Tool calls / query | 3.6 | 1.8 |
| Tokens / query | 8,995 | 8,235 |
| Cost / run | $0.0065 | $0.0053 |
| Wrapper overhead | — | ~54 chars (~15 tokens) per call |
| Out-of-scope envelopes | — | 0 |

Routing is transparent: the inner result is exactly what the paper tool returns.
Answer **depth** dropped, though. With the richer real search cards, the model
answers after 1–2 calls: Q3 no longer opens doc 115's "85% token cost" claim
(doc 115 still ranks first for that query), and Q4 names one GNN paper instead of
2–3. That is a tool-surface and prompting issue, carried into Phase B. Note that
real `search_documents` responses are 5–6K chars, so harnesses must not cut
tool output at 3K.

### Still open

| # | Issue | Impact | Suggested fix |
|---|---|---|---|
| e | Merged-corpus concepts are renamed `g_<24 hex> / name`. | Opaque to agents; the hex prefix also lands in the FTS concept column. | Keep the scoped key internally, but expose the graph **label** plus the original name, and keep the prefix out of FTS text. |
| h | `serve-graphs` only runs on MCP 1.x. | A future environment refresh to MCP 2.x breaks the hub. | Port `graph_server.py` to the 2.x `MCPServer` API (it uses `_mcp_server` internals), or keep the 1.x pin explicit in the launch scripts. |

## Roadmap

### Phase A — Hardening ✅
Done; see above. Keep the **full suite** as the gate for every report, not a
selected subset.

### Phase B — Answer depth and leakage evaluation ✅ (7 November 2026)

**Answer depth.** A workflow prompt (search → `get_document(detail='claims')` for
the top 2–3 hits → answer) raised tool calls from 1.8 to 3.2 per query. Q4 now
finds both GNN papers (229, 152), and Q2 and Q5 cite specific claims (cost
$0.0076/run). Q3 is still partial: it correctly reports no graph-vs-dense-vector
comparison but never opened doc 115, whose claims do contain "reduce token costs
by 85% compared to raw image inputs". That is model variance (it stopped at 2
searches despite the 3–6 call instruction), not a tool gap.

**Leakage evaluation.** Two graphs with separate corpora and overlapping
vocabulary and integer IDs, in an isolated catalog (`output/phase-b/`):

| Graph | Corpus | Docs | Claims |
|---|---|---|---|
| `ai-research-papers` | `pipeline/work/doc_graph.db` | 130 | 1,906 |
| `timeline-mapping` | `output/phase-b/timeline-papers.sqlite` (built deterministically from 130 vault notes by `scripts/eval_build_timeline_corpus.py`; claims are note authors' assertions, concepts are `[[links]]`, Timeline-local empty alias policy) | 130 | 1,007 |

20 probes (`scripts/eval_graph_leakage.py`, Qwen3-32B, $0.019, every answer reviewed by hand):

| Probe kind | n | Leaked | Notes |
|---|---|---|---|
| Negative (other domain; often known to the model, e.g. MKUltra, Paul Warburg) | 6 | **0** | All declined with "not in this corpus"; no outside facts supplied |
| Doc-ID trap (`doc:1` in each graph) | 2 | **0** | Each resolved to its own graph's doc 1 |
| Homonym (network / model / node / pattern / knowledge × 2 graphs) | 10 | **0** | Every citation came from the queried graph |
| Federated (two graphs, explicit `graph` argument) | 2 | **0** | Citations grouped under per-corpus headings; each grounded in the right graph |
| **Total** | **20** | **0 / 20** | 0 out-of-scope tool envelopes |

Failures that are **not** leakage (all within one graph):
- **Citation error ×2.** One cites concept 62 ("preston model community wealth
  building") as `doc:62` (a different document). Concept IDs are bare integers
  while documents are `doc:N`, so the model conflated them. The other is a
  spurious "(doc:1)" pointing at an empty search.
- **Recall miss ×1 (+1 inside a federated answer).** "Networks" returned nothing
  in Timeline although 7 documents mention "network" in their claims. The paper
  FTS index (`document_search`) uses the default `unicode61` tokenizer with no
  stemming, so plurals don't match.

The scorer separates `cross_graph_leak`, `prior_knowledge_leak`, `citation_error`
and `recall_miss`; `--rescore` re-scores saved results without model calls. To
re-run, start the evaluation hub and run the probes:

```powershell
$env:PYTHONPATH='F:/uv-data/Geo_Grapher/src;F:/uv-data/Geo_Grapher'
./output/wheel-env/Scripts/python.exe -m geographer serve-graphs --catalog output/phase-b/catalog.sqlite --transport http --port 8776
python scripts/eval_graph_leakage.py --hub http://127.0.0.1:8776/mcp --catalog output/phase-b/catalog.sqlite --out output/phase-b/leakage-results.json
```

**Conclusion for the original question:** with one store per graph and
`graph_id` on every call, an agent did not blend these two corpora. That held
even under homonyms, colliding integer IDs and questions the model could answer
from memory. The remaining quality issues are retrieval recall and ID typing
within a graph.

### Phase B follow-up — paper-tools v4 ✅ (7 November 2026)

Changes (`pipeline/`):
- **Stemmed search** (`paper-read-v4`): `document_search` is recreated each refresh
  with `tokenize='porter unicode61'`, so "networks" matches "network". The read-model
  bump forces a rebuild; pre-v4 corpora answer `READ_MODEL_OUTDATED` until
  `maintain refresh --backup PATH`. `corpus_merge` now checks the current version.
- **Typed IDs** (`paper-tools-v4`): concept IDs are `concept:N` in `get_document`,
  `get_concept` (incl. related-concept endpoints) and `find_by_concept`, and
  `definition_source_document_id` is `doc:N`. Inputs are unchanged.
- **Concept-miss hint**: an empty `get_concept`/`find_by_concept` result says
  concepts are a curated index and points to `search_documents`.
- Tests: 4 new (inflected search, typed IDs, v3→v4 index upgrade, miss hint).
  Suite: 352 pass; 1 failure in `test_main_workspace.py` belongs to Codex's
  concurrent workspace work (expects `content="graphs"`, build renders `integrated`).
- Refreshed: `pipeline/work/doc_graph.db` (backup
  `doc_graph_backup_20261107_195123_pre_v4.db`) and
  `output/phase-b/timeline-papers.sqlite`; raw counts unchanged. :8774 restarted.
  **Claude Desktop's `doc-graph` server still has v3 code loaded and will return
  `READ_MODEL_OUTDATED` until Claude Desktop is restarted.**

Re-measured:

| | v3 | v4 | v4 + miss hint (homonyms only) |
|---|---|---|---|
| Cross-graph leaks | 0/20 | 0/20 | 0/10 |
| Prior-knowledge leaks | 0/20 | 1/20 (minor: suggested GAE/VGAE while correctly declining) | 0/10 |
| Citation errors | 2/20 | 1/20 (spurious "doc:0") | 0/10 |
| Recall misses | 1/20 (+1 in a federated answer) | 3/20, all via concept-only lookups | 1/10 |

5-question benchmark (v4, depth prompt): 3.4 tool calls/query, $0.0080/run.
Q3 now cites doc 115's "85% token cost" claim, though without the caveat that the
comparison is against raw image inputs rather than dense vectors.

### Late 7 November — Codex hand-over, hardening, scaled probes

**Codex's unfinished task (content-sized bubbles)** was complete in code but unverified
when Codex ran out of tokens: file-relative display radii (symbols are fractions
of a file; files/documents grow with lines; enclosures grow to fit) and a
radius-aware spherical fallback replacing the shelf grid. Verified: full suite
passes. On real ToolSet frames, dense folders now pack as round clusters
(anisotropy 1.04–1.13, 0% of siblings on shared grid planes; median radius:
files ~1.8, folders 2.2–2.8, summary groups ~0.8). Playwright 12/12; :8765
restarted on the new geometry. Codex's integrated main workspace (graph picker in
the original toolbar) was already finished and passes.

**Hardening against failures seen this session:**

| Failure seen | Hardening |
|---|---|
| Reports verified on hand-picked test subsets; a regression shipped | `scripts/verify.ps1`: full pytest + typecheck + build + Playwright, judged by exit code (`-Live` adds the :8765 smoke) |
| Servers died at start-up under system Python (MCP 2.2.0) | `require_pinned_mcp()` in the CLI exits with the fix before importing; `scripts/start-servers.ps1` restarts :8765/:8774 under `wheel-env`, only stopping processes whose command line matches, venv launcher included, and health-checks; logs/PIDs in `output/logs/` |
| Agents judged "absent" from search cards (titles/abstracts only) | `matched_claim_excerpt` («match») on cards whose claims contain a query word |
| Agents stopped after one search; concept lookups mistaken for full search | Workflow guidance in the doc-graph server instructions and `search_documents` description (search → open claims → answer; concept index is not evidence of absence) |
| Corpus newer than a running server gave "run refresh" (wrong fix) | `READ_MODEL_OUTDATED` now says "restart this MCP server, do not refresh" when the corpus is newer |
| Evaluation lost a whole run to a provider 429 | Retry with backoff on transient provider errors; results checkpointed after every probe; `--resume` |
| Scorer counted planted IDs echoed in a denial | Excluded when the answer reports absence |
| Reasoning model ended turns with no final answer | Forced tool-free final answer; `no_answer` category; `--resume` checkpoints keep not-yet-reached results |

Tests: 361 backend (5 new), 12 browser.

**Scaled leakage probes** (29: 14 homonym incl. "agents"/"fields", 6 negative,
4 adversarial false-premise/planted-reference, 3 federated incl. "which corpus
covers X", 2 doc-ID traps):

| Model | Cross-graph | Prior knowledge | Citation errors | Recall misses | Cost |
|---|---|---|---|---|---|
| Qwen/Qwen3-32B | 0/29 | 0/29 | 0/29 | 0/29 | $0.030 |
| openai/gpt-oss-120b | 0/29 | 0/29 | 0/29 | 0/29 | $0.136 (6.8 tool calls/probe) |

Across the four Qwen runs this session (20 + 20 + 10 + 29 answers): 0 cross-graph leaks in 79.
With gpt-oss-120b: 0 in 108 answers over two model families. One-sided 95% upper bound
on the per-answer cross-graph leak rate at n=108 is ~2.7%.

gpt-oss-120b researches more (6.8 tool calls/probe) and, on the planted-reference
probe, opened the Timeline graph's real doc 115 instead of accepting the false
premise. Its first pass ended **13/29 turns silently** (no final message, sometimes
after only 4–7 calls); the harness now forces a final tool-free answer when a turn
ends without one or hits the step cap, and the scorer reports empty answers as
`no_answer` rather than counting them as leaks. Production agents using
reasoning models need the same guard.

**Repository hygiene:** `.gitignore` now separates system from content
(papers/PDFs, `pipeline/work/` corpora and backups, `*.db`/`*.sqlite*`, extracted
`*.text.json`/`*.nodes.json`, `output/`, logs, transcripts, `tmp/`, secrets). The
341 content files that were in the initial commit are untracked from the index
(still on disk); 228 system files remain tracked.

**Next actions:**
1. ~~Show the matching claim snippet on search cards.~~ Done (`matched_claim_excerpt`). The last recall miss ("nodes"
   in Timeline) was a correct search whose cards showed only titles/abstracts, so
   the model concluded the term was absent without opening the claims.
2. ~~Scale the probe set (adversarial phrasing, a second model).~~ Done: 0/108,
   upper bound ~2.7%. Still open: a third graph (e.g. a Quantule or CSI pilot) once
   Phase C/D give those projects typed collections and artifact manifests.
3. Phase C (source roles/collections) is now the next structural step.
4. Open from earlier: merged-graph concept labels (`g_<hex> / name`), and porting
   `graph_server.py` to the MCP 2.x API (the pin and start-up guard cover it today).

### Phase C — Source roles / collections
Codex's earlier recommendation, still the right next structural step: typed
collections under each graph (internal design, external publication,
observation/measurement, hypothesis), declared in the reviewed profile and shown
in discovery, search filters and evidence. Plus the reviewed **universal alias
template** (e.g. `llm`, `sgd`) that each graph materialises deliberately.

### Phase D — Artifact manifest layer
Format, content hash, producer, capture/run time, parameters and parent artifacts,
with bounded readers. Agents get a run/dataset card and specific slices, not raw
arrays. First formats: PDF (Timeline has 28 unparsed), CSV/JSON, then NumPy/HDF5.

### Phase E — Real project pilots, one at a time
1. **Timeline-mapping**: full Markdown + PDFs (after D). Dates and correlations
   stay documentary assertions until typed event objects exist.
2. **Quantule**: one solver module + one run manifest + its reference notes.
3. **network_management**: one CSI processing module + one capture manifest.
4. **Librarian_V2**: application code profiled separately from its 6k+ vault notes.

### Phase F — UX
- Graph import / collision-review wizard in the UI (CLI-only today).
- Bridge authoring UI with required rationale and evidence.
- Three.js bundle split (existing size advisory).
