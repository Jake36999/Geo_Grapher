# Phase 8 Wave L — work in progress, 2026-11-14

Final status: completed the requested Wave L candidate and stopped at OWNER STOP L. See `PHASE8_WAVE_L_GATE_REPORT.md` for the final 802 Geo / 2,279 native passes, browser evidence, retained failures and the newer-roadmap scope boundary. This earlier progress record is retained without replacing its original rows.

Scope: Part B of the owner's library setup prompt. OWNER STOP L precedes all real-library setup. No Part C survey, ingestion, model call, binding, push or tag has been performed.

## Isolation and space

- Geo baseline: main `a6ad30f5bce11b3d2306b3091ea55eebf32c53f7`.
- Librarian baseline: master `fd070b1`.
- Worktrees: `G:/Libraries/_qa/phase8-wave-l-20261114/{geographer,librarian}`; branches `codex/phase8-wave-l-{geographer,librarian}`.
- Metadata-only checkout estimate: 14,577,721 + 23,870,898 bytes. Reserved allowance for tests/builds/caches: 4 GiB. Initial G free: 142,784,770,048 bytes, comfortably above 5 GiB after allowance. C/F are below 5 GiB; no bulk outputs go there.
- Claude's untracked setup prompt and parked native branch remain untouched.
- Evidence logs and disposable fixtures: `G:/Libraries/_qa/phase8-wave-l-20261114/{evidence,temp}`. Credential tests contain synthetic data only.

## First results — retained

| Check | First result | Follow-up |
|---|---|---|
| Geo credential RED | 4 failed | 22 passed including workspace-init regression tests |
| Librarian credential RED | 2 failed | 14 passed including deploy-survey regression tests |
| Geo inventory/suggestions RED | 4 failed | 4 new checks passed; 3 old assertions failed because PDF folders now have a separate paper partition; expectations updated |
| Librarian shared inventory RED | 1 failed, 1 passed (disabled) | 20 passed across shared-inventory, credential and existing survey tests, from neutral F:/uv-data |
| Geo third-party boundary RED | 5 failed | implementation under test |
| Librarian third-party RED | 2 failed | 18 passed, 1 failed: existing packet-failure test also broke preflight catalog; fixture updated to retain valid catalog and fail packet only |
| Geo third-party regression first GREEN attempt | 12 failed, 22 passed | missing tokenizer assets in isolated worktree; rerun uses existing read-only pinned tokenizer assets, not a network download |

Two early GREEN commands named nonexistent test modules; collection ran zero tests. Logs retained as `*-credentials-green.txt`; actual runs are `*-credentials-green-2.txt`. No result was replaced.

## Implementation decisions so far

- Refuse credential-like paths before content counting, extraction, ingestion or model dispatch. Report refused names only. Git ingestion lists paths/sizes, filters them, then fetches approved blobs; it no longer archives the whole commit first.
- `folder-inventory-v1` transfers path/size/mtime metadata and the shared native survey fingerprint through CLI stdin. Geo planning never performs a second directory walk. Partial/incomplete, escaping and wrong-root inventories are rejected. Same-size edits invalidate plans through mtime metadata.
- Third-party suggestions are human-review suggestions. Nested Git is conservatively labelled ownership-unconfirmed without reading remote URLs (which may embed credentials). Filename and licence-presence signals never determine ownership automatically.
- External research stays bronze and explicitly labelled. Normative contracts/v1.1 are not changed; provenance is carried by routing envelopes, agent projections and task packets.

Spend: $0. No paid work is approved or dispatched for Wave L. Full-suite counts, UI evidence and final commit hashes are pending; this is not an OWNER STOP L completion report.
