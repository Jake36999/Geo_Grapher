# Corpus, ingestion and viewer review — 7 November 2026

## Outcome

The Geo Grapher skill was installed and validated before reviewing the attached
transcript. The broken viewer is repaired on port 8765. The separate research
corpus now serves bounded, ranked, provenance-labelled results from additive
read models. Original corpus rows and the canonical code snapshot are preserved.
No paid model trials or paper re-extractions were run.

## Viewer defect

The listener was an older running backend serving newer frontend assets.
`POST /api/v1.1/viewport/frame` returned HTTP 405 with a plain-text body; the
frontend tried to decode it as JSON. Bootstrap/HTML success did not establish
API compatibility. After identifying the exact process and backing up its
database, the listener was restarted using current source and the pinned
project environment. The temporary staging listener was subsequently stopped;
the repaired live listener remains running.

`frontend/src/api.ts` now includes method, path, status and a bounded text snippet
when responses are not JSON. A 405 adds an actionable backend/version hint.
It does not substitute an empty graph. Live Edge/Playwright checks confirm two
successful frame POSTs, two initial nodes and five Nearby nodes, a rendered
canvas and no page errors. A separate browser-intercepted plain-text 405 test
confirms the new message instead of a JSON syntax error. Evidence:
`output/viewer-qa/live-final.json`, `live-final.png`, `http405.json`.

## Review of the submitted corpus claims

Measurements below use read-only SQL over the preserved original tables. The
applied publication receipt is `output/paper-audit/applied-cleanup.json`.

| Supplied claim | Verified result / correction |
|---|---|
| 52/1,098 concepts shared across documents | Confirmed, using distinct document IDs: 4.74% |
| 70/200 documents isolated | Confirmed on the raw graph. **51** have no sections (50 NULL titles, one empty title); only 19 raw isolates have sections. Fragmented terminology alone does not explain 70 isolates. |
| Six duplicate paper groups | Confirmed after Unicode case folding/title normalization and author corroboration. Five title pairs are literal matches; the sixth contains a typographic ligature. A SQL NULL-title group is not a duplicate paper. |
| 43 unread abstract placeholders | Confirmed. They must not be presented as abstracts. |
| 129 junk claims | Under-counts the problem: 148 full unread placeholders plus 12 standalone template headers, **160** excluded claims. 129 corresponds to three repeated placeholder categories. |
| 74 papers lack a year | Confirmed for raw NULL years. Dates were not guessed from filenames. One merged work has conflicting 2015/2026 source values, exposed as a conflict rather than silently choosing. |
| Every related result had one shared concept | Describes those sampled queries, not an established corpus-wide invariant. Current relatedness uses distinct concepts, avoiding defines/mentions double counting; the mobile-agent paper has results with two shared concepts. |
| Search cannot find retrieval augmented generation | Legacy literal phrase search was inadequate; FTS5 BM25 now finds three active works for those literal words. This is lexical retrieval, not semantic equivalence. |

The raw graph has duplicate-paper links and concepts attached to placeholder
sections. Removing these can reduce apparent connectivity. No connectivity score
is used as a target that would justify invented synonyms.

## Primary-source checks on the research recommendations

| Recommendation | Evidence and engineering interpretation |
|---|---|
| ASCOC synonym merging | Local PDF p.6/Table 2 confirms vocabulary retention 83.6% and triple retention 97.39%. Its synonym-merging F1 is **0.4314**. FAISS/MNN synonym clustering is distinct from TransE-plus-LLM link completion; p.8/Table 4's **0.94 precision** belongs to completion, not merge precision. Candidate generation plus explicit review is justified; reliable automatic equivalence is not established. [Publisher](https://www.sciencedirect.com/science/article/pii/S0957417425042502). |
| ChatP&ID context reduction | Local PDF p.19/§6.1 directly reports 150K tokens for Proteus XML, 66K complete graph, 32K process graph and 7K conceptual graph. Table 5 reports ContextRAG average accuracy 0.91 and lowest average cost/time in that tested comparison. It does not establish superiority for every graph task/model. [Paper](https://aiche.onlinelibrary.wiley.com/doi/10.1002/aic.70540). |
| Moderate knowledge exposure, K=3 | Confirmed in the local mobile-agent PDF p.8 and Fig.5 discussion: a UAV/Qwen 3B case study, not a universal retrieval default. Bounded configurable cards are an engineering choice; no hard-coded global K=3 optimum is claimed. [Authors' preprint](https://arxiv.org/abs/2603.05831). |
| CQRS/read views | Separating write/read models is a documented architecture pattern, not experimental proof of this system's speed. Fowler also warns about added complexity. Implemented here as same-database, same-transaction derived tables, without a distributed CQRS system. [Original discussion](https://martinfowler.com/bliki/CQRS.html). |
| Agent write-back / Reflexion | Reflexion maintains episodic verbal feedback and evaluates later task performance; it does not establish that stored cross-paper syntheses become true. Annotations here remain unreviewed, immutable documentary assertions with archived source references. [Authors' paper](https://arxiv.org/abs/2303.11366). |
| Provenance / KG.GOV | Supports modelling dataset/process provenance. It does not prescribe the exact extraction columns quoted in the review; those are our engineering choices. Known model/date/hash/page metadata is retained, legacy unknowns remain explicit. [Publisher](https://www.sciencedirect.com/science/article/pii/S1570826824000337). |
| Paper text as untrusted data | Appropriate boundary, supported by the instruction-hierarchy research; labels are not a complete prompt-injection defence. Tools and extraction prompts mark third-party text as data. [Authors' paper](https://arxiv.org/abs/2404.13208). |
| Embedding drift | The cited CVPR paper studies changing embedding networks in class-incremental learning. It does **not** show fixed text vectors change just because a library grows. Version encoder/model revision and input hash; corpus growth invalidates corpus-dependent packs/statistics, not every unchanged vector. [CVPR paper](https://openaccess.thecvf.com/content_CVPR_2020/papers/Yu_Semantic_Drift_Compensation_for_Class-Incremental_Learning_CVPR_2020_paper.pdf). |

PDF tables/pages were also visually inspected; rendered evidence is under
`output/paper-audit/`. The review's blanket suggestion to discard PyTorch was
rejected: it is a legitimate framework concept. `truncated svd` is related to,
not identical with, `svd`. Neither was merged. Broad claims about the survey's
experimental coverage were not used as acceptance evidence.

## Implemented remediation

### Ingestion

- Directory code ingestion now honors configured source roots and rejects a
  nonexistent root, matching Git-ingestion scope behavior. Existing stage-1
  extraction/store fixtures and incremental HTTP checks remain passing.
- PDF extraction records actual page indices rather than PDF block numbers,
  retains full/short section bodies, hashes sources and resumes by extractor
  version. Existing legacy coordinates are not retroactively trusted.
- Model extraction validates responses locally, aligns duplicate headings by
  section position, preserves prefix/truncation coverage and records producer
  and extraction time. Errors/incomplete sections stop further calls and cannot
  publish. Known token usage from invalid responses is retained.
- Markdown uses safe YAML and typed author parsing, ignores fenced headings,
  preserves repeated section content and source hashes, and retains section
  text. Notes remain assertions about papers, not independent PDF verification.
- Changed-source SQLite import uses savepoints, replaces obsolete concept edges,
  preserves unchanged artifact IDs, validates FKs and refreshes read models in
  the writer transaction. Invalid title/section/position/hash inputs are rejected.
  Script paths/default database locations no longer depend on caller CWD.
- Dry runs do not extract/write artifacts or access API keys. No extraction
  provider was invoked during this work. The old price-estimate spending stop
  is explicitly documented as **not** a provider-enforced dollar guarantee.

### Corpus and actor interface

- `pipeline/corpus.py` creates versioned, additive read models. Reviewed document
  linkage preserves each source; metadata conflicts and field origins remain
  visible. Backup, raw row-count checks, FK checks and transactions protect the
  applied cleanup.
- `concept_aliases.json` merges reviewed knowledge-graph and generative-AI
  spelling/abbreviation variants only. Disclosure headings are excluded from
  relatedness ranking. No embeddings or model votes automatically merge nodes.
- Seven default paper tools now use FTS5 BM25, bounded cards, ranked/paginated
  claims, source section IDs, explicit omissions and whole-token concept matches.
  Structured MCP output is serialized once. Exact ambiguity is reported rather
  than selecting an arbitrary matching paper or repeated heading.
- Revision-keyed topic packs are an explicit maintenance operation; stale packs
  invalidate on content, incidence, provenance, policy or read-model version
  changes. Query requests never synchronize/write the corpus.
- Explicit annotation API/CLI and an opt-in MCP write capability retain immutable
  unreviewed conclusions, author, revision and archived source rows. Default
  seven-tool server remains read-only. Versioned vector import and bounded
  cosine-candidate export are available offline; no vectors/models were fetched.

## Applied counts and token measurements

| Measurement | Result |
|---|---:|
| Preserved raw documents / claims / concepts | 200 / 2,228 / 1,098 |
| Readable canonical works | 130 |
| Quarantined source records | 64: 51 without sections, 13 placeholder-only |
| Corroborated duplicate work pairs | 6 |
| Read-model claims | 1,906: excludes 160 junk claims and deduplicates 162 repetitions |
| Canonical concepts | 1,094 |
| Shared read-model concepts / isolated works | 49 / 24 |

These read-model metrics have different denominators and cleaned incidences;
they are not an experimental causal claim that four alias merges resolved the
raw graph's isolation. Remaining fragmentation needs source-grounded review.

Exact offline `o200k_base` counts for three illustrative cards:

| Paper source | Legacy unbounded document payload | New merged-work card | First ranked claim page |
|---|---:|---:|---:|
| Mobile Agentic AI (211 → work 49) | 2,881 | 710 | 1,183 |
| ChatP&ID (115) | 1,320 | 591 | 1,041 |
| Agentic AI review (112 → work 59) | 2,450 | 689 | 1,146 |

Cards omit claim bodies by design and include merged-source provenance. These
are payload-size measurements, not equal-content model-accuracy comparisons or
a universal fivefold improvement. Receipt: `output/paper-audit/token-density.json`.

## Submitted model-repair results

The archived bounded-repair scores show one accepted 70B direction/graph repair
out of three 70B repairs, and zero accepted Qwen repairs out of one. The remaining
failures are missing documentary citations or the required source-basis label.
This is consistent with **8/12 one-shot** and **9/12 after permitted repair**,
not a new one-shot score. Existing score files retain cumulative budgets and
provider-usage attestations. Billing is not independently verified. Repair
regression tests pass; no model retry was launched or missing answer auto-filled.

## Validation and remaining limits

Focused tests cover import rollback/replacement, extraction failures and source
coverage, read models, MCP serialization and real stdio, provenance, aliases,
annotations, vector versioning, source roots and dry runs. **76 tests passed** with one existing deprecation warning (19.83 s); receipt:
`output/paper-audit/verification.json`. Real paper stdio smoke tests exercise all
seven tools through MCP 1.30.0 and 2.2.0, including structured errors. Browser
checks and the frontend build pass. One existing Starlette/httpx deprecation
warning remains.

Legacy incomplete papers were not re-extracted, unknown metadata was not
fabricated, and model/embedding suggestions were not promoted automatically.
Read-side refresh is a deterministic full rebuild per write batch, not sublinear
incremental indexing. No large/paid study, target-hardware performance gate,
human/assistive-technology acceptance or full release acceptance is claimed.

Reconnect the paper MCP server in its client to load the updated module; its
configuration was left intact. Refresh the viewer tab if it still displays the
earlier failure. Operational details are in `pipeline/README.md` and the installed
`C:/Users/jakem/.codex/skills/geo-grapher/SKILL.md`.
