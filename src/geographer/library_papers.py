"""Publish a native verified conversion into a reviewed graph, retaining generations."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import uuid
from fnmatch import fnmatchcase

from .source import EXCLUDED, credential_path, generated_path


def _sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _owned_path(path, root):
    path = Path(path).absolute()
    if not path.is_relative_to(root) or path.resolve() != path:
        raise ValueError('PAPER_SCOPE: escaped or linked generated artifact')
    for parent in (path, *path.parents):
        if parent.is_symlink() or getattr(parent, 'is_junction', lambda:False)():
            raise ValueError('PAPER_SCOPE: linked generated artifact')
        if parent == root:
            break
    return path


def _source_allowed(original, source):
    root = Path(source['root']).resolve()
    if not original.is_relative_to(root):
        return False
    relative = original.relative_to(root)
    if any(p.startswith('.') or p in EXCLUDED for p in relative.parts):
        return False
    name = relative.as_posix()
    return (any(fnmatchcase(name, g) for g in source.get('include_globs', ['*']))
            and not any(name == g or fnmatchcase(name, g) for g in source.get('exclude_globs', [])))


def publish(catalog, request):
    from pipeline.stage3_build_db import DDL, load_nodes_file
    library = Path(request['library']).resolve()
    artifact = _owned_path(request['artifact'], library / '.librarian/derived/paper-graph')
    expected = request['artifact_sha256']
    if _sha(artifact) != expected:
        raise ValueError('PAPER_ARTIFACT_STALE: the approved projection changed')
    data = json.loads(artifact.read_text(encoding='utf-8'))
    if (data.get('source') != 'librarian_conversion'
            or data.get('coverage', {}).get('status') != 'full_conversion'):
        raise ValueError('PAPER_SCOPE: a verified full native conversion is required')
    conversion = _owned_path(data['conversion']['path'], library / '.librarian/conversions')
    original = Path(data['original']['path']).resolve()
    if credential_path(original) or generated_path(original):
        raise ValueError('PAPER_SCOPE: excluded source')
    with catalog.import_lock:
        matches = [g for g in catalog.graphs() if g['label'] == request['graph_label']]
        if len(matches) != 1:
            raise ValueError('PAPER_SCOPE: choose one existing reviewed graph label')
        graph = matches[0]; profile = json.loads(graph['profile_json'])
        if (not catalog.owns_store(graph) or profile.get('graph_kind') != 'reviewed_folder_group'
                or Path(profile.get('library', '')).resolve() != library or profile.get('disabled')):
            raise ValueError('PAPER_SCOPE: graph is not an active reviewed folder group for this library')
        if (data['original']['authorship'] != profile.get('stratum', {}).get('authorship')
                or not any(_source_allowed(original, r)
                           for r in profile.get('source_roots_reviewed', []))):
            raise ValueError('PAPER_SCOPE: original is outside this graph provenance or source roots')
        prior = graph['paper_database']
        required = 100 * 1024**2 + (Path(prior).stat().st_size * 2 if prior else 0) + conversion.stat().st_size * 20
        if shutil.disk_usage(catalog.path.parent).free - required < 5 * 1024**3:
            raise ValueError('DISK_RESERVE: paper generation would leave less than 5 GiB')
        database = Path(graph['code_database']).parent / ('papers-native-' + uuid.uuid4().hex + '.sqlite')
        # Failed/unbound candidates remain for inspection; published generations
        # and all earlier source stores are never edited or deleted here.
        with sqlite3.connect(database) as conn:
            if prior:
                with sqlite3.connect(Path(prior).resolve().as_uri() + '?mode=ro', uri=True) as old:
                    old.backup(conn)
            conn.executescript(DDL)
            with contextlib.redirect_stdout(io.StringIO()):
                load_nodes_file(artifact, conn)
            conn.commit()
            documents = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        if _sha(artifact) != expected:
            raise ValueError('PAPER_ARTIFACT_STALE: projection changed during import')
        with catalog.lock, catalog.connection:
            changed = catalog.connection.execute('UPDATE graphs SET paper_database=? '
                'WHERE graph_id=? AND paper_database IS ? AND snapshot_id IS ? AND profile_json=?',
                (str(database), graph['graph_id'], prior, graph['snapshot_id'], graph['profile_json'])).rowcount
            if changed != 1:
                raise ValueError('PAPER_SCOPE: graph assignment changed during import')
    return dict(geographer_version='0.2.0', published=True, graph_id=graph['graph_id'],
        paper_database=str(database), previous_paper_database=prior, documents=documents,
        coverage=data['coverage'], source_stores_retained=True)
