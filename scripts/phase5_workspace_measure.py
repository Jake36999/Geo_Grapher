"""Pinned P5.3 ingestion and grouped-frame smoke measurements (development host)."""
from __future__ import annotations
import json,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from geographer.analysis import DEFAULT_FILTER
from geographer.incremental import build_digest
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.service import QueryService
from geographer.tokens import TokenCounter
from phase5_measure import TOOLSET,COMMIT

def main():
    output=ROOT/'output/phase5';output.mkdir(exist_ok=True)
    repository=Repository.from_git(TOOLSET,'ToolSet',COMMIT,('aletheia_toolchain','local_tool_assist_mcp'))
    with SnapshotStore(output/'p53-toolset.sqlite') as store:
        prior=[r['snapshot_id'] for r in store.connection.execute("SELECT snapshot_id,config_json FROM snapshot_sets WHERE status='complete'") if json.loads(r['config_json']).get('implementation_digest')==build_digest()]
        sid=prior[-1] if prior else ingest(store,[repository],stage=3)['snapshot_id'];svc=QueryService(store)
        ctx=svc._context(sid);graph=ctx['g'];focus=next(e.entity_id for e in graph.entities.values() if e.kind=='repository')
        observations=[]
        for grouping in ({'mode':'mixed','revealed_ids':[ctx['tree'].root,focus]},{'mode':'kind','kind':'file'},{'mode':'kind','kind':'class'}):
            q=dict(schema_version='1.1',request_id='p53-workspace',snapshot_id=sid,budget=dict(limit_tokens=32768,tokenizer='o200k_base',allow_byte_fallback=False),
                identity_mode='canonical_map',grouping=grouping,focus_id=focus,revealed_ids=[ctx['tree'].root,focus],pins=[],context_radius=1,filter=DEFAULT_FILTER,
                layout_version='sphere-pack-v1',seed='geographer-workspace-v1',beta=.8,edge_lens=dict(enabled=False,center=[0,0,0],radius=5,strength=.8),node_budget=500,curve_budget=2000,
                viewport=dict(width_px=1440,height_px=900,device_pixel_ratio=1),camera=dict(eye=[20,14,26],target=[0,0,0],up=[0,1,0],fov_y_degrees=45,near=.01,far=1000000))
            start=time.perf_counter();response=svc.query('viewport_frame',q);elapsed=1000*(time.perf_counter()-start)
            assert 'data' in response,response
            observations.append(dict(grouping=grouping,elapsed_ms=elapsed,nodes=len(response['data']['nodes']),curves=len(response['data']['curves']),
                count_method=response['budget']['count_method'],accounting_upper_bound=response['budget']['accounting_upper_bound'],
                full_envelope_tokens=TokenCounter().count(response),
                omissions=response['data']['scene_completeness'],max_packing_violation=response['data']['packing']['max_violation']))
        result=dict(snapshot_id=sid,commit=COMMIT,source_digest=repository.content_digest,implementation_digest=build_digest(),
            entities=len(graph.entities),relationships=len(graph.relationships),relationship_statuses=dict(Counter(r.resolution_status for r in graph.relationships.values())),
            publication_validation=store.validate(sid),frames=observations,host_scope='Development host; graph preloaded, first requested frame plan/layout cold; not target-device C14')
        (output/'p53-workspace-metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
