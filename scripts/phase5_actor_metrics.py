"""Measured current v1/v1.1 actor costs on the same pinned repository."""
from __future__ import annotations
import copy,json,sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from geographer.actor import ActorEncoder
from geographer.incremental import build_digest
from geographer.pipeline import ingest
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.tokens import TokenCounter
from phase5_measure import TOOLSET,COMMIT

def run():
    out=ROOT/'output/phase5';repo=Repository.from_git(TOOLSET,'ToolSet',COMMIT,('aletheia_toolchain','local_tool_assist_mcp'))
    with SnapshotStore(out/'p52-toolset.sqlite') as store:
        rows=list(store.connection.execute("SELECT snapshot_id,config_json FROM snapshot_sets WHERE status='complete'"))
        matching=[r['snapshot_id'] for r in rows if json.loads(r['config_json']).get('implementation_digest')==build_digest()]
        if matching:sid=matching[-1]
        else:
            report=ingest(store,[repo],stage=3);sid=report['snapshot_id'];assert not store.validate(sid)
        svc=QueryService(store,secret=b'phase5-actor-metrics-fixture-key!!')
        original=json.loads((out/'context-baseline.json').read_text(encoding='utf-8'))['metrics']['request']
        q={**original,'snapshot_id':sid,'request_id':'p52-density'}
        responses={}
        for version in ['1.0','1.1']:
            result=svc.query('get_architecture_context',{**q,'schema_version':version});assert 'data' in result,result
            responses[version]=result
        # Fixed record set isolates format cost. Its retained continuation is an
        # opaque cost sample, not a resumable public tool result.
        fixed=copy.deepcopy(responses['1.0']);fixed['schema_version']='1.1';fixed['data']['paths']=[]
        prototype=SimpleNamespace(mandatory=fixed['data'],units=[],evidence_plans={})
        encoder=ActorEncoder(svc,svc._context(sid),fixed['data']['view_id'],q['filter'])
        encoder.prepare(prototype);fixed['data']=encoder.envelope_data(prototype.mandatory)
        comparisons={}
        for encoding in ('o200k_base','cl100k_base'):
            counter=TokenCounter(encoding);arms={}
            for name,response in [('v1_fixed',responses['1.0']),('v11_fixed_format',fixed)]:
                region={k:v for k,v in response.items() if k!='budget'};region['request_id']='fixed-cost'
                envelope={**region,'budget':counter.report(region,32768)}
                arms[name]=counter.count(envelope)
            comparisons[encoding]=arms
        def costs(result):
            data=result['data']
            return dict(nodes=len(data['nodes']),relationships=len(data['relationships']),
                complete_witness_previews=sum(r.get('preview_complete',False) for r in data['relationships']),
                payload_bytes=len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode('utf-8')),
                tokens={name:TokenCounter(name).count(result) for name in ('o200k_base','cl100k_base')})
        wire11=svc.wire11
        operations=[n for n in svc.wire.document['operations'] if n!='viewport_frame']
        input_cost={}
        for name,wire in [('v1',svc.wire),('v11',wire11)]:
            pruned=[dict(name=op,inputSchema=wire.schema(op,'request')) for op in operations]
            unpruned=[dict(name=op,inputSchema={**wire.document['operations'][op]['request'],'$defs':wire.definitions}) for op in operations]
            input_cost[name]=dict(pruned=TokenCounter().count(pruned),all_definitions=TokenCounter().count(unpruned))
        graph=svc._context(sid)['g']
        report=dict(snapshot_id=sid,source_digest=repo.content_digest,implementation_digest=build_digest(),
            graph_counts=dict(entities=len(graph.entities),relationships=len(graph.relationships),
                relationship_statuses=dict(Counter(r.resolution_status for r in graph.relationships.values()))),
            publication_validation=store.validate(sid),request=q,adaptive={v:costs(r) for v,r in responses.items()},
            fixed_record_set_format_cost=comparisons,mcp_input_schema_tokens=input_cost,
            limitations=['fixed-format comparison is a cost artifact, not a resumable tool result',
                'adaptive pages select different records; preview richness and fixed-set density are measured separately',
                'cl100k re-counts do not alter the served o200k budget guarantee'])
        (out/'p52-actor-metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        for version,result in responses.items():(out/f'p52-actor-{version}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
if __name__=='__main__':run()
