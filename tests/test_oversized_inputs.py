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
