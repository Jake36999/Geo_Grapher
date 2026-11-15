"""S0: retain the old catalog, refresh the pinned Librarian graph on G:, spend nothing."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(Path('G:/Libraries/_qa').resolve()) or output.exists():
        raise SystemExit('Use a fresh G:/Libraries/_qa output; retain every first result')
    revision = subprocess.run(['git', '-C', str(args.repository), 'rev-parse', args.revision + '^{commit}'],
        check=True, capture_output=True, text=True).stdout.strip()
    with closing(readonly(args.source_catalog)) as original:
        original.row_factory = sqlite3.Row
        graphs = [dict(row) for row in original.execute('SELECT * FROM graphs ORDER BY graph_id')]
        estimated = sum(Path(row[key]).stat().st_size for row in graphs
                        for key in ('code_database', 'paper_database') if row[key]) + 3 * 1024**3
        if shutil.disk_usage(output.parent).free - estimated < 5 * 1024**3:
            raise SystemExit('Estimated copy/index would leave less than 5 GiB')
        output.mkdir()
        catalog_path = output / 'catalog.sqlite'
        with closing(sqlite3.connect(catalog_path)) as destination: original.backup(destination)
    report = dict(revision=revision, source_catalog=str(args.source_catalog.resolve()),
                  catalog=str(catalog_path), estimated_bytes=estimated, spend=0, graphs=[])
    for row in graphs:
        destination = output / 'graphs' / row['graph_id']; destination.mkdir(parents=True)
        paths = {}
        for key, name in [('code_database', 'code.sqlite'), ('paper_database', 'papers.sqlite')]:
            if row[key]:
                target = destination / name
                with closing(readonly(row[key])) as source, closing(sqlite3.connect(target)) as copied:
                    source.backup(copied)
                paths[key] = str(target)
        with closing(sqlite3.connect(catalog_path)) as catalog:
            catalog.execute('UPDATE graphs SET code_database=?,paper_database=? WHERE graph_id=?',
                            (paths['code_database'], paths.get('paper_database'), row['graph_id']))
            catalog.commit()
        with closing(readonly(paths['code_database'])) as store:
            count = store.execute('SELECT count(*) FROM entities WHERE snapshot_id=?', (row['snapshot_id'],)).fetchone()[0]
        report['graphs'].append(dict(label=row['label'], graph_id=row['graph_id'], before=count,
                                     before_snapshot=row['snapshot_id']))
    from geographer.graph_catalog import GraphCatalog
    from geographer.source import Repository
    with closing(GraphCatalog(catalog_path)) as catalog:
        repo = Repository.from_git(args.repository, 'librarian-v2', revision, source_roots=('src',))
        target = next(row for row in graphs if row['label'] == 'librarian-v2')
        result = catalog.import_project(args.repository, repo, label='librarian-v2', decision='keep_separate', stage=3)
        assert result['graph_id'] == target['graph_id'], 'preserve graph identity'
        current = catalog.graph(result['graph_id'])
        with closing(readonly(current['code_database'])) as store:
            sid = current['snapshot_id']
            after = store.execute('SELECT count(*) FROM entities WHERE snapshot_id=?', (sid,)).fetchone()[0]
            staging = store.execute("SELECT count(*) FROM entities WHERE snapshot_id=? AND rel_path='src/resource_librarian/staging.py'", (sid,)).fetchone()[0]
            assert staging > 0, 'staging.py must be indexed'
            assert store.execute('SELECT count(*) FROM entities WHERE snapshot_id=?', (target['snapshot_id'],)).fetchone()[0] == 424
        report.update(selected_files=len(repo.files), selected_bytes=sum(len(raw) for raw in repo.files.values()),
                      after=after, staging_entities=staging, ingestion=result)
    (output / 's0-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
