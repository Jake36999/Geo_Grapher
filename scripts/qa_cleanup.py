"""Retain two newest marked QA copies per scenario; gate evidence stays protected."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import stat


def _absolute(path):
    return Path(os.path.abspath(path))


def _reparse(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def _ancestry(path):
    for item in (path, *path.parents):
        if _reparse(item):
            raise ValueError(f'Reparse/junction ancestry is protected: {item}')
    if any(part.casefold() == 'phase67-gates' for part in path.parts):
        raise ValueError(f'Gate paths are protected: {path}')
    if path.resolve() != path:
        raise ValueError(f'Redirected path is protected: {path}')


def _root(path):
    root = _absolute(path)
    _ancestry(root)
    marker = root / '.geographer-qa-root.json'
    if not root.is_dir() or _reparse(marker):
        raise ValueError('Expected an ordinary marked QA root')
    try:
        data = json.loads(marker.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ValueError('Missing or invalid QA root marker') from exc
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1 or data.get('kind') != 'geographer-disposable-qa-root':
        raise ValueError('Invalid QA root marker')
    return root


def _tree(path):
    pending = [path]
    while pending:
        item = pending.pop()
        if _reparse(item):
            raise ValueError(f'Reparse content is protected: {item}')
        if item.suffix.casefold() == '.whl' or item.name.casefold() == 'phase67-gates':
            raise ValueError(f'Frozen wheel/gate content is protected: {item}')
        if item.is_dir():
            pending.extend(sorted(item.iterdir(), key=lambda p: p.name))


def _copy(root, path):
    if not path.is_absolute() or path.parent.parent != root:
        raise ValueError('Copy must be directly under a QA scenario')
    _ancestry(path)
    _tree(path)
    try:
        data = json.loads((path / 'qa-copy.json').read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1 or data.get('disposable') is not True or data.get('scenario') != path.parent.name or data.get('state') not in {'complete', 'failed'}:
            raise ValueError('Unmarked, active or invalid copy')
        stamp = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError('Copy date must include a timezone')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError('Invalid/incomplete copy manifest: ' + str(exc)) from exc
    return stamp.astimezone(timezone.utc)


def plan_cleanup(root: Path, keep: int = 2) -> dict:
    root = _root(root)
    if type(keep) is not int or keep < 2:
        raise ValueError('Retain at least two complete copies per scenario')
    remove, retained, skipped = [], [], []
    for scenario in sorted(root.iterdir(), key=lambda p: p.name):
        if _reparse(scenario):
            skipped.append({'path': str(scenario), 'reason': 'Reparse scenario protected'})
            continue
        if not scenario.is_dir():
            continue
        eligible = []
        for path in sorted(scenario.iterdir(), key=lambda p: p.name):
            if _reparse(path):
                skipped.append({'path': str(path), 'reason': 'Reparse copy protected'})
                continue
            if not path.is_dir():
                continue
            try:
                eligible.append((_copy(root, path), path.name, path))
            except (ValueError, OSError) as exc:
                skipped.append({'path': str(path), 'reason': str(exc)})
        eligible.sort(key=lambda item: (item[0], item[1]))
        remove.extend(str(p) for _, _, p in eligible[:-keep])
        retained.extend(str(p) for _, _, p in eligible[-keep:])
    return {'root': str(root), 'keep': keep, 'remove': sorted(remove), 'retained': sorted(retained), 'skipped': skipped}


def apply_cleanup(plan: dict) -> dict:
    root = _root(plan['root'])
    current = plan_cleanup(root, plan.get('keep', 2))
    proposed = plan.get('remove')
    if not isinstance(proposed, list) or len(proposed) != len(set(proposed)) or set(proposed) != set(current['remove']):
        raise ValueError('Forged or stale cleanup plan; calculate a new plan')
    targets = [Path(p) for p in sorted(proposed)]
    for path in targets:
        _copy(root, path)  # Validate every absolute target before any mutation.
    removed = []
    for path in targets:
        _root(root)
        if str(path) not in plan_cleanup(root, current['keep'])['remove']:
            raise ValueError('Copy retention state changed before deletion')
        _copy(root, path)
        shutil.rmtree(path)  # Never resolve a junction away and delete its target.
        removed.append(str(path))
    return {'removed': removed, 'retained': current['retained'], 'skipped': current['skipped']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('output/qa-workspaces'))
    parser.add_argument('--apply', action='store_true', help='Apply verified retention; default is dry-run')
    args = parser.parse_args()
    if not args.root.exists():
        print(json.dumps({'root': str(_absolute(args.root)), 'remove': [], 'note': 'No managed QA root exists'}))
        return
    plan = plan_cleanup(args.root)
    result = apply_cleanup(plan) if args.apply else plan
    print(json.dumps({'dry_run': not args.apply, **result}, indent=2))


if __name__ == '__main__':
    main()
