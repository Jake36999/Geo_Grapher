"""Expanded reference viewport benchmark; fresh derived cache in an isolated copy."""
from __future__ import annotations
import argparse,cProfile,json,pstats,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from geographer.analysis import DEFAULT_FILTER,materialize_view
from geographer.service import QueryService
from geographer.store import SnapshotStore
from geographer.tokens import TokenCounter

def run(label,profile=False,cache_mib=64,precomputed=False):
    out=ROOT/'output/phase5';out.mkdir(exist_ok=True)
    target=out/f'performance-{label}.sqlite'
    source=sqlite3.connect(f'file:{(ROOT/"output/benchmark.sqlite").as_posix()}?mode=ro',uri=True)
    dest=sqlite3.connect(target);source.backup(dest);dest.close();source.close()
    with SnapshotStore(target,cache_mib=cache_mib) as store:
        sid=store.connection.execute("SELECT snapshot_id FROM snapshot_sets WHERE status='complete' ORDER BY snapshot_id LIMIT 1").fetchone()[0]
        with store.connection:
            for table in ('quotient_witness_map','level_scc_condensations','partition_members','quotient_projections','view_representatives','analysis_views'):
                store.connection.execute(f'DELETE FROM {table} WHERE snapshot_id=?',(sid,))
        svc=QueryService(store);ctx=svc._context(sid);TokenCounter()
        if precomputed:
            materialize_view(store,sid,ctx['g'],{'mode':'kind','kind':'file'})
            store.connection.execute('PRAGMA shrink_memory')
        q=dict(schema_version='1.0',request_id='reference',snapshot_id=sid,
            budget=dict(limit_tokens=32768,tokenizer='o200k_base',allow_byte_fallback=False),
            focus_id='bench:repo',revealed_ids=['bench:workspace','bench:repo'],pins=[],context_radius=1,
            filter=DEFAULT_FILTER,layout_version='sphere-pack-v1',seed='geographer-workspace-v1',beta=.8,
            edge_lens=dict(enabled=False,center=[0,0,0],radius=5,strength=.8),node_budget=500,curve_budget=2000,
            viewport=dict(width_px=1440,height_px=900,device_pixel_ratio=1),
            camera=dict(eye=[20,14,26],target=[0,0,0],up=[0,1,0],fov_y_degrees=45,near=.01,far=1000000))
        samples=[];prof=cProfile.Profile()
        if profile:prof.enable()
        for i in range(4):
            q['request_id']=f'reference-{i}';start=time.perf_counter();result=svc.query('viewport_frame',q)
            samples.append(1000*(time.perf_counter()-start));assert 'data' in result,result
        if profile:
            prof.disable();prof.dump_stats(out/f'performance-{label}.prof')
            with (out/f'performance-{label}-profile.txt').open('w',encoding='utf-8') as stream:pstats.Stats(prof,stream=stream).sort_stats('cumulative').print_stats(35)
        report=dict(label=label,request=q,manifest='geographer-benchmark-v1',entities=50000,relationships=150000,sqlite_cache_mib=cache_mib,
            scope='graph/tokenizer preloaded; first layout/frame plan cold; ingestion file rollup available' if precomputed else 'graph/tokenizer preloaded; first plan and derived SQL cache cold; following 3 calls warm',
            samples_ms=samples,nodes=len(result['data']['nodes']),curves=len(result['data']['curves']),
            tokens=TokenCounter().count(result),profiler=profile,host='development host, not C14 target')
        (out/f'performance-{label}.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('--profile',action='store_true');p.add_argument('--cache-mib',type=int,default=64);p.add_argument('--precomputed',action='store_true');args=p.parse_args();run(args.label,args.profile,args.cache_mib,args.precomputed)
