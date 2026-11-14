# Phase 8 B0 — S2 conversion storage

2026-11-14. Candidate worktrees on G:, Wave L and S1 retained. No merge, push, tag, paid conversion or model-binding change.

S2 implements persistent generated PDF/OCR conversions at `.librarian/conversions/<evidence-id>.md`, outside rebuildable derived state. Evidence binds conversion bytes, original SHA256, method and page count. Cache reuse verifies that binding before any provider call. Original-source evidence is distinct from generated conversion evidence. Tampering refuses without reprocessing.

Acceptance retains originals, copies only the original attachment into managed Sources files, and keeps the conversion hidden. Its fingerprint participates in the approval guard. Direct note-index upserts also exclude conversions. Existing source-promotion fixtures now use a migrated conversion and assert one original copy, hidden text and unchanged interruption/lease protections.

`scripts/migrate_conversions.py <exact-vault>` defaults to a free, read-only survey. `--apply` is an operator action for a quiet library: explicit catalogue/staging associations only, verified hidden replacement, SHA256/path manifest, reference update, both old files retained. Legacy page mapping remains unverified. No basename-based classification. Resource-Library's current native vault survey returned zero recorded legacy associations; no live migration was applied. This is not a claim that every historical external folder has been surveyed.

All first evidence is retained in `G:/Libraries/_qa/phase8-b0-20261114/evidence/`:

| Check | First/result rows |
|---|---|
| Initial storage preparation | `s2-preparation-red.txt`: 2 failed; `s2-first-green.txt`: 2 passed |
| Integrity and acceptance | `s2-integrity-staging-red.txt`: 2 failed / 3 passed; `s2-integrity-green.txt`: 5 passed |
| Migration | `s2-migration-red.txt`: 2 failed / 5 passed; `s2-migration-green.txt`: 7 passed |
| Byte-preserving migration and survey | `s2-survey-red.txt`: 2 failed / 6 passed; later green included below |
| Direct index exclusion | `s2-index-red.txt`: 1 failed / 8 passed; later green included below |
| First broader invocation | `s2-regression-first.txt`: no tests ran, nonexistent test_batch.py path; corrected invocation retained separately |
| Broader regression | `s2-regression-second.txt`: 45 failed / 58 passed / 1 skipped; legacy fixture/contract expectations and mixed line endings exposed |
| Updated regression | `s2-regression-third.txt`: 1 failed / 103 passed / 1 skipped; fixture helper depended on a record already quarantined |
| Access-review check | `s2-regression-fourth.txt`: 1 failed / 108 passed / 1 skipped; PDF/OCR implementation fingerprints required renewed review |
| Final targeted regression | `s2-regression-fifth.txt`: **130 passed / 1 skipped**, 48.63 s; storage, migration, OCR/PDF, guarded single/batch promotion, staging, access declarations and staging safety |
| Real survey | `s2-real-survey-first.json`: dry-run, zero references |

Authorship boundary coverage remains native A **90/90**, B **12/12**, C **79 n/a**; Geo A **37/37**, B **3/3**; external adapter **1/1**. These are S1 authorship results, not certification of S4 reading controls. Full class-A access completion remains pending S4. S1 full-suite counts and live-refresh evidence remain in their separate reports; no historical row is replaced.

Next: S3 full-conversion graph/page mapping, then S4–S6b and R. Missing original PDFs remain catalogue-only. S6 is the owner merge stop. All QA fixtures are on G:. Dependencies are reused via junctions, not guaranteed read-only by filesystem permissions. G: had 117.5 GB free and F: 13.77 GB before this small stage; no bulk source copies were made.
