# Recovery accounting contract (Review 4)

This design is registered before product changes. It contains no question, target, marker or key data. The implementation and no-model fixtures must prove these bounds before paid agent evaluation.

- The ordinary code-research walk retains its 12-step budget.
- A shared ledger admits at most three **additional executable steps** per episode; each pattern may act once. A real step gets a stable step ID. Joint remedies share that ID rather than charging or silently repeating an action.
- FP1/FP2 search transformations execute locally inside Geo Grapher. FP6 offers only scoped canonical candidates on structured errors. They never invoke a model.
- FP3 selects a top unopened candidate from structured retrieval metadata and opens it directly through the permitted registry tool. It does not ask a model to choose a candidate.
- There is at most **one post-evidence model revision**, shared by FP3/FP4 and the FP5 definition/application contract. An unresolved check cannot schedule another revision.
- FP7 permits at most **one guarded tool-free step-limit synthesis**. It shares the same three-step ledger. Thus there are at most **two additional paid model invocations** per episode, not three. A source-open/search action can use the third executable step.
- Both extra model invocations retain the pinned route, temperature, cancellation, context, token and cost guards. Tools proposed during a tool-free action never execute.
- Search triggers and actions remain in the front door; the Loop schedules deferred actions but does not duplicate search scoring rules. The code-research caller can request a detection-only first pass so its first draft is recorded before remedial search/source/revision. Other clients may apply front-door recovery immediately.
- Every record carries `{pattern, trigger_value, action, outcome}` with `outcome` resolved/unresolved, plus optional step ID and before/after observations. Runtime outcomes use structured signals, never answer keys. Benchmark success is scored only after collection.
- First-attempt reporting must distinguish an actual pre-recovery answer from an episode that needed recovery before producing any answer. It must not invent a counterfactual answer from recovered observations.

The two-paid-call bound is a budget requirement. If it cannot be proved, the estimate must be revised and paid work blocked until any required owner approval is obtained. No merge or push is authorised by this design.
## Search transport and accounting

The agent-facing search schema stays flat. Episode context uses standard MCP request metadata under `geographer/recovery`: `episode_id`, original `question`, `mode` (`auto`, `defer`, `off`) and `remaining_steps` (0–3). The Loop, not the model, supplies it. A first-pass `defer` result exposes deterministic pending triggers and baseline evidence; it consumes no recovery step. A subsequent `auto` action may apply FP1 and FP2 jointly, with one shared step ID. Repeated identical requests reuse the repaired candidate cache rather than executing another remedial search. Pattern records and consumed-step counts are returned before the complete-envelope token/character recount.

Server episode state is scoped to the MCP connection, original-question digest and episode ID. A scoped server admits at most 1,024 named episodes and fails closed at capacity rather than evicting used-pattern records and accidentally permitting a second recovery. Ordinary calls without episode metadata are independent tool-call episodes. This finite-server limit is a known operational bound; it is not an unbounded conversation memory. Cross-server and agent-side accounting must also be enforced by the Loop's shared three-step ledger.

`resolved` on FP1/FP2 means the resulting preview clears the deterministic weak-hit condition; it is not a claim that a benchmark answer is correct. FP6 logs the existing scoped candidate menu as an observation with zero additional executable steps, and marks resolution only after a real offered ID is accepted. A menu is not an automatic source retry. End-to-end recovery rates are separately scored after collection. The isolated Librarian feature branch now supplies the shared agent-side ledger and forwards `used_patterns` across scoped server connections. Its integration is a release prerequisite; a standalone front door does not impose an episode-wide ledger on unrelated clients.

## Diagnostics and retention

The code-research Loop keeps the initial draft internally and emits only the chosen final text to its user. Evaluation receipts can contain that draft, the final answer, tool arguments and bounded source previews. Keep evaluation output private along with browser traces. Per-HTTP receipts contain request hashes and usage; separate raw response files can contain private source-bearing arguments or answers. They contain no authentication headers. Retain the original files for audit rather than overwriting failed attempts.

Semantic retrieval remains explicitly opt-in and local-only. Its derived SQLite cache is disposable, snapshot/encoder-bound and distinct from canonical graph facts. Enabling it requires the exact model assets and a matching prebuilt namespace; cache mismatch fails closed. See [local semantic search](LOCAL_SEMANTIC_SEARCH.md) for provisioning and rollback.

