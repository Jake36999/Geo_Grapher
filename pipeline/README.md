# Paper corpus operations

This source-checkout extension is separate from Geo Grapher's immutable code
snapshots. Its claims are documentary assertions, not verified facts or code
dependencies. The `pipeline/` scripts are not bundled in the application wheel.
Use the pinned project Python (MCP 1.30.0); the paper server also has transport
smoke coverage against the installed MCP 2.2.0 environment. PDF extraction
requires the optional `papers` dependency (PyMuPDF); querying does not.

## Read tools

Start stdio with `python -m pipeline.mcp_doc_graph` from the checkout, or execute
the script by absolute path. `GEOGRAPHER_DOC_GRAPH_DB` selects the database;
the default is the absolute `pipeline/work/doc_graph.db`, independent of CWD.
Reconnect an already-running MCP client after updating the server. Existing
Claude Desktop configuration is not changed by these fixes.

For independent project graphs, attach a distinct corpus file with
`geographer attach-graph-papers --catalog CATALOG --graph-id GRAPH_ID --database DB`.
The graph hub exposes `paper_*` tools with `{graph_id, request}`. Database
selection is context-local, so concurrent graph queries cannot change a global
database path. A physical database cannot be attached to two project graphs.
The reusable alias file is a policy template, not shared concept storage:
`maintain refresh --alias-policy PROJECT_POLICY.json --backup NEW_BACKUP` applies
a reviewed graph-local policy. These changes do not migrate the existing global
research corpus or assign it to a project automatically.

Ten default tools are read-only. Each response includes `context.api_version`
(`paper-tools-v4`), `server_build` and `corpus_revision`. Pass that revision as
`expected_revision` on subsequent pages. `STALE_CORPUS` means restart pagination.
Identifiers are typed: documents `doc:N`, concepts `concept:N`, claims `claim:N`
(v4 typed concept IDs, which v3 returned as bare integers). Search uses Porter
stemming (`paper-read-v4`), so "networks" matches "network"; corpora built
before v4 report `READ_MODEL_OUTDATED` until `maintain refresh --backup PATH`.
Use `get_corpus_status` after connecting to identify stale code/read models and
distinguish original source counts from readable canonical works.

| Tool | Contract |
|---|---|
| `search_documents(query, limit=10, offset=0, match_mode='any')` | BM25 with Porter stemming; `any`, `all`, `phrase`; exact titles first; reviewed aliases indexed; max 25 cards; `matched_claim_excerpt` («match») when a query word hits a card's claims |
| `get_document(title, detail='card', claim_limit=8, claim_offset=0)` | `card`, `claims`, or bounded `full`; max 50 claims/page |
| `get_outline(title, limit=50, offset=0, include_placeholders=false)` | Source section IDs, max 100/page; omitted placeholder count disclosed |
| `get_section(title, heading='', section_id=null, text_offset=0, max_chars=8000, claim_offset=0, claim_limit=10)` | Text max 32,000 characters/page; max 50 claims/page |
| `get_concept(name, limit=10, offset=0, concept_offset=0)` | Exact/reviewed alias first; five concept matches/page, max 25 documents/match; typed nonidentity links |
| `find_by_concept(concept, edge_type='both', limit=10, offset=0, concept_offset=0)` | Separate concept/document pagination; `defines`, `mentions`, `both`; max 25 documents/page |
| `get_related(title, limit=8, offset=0)` | Distinct shared-concept IDF ranking, max 20/page; total disclosed |
| `get_claim(title, claim_id, text_offset=0, max_chars=2000, evidence_offset=0, evidence_limit=5, source_claim_id=null)` | Complete normalized claim or original extraction; max 8,000 characters and 25 source occurrences/page |
| `get_annotations(title, annotation_id=null, source_index=null, offset=0, limit=3, text_offset=0, max_chars=2000, as_of_id=null)` | Full notes or archived source rows; max 10 notes/page, 8,000 characters each |
| `get_corpus_status()` | Server/build, active/original counts, quarantine, known provenance coverage; no writes |

Use `doc:49` identities returned in cards to avoid ambiguous title matching.
Use `section_id` for repeated headings. `get_claim` follows all original
occurrences of a deduplicated claim, making it discoverable from either source
section. Normalized/original extraction text is distinguished; neither is claimed
to be verbatim PDF text. Page locations have section-level precision only.
Explicit pagination/truncation fields
describe omitted text and claims. `full` supplies a bounded outline/claim page,
not an unbounded paper dump. Claim ordering is by declared type (limitations,
findings, contributions, methods), not a claim of scientific trust. Source text
is retrieved through sections. Both MCP SDKs return one structured payload,
without a duplicate JSON text block.

## Preserved sources and derived read models

`documents`, `sections`, `claims`, `concepts` and incidence rows retain originals.
`corpus.py` builds additive `read_*` tables/views plus FTS5 in the writer's
transaction. No query rebuilds the index. Publication checks raw row counts and
foreign keys. The initial backup before remediation is
`output/paper-audit/doc-graph-before-remediation-20261107.sqlite`.

Records without source sections, or with only unread placeholders, are
quarantined from active results. Placeholder/header claims are excluded from
the read model. Exact duplicate claims retain all original claim IDs. Works
merge only with corroborated identifiers or normalized title plus author
overlap; conflicting identifiers prevent title-based merges. Conflicting years
remain unknown with both source values exposed. This is deterministic record
linkage, not bibliographic verification or fuzzy title matching.

Only the reviewed equivalences in `concept_aliases.json` merge concepts. The
policy is validated before derived tables change: conflicting alias ownership
and contradictions between equivalence/nonidentity links are rejected. All
source IDs matching reviewed spelling variants join the same canonical group.
Typed `variant_of`, `specialization_of` and `related_to` links retain distinct
identities and do not count as shared concepts.
`truncated svd` remains a variant of `svd`, not an alias. Disclosure headings
are excluded from relatedness ranking; PyTorch remains a valid searchable term.
Shared terms do not establish agreement, entailment, or semantic equivalence.

```powershell
python -m pipeline.maintain --db pipeline/work/doc_graph.db stats
python -m pipeline.maintain --db pipeline/work/doc_graph.db refresh --backup output/UNIQUE_BACKUP.sqlite --report output/cleanup.json
python -m pipeline.maintain --db pipeline/work/doc_graph.db pack 'retrieval augmented generation' --limit 3
```

`refresh` requires a new backup destination. `pack` is an explicit cache write;
repeating it returns the cached card collection. Corpus revisions include raw
content, incidences, provenance, alias policy and the read-model algorithm
version. Changed revisions invalidate cached topic packs; pack keys include the
query API/build identity too. Unchanged fingerprints skip derived/FTS writes.
Changed batches still rebuild the read model once; this is not a sublinear
incremental algorithm. Canonical concept incidences are now materialized and
indexed rather than rejoining raw section evidence during every graph query.

## Ingestion and provenance

Stage 1 hashes PDFs and resumes only matching extractor/source versions, records
actual one-based page numbers, and preserves long and short sections. PDF
heading/reading-order extraction remains heuristic. Stage 2 matches claims by
section position, validates provider responses locally, records model identity,
extraction time and shown-prefix coverage, and marks failures incomplete. Stage
2b parses safe YAML, preserves author names containing commas, ignores fenced
headings, retains section text and hashes note sources. Stage 3 atomically
replaces changed sources, removes obsolete edges, validates foreign keys, skips
identical artifact hashes, and refreshes read models before publication.

Legacy artifacts retain explicit unknown/legacy coverage. Old model IDs,
extraction dates, source hashes and PDF page coordinates are not invented.
Missing years are not inferred from filenames. Current cleanup does not
re-extract the original PDFs or run models.

The orchestrator resolves sibling scripts absolutely; `--work-dir` also selects
the default database. Its `--dry-run` does not extract or write files and needs
existing text artifacts for cost estimates. Actual stage 2 uses paid DeepInfra
calls: do not run it for maintenance or validation. Its configured price-based
stop is an estimate, not a provider-enforced billing guarantee. Provider-side
spending controls remain necessary for any separately authorized model run.

## Explicit annotation and vector workflows

`python -m pipeline.maintain annotate annotation.json` accepts `kind` (`note`,
`synthesis`, `contradiction`), `text` (max 8,000 characters), `source_refs`
(`[{"kind":"claim","id":123}]`, max 20), `expected_revision`, and `author`.
It archives the referenced source rows, is idempotent, and creates an immutable
**unreviewed** annotation. Cards expose up to three annotation previews with
revision-staleness flags and handles. `get_annotations` retrieves full text and
archived source records after re-import. Pass the first page's `as_of_id` with
later collection offsets to prevent concurrent appends shifting pages. Text
continuations require an `annotation_id`; `source_index` selects an archived
source row. Archive record hashes are not hashes of the original PDF.
Enabling `GEOGRAPHER_DOC_ALLOW_ANNOTATIONS=1` explicitly
adds the `annotate_document` write tool; default server capabilities stay
read-only (ten tools). Annotations never replace extracted evidence.

`import-vectors FILE.json` accepts pinned `model`, `model_revision`, and
`records: [{concept_id, input_text, vector}]`. Input must match the current
canonical name; dimensions and finite norms are validated. `candidates --model
NAME --model-revision REV` emits bounded cosine proposals, excluding stale input
hashes and never mixing encoder revisions. The offline pair scan is limited to
2,000 concepts. No encoder is downloaded or invoked. Review proposals against
definitions and source context before manually editing the alias policy; there
is no automatic embedding/LLM merge or scientific-claim promotion.

## Verification

Run `python -m pytest tests/test_paper_pipeline.py tests/test_paper_followup.py`
with the pinned environment.
`scripts/qa-paper-mcp.py` exercises every tool through actual stdio, including
structured errors. It accepts repeated `--python` executables for SDK
compatibility checks. Tests and maintenance invoke no paid APIs.
