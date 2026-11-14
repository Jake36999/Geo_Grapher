# Agent recovery integration review registration

Before dispatch: one DeepInfra `deepseek-ai/DeepSeek-V4.1-Flash` engineering review, temperature 0.2, no thinking, output at most 2,048 tokens, task allowance **$0.03**, no registered retry. Use the approved delegation script and mandatory dry run. The packet contains only the public recovery contract and selected source from the isolated Librarian feature branch; no question sets, keys, owner configuration or credentials.

Purpose: identify concrete insertion points and guard requirements for FP3/FP4/FP7, first-draft checkpoints, standard MCP recovery metadata, a shared three-extra-step ledger and at most two additional model invocations. This is advice only; implementation still requires failing tests first. It is not the paid diagnostic pilot or the final benchmark cycle.

Conservative workflow allocation becomes **$6.32253291** including the construction allowance, both engineering-review allowances, 60 A/B episodes, 30 pilot episodes and the 90-episode final cycle. Hard cap remains **$6.50**; pool reserve remains nonspendable. No merge or push is authorised.
## First review outcome

The single registered call completed and cost **$0.00239160**, receipt `20261113T193247-172e9a51`, but its 2,048-token output was **truncated**. It is retained as partial advice, not a completed review; no retry is registered or dispatched. Raw output and receipt remain under `D:/Librarian_V2/tmp/deepinfra-delegation/runs/20261113T193247-172e9a51-review4-agent-design.*`. The prior mandatory dry-run reserve was $0.00270140. Cumulative workflow commitment after this call is **$0.26683144**, leaving **$6.23316856** below the hard cap; reserve unchanged.

Locally verified useful insertion points: maintain a separate recovery ledger instead of raising the ordinary step limit; route every new paid call through context fitting, profile reservation and runtime invocation/event binding; check cancellation around direct source opens; transport metadata separately from tool arguments; keep the existing MCP admission checks and active registry surface. The partial review does not verify an implementation, first-attempt metrics or the two-paid-call bound. Those still require failing tests and local verification.

