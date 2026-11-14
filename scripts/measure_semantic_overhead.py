"""Small controlled ingestion overhead; real local model, no source execution."""
import argparse
import json
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.semantic import load_encoder


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',required=True)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    if args.out.exists() or args.work.exists():raise SystemExit('Use fresh work/results to retain first measurements')
    args.work.mkdir(parents=True);encoder=load_encoder(args.model)
    source='\n'.join(f'def operation_{n}(value):\n    """Read a bounded local record and return its documented value."""\n    return value + {n}\n' for n in range(100))
    repo=Repository('overhead','fixed-source',{'operations.py':source.encode()});rows=[]
    for trial in range(3):
        results={}
        for enabled in (False,True):
            name=f'trial{trial}-'+('semantic' if enabled else 'plain')
            with SnapshotStore(args.work/(name+'.sqlite')) as store:
                config=dict(cache=args.work/(name+'-vectors.sqlite'),encoder=encoder) if enabled else None
                results['semantic' if enabled else 'plain']=ingest(store,[repo],semantic=config)
        assert results['plain']['snapshot_id']==results['semantic']['snapshot_id']
        a=results['plain']['elapsed_seconds'];b=results['semantic']['elapsed_seconds']
        rows.append(dict(trial=trial,plain_seconds=a,semantic_seconds=b,delta_seconds=b-a,derived=results['semantic']['semantic']))
    result=dict(encoder_fingerprint=encoder.fingerprint,fixture_declarations=100,trials=rows,
        median_delta_seconds=statistics.median(row['delta_seconds'] for row in rows),
        scope='Warm loaded encoder, three synthetic 100-declaration ingests. Real frozen-corpus backfill is measured separately. No extrapolation to full ingest latency.',paid_calls=0)
    with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
