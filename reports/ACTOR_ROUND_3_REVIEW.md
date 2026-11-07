# V3 contract defect and V4 correction — 7 November 2026

The next 12 archived responses were read alongside their matching request schemas, not only the supplied narrative. Original scores reproduce as **7/12** (70B 1/4, 405B 3/4, 480B 3/4). Every prompt hash matches; all rows record `negotiated_mode=json_schema`. Original inputs, answers and scores are preserved. No new paid trial ran.

## Root cause: the correct flat-arm answer was excluded by our schema

For `0/stale_document/flat_search`, the public request already names `app/service.py.process` as the target and the fact vocabulary permits `immediate_callee:app/service.py.process`. However, the V3 transport path enum was:

```json
["app/helpers.py.retry_save", "app/ui.py.bypass", "app/ui.py.submit"]
```

**`app/service.py.process` was absent.** The enum builder collected declarations from selected source files and graph nodes. Flat search supplied no graph nodes and did not include the target declaration file. A strict-schema answer could not contain the correct target even when the model identified it in facts. This was an implementation defect in the schema I supplied; the missing feasibility test should have caught it before any paid run.

The three returned endpoints are all allowed alternatives from that enum. The evidence does not establish that the 70B model remembered another task or that the 480B model independently chose a self-loop because of poor reasoning. The correct choice was unavailable. Adding a consistency instruction alone would leave incompatible output constraints.

The flat arm actually used **three** source slots: `guide.md`, `app/ui.py`, `app/helpers.py`. It did not have an unused fourth slot for `app/service.py`. Raising the file allowance or swapping in oracle-derived source after seeing the result would change the retrieval comparison. The correction below keeps the original three files and slot/budget limits.

Machine-readable audit: `output/phase5/round3-recorded-audit.json`. `path_enum_missing_public_anchors` identifies the omitted target for all three stale-document flat trials. Their scores remain failed historical outcomes, with a contract-invalid diagnosis rather than model-error attribution. **7/12 cannot establish a fair graph-versus-flat advantage when three flat-arm trials had an infeasible contract.** The smaller dataset and prior cross-model/protocol differences remain limitations too.

## Implemented V4

1. **Identity closure from the snapshot.** The existing public query anchors are resolved in the snapshot before retrieval. Both arms now receive a compact mandatory `scope.anchor_identities` list: qualified name, kind, repo/path and `basis=snapshot_identity_only`. The transport enum and local identity validator accept these known identities even when their declaration files are outside the source page. No dependency edge, hidden oracle target or source body is inferred from that metadata. Source/witness evidence is still required for path steps. The flat arm gains no graph traversal and its three source files are unchanged.
2. **Feasibility before provider execution.** `check_path_enum_feasibility` checks that the schema can represent every public requested endpoint. It does not require a positive path to exist, so disconnected/abstention tasks remain valid. A violation becomes `invalid_actor_contract`/`PATH_ENUM_INFEASIBLE`, archived without launching an adapter. Re-exporting an old incomplete evidence page is rejected; prepare fresh V4 evidence instead of blindly copying a requested name or hidden golden into the enum.
3. **Scoped fact/path consistency.** The proposed rule is applied to explicitly declared `direct_call` tasks (callers/callees, immediate-callee documentary checks and same-name direct calls). A selected requested `callee:X` or `immediate_callee:X` must agree with its path endpoint; unrelated callee labels are removed rather than generating unrequested paths. Direct-call paths have exactly two subjects. Dependency-chain tasks do not force every intermediate callee to be the final target. This avoids breaking legitimate multi-hop explanations.
4. **Repairable format errors stay repairable.** A wrong endpoint, self-loop or inserted intermediate on a direct-call answer receives consistency/anchor/length diagnostics. The validator does not misclassify those malformed paths as missing source and prevent a repair. A correctly formed requested path with genuinely absent call-source evidence still returns a non-repairable retrieval gap. Answers are never silently rewritten from facts.

The V3 public anchor validator already rejected wrong endpoint pairs. The archived rows do not demonstrate that the external runner invoked that validator/repair loop; even if it had, the old strict enum prevented a valid repair. The runner should apply both the supplied transport format and the local validators, preserving every attempt and its usage.

## Ready for a fresh small run

Use **`output/phase5/actor-contract-v4-final-20261107/handoff/requests.jsonl`**. It contains the same two questions × flat/graph arms, with fresh prompt/schema hashes and no model execution. The import-only target `app/service.py.process` is legal in the flat stale-document path. Graph and flat source selections remain unchanged. Full canonical request sizes are 2,795/2,834 tokens for flat and 8,678/8,914 for graph; all satisfy the existing 16,384-token preflight with 1,024 reserved output tokens and framing margin.

Regenerate only four requests with `python -m evaluation.prepare_grounded_handoff --output NEW_DIRECTORY`; never replace the prior model results. Send the exported `response_format`, then apply `validate_actor_answer`/the bounded process adapter before treating an answer as acceptable. New provider performance remains unverified. The only claim here is that the observed schema contradiction is removed and the local checks pass.

## Verification

**87 targeted offline tests pass** in 17.56 seconds (`output/actor-round3-regressions.log`). New cases reproduce the historical enum defect; accept the legitimate imported-callee path without adding a source file; reject excluded public identities before subprocess execution; diagnose all three recorded wrong endpoints and direct-call intermediates; preserve multi-hop semantics; and prove identity metadata cannot substitute for original call source. Existing actor schema compatibility, bounded repair/interchange, wire/budget and MCP stdio/HTTP/SSE checks remain included. The one warning is the existing Starlette TestClient deprecation. The four-request preparer also passes (`output/actor-contract-v4-preparation.log`). No large benchmark, model call, application deployment or release-acceptance closure is implied.
