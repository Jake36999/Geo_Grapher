# Phase 6–7 Wave 2: Substrate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- give every snapshot the fingerprints that staleness, diffs and clone detection
  need;
- classify drift between snapshots;
- ingest Jupyter notebooks;
- onboard any folder with one command;
- diff or clone-match graphs without merging them, including container-cycle
  deltas.

**Architecture:**
- **Fingerprints:**
  - live in an additive supplementary table, `entity_fingerprints`, written with
    the snapshot facts before publish and protected by the immutability
    triggers;
  - `signature_hash` and `ts_guard_hash` are computed during extraction, where
    the AST is available;
  - span and out-edge hashes are computed in `prepare_analysis`, so merges get
    them too.
- **Drift:** a pure function over two fingerprint maps.
- **`init-workspace`:** produces a reviewable plan, then applies it through the
  existing `GraphCatalog.import_project`.
- **Cross-graph diff and clone matching:** read-only `ATTACH` joins.

**Tech Stack:** Python 3.11.3, SQLite 3.40.1, pytest. Librarian V2 for Task 4.

**Spec:** `docs/superpowers/plans/2026-11-11-phase6-7-00-master.md`. Its Part B
definitions G1, G2, G3, G12 and G13 are normative here. Background: the scoping
report's U1, U11 and U21.

## Global Constraints

The master plan's Global Constraints apply. In particular:
- `PRAGMA user_version` stays 1.
- `contracts/geographer.schema.sql` is byte-frozen.
- Supplementary DDL goes in `contracts/v1.1/FINGERPRINT_ADDENDUM.sql`.
- No fingerprint field appears on the wire.

Branch: `git switch -c phase67-wave2` (from the merged wave 1).

## Review Focus

1. **Old stores.** A store published before this wave has no
   `entity_fingerprints` rows, and on first open by new code has no table
   either. Drift must return `UNKNOWN`, never `HARD` (Task 2).
2. **Re-opening and concurrent opens.** The router and an ingest may open the
   same store. Applying the addendum must be idempotent, and an old store
   gains an empty table without its snapshots being treated as computed
   (Task 1).
3. **Unparseable or huge files.** Syntax errors, files with no defs, and classes
   without bodies must yield NULL fingerprints, not abort ingest (Task 1).
4. **Overlapping partitions in `init-workspace`:**
   - a `docs` folder nested inside a `legacy` folder;
   - a symlinked folder;
   - a workspace that is already a registered graph.
   
   The plan must be rejected or folded, never produce overlapping roots (Task 3).
5. **Diff across two graphs with colliding qualified names but unrelated
   code.** Different repos may both define `utils.load`. The pass-4 suffix match
   must not claim a contract drift unless the kind matches *and* the pair is
   unique in both graphs (Task 5).

---

### Task 1: `entity_fingerprints` table and computation (master G1, G2)

**Files:**
- Create: `contracts/v1.1/FINGERPRINT_ADDENDUM.sql`
- Create: `src/geographer/fingerprints.py`
- Modify:
  - `src/geographer/store.py`:
    - `__init__` (after the `user_version` check, before the trigger loop at
      `:46`): apply the addendum on writable connections, and add
      `entity_fingerprints` to the trigger tuple;
    - `write_graph` (`:114`): insert the rows;
    - `graph()` (`:333`): load them;
    - `merge()` (`:373`): carry them over.
  - `src/geographer/model.py` (`Graph`): add
    `fingerprints: dict[str, dict] = field(default_factory=dict)`.
  - `src/geographer/extract.py:234-246`: next to the `declaration-v1` analysis,
    store `self.graph.fingerprints[eid] = {'signature_hash': …, 'ts_guard_hash': …}`
    for function/method/class.
  - `src/geographer/analysis.py` (`prepare_analysis`): complete each entry with
    `span_sha256`, `exact_out_edges_hash`, and copies of `ast_body_hash` and
    `wl_3hop_hash`, after the WL-3 pass at `:416`.
- Test: `tests/test_fingerprints.py`

The addendum DDL:

```sql
-- Geo Grapher v1.1 fingerprint addendum; additive, user_version unchanged.
CREATE TABLE IF NOT EXISTS entity_fingerprints (
  snapshot_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  algorithm_version TEXT NOT NULL CHECK(algorithm_version='entity-fingerprint-v1'),
  span_sha256 TEXT, ast_body_hash TEXT, signature_hash TEXT,
  ts_guard_hash TEXT, exact_out_edges_hash TEXT, wl_3hop_hash TEXT,
  PRIMARY KEY(snapshot_id, entity_id),
  FOREIGN KEY(snapshot_id, entity_id) REFERENCES entities(snapshot_id, entity_id)
) STRICT;
CREATE INDEX IF NOT EXISTS fp_ast ON entity_fingerprints(snapshot_id, ast_body_hash) WHERE ast_body_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS fp_sig ON entity_fingerprints(snapshot_id, signature_hash, ts_guard_hash) WHERE signature_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS fp_wl ON entity_fingerprints(snapshot_id, wl_3hop_hash) WHERE wl_3hop_hash IS NOT NULL;
```

**Interfaces:**
- Produces:
  - `signature_hash(header: str, decorators: list[str]) -> str`;
  - `guard_clauses(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, local_names: set[str]) -> list[list]`;
  - `ts_guard_hash(clauses: list[list]) -> str`;
  - `span_sha256(raw: bytes, start_line: int, end_line: int) -> str`;
  - `exact_out_edges_hash(graph: Graph, entity_id: str) -> str`;
  - `SnapshotStore.fingerprints(sid: str) -> dict[str, dict] | None`, which
    returns **None** when the table is absent or holds 0 rows for that snapshot.
- Consumes: `normalize.ScopeIndex`, for the names bound in the entity's scope.

- [ ] **Step 1: Write the failing tests.**

```python
def fp(tmp_path, files):  # helper: ingest files at stage 3, return (store, sid, {qualname: fp})
    ...

def test_cosmetic_edit_keeps_signature_guard_and_ast(tmp_path):
    a = fp(tmp_path / "a", {"m.py": "def f(x):\n    # c1\n    if x > 1:\n        return g(x)\n\ndef g(y):\n    return y\n"})[2]
    b = fp(tmp_path / "b", {"m.py": "def f(x):\n    # c2 changed\n    if x > 1:\n        return g(x)\n\ndef g(y):\n    return y\n"})[2]
    for k in ("signature_hash", "ts_guard_hash", "ast_body_hash", "exact_out_edges_hash"):
        assert a["m.f"][k] == b["m.f"][k]
    assert a["m.f"]["span_sha256"] != b["m.f"]["span_sha256"]

def test_local_rename_keeps_guard_hash_but_guard_change_does_not(tmp_path):
    base = fp(tmp_path / "a", {"m.py": "def f(x):\n    if x > 1:\n        return x\n"})[2]["m.f"]
    renamed = fp(tmp_path / "b", {"m.py": "def f(z):\n    if z > 1:\n        return z\n"})[2]["m.f"]
    changed = fp(tmp_path / "c", {"m.py": "def f(x):\n    if x >= 1:\n        return x\n"})[2]["m.f"]
    assert base["ts_guard_hash"] == renamed["ts_guard_hash"] and base["ts_guard_hash"] != changed["ts_guard_hash"]
    assert base["signature_hash"] != renamed["signature_hash"]  # parameter name is part of the signature

def test_decorator_change_changes_signature(tmp_path):
    a = fp(tmp_path / "a", {"m.py": "def f():\n    pass\n"})[2]["m.f"]
    b = fp(tmp_path / "b", {"m.py": "import functools\n@functools.cache\ndef f():\n    pass\n"})[2]["m.f"]
    assert a["signature_hash"] != b["signature_hash"]

def test_unparseable_file_and_non_code_entities_get_no_crash(tmp_path):
    store, sid, fps = fp(tmp_path, {"bad.py": "def (:\n", "ok.py": "class C: pass\n", "README.md": "# t\n"})
    assert "ok.C" in fps and fps["ok.C"]["ast_body_hash"] is None

def test_fingerprints_are_immutable_after_publish(tmp_path):
    store, sid, _ = fp(tmp_path, {"m.py": "def f():\n    pass\n"})
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        store.connection.execute("DELETE FROM entity_fingerprints WHERE snapshot_id=?", (sid,))

def test_old_store_reports_not_computed(tmp_path):
    store, sid, _ = fp(tmp_path, {"m.py": "def f():\n    pass\n"})
    copy = tmp_path / "old.sqlite"; drop_table_copy(store, copy, "entity_fingerprints")
    reopened = SnapshotStore(copy)          # re-creates an empty addendum table
    assert reopened.fingerprints(sid) is None

def test_addendum_idempotent_on_reopen(tmp_path):
    store, sid, fps = fp(tmp_path, {"m.py": "def f():\n    pass\n"})
    path = Path(store.connection.execute("PRAGMA database_list").fetchone()[2])
    second = SnapshotStore(path)            # concurrent open while `store` is still open
    assert second.fingerprints(sid) == store.fingerprints(sid) and len(fps) == 1

def test_fingerprints_deterministic_across_processes(tmp_path):
    ...  # spawn `python -c` twice with PYTHONHASHSEED=1/2 ingesting the same fixture; compare canonical(fps)
```

  Implement the helper bodies and the last test in full:
  - `fp` uses `Repository.from_directory` + `pipeline.ingest(store, [repo], stage=3)`
    and maps `qualified_name → row`, with the repo prefix stripped.
  - `drop_table_copy` runs `sqlite3.Connection.backup` into the copy, then on
    the copy drops the `immutable_entity_fingerprints_*` triggers and the table.
  - The determinism test runs the `fp` ingest in two `python -c` subprocesses
    with `PYTHONHASHSEED` 1 and 2 and asserts that `canonical(fps)` is equal.
- [ ] **Step 2:** Run `pytest tests/test_fingerprints.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement per master G2.**
  - Guard clause kinds, mapped from AST nodes:

    | AST node | clause_kind |
    |---|---|
    | `If` | `if`, or `elif` when the source line starts with `elif` |
    | `While` | `while` |
    | `For` / `AsyncFor` (`iter`) | `for_iter` |
    | `Assert` | `assert` |
    | `match_case` (`guard`) | `match_case_guard` |
    | `IfExp` | `ifexp` |
    | `comprehension` (`ifs`) | `comp_if` |
    | `ExceptHandler` (`type`) | `except_type` |
    | `withitem` (`context_expr`) | `with_item` |

  - Walk pre-order, without descending into nested FunctionDef, AsyncFunctionDef,
    ClassDef or Lambda.
  - Apply the addendum with
    `executescript(read_text())` on every open; it is idempotent through
    `IF NOT EXISTS`.
  - `fingerprints(sid)` returns None when `SELECT count(*)` for the snapshot is 0.
- [ ] **Step 4:** Run the tests, then the full `pytest tests -q`. Expected: all
  pass. The baseline-digest test passes because the frozen DDL is unchanged.
- [ ] **Step 5: Commit:** `feat(store): entity fingerprints addendum (entity-fingerprint-v1)`.

---

### Task 2: Counterpart resolution and drift classifier (master G3)

**Files:**
- Create: `src/geographer/drift.py`
- Modify: `src/geographer/cli.py`: `drift-report --store-a P --snapshot-a S --store-b P --snapshot-b S --out FILE`
- Test: `tests/test_drift.py`

**Interfaces:**
- Produces:
  - `Tier = Literal['IDENTICAL','LINE_SHIFT','COSMETIC','BODY_REFACTOR','NEIGHBOUR_DRIFT','CONTRACT_CHANGE','MOVED','MISSING','UNKNOWN']`;
  - `Outcome = Literal['NOOP','REANCHOR','SUSPECT','HARD','UNKNOWN']`;
  - `Contract = Literal['STRICT_BYTE_SPAN','AST_ALPHA_INVARIANT','CONTROL_GUARD_INVARIANT','TOPOLOGICAL_WL3']`;
  - `resolve(base: dict[str, dict], new: dict[str, dict], base_entities: dict[str, Entity], new_entities: dict[str, Entity]) -> dict[str, tuple[str | None, str]]`,
    mapping a base ID to `(new ID or None, rule)`, where
    `rule ∈ {'same_id','same_qualname','unique_ast','none'}`;
  - `tier(fb: dict | None, fn: dict | None, start_b: int | None, start_n: int | None, moved: bool) -> Tier`;
  - `OUTCOME: dict[Tier, dict[Contract, Outcome]]`, the master G3 matrix
    verbatim;
  - `drift_report(store_a, sid_a, store_b, sid_b) -> dict`, with
    `{counts: {tier: n}, entities: [{entity_id, counterpart, rule, tier}]}`
    sorted by `entity_id`.

- [ ] **Step 1: Write the failing tests.** These cover every G3 row with
  two-snapshot fixtures built by the Task 1 `fp` helper.

```python
@pytest.mark.parametrize("edit,expected", [
    ("", "IDENTICAL"),
    ("insert_line_above", "LINE_SHIFT"),
    ("change_comment", "COSMETIC"),
    ("refactor_body_same_calls", "BODY_REFACTOR"),
    ("edit_callee_body_only", "NEIGHBOUR_DRIFT"),
    ("change_signature", "CONTRACT_CHANGE"),
    ("change_guard", "CONTRACT_CHANGE"),
    ("change_call_target", "CONTRACT_CHANGE"),
    ("rename_function_same_body", "MOVED"),
    ("delete_function", "MISSING"),
])
def test_tier_for_scripted_edit(tmp_path, edit, expected):
    assert drift_for(tmp_path, EDITS[edit])["m.f"] == expected

def test_outcome_matrix_is_master_g3():
    assert OUTCOME["NEIGHBOUR_DRIFT"] == {"STRICT_BYTE_SPAN": "NOOP", "AST_ALPHA_INVARIANT": "NOOP", "CONTROL_GUARD_INVARIANT": "NOOP", "TOPOLOGICAL_WL3": "SUSPECT"}
    assert OUTCOME["BODY_REFACTOR"]["CONTROL_GUARD_INVARIANT"] == "NOOP" and OUTCOME["BODY_REFACTOR"]["STRICT_BYTE_SPAN"] == "HARD"
    assert set(OUTCOME["UNKNOWN"].values()) == {"UNKNOWN"}

def test_drift_on_store_without_fingerprints_is_unknown_not_hard(tmp_path):
    report = drift_between_old_and_new(tmp_path)  # base store copy without the table
    assert set(report["counts"]) == {"UNKNOWN"}
```

  `EDITS` maps each name to `(before_source, after_source)` for `m.py`. Write the
  ten source pairs explicitly. In `edit_callee_body_only`, `f` calls `g` and only
  `g`'s body changes.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `tier` evaluates master G3's rows in order.
  - `resolve` builds `(repo_id, qualified_name, kind)` and
    `(repo_id, kind, ast_body_hash)` indexes, and uses the hash only when it is
    unique on both sides.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(drift): cross-snapshot identity and five-tier drift classifier`.

---

### Task 2A: Jupyter notebook extraction, stdlib `json` only (`ipynb-v1`)

**Files:**
- Create: `src/geographer/notebooks.py`
- Modify:
  - `src/geographer/source.py:17`: add `.ipynb` to `SUPPORTED`;
  - `src/geographer/extract.py:166-190`: dispatch on suffix. An `.ipynb` is
    converted with `notebooks.to_virtual_source`, and the virtual Python text
    goes through the normal Python path. Markdown cells become fragments of the
    file entity.
- Test: `tests/test_notebooks.py`

**Interfaces:**
- `to_virtual_source(raw: bytes, rel_path: str) -> NotebookSource`, where:

  ```python
  @dataclass(frozen=True)
  class NotebookSource:
      python_text: str                 # the virtual source the AST is parsed from
      cells: tuple[CellSpan, ...]      # every cell, in notebook order
      notebook_sha256: str             # sha256 of the raw .ipynb bytes
  @dataclass(frozen=True)
  class CellSpan:
      index: int; cell_type: Literal['code','markdown','raw']; start_line: int; end_line: int  # 1-based, in python_text
  ```

- **Virtual text construction:**
  - For each cell in order, emit a header line `# %% [cell <index>] <cell_type>`.
  - Then emit the cell's `source`. It is a list of strings or a single string;
    join a list with `''`. The text must end with `\n`.
  - In **code** cells, comment out lines whose first non-space character is `%`
    or `!` (IPython magics and shell escapes) by prefixing `# `.
  - Comment out **markdown** and **raw** cells entirely, so `python_text` stays
    valid Python whatever the markdown says.
  - Ignore `outputs` and `metadata`, so no execution output is ever ingested.
- **Entities:**
  - The file entity has kind `file`, language `python` and `rel_path` ending in
    `.ipynb`.
  - Functions and classes are extracted normally, with line numbers in
    `python_text`.
  - `source-bytes-v1` for the file stores `python_text` encoded as UTF-8, with
    extra result keys `coordinate_space: 'ipynb-python-v1'` and
    `notebook_sha256`. `get_entity_content` therefore returns exactly the text
    that line numbers refer to, so citations stay consistent.
  - Each markdown cell becomes one `fragment` of the file entity, via the
    existing `self.fragment(...)` with its virtual line span and role
    `documents`. It gets a `documentary-tree-v1` analysis from `parse_document`
    over the cell's own text, like docstrings (`extract.py:600-616`).
- **Errors:**
  - Invalid JSON, `nbformat < 4`, or no `cells` list → a parse failure
    `NotebookFormatError`, recorded like other parse failures.
  - A code cell that doesn't parse: comment out the whole cell in
    `python_text`, prefix its header with `# %% [cell N] code (unparsed)`, and
    record a soft failure. The rest of the notebook is still extracted.

- [ ] **Step 1: Write the failing tests.**

```python
NB = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [
    {"cell_type": "markdown", "metadata": {}, "source": ["# Solver\n", "Uses `step` to advance.\n"]},
    {"cell_type": "code", "metadata": {}, "execution_count": 1, "outputs": [{"output_type": "stream", "text": "SECRET OUTPUT"}],
     "source": ["%matplotlib inline\n", "import math\n", "def step(x):\n", "    return math.sqrt(x)\n"]},
    {"cell_type": "code", "metadata": {}, "execution_count": 2, "outputs": [], "source": "!pip install foo\nprint(step(4))\n"},
    {"cell_type": "code", "metadata": {}, "execution_count": 3, "outputs": [], "source": ["def broken(:\n"]}]}

def test_virtual_source_is_valid_python_and_comments_magics():
    src = to_virtual_source(json.dumps(NB).encode(), "nb.ipynb")
    ast.parse(src.python_text)
    assert "# %matplotlib inline" in src.python_text and "# !pip install foo" in src.python_text
    assert "SECRET OUTPUT" not in src.python_text and [c.cell_type for c in src.cells] == ["markdown", "code", "code", "code"]

def test_notebook_function_extracted_with_markdown_fragment(tmp_path):
    (tmp_path / "nb.ipynb").write_text(json.dumps(NB), encoding="utf-8")
    g = extract_repo(tmp_path)   # helper over Repository.from_directory + Extractor
    step = next(e for e in g.entities.values() if e.qualified_name.endswith("step"))
    assert step.rel_path == "nb.ipynb" and step.kind == "function"
    frags = [e for e in g.entities.values() if e.kind == "fragment" and e.rel_path == "nb.ipynb"]
    assert frags and any("Solver" in g.analyses["text:" + f.entity_id]["result"]["text"] for f in frags)

def test_unparsed_cell_is_soft_failure_and_rest_survives(tmp_path):
    (tmp_path / "nb.ipynb").write_text(json.dumps(NB), encoding="utf-8")
    g, failures = extract_repo(tmp_path, with_failures=True)
    assert any(e.qualified_name.endswith("step") for e in g.entities.values())
    assert any("unparsed" in json.dumps(f) or f.get("code") == "SyntaxError" for f in failures)

def test_invalid_notebook_is_parse_failure(tmp_path):
    (tmp_path / "bad.ipynb").write_text("{not json", encoding="utf-8")
    g, failures = extract_repo(tmp_path, with_failures=True)
    assert any(f.get("code") == "NotebookFormatError" for f in failures)

def test_entity_content_lines_match_virtual_source(service_for_notebook):
    svc, sid, step_id = service_for_notebook
    chunk = entity_content(svc, sid, step_id)["chunks"][0]
    assert chunk["text"].startswith("def step(x):")
```

  Write the helpers `extract_repo(path, with_failures=False)`,
  `service_for_notebook` and `entity_content` in the test file, following
  `tests/test_stage1_extraction.py` and `tests/test_stage3_service.py`.
- [ ] **Step 2:** Run `pytest tests/test_notebooks.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Fingerprints (Task 1) work unchanged, because spans are computed over the
    stored `python_text` bytes.
  - `workspace_init.scan` (Task 3) now counts `.ipynb` as supported code for
    the archetype rule.
- [ ] **Step 4:** Run the tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(extract): stdlib Jupyter notebook extraction (ipynb-v1)`.

---

### Task 3: `geographer init-workspace` (master G13, D2)

**Files:**
- Create: `src/geographer/workspace_init.py`
- Modify: `src/geographer/cli.py`: `init-workspace --root DIR --catalog PATH [--plan-out FILE|-] [--apply FILE] [--yes]`
- Test: `tests/test_workspace_init.py`

**Interfaces:**
- Produces:
  - `scan(root: Path) -> dict`, the plan: `{plan_version:'workspace-init-v1', root, archetype, partitions:[{key, subtrees:[rel], role, stratum:{role,trust_tier,modality}, file_counts:{suffix:n}, bytes, exclude_globs}], excluded:[{rel, reason}], unsupported_by_suffix:{suffix:n}, manual_steps:[{kind:'paper_corpus', dir, command}], plan_id}`;
  - `apply(catalog: GraphCatalog, plan: dict, *, approved_keys: set[str]) -> list[dict]`,
    returning one import report per partition.
- `plan_id = digest(plan without plan_id)`. `apply` rescans and refuses with
  `PLAN_STALE` if the `plan_id` differs.
- `--yes` approves every partition.
- Without `--apply` or `--yes`, the command writes the plan only. **It never
  ingests on a plain `init-workspace`.**

- [ ] **Step 1: Write the failing tests.** Fixture tree:
  - `src/a.py`
  - `docs/guide.md`
  - `legacy/old.py`
  - `legacy/docs/x.md` (nested: folds into `legacy`)
  - `node_modules/z.js`
  - `.venv/…`
  - `papers/p.pdf`
  - `README.md`

```python
def test_scan_proposes_disjoint_partitions_and_excludes_noise(tree):
    plan = scan(tree)
    keys = {p["key"]: p for p in plan["partitions"]}
    assert set(keys) == {"residual", "docs", "legacy"} and keys["legacy"]["stratum"]["trust_tier"] == "bronze"
    assert {"node_modules", ".venv"} <= {e["rel"] for e in plan["excluded"]}
    assert "legacy/docs" in keys["legacy"]["subtrees"][0] or keys["legacy"]["subtrees"] == ["legacy"]
    assert plan["manual_steps"][0]["kind"] == "paper_corpus" and "--dry-run" in plan["manual_steps"][0]["command"]
    subtrees = [s for p in plan["partitions"] if p["key"] != "residual" for s in p["subtrees"]]
    assert all(not a.startswith(b + "/") for a in subtrees for b in subtrees if a != b)

def test_plain_init_writes_plan_and_ingests_nothing(tree, tmp_path):
    run_cli(["init-workspace", "--root", str(tree), "--catalog", str(tmp_path / "c.sqlite"), "--plan-out", str(tmp_path / "p.json")])
    assert GraphCatalog(tmp_path / "c.sqlite").graphs() == []

def test_apply_creates_one_graph_per_partition_with_keep_separate(tree, tmp_path):
    catalog = GraphCatalog(tmp_path / "c.sqlite"); plan = scan(tree)
    reports = apply(catalog, plan, approved_keys={p["key"] for p in plan["partitions"]})
    assert len(catalog.graphs()) == 3
    residual = next(g for g in catalog.graphs() if Path(g["root_path"]) == tree.resolve())
    assert any("legacy" in glob for glob in json.loads(residual["profile_json"])["exclude_globs"])

def test_apply_refuses_stale_plan(tree, tmp_path):
    plan = scan(tree); (tree / "src" / "b.py").write_text("x=1\n")
    with pytest.raises(ValueError, match="^PLAN_STALE"):
        apply(GraphCatalog(tmp_path / "c.sqlite"), plan, approved_keys={"residual"})

def test_scan_handles_symlink_and_already_registered_root(tree, tmp_path):
    ...  # symlinked dir is listed in excluded with reason 'symlink'; scanning a root already in the catalog marks plan['existing_graph_id']
```

  Write the last test in full. Use `os.symlink` with `pytest.skip` when Windows
  denies it.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3: Implement per master G13.**
  - Make one `os.walk` with in-place pruning.
  - Partitions are top-level directories, plus nested directories whose role
    differs from their parent's. A nested directory whose parent is already a
    non-`current` partition folds into that parent.
  - `apply` imports partitions in key order:
    - each with `Repository.from_directory(subtree_root, label, exclude_globs=…)`;
    - the residual with `decision='keep_separate'`;
    - then `catalog.set_stratum(...)` from wave 1 Task 5.
- [ ] **Step 4:** Run the tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(onboarding): init-workspace plan/apply with disjoint partitions`.

---

### Task 4: Librarian deploy-survey hook (Librarian repo)

**Files (`D:/Librarian_V2`):**
- Modify: `src/resource_librarian/deploy_survey.py` (the survey result): add an
  optional `geo_grapher` section.
- Test: `tests/test_deploy_survey_geo_grapher.py`

**Interfaces:**
- The hook runs only when the environment variable `GEOGRAPHER_INIT` names an
  executable command (e.g. `uvx --from geo-grapher==0.1.2 geographer`).
- It runs `<cmd> init-workspace --root <root> --catalog <tmp> --plan-out -`:
  - read-only, with a timeout of 60 s;
  - the parsed plan goes under `survey["geo_grapher"] = {"plan": …, "command": …}`;
  - on failure: `{"error": "<code>", "detail": "<≤300 chars>"}`.
- It never applies a plan. It never writes into the surveyed folder; the temp
  catalog is under the Librarian's temp dir and deleted afterwards.

- [ ] **Step 1: Write the failing tests.**
  - A fake command (a Python script printing a fixed plan JSON) must produce
    `survey["geo_grapher"]["plan"]["plan_version"] == "workspace-init-v1"`.
  - An unset `GEOGRAPHER_INIT` produces no `geo_grapher` key.
  - A failing command yields an `error` entry and the rest of the survey is
    unchanged.
  - The surveyed folder's file listing is byte-identical before and after.
- [ ] **Step 2:** Run `D:/Librarian_V2/.venv/Scripts/python.exe -m pytest tests/test_deploy_survey_geo_grapher.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement with `subprocess.run(shlex.split(cmd, posix=False) + [...], capture_output=True, timeout=60)`.
- [ ] **Step 4:** Run the full Librarian suite. Expected: all pass (2,147 + new).
- [ ] **Step 5: Commit** in `D:/Librarian_V2` on branch `geo-grapher-survey`:
  `feat(deploy): optional Geo-Grapher partition preview in the survey`.

---

### Task 5: Cross-graph diff and clone matching (U11)

**Files:**
- Create: `src/geographer/cross_graph.py`
- Modify: `src/geographer/cli.py`: `diff-graphs --catalog C --graph-a ID --graph-b ID --out FILE` and `clone-report --catalog C --graph-ids ID,ID[,…] --out FILE`
- Test: `tests/test_cross_graph_diff.py`

**Interfaces:**
- Consumes: wave 1's `discovery.quotient_cycles(store, sid)`.
- Produces:
  - `diff_graphs(catalog: GraphCatalog, graph_a: str, graph_b: str) -> dict`,
    returning `{classes: {class: n}, pairs: [...], exclusive_a: [...], exclusive_b: [...], quotient_cycle_delta: {...}}`.
  - `quotient_cycle_delta(cycles_a: list[dict], cycles_b: list[dict]) -> dict`,
    returning
    `{entries: [{state, rel_paths_a, rel_paths_b, qcics_a, qcics_b}], counts: {state: n}}`:
    - match cycles across the two graphs greedily, in descending Jaccard of
      `member_rel_paths` (ties by sorted path tuple). A match needs
      Jaccard ≥ 0.5, and each cycle matches at most once;
    - state rules:

      | State | Condition |
      |---|---|
      | `CYCLE_DISSOLVED` | in A only |
      | `CYCLE_INTRODUCED` | in B only |
      | `COUPLING_REDUCED` | matched, with `qcics_b < 0.95·qcics_a` |
      | `COUPLING_INCREASED` | matched, with `qcics_b > 1.05·qcics_a` |
      | `INVARIANT` | matched, otherwise |

    - entries are sorted by `(state, rel_paths_a or rel_paths_b)`, and QCICS
      values are rounded to 6 places;
    - files are compared by `rel_path`, so this is meaningful across snapshots of
      one project or across graphs with comparable layouts. Unmatched cycles
      simply report dissolved or introduced.
    Classes are matched in passes, in order, each removing matched entities:
    1. `EXACT_AST_SURVIVOR`: equal `(kind, ast_body_hash)`.
    2. `CONTRACT_PRESERVING_REFACTOR`: equal `(kind, signature_hash, ts_guard_hash)`.
    3. `TOPOLOGICAL_ROLE_ANALOG`: equal `(kind, wl_3hop_hash)`.
    4. `SIGNATURE_OR_GUARD_DRIFT`: equal `(kind, last qualname segment)`.
    5. `STRATUM_EXCLUSIVE`: everything left.
    
    A pass matches only keys that occur **exactly once on each side**. Pairs are
    sorted by `(class order, entity_a, entity_b)`. Use hash buckets, O(|A|+|B|).
  - `clone_pairs(catalog: GraphCatalog, graph_ids: list[str], limit: int = 200) -> dict`,
    returning `{pairs: [{graph_a, entity_a, graph_b, entity_b, match: 'py-ast-v1'|'signature+guard'}], truncated: bool}`.
    - `ATTACH` each store `?mode=ro` as `g0…g7`, joining on each store's
      catalog-registered `snapshot_id`.
    - An `ast_body_hash` match outranks `signature+guard`.
    - Order by `(match, graph_a, entity_a, graph_b, entity_b)`.
- Either function refuses graphs whose snapshot has no fingerprints
  (`FINGERPRINTS_NOT_COMPUTED`) and names them.

- [ ] **Step 1: Write the failing tests.**

```python
def test_diff_classifies_all_five_classes(two_graph_catalog):
    catalog, a, b = two_graph_catalog  # fixture sources: identical h; body-changed-same-contract r; renamed k; same-name-diff-signature f; a-only x; b-only y
    d = diff_graphs(catalog, a, b)
    assert d["classes"] == {"EXACT_AST_SURVIVOR": 1, "CONTRACT_PRESERVING_REFACTOR": 1, "TOPOLOGICAL_ROLE_ANALOG": 1,
                            "SIGNATURE_OR_GUARD_DRIFT": 1, "STRATUM_EXCLUSIVE": 2}

def test_quotient_cycle_delta_states():
    A = [dict(member_rel_paths=["a.py", "b.py"], qcics=2.0), dict(member_rel_paths=["c.py", "d.py"], qcics=1.0),
         dict(member_rel_paths=["e.py", "f.py"], qcics=1.0), dict(member_rel_paths=["g.py", "h.py"], qcics=1.0)]
    B = [dict(member_rel_paths=["a.py", "b.py"], qcics=1.0), dict(member_rel_paths=["c.py", "d.py", "x.py"], qcics=1.5),
         dict(member_rel_paths=["e.py", "f.py"], qcics=1.02), dict(member_rel_paths=["y.py", "z.py"], qcics=0.7)]
    assert quotient_cycle_delta(A, B)["counts"] == {"COUPLING_REDUCED": 1, "COUPLING_INCREASED": 1, "INVARIANT": 1,
                                                     "CYCLE_DISSOLVED": 1, "CYCLE_INTRODUCED": 1}

def test_diff_reports_dissolved_ping_pong_cycle(two_snapshot_catalog_cycle_removed):
    catalog, a, b = two_snapshot_catalog_cycle_removed   # graph b = graph a with the b.py→a.py call moved into a.py
    assert diff_graphs(catalog, a, b)["quotient_cycle_delta"]["counts"] == {"CYCLE_DISSOLVED": 1}

def test_suffix_match_requires_uniqueness_on_both_sides(two_graph_catalog_with_duplicate_names):
    catalog, a, b = two_graph_catalog_with_duplicate_names  # two `load` functions in graph a
    assert diff_graphs(catalog, a, b)["classes"].get("SIGNATURE_OR_GUARD_DRIFT", 0) == 0

def test_clone_pairs_find_copy_pasted_function_across_three_graphs(three_graph_catalog):
    out = clone_pairs(*three_graph_catalog)
    assert {(p["match"]) for p in out["pairs"]} == {"py-ast-v1"} and len(out["pairs"]) == 3

def test_cross_graph_refuses_graph_without_fingerprints(two_graph_catalog_one_old):
    with pytest.raises(ValueError, match="^FINGERPRINTS_NOT_COMPUTED"):
        diff_graphs(*two_graph_catalog_one_old)

def test_diff_is_deterministic_under_argument_and_hashseed_order(two_graph_catalog):
    ...  # diff(a,b) pairs mirrored == diff(b,a); two subprocesses with different PYTHONHASHSEED give identical bytes
```

  Write the fixtures with explicit sources. Write the last test in full.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement as specified above.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(cross-graph): fingerprint diff and catalog clone join`.

---

### Task 6: Wave 2 gate

**Files:**
- Create: `reports/PHASE67_WAVE2_GATE.md`

- [ ] **Step 1: Re-ingest gate copies of ToolSet and librarian-v2** under
  `output/phase67-gates/wave2/` so they get fingerprints. Record:
  - ingest time compared with the previous snapshot build, to show the overhead
    of fingerprinting;
  - fingerprint row counts.
- [ ] **Step 2: Drift on a real edit.** In a scratch copy of the Geo-Grapher
  repo, apply 6 scripted edits to `src/geographer/labels.py`, one per G3 tier,
  re-ingest, and run `drift-report`. Expected: each edit lands in its tier, and
  everything else is `IDENTICAL`, `LINE_SHIFT` or `NEIGHBOUR_DRIFT`.
- [ ] **Step 3:** Run `init-workspace --plan-out -` on
  `D:/Librarian_V2`, `D:/Timeline-mapping` and `F:/uv-data/Geo_Grapher`, and
  paste the three plans' partition tables into the report. Expected: no
  overlapping roots, and noise excluded.
- [ ] **Step 4:** Run `clone-report` across ToolSet and librarian-v2 and record
  the top 10 pairs.
- [ ] **Step 5:** Run `./scripts/verify.ps1` and the full Librarian suite.
  Expected: exit 0 for both.
- [ ] **Step 6: Commit:** `docs: wave 2 gate report`.
