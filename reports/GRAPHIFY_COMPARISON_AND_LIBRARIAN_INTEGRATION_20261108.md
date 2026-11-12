# Geo-Grapher vs Graphify, and Geo-Grapher as the Librarian's knowledge-graph tool — 8 November 2026

## Verdict

- **As a knowledge graph for agents, Geo-Grapher is the stronger system.** It is
  correct where Graphify was measured to be wrong (direction, identity,
  namespaces, multi-repo merges), deterministic where Graphify is stochastic
  (communities), token-exact where Graphify is approximate, and isolated per
  project with measured leakage of zero.
- **Graphify is still ahead on breadth and ergonomics.** It reads images, audio
  and video, many languages, and any folder in one command. It exports to
  Obsidian, a wiki, GraphML, Neo4j and HTML, and its "god nodes / surprising
  connections" report is a discovery surface Geo-Grapher does not have.
- **For the Librarian, Geo-Grapher fits as a standard MCP tool, not a replacement
  for its search.** It fills two gaps the Librarian's own 2026-11-03 review lists
  as lost from V1: capability-sized code context and a graph/community lane. It
  needs no new Librarian runtime code to start.
- **Routing the tests through the Librarian found a real failure the direct
  harness could not:** when the agent chooses `graph_id` itself, it can hop to
  another graph and blend the results. That is now fixed at the server boundary
  with a per-connection allow-list (`serve-graphs --graph-id`). Results are in §4.

## 1. Geo-Grapher against Graphify

Graphify evidence comes from the measured audit of Graphify 0.9.26 (39,424 nodes,
seven repos) in `D:/Aletheia_project/DEV_TOOLS/ToolSet/docs/graphify-representation-findings.md`
(findings F1–F9), plus the Graphify skill definition. Geo-Grapher was designed
against that audit (FINAL_DESIGN_SPECIFICATION source S4).

| Dimension | Graphify | Geo-Grapher |
|---|---|---|
| Graph model | One flat, undirected, simple graph; one integer community label per node | Containment tree + directed, typed dependency relations with evidence/witnesses + a documentary layer; paper store Document→Section→Claim→Concept |
| Identity | Label-based: 36.1% of AST nodes share a label (F4); a node is often not a symbol (F3) | Canonical entity IDs namespaced per repository/graph; typed `doc:N` / `concept:N` / `claim:N` handles |
| Direction | Merged graph reversed 96.6% of scorable calls (F1) | Directed relationships; per-call resolution status (exact / candidate / unresolved) |
| Multiple projects | Merges into one cross-repo graph; community IDs collide across repos (F2); partitions don't compose (F7) | One independent store per root; overlap review; explicit bridges; reviewed namespace-preserving merge; per-connection allow-list |
| Grouping | Louvain/Leiden communities: file-sized (F5), differ between runs (NMI 0.965–0.990, F6), tests mixed with production (F9) | Deterministic SCC layering, WL refinement, quotient views and LCA; rules-based conceptual grouping |
| Confidence | EXTRACTED / INFERRED / AMBIGUOUS edge labels | Resolution statuses + evidence records; claims marked unverified documentary assertions; results flagged untrusted |
| Query surface | BFS/DFS `query` with approximate token budget; `path`; `explain` | 8 code operations (search, architecture context, dependants/impact, conformance rules, similar code, witnesses, content, viewport) + 10 paper tools; exact o200k token envelopes with endpoint closure; pagination with revision guards |
| Agent access | MCP stdio mode, but the extraction pipeline runs as a Claude Code skill driving host subagents (or Gemini) | MCP stdio + HTTP from any host; runs headless with DeepInfra models; demonstrated through the Librarian |
| Extraction cost | LLM tokens per document on every uncached file | Code graph: zero LLM calls; papers: about $0.14 for 114 PDFs once, then cached |
| Inputs | Code in many languages (tree-sitter), docs, papers, images (vision), audio/video (Whisper) | Python (ast/symtable + conservative CFG resolver), JS/TS candidates, Markdown/text; papers via the separate PDF pipeline. No images, audio or video |
| Outputs | Interactive HTML, Obsidian vault, wiki, GraphML, Neo4j/FalkorDB, SVG | 3D nested-sphere workspace + list + matrix, multi-graph, saved views. No Obsidian/GraphML/Neo4j export |
| Updates | `--update` (cached), `--watch` | Content-addressed snapshots with partial reuse; no watch mode |
| Discovery | GRAPH_REPORT.md: god nodes, surprising cross-document links, hyperedges | Architecture diagnostics (SCCs, boundaries, conformance); no "surprising connections" report |

**What would close the remaining gap.** These are features, not representation
changes:
1. An **Obsidian/Markdown export** of a graph, which matters most for the Librarian.
2. A deterministic **discovery report** (high-centrality and cross-boundary entities).
3. **More languages** via the existing tree-sitter adapter path.
4. A **watch mode** on top of incremental snapshots.

Image, audio and video ingestion is better left to the Librarian's own
OCR/STT services feeding notes.

## 2. What the Librarian is built around

- **Searchable surfaces, not graphs.** The pieces:
  - FTS5 chunks carry section roles (claim / caveat), alongside names and coverage, plus optional vectors (`model2vec` by default, `fastembed`, or hosted APIs).
  - These are fused by reciprocal rank fusion.
  - Constraints eliminate candidates, every result says why it matched, and no generative model runs on the read path.
  - Per-slice evaluation reports hit@k and MRR.
- **Evidence first.** EvidenceStore, quote checks, and DIK records (Data → Information with typed, basis-labelled edges → Knowledge as the note), each with an origin label.
- **Graph today.** Advisory note-link communities (`communities.py`, label propagation). The Librarian's own 2026-11-03 review lists two V1 capabilities lost in V2:
  - the **community lane in retrieval**;
  - **capability-sized code context** (seed → transitive imports → SCC packing → budgeted digest).
- **Model reliability for DeepInfra.**
  - Provider retries on 429/5xx/timeouts, with typed failure categories.
  - Context-window fitting and per-profile token/cost/time budgets.
  - Qualification tiers L0–L3.
  - External MCP results wrapped as untrusted; oversize structured results withheld intact.

**Fit.** Geo-Grapher complements the Librarian rather than competing with it:
- `get_architecture_context` is the budgeted, capability-sized code context the
  Librarian's review asked for.
- Geo-Grapher's deterministic structure (layers, boundaries, conformance) is a
  stronger basis for a graph lane than stochastic communities.
- Embeddings and lexical search stay the Librarian's job.

## 3. Recommended integration

**Stage 1: works today, measured (§4).** Attach Geo-Grapher in Settings → MCP
servers as a stdio server, one connection per library, pinned to that library's
graph(s):

```json
"geo-grapher": {
  "command": "F:/uv-data/Geo_Grapher/output/wheel-env/Scripts/python.exe",
  "args": ["-m", "geographer", "serve-graphs", "--catalog", "F:/uv-data/Geo_Grapher/output/named-graphs/catalog.sqlite",
           "--graph-id", "g_03a111af7e3130d797ab1772", "--tools", "papers", "--max-result-chars", "7500", "--transport", "stdio"],
  "env": {"PYTHONPATH": "F:/uv-data/Geo_Grapher/src;F:/uv-data/Geo_Grapher"},
  "cwd": "F:/uv-data/Geo_Grapher"
}
```

**Stage 2: standard.**
- Publish Geo-Grapher as a pinned installable and add it to the Librarian's curated server list (`CURATED_SKILLS`) next to Semantic Scholar, launched as `uvx --from geo-grapher==X geographer serve-graphs --catalog ${GEOGRAPHER_CATALOG} --graph-id ${GEOGRAPHER_GRAPH} --transport stdio`.
- Suggest it from the `software-systems` profile (code graphs) and from the `history` and `course` profiles (paper/note graphs).
- Profiles only suggest; a person still accepts the exact definition, as with every outside server.

**Stage 3: deeper.**
- A Librarian search lane that runs Geo-Grapher next to FTS/vectors, with an explanatory "why" per result.
- Bridges between DIK records and Geo-Grapher entity IDs.
- L1/L2 qualification probes for models on the Geo-Grapher tools; the harness in §4 is effectively an L2 walk.

**Integration issues found by routing through the Librarian:**

| Issue | Evidence | Status |
|---|---|---|
| Agent hops graphs on an open connection and blends results | Probe 28: AI-graph question answered from Timeline notes, unattributed | **Fixed in Geo-Grapher:** `--graph-id` allow-list; `graph_label` on every envelope |
| Librarian prompt conventions make external docs look like vault notes | Citations like `[[Sources/papers/doc:115]]` and `[doc:109](Offerings/timeline-mapping/...)` point at notes that don't exist | Open: the Librarian's external-tool prompt addendum should say to cite external handles verbatim; Geo-Grapher could add a `cite_as` handle per card |
| MCP version mismatch | Librarian's MCP 2.2 client sends `server/discover`; Geo-Grapher's MCP 1.30 server logs validation errors, then works | Open: port `graph_server.py` to MCP 2.x (existing roadmap item) |
| Librarian withholds structured results over 8,000 chars | A 10-result AI-graph search is about 7,100 chars | 0 withheld so far; keep default page sizes at or under 10 or add a compact card mode |
| Mistyped graph IDs | Model dropped characters from a 24-hex ID once | Hub rejected it. Accepting a graph's label as an alias on an allow-listed connection would remove the risk |
| External tools default to "ask" per call | Librarian seeds every MCP tool "ask" | A person may set read-only Geo-Grapher tools to "allow" per library |

## 4. Tests routed through the Librarian

`scripts/librarian_harness.py` runs under the Librarian's own interpreter
(`D:/Librarian_V2/.venv`) and uses its real machinery:
- `providers.from_settings` for DeepInfra, with retries and failure categories;
- `loop.Loop` for the agent walk, with context fitting, budgets and untrusted wrapping;
- `mcp_client.McpManager`, which accepts Geo-Grapher's stdio server and registers `mcp__<server>__*` tools.

Geo-Grapher stays a tool. The model is given only a graph's label and must find
its `graph_id` with `list_graphs`. Nothing was installed into either environment.
The probe set and scorer are shared with `scripts/eval_graph_leakage.py`.

**Benchmark (5 questions, Qwen3-32B, open connection):** 5/5 answered, 6/7 key
facts found, 4.4 tool calls/question, 0 wrong-graph calls, 0 withheld, 0 tool
errors. This is the best fact recall of any harness this session; Q3 cites the
85% claim *with* the "versus raw image inputs" caveat.

**Leakage probes (29, Qwen3-32B), reviewed by hand:**

| Connection | Cross-graph leaks | Prior-knowledge leaks | Citation errors | Recall misses | Wrong-graph calls |
|---|---|---|---|---|---|
| Open (agent can reach both graphs) | **1** (probe 28) | 0 | 1 | 0 | 3 real + 1 mistyped ID |
| Library-scoped (`--graph-id`) | **0** | 0 | 3 | 0 | 0 (none attempted) |

With library scoping, `list_graphs` shows each connection only its own graph, so
the model never tried to hop. The allow-list did not have to block anything, and
the MKUltra false premise was declined.

**A new citation error seen only through the Librarian:** in 4 answers across
both runs, the model renumbered documents by position (`doc:1`, `doc:2`, `doc:3`)
while giving the right titles (e.g. CoACL is doc 152). It never happened in the
direct harness, so it is likely an interaction with how the Librarian frames tool
results. A string `cite_as` handle per card (`ai-research-papers/doc:152`) should
resist renumbering, and the scorer catches it as a citation error, never as a leak.

Open-connection flags the scorer raised but review cleared: probe 5 ("unsupported
terms" were UI words), probe 22 (a mistyped graph ID the hub rejected) and
probe 24 (attribution by paragraph, now understood by the scorer).

Reproduce:

```powershell
D:/Librarian_V2/.venv/Scripts/python.exe scripts/librarian_harness.py smoke  --scoping library
D:/Librarian_V2/.venv/Scripts/python.exe scripts/librarian_harness.py bench  --model Qwen/Qwen3-32B
D:/Librarian_V2/.venv/Scripts/python.exe scripts/librarian_harness.py probes --model Qwen/Qwen3-32B --scoping library
```

### Geo-Grapher fixes from these findings (8 Nov, later)

| Fix | What it does |
|---|---|
| `cite_as` handles | Every document reference in a routed paper result carries `graph-label/doc:N`; tool descriptions and hub instructions ask for it verbatim |
| Label aliases + recoverable errors | `graph_id` accepts an unambiguous graph label; unknown, mistyped or disallowed IDs return an error listing the graphs this connection may use |
| `--max-result-chars N` | Fits paper results under a client's size cap by dropping whole trailing items and moving `next_offset` back (adds `size_limit`), never by cutting JSON. Librarian connections use 7500 |

Re-measured through the Librarian (library-scoped, Qwen3-32B):

| Run | Leaks | Citation errors | Recall misses | Withheld (oversize) | Facts (bench) |
|---|---|---|---|---|---|
| Probes before the fixes | 0/29 | 3 (positional renumbering) | 0 | 0 | — |
| Probes with `cite_as` | 0/29 | **0** | 0 | 1 | — |
| Benchmark with `cite_as`, no cap | — | — | — | 3 | 7/7 |
| Benchmark with `cite_as` + 7500 cap | — | — | — | **0** | **7/7** |

18 of the 20 probe answers that cite documents used the `cite_as` handles
verbatim. The handles add about 35 characters per card, which pushed 10-result
searches past the Librarian's 8,000-character limit (8,081 measured). The size
cap resolves that. Verification: 365 backend tests (3 new), typecheck, build,
12 browser checks.

### Stage 2: the Librarian-side integration (8 Nov, later)

**Geo-Grapher packaging.**
- The wheel now includes the `pipeline` paper tools and their alias policy, so an installed `geographer serve-graphs` offers `paper_*` tools. It is built to `dist/` (3.7 MB, no corpus data).
- `serve-graphs` reads `GEOGRAPHER_CATALOG`, `GEOGRAPHER_GRAPHS` and `GEOGRAPHER_MAX_RESULT_CHARS` as defaults, because curated `args` cannot reference variables.
- `uvx --from geo-grapher==0.1.0` with `UV_FIND_LINKS=dist` installs and runs it. PyPI has no `geo-grapher`, so there is no name clash.

**Librarian changes** (`D:/Librarian_V2`, uncommitted; the existing uncommitted `mcp_client.py`/`test_mcp_structured_bounds.py` work was left untouched):

| File | Change |
|---|---|
| `ui/src/settings.ts` (+ rebuilt `ui/app.js`, a 16-line diff) | Curated entry `geo-grapher`: `uvx --from geo-grapher==0.1.0 geographer serve-graphs --transport stdio`, env `GEOGRAPHER_CATALOG`/`GEOGRAPHER_GRAPHS` (`${...}` references), `GEOGRAPHER_MAX_RESULT_CHARS=7500`, `UV_FIND_LINKS=${GEOGRAPHER_WHEELS}` |
| `starter/About/Recommended MCP Servers.md` | Matching row (the agent-readable curated list), including how to pin a library's graphs |
| `standard/profiles/software-systems.yaml`, `history.yaml` | Suggest `geo-grapher` (suggestions only; a person still installs and enables it) |
| `loop.py` | External-tools addendum: outside results are not vault notes; cite the server's `cite_as`/`id` handle verbatim in backticks. Plus a Core-side guard, `unlink_external_handles`: in shown/persisted replies, `[[x]]` where `x` is a `cite_as` handle an outside tool returned that turn becomes `` `x` ``; real vault links are untouched |
| tests | Profile suggestions must be installable curated IDs; the Geo-Grapher row parses and is pinned; addendum rule present; guard unit and loop tests |

Librarian suite: **2,140 passed**, 2 skipped. Geo-Grapher gate: 365 passed + 12 browser.

**End to end** (Librarian loop → the `uvx`-installed pinned package, library-scoped via `GEOGRAPHER_GRAPHS`):

| Run | Result |
|---|---|
| Benchmark | 5/5 answered, **7/7 facts**, 0 withheld, 0 wrong-graph calls |
| 29 probes (before the guard) | 0 cross-graph leaks, 0 citation errors, 0 recall misses, 0 wrong-graph calls, 0 withheld. 2 minor prior-knowledge intrusions inside correct "not in this corpus" answers (a wrong acronym expansion; a suggested search phrase). 1 federated turn hit the 12-step limit with no answer |
| Citation style | Fabricated vault paths (`[[Sources/papers/doc:115]]`) went from common to **0**. The prompt rule alone left `[[ai-research-papers/doc:115]]` wrappers in 3–4 of 5 answers, which is why the Core-side guard was added |

**Blocker found in the Librarian (not changed): outside tools are never offered.**
- The app runs with task-sized tool bundles (`use_tool_bundles: True`), and every phase's bundle is a fixed list of Librarian tool names (`agent_runtime.BUNDLES`).
- Connected `mcp__*` tools are registered and announced in the system prompt and phase hints, but are offered in **no** phase. Any call is refused `TOOL_BUNDLE_REFUSED`.
- This affects every outside server, Semantic Scholar included, not just Geo-Grapher.
- The harness ran with bundles off, so it measured the tools' quality, not this gate.
- Fixing it is a policy decision about the Librarian's execution boundary: which outside tools join which phases, and under what cap (Geo-Grapher offers 20 tools; a bundle holds about 11).

**Also noted:** when the Librarian loop hits `max_steps` it returns no reply. A forced final answer, as the direct harness does, would avoid silent turns.

### Outside tools in Librarian bundles: resolved (11 Nov)

Decision: read-only outside tools join the research phases.

**Librarian (`agent_runtime.py`).**
- In `frame`, `focus`, `map`, `need`, `search` and `judge`, `bundle_selection` now adds read-only (`readOnlyHint`) tools from connected servers.
- Only servers enabled in that library connect, so a library's own choice still governs.
- Tools the phase's existing `PHASE_TOOL_HINTS` names come first, then the server's own order.
- Caps: 6 per server and 8 in total, *outside* the 12-tool built-in limit, so a phase's own tools are never displaced. `BundleSelection.external_omitted` counts what the caps left out.
- Write-effect outside tools, other phases and lower tiers get none. The registry and broker still admit every call.

**Geo-Grapher 0.1.1.**
- `GEOGRAPHER_TOOLS` / `--tools` = `papers` or `code`, 6 tools each, within the per-server cap. Tools outside the preset are hidden and refused.
- On a connection pinned to one graph, `graph_id` is optional.
- The curated entry and starter note now pin 0.1.1 and pass `GEOGRAPHER_TOOLS`.

**Measured in the app's own configuration** (bundles on, inside an `explore` session, `uvx`-installed 0.1.1, one graph per library):
- Benchmark: 5/5 answered, **7/7 facts**.
- 6 outside tools offered per turn, **0 `TOOL_BUNDLE_REFUSED`**, 0 withheld, 0 wrong-graph calls.
- Probes (29):
  - **0 cross-graph leaks, 0 citation errors, 0 recall misses**, 0 wrong-graph calls, 0 bundle refusals, 0 withheld, 0 stopped turns.
  - 2 minor prior-knowledge hints, both inside correct "not in this corpus" answers: a suggested search phrase, and dates in an offer to search further.
- Citation style: **0 wiki links, 0 fabricated vault paths**; 17 answers cite `cite_as` handles. The prompt rule plus the Core-side guard together closed what the rule alone could not.
- Harness note: the first bundles-on run under-attributed retrievals when the model passed a graph *label* or omitted `graph_id`, both valid now. The harness was fixed to resolve both, and the figures above come from the re-run.

Verification: Librarian **2,147 passed** (2 skipped); Geo-Grapher 367 passed + typecheck, build, 12 browser checks.

## 5. Next steps

1. ~~Stage 2: package Geo-Grapher, curated entry, profile suggestions~~ Done (uncommitted in both repos).
2. ~~External-citation rule~~ Done, plus the Core-side guard.
2a. ~~Decide how outside tools enter the Librarian's tool bundles~~ Done: read-only tools, research phases, capped.
2b. Optional: a forced final answer when the Librarian loop hits `max_steps`.
3. In Geo-Grapher: ~~`cite_as` handles~~, ~~label aliases~~ and ~~a size cap~~ are done. Remaining: MCP 2.x port (removes the `server/discover` noise), an Obsidian/Markdown graph export, and a deterministic discovery report.
4. Stage 1 launch line for a Librarian library should now be:
   `serve-graphs --catalog CATALOG --graph-id GRAPH_ID --max-result-chars 7500 --transport stdio`.

Verification of the Geo-Grapher changes in this pass (allow-list, `graph_label`,
CLI flag): `scripts/verify.ps1` passed: 362 backend tests (1 new), typecheck,
build, 12 browser checks.
