# Phase 8 B0 — S3 full-conversion paper graph

2026-11-14. Native candidate `0b738f7`; Geo candidate `a8ab78c`. Neither merged or pushed. $0 spent. S2 and every prior result remain retained.

Native batches now project verified full conversions plus `dik.chapters()` into free, rebuildable paper-graph artifacts. Original and generated identities/hashes remain separate. Deep reads preserve anchored original page numbers; unanchored generated text uses a part locator, not an invented PDF page 1. New cleanup requests preserve explicit page markers. Old paid cleanup is reused without automatic reconversion. Missing/changed/unclassified originals, missing anchors and incomplete OCR produce explicit catalogue-only projections. Conversion coverage metadata is evidence-bound.

Geo imports verify local original/conversion SHA256 and complete ordered section/page coverage. Paper results retain page provenance and distinct generated/original representations. Source text remains unverified against original pages; this is not a claim-verification result. The standalone wrapper's S1 provenance overwrite was discovered during the cross-repository smoke, reproduced RED, and corrected to keep detailed provenance alongside authorship.

The note-only importer now emits catalogue-only entries, not apparent original-paper sections. Read model `paper-read-v5` keeps those references searchable and labels search cards `catalogue_only`; incomplete failed extractions remain quarantined. Existing v4 stores require a backed-up read-model refresh when deploying this candidate. No live paper binding was changed.

Real `06-Papers` candidate: 88 top-level Markdown files / 387,820 bytes, zero top-level PDFs; 86 eligible catalogue notes (index/control notes excluded). Free dry run: 86 converted / 0 failed. Candidate import: **86 documents, 0 sections, 0 claims**. First query exposed that the old read model quarantined all 86; retained as `s3-catalogue-query-first.json`. A separate v5 store then passed search and empty-outline checks, with explicit catalogue-only coverage. Both stores and all source notes remain. Total candidate build 845,526 bytes, inside the registered 8 MiB estimate; G: had over 117 GB free.

Evidence under `G:/Libraries/_qa/phase8-b0-20261114/evidence/`:

| Check | Retained rows |
|---|---|
| Native initial RED → GREEN | `s3-native-red.txt`: 4 failed; `s3-native-first-green.txt`: 13 passed including S2 |
| Producers RED | `s3-producers-red.txt`: 2 failed / 4 passed, one missing tool-registration fixture; corrected RED retained separately with the actual missing page-marker behavior |
| Producers GREEN | `s3-producers-green.txt`: 15 passed including S2 |
| Native legacy-cache regression | `s3-native-regression-first.txt`: 2 failed / 40 passed / 1 skipped; second: 42 passed / 1 skipped |
| Partial OCR / coverage integrity RED | `s3-partial-ocr-red.txt`: 1 failed / 7 passed; `s3-coverage-binding-red.txt`: 2 failed / 7 passed |
| Native broader final | `s3-native-broad-first.txt`: **118 passed / 1 skipped**, 39.22 s; paper graph/conversions, PDF/deep-read/OCR, DIK, Core batch/interruption/identity, intake, access declarations |
| Geo initial RED | `s3-geo-red.txt`: 3 failed |
| Geo intermediate GREEN | `s3-geo-first-green.txt`: 66 passed; second: 67 passed; third: 68 passed |
| Catalogue RED | `s3-catalogue-red.txt`, `s3-catalogue-visibility-red.txt`, `s3-catalogue-label-red.txt`: each exposes the named missing behavior; all retained |
| Standalone provenance RED | `s3-standalone-provenance-red.txt`: 1 failed / 5 passed |
| Geo final rows | `s3-geo-final-targeted.txt`: 69 passed; second: 1 failed / 69 passed (S1 test expected the provenance overwrite); third: **70 passed**, 4.12 s |
| Real candidates | `s3-catalogue-size-plan.json`, `s3-real-catalogue-dry-first.txt`, build/import-first logs, import-v5 log, query-first and query-v5 JSON |
| Cross-repo smoke | First shell invocation failed before import because its fixture glob used an untruncated pytest name (`AssertionError: []`). Second imported successfully but exposed the provenance overwrite (`TypeError: string indices must be integers, not 'str'`). Both tool outputs remain in this chat; `s3-cross-repo-third.json` records the corrected check: native artifact → Geo import → 2-section outline → full late text, pages 2–3, generated representation explicit, original verification false. Fixture PDF bytes are synthetic; this is not the S6 real-PDF demonstration. |

Authorship boundary counts remain native A **90/90**, B **12/12**, C **79 n/a**; Geo A **37/37**, B **3/3**; external adapter **1/1**. Full class-A access controls remain pending S4. Final full suites and the integrated person/agent demonstration belong to S6; these targeted checks do not replace them. Continue S4–S6b and R, then the owner merge stop.
