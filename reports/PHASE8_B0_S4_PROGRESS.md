# Phase 8 B0 — S4 foundation, not a completion gate

2026-11-14. Native checkpoint `48acb1b`, on the unmerged B0 feature branch.
No merge, push, tag, paid dispatch or model-binding change. S4 remains in progress;
this is not an owner stop and does not replace the planned S6 gate.

Implemented with RED-first evidence:

- Actual-route token allocation, separate visible/reasoning reserves, profile windows
  that can narrow rather than inflate the model window. Current request measurement is
  a conservative serialized UTF-8 byte bound, not an exact model-tokenizer count;
  receipts disclose this and a 256-token framing reserve. Four characters per token is
  planning guidance only. The historical external character-cap behavior is unchanged.
- Located conversion-page reads and original-PDF-page reads, 1–8 explicit targets,
  cached conversion integrity, no OCR/model per access, original hashes and honest
  `claim_verification: not_performed`. Reading pages is not scientific claim validation.
- Central raw-read refusal, scoped person checkpoints for tiers 1–2, binding to source
  bytes/pinned note, normalized arguments, actual model, tier and publication session.
  One consumption under concurrency; sessionless helpers use the parent handle without
  its conversation. Permission requests themselves do not taint. Actual third-party or
  unknown-source reads still protect canonical publication.
- Native page/raw readers also respect the existing per-call character cap, including
  JSON escaping, and disclose text omitted. Durable references require fresh permission
  in a fresh reader; per-call allocation receipts are excluded from source-byte identity.
- Person-started ingestion retains its internally bound batch/item capability, sending
  bounded chunks to the Clerk and retaining staging. This does not authorize an ordinary
  agent's whole-document shortcut.
- Clerk code dispatch sizes both input and expected output before a provider call. The
  task's 1,800 visible tokens bind even when the general profile allows 4,096. Output
  sizing is a planning estimate from packet counts, not a single-shot completion claim.

The full regression run also exposed two S3 DIK page defects: a chunk spanning an entire
middle chapter was not counted as overlapping it, and skipping a text-empty earlier page
renumbered later pages. Both have failing tests and fixes. Old paid/unmapped conversions
are retained without automatic reconversion.

Evidence is in `G:/Libraries/_qa/phase8-b0-20261114/evidence/`; every row/log remains:

| Check | Retained outcome |
|---|---|
| Initial route/raw boundary RED | `s4-budgets-red.txt`: 5 failed / 2 passed |
| Initial implementation | first-green: 3 failed / 4 passed (new typed codes needed registration); second-green: 7 passed |
| Bounded tools RED → GREEN | bounded-tools-red: 3 failed / 7 passed; first-green: 2 failed / 8 passed (fixture monkeypatch bound too early); second-green: 10 passed |
| One-off grants RED → GREEN | raw-grants-red: 10 passed / 3 fixture errors (missing new tool); first-green: 13 passed |
| Permission-only control | grant-control-red: 1 failed / 14 passed; route-wiring-red: 3 failed / 14 passed; route-wiring-first-green: 17 passed |
| Helper route / unknown originals | helper-and-unknown-red: 2 failed / 17 passed; first green: 1 failed / 18 passed (8k fixture could not fit helper prompt); adjusted 32k fixture run exposed a Windows lock-path race; grant-lock-green: 19 passed |
| Sessionless helper grant | helper-grant-red: 2 failed / 19 passed; first-green: 21 passed |
| Clerk output preflight | clerk-output-red: 2 failed / 21 passed; first-green: 23 passed |
| Direct deep-read shortcut | deep-read-red: 1 failed / 23 passed; later repaired |
| Character caps | page-character-cap-red: 1 failed / 24 passed; green: 25 passed; raw-character-cap-red: 1 failed / 25 passed; green: 26 passed |
| Broader first | broad-first: 1 failed / 176 passed (old cited-evidence test lacked a person grant); audited-grant-red reproduced missing permission-control harness classification; green: 1 passed / 31 deselected |
| Broader second | broad-second: 1 failed / 198 passed (scripted Clerk endpoint lacked declared route metadata) |
| **Full first** | **42 failed / 2,331 passed / 2 skipped / 5 deselected**, 533.68 s, `s4-full-native-first.txt`; preserved, not replaced |
| Approved ingestion | approved-ingestion-red: 1 failed / 26 passed; fixed the internally bound batch case |
| Failure-targeted first | 2 failed / 216 passed: file validation order and old cleanup fixture/page assumptions |
| Reference identity | reference-grants-first: 1 failed / 1 passed / 15 deselected; allocation metadata incorrectly belonged to durable bytes; fixed |
| DIK RED | dik-overlap-red: 1 failed / 9 passed; dik-pages-red: 2 failed / 9 passed |
| Repair second | 1 failed / 80 passed: fake cleaner invented repeated chapter headings and queued an unscripted relation task; fixture now preserves page markers and one actual heading |
| **Failure-targeted final** | **250 passed**, 47.32 s, `s4-full-failure-targeted-final.txt`; includes all affected modules and the new boundary/page tests. This is not a second full-suite pass. |

The older whole-read fixtures now explicitly identify person actions, or obtain a scoped
person grant; they are not silently relabelled as trusted third-party sources. The
agent revision-merge test strips the person marker from its model context. Source/batch
acceptance tests expect the S2 hidden conversion, with the original retained.

Read-only inspection of the actual persisted Resource-Library bindings is recorded in
`s4-resource-routes-first.json`:

| Persisted role | Model | Shipped catalogue window | Profile output / code-task visible |
|---|---|---:|---:|
| lead | ByteDance/Seed-2.0-mini | 256,000 | 4,096 |
| research_helper | google/gemma-4-26B-A4B-it | 262,144 | 4,096 |
| clerk | Qwen/Qwen3.5-397B-A17B | 262,144 | 4,096 / **1,800** |

These are persisted settings and shipped catalogue metadata, not evidence of the live
Core's current route, endpoint availability or fresh qualification. The prior pilot
reported Seed closed and used a scoped Gemma override; this work has not tested Seed
again or changed the binding. Model-card precedence/reconciliation remains S6b. The
actual current request and reviewed reasoning reserve determine each allocation; do not
substitute an assumed 1M lead window or a fixed guessed prompt. For the registered free
262,144-window / 10,000-prompt fixture with 1,800 visible + 1,024 reasoning reserve, a
400,000-token comparison clamps to **249,320 total / 124,660 per source**. That is a
fixture calculation, not a measured production-session allocation.

Authorship coverage after adding two content readers and one permission control: native
A **92/92 authorship**, B **12/12**, C **80 n/a** (184 declarations, audit problems zero
at the targeted checkpoint); Geo A **37/37**, B **3/3**; external adapter **1/1**. Full
class-A S4 access conformance is **not yet certified**.

Remaining S4: the runnable source-verification dispatch template built on the audited
evidence-to-claim macro, complete read-surface sweep, final full suite, Geo verify/preset
checks, and effective route reports from that free integrated path. Then continue S5,
S6/S6b and R and stop at the combined owner merge gate. Keep the live hub/store and all
old snapshots intact. S2/S3 reports remain separate.
