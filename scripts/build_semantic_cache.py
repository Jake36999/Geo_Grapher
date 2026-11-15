"""Explicit local-only backfill. Canonical stores stay read-only and unchanged."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from offline_graphs import FrozenGraphs
from geographer.semantic import load_encoder,SemanticCache


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog',type=Path,required=True);p.add_argument('--graph',action='append',required=True)
    p.add_argument('--model',required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise SystemExit('Preserve first cache-build measurement')
    encoder=load_encoder(args.model);result=dict(encoder_fingerprint=encoder.fingerprint,encoder=encoder.metadata,graphs={},paid_calls=0)
    with FrozenGraphs(args.catalog) as frozen:
        for label in args.graph:
            graph=frozen.graph(label)
            path=Path(frozen.stores[label].connection.execute('PRAGMA database_list').fetchone()[2])
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            result['graphs'][label]=SemanticCache.build(args.cache,graph,frozen.snapshots[label],encoder)
            after=hashlib.sha256(path.read_bytes()).hexdigest()
            if before!=after:raise RuntimeError('Canonical store changed during read-only backfill')
            result['graphs'][label].update(canonical_sha256=before,canonical_unchanged=True,snapshot=frozen.snapshots[label])
    with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:result[k] for k in ('graphs','encoder_fingerprint','paid_calls')}))

if __name__=='__main__':main()
