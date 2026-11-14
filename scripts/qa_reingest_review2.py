"""Re-ingest frozen source-byte copies; never open original project stores writable."""
import argparse,json,sqlite3,time
from pathlib import Path
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore

def main():
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--baseline-db',type=Path);a=p.parse_args()
    if a.out.exists() or a.baseline_db and a.baseline_db.exists():raise SystemExit('Use new evidence paths')
    with sqlite3.connect(a.catalog) as c:
        c.row_factory=sqlite3.Row;rows=[dict(r) for r in c.execute('SELECT * FROM graphs WHERE paper_database IS NULL')]
    results=[]
    for row in rows:
        if a.baseline_db and row['label']!='librarian-v2':continue
        with sqlite3.connect(Path(row['code_database']).resolve().as_uri()+'?mode=ro',uri=True) as db:
            repos=db.execute("SELECT repo_id,revision FROM snapshots WHERE snapshot_id=? AND repo_id<>'@workspace'",(row['snapshot_id'],)).fetchall()
            before=db.execute('SELECT count(*) FROM entities WHERE snapshot_id=?',(row['snapshot_id'],)).fetchone()[0]
        if len(repos)!=1:raise ValueError('This gate fixture expects one source namespace per code graph')
        profile=json.loads(row['profile_json']);rid,revision=repos[0]
        root=Path(row['root_path']).resolve()
        # All source copies must stay beside this disposable catalog.
        if not root.is_relative_to(a.catalog.resolve().parent):raise ValueError('Refusing to ingest an original source root')
        repo=Repository.from_directory(root,rid,source_roots=tuple(profile.get('source_roots',[''])) or ('',),
            include_globs=tuple(profile.get('include_globs',['*'])) or ('*',),exclude_globs=tuple(profile.get('exclude_globs',[])))
        repo.revision=revision
        dest=a.baseline_db or Path(row['code_database'])
        started=time.perf_counter()
        with SnapshotStore(dest) as store:
            report=ingest(store,[repo],stage=3)
            sid=report['snapshot_id'];constants=store.connection.execute("SELECT count(*) FROM entities WHERE snapshot_id=? AND kind='constant'",(sid,)).fetchone()[0]
            after=store.connection.execute('SELECT count(*) FROM entities WHERE snapshot_id=?',(sid,)).fetchone()[0]
        elapsed=time.perf_counter()-started
        if not a.baseline_db:
            with sqlite3.connect(a.catalog) as c:c.execute('UPDATE graphs SET snapshot_id=? WHERE graph_id=?',(sid,row['graph_id']))
        results.append(dict(label=row['label'],graph_id=row['graph_id'],old_snapshot_id=row['snapshot_id'],snapshot_id=sid,
            old_entities=before,entities=after,constants=constants,seconds=elapsed,report=report))
        a.out.write_text(json.dumps(results,indent=2),encoding='utf-8');print(json.dumps(results[-1]),flush=True)
if __name__=='__main__':main()
