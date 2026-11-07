# Paper corpus follow-up — 7 November 2026

## Delivered

The supplied attachment repeats the earlier research/corpus review rather than
providing new model-trial outcomes. This pass checked the current implementation
and addressed additional retrieval, provenance, pagination and update gaps.
It preserves the expanded alias policy and broad-OR search behavior already in
the workspace. No paid model/provider call or paper re-extraction was performed.

### Running-server and corpus identity

`paper-tools-v3` adds `get_corpus_status` and a small response-level `context`:
API version, running source build ID and corpus revision. The status tool checks
whether on-disk query sources differ from the loaded build, whether read models
need migration, and reports original versus active counts with quarantine and
known provenance coverage. This makes it possible to distinguish stale process
results from current ingestion defects. A client still has to reconnect a
previously loaded MCP process; desktop configuration was not changed.

All paginated read operations accept `expected_revision`. A mismatch returns a
structured `STALE_CORPUS` error instead of mixing pages from different corpus
versions. Outdated read models return `READ_MODEL_OUTDATED`, while the status
tool remains available for diagnosis. Response identity appears once per
response, not on every claim or graph member.

### Complete evidence without unbounded dumps

- New `get_claim` retrieves full normalized claim text or an original extraction
  occurrence in bounded pages. Evidence occurrences are independently paginated
  and retain source document/section IDs, extraction provenance and available
  section-level page locations. Extracted claims are not labelled verbatim PDF
  quotations, and section locations are not promoted to exact claim positions.
- Fixed deduplicated claims disappearing from their second source section.
  Section queries now follow all original occurrence IDs. Counts in outlines
  describe the source section rather than only whichever duplicate was retained.
- New `get_annotations` retrieves full immutable notes, archived source rows and
  record hashes after source re-import. Cards include retrieval handles instead
  of leaving truncated notes inaccessible. Archived interpretations stay
  unreviewed and expose whether they predate the current corpus.
- Annotation collection pagination pins `as_of_id`; concurrent appends do not
  shift a caller's next page. Text continuation requires a fixed annotation ID.
- Placeholder-only sections are omitted from outlines by default with an
  explicit omitted count. They remain retrievable through the opt-in outline
  flag and carry a quality label. Original records are never deleted.

### Retrieval and concept integrity

- Search exposes `any` (existing OR behavior), `all` and `phrase`, retains BM25
  ordering and prioritizes exact titles. Reviewed aliases are indexed too, so an
  abbreviation can find works using its reviewed long form. The no-FTS fallback
  now searches claim text and reviewed concept aliases as well as metadata.
- `get_concept` and `find_by_concept` no longer silently stop after five concept
  matches. `concept_offset`, match counts and pagination make additional matches
  discoverable; document pages remain independent. Partial matches rank by
  document frequency, then name length/name/ID. Exact aliases still take priority.
- `get_related` is pageable and reports total results and witness-preview
  completeness, while retaining distinct-concept IDF scoring.
- Policy validation rejects conflicting alias ownership and equivalence that
  contradicts a declared nonidentity link. A normalized-name lookup previously
  retained only one raw ID per spelling: all matching raw IDs now merge within
  an explicitly reviewed group. A regression covers hyphen/space RAG variants.
- The registry's `variant_of` and `specialization_of` links are materialized and
  exposed without merging identity or inflating shared-concept counts. The
  existing exclusions and aliases were preserved, not replaced with automated
  guesses. Structural validation does not independently establish the scientific
  validity of a curated equivalence.

Ten default paper tools are read-only: the original seven plus status, claim
and annotation reads. The existing annotation write remains explicitly opt-in.
The canonical code-analysis wire contracts and spatial workspace were unchanged.

### Update/query efficiency

Unchanged source/provenance/policy fingerprints skip read-table and FTS writes.
Changed batches still rebuild derived data once inside the writer transaction;
this is not a sublinear incremental index. Cached pack keys now include query
API/build identity so changed query semantics cannot silently reuse old payloads.

Canonical document/concept incidences are materialized with primary/reverse
indexes instead of repeatedly joining raw evidence views. Relatedness computes
concept frequencies once per SQL query.

On the existing 130-work corpus, five samples of the same relatedness SQL query
returned identical pairs: median **5.40 ms through the old view versus 0.48 ms
through the indexed table**, approximately 11.3× for this query. An unchanged
refresh took 31.8 ms and performed zero derived writes; the measured changed
refresh took 143.5 ms. These are small local measurements, not release hardware
acceptance or evidence of end-to-end model/task improvements. Receipt:
`output/paper-followup/staging-verification.json`.

## Publication and validation

The migration was tested on a separate database, then applied with a consistent
backup at `output/paper-followup/corpus-before-v3.sqlite`. All original table row
hashes match that backup, and foreign-key validation passes. The alias policy
already present at the start of this pass produced **1,091** canonical concepts,
46 shared concepts and 24 isolated works; those counts were unchanged by this
migration. There remain 200 original source records, 130 readable works, 64
quarantined sources, and 1,906 retained claims. This pass did not manufacture
new connections or imply that all incomplete records have been repaired.

**98 focused tests passed**, including 22 new follow-up cases, existing ingestion
and store checks, incremental HTTP behavior and repair guards. The one existing
Starlette/httpx deprecation warning remains. Tests cover full text reconstruction,
all duplicate source occurrences, annotation archives after re-import, revision
changes, concurrent annotation appends, query isolation, typed concept links,
invalid policies, search modes and no-op refresh writes.

Real stdio checks exercised all ten tools on MCP **1.30.0 and 2.2.0**, including
structured errors and stale revision rejection. Both return one structured
payload without duplicated JSON text. The live Edge/Playwright viewer check on
port 8765 still passes with initial and expanded frames and no page errors.

Exact offline `o200k_base` card comparisons and final server identity are in
`output/paper-followup/final-verification.json`. Fixed response identity added
approximately 70 tokens to the sampled cards. This is an explicit tradeoff for
version/pagination safety, not a claim of reduced size relative to the already
compact prior cards. Paper responses have documented row/character bounds;
this does not replace the canonical service's exact full-envelope token budget.

Machine-readable receipts: `pytest.xml`, `mcp-live.json`, `applied-v3.json`,
`final-staging-verification.json` and `final-verification.json` under
`output/paper-followup/`; browser evidence is under `output/viewer-qa/`.

No full release acceptance, large model trial, automatic LLM synonym
confirmation, or re-extraction of legacy incomplete papers is claimed. Missing
metadata remains unknown. Reconnect the paper MCP server, run
`get_corpus_status`, and verify `paper-tools-v3` / `paper-read-v3` before comparing
new query results. Current usage is documented in `pipeline/README.md`.
