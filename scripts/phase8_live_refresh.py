"""Approved pinned native refresh: build on persistent G, separately publish by CAS."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess

MAX_BUILD_BYTES = 4 * 1024**3
MIN_FREE_BYTES = 5 * 1024**3
LIVE_CATALOG = Path('F:/uv-data/Geo_Grapher/output/named-graphs/catalog.sqlite')
HUB_ROOT = Path('G:/Libraries/_geo-hub')


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def check_destination(path):
    path = Path(path).resolve()
    if not path.is_relative_to(HUB_ROOT.resolve()) or path == HUB_ROOT.resolve() or path.exists():
        raise ValueError('PERSISTENT_HUB: use a fresh child of G:/Libraries/_geo-hub; retain first results')
    return path


def validate_snapshots(plan):
    with closing(readonly(plan['code_database'])) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SNAPSHOT_VALIDATION: integrity check failed')
        for sid in [plan['expected']['snapshot_id'], plan['snapshot_id']]:
            if not conn.execute('SELECT count(*) FROM entities WHERE snapshot_id=?', (sid,)).fetchone()[0]:
                raise ValueError('SNAPSHOT_VALIDATION: old and new snapshots must both be readable')


def publish_binding(catalog, plan):
    """No source deletion or head overwrite; validates the actual replacement store."""
    validate_snapshots(plan)
    if shutil.disk_usage(Path(catalog).resolve().parent).free < MIN_FREE_BYTES + 1024**2:
        raise ValueError('SPACE_RESERVE: leave 5 GiB plus catalog publication headroom')
    expected = plan['expected']
    with closing(sqlite3.connect(catalog)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute('UPDATE graphs SET code_database=?,snapshot_id=?,profile_json=? '
            'WHERE graph_id=? AND snapshot_id=? AND code_database=? AND profile_json=?',
            (plan['code_database'], plan['snapshot_id'], plan['profile_json'], plan['graph_id'],
             expected['snapshot_id'], expected['code_database'], expected['profile_json']))
        if cursor.rowcount != 1:
            raise ValueError('HEAD_CHANGED: another session changed the binding/profile; publish nothing')


def backup(source, destination):
    with closing(readonly(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)


def build(output, repository, revision):
    output = check_destination(output)
    HUB_ROOT.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(HUB_ROOT).free - MAX_BUILD_BYTES < MIN_FREE_BYTES:
        raise ValueError('SPACE_RESERVE: 4 GiB build allowance plus 5 GiB free required on G')
    revision = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', revision + '^{commit}'], text=True).strip()
    with closing(readonly(LIVE_CATALOG)) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM graphs WHERE label='librarian-v2'").fetchone())
    output.mkdir()
    (output / 'LIVE_BACKED.md').write_text(
        '# Reserved live-backed graph storage\n\nNever remove as disposable QA. '
        'Publication status is recorded in publication.json; all old snapshots/stores are retained.\n', encoding='utf-8')
    copied_catalog = output / 'catalog-build.sqlite'
    backup(LIVE_CATALOG, copied_catalog)
    database = output / 'graphs' / row['graph_id'] / 'code.sqlite'
    database.parent.mkdir(parents=True)
    backup(row['code_database'], database)
    with closing(sqlite3.connect(copied_catalog)) as conn, conn:
        conn.execute('UPDATE graphs SET code_database=? WHERE graph_id=?', (str(database), row['graph_id']))
    from geographer.source import Repository, generated_path
    from geographer.graph_catalog import GraphCatalog
    repo = Repository.from_git(Path(repository), 'librarian-v2', revision, source_roots=('src', 'ui/src'))
    assert not any(generated_path(path) for path in repo.files)
    assert any(path.startswith('ui/src/') and path.endswith('.ts') for path in repo.files)
    with closing(GraphCatalog(copied_catalog)) as catalog:
        result = catalog.import_project(repository, repo, label='librarian-v2', decision='keep_separate', stage=3)
        assert result['graph_id'] == row['graph_id']
        current = catalog.graph(row['graph_id'])
    profile = json.loads(current['profile_json'])
    profile['stratum'] = dict(role='current', purpose='own-current', authorship='owner_created',
                              trust_tier='gold', modality='code')
    plan = dict(graph_id=row['graph_id'], snapshot_id=current['snapshot_id'], code_database=str(database),
        profile_json=json.dumps(profile, separators=(',', ':')), revision=revision,
        expected={key: row[key] for key in ['snapshot_id', 'code_database', 'profile_json']},
        selected_files=len(repo.files), selected_bytes=sum(len(v) for v in repo.files.values()),
        source_roots=['src', 'ui/src'], generated_authorship='generated', generated_bundles_excluded=True,
        ingestion=result, spend=0)
    validate_snapshots(plan)
    with closing(readonly(database)) as conn:
        plan['counts'] = {sid: conn.execute('SELECT count(*) FROM entities WHERE snapshot_id=?', (sid,)).fetchone()[0]
                          for sid in [row['snapshot_id'], current['snapshot_id']]}
        plan['generated_app_js_entities'] = conn.execute('SELECT count(*) FROM entities WHERE snapshot_id=? '
            "AND rel_path='src/resource_librarian/ui/app.js'", (current['snapshot_id'],)).fetchone()[0]
        assert plan['generated_app_js_entities'] == 0
    plan['build_bytes'] = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    if plan['build_bytes'] > MAX_BUILD_BYTES:
        raise ValueError('BUILD_ALLOWANCE: more than 4 GiB; retain the failed build without publication')
    (output / 'build-plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--repository', type=Path, default=Path('D:/Librarian_V2'))
    parser.add_argument('--revision', default='fd070b1')
    parser.add_argument('--publish-plan', type=Path)
    args = parser.parse_args()
    if args.publish_plan:
        plan_path = args.publish_plan.resolve()
        if not plan_path.is_relative_to(HUB_ROOT.resolve()):
            raise ValueError('PERSISTENT_HUB: publication plan must be live-backed')
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        if not Path(plan['code_database']).resolve().is_relative_to(plan_path.parent):
            raise ValueError('PERSISTENT_HUB: store must stay inside this build')
        if sum(p.stat().st_size for p in plan_path.parent.rglob('*') if p.is_file()) > MAX_BUILD_BYTES:
            raise ValueError('BUILD_ALLOWANCE: 4 GiB exceeded')
        backup(LIVE_CATALOG, plan_path.parent / 'catalog-before-publication.sqlite')
        publish_binding(LIVE_CATALOG, plan)
        result = dict(published=True, graph_id=plan['graph_id'], snapshot_id=plan['snapshot_id'],
                      code_database=plan['code_database'], spend=0)
        (plan_path.parent / 'publication.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
    else:
        if not args.output:
            parser.error('--output required for build; publication is a separate call')
        result = build(args.output, args.repository, args.revision)
        print(json.dumps({k: result[k] for k in ['revision','snapshot_id','selected_files',
            'selected_bytes','counts','build_bytes','generated_app_js_entities','spend']}, indent=2))


if __name__ == '__main__':
    main()
