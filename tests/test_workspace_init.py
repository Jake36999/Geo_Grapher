"""geographer init-workspace: disjoint partitions, hygiene sieve, archetype, plan/apply (workspace-init-v1)."""
import json
import os
import sys
from pathlib import Path

import pytest

from geographer.graph_catalog import GraphCatalog
from geographer.workspace_init import PLAN_VERSION, apply, scan


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "ws"
    files = {
        "src/a.py": "def a():\n    return 1\n",
        "src/old/b.py": "def b():\n    return 2\n",
        "docs/guide.md": "# Guide\nRead me.\n",
        "legacy/old.py": "def legacy():\n    return 0\n",
        "legacy/docs/x.md": "# X\n",
        "node_modules/z.js": "var z=1;\n",
        ".venv/lib/site.py": "x=1\n",
        "build/out.py": "x=2\n",
        "src/__pycache__/a.cpython-311.pyc": "",
        "papers/p.pdf": "%PDF-1.4",
        "data.csv": "a,b\n",
        "README.md": "# Workspace\n",
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def keyed(plan):
    return {p["key"]: p for p in plan["partitions"]}


def test_scan_proposes_disjoint_partitions_and_excludes_noise(tree):
    plan = scan(tree)
    assert plan["plan_version"] == PLAN_VERSION == "workspace-init-v1"
    parts = keyed(plan)
    assert set(parts) == {"residual", "docs", "legacy", "src__old", "papers"}
    assert parts["legacy"]["subtrees"] == ["legacy"] and parts["legacy"]["role"] == "legacy"
    assert parts["legacy"]["stratum"] == {"role": "legacy", "trust_tier": "bronze", "modality": "code"}
    assert parts["docs"]["stratum"] == {"role": "docs", "trust_tier": "silver", "modality": "doc"}
    assert parts["residual"]["subtrees"] == [] and parts["residual"]["stratum"]["trust_tier"] == "gold"
    excluded = {e["rel"]: e["reason"] for e in plan["excluded"]}
    assert {"node_modules", ".venv", "build", "src/__pycache__"} <= set(excluded)
    subtrees = [s for p in plan["partitions"] for s in p["subtrees"]]
    assert all(not a.startswith(b + "/") for a in subtrees for b in subtrees if a != b)
    assert [p["key"] for p in plan["partitions"]] == sorted(p["key"] for p in plan["partitions"])


def test_legacy_docs_fold_into_legacy(tree):
    parts = keyed(scan(tree))
    assert "legacy__docs" not in parts and parts["legacy"]["file_counts"] == {".md": 1, ".py": 1}


def test_residual_excludes_other_partitions_and_hygiene(tree):
    globs = set(keyed(scan(tree))["residual"]["exclude_globs"])
    assert {"legacy", "legacy/*", "docs", "docs/*", "src/old", "src/old/*", "build", "build/*"} <= globs


def test_counts_unsupported_and_manual_paper_step(tree):
    plan = scan(tree)
    assert plan["unsupported_by_suffix"].get(".csv") == 1 and ".pdf" not in plan["unsupported_by_suffix"]
    step = plan["manual_steps"][0]
    assert step["kind"] == "paper_corpus" and step["dir"] == "papers" and step["pdf_count"] == 1
    assert "--dry-run" in step["command"] and "run_pipeline.py" in step["command"]
    assert keyed(plan)["papers"]["file_counts"].get(".pdf") == 1


@pytest.mark.parametrize("files,archetype", [
    ({"a.py": "x=1\n", "b.md": "# b\n"}, "software_engineering"),
    ({"a.pdf": "%PDF", "b.pdf": "%PDF", "c.md": "# c\n"}, "academic_literature"),
    ({"a.py": "x=1\n", "a.pdf": "%PDF", **{f"n{i}.md": "# n\n" for i in range(6)}}, "research_lab"),
    ({f"n{i}.md": "# n\n" for i in range(5)}, "notes_vault"),
    ({}, "notes_vault"),
])
def test_archetype_rule(tmp_path, files, archetype):
    root = tmp_path / "w"; root.mkdir()
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    assert scan(root)["archetype"] == archetype


def test_plan_is_deterministic_and_has_stable_id(tree):
    a, b = scan(tree), scan(tree)
    assert a == b and len(a["plan_id"]) == 64


def test_plain_init_writes_plan_and_ingests_nothing(tree, tmp_path, monkeypatch):
    from geographer import cli
    out = tmp_path / "p.json"
    monkeypatch.setattr(sys, "argv", ["geographer", "init-workspace", "--root", str(tree), "--catalog", str(tmp_path / "c.sqlite"), "--plan-out", str(out)])
    cli.main()
    assert json.loads(out.read_text(encoding="utf-8"))["plan_version"] == "workspace-init-v1"
    assert GraphCatalog(tmp_path / "c.sqlite").graphs() == []


def test_apply_creates_one_graph_per_partition_with_strata(tree, tmp_path):
    catalog = GraphCatalog(tmp_path / "c.sqlite"); plan = scan(tree)
    reports = apply(catalog, plan, approved_keys={p["key"] for p in plan["partitions"]})
    assert len(reports) == 5 and len(catalog.graphs()) == 5
    residual = next(g for g in catalog.graphs() if Path(g["root_path"]) == tree.resolve())
    profile = json.loads(residual["profile_json"])
    assert "legacy" in profile["exclude_globs"] and profile["stratum"]["trust_tier"] == "gold"
    legacy = next(r for r in reports if r["key"] == "legacy")
    assert json.loads(catalog.graph(legacy["graph_id"])["profile_json"])["stratum"]["trust_tier"] == "bronze"


def test_apply_only_ingests_approved_keys(tree, tmp_path):
    catalog = GraphCatalog(tmp_path / "c.sqlite")
    reports = apply(catalog, scan(tree), approved_keys={"docs"})
    assert [r["key"] for r in reports] == ["docs"] and len(catalog.graphs()) == 1


def test_apply_refuses_stale_plan(tree, tmp_path):
    plan = scan(tree); (tree / "src" / "c.py").write_text("x=1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="^PLAN_STALE"):
        apply(GraphCatalog(tmp_path / "c.sqlite"), plan, approved_keys={"residual"})


def test_scan_marks_already_registered_root(tree, tmp_path):
    catalog = GraphCatalog(tmp_path / "c.sqlite"); plan = scan(tree)
    apply(catalog, plan, approved_keys={"residual"})
    assert scan(tree, catalog)["existing_graph_id"] is not None and scan(tree)["existing_graph_id"] is None


def test_symlinked_directory_is_excluded(tree, tmp_path):
    target = tmp_path / "elsewhere"; target.mkdir(); (target / "e.py").write_text("x=1\n", encoding="utf-8")
    try:
        os.symlink(target, tree / "linked", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted here")
    excluded = {e["rel"]: e["reason"] for e in scan(tree)["excluded"]}
    assert excluded.get("linked") in {"symlink", "reparse_point"}


def test_scan_rejects_missing_root(tmp_path):
    with pytest.raises(ValueError):
        scan(tmp_path / "nope")


def test_partition_globs_are_relative_to_their_own_root(tree):
    (tree / "legacy" / "build").mkdir(); (tree / "legacy" / "build" / "gen.py").write_text("x=1\n", encoding="utf-8")
    legacy = keyed(scan(tree))["legacy"]
    assert legacy["exclude_globs"] == ["build", "build/*"]
