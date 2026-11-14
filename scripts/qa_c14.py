"""Prospective C14: three fresh installed-wheel processes on a quiet machine."""
import argparse
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import statistics
import subprocess
import sys
import tempfile


def passes(samples):
    return (len(samples)==3 and all(math.isfinite(x) and x>=0 for x in samples)
            and statistics.median(samples)<3.0 and max(samples)<3.5)


def sample(database,sid):
    import copy,time,geographer,importlib.metadata
    from geographer.store import SnapshotStore
    from geographer.service import QueryService
    from geographer.analysis import DEFAULT_FILTER
    with SnapshotStore(database) as store:
        svc=QueryService(store,secret=b'x'*32);g=store.graph(sid)
        focus=next(e.entity_id for e in sorted(g.entities.values(),key=lambda e:e.entity_id)
                   if e.kind=='function' and not(e.is_external or e.is_test or e.is_generated or e.is_vendor))
        req=dict(schema_version='1.1',request_id='directed',snapshot_id=sid,
            budget=dict(limit_tokens=8192,tokenizer='o200k_base',allow_byte_fallback=False),
            focus_id=focus,grouping={'mode':'atomic'},context_radius=2,filter=copy.deepcopy(DEFAULT_FILTER),
            pins=[],qi=dict(enabled=True,max_diameter=2,algorithm='directed-helper-condensation-v1'),cursor=None)
        start=time.perf_counter();result=svc.query('get_architecture_context',req)
        assert 'error' not in result,result
        svc.wire11.validate('get_architecture_context','response',result)
        seconds=time.perf_counter()-start
    print(json.dumps(dict(seconds=seconds,pid=os.getpid(),snapshot_id=sid,focus_id=focus,
        success=True,package_file=geographer.__file__,package_version=importlib.metadata.version('geo-grapher'))))


def main():
    p=argparse.ArgumentParser();p.add_argument('--quiet-machine',action='store_true')
    p.add_argument('--wheel',type=Path);p.add_argument('--catalog',type=Path)
    p.add_argument('--out',type=Path);p.add_argument('--graph',default='ToolSet')
    p.add_argument('--sample',nargs=2,metavar=('DATABASE','SNAPSHOT'));a=p.parse_args()
    if a.sample:sample(*a.sample);return 0
    if not a.quiet_machine:p.error('Explicit --quiet-machine is required; stop other QA workloads first')
    if not all((a.wheel,a.catalog,a.out)):p.error('--wheel, --catalog and a fresh --out are required')
    if a.out.exists():p.error('Preserve first samples: use a new --out')
    wheel=a.wheel.resolve()
    with closing(sqlite3.connect(a.catalog.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row
        row=c.execute('SELECT * FROM graphs WHERE label=?',(a.graph,)).fetchone()
        if row is None:p.error('Requested timing graph is absent')
        graph=dict(row)
    report=dict(quiet_machine=True,rule='median of 3 cold <3.0 s AND max <3.5 s; prospective only',
        timing_scope='Fresh process; graph/focus lookup before clock, query and validation timed; no OS-cache flush',
        wheel=str(wheel),wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
        snapshot_id=graph['snapshot_id'],samples=[])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    env={k:v for k,v in os.environ.items() if k.upper()!='PYTHONPATH'}
    with tempfile.TemporaryDirectory(prefix='geographer-c14-') as tmp:
        copies=[Path(tmp)/f'sample-{i}.sqlite' for i in range(1,4)]
        for dest in copies:
            with closing(sqlite3.connect(Path(graph['code_database']).resolve().as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(dest)) as dst:src.backup(dst)
        for i,db in enumerate(copies,1):
            cmd=['uvx','--python',sys.executable,'--refresh-package','geo-grapher','--from',str(wheel),
                 'python',str(Path(__file__).resolve()),'--sample',str(db),graph['snapshot_id']]
            r=subprocess.run(cmd,cwd=tmp,env=env,capture_output=True,text=True)
            try:item=json.loads(r.stdout)
            except ValueError:item=dict(success=False,stdout=r.stdout,stderr=r.stderr)
            item.update(sample=i,returncode=r.returncode);report['samples'].append(item)
            a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(item),flush=True)
    rows=report['samples']
    valid=all(r.get('success') and r['returncode']==0 and '/site-packages/' in r.get('package_file','').replace('\\','/') for r in rows)
    valid=valid and len({r.get('pid') for r in rows})==3 and len({(r.get('snapshot_id'),r.get('focus_id')) for r in rows})==1
    values=[r['seconds'] for r in rows] if valid else []
    report.update(passed=valid and passes(values),median_seconds=statistics.median(values) if values else None,
        max_seconds=max(values) if values else None)
    a.out.write_text(json.dumps(report,indent=2)+'\n');return int(not report['passed'])


if __name__=='__main__':raise SystemExit(main())
