# Cross-project isolation and navigation assessment

7 November 2026. Assessment plus bounded implementation/pilot; no model calls,
simulations, experiment jobs, or target repository code were executed.

## Finding

Geo Grapher can now provide useful, scoped access to selected code and Markdown
from unrelated projects, with independent root clusters. It is **not yet ready
to faithfully ingest every kind of content in all four projects as domain
knowledge**. Its strongest current capability is source architecture and grounded
document navigation. Its main remaining gaps are typed source collections,
native research/data artifacts, and domain-specific claims/events/experiments.

Before this change, entity IDs/containment were repository-scoped, but Python
module resolution and documentary symbol mentions shared an index across a
combined workspace. Unrelated `utils`, `models`, or similar names could therefore
produce cross-project bindings/mentions. UI search and similarity also sent an
empty repository scope, and the multi-project Home action selected the first
repository. These were real risks, not evidence that merely similar prose had
been semantically proven equivalent.

## Changes delivered

- New multi-project extraction isolates import/mention indexes by default.
  Existing cross-repository analysis remains available through explicitly shared
  `resolution_group` declarations. Repository identities and root ownership
  remain separate even within such groups. Extractor version is now
  `python-ast-symtable-v3-isolated`; selection/isolation policy enters snapshot
  configuration and identity. Existing immutable snapshots are not rewritten.
- Search/similarity in multi-project snapshots requires explicit `repo_ids`.
  Unknown IDs are rejected. Listing all project IDs is an intentional comparison;
  identical filenames, identifiers or AST hashes never implicitly expand scope.
- Focused architecture/DOI context no longer pulls in unrelated project content.
  The UI defaults search to the current project, provides a labelled project
  selector and an explicit all-project option, and labels each result's project.
  Inspector similarity is scoped to the selected entity's repository.
- Repository roots remain sibling, disjoint spheres. All project roots are
  retained by viewport budgeting, while automatic detail stays in the focused
  project. Multi-project Home shows the workspace instead of entering the first
  repository. The synthetic workspace is not rendered as an imported-project
  bubble; its focus outline may still orient the collection. Canonical parentage
  and LCA math are unchanged.
- Added `geographer://projects` MCP discovery: published snapshots, project IDs,
  revisions, root IDs, selected-file counts and profile markers, without source
  bodies. Agents can select a project before searching rather than guessing a
  snapshot/root or requesting the whole graph. Old snapshots advertise legacy
  shared namespaces and need deliberate re-ingestion for the new guarantees.
- Added bounded `inspect-project` and strict `ingest-workspace` profiles. The
  latter names separate nonoverlapping filesystem roots, source roots, include/
  exclude patterns and file/byte budgets. Directory walking prunes excluded and
  irrelevant subtrees instead of recursively enumerating environments first.
  Over-budget selections fail, not silently truncate. No project code is imported.

Wire/table shapes are unchanged. The existing multi-project `repo_ids` policy is
tightened; details are in `contracts/v1.1/PROJECT_ISOLATION_ADDENDUM.md`.

## What was actually assessed

| Project | Inspection in this pass | Current suitability and principal gap |
|---|---|---|
| `D:/Librarian_V2` | Bounded metadata inventory; selected seven files for ingestion | Good Python/TS/source architecture target. Its root also contains large quantities of notes, reports and generated artifacts, so application code must be profiled separately from library/reference content. |
| `D:/Timeline-mapping` | Bounded inventory and eight selected Markdown notes | Useful Markdown/source-span navigation, including preservation of hypotheses and cautions as documentary text. Not a chronology/claim-verification engine: dates, dating methods, correlations, contradictions and evidence strength are not yet typed domain objects. |
| `F:/quantule_mapper` | Top-level folders and README only; **not recursively ingested** | Python/UI components suit a later narrow pilot. Solver code, external research, run configuration, numerical arrays, ledgers, plots and derived metrics need distinct collections and explicit provenance. A matching physics term is not evidence of agreement or a shared experiment. |
| `F:/network_management` | Top-level folders and README only; **not recursively ingested** | Selected Python/TS/docs could be mapped now. CSI captures, calibration/experiment exports, external references, native driver/tooling languages and generated operational artifacts exceed the current canonical extractor's coverage. |

Librarian inspection stopped honestly at **10,000 entries** after observing 6,368
Markdown and 39 Python files among other formats. Those are **partial observed
counts**, not a full inventory or application-code estimate. Environments,
build/vault machinery and links were pruned and counted separately. This strongly
supports selecting inputs rather than ingesting the entire root indiscriminately.

Timeline inspection completed within its declared exclusions: **247 Markdown
files and 28 PDFs** were observed, plus other formats. The canonical source
extractor supports Python, Markdown/plain text and JS/TS-family syntax; those 28
PDFs were **not** parsed. Excluded machinery is outside the inventory denominator.
Receipts: `output/project-isolation/*-inventory.json`.

## Bounded two-project pilot

Profile: `output/project-isolation/pilot.manifest.json`. It selects seven
Librarian files (six Python files and README) and eight Timeline Markdown notes.
Neither full project was ingested; the selected bytes are independently digested
working-tree inputs, not a pinned full Git revision. No global paper corpus or
existing application database was mixed with these sources.

The published pilot has **524 entities, 284 code relationships, 284 evidence
records and 200 documentary incidences**, with no parse failures. Validation
found **zero cross-project code relationships and zero cross-project documentary
incidences**. The high unresolved-call count is expected from this deliberately
partial source selection and unindexed third-party dependencies; this is not a
resolver recall benchmark on either full repository.

Real MCP stdio discovery → project-scoped documentary search → original content
retrieval passed for both projects. All returned nodes stayed in the selected
namespace. Browser checks confirmed two sibling project clusters, a scoped
default search, a Timeline-only search, and deliberate all-project comparison.
The 1006×884 screenshot was visually inspected. Geometry regressions also check
disjoint root spheres when focus is nested inside one repository.

The pilot is running separately at **http://127.0.0.1:8773/**. The existing
8765 backend was left running while the other model tests continue; it must be
restarted after those tests to load the new server/extractor code. New compiled
frontend assets are available. No DeepInfra/Librarian process was stopped.

## Limits that matter for these projects

1. **Project boundaries do not classify evidence.** The extractor preserves text
   and locations but does not yet give every document an enforced collection such
   as internal design, external publication, experiment observation or hypothesis.
   In particular, the current `is_external` flag concerns unindexed code symbols;
   it is not a classification of externally authored papers.
2. **Generic document trees are not domain knowledge graphs.** Markdown headings,
   blocks and code mentions are indexed. Obsidian links, events, timelines,
   confidence labels and source tiers are not automatically validated/turned into
   typed historical facts. Timeline notes' own `T1`/confidence assertions remain
   their authors' documentary statements. A correlation remains a hypothesis;
   shared vocabulary must not establish causation or factual agreement.
3. **Native artifacts need their own pipeline.** PDFs, CSV/JSON experiment data,
   NumPy/HDF5 arrays, images, notebooks and native-driver sources are not all
   parsed by this canonical source extractor. No empty source parse-failure list
   should be interpreted as full coverage of a root containing those artifacts.
4. **The paper store is separate.** Its concept/work aliases are corpus-wide,
   not per-project tenant scopes. Until it gains project/collection scope, use a
   separate paper database/server per project. Do not feed all four projects into
   one corpus and expect the code-workspace isolation rules to apply there.
5. **Scoping is not access control or an LLM reasoning guarantee.** Explicit
   comparisons, pins and canonical IDs can access other published projects. The
   tool identifies origins; an agent can still make a mistaken inference across
   them. Security isolation would require separately authorized stores/services.

## Recommended next increment

Keep the bounded profiles. Before expanding ingestion to all four roots, add
typed **collections/source roles** beneath each project and make them visible in
discovery, search filters and evidence. Keep external reference claims separate
from measured observations and project hypotheses, with explicit support/refute/
derived-from links and original-source handles. Source-role defaults should be
declared in a reviewed profile, not inferred as truth from a filename or embedding.

Then add an **artifact manifest layer**: format, content hash, producer, capture/
run time, parameters and parent artifacts, with bounded readers for selected
formats. Agents should obtain a run/dataset card and specific slices, not all
nearby numerical or documentary content. Shared reference material can be linked
deliberately without merging project-specific interpretations.

A sensible next pilot is one Quantule solver module + one small run manifest +
its selected reference notes, or one CSI processing module + one capture manifest.
Domain views (solver/run/metric, capture/calibration/experiment, event/date/source/
hypothesis) follow those provenance foundations. None of these further pipelines
is claimed complete in this pass.

## Verification

The primary regression run passed **88 tests**, covering project isolation,
explicit cross-repository resolution/ambiguity, AST/CFG extraction, partitions,
query contracts, HTTP/MCP transports and sphere geometry. A separate **84-test** run passed the store, actor, incremental HTTP and paper
regressions: **172 tests total**. Receipts are `tests.xml`,
`additional-tests.xml` and `verification.json` in `output/project-isolation/`. Frontend typecheck/build passes. Browser and real MCP smoke checks
pass. Existing Starlette/httpx and large frontend chunk warnings remain; no large
benchmark, paid model trial, full-project ingestion or release acceptance is claimed.

Evidence: `tests.xml`, `additional-tests.xml`, `pilot-ingestion.json`, `mcp.json`,
`browser.json`, `clusters-desktop.png`, `clusters-1006.png` and
`frontend-build.log` under `output/project-isolation/`.
