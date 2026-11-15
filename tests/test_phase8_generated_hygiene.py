import subprocess

import pytest

from geographer.source import Repository


@pytest.mark.parametrize('mode', ['directory', 'git'])
def test_generated_bundles_excluded_before_reading_but_typescript_selected(tmp_path, mode):
    for rel in ['src/resource_librarian/ui/app.js', 'dist/bundle.js',
                'ui/src/app.ts', 'src/module.js']:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('export const value = 1;', encoding='utf-8')
    if mode == 'git':
        subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
        subprocess.run(['git', '-C', str(tmp_path), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Fixture', '-c',
                        'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        revision = subprocess.check_output(['git', '-C', str(tmp_path), 'rev-parse', 'HEAD'], text=True).strip()
        repo = Repository.from_git(tmp_path, 'fixture', revision)
    else:
        repo = Repository.from_directory(tmp_path, 'fixture')
    assert set(repo.files) == {'ui/src/app.ts', 'src/module.js'}
