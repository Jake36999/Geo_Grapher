"""Cold-process QI timing against disposable stores; no model calls."""
import argparse,json,os,sqlite3,subprocess,sys,time
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--out',type=Path);p.add_argument('--sample');a=p.parse_args()
 if a.sample:
  label,algorithm=a.sample.split(',')
  from geographer.graph_catalog import GraphCatalog
  from geographer.graph_router import GraphRouter
  from geographer.analysis import DEFAULT_FILTER
  with sqlite3.connect(a.catalog.resolve().as_uri()+'?mode=ro',uri=True) as c:
   c.row_factory=sqlite3.Row;g=dict(c.execute('SELECT * FROM graphs WHERE label=?',(label,)).fetchone())
  with sqlite3.connect(Path(g['code_database']).resolve().as_uri()+'?mode=ro',uri=True) as c:
   eid=c.execute("SELECT entity_id FROM entities WHERE snapshot_id=? AND kind='function' ORDER BY entity_id LIMIT 1",(g['snapshot_id'],)).fetchone()[0]
  catalog=GraphCatalog(a.catalog);router=GraphRouter(catalog)
  req=dict(schema_version='1.1',request_id='cold-qa',snapshot_id=g['snapshot_id'],
   budget=dict(limit_tokens=8192,tokenizer='o200k_base',allow_byte_fallback=False),focus_id=eid,
   grouping={'mode':'atomic'},context_radius=2,pins=[],filter=DEFAULT_FILTER,
   qi=dict(enabled=True,max_diameter=2,algorithm=algorithm),cursor=None)
  started=time.perf_counter();out=router.query(g['graph_id'],'get_architecture_context',req);elapsed=time.perf_counter()-started
  print(json.dumps(dict(label=label,algorithm=algorithm,seconds=elapsed,success='error' not in out and 'error' not in out.get('result',{}),focus_id=eid)))
  router.close();catalog.close();return
 if not a.out or a.out.exists():raise SystemExit('A new --out path is required')
 env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'};rows=[]
 for label in ('ToolSet','librarian-v2'):
  for algorithm in ('helper_tree_balls_v1','directed-helper-condensation-v1'):
   for sample in range(3):
    result=subprocess.run([sys.executable,__file__,'--catalog',str(a.catalog.resolve()),'--sample',label+','+algorithm],env=env,capture_output=True,text=True,check=True)
    row=json.loads(result.stdout);row['sample']=sample+1;rows.append(row)
    a.out.write_text(json.dumps(rows,indent=2),encoding='utf-8');print(json.dumps(row),flush=True)
 raise SystemExit(any(not r['success'] or r['label']=='ToolSet' and r['seconds']>=3 for r in rows))
if __name__=='__main__':main()
