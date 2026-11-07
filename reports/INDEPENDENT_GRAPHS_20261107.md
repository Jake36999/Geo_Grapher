# Independent project graphs — implementation and test review

7 November 2026. Implements the revised one-graph-per-project boundary while
preserving the prior prototypes and standalone query servers.

## Review of the supplied test run

The transcript reports tool use on all five questions: **18 calls**, **44,974
reported tokens** (8,994.8 average), and approximately **$0.0065**. It attributes
the improvement to a 1,200→2,000 output allowance, a tool-use instruction and two
column-name corrections in its runner. This shows an improved tool-use workflow;
it is not a controlled answer-accuracy/grounding evaluation, nor the earlier
direction/stale-document benchmark. Those results must not be combined into one
pass rate. No provider trial or billing verification was repeated here.

The architecture does not depend on the transcript's stronger claims about
embedding geometry or formal ontology guarantees. Isolation is enforced through
separate stores, explicit graph addresses and observed noninterference tests.
Typed nodes, project prefixes and reusable aliases do not by themselves prove
that an LLM will reason correctly or that two claims mean the same thing.

## Delivered architecture

`GraphCatalog` registers each resolved project root with a stable graph identity
and its **own canonical SQLite snapshot store**. A project may attach its own
paper corpus, also in a separate file. The catalog stores registrations, overlap
decisions and declared bridges, not a combined entity/concept index. Code-store
ownership and paper-file uniqueness are checked, including physical file aliases.
Catalog creation refuses to add its tables to an existing project database.

The new scoped MCP hub requires `{graph_id, request}`. Missing/unknown graph IDs
are errors. Code request schemas remain the approved inner v1.1 contracts;
optional paper tools use `paper_*` names. Snapshot/alias/cursor resolution stays
inside the chosen graph. Paper selection uses a context-local override rather
than changing a process-global database path. Existing single-store servers
retain their configured store for compatibility.

`list_graphs` and `geographer://graphs` expose the project registry and published
heads. One unavailable graph is reported explicitly and does not prevent discovery
of healthy graphs. The UI disables unavailable selections instead of silently
opening another graph.

## Collisions and aliases

Root planning detects exact-root reuse and parent/child overlaps. An overlapping
import stops for an explicit decision; a plan digest protects against stale
decisions. `keep_separate` retains independent stores. `child_module` additionally
records an operator-declared bridge while keeping both graphs separate. Imports
reserve the catalog writer transaction while registering the new head/decision.
Unchanged inputs can reuse an existing snapshot. Batch imports commit per project
and report any completed graphs if a later import requires collision review.

Automatic merge is **disabled**. There is no physical merge executor or GUI import
wizard in this baseline. Root overlap can leave documentary/source copies in
both graphs; historical parent snapshots are not automatically rewritten to
extract a child subtree. These are explicit independent copies, not shared nodes.

Reusable alias rules are templates applied within each graph. A domain-local
reviewed policy can be supplied to `pipeline.maintain refresh --alias-policy` with
the existing mandatory backup. Same-named concepts or same-DOI source instances
in different graphs stay separate. Declared concept/document bridges are bounded
operator assertions with rationale/evidence; they do not coalesce identities or
change retrieval/diagnostic calculations. Local endpoint references/evidence are
operator supplied, not independently verified scientific claims.

## Federation and display

`federated_search` explicitly selects 2–8 graph IDs. It returns independent
canonical search envelopes with **no global ranking**. Exact token accounting
covers the complete serialized federation response. Whole graph envelopes are
omitted with a reason when needed; partial node/edge deletion cannot break
endpoint closure. Single code-query routing also includes the scope wrapper in
its token cap. Paper tools retain their documented character/row limits.

The new workspace shows up to four root clusters in one interactive 3D overview
and two independent detailed 3D/list/matrix applications. Each pane's API paths
and saved views are graph-scoped. Catalog labels remain presentation labels;
underlying graph/entity IDs remain unchanged. Dashed amber bridges form a distinct
display layer and do not enter either graph's dependency metrics. Keyboard
selection and standalone links complement WebGL navigation.

The shared overview currently shows graph roots, not one mixed-detail scene
containing every internal node from every graph. Cross-graph impact/similarity,
paper-specific federation, merge execution, richer bridge validation and a
resource-governed large graph-service pool remain further increments. This is
not multi-tenant authorization or full release acceptance.

## Real bounded pilot

The earlier 15-file profile was re-ingested into two new independent stores:

| Project | Graph ID | Entities | Code relationships |
|---|---|---:|---:|
| Librarian_V2 | `g_1bbebca16afc45c39b2f2f8a` | 424 | 284 |
| Timeline-mapping | `g_f329b1eb566856ee104f3f35` | 101 | 0 |

Each has its own SQLite file, snapshot head, lexical index and query service.
The zero Timeline code-edge count is expected: the pilot includes Markdown,
not an implemented historical event/claim graph. Neither full project was
ingested; Quantule and network_management were not ingested. No paper corpus
was automatically assigned to either project. The current AI research corpus
remains separate; a paper test harness must not assume these pilot graphs have
paper data attached.

Preview: **http://127.0.0.1:8774/**. The existing 8765 service and earlier 8773
combined-snapshot pilot are preserved. No DeepInfra/Librarian process was stopped.

## Verification

Regression coverage includes:

- Adding a second graph leaves the first graph's code search response and paper
  retrieval response unchanged, including local ranking/aliases.
- Identical local paper IDs and a homonymous `field` concept retain different
  meanings under concurrent queries to independent corpora.
- Missing/unknown graph IDs, foreign snapshots, misregistered stores and attempts
  to attach one paper database to two graphs are rejected.
- Root overlap decisions, stale plans, durable child-module/reference bridges,
  graph-identity collisions and same-input snapshot reuse are exercised.
- Real MCP stdio tests cover code and paper wrappers, repeated tool discovery,
  structured graph errors and mandatory scope.
- Federation and single-code routing verify full-response token limits.
- HTTP tests and real-browser checks cover two independent detail panes, graph
  overview selection, graph-local API paths and responsive layouts. Screenshots
  were visually inspected; pane headers were adjusted to wrap at narrow widths.
- Existing paper, source-isolation, actor and transport regressions remain in
  the selected test run. Final counts are recorded in the machine receipt below.

Receipts: `output/named-graphs/tests.xml`, `browser.json`, `ingestion.json`,
`verification.json`, `frontend-build.log`, `workspace-desktop.png` and
`workspace-1006.png`. Existing Starlette/httpx deprecation and frontend chunk-size
warnings remain. No paid models, simulations, large soak study or target-hardware
acceptance was run.

Final result: **106 tests passed** (one existing deprecation warning). Real
Streamable HTTP MCP negotiation used protocol **2025-11-25**. A two-graph
federation response consumed **2,585 / 4,096 exact tokens**, including its wrapper,
with independent rankings. Both published project stores passed validation.
Additional transport/harness receipts are `mcp-http.json` and
`harness-handoff.json` in `output/named-graphs/`. The latter is an adapter handoff,
not authorization for additional paid model trials.

The exact routing/storage/UI boundary and operating commands are in
`GRAPH_WORKSPACE_SPECIFICATION.md`. The next harness adaptation should discover
graphs, select the intended owner, check `papers_available` when using paper tools,
and retain `graph_id` with every returned source/claim reference.
