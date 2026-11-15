"""Metadata interchange with Librarian. No source bodies, Git config or credentials."""
import os
from pathlib import Path

from .credentials import credential_path
from .model import digest
from .source import valid_path

VERSION = 'folder-inventory-v1'


def validate(root, inventory):
    if (inventory.get('version') != VERSION or Path(inventory['root']).resolve() != root
            or not isinstance(inventory.get('fingerprint'), str)
            or inventory.get('partial') or inventory.get('unreadable')):
        raise ValueError('INVENTORY_INVALID: wrong root/version or incomplete survey')
    seen = set()
    for row in inventory.get('entries', []):
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError('INVENTORY_INVALID: expected path, size, mtime_ns')
        name, size, mtime = row
        if (not isinstance(name, str) or not valid_path(name.rstrip('/')) or name in seen
                or not isinstance(size, int) or not isinstance(mtime, int)):
            raise ValueError('INVENTORY_INVALID: unsafe or duplicate metadata entry')
        seen.add(name)
    return inventory


def collect(root, hygiene):
    entries = []; refused = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        here = Path(directory)
        for name in sorted(dirs + files):
            path = here / name; rel = path.relative_to(root).as_posix()
            if credential_path(rel):
                refused.append(rel)
                if name in dirs: dirs.remove(name)
                continue
            info = path.lstat()
            if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                entries.append((rel, -1, 0))
                if name in dirs: dirs.remove(name)
            elif name in dirs:
                excluded = name in hygiene or name.endswith('.egg-info') or name.lower().endswith('cache')
                entries.append((rel + '/', -2 if excluded else 0, 0))
                if excluded: dirs.remove(name)
            else:
                entries.append((rel, info.st_size, info.st_mtime_ns))
            if len(entries) > 200000:
                raise ValueError('INVENTORY_TOO_LARGE: narrow the content root')
    entries.sort()
    return dict(version=VERSION, root=str(root), entries=entries, fingerprint=digest(entries),
                credential_refusals=dict(count=len(refused), paths=sorted(refused)))


def walk(root, inventory):
    """os.walk-compatible traversal over metadata; caller may prune the yielded dirs."""
    children = {'': [[], []]}
    for name, size, _ in inventory['entries']:
        if credential_path(name):
            continue
        relative = name.rstrip('/'); parent, _, leaf = relative.rpartition('/')
        children.setdefault(parent, [[], []])
        if name.endswith('/'):
            children[parent][0].append(leaf)
            children.setdefault(relative, [[], []])
        elif size >= 0:
            children[parent][1].append(leaf)
    stack = ['']
    while stack:
        relative = stack.pop()
        dirs, files = children.get(relative, [[], []])
        dirs = sorted(dirs)
        yield str(root / relative), dirs, sorted(files)
        stack.extend('/'.join(filter(None, (relative, name))) for name in reversed(dirs))


def check_current(root, inventory):
    validate(root, inventory)
    hygiene = {Path(name.rstrip('/')).name for name, size, _ in inventory['entries'] if size == -2}
    current = collect(root, hygiene)
    normal = lambda rows: sorted(tuple(r) for r in rows if r[1] != -3 and not credential_path(r[0]))
    if normal(current['entries']) != normal(inventory['entries']):
        raise ValueError('PLAN_STALE: the shared survey no longer matches the folder')
