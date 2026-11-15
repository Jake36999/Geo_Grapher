"""One oversized file must not abort a large project's graph (quantule_mapper, 2026-11-15)."""


def test_oversized_files_are_skipped_and_recorded_not_fatal(tmp_path):
    from geographer.source import Repository
    (tmp_path / "small.py").write_text("def f():\n    return 1\n")
    (tmp_path / "transcripts").mkdir()
    big = tmp_path / "transcripts" / "2025_August.txt"
    big.write_bytes(b"x" * (4 * 1024 * 1024 + 1))
    repo = Repository.from_directory(tmp_path, "proj")
    assert "small.py" in repo.files and "transcripts/2025_August.txt" not in repo.files
    assert repo.omitted == [{"path": "transcripts/2025_August.txt", "bytes": 4 * 1024 * 1024 + 1,
                             "reason": "exceeds 4 MiB per-file limit"}]


def test_same_named_owners_with_different_signatures_keep_nested_ids_distinct(tmp_path):
    """Notebooks often redefine a function in a later cell; nested lambdas must not collide."""
    from geographer.extract import PythonExtractor
    from geographer.source import Repository
    (tmp_path / "nb.py").write_text(
        "def rk4_step(a):\n    return (lambda x: x)(a)\n\n"
        "def rk4_step(a, b):\n    return (lambda x: x)(a + b)\n")
    graph = PythonExtractor([Repository.from_directory(tmp_path, "proj")]).extract()
    lambdas = [e for e in graph.entities.values() if e.qualified_name.startswith("nb.py.rk4_step.<lambda>")]
    assert len(lambdas) == 2 and len({e.entity_id for e in lambdas}) == 2
    assert sorted(e.qualified_name for e in lambdas) == ["nb.py.rk4_step.<lambda>", "nb.py.rk4_step.<lambda>@L5"]


def test_ids_without_a_collision_are_unchanged(tmp_path):
    from geographer.extract import PythonExtractor
    from geographer.model import entity_id
    from geographer.source import Repository
    (tmp_path / "m.py").write_text("def f(a):\n    return (lambda x: x)(a)\n")
    graph = PythonExtractor([Repository.from_directory(tmp_path, "proj")]).extract()
    lam = next(e for e in graph.entities.values() if e.qualified_name == "m.py.f.<lambda>")
    import ast
    sig = ast.dump(ast.parse("lambda x: x", mode="eval").body.args, include_attributes=False)
    assert lam.entity_id == entity_id("proj", "m.py", "m.py.f.<lambda>", "function", sig, 0)
