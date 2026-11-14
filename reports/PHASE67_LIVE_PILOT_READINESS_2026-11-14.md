# Live six-task pilot — readiness attempt, 2026-11-14

**Current outcome: pilot FAIL.** Owner approvals subsequently cleared funding and temporary setup; the actual outcomes are in [the pilot report](PHASE67_LIVE_PILOT_20261114.md) and [machine-readable results](PHASE67_LIVE_PILOT_RESULT_20261114.json). Initial readiness findings and pending-approval rows below are retained history, not the final state.

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

## Continued after explicit owner recovery approval

The initial attempt above is retained. The owner then approved stale-lease recovery and obtaining the free plans. Recovery succeeded using the normal `app --takeover --port 0` entry point in a hidden background process. **Resource-Library Core is running at http://127.0.0.1:64046, PID 21752**. The unrelated WebView PID was untouched. The Core is deliberately left running for the owner.

Both free **L0 checks PASS**. Both live L1 plans return `estimated_cost_usd: null` and `requires_spend_confirmation: true`; no paid qualification was dispatched. Current official [Gemma rates](https://deepinfra.com/google/gemma-4-26B-A4B-it) and [Qwen rates](https://deepinfra.com/pricing), combined with the source's requested 64-token proposal and 256-token continuation ceilings per role, give a planning estimate below $0.01 for the original pair, with $0.02 requested as an allowance rather than a quoted invoice. Provider retries/uncertain outcomes must be metered; no failed qualification run may be repeated or another model substituted silently.

A fresh managed **ToolSet-only database copy** was prepared at `D:/Librarian_V2/tmp/geo-grapher-qa-workspaces/pilot/20261114-six-task`. The actual installed 0.2.0 wheel returned all **six no-model candidate packets** within their token/7,500-character caps. This is a transport/candidate-anchor check, not a live lead-authored plan or a passing pilot. The tier-2 candidate packet explicitly reports **two upstream records omitted** at its 1,800-token profile ceiling; do not hide this limitation or infer full synthesis coverage.

Dedicated Core MCP entry **`geo_phase67_pilot_20261114`** was added for that approved wheel and scoped copy, exposing six `lead` tools. Existing server definitions, model bindings and global permission mode were left unchanged. L0 was repeated and passed after this tool-registry/fingerprint change. The Core connection is accepted/enabled/connected. A first discovery call at `consult` was correctly `TIER_REFUSED`. Retrying at `contribute` timed out at the client because the broker's newly seeded **Ask** permission awaited a person. The exact own pending request `ffe0f73e` was then denied/cancelled to prevent late execution; **no permission was granted or bypassed**. This is a remaining authorization gate, not an established transport defect. Full Core dispatch readiness has not passed.

Further read-only Core inspection identifies two additional requirements:

- The production lead **Seed-2.0-mini is `ineligible`**. An eligible lead must be selected by the owner, or the owner must explicitly accept the existing app's lead override for this pilot. No override or binding change has been made.
- The native tier-1 reviewer uses the **lead model**, while tier 2 uses the research-helper binding. `_helper_profile_guard` enforces the `research_helper` role on the route actually used. Therefore **Seed also needs separate research-helper qualification** for tier-1 review; qualifying Gemma and Qwen alone is insufficient. A lead override does not waive helper/Clerk qualification.

### Funding and policy approvals pending

The actual shared ledger has **$1.99373526 remaining**, including unresolved historical reservations, below the required **$2 reserve** by **$0.00626474**. No historical uncertainty was released or reclassified. The current ceiling is $14.24739611 and committed amount $12.25366085. **No new paid work is allowed until funding is restored.**

The earlier question about just two L1 runs is superseded by the complete prerequisites: requested **$0.50 pool top-up**, **up to $0.40 total qualification/pilot allowance**, an explicit eligible-lead/override decision (including the tier-1 helper-role probe), and permission for only the scoped pilot server's read tools. Stop if a bounded estimate does not fit the allowance/reserve; no benchmark cycle is included. These are requests, **not approvals or applied budget changes**.

`PHASE67_LIVE_PILOT_PREFLIGHT_20261114.json` records the exact free results, first attempts, current pool numbers and artifact hashes. **Paid calls 0; live tasks dispatched 0/6.** The QA copy remains active/protected for resumption. Product code and both model bindings/global permission policy remain unchanged; no tag or push. Pilot and F4 acceptance remain unvalidated.
