"""Synthetic credential names only; never open real credentials."""
from pathlib import Path
import subprocess

import pytest

from geographer.source import Repository
from geographer.workspace_init import scan


REFUSED = ('Frank.env', '.env', '.env.local', 'certs/public.txt',
           'wazuh_config/certs/server.pem', 'private.key', 'bundle.p12',
           'bundle.pfx', 'id_private.py')


def fixture_tree(root):
    for name in (*REFUSED, 'src/safe.py'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic fixture only\n', encoding='utf-8')


def test_survey_refuses_credentials_before_counting_content(tmp_path):
    fixture_tree(tmp_path)
    plan = scan(tmp_path)
    refused = plan['credential_refusals']
    assert refused['count'] >= 7
    assert 'Frank.env' in refused['paths']
    assert 'id_private.py' in refused['paths']
    assert sum(p['file_counts'].get('.py', 0) for p in plan['partitions']) == 1


def test_directory_reader_never_opens_refused_paths(tmp_path, monkeypatch):
    fixture_tree(tmp_path)
    original = Path.read_bytes
    def guarded(path):
        assert path.relative_to(tmp_path).as_posix() not in REFUSED
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', guarded)
    assert set(Repository.from_directory(tmp_path, 'fixture').files) == {'src/safe.py'}


def test_explicit_repository_rejects_credentials():
    with pytest.raises(ValueError, match='CREDENTIAL_REFUSED'):
        Repository('fixture', 'synthetic', {'certs/note.md': b'synthetic'})


def test_git_filters_names_before_fetching_blob_contents(tmp_path, monkeypatch):
    fixture_tree(tmp_path)
    def git(*args):
        return subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    git('init'); git('add', '.')
    git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'synthetic')
    revision = git('rev-parse', 'HEAD').stdout.decode().strip()
    original = subprocess.run
    def guarded(argv, *args, **kwargs):
        assert 'archive' not in argv, 'whole-tree archive copies refused blobs before filtering'
        return original(argv, *args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', guarded)
    assert set(Repository.from_git(tmp_path, 'fixture', revision).files) == {'src/safe.py'}


def test_paper_entrypoints_refuse_before_opening_credentials(tmp_path, monkeypatch):
    from pipeline.stage1_extract_text import extract_pdf
    from pipeline.stage2_from_md import _convert_md
    import sys
    from types import SimpleNamespace
    path = tmp_path / 'certs'; path.mkdir()
    (path / 'note.md').write_text('synthetic')
    monkeypatch.setitem(sys.modules, 'fitz', SimpleNamespace(open=lambda *a: pytest.fail('refused PDF was opened')))
    with pytest.raises(ValueError, match='CREDENTIAL_REFUSED'):
        extract_pdf(path / 'paper.pdf')
    with pytest.raises(ValueError, match='CREDENTIAL_REFUSED'):
        _convert_md(path / 'note.md')


def test_direct_credential_directory_root_is_refused_before_walk(tmp_path):
    root = tmp_path / 'certs'; root.mkdir(); (root / 'public.txt').write_text('synthetic')
    with pytest.raises(ValueError, match='CREDENTIAL_REFUSED'):
        Repository.from_directory(root, 'fixture')
    with pytest.raises(ValueError, match='CREDENTIAL_REFUSED'):
        scan(root)
