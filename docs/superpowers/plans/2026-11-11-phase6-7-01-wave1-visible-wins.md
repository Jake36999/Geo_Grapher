# Phase 6–7 Wave 1: Visible Wins — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the viewer and agent answers visibly better with no new substrate:
- readable labels with content snippets and role badges;
- coloured directional edges, including doc→code threads;
- a "planets within planets" affinity layout, where radial depth means
  coreness and angle means affinity;
- a deterministic discovery card with Markdown export;
- provenance-calibrated federation;
- graph copy, delete and active-set controls.

**Architecture:**
- Labels and edge classes are computed server-side from existing snapshot facts
  and added to the v1.1 wire as optional fields. The frontend renders them.
- The discovery card is a pure function of the stored Stage 2/3 analyses.
- Federation selection and lifecycle operations are catalog/router code.

**Tech Stack:** Python 3.11.3, SQLite 3.40.1, tiktoken, Starlette; React + three.js; pytest; Playwright.

**Spec:** `docs/superpowers/plans/2026-11-11-phase6-7-00-master.md`. Its Part B
definitions G1, G8, G9, G10 (including `role-badge-v1`), G11, G12 and G14 are
normative here. Background:
`reports/PHASE_6_7_IMPLEMENTATION_SCOPING_20261111.md` (U3, U9, U16, U17, U22, U23a–c).

## Global Constraints

Everything in the master plan's Global Constraints applies. In particular:
- The frozen contract files stay byte-identical.
- Wire changes go only into `contracts/v1.1/geographer.wire.d.ts`, followed by
  `npm run contracts`.
- `NodeRecord` gains no hash or `entity_id` field.
- The `papers` and `code` presets stay at 6 tools.

Run Python tests with:

```
$env:PYTHONPATH='F:/uv-data/Geo_Grapher/src;F:/uv-data/Geo_Grapher'
output/wheel-env/Scripts/python.exe -m pytest <path> -q -p no:cacheprovider
```

Branch: `git switch -c phase67-wave1`.

## Review Focus

1. **Label edge cases:**
   - a Markdown fragment before the first heading;
   - an empty `#` heading;
   - two sibling sections with the same heading;
   - a `.txt` document with no headings;
   - a docstring fragment.
   
   Each gets a stable, non-empty label of ≤ 48 chars. Covered in Task 1.
2. **Unicode and very long headings.** Truncation must not split a surrogate
   pair or grapheme into invalid UTF-8, and must append `…`. Covered in Task 1.
3. **Delete while a request is in flight on Windows.** The store is unlinked only
   after the lease count reaches zero; the request still completes. Covered in
   Task 6.
4. **Delete of a graph other state depends on:**
   - a merge source;
   - the hub's primary graph;
   - a registered external store, which is unregistered but never unlinked.
   
   Covered in Task 6.
5. **Federation degenerate inputs:**
   - every graph errors;
   - one graph has zero hits;
   - the budget is smaller than every compact envelope.
   
   Covered in Task 5.

---

### Task 1: Display labels and role badges (`display-label-v1`, `role-badge-v1`, master G10)

**Files:**
- Create: `src/geographer/labels.py`, holding labels, snippets, the frozen
  `STOPWORDS` list and role badges.
- Modify: `src/geographer/extract.py:234-246`. Beside `declaration-v1`, add the
  analysis `role-inputs:<eid>` with
  `{decorators: [ast.unparse(d)…], bases: [ast.unparse(b)…]}` for every function,
  method and class.
- Modify: `frontend/src/Inspector.tsx`. When `role_badge` is set, show it as a
  tag (`[Entry]`, `[Core]`, `[IO]`, `[Schema]`, `[Gate]`, `[Util]`, `[Spec]`)
  beside the node title.
- Modify:
  - `src/geographer/service.py:142-162` (`_node`): add `display_label`;
  - `src/geographer/viewport.py:126+` (`build_frame`): sibling disambiguation;
  - `src/geographer/actor.py` (`ActorEncoder`, the v1.1 `NodeRecord`
    projection): pass `display_label` through. The 1.0 wire is untouched.
- Modify: `contracts/v1.1/geographer.wire.d.ts` (`NodeRecord`): add
  `display_label?: string | null;` and
  `role_badge?: 'Entry' | 'Schema' | 'Gate' | 'IO' | 'Core' | 'Util' | 'Spec' | null;`,
  then regenerate
  `contracts/v1.1/generated/geographer.wire.schema.json` with `npm run contracts`,
  setting `maxLength: 48` in the generator's override table if it has one,
  otherwise in the d.ts JSDoc tag the generator reads.
- Modify: `frontend/src/api.ts:405` (`shortName`): prefer `node.display_label`.
- Test: `tests/test_display_labels.py`

**Interfaces:**
- Produces:
  - `base_label(graph: Graph, entity_id: str) -> str` (≤ 48 chars);
  - `snippet(text: str, budget: int) -> str`: the first 4 content words (at
    least 3) that fit in `budget` chars;
  - `disambiguate(nodes: list[dict]) -> dict[str, str]`, keyed by node `id`;
    input dicts carry `id`, `kind`, `parent_id`, `qualified_name`,
    `source.rel_path`, `display_label` and, for fragments, the internal key
    `label_text` (the fragment's own text, read from `text:<fid>`);
  - `role_badge(graph: Graph, entity_id: str) -> str | None`, implementing
    G10 `role-badge-v1` in rule order;
  - `truncate_label(text: str, limit: int = 48) -> str`.
- `label_text` is internal. `ActorEncoder` must not emit it; a wire-schema
  validation test proves this.
- Consumes: the `text:<fid>` and `document:<doc_id>` analyses already in
  `graph.analyses`.

- [ ] **Step 1: Write the failing tests.**

```python
from geographer.labels import base_label, disambiguate, truncate_label

def test_markdown_fragment_uses_heading_path(extract_markdown):
    g, fid = extract_markdown("# Guide\n## Install\nRun it.\n", line=3)
    assert base_label(g, fid) == "Guide › Install"

def test_fragment_label_edge_cases(extract_markdown):
    g, fid = extract_markdown("Intro text\n# A\n", line=1)
    assert base_label(g, fid) == "README.md · intro"
    g, fid = extract_markdown("#\nbody\n", line=2)
    assert base_label(g, fid) == "README.md · intro"
    g, fid = extract_markdown("plain words\n", line=1, name="notes.txt")
    assert base_label(g, fid) == "notes.txt · intro"

def test_docstring_fragment_label(extract_python):
    g, fid = extract_python('def run():\n    """Do it."""\n', fragment_of="run")
    assert base_label(g, fid) == "run · docstring"

def test_truncation_is_left_trimmed_and_valid_utf8():
    long = " › ".join(["Überschrift-" + "x" * 10] * 6)
    out = truncate_label(long)
    assert len(out) <= 48 and out.startswith("…") and out.encode("utf-8")

def frag(i, line, text, label="Setup"):
    return dict(id=i, kind="fragment", parent_id="d", qualified_name=i, source=dict(rel_path="a.md", start_line=line),
                display_label=label, label_text=text)

def test_fragments_under_same_heading_get_content_snippets():
    nodes = [frag("f1", 3, "Install the **package** with pip and then configure it."),
             frag("f2", 9, "Then run the `migrate` command against your database.")]
    assert disambiguate(nodes) == {"f1": "Setup · Install package pip configure",
                                   "f2": "Setup · run migrate command database"}

def test_snippet_collision_falls_back_to_numbering():
    nodes = [frag("f1", 3, "Install package pip wheel."), frag("f2", 9, "Install package pip wheel.")]
    out = disambiguate(nodes)
    assert out["f1"] == "Setup · Install package pip wheel" and out["f2"] == "Setup · Install package pip wheel (2)"

def test_snippet_respects_48_chars_and_minimum_three_words():
    nodes = [frag("f1", 3, "Configuration orchestration parameterisation internationalisation", label="A fairly long heading label here"),
             frag("f2", 9, "Other words entirely different here", label="A fairly long heading label here")]
    out = disambiguate(nodes)
    assert all(len(v) <= 48 for v in out.values()) and all(len(v.split(" · ")[1].split()) >= 3 or v.endswith("…") for v in out.values())

@pytest.mark.parametrize("src,qual,badge", [
    ("def main():\n    pass\n", "m.main", "Entry"),
    ("import click\n@click.command()\ndef go():\n    pass\n", "m.go", "Entry"),
    ("from pydantic import BaseModel\nclass Cfg(BaseModel):\n    x: int = 1\n", "m.Cfg", "Schema"),
    ("from dataclasses import dataclass\n@dataclass\nclass P:\n    x: int\n", "m.P", "Schema"),
    ("def validate_input(x):\n    return x\n", "m.validate_input", "Gate"),
    ("def load_config(p):\n    return open(p).read()\n", "m.load_config", "IO"),
    ("def _h(x):\n    return x\n", "m._h", "Util"),
])
def test_role_badges(extract_module, src, qual, badge):
    g, eid = extract_module(src, qual)
    assert role_badge(g, eid) == badge

def test_core_badge_from_in_degree(extract_module):
    src = "def core(x):\n    return x\n" + "".join(f"def c{i}():\n    return core({i})\n" for i in range(3))
    g, eid = extract_module(src, "m.core")
    assert role_badge(g, eid) == "Core"

def test_spec_badge_and_none(extract_markdown, extract_module):
    g, fid = extract_markdown("# Design\nText.\n", line=2, name="docs/DESIGN_SPECIFICATION.md")
    assert role_badge(g, fid) == "Spec"
    g, eid = extract_module("def plain(x):\n    return x + 1\n", "m.plain")
    assert role_badge(g, eid) is None

def test_duplicate_main_gets_minimal_ancestor_prefix():
    nodes = [dict(id="m1", kind="function", parent_id="p", qualified_name="pkg.cli.main", source=dict(rel_path="pkg/cli.py", start_line=1), display_label="main"),
             dict(id="m2", kind="function", parent_id="p", qualified_name="pkg.worker.main", source=dict(rel_path="pkg/worker.py", start_line=1), display_label="main")]
    assert disambiguate(nodes) == {"m1": "cli::main", "m2": "worker::main"}
```

Add these fixtures to `tests/conftest.py`, each built from a `tmp_path` repo via
the existing `extract` fixture:
- `extract_markdown(text, line, name='README.md') -> (Graph, fragment_id)`:
  selects the fragment whose `start_line == line`; `name` may include
  directories;
- `extract_python(src, fragment_of) -> (Graph, fragment_id)`;
- `extract_module(src, qualname) -> (Graph, entity_id)`: writes `m.py`, runs
  `prepare_analysis` (stage 2) so degrees exist, and returns the entity whose
  `qualified_name` ends with `qualname`.

- [ ] **Step 2:** Run `pytest tests/test_display_labels.py -q`. Expected: FAIL
  with `ModuleNotFoundError: geographer.labels`.
- [ ] **Step 3: Implement `labels.py` per master G10.**
  - The heading chain walks `parent_section_id` up to the root section and
    reverses it.
  - `truncate_label` trims whole path segments from the left first, then
    characters, prefixing `…`.
  - Colliding fragment siblings get `"<label> · <snippet>"` per G10. The snippet
    budget is `48 − len(label) − 3`. If that leaves room for fewer than 3 words,
    truncate the label part first with `truncate_label`.
  - Residual collisions are numbered by `(source.start_line, id)`.
  - `STOPWORDS` is a frozen tuple of 120 common English function words, matched
    case-insensitively. Content words must never be added to it: `package`,
    `pip`, `wheel`, `install`, `run`, `migrate`, `command`, `database` and
    `configure` must stay content words. Include at least: `a an the and or but
    if then else when with without against of to in on at
    by for from as is are was were be been being it its this that these those
    you your we our they their he she his her not no can will would should could
    may might must do does did done have has had into onto over under than so
    such via per using use used`.
  - The minimal distinguishing ancestor uses `rel_path` without its extension,
    split on `/`. Take the shortest suffix length `k ≥ 1` that makes all
    colliding labels unique, formatted `"::".join(suffix) + "::" + name`. If no
    `k` works, append `" (n)"`.
- [ ] **Step 4: Wire it in.**
  - `_node` sets `display_label=base_label(ctx['g'], eid)`,
    `role_badge=role_badge(ctx['g'], eid)` and, for fragments, `label_text` for
    entities; groups get the synthetic name with `role_badge=None`.
  - Cache badges per snapshot in `ctx`, because degree counting is per entity.
  - `build_frame` calls `disambiguate` on `data['nodes']` just before packing
    and overwrites `display_label`.
  - `shortName` returns `node.display_label` when it is a non-empty string.
- [ ] **Step 5: Add contract tests** to `tests/test_display_labels.py`:
  - `test_wire_schema_has_optional_display_label_and_role_badge`:
    `display_label` and `role_badge` are both in
    `schema['$defs']['NodeRecord']['properties']`, neither is in `required`,
    `display_label` has `maxLength == 48`, and `role_badge` has the 7-value enum
    plus null;
  - `test_label_text_never_on_wire`: a v1.1 `viewport_frame` response validates
    against `svc.wire11`, and no node has `label_text`.
- [ ] **Step 6:** Run `pytest tests/test_display_labels.py tests/test_phase5_contracts.py tests/test_stage4_geometry.py -q`,
  then `npm run typecheck`. Expected: all pass.
- [ ] **Step 7: Commit:** `feat(labels): display labels with content snippets and role badges`.

---

### Task 2: Documentary links layer in `viewport_frame` (master G9)

**Files:**
- Modify: `src/geographer/viewport.py` (`build_frame`, after the curve candidate loop at `:215-244`)
- Modify: `contracts/v1.1/geographer.wire.d.ts` (`ViewportFrameData`): add the optional field below, then run `npm run contracts`
- Test: `tests/test_documentary_links.py`

```ts
documentary_links?: {
  link_id: Id; fragment_rep: Id; entity_rep: Id;
  role: 'discusses' | 'documents' | 'rationale_for' | 'cites';
  incidence_count: number; control_points: Vec3[]; degree: 1 | 2 | 3; knots: number[];
}[];
```

**Interfaces:**
- Produces: `documentary_links(service, sid, part, tree, centres, visible: set[str], budget: int) -> list[dict]`
  in `viewport.py`.
- `link_id = 'doclink:' + digest(fragment_rep, entity_rep, role)[:24]`.
- Ordering: by `(-incidence_count, link_id)`.
- Budget: `min(200, curve_budget)`.

- [ ] **Step 1: Write the failing tests.** Use a fixture repo with `README.md`
  containing ``Use `run` here.`` and `app.py` defining `run`.

  Add the fixture `frame_for(grouping: dict, curve_budget: int = 200) -> dict` to
  `tests/conftest.py`:
  - ingest that repo at stage 3 into a `tmp_path` `SnapshotStore`;
  - build a `QueryService`;
  - issue `viewport_frame` with `viewport_request(sid, root_id)` from
    `tests/test_stage4_geometry.py:44`, changed to `schema_version='1.1'`, with
    the given `grouping` and `curve_budget`;
  - return `result['data']`.

  Move `viewport_request` into `conftest.py` so both files share it.

```python
def test_frame_emits_documentary_link_between_doc_and_code(frame_for):
    data = frame_for(grouping={"mode": "kind", "kind": "file"})
    links = data["documentary_links"]
    assert any(l["role"] in {"documents", "discusses"} for l in links)
    ids = {n["id"] for n in data["nodes"]}
    assert all(l["fragment_rep"] in ids and l["entity_rep"] in ids for l in links)  # endpoint closure

def test_documentary_links_are_deterministic_and_budgeted(frame_for):
    a = frame_for(grouping={"mode": "atomic"}, curve_budget=1)
    b = frame_for(grouping={"mode": "atomic"}, curve_budget=1)
    assert a["documentary_links"] == b["documentary_links"] and len(a["documentary_links"]) <= 1
```

- [ ] **Step 2:** Run the tests. Expected: FAIL with `KeyError: 'documentary_links'`.
- [ ] **Step 3: Implement.**
  - Read `documentary_incidences` for the snapshot.
  - Map each `fragment_id` and `entity_id` to its nearest visible
    ancestor-or-self with `tree.ancestors(...)` ∩ `visible`.
  - Drop pairs that map to the same rep, and aggregate the rest by
    `(fragment_rep, entity_rep, role)`.
  - Build control points with the existing `control_polygon` and `knots_for`.
  - Admit each link as a packer `Unit('doclink:'+link_id, 2, 60, records)`,
    whose records carry the two endpoint nodes and spheres, so closure holds.
- [ ] **Step 4:** Run the tests plus `tests/test_stage4_geometry.py tests/test_phase5_contracts.py`. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(viewport): documentary links layer for doc→code threads`.

---

### Task 3: Edge classification on curves (`edge-chromatics-v1`, master G9)

**Files:**
- Create: `src/geographer/edge_classes.py`
- Modify:
  - `src/geographer/viewport.py`: set `relationship_family` and `runtime_status`
    on each curve dict;
  - `src/geographer/graph_composition.py`: bridge-layer curves get
    `relationship_family='catalog_bridge'`.
- Modify: `contracts/v1.1/geographer.wire.d.ts`: add optional
  `relationship_family?` and `runtime_status?` to the `curves[]` items, as string
  unions of the G9 values; then run `npm run contracts`.
- Test: `tests/test_edge_classes.py`

**Interfaces:**
- Produces:
  - `classify_relationship(family: str, subtype: str, resolution_status: str) -> tuple[str, str]`,
    returning `(relationship_family, runtime_status)`;
  - `classify_documentary(role: str) -> str`.
- The `violation` family is applied client-side from the existing `violations`
  prop. The backend never emits it.

- [ ] **Step 1: Write the failing tests.**

```python
from geographer.edge_classes import classify_relationship, classify_documentary
import pytest

@pytest.mark.parametrize("args,expected", [
    (("static", "calls", "exact"), ("call_or_data", "exact")),
    (("static", "calls", "candidate"), ("call_or_data", "candidate")),
    (("static", "imports", "exact"), ("hierarchy", "exact")),
    (("static", "inherits", "unresolved"), ("hierarchy", "candidate")),
    (("runtime", "calls", "observed"), ("call_or_data", "observed")),
    (("expected", "calls", "declared"), ("call_or_data", "expected_only")),
])
def test_classify_relationship(args, expected):
    assert classify_relationship(*args) == expected

def test_classify_documentary_roles():
    assert [classify_documentary(r) for r in ("rationale_for", "documents", "discusses", "cites")] == \
           ["doc_rationale", "doc_describes", "doc_describes", "doc_cites"]

def test_frame_curves_carry_classes(frame_for):
    curves = frame_for(grouping={"mode": "atomic"})["curves"]
    assert curves and all(c["relationship_family"] in {"call_or_data", "hierarchy"} and c["runtime_status"] for c in curves)
```

- [ ] **Step 2:** Run the tests. Expected: FAIL (module missing).
- [ ] **Step 3: Implement the G9 table.** In `build_frame`, classify from the
  quotient projection row's `family`, `subtype` and `resolution_status`.
  Documentary links (Task 2) get `relationship_family` from
  `classify_documentary` and `runtime_status='exact'`.
- [ ] **Step 4:** Run the tests plus `tests/test_phase5_contracts.py`. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(edges): backend relationship family and runtime status`.

---

### Task 3A: "Planets within planets" affinity layout (`sphere-affinity-v1`, master G14; U17)

**Files:**
- Modify: `src/geographer/geometry.py`:
  - add `pack_siblings_affinity`;
  - `pack_tree` gains an optional `affinity` argument;
  - `pack_siblings` itself is unchanged.
- Modify: `src/geographer/viewport.py`:
  - `:180`: when `q['layout_version'] == 'sphere-affinity-v1'`, build
    affinity/external maps from the frame's quotient projections and documentary
    links, and pass them to `pack_tree`;
  - `:200`: echo the requested `layout_version`.
- Modify: `contracts/v1.1/geographer.wire.d.ts`: `ViewportFrameRequest` and
  `ViewportFrameData` gain
  `layout_version: 'sphere-pack-v1' | 'sphere-affinity-v1'`. Then run
  `npm run contracts`.
- Modify: `src/geographer/graph_composition.py:65`: request `sphere-affinity-v1`.
- Test: `tests/test_affinity_layout.py`

**Interfaces:**
- Produces:
  - `pack_siblings_affinity(ids: list[str], radii: list[float], count: int, seed: str, affinity: dict[tuple[str, str], float], external: dict[str, float], *, preferred_radius: float | None = None, steps: int = 40) -> tuple[list[Vec3], float, bool, float]`,
    which returns the same tuple as `pack_siblings`
    (`centres, radius, used_fallback, max_violation`); `affinity` keys are
    sorted pairs `(a, b)` with `a < b`;
  - `pack_tree(children, root, counts, seed, aggregate=(), preferred_radii=None, affinity: dict[str, tuple[dict, dict]] | None = None) -> Packing`,
    where the `affinity` value for parent `p` is `(pair_weights, external_degree)`.
    When it is None, `pack_tree` behaves exactly as today.
  - `layout_bands(ids, affinity, external) -> dict[str, tuple[str, float]]`,
    returning `id → (band, r_norm)`. It is shared by the solver and the tests.
- Pure Python `math` only: no numpy, no `random`.

- [ ] **Step 1: Write the failing tests.**

```python
from geographer.geometry import pack_siblings_affinity, layout_bands, violations, pack_siblings, unit, dot

IDS = [f"n{i}" for i in range(9)]
RADII = [0.4] * 9
# hub n0 coupled to n1..n4; pair n5–n6 coupled; n7, n8 isolated (n8 has external calls)
AFF = {("n0", f"n{i}"): 3.0 for i in range(1, 5)} | {("n5", "n6"): 2.0}
EXT = {"n8": 4.0, "n0": 2.0}

def test_bands_follow_master_g14():
    b = layout_bands(IDS, AFF, EXT)
    assert b["n0"][0] == "core" and 0.05 <= b["n0"][1] <= 0.42
    assert b["n5"][0] == "mantle" and 0.42 <= b["n5"][1] <= 0.72
    assert b["n7"] == ("crust", 0.95) and b["n8"][0] == "crust" and 0.72 <= b["n8"][1] < 0.95

def test_no_overlap_and_containment():
    centres, radius, fallback, err = pack_siblings_affinity(IDS, RADII, 9, "s", AFF, EXT)
    assert violations(centres, RADII, radius) <= 1e-4

def test_radial_order_core_mantle_crust():
    centres, radius, *_ = pack_siblings_affinity(IDS, RADII, 9, "s", AFF, EXT)
    r = {i: math.sqrt(dot(c, c)) / radius for i, c in zip(IDS, centres)}
    assert r["n0"] < min(r["n5"], r["n6"]) and max(r["n5"], r["n6"]) < min(r["n7"], r["n8"])

def test_affine_pairs_cluster_by_angle():
    centres, *_ = pack_siblings_affinity(IDS, RADII, 9, "s", AFF, EXT)
    d = {i: unit(c) for i, c in zip(IDS, centres)}
    affine = [dot(d[a], d[b]) for (a, b) in AFF]
    zero = [dot(d[a], d[b]) for a in IDS for b in IDS if a < b and (a, b) not in AFF]
    assert sum(affine) / len(affine) > sum(zero) / len(zero)

def test_input_order_invariant_and_deterministic():
    a = pack_siblings_affinity(IDS, RADII, 9, "s", AFF, EXT)
    perm = list(reversed(IDS))
    b = pack_siblings_affinity(perm, [0.4] * 9, 9, "s", AFF, EXT)
    assert dict(zip(IDS, a[0])) == dict(zip(perm, b[0]))

def test_no_affinity_degenerates_to_valid_layout():
    centres, radius, fallback, err = pack_siblings_affinity(IDS, RADII, 9, "s", {}, {})
    assert violations(centres, RADII, radius) <= 1e-4 and all(layout_bands(IDS, {}, {})[i] == ("crust", 0.95) for i in IDS)

def test_large_sibling_count_skips_relaxation_but_stays_valid():
    ids = [f"m{i:03d}" for i in range(400)]
    centres, radius, *_ = pack_siblings_affinity(ids, [0.2] * 400, 400, "s", {}, {})
    assert violations(centres, [0.2] * 400, radius) <= 1e-4

def test_old_layout_version_unchanged(frame_for):
    old = frame_for(grouping={"mode": "atomic"})                  # requests sphere-pack-v1
    assert old["layout_version"] == "sphere-pack-v1"
    new = frame_for(grouping={"mode": "atomic"}, layout_version="sphere-affinity-v1")
    assert new["layout_version"] == "sphere-affinity-v1" and new["spheres"] != old["spheres"]
```

  Extend the `frame_for` fixture (Task 2) with a `layout_version` keyword that
  defaults to `'sphere-pack-v1'`. Existing tests in
  `tests/test_stage4_geometry.py` must pass unchanged.
- [ ] **Step 2:** Run `pytest tests/test_affinity_layout.py -q`. Expected: FAIL (`ImportError`).
- [ ] **Step 3: Implement exactly per master G14.**
  - Compute `R_P` with the same expression `pack_siblings` uses
    (`geometry.py:115`).
  - Seed with the golden spiral over IDs sorted by `(−ĉ, id)`; the phase comes
    from `digest(seed, sorted_ids)`.
  - Run the 40 Jacobi tangent steps.
  - Run the existing sweep loop with the mobility-weighted shift split, then the
    containment clamp. Fall back to `compact_fallback` exactly as
    `pack_siblings` does.
  - Sort IDs internally and map outputs back to the caller's order.
  - Round centres with `round(x, 9)`.
  - In `viewport.py`, compute pair weights for siblings under the same display
    parent. Use quotient projections whose `source_rep_id` and `target_rep_id`
    are both children of that parent (`witness_count`), plus documentary links
    (Task 2) between them (`incidence_count`). External degree is the
    projections from a child to any rep outside the parent's display subtree.
- [ ] **Step 4:** Run `pytest tests/test_affinity_layout.py tests/test_stage4_geometry.py tests/test_phase5_contracts.py -q`. Expected: PASS.
- [ ] **Step 5:** Run a latency check on the ToolSet gate copy. A cold
  file-view and atomic `viewport_frame` with `sphere-affinity-v1` must stay
  within C14 (≤ 3.0 s). Add it as `@pytest.mark.integration`
  `test_affinity_layout_latency_toolset`, skipped if the store is absent.
- [ ] **Step 6: Commit:** `feat(layout): sphere-affinity-v1 radial coreness and tangential affinity layout`.

---

### Task 4: Frontend edge rendering (palette, direction gradient, dashes, legend)

**Files:**
- Create:
  - `frontend/src/edgeStyle.ts`: palette, OkLab mix, WCAG contrast, alpha and
    dash laws;
  - `frontend/src/edgeStyle.test.ts`: run through the Playwright config, or a
    plain `node --test` on the compiled file. Use whichever runner
    `package.json` gains in this task, and add the script `test:unit`.
- Modify:
  - `frontend/src/Scene.tsx:189-210, 460-505`: replace the grey `THREE.Color`
    choice with `edgeStyle`; switch `lineMaterial` to a `ShaderMaterial` on
    the same `LineSegments`;
  - `frontend/src/App.tsx:1817-1832`: legend.
- Test: `tests/browser-graphs/edge-chromatics.spec.cjs`

**Interfaces:**
- Produces:
  - `familyStops(family: RelationshipFamily, theme: 'dark'|'light'): [string, string]`;
  - `colourAt(family, theme, t: number): [r: number, g: number, b: number]`;
  - `alphaAt(t: number): number`, defined as `0.95 - 0.60*t`;
  - `dashFor(status: RuntimeStatus): { dash: number; gap: number } | null`;
  - `contrastRatio(hexA: string, hexB: string): number`.
- Shader attributes per vertex:
  - `position`;
  - `color` (from `colourAt`);
  - `aT`, the curve parameter t ∈ [0,1];
  - `aDist`, the cumulative world length;
  - `aStatus`: 0 exact, 1 candidate, 2 expected_only, 3 observed.
- Uniforms: `uTime` (seconds, advanced each animation frame), `uDimOthers`
  (0 or 1), `uHover`.

- [ ] **Step 1: Write the failing unit tests.**

```ts
import { familyStops, alphaAt, contrastRatio, dashFor } from "./edgeStyle";
const families = ["call_or_data","hierarchy","doc_rationale","doc_describes","doc_cites","catalog_bridge","violation"] as const;
for (const theme of ["dark","light"] as const) for (const f of families) {
  const [a, b] = familyStops(f, theme);
  const bg = theme === "dark" ? "#17191C" : "#F3F2EF";
  assert(contrastRatio(a, bg) >= 4.5 && contrastRatio(b, bg) >= 4.5, `${f}/${theme}`);
}
assert(alphaAt(0) === 0.95 && Math.abs(alphaAt(1) - 0.35) < 1e-9 && alphaAt(0.3) > alphaAt(0.7));
assert(dashFor("exact") === null && dashFor("candidate")!.dash === 0.30 && dashFor("expected_only")!.dash === 0.06);
```

- [ ] **Step 2:** Run `npm run test:unit`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement `edgeStyle.ts`.**
  - The dark stops are those listed in master G9.
  - Light stops darken the dark stop in OkLab L in steps of 0.02 until contrast
    against `#F3F2EF` is ≥ 4.5, then are frozen as constants. The test proves it.
  - Contrast uses the WCAG 2.x relative-luminance formula.
- [ ] **Step 4: Change the scene.**
  - The fragment shader discards fragments where `aStatus` is 1 or 2 and
    `mod(aDist, dash+gap) > dash`.
  - Observed edges multiply brightness by `1.0 + 0.6*max(0.0, sin(6.2832*(aDist*0.5 - uTime/1.2)))`.
  - Hovering or pinning sets `uDimOthers=1`, and non-hovered alpha is multiplied
    by 0.35.
  - `uTime` advances in the existing render loop.
  - Documentary links (Task 2) are drawn into the same buffer.
  - Keep `curve_budget` behaviour unchanged.
- [ ] **Step 5: Replace the legend lines.**

```
→ Colour = relationship: orange call/data · violet hierarchy · cyan design rationale · sky describes · teal cites · gold bridge · red violation
→ Direction: bright at the source, fading into the target
→ Pattern: solid exact · dashed candidate · dotted expected only · pulsing observed at runtime
→ Size: content & packing share · Radial depth: coreness vs. indifference · Angle: relational affinity
```

  The frontend requests `layout_version: 'sphere-affinity-v1'` by default
  (`frontend/src/api.ts`, wherever `'sphere-pack-v1'` is set today). When the
  frame comes back as `sphere-pack-v1`, from an older server or a saved view,
  the last legend line falls back to
  `Size: content and packing share. Position is not similarity.`
  Saved layout edits (`layoutEditing.ts`) are keyed by `layout_version`.
  Edits made under `sphere-pack-v1` are not applied to `sphere-affinity-v1`
  frames; show the existing "edits not applicable" state, or drop them silently
  if no such state exists.

- [ ] **Step 6: Write the browser test** `edge-chromatics.spec.cjs`. Load the
  integrated workspace on the fixture used by `integrated-workspace.spec.cjs`;
  assert the legend text above, including the `Radial depth: coreness vs. indifference` line; take a canvas screenshot and assert there are at
  least 2 distinct hue clusters among non-background pixels (hue bins of 30°);
  assert no console errors.
- [ ] **Step 7:** Run `npm run test:unit`, `npm run typecheck`, `npm run build`,
  then `playwright test --config playwright.graphs.config.cjs`. Expected: all pass.
- [ ] **Step 8: Commit:** `feat(viewer): high-contrast directional edge rendering and legend`.

---

### Task 5: Graph strata and PC-MCKP federation (master D2; Phase 6 Track 2.1, corrected)

**Files:**
- Create: `src/geographer/federation.py`
- Modify:
  - `src/geographer/graph_router.py:234-265` (`federated_search`);
  - `src/geographer/graph_catalog.py`: add
    `set_stratum(graph_id: str, role: str, trust_tier: str, modality: str) -> None`,
    which writes `profile_json.stratum`;
  - `src/geographer/cli.py`: add a `set-graph-stratum` subcommand
    (`--catalog --graph-id --role --trust-tier --modality`).
- Modify: `tests/test_graph_catalog.py::test_federation_budget_drops_largest_envelope_regardless_of_order`,
  renamed `test_federation_selection_is_order_independent`. It keeps the
  permutation assertion; the "largest dropped" assertion goes.
- Test: `tests/test_federation_selection.py`

**Interfaces:**
- Values:
  - `trust_tier ∈ {gold, gold_paper, silver, bronze, bronze_transcript}`, with
    `w_tier` = 1.00 / 0.95 / 0.75 / 0.35 / 0.15;
  - `modality ∈ {code, doc, paper, legacy_doc, transcript}`.
  - Default when unset: `silver` with `code`, or with `paper` if the graph has a
    `paper_database` and 0 code entities.
- Produces:
  - `intent(query: str) -> Literal['identifier','conceptual','historical']`;
  - `utility(trust_tier, modality, intent, store_mb: float, hit_ranks: list[int], n_exact: int) -> int`;
  - `select(candidates: list[Candidate], budget: int) -> dict[str, Literal['full','compact','omit']]`,
    where `Candidate(graph_id: str, tier: str, tokens: int, utility: int)`.
- `utility` formula:

  ```
  U = floor(10000 · w_tier · φ(intent, modality) · ψ(store_mb) · R)
  ψ(S) = 1 / (1 + 0.25·ln(1 + S))
  R = 12·Σ_{i ≤ min(5,n)} 1/(60+i) + 0.4·ln(1+n_exact)
  ```

  `φ` is the Phase 6 §2.1 table:

  | Intent | code | paper/doc | legacy_doc/transcript |
  |---|---|---|---|
  | identifier | 1.25 | 1.00 | 0.60 |
  | conceptual | 1.05 | 1.20 | 0.70 |
  | historical | 1.00 | 1.00 | 1.15 |

  - `intent`: `historical` if any token is in `{legacy, deprecated, history, brainstorm, old}`;
    `identifier` if the query matches `[A-Za-z_][\w.]*\(?\)?` with a `_`, `.` or
    an inner capital; else `conceptual`.
  - Errored graphs have `U = 0` and are always `omit`, with reason `GRAPH_UNAVAILABLE`.
- `select`:
  - enumerate all `{full, compact, omit}^n` (n ≤ 8, ≤ 6,561 combinations);
  - maximise `(ΣU, −Σtokens, tuple(sorted (graph_id, tier)) reversed-lexicographic)`
    subject to `Σtokens ≤ budget`;
  - full = `limit=5` results, compact = `limit=2`.
- The router assembles the response, counts it exactly with `TokenCounter`, and
  on overflow re-runs `select` with `budget − overflow` (at most 4 times).
- Response gains `selection = {method: 'pc-mckp-v1', tiers: {gid: tier}, utility: {gid: U}}`.
  `omitted[].reason ∈ {GRAPH_UNAVAILABLE, budget_compact_only, budget_omitted}`.

- [ ] **Step 1: Write the failing tests.**

```python
from geographer.federation import intent, utility, select, Candidate
import itertools

def test_intent_classifier():
    assert intent("parse_document") == "identifier" and intent("GraphRouter.query") == "identifier"
    assert intent("how are graphs isolated") == "conceptual" and intent("legacy solver notes") == "historical"

def test_volume_dampener_prefers_small_curated_store():
    small = utility("gold_paper", "paper", "conceptual", 0.55, [1, 2, 3], 0)
    big = utility("bronze_transcript", "transcript", "conceptual", 85.32, [1, 2, 3, 4, 5], 0)
    assert small > big

def test_select_is_permutation_invariant():
    cands = [Candidate(g, t, tok, u) for g, t, tok, u in [
        ("g_a", "full", 1800, 9000), ("g_a", "compact", 700, 6000),
        ("g_b", "full", 1600, 8000), ("g_b", "compact", 600, 5000),
        ("g_c", "full", 2500, 3000), ("g_c", "compact", 900, 1500)]]
    results = {tuple(sorted(select(list(p), 3000).items())) for p in itertools.permutations(cands)}
    assert len(results) == 1

def test_pc_mckp_degenerate_inputs():
    assert select([], 4096) == {}
    assert select([Candidate("g_a", "full", 5000, 10), Candidate("g_a", "compact", 3000, 5)], 2048) == {"g_a": "omit"}
    assert select([Candidate("g_a", "full", 100, 0), Candidate("g_a", "compact", 50, 0)], 4096) == {"g_a": "omit"}
```

  Add a router-level test, `test_federation_all_graphs_failing_returns_valid_envelope`,
  in `tests/test_graph_catalog.py`. It deletes both stores and asserts that
  `results == []`, both graphs appear in `omitted` with `GRAPH_UNAVAILABLE`, and
  no exception is raised.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3: Implement `federation.py`, then rewrite `federated_search`.**
  - Query each graph twice (limit 5 and 2), or once at limit 5 and derive
    compact by slicing whole items.
  - Count tokens per envelope.
  - Call `select`, then assemble and verify.
  - Keep `ranking='independent_per_graph_no_global_rank'`.
- [ ] **Step 4:** Run `pytest tests/test_federation_selection.py tests/test_graph_catalog.py -q`. Expected: PASS.
- [ ] **Step 5: Commit:** `feat(federation): provenance-calibrated envelope selection (pc-mckp-v1)`.

---

### Task 6: Graph lifecycle (copy, delete, active set; master G8)

**Files:**
- Modify:
  - `src/geographer/graph_catalog.py`: `copy_graph` and `delete_graph`;
  - `src/geographer/graph_router.py`: `retire_graph`;
  - `src/geographer/graph_server.py:173-179`: routes;
  - `src/geographer/cli.py`: `copy-graph` and `delete-graph` subcommands.
- Modify:
  - `frontend/src/Workspace.tsx:159+` (graph picker): menu items **Copy…**
    (label prompt), **Delete…** (type the label to confirm) and an **Active**
    toggle (max 4);
  - `frontend/src/api.ts`: client calls.
- Test: `tests/test_graph_lifecycle.py`, `tests/browser-graphs/lifecycle.spec.cjs`

**Interfaces:**
- Produces:
  - `GraphCatalog.copy_graph(graph_id: str, label: str) -> dict`, returning
    `{graph_id, label, copied_from, snapshot_id}`;
  - `GraphCatalog.delete_graph(graph_id: str, *, retire: Callable[[str], None] | None = None, protected: frozenset[str] = frozenset()) -> dict`,
    returning `{deleted, bridges_removed: list[str], files_unlinked: list[str], files_kept: list[str]}`;
  - `GraphRouter.retire_graph(graph_id: str, timeout: float = 10.0) -> None`,
    which raises `ValueError('GRAPH_BUSY')` on timeout.
- HTTP:
  - `POST /api/graphs/{graph_id}/copy` with `{label}` → 200 with the copy dict;
  - `DELETE /api/graphs/{graph_id}` with `{confirm_label}` → 200 receipt;
    409 `GRAPH_IN_USE` / `GRAPH_BUSY`; 400 on label mismatch;
  - `GET` and `PUT /api/workspace/active-graphs` with `{graph_ids: [..≤4]}`.
- Errors are raised as `ValueError` with a message starting with the code.

- [ ] **Step 1: Write the failing tests.** Use the `hub` fixture and
  `import_graph` from `tests/test_graph_catalog.py`.

```python
def test_copy_is_independent_and_queryable(hub, tmp_path):
    catalog, router, first = hub
    copy = catalog.copy_graph(first["graph_id"], "A copy")
    assert copy["graph_id"] != first["graph_id"] and catalog.graph(copy["graph_id"])["snapshot_id"] == first["ingestion"]["snapshot_id"]
    assert router.query(copy["graph_id"], "search_entities", request(first))["data"]["results"]

def test_delete_removes_owned_store_and_bridges(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / "b", "B")
    catalog.add_bridge(first["graph_id"], "root", second["graph_id"], "root", "reference", "test", [{"note": "x"}])
    path = Path(catalog.graph(second["graph_id"])["code_database"])
    receipt = catalog.delete_graph(second["graph_id"], retire=router.retire_graph)
    assert receipt["deleted"] == second["graph_id"] and len(receipt["bridges_removed"]) == 1 and not path.exists()

def test_delete_refuses_merge_source_and_never_unlinks_registered_store(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / "b", "B")
    merged = merge_two(catalog, first["graph_id"], second["graph_id"])  # helper: the existing merge plan+execute path, as in test_graph_merge_composition.py
    with pytest.raises(ValueError, match="^GRAPH_IN_USE"):
        catalog.delete_graph(first["graph_id"], retire=router.retire_graph)
    external = tmp_path / "external.sqlite"
    shutil.copy(catalog.graph(second["graph_id"])["code_database"], external)
    gid = catalog.register_existing_store(external)
    receipt = catalog.delete_graph(gid, retire=router.retire_graph)
    assert external.exists() and receipt["files_kept"] == [str(external.resolve())] and receipt["files_unlinked"] == []

def test_delete_waits_for_leases_then_unlinks(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / "b", "B")
    key, _ = router.acquire(second["graph_id"])
    t = threading.Timer(0.3, router.release, args=(key,)); t.start()
    receipt = catalog.delete_graph(second["graph_id"], retire=router.retire_graph)
    assert receipt["files_unlinked"]

def test_delete_endpoint_requires_matching_label(hub, tmp_path):
    catalog, router, first = hub
    second = import_graph(catalog, tmp_path / "b", "B")
    client = TestClient(create_graph_http(router))
    wrong = client.request("DELETE", f"/api/graphs/{second['graph_id']}", json={"confirm_label": "nope"})
    assert wrong.status_code == 400
    ok = client.request("DELETE", f"/api/graphs/{second['graph_id']}", json={"confirm_label": "B"})
    assert ok.status_code == 200 and ok.json()["deleted"] == second["graph_id"]
```

  `merge_two` reuses the plan/execute calls already used in
  `tests/test_graph_merge_composition.py`. Copy that file's helper into
  `tests/test_graph_lifecycle.py`.
- [ ] **Step 2:** Run the tests. Expected: FAIL (`AttributeError: copy_graph`).
- [ ] **Step 3: Implement exactly per master G8.**
  - `delete_graph` checks refusals before calling `retire`.
  - The catalog transaction runs before any unlink.
  - Unlink retries use `time.sleep(0.05 * 2**n)` for n in 0..4.
  - `retire_graph` adds every `(graph_id, *)` key to `self.retired` and waits
    on a `threading.Condition` that `release` notifies.
  - The active set lives in the `create_graph_http` closure.
- [ ] **Step 4: Frontend.**
  - Add the picker menu items.
  - Delete opens a dialog that shows bridge count and owned/registered status
    (from `GET /api/graphs`) and requires typing the label.
  - The active toggle calls `PUT` and refreshes the composition frame.
- [ ] **Step 5: Write the browser test.** Copy a graph and assert it appears;
  then delete the copy with confirmation and assert it disappears; assert no
  console errors.
- [ ] **Step 6:** Run `pytest tests/test_graph_lifecycle.py tests/test_graph_catalog.py -q`,
  `npm run typecheck`, and the browser suite. Expected: PASS.
- [ ] **Step 7: Commit:** `feat(lifecycle): graph copy, safe delete and active set`.

---

### Task 7: Discovery card and Markdown export (`discovery-card-v1`, master G11)

**Files:**
- Create: `src/geographer/discovery.py`
- Modify:
  - `src/geographer/cli.py`: `discovery-report --store PATH [--snapshot ID] --out FILE.md [--json FILE]`;
  - `src/geographer/graph_server.py:87-90`: resources
    `geographer://graphs/{graph_id}/discovery` (JSON) and `…/discovery.md`.
- Test: `tests/test_discovery_card.py`

**Interfaces:**
- Produces:
  - `fas_min(k: int, weights: dict[tuple[int, int], float]) -> tuple[float, list[int]]`,
    returning the back-arc weight (≥ 1) and the ordering;
  - `build_card(store: SnapshotStore, snapshot_id: str) -> dict`, with keys
    `card_version, snapshot_id, quotient_cycles[≤5], boundary_bottlenecks[≤5], surprising_links[≤5], honesty, sources`;
  - `render_markdown(card: dict) -> str`;
  - `quotient_cycles(store: SnapshotStore, snapshot_id: str) -> list[dict]`:
    **every** file-level quotient SCC with `k ≥ 2`, not just the top 5. Each
    entry is `{representative_ids: sorted, member_rel_paths: sorted, qcics, rho_c6, fas_weight, w_cross}`.
    `build_card` takes its top 5 from this list. Wave 2 Task 5 consumes it.
  - `feedback_arcs(store: SnapshotStore, snapshot_id: str) -> frozenset[str]`:
    the `projection_id`s of the file-level quotient projections that are back
    arcs in each cycle's FAS ordering. Wave 3 Task 3 consumes it.
- Inputs:
  - the file-level view: the `analysis_views` row with
    `grouping_json = {"mode":"kind","kind":"file"}` and the default filter;
  - its `level_scc_condensations` and `quotient_projections`;
  - `partition_members` (atoms per file);
  - `relationships` (atomic SCCs);
  - `boundary-cayley-v1` analyses.

- [ ] **Step 1: Write the failing tests.**

```python
from geographer.discovery import fas_min, build_card, render_markdown, quotient_cycles, feedback_arcs

def test_fas_exact_regime_on_triangle():
    w, order = fas_min(3, {(0, 1): 1, (1, 2): 1, (2, 0): 1})
    assert w == 1 and sorted(order) == [0, 1, 2]

def test_fas_greedy_regime_is_deterministic():
    k = 10; edges = {(i, (i + 1) % k): 1 for i in range(k)} | {(i, (i + 3) % k): 2 for i in range(k)}
    assert fas_min(k, edges) == fas_min(k, dict(reversed(list(edges.items()))))

def test_card_finds_ping_pong_file_cycle(ping_pong_store):
    # fixture: a.py:f → b.py:g, b.py:h → a.py:k; atom graph acyclic ⇒ ρ_C6 = 1
    card = build_card(*ping_pong_store)
    top = card["quotient_cycles"][0]
    assert top["rho_c6"] == 1.0 and set(top["members_labels"]) == {"a.py", "b.py"}

def test_card_honesty_line_without_runtime(ping_pong_store):
    card = build_card(*ping_pong_store)
    assert "no runtime, performance or quality claim" in card["honesty"]
    assert all(row["source_analysis"] for sect in ("quotient_cycles", "boundary_bottlenecks", "surprising_links") for row in card[sect])

def test_card_bytes_identical_across_processes(ping_pong_store_path):
    outs = {subprocess.run([sys.executable, "-m", "geographer", "discovery-report", "--store", str(ping_pong_store_path), "--out", "-"],
                           env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, check=True).stdout for seed in ("1", "2")}
    assert len(outs) == 1

def test_quotient_cycles_and_feedback_arcs(ping_pong_store):
    cycles = quotient_cycles(*ping_pong_store)
    assert len(cycles) == 1 and cycles[0]["member_rel_paths"] == ["a.py", "b.py"]
    arcs = feedback_arcs(*ping_pong_store)
    assert len(arcs) == 1   # a 2-cycle of weight-1 arcs needs exactly one back arc

def test_markdown_under_token_budget(ping_pong_store):
    from geographer.tokens import TokenCounter
    assert TokenCounter().count(render_markdown(build_card(*ping_pong_store))) <= 1100
```

- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `fas_min` follows master G11 and Phase 6 §8.1.
  - Bitmask DP for `2 ≤ k ≤ 8`: `dp[mask] = min over v∈mask of dp[mask\{v}] + Σ_{u∈mask\{v}} W(v→u)`,
    with ties going to the lexicographically smallest order tuple. Reconstruct
    the order.
  - Eades–Lin–Smyth for `k > 8`, ties by smallest index.
  - Rank rows by score descending, then `representative_id`, with `round(x, 6)`.
  - `members_labels` uses `labels.base_label` (Task 1).
  - The CLI `--out -` writes to stdout.
- [ ] **Step 4: Run on real data.** Run
  `python -m geographer discovery-report --store output/toolset.sqlite --out output/phase67-gates/toolset-discovery.md`
  and open the file. Expected: three sections plus the honesty line, ≤ 1,100
  tokens, and no exception.
- [ ] **Step 5:** Run the tests. Expected: PASS.
- [ ] **Step 6: Commit:** `feat(discovery): deterministic discovery card with Markdown export`.

---

### Task 8: Wave 1 gate

**Files:**
- Create: `reports/PHASE67_WAVE1_GATE.md`

- [ ] **Step 1: Build gate copies.** Copy `output/named-graphs/catalog.sqlite`
  and the four graph stores into `output/phase67-gates/wave1/`, never touching
  the originals. Re-point `code_database` paths in the copied catalog.
- [ ] **Step 2: Measure on ToolSet and librarian-v2,** and record the results in
  the report:
  - the count of `Documentation · line` labels in a file-view frame and an
    atomic frame (expected 0);
  - the number of duplicate visible labels per parent (expected 0);
  - the share of labels that needed a snippet or a number;
  - the distribution of role badges;
  - for `sphere-affinity-v1` frames: overlaps (expected 0), mean `r_norm` per
    band (expected core < mantle < crust), mean affine-pair cosine versus
    zero-affinity cosine (expected affine > zero), and cold frame latency
    (expected ≤ 3.0 s);
  - the documentary link count;
  - the distribution of curve families;
  - the discovery card token count;
  - federation selections for 5 queries across the 4 graphs under 4,096 and
    8,192 budgets, checking every permutation (expected identical).
- [ ] **Step 3:** Run `./scripts/verify.ps1`. Expected: exit 0. Paste the summary
  table into the report.
- [ ] **Step 4: Commit:** `docs: wave 1 gate report`.
