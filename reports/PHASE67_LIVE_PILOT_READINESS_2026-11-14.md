# Live six-task pilot — readiness attempt, 2026-11-14

Owner requested execution after the 0.2.0 release preparation. This authorises attempting the live pilot; it does not reopen the closed code-quality evaluation cycles. Web App QA & Release Copilot's get-started/audit-release workflow was used to inspect the real prerequisites before dispatch.

**Status: BLOCKED before dispatch. No live task, qualification probe or paid model call ran. No passing-pilot claim.**

## Observed readiness

| Check | Observed result |
|---|---|
| Resource-Library selected | Existing `D:/Resource-Library/.librarian-app` configuration, unchanged |
| `resource_librarian host status` | `status: stopped`, `process: null`, `cores: []` |
| Normal `host start --vault ...` | Refused: `stale_vault_lease`; prior Core PID 30316, recorded start 2026-11-12T01:35:15+00:00 |
| Current process at PID 30316 | `msedgewebview2`, started 2026-11-13T10:33:40; an unrelated reused PID, not the former Core. No process was terminated. |
| Lead binding | `preset-deepinfra` / `ByteDance/Seed-2.0-mini`; saved role-specific qualification: none |
| Research helper binding | `preset-deepinfra` / `google/gemma-4-26B-A4B-it`; saved role-specific qualification: none |
| Clerk binding | `preset-deepinfra` / `Qwen/Qwen3.5-397B-A17B`; saved role-specific qualification: none |

Bindings and qualifications were read via `RoleRouteStore.resolve` and `QualificationStore.get`, without printing credentials or Core discovery tokens. No saved record means no evidence to accept; fresh route status must be checked through the recovered Core. No model was substituted.

## Required owner action

The application explicitly refuses normal startup and requests an explicit stale-lease takeover after checking the former Core is stopped. The maintained [Librarian agent guide](D:/Librarian_V2/docs/agent-guide.md) says **“Never take over on your own”** and **“Only the person clears this”** for role qualification; agents must not bypass the gate. The PID check above avoids mistaking a recycled PID for the former writer.

Request owner approval for explicit stale-lease recovery, or have the owner recover the library through its UI. Do not kill PID 30316. After recovery, obtain the free role-specific plans/status using the exact commands in [gate §10](PHASE67_WAVE4_GATE.md#10-resource-library-qualification--exact-owner-steps-35). L0 is free; L1 requires the owner's visible spend confirmation. Check helper and Clerk for `screened` and fresh evidence, and check any lead prerequisite before opening the explore session. A live exact estimate is unavailable while Core is stopped. The guide's historical approximately $0.005 per role is planning context, not a current quoted estimate.

## Prepared execution scope, not executed

Use the reviewed 0.2.0 wheel, SHA256 `4d903d7df0cb029e332b8bff1e076b122d40dabe8dfab765aaf7615bfcc4450d`, through an enabled/accepted scoped MCP server. Preserve normal production bindings and use a disposable copy of the real ToolSet snapshot. After Core/role readiness, do the no-model packet/dispatch-shape/budget preflight before any paid dispatch. Preserve first attempts and maintain the existing reserve/cap; never reopen a model cycle or switch the Clerk after a timeout.

In the actual Resource-Library `explore` session, the lead must compile and call `dispatch_plan` for four tier-3 code-block contracts, one tier-2 synthesis depending on them, and one tier-1 review depending on the synthesis. A handwritten template or scripted provider is not a substitute for the lead's live plan.

Record actual waves, all six task states, Clerk citation-verification numerator/denominator and closure strengths, stale count, wall time, model identities and cost receipts. Expected dependency layers are four contracts → synthesis → review; observed execution is authoritative. Verified citation handles show bounded citation resolution, not semantic correctness.

| Pilot metric | This attempt |
|---|---|
| Live tasks dispatched | **0/6** |
| No-model preflight | **Not reached**: Core/role readiness blocked |
| Waves / verification / stale / timing | **Not measured** |
| Paid calls / cost | **0 / $0** |
| Release/pilot verdict | Pilot remains **unvalidated**; F4 owner acceptance still pending |

No product code, binding, qualification, lease, release tag or remote branch was changed. No push.
