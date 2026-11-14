"""Compare re-ingested facts, normalising only version/snapshot-bound identifiers."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--ingest-report', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Use a new result path')
    results = []
    with readonly(args.catalog) as catalog:
        for row in json.loads(args.ingest_report.read_text()):
            database = catalog.execute('SELECT code_database FROM graphs WHERE graph_id=?', (row['graph_id'],)).fetchone()[0]
            with readonly(database) as connection:
                result = {'label': row['label']}
                for table, ignored in (
                    ('entities', {'snapshot_id', 'qi_cluster_id'}),
                    ('relationships', {'snapshot_id', 'relationship_id', 'occurrence_key'}),
                    ('entity_fingerprints', {'snapshot_id'}),
                ):
                    fields = [c[1] for c in connection.execute('PRAGMA table_info(' + table + ')') if c[1] not in ignored]
                    def records(snapshot):
                        return sorted(connection.execute('SELECT ' + ','.join(fields) + ' FROM ' + table + ' WHERE snapshot_id=?', (snapshot,)).fetchall(), key=repr)
                    before, after = records(row['old_snapshot_id']), records(row['snapshot_id'])
                    result[table] = {'count': len(after), 'unchanged': before == after}
                def blocks(snapshot):
                    groups = defaultdict(set)
                    for entity, group in connection.execute('SELECT entity_id,qi_cluster_id FROM entities WHERE snapshot_id=? AND qi_cluster_id IS NOT NULL', (snapshot,)):
                        groups[group].add(entity)
                    return sorted(sorted(members) for members in groups.values())
                result['qi_memberships_unchanged'] = blocks(row['old_snapshot_id']) == blocks(row['snapshot_id'])
                def incidences(snapshot):
                    return set(connection.execute('SELECT fragment_id,entity_id,role FROM documentary_incidences WHERE snapshot_id=?', (snapshot,)))
                before, after = incidences(row['old_snapshot_id']), incidences(row['snapshot_id'])
                result['incidences'] = {'added': len(after - before), 'removed': len(before - after)}
                results.append(result)
    passed = all(r['qi_memberships_unchanged'] and all(r[t]['unchanged'] for t in ('entities', 'relationships', 'entity_fingerprints')) for r in results)
    report = {'passed': passed, 'normalisation': 'Ignore snapshot IDs; compare QI memberships instead of snapshot-bound cluster IDs; omit version-bound relationship IDs and occurrence keys while preserving edge multiplicity and every remaining field.', 'graphs': results}
    args.out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
