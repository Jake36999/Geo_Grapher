"""Retention applies only to marked disposable copies, never gates or wheels."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from scripts.qa_cleanup import plan_cleanup, apply_cleanup


def root_at(path):
    path.mkdir(parents=True)
    (path / '.geographer-qa-root.json').write_text(json.dumps({'schema_version': 1, 'kind': 'geographer-disposable-qa-root'}))
    return path


def copy_at(root, name, day, scenario='browser', state='complete'):
    path = root / scenario / name
    path.mkdir(parents=True)
    (path / 'qa-copy.json').write_text(json.dumps({'schema_version': 1, 'disposable': True,
        'scenario': scenario, 'created_at': f'2026-11-{day:02d}T00:00:00Z', 'state': state}))
    (path / 'store.sqlite').write_text('disposable fixture')
    return path


def test_keep_newest_two_per_scenario_and_apply_only_older_copies(tmp_path):
    root = root_at(tmp_path / 'qa')
    paths = [copy_at(root, f'copy-{n}', n) for n in range(1, 5)]
    other = copy_at(root, 'only', 1, 'security')
    plan = plan_cleanup(root)
    assert set(plan['remove']) == {str(p.resolve()) for p in paths[:2]}
    assert all(p.exists() for p in paths)
    result = apply_cleanup(plan)
    assert set(result['removed']) == set(plan['remove'])
    assert all(not p.exists() for p in paths[:2])
    assert all(p.exists() for p in paths[2:]) and other.exists()


def test_unmarked_active_and_frozen_wheel_copies_are_protected(tmp_path):
    root = root_at(tmp_path / 'qa')
    active = copy_at(root, 'active', 1, state='active')
    frozen = copy_at(root, 'frozen', 1)
    (frozen / 'release.whl').write_text('must stay')
    unknown = root / 'browser' / 'unmarked'
    unknown.mkdir()
    for n in (2, 3):copy_at(root, f'new-{n}', n)
    plan = plan_cleanup(root)
    assert not plan['remove']
    apply_cleanup(plan)
    assert active.exists() and frozen.exists() and unknown.exists()


def test_gate_root_and_forged_or_stale_plans_are_refused(tmp_path):
    protected = root_at(tmp_path / 'output' / 'phase67-gates' / 'wave4')
    with pytest.raises(ValueError, match='[Pp]rotect|[Gg]ate'):
        plan_cleanup(protected)
    root = root_at(tmp_path / 'qa')
    for n in range(1, 5):copy_at(root, f'copy-{n}', n)
    plan = plan_cleanup(root)
    outside = tmp_path / 'original'
    outside.mkdir()
    with pytest.raises(ValueError):apply_cleanup({**plan, 'remove': [str(outside)]})
    copy_at(root, 'newer', 10)
    with pytest.raises(ValueError):apply_cleanup(plan)
    assert outside.exists()
    upper = root_at(tmp_path / 'case-output' / 'PHASE67-GATES' / 'wave4')
    with pytest.raises(ValueError, match='[Pp]rotect|[Gg]ate'):plan_cleanup(upper)


def test_timestamp_order_uses_utc_and_rejects_naive_dates(tmp_path):
    root = root_at(tmp_path / 'qa')
    oldest = copy_at(root, 'oldest', 2)
    middle = copy_at(root, 'middle', 1)
    newest = copy_at(root, 'newest', 3)
    naive = copy_at(root, 'naive', 1)
    for path, value in [(oldest, '2026-11-02T01:00:00+02:00'),
                        (middle, '2026-11-01T23:30:00Z'),
                        (newest, '2026-11-02T01:00:00Z'),
                        (naive, '2026-11-01T00:00:00')]:
        manifest = path / 'qa-copy.json'
        data = json.loads(manifest.read_text())
        data['created_at'] = value
        manifest.write_text(json.dumps(data))
    assert plan_cleanup(root)['remove'] == [str(oldest.resolve())]


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows junction boundary')
def test_junction_is_never_followed_or_removed(tmp_path):
    root = root_at(tmp_path / 'qa')
    outside = tmp_path / 'original'
    outside.mkdir()
    (outside / 'keep.txt').write_text('original')
    scenario = root / 'browser'
    scenario.mkdir()
    link = scenario / 'junction'
    made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True, text=True)
    assert made.returncode == 0, made.stderr
    assert not plan_cleanup(root)['remove']
    apply_cleanup(plan_cleanup(root))
    assert (outside / 'keep.txt').read_text() == 'original' and link.exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows junction boundary')
def test_root_junction_is_rejected_before_resolution(tmp_path):
    actual = root_at(tmp_path / 'original')
    for n in range(1, 4):copy_at(actual, f'copy-{n}', n)
    alias = tmp_path / 'alias'
    made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(actual)], capture_output=True, text=True)
    assert made.returncode == 0
    with pytest.raises(ValueError, match='[Rr]eparse|[Jj]unction|[Rr]edirect'):
        plan_cleanup(alias)
    assert (actual / 'browser' / 'copy-1').exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows junction boundary')
def test_target_swapped_after_first_removal_is_rechecked(tmp_path, monkeypatch):
    import scripts.qa_cleanup as cleanup
    root = root_at(tmp_path / 'qa')
    paths = [copy_at(root, f'copy-{n}', n) for n in range(1, 5)]
    original = tmp_path / 'original'
    original.mkdir()
    (original / 'keep.txt').write_text('original')
    delete = cleanup.shutil.rmtree
    calls = []
    def swap_after_first(path):
        calls.append(Path(path))
        delete(path)
        if len(calls) == 1:
            target = paths[1]
            saved = target.with_name('saved')
            assert target.resolve().is_relative_to(root.resolve()) and saved.parent == target.parent
            target.rename(saved)
            made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(target), str(original)], capture_output=True, text=True)
            assert made.returncode == 0
    monkeypatch.setattr(cleanup.shutil, 'rmtree', swap_after_first)
    with pytest.raises(ValueError):cleanup.apply_cleanup(cleanup.plan_cleanup(root))
    assert len(calls) == 1 and (original / 'keep.txt').read_text() == 'original'
