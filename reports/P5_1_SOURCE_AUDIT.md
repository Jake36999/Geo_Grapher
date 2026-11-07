# P5.1 — targeted source audit

6 November 2026. Inspected the pinned git archive at `f8bc1ec4c54884293dace635275e95c685b03371`, not the mutable working tree. This is a purposeful eight-case audit, not a statistical accuracy estimate. Machine-readable excerpts and source coordinates are retained in `output/phase5/source-audit-candidates.json`; complete source bytes remain in the published snapshots.

| Source and site | Inspected evidence | Assessment |
| :--- | :--- | :--- |
| `_quarantine/manifest_doctor.py:69`, `parse_args()` | Unique module definition at line 51; the module entry calls main after these declarations | Candidate → exact is justified under the declared static binding assumptions. An unrelated try block must not downgrade the earlier call. |
| `_quarantine/manifest_doctor.py:76`, `load_and_validate_manifest(...)` | The try body calls the unique module helper defined at line 64; that helper delegates to an imported library function | Candidate → exact applies to the local helper binding only, not the external delegated call or successful execution. |
| `code_intelligence/benchmark_abstraction.py:112`, `config.collection_name(repo)` | Source imports `from . import config`; `code_intelligence/config.py:189` defines `collection_name(slug: str)` | Unresolved → exact repairs the imported-module member branch. It is not an inference from identifier similarity. |
| `architecture_validator.py:338`, `self._add(...)` | `RuleEngine._add` is defined at line 306; the call is a receiver lookup inside the class | Unresolved → candidate is appropriate. The declaration is grounded, but Python receiver/override semantics prevent an unconditional exact dispatch claim. |
| `_quarantine/manifest_doctor.py:70`, `Path(...)` | Explicit `from pathlib import Path`; pathlib is not indexed in the selected repository roots | Retaining unresolved status with unindexed-import provenance is appropriate; it is not counted as a missed internal definition. |
| `_quarantine/manifest_doctor.py:71`, `manifest_path.exists()` | The receiver is a local value produced by the unindexed `Path` constructor | Retaining unresolved dynamic-attribute status avoids inventing points-to/type information. |
| `_quarantine/manifest_doctor.py:96`, `SystemExit(main())` | Standard builtin name in the module's main guard; no corresponding local definition in the inspected source | Retaining unresolved target status with a builtin-binding reason distinguishes it from a failed intra-repository import. |
| `tests/test_delegate.py:170`, `class TestAskJson(DelegateCase)` | `DelegateCase` is defined at line 44 and itself inherits unindexed `unittest.TestCase` | The direct internal base binding is exact; this does not establish a complete C3 MRO through the external base or exact inherited runtime dispatch. |

Paths above are relative to `aletheia_toolchain/`. Audited facts remain conditional on the supported static semantics and the pinned artifacts. None of these snippets was executed.

Async/suspension, import-root ambiguity, closure mutation, decorators, early module calls, exception cleanup and adversarial receiver/MRO cases additionally have independently authored positive/negative fixtures in `tests/test_phase5_resolver.py` and the existing Stage 1 suite. They are fixture evidence, not falsely represented here as manually reviewed real-repository examples.

The separate `scripts/phase5_oracle.py` labels 182 unique same-file module-function call sites using AST/symtable source under documented conservative exclusions, without consulting resolver statuses. It scores both stored baseline and new output. This provides a reproducible supported-subset comparison, while this audit checks examples and limitations directly. Neither establishes whole-Python completeness or whole-repository precision.
