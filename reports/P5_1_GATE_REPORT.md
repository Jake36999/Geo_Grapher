# P5.1 — resolver recall and KG1 gate report

6 November 2026. Status: **P5.0 and P5.1 passed for the declared supported subset**. P5.2 has not been implemented. The v1.1 actor contract is drafted and schema-validated; production HTTP/MCP/UI continue to use the unchanged v1.0 wire format.

The pinned ToolSet revision remains `f8bc1ec4c54884293dace635275e95c685b03371`, selected-content digest `e50bcf9c66d7cbf4e2d0ef15b1274f3ba918197abaee87e508f7f1f0e365261e`. No source was executed and git worktree status was checked before/after ingestion. The final Stage 1 snapshot is `snapshot:5f15b49fd24dae036a6caaf761559d207e0e27b49458619a16bd2c0be6ef830c`, with zero parse failures and successful full publication validation. Final ingestion took 22.5511 seconds on this development host, versus 14.4292 seconds for the pre-change baseline; these are single observations, not a performance acceptance claim. Richer provenance adds extraction/storage work; source-byte/encoding/hash metadata is cached per artifact.

## Implemented changes

- Binding-specific certainty removes the blanket complex-flow downgrade. Fixed-point CFG joins, local rebinding, expression-level walrus effects and exception-name cleanup remain conservative. Callee loading precedes argument-side writes. Known early module calls propagate through named local helpers and downgrade references to declarations not yet initialized.
- Recursive imported-member traversal resolves modules, re-exports and nested class namespaces with cycle guards and export-before-submodule precedence. The package from-list case (`from . import submodule`) is handled explicitly. Assignment/deletion/setattr patches through module/member aliases invalidate affected exporters across files.
- Source-grounded directed inheritance facts and a supported C3 class/member index are published. Inconsistent/dynamic/unindexed MROs are disclosed. Receiver bindings follow the first method parameter rather than the spelling self/cls; class/instance dispatch stays candidate under open-world assumptions. Noncallable class slots mask inherited methods; final annotations and lack of subclasses are not promoted to exact proofs.
- `claim-details-v1` stores target-independent occurrence IDs, original source digests/byte spans, syntax, primary/secondary reasons, binding state, assumptions, alternatives and MRO provenance in evidence details. Python conclusions and tree-sitter syntax claims are distinct. Encoded/BOM/Unicode/CRLF round trips are tested; legacy snapshots remain unchanged.
- Prominent Exact / Internal exact + candidates / All uncertainty presets use one shared JSON definition. The internal preset advertises and enforces internal endpoints; other filter flags remain intact. The browser test verifies actual expanded requests and saved-view restoration.

## Same-denominator ToolSet comparison

| Measure | Before | After |
| :--- | ---: | ---: |
| Distinct Python call sites | 11,486 | 11,486 |
| Exact known-internal call sites | 1,221 | 1,770 |
| Candidate known-internal call sites | 366 | 410 |
| Unresolved call sites | 9,899 | 9,306 |
| Original call relationship rows, including alternatives | 11,501 | 11,501 |
| All relationship rows | 12,526 | 12,754 |
| All exact / candidate / unresolved relationship rows | 1,502 / 395 / 10,629 | 2,063 / 439 / 10,252 |
| Added inheritance rows | 0 | 228 (12 exact, 216 unresolved) |

The extra 228 rows are inheritance, not additional calls. There are 593 more known-internal call sites (549 exact, 44 candidate). Candidate alternatives remain 15 additional call rows over the site count. Unknown/non-indexed targets are not relabelled internal to inflate improvement. Primary cause distributions remain inspectable: unresolved dynamic receivers, builtins and unindexed packages explain much of the remaining graph; these counts are not all resolver defects.

## Independent evidence

The separate AST/symtable source oracle labels **182** same-file module-function calls under documented conservative exclusions. Baseline correct exact results: **76/182 (41.8%)**. New correct exact results: **177/182 (97.3%)**. No wrong-exact target was found in that labelled subset. These are positive supported-subset recall measurements, not whole-repository precision, whole-Python completeness or calibrated probabilities. Negative/unsupported cases have independent adversarial fixtures. See `scripts/phase5_oracle.py`, `output/phase5/independent-oracle.json` and the targeted eight-case source audit in `reports/P5_1_SOURCE_AUDIT.md`.

## Token-density evidence and scope

The served format deliberately remains v1.0 during P5.1. A matched request shape and identical pinned source, using separately published Stage 3 analysis snapshots, produced:

| Whole-envelope fixed response | Nodes | Relationships | o200k_base tokens | cl100k_base tokens |
| :--- | ---: | ---: | ---: | ---: |
| Pre-change v1.0 | 9 | 7 | 8122 | 8390 |
| P5.1 v1.0 | 10 | 7 | 8049 | 8313 |

The actual requests use o200k_base with an 8,192-token limit. cl100k_base counts above are re-counts of those fixed envelopes, not a claim that an o200k request guarantees an 8,192 cl100k limit. Adaptive pages select different items after classification changes and BPE-dependent identity costs, so these rows do **not** isolate a schema density gain. Both use Stage 3 analysis, avoiding a false saving from missing Stage 1-only WL metadata.

The separate fixed-envelope metadata ablation reduced 8,122 to 5,171 o200k tokens (36.3%) before adding useful descriptors/previews. The proposed 70% removable overhead, ~5x density and 60–90 tokens/item remain unproven goals. Actual v1.1 serializer/packing/round-trip comparisons belong to P5.2–P5.3; declarations alone do not realize those savings.

## Validation and remaining boundaries

**100 backend tests passed**, including the real pinned ingestion, all prior Stage 1–4 checks and P5.0/P5.1/KG1 fixtures. **27 browser tests passed**, including visibility selection/persistence and existing accessibility/evidence/state journeys. TypeScript type-checking, formatting and v1.1 declaration/schema validation passed. Modified generator output for v1.0 remains byte-identical. Both approved specifications and all four original normative contracts retain their baseline hashes. Recorded commands/logs: `output/phase5-pytest.log`, `output/phase5-browser.log`, `output/phase5-oracle.log`, `output/phase5-after.log`, `output/phase5-density-after.log`.

Remaining limitations include callback/cyclic module initialization beyond detected early named calls, points-to inference, arbitrary alias assignments, reflective/decorated/dynamic dispatch, unindexed external bases and full runtime behavior. Unsupported MRO is not silently reconstructed; receiver candidates are not exact runtime targets. Documentary/source trees, rich previews, actor alias serving, packing optimizations and runtime telemetry remain later scheduled work. C14 cold-expanded performance and outstanding human/assistive-technology/hardware/final-soak gates are not closed by this increment.

Reproduction uses the isolated MCP 1.30.0 environment: `output/wheel-env/Scripts/python.exe -m pytest -q` with `PYTHONPATH=src`; `npm run test:ui`; `node scripts/generate-contracts.cjs 1.1`; `output/wheel-env/Scripts/python.exe scripts/phase5_measure.py baseline` (verifies the preserved pre-change manifest/store); `scripts/phase5_oracle.py`; and `scripts/phase5_measure.py density-after`. Pre-change classifications are preserved artifacts, not regenerated by pretending the upgraded resolver is the old implementation.
