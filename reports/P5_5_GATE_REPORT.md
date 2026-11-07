# P5.5 — evaluation tooling and bounded actor pilot

6 November 2026. The reproducible offline evaluator, independent fixture rubric, small actual subagent pilot and DeepInfra handoff are delivered. **The large model study is shelved at the user's request. Full P5.5/release acceptance is not closed.** No production application code or original normative contract changed in this increment.

## Delivered

`evaluation/` contains 12 source-pinned development tasks covering all six release tasks and helper/retry, inherited dispatch, stale documentation, same-name symbols, disconnected evidence and runtime abstention. Expected answers, source intervals and ordered witnesses were authored from fixture source rather than copied from query answers. Byte locks and substring/span checks detect stale fixtures. These are narrow development tasks, not a held-out corpus or whole-repository correctness oracle.

Five fixed one-shot policies compare flat file search, a conventional directed table, architecture context, context plus documentary retrieval, and context plus documentary retrieval plus typed paths. All share the source catalog, three-file cap, questions/public anchors, model/rules/snapshot manifests and token limits. Production service responses retain full envelopes and are checked for endpoint/witness/path closure. The table shares the production extractor; only the source oracle is independent. Per-arm selection policies, warm caches and instrumentation are explicit.

The outer evidence cap is 8,192 tokens. Optional actual-provider runs have a 16,384-token local request/response cap, 1,024-token output reservation, a separate reported provider ledger, pinned model/configuration and explicit per-call/total spend caps. All tool response wrappers included in the one-shot prompt count; there is no hidden multi-turn model conversation. Missing configuration yields `unverified`, not invented answers. Failures/omissions remain archived.

Full protocol, commands and result format: [evaluation README](../evaluation/README.md). Primary artifacts:

- `output/phase5/p55-final-o200k/` and `p55-final-cl100k/`: manifests, 180 transcript records each, summaries and source snapshots (12 tasks × 5 arms × 3 trials).
- `output/phase5/p55-stress/stress.json`: separately labelled documentary/path workloads.
- `output/phase5/p55-final-toolset/`: validated pinned snapshot, per-occurrence reasons/locality and independent-oracle results.
- `output/phase5/p55-subagent-pilot/`: four real isolated subagent inputs/answers and grades.
- `output/phase5/p55-deepinfra-handoff/`: four oracle-free request envelopes and source/task/input locks for the user's harness. No paid requests are launched by export/import.

Run manifests preserve hashes from their execution time. Subsequent tooling changes added the ToolSet path-variable regression fix, pilot grading and external handoff; historical offline results were not overwritten or passed off as a rerun of those later files. Production implementation digest remains `47f391df7d7d8adac859098443e669a6b8496c7d0effa7a132010cfce5d34d8f`.

## Offline results, not model answer accuracy

Each arm has 36 observations per tokenizer. Repeated tasks are not independent population samples; figures below are descriptive, without superiority confidence intervals. Source-span recall is the mean fraction of required original source intervals delivered, not the correctness of a generated explanation. Witness-pair recall applies only to tasks with labelled paths; it does not prove execution or full source sufficiency.

| Policy | Median evidence tokens o200k / cl100k | Required source-span recall | Original witness-pair recall o200k / cl100k |
|---|---:|---:|---:|
| Flat search | 856 / 840 | 94.44% | 0 / 0 |
| Directed table | 2,005.5 / 1,980 | 88.89% | 100% / 100% |
| Architecture | 4,099 / 4,047 | 88.89% | 91.67% / 91.67% |
| Architecture + documents | 6,011.5 / 5,975 | 93.06% | 91.67% / 91.67% |
| Architecture + documents + paths | 6,567 / 6,008 | 93.06% | 100% / 91.67% |

No service request/endpoint-closure error occurred in either recorded comparison. The o200k path arm delivered all eight labelled paths; cl100k explicitly returned `omitted_by_budget` for the cross-boundary and impact paths at its 4,096-token context-page cap. Correct omission is preserved as incomplete retrieval, not success. Larger token usage and graph structure did **not** establish better task performance. Flat search recovered more required source spans on this small fixture. Search reciprocal rank is reported only for actual search-hit order; graph hash order is not treated as relevance. Source-only flat search has null graph-entity ranking, rather than a misleading zero-quality score.

Documentary stress: 201 source/document files, 310,389 bytes; nine labelled lookup variants recovered their intended entity at rank one. Instrumented ingestion/index construction took about 15.0 seconds with approximately 131 MiB peak traced allocations. Bounded-path stress: 2,000 constructed vertices and 24 queries agreed with independently written depth-bounded directed BFS on every case. These workloads are synthetic, not production scale/usability claims. No pruning index or learned/Steiner method was enabled, so no pruning/model improvement is claimed.

## Actual small actor pilot

Following the user's request, four independent Codex subagents ran two tasks (call direction and stale documentation) against flat versus graph/document/path evidence, one trial each. Agents received no parent history and were instructed to read only their assigned prompt file, with no source/oracle browsing. Their actual returned answer fields are faithfully transcribed in the archive with storage whitespace normalized; they are not oracle-generated answers or raw provider transcripts. Exact inherited model/version, reasoning tokens, provider usage and system/tool framing were unavailable. The recorded input-file regions were about 1,901–1,926 tokens for flat versus 10,525–10,537 for graph; archived answer JSON regions were 312–371 tokens. Every archived file/answer pair was below the 16,384-token pilot cap and every archived answer below 1,024 tokens. This is **not** a verified whole-provider-token comparison.

Both arms supplied the correct required direction/current-callee claims, paths and scope. The graph-backed stale-document answer lacked the original `guide.md` citation. Its three retrieved source files were `ui.py`, `helpers.py` and `storage.py`; flat search delivered `guide.md`. The question's historical claim and node/relationship context let the graph actor explain the contradiction, but the independent evidence-sufficiency criterion still failed. Preserve this failure: add source/document evidence selection and budget allocation to the remediation backlog; do not replace it with a successful-looking answer or expand the file cap after observing the oracle.

The pilot also exposed a rubric false negative: original strict fact-set equality rejected extra correct scope labels in every response. `source-rubric-v2` now checks all required task facts and permits explicitly scoped context labels, rejecting unknown extra assertions. Original `strict_v1_fact_set_match` results remain recorded. Under v2, three of four responses satisfy the structured rubric; the missing document citation still fails. Because this correction followed the pilot and only two tasks were used, **3/4 is diagnostic, not a held-out accuracy estimate or superiority result**. Free-prose explanations still need independent human review.

The larger DeepInfra/model comparison remains shelved. The handoff importer accepts actual `eval_id`, pinned `model`, prompt hash, provider request identity, usage and structured answer. It retains missing, invalid, identity/budget failures, rejects duplicates and preserves prior score artifacts. Mock protocol tests cannot close the actual-provider gate.

## Pinned repository and unchanged performance workload

ToolSet was re-ingested without executing application code at commit `f8bc1ec4c54884293dace635275e95c685b03371`, with selected source digest `e50bcf9c66d7cbf4e2d0ef15b1274f3ba918197abaee87e508f7f1f0e365261e`. Publication validation is clean and the working-tree status is unchanged. The snapshot still has 16,137 entities and 12,754 relationships: 2,063 exact, 439 candidate and 10,252 unresolved. Deduplicated call occurrences: 1,770 exact known-internal, 410 candidate known-internal and 9,306 unknown-locality unresolved (11,486 total). All 182 pre-existing independent supported-subset oracle sites were emitted; 177 resolved correctly as exact, with zero wrong-exact targets. This deliberately narrow oracle does not establish whole-repository precision/recall. Full per-occurrence reason/locality data and source-oracle hash are retained.

The unchanged 50k-entity/150k-edge `geographer-benchmark-v1` viewport workload was repeated before the user's request to shelve larger tests. With graph/tokenizer preloaded and derived cache/plan cold, it took **6,219 ms cold**, then approximately **75 ms** for each of three warm calls; 102 nodes/13 curves were displayed within a 32,380-token envelope. Record: `output/phase5/performance-p55.json`. Concurrent development-host ingestion/tests ran during this sample. This misses 3 seconds for that cold condition; it does not close C14 or supersede the distinct precomputed-view condition in earlier reports. No additional large performance reruns were launched after the user's steering. Cold preparation remains an open remediation/measurement item.

An initial ToolSet audit script completed ingestion/oracle checks but used a shadowed source-path variable for its final Git status check. The script was corrected, regression-tested and rerun successfully into `p55-final-toolset`; the initial failed run/log remains historical and is not the passing evidence.

## Verification and remaining gates

The full backend run completed **184 tests** with the existing 13 warnings (`output/phase5-pytest-p55.log`, 58.10 seconds). Browser regression completed **38 journeys** (`output/phase5-browser-p55.log`, 48.1 seconds), including existing accessibility and transport-related coverage. Original-contract guards passed. After the small-pilot/rubric/handoff refinements, the focused evaluation suite passed **30 tests** (`output/phase5-evaluation-regression-final.log`, 9.68 seconds). The later five evaluator checks were targeted; do not describe this as a fresh 189-test full run. Application source did not change.

Outstanding: user-owned pinned-provider matched-whole-prompt comparison, source/document evidence selection, cold preparation performance, human orientation/AT studies, target i5/Iris Xe C14 evidence and final-build soak. The user has shelved larger model tests; preserve the prepared protocol and await their harness outputs. No external publication, deployment or full release readiness is implied.
