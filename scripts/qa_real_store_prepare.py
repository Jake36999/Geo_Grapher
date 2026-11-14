"""Make disposable gate-store and source-byte copies for application QA."""
import argparse,base64,json,sqlite3,subprocess
from pathlib import Path

def backup(src,dest):
    with sqlite3.connect(Path(src).resolve().as_uri()+'?mode=ro',uri=True) as r,sqlite3.connect(dest) as w:r.backup(w)

def main():
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve()
    if out.exists():raise SystemExit('Use a fresh QA output directory; existing evidence is preserved')
    out.mkdir(parents=True);backup(a.catalog,out/'catalog.sqlite')
    with sqlite3.connect(out/'catalog.sqlite') as cat:
        cat.row_factory=sqlite3.Row
        rows=cat.execute('SELECT * FROM graphs').fetchall()
        for row in rows:
            source=out/'sources'/row['graph_id'];source.mkdir(parents=True)
            for column in ('code_database','paper_database'):
                if not row[column]:continue
                dest=out/(row['graph_id']+'-'+column+'.sqlite');backup(row[column],dest)
                cat.execute(f'UPDATE graphs SET {column}=? WHERE graph_id=?',(str(dest),row['graph_id']))
                if column=='code_database':
                    with sqlite3.connect(dest) as db:
                        for (raw,) in db.execute("SELECT result_json FROM analysis_results WHERE snapshot_id=? AND algorithm_version='source-bytes-v1'",(row['snapshot_id'],)):
                            item=json.loads(raw);target=(source/item['rel_path']).resolve()
                            if not target.is_relative_to(source):raise ValueError('Snapshot source path escapes QA root')
                            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(base64.b64decode(item['bytes_base64']))
            cat.execute('UPDATE graphs SET root_path=? WHERE graph_id=?',(str(source),row['graph_id']))
    browse=out/'browse';(browse/'project'/'src').mkdir(parents=True);(browse/'project'/'docs').mkdir()
    (browse/'project'/'src'/'small.py').write_text('def check(value):\n    return bool(value)\n',encoding='utf-8')
    (browse/'project'/'docs'/'guide.md').write_text('# Scratch project\nSmall QA copy.\n',encoding='utf-8')
    (browse/'project'/'README.md').write_text('# Scratch project\n',encoding='utf-8')
    escape=out/'outside-browse';escape.mkdir()
    junction=browse/'junction'
    link=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(escape)],capture_output=True,text=True)
    (out/'preparation.json').write_text(json.dumps(dict(source_catalog=str(a.catalog.resolve()),catalog=str(out/'catalog.sqlite'),
        browse_root=str(browse),junction_created=link.returncode==0,graphs=[dict(graph_id=r['graph_id'],label=r['label'],snapshot_id=r['snapshot_id']) for r in rows]),indent=2),encoding='utf-8')
    print(out/'catalog.sqlite')

if __name__=='__main__':main()
