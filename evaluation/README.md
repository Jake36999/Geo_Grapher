# P5.5 evaluation protocol

Run from the repository root with the tested Python environment and `src` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH='F:/uv-data/Geo_Grapher/src'
& './output/wheel-env/Scripts/python.exe' -m evaluation.run --output output/phase5/MY_NEW_RUN --repeats 3
& './output/wheel-env/Scripts/python.exe' -m evaluation.run --output output/phase5/MY_NEW_CL100K_RUN --encoding cl100k_base --repeats 3
& './output/wheel-env/Scripts/python.exe' -m evaluation.stress --output output/phase5/MY_NEW_STRESS
& './output/wheel-env/Scripts/python.exe' -m evaluation.toolset --output output/phase5/MY_NEW_TOOLSET
```

Each destination must be new. Historical evidence is retained. All normal runs are offline and execute no fixture/repository source. The separate explicit model command can execute an adapter. No API credential is read by this harness. The fixtures are data, including their deliberately misleading documentation.

## Locked tasks and independent grading

`tasks.json` supplies the six approved release tasks plus retry/CFG, inherited dispatch, misleading documentation, same-name symbols, disconnection and unsupported runtime claims. Questions, public focus/pin anchors and queries go to retrieval; `oracle` never does. Expected labels, source intervals and admissible ordered paths were manually authored from the fixture text before running the resolver. `sources.lock.json` pins every fixture byte. A source mismatch or stale oracle span stops the run; updating the lock requires source/oracle review. The small development fixture is not a held-out benchmark or a claim of whole-repository accuracy.

`grade()` validates a strict structured answer: closed-label facts, ordered qualified-name paths, citations, abstention and exact scope. The shared vocabulary contains all candidate labels across tasks, including contradictory choices; selected-task answers are withheld. This is a constrained structured task, not open-ended natural-language answer grading. Explanatory prose needs human review. An apparently correct answer without required delivered-source witnesses fails. Validity and sufficiency are separate: citations must be in the pinned source, delivered to that actor, and cover every required span. A reverse or incomplete path fails even with plausible prose. Grader tests use hand-constructed answers exclusively as **test fixtures**, never as model outcomes.

The small subagent pilot exposed a v1 rubric false negative: exact equality of fact sets rejected additional correct scope labels. `source-rubric-v2` requires every task-specific claim and permits explicitly scoped context claims; other extra claims fail. `strict_v1_fact_set_match` remains in the result. This revision was made after the pilot; those scores are diagnostic, not held-out confirmation. Explanations are still not automatically semantically verified.

## Five arms and fixed access policy

1. `flat_search`: deterministic lexical file ranking over all code/document text; up to three whole source files.
2. `directed_table`: conventional directed exact-static table with endpoint definitions, plus raw source access. Table facts share the production extractor; they are not an independent correctness oracle.
3. `architecture`: production v1.1 architecture context, raw source access, and conformance on the rule task.
4. `architecture_documents`: architecture plus hybrid formal/documentary lexical search.
5. `architecture_documents_paths`: the same plus typed witness path requests.

All arms receive the same questions, source/snapshot/rule/runtime manifest, shared label vocabulary, answer schema, source catalog, three-file source-access cap, maximum three service calls, 8,192-token evidence cap, 16,384-token total local request/response cap and 1,024-token output reservation. They may consume less than the cap. Flat search uses its lexical order; table/context arms use public focus/pins; documentary arms first use retrieved hits to choose files. These are preregistered **one-shot retrieval policies**, not autonomous agent strategies. No interactive tools or previous conversation are hidden from the token ledger. Model arms receive only one accumulated prompt containing all committed evidence and service wrappers. Retrieval requests/results, including errors and unconsumed continuation cursors, are archived separately.

Evidence packing admits whole service envelopes/table bundles/source files. It counts the entire evaluation evidence envelope, including omission bookkeeping and scope; it never slices graph records or path steps. Production responses are independently checked for node/witness/path closure. Signed cursors are retained as served. Service calls use 4,096/2,048-token page limits; the outer cap includes all retained pages. Source selection is bounded and can miss relevant files. Such misses remain results, not silently replaced with oracle material.

`transcripts.jsonl` retains every trial/task/arm, request, response, omission, error, prompt hash and model status. `manifest.json` records source/task/harness/build hashes, snapshot/model/filter/runtime identity, tokenizer weights, configuration, index cost, traced memory and environment. Seed 505 randomizes task/arm order. Caches are shared; tracemalloc is enabled, so latency is an instrumented development-host distribution, not a cold or target-device measurement. Repeats of the same 12 tasks are not independent population samples. No superiority confidence interval is claimed.

Offline metrics report source-span recall, graph-entity presence (null for source-only flat search), search reciprocal rank only where a search ranking exists, original witness-pair recall, typed path outcomes, tokens, omissions, errors, latency, index cost and traced memory. A context node's hash order is not a relevance ranking. These metrics are not answer correctness. Documentary claims never become source truth; runtime absence never becomes a negative execution label. Optional learned/Steiner/pruning experiments are disabled. The stress workload compares the reference typed path engine with independent bounded BFS and makes no pruning speedup claim.

## Optional actual-model adapter

Supply `--adapter-config path/to/config.json` only for an intentionally configured model run:

```json
{
  "command": ["C:/absolute/path/python.exe", "C:/absolute/path/provider_adapter.py"],
  "model": "EXACT_PINNED_PROVIDER_MODEL_VERSION",
  "configuration": {"temperature": 0, "seed": 505},
  "provider_spend_cap": 0.01,
  "max_run_spend": 2
}
```

Caps are in the adapter's declared billing currency, conventionally USD. The harness rejects a run whose worst case (all scheduled requests times the per-request cap) exceeds the explicit total cap. No retries are hidden. Never put API keys in configuration or stdout: configuration and transcripts are archived. The trusted adapter owns credentials, provider-specific framing/tokenization, actual model execution and **pre-request** enforcement of both output and monetary caps. This repository does not supply a provider SDK or imply that a JSON process alone proves a remote inference occurred. Archive provider request identity/usage and verify it against the provider's logs for acceptance.

The adapter receives one UTF-8 JSON object on stdin:

```json
{"protocol":"geographer-eval-model-v1","model":"PINNED_VERSION","configuration":{},"prompt":{},"max_output_tokens":1024,"provider_spend_cap":0.01}
```

Return one UTF-8 JSON object on stdout, with no banners:

```json
{"model":"PINNED_VERSION","provider_request_id":"ACTUAL_PROVIDER_ID","usage":{"input_tokens":1000,"output_tokens":200},"answer":{"status":"answer","facts":[],"citations":[],"paths":[],"scope":{"snapshot_id":"...","filter":"...","grouping":"...","model_digest":"...","runtime_collection":null},"explanation":"..."}}
```

The harness counts the full canonical local adapter request before execution, reserves output plus 256 framing tokens, and rejects oversized requests without launching the process. It then checks both complete local request/response and reported provider input/output ledgers. These are separate tokenizations, not a claim of exact provider framing from tiktoken. Provider mismatches, over-budget completions, invalid answers, failed starts, nonzero exits, output overflow and 60-second timeouts are retained as failures, never omitted or successful scores. Stdout/stderr are bounded to 1 MiB/8 KiB; overflow terminates the adapter. It is trusted code, not an OS sandbox; adapters must not leave descendant processes. Local protocol tests use explicit mock subprocesses and cannot close the actual-model gate.

Without adapter configuration every model outcome is `unverified`, with an explicit reason. No synthetic answers, invented accuracy, or inferred model superiority are reported.

## User-owned DeepInfra harness handoff

The user requested a small subagent pilot and shelved larger model tests in favour of their own DeepInfra-connected harness. No provider SDK or account configuration is needed here. The prepared handoff is `output/phase5/p55-deepinfra-handoff/requests.jsonl` (four actual evidence prompts: two tasks, flat and graph/document/path arms, one trial). It contains no selected-task oracle. Its manifest pins the input file and source/task versions. Do not automatically expand this to a paid study.

### Grounding remediation — 7 November 2026

The original handoff/results remain historical. A corrected four-request handoff is in `output/phase5/mcp-remediation-20261107/handoff/requests.jsonl`. The documentary question now reserves one of the same three source slots for original document support and admits source bundles before graph envelopes. Source presentation has absolute `lines[].line` values and verbatim line text. Public task-type namespace constraints remove unrelated label families; they never select hidden oracle values. Whole-envelope budgets still include the new presentation. Model paths use original code-subject qualified names, not bare filenames or arbitrary vocabulary right-hand values.

Regenerate a small handoff without a paid call:

```powershell
& './output/wheel-env/Scripts/python.exe' -m evaluation.prepare_grounded_handoff --output output/phase5/NEW_GROUNDED_HANDOFF
```

Task-local validation is available as `evaluation.grounding.validate_actor_answer(answer, prompt)`. It returns structured `{code, message, retryable}` issues using only delivered evidence and the public task contract, never goldens. `validation_callback(prompt)` returns a callable suitable for a librarian validation-hook interface. Use the structured API to distinguish missing retrieval (`retryable=false`) from model formatting/citation errors. The referenced legacy `.utility/librarian/localmodel.py` is not Librarian V2's current `clerk.py`; no global file-path prohibition was added to either library.

The validators check complete vocabulary strings including prefixes (do **not** split them into right-hand values), task-type namespaces, code-subject identity, citation bounds/scope, and AST call/base-expression source spans. An import, comment, string or definition header is not a call-site witness. A stale-document claim requires documentary citation. These checks reject unsupported presentation; they cannot prove semantic correctness, exact binding or staleness merely from a syntactic call or a `.md` suffix. The independent rubric remains necessary.

`run_model(..., max_repairs=1)` is opt-in; default zero adds no model calls. Adapter config may add `"max_repairs": 1`; the worst-case run spend check now includes both attempts. Every attempt and validation issue is archived. Input/output/provider totals are cumulative across attempts, and repair prompts include the previous answer and diagnostic messages. A missing documentary/source witness stops retry; repair never invents missing retrieval. A retry that cannot fit the remaining budget is rejected before launching another process. The model output schema keeps its existing `maxItems` constraints; there is no arbitrary five-fact limit. A provider-specific bridge may simplify its transport schema, but must still run the full local schema/grounding checks and preserve usage for every attempt.

No new paid trial or large benchmark was launched for this remediation. The four original Llama responses were checked offline against their original delivered evidence. Fresh model performance remains unverified until the user's harness consumes the corrected handoff.

The actual Librarian V2 MCP client now preserves the atomicity of structured results: its existing 8,000-character boundary withholds oversized JSON with a retryable size error instead of slicing endpoint/citation records. On that error, request a smaller Geo Grapher page/token budget; do not parse the withheld body as a successful page. Both SDK structured-result spellings are supported. This current client connects over stdio, so use `geographer serve --database ... --schema-version 1.1`; simply registering Geo Grapher's HTTP endpoint is not sufficient for that stdio-only client.

### Multi-model follow-up and contract v3

The next archived round is audited in `reports/ACTOR_ROUND_2_REVIEW.md`. Its original 2/12 pass count is preserved. `guide.md` is present in every saved stale-document graph input; omitted or partial citations must not be described as missing retrieval. There is no archived three-model 0/12 baseline.

Use the newer `output/phase5/actor-contract-v3-20261107/handoff/requests.jsonl` for the next small user-harness run. It supplies explicit required provenance, derived document-section anchors, public path requests, and evidence-grounded enums for facts, citation filenames and qualified subjects. Every exported request now carries a ready `response_format` and a `schema_transport` audit. Its canonical size, including this metadata, is included in preflight accounting. Regenerating with `evaluation.prepare_grounded_handoff` uses the current contract; original runs remain unchanged.

The compatibility helper is:

```python
from evaluation.transport_schema import compile_transport_schema
from evaluation.grounding import validate_actor_answer

compiled = compile_transport_schema(prompt, unsupported_keywords=("uniqueItems",))
response_format = compiled["response_format"]
# Send response_format via the user-owned provider adapter.
# On return, retain full local JSON-schema/grounding validation:
issues = validate_actor_answer(answer, prompt)
```

Add other unsupported keywords to that tuple only for an explicit reviewed provider profile; do not remove them from `prompt['answer_schema']` or local validation. `uniqueItems` is omitted from transport by default but remains enforced locally. Full-label/file/subject enums prevent prose strings and field identity confusion where the provider enforces them. Structured output is not semantic proof, and some endpoints may still reject the mode. Any fallback must be explicit, recorded and followed by the same local checks; no automatic downgrade is performed by the compiler.

The current result protocol does not prove that the external runner used a response format or repair loop. Archive the selected mode, schema hash, failed negotiations, every attempt and full provider payload/usage alongside the result rows for the next comparison. No external runner code or account settings were modified and no paid follow-up ran here.

### V4 identity closure and consistency correction

The V3 model round exposed a defect in our enum generation: the stale-document flat schema excluded the public requested target `app/service.py.process`. Under strict schema mode, its correct path was impossible. See `reports/ACTOR_ROUND_3_REVIEW.md`; original scores stay 7/12 with the contract defect disclosed, not interpreted as a fair model/arm comparison.

Use **`output/phase5/actor-contract-v4-final-20261107/handoff/requests.jsonl`** for the next run. V4 adds compact snapshot-validated public anchor identities for every arm, while keeping source files, slot counts and token limits unchanged. Identity-only records are not source bodies or dependency edges. The compiler and validator accept these identities; a feasibility gate rejects public endpoints excluded by a schema before any adapter runs. Old incomplete pages may now fail export/compilation: regenerate four fresh requests with `evaluation.prepare_grounded_handoff` rather than modifying the immutable V3 inputs.

The fact→endpoint rule is scoped to `answer_contract.path_semantics="direct_call"`. Immediate/direct callee claims must agree with the corresponding requested path, which has exactly two subjects. Multi-hop chains can refer to intermediate callees without forcing them to be final endpoints. Wrong direct endpoints/loops/lengths are repairable answer errors; a real source gap remains non-repairable. No path or fact is automatically copied over the other to manufacture a pass.

`check_path_enum_feasibility(prompt, schema)` is also available for external runners to check stored schemas. Local process calls archive `invalid_actor_contract` without launching a provider subprocess if compilation fails. Exported response formats and all local validation/attempt-budget requirements still apply. No new paid calls ran while preparing V4.

### V4 outcomes: repair only the four failed answers

The recorded V4 one-shot result is 8/12, with all endpoint contracts feasible. See `reports/ACTOR_ROUND_4_REVIEW.md`. A local check previously failed to require documentary assessment/citation when the model omitted `document:stale`; this now follows the existing public documentary task flag. V4.1 contracts explicitly list required assessment namespaces. Neither the conclusion nor provenance is silently inserted from a golden answer.

There is no need to resample the eight passing answers. The offline planner prepares oracle-free repairs from recorded responses:

```powershell
& './output/wheel-env/Scripts/python.exe' -m evaluation.prepare_repairs --directory output/phase5/actor-contract-v4-final-20261107 --output NEW_REPAIR_DIRECTORY
```

Prepared packets already exist at `output/phase5/actor-v4-repairs-20261107/70b/requests.jsonl` (three) and `500b/requests.jsonl` (one). The `300b` packet is empty. No provider calls are made by preparation. Use each request's pinned model and **remaining** output/total limits, not fresh original limits.

`build_repair_prompt` keeps all original source records/scope verbatim. Direct-call repairs disclose omission of non-source service/rule records; no new evidence is fetched. Other tasks retain full original context. This policy is shared with `run_model(max_repairs=1)`. A missing source or exhausted original budget blocks repair.

Return actual results with the repair prompt hash and usage, then use `evaluation.handoff score --handoff PATH_TO_MODEL_REPAIR_DIRECTORY --results RESULTS.jsonl --model EXACT_MODEL_ID`. The scorer pins that model, checks the original parent receipt hash, verifies cumulative parent/child local and provider budgets, reports grounding issues plus the independent rubric, and adds `accepted` only if both pass. Reports use `evaluation_stage="bounded_repair"`; original one-shot scores remain untouched. Keep original receipt files at their recorded paths, and archive returned repairs separately. Repaired outcomes and total costs must not be presented as initial one-shot accuracy.

```powershell
& './output/wheel-env/Scripts/python.exe' -m evaluation.handoff export --run output/phase5/p55-final-o200k --output output/phase5/NEW_SMALL_HANDOFF
& './output/wheel-env/Scripts/python.exe' -m evaluation.handoff score --handoff output/phase5/NEW_SMALL_HANDOFF --results ACTUAL_RESULTS.jsonl --model EXACT_MODEL_VERSION
```

Each external result line must contain `eval_id`, `model`, `prompt_sha256`, `provider_request_id`, `usage: {input_tokens, output_tokens}` and `answer`. Copy identifiers from the request; return the actual model/version and provider usage. The user's harness owns monetary/output enforcement and provider request archives. The importer checks pinned model/input identity, both local and reported provider token ledgers, and the source rubric. Missing, invalid, over-budget, duplicate and unknown outcomes are explicit. Repeated imports cannot overwrite a prior score artifact. Mock interchange tests stay in temporary test directories and are not model evidence.

Actual Codex subagent pilot inputs/answers and grades are under `output/phase5/p55-subagent-pilot/`. They used isolated parent-free contexts, one allowed input-file read and no repository/oracle access. Raw provider/system/tool framing and exact inherited model version are unavailable. File/completion token counts are recorded separately; this pilot cannot close pinned-provider whole-prompt acceptance. The larger offline retrieval runs were already recorded before the user deferred larger tests; their original hashes/results remain historical evidence.

## Human/AT study protocol (not executed by this runner)

Use the same source-locked questions and evidence for spatial, search and table/matrix conditions. Randomize/counterbalance order with a recorded seed, disclose practice/training and task carryover, and record participant/device/browser/assistive-technology versions and consent. Keep each failure/abstention. Score the independent task rubric, evidence recovery, elapsed time and ability to name current container/filter/snapshot. Ask participants to recover original witnesses, not merely read a bundle count. Record screen-reader keyboard journeys separately. Automated retrieval/model runs do not establish human orientation, screen-reader usability, C14 performance or final-build soak acceptance.
