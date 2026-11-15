"""Execute each frozen phase once; preserve partial results and close on failure."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
from register_recovery_eval import ROOT,LIB,write_new

def main():
    p=argparse.ArgumentParser();p.add_argument('registration',type=Path);a=p.parse_args()
    reg=json.loads(a.registration.read_text(encoding='utf-8'));directory=a.registration.parent
    state=directory/(reg['stage']+'.cycle-state.json')
    write_new(state,dict(status='started',complete=False,started_at=datetime.now(timezone.utc).isoformat()))
    records=[];complete=False
    try:
        env=dict(os.environ,PYTHONPATH=str(LIB/'src'),TEMP='D:/Librarian_V2/tmp/geo-grapher-wave4-final-tests',TMP='D:/Librarian_V2/tmp/geo-grapher-wave4-final-tests')
        for name,phase in reg['phases'].items():
            cmd=['D:/Librarian_V2/.venv/Scripts/python.exe',str(ROOT/'scripts/review4_budgeted_harness.py'),
                 '--registration',str(a.registration.resolve()),'--phase',name,'bench']
            for key,value in phase['configuration'].items():
                if key=='mode':continue
                cmd.extend(['--'+key.replace('_','-'),str(value)])
            cmd.extend(['--out',phase['out']])
            log=directory/(name+'.dispatch.log')
            with log.open('x',encoding='utf-8') as stream:run=subprocess.run(cmd,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
            path=Path(phase['out']);rows=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
            ok=run.returncode==0 and len(rows)==phase['episodes'] and not any(r.get('dispatch_blocked') for r in rows)
            records.append(dict(phase=name,returncode=run.returncode,collected=len(rows),complete=ok,log=str(log)))
            print(json.dumps(records[-1]),flush=True)
            if not ok:break
        complete=len(records)==len(reg['phases']) and all(r['complete'] for r in records)
    finally:
        # This state cannot authorise dispatch; the exclusive initial file prevents retry.
        state.write_text(json.dumps(dict(status='closed',complete=complete,phases=records,
            closed_at=datetime.now(timezone.utc).isoformat()),indent=2),encoding='utf-8')
    if not complete:raise SystemExit('Registered stage closed incomplete; first results retained, no redispatch')

if __name__=='__main__':main()
