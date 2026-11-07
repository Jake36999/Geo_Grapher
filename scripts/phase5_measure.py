"""Pinned, non-executing Phase 5 ingestion and token-density measurements."""
from __future__ import annotations
import argparse, collections, copy, hashlib, json, sqlite3, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from geographer.extract import PythonExtractor
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.model import canonical
from geographer.analysis import DEFAULT_FILTER
from geographer.service import QueryService
from geographer.tokens import TokenCounter

COMMIT = 'f8bc1ec4c54884293dace635275e95c685b03371'
TOOLSET = Path('D:/Aletheia_project/DEV_TOOLS/ToolSet')

def run(label):
    out = ROOT / 'output' / 'phase5'; out.mkdir(exist_ok=True)
    before = subprocess.check_output(['git', '-C', str(TOOLSET), 'status', '--porcelain'])
    repo = Repository.from_git(TOOLSET, 'ToolSet', COMMIT, ('aletheia_toolchain', 'local_tool_assist_mcp'))
    if label=='baseline' and (out/'baseline-triage.json').exists():
        artifact=json.loads((out/'baseline-triage.json').read_text(encoding='utf-8'))
        assert artifact['source_digest']==repo.content_digest
        with SnapshotStore(out/'baseline.sqlite') as store:
            sid=artifact['ingestion']['snapshot_id'];store.require_complete(sid)
            statuses=dict(store.connection.execute('SELECT resolution_status,count(*) FROM relationships WHERE snapshot_id=? GROUP BY resolution_status',(sid,)))
            assert statuses==artifact['ingestion']['relationship_statuses']
        print(json.dumps({'mode':'verified preserved pre-change baseline',**{k:v for k,v in artifact.items() if k!='site_records'}},indent=2))
        return
    # Instrument source occurrences independently of emitted alternative IDs.
    sites = {}
    original = PythonExtractor.emit
    def emit(self, unit, source, target, subtype, status, node, ordinal=0, details=None):
        key = (unit.repo.repo_id, unit.path, source, subtype, node.lineno, node.col_offset,
               getattr(node, 'end_lineno', node.lineno), getattr(node, 'end_col_offset', 0),
               (details or {}).get('import', (details or {}).get('callee', '')))
        sites.setdefault(key, []).append((target, status, dict(details or {})))
        return original(self, unit, source, target, subtype, status, node, ordinal, details)
    PythonExtractor.emit = emit
    try:
        with SnapshotStore(out / f'{label}.sqlite') as store:
            report = ingest(store, [repo], stage=1)
            graph = store.graph(report['snapshot_id'])
            assert not store.validate(report['snapshot_id'])
    finally:
        PythonExtractor.emit = original
    # Reason data comes from actual persisted, validated evidence, not just the
    # instrumentation's arguments to emit (which predate claim construction).
    ev_by_site=collections.defaultdict(list)
    for e in graph.evidence.values():
        d=json.loads(e.details_json)
        if 'reason_code' in d:
            r=graph.relationships[e.relationship_id]
            ev_by_site[(e.rel_path,r.source_subject_id,e.start_line,d.get('callee',''))].append(d)
    counts = collections.Counter(); records = []
    for key, alternatives in sorted(sites.items()):
        if key[3] != 'calls': continue
        statuses = {s for _, s, _ in alternatives}
        status = 'exact' if statuses == {'exact'} else 'candidate' if 'candidate' in statuses else 'unresolved'
        localities = {'external_placeholder' if graph.entities[t].is_external else 'internal' for t, _, _ in alternatives}
        # A placeholder is not proof of an external/builtin target.
        locality = 'known_internal_target' if localities == {'internal'} else 'unknown_target_locality'
        details = alternatives[0][2]
        reasons = details.get('reason_codes') or details.get('additional_reason_codes', []) + ([details['reason_code']] if 'reason_code' in details else ['legacy_reason_unavailable'])
        persisted=ev_by_site.get((key[1],key[2],key[4],key[8]),[])
        if persisted:reasons=sorted({d['reason_code'] for d in persisted})
        counts[(status, locality)] += 1
        records.append(dict(site=list(key), status=status, locality=locality, reasons=sorted(set(reasons)),
                            targets=sorted({t for t, _, _ in alternatives})))
    artifact = dict(label=label, ingestion=report, call_sites=len(records),
        call_site_counts=[dict(status=s, locality=l, count=n) for (s,l),n in sorted(counts.items())],
        site_records=records, source_digest=repo.content_digest,
        measurement='instrumented emitted Python calls; unreachable sites retained; candidate alternatives deduplicated by AST span')
    (out / f'{label}-triage.json').write_text(json.dumps(artifact, indent=2), encoding='utf-8')
    assert before == subprocess.check_output(['git', '-C', str(TOOLSET), 'status', '--porcelain'])
    print(json.dumps({k:v for k,v in artifact.items() if k != 'site_records'}, indent=2))

def density_after():
    out=ROOT/'output/phase5'
    artifact=json.loads((out/'after-triage.json').read_text(encoding='utf-8'))
    baseline=json.loads((out/'context-baseline.json').read_text(encoding='utf-8'))
    request=copy.deepcopy(baseline['metrics']['request'])
    # Match the historical context's analysis stage, not a Stage 1 graph with
    # missing WL hashes (which would create a spurious density improvement).
    from geographer.incremental import build_digest
    with SnapshotStore(out/'context-after.sqlite') as store:
        matching=[r['snapshot_id'] for r in store.connection.execute("SELECT snapshot_id,config_json FROM snapshot_sets WHERE status='complete'")
                  if json.loads(r['config_json']).get('implementation_digest')==build_digest()]
        if matching:sid=matching[-1]
        else:
            repo=Repository.from_git(TOOLSET,'ToolSet',COMMIT,('aletheia_toolchain','local_tool_assist_mcp'))
            report=ingest(store,[repo],stage=3);sid=report['snapshot_id']
            assert report['relationship_statuses']==artifact['ingestion']['relationship_statuses']
            assert not store.validate(sid)
        request['snapshot_id']=sid
        svc=QueryService(store,secret=b'phase5-density-reproducible-key!!')
        response=svc.query('get_architecture_context',request)
        assert 'data' in response,response
        svc.wire.validate('get_architecture_context','response',response)
        metrics={name:TokenCounter(name).count(response) for name in ('o200k_base','cl100k_base')}
        result=dict(request=request,analysis_stage=3,nodes=len(response['data']['nodes']),relationships=len(response['data']['relationships']),
                    full_envelope_tokens=metrics,format='unchanged served v1.0; source classification changed; v1.1 is schema-only at P5.0/P5.1',response=response)
        (out/'context-after.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='response'},indent=2))

def context():
    out = ROOT / 'output' / 'phase5'; out.mkdir(exist_ok=True)
    src = sqlite3.connect(f'file:{(ROOT/"output/stage3-toolset.sqlite").as_posix()}?mode=ro', uri=True)
    dst = sqlite3.connect(out/'context-baseline.sqlite'); src.backup(dst); dst.close(); src.close()
    with SnapshotStore(out/'context-baseline.sqlite') as store:
        sid=store.connection.execute("SELECT snapshot_id FROM snapshot_sets WHERE status='complete' ORDER BY snapshot_id LIMIT 1").fetchone()[0]
        svc=QueryService(store,secret=b'phase5-density-reproducible-key!!')
        g=svc._context(sid)['g']
        focus=next(e.entity_id for e in sorted(g.entities.values(),key=lambda e:e.rel_path or '') if e.kind=='file' and e.language=='python')
        request=dict(schema_version='1.0',request_id='phase5-density',snapshot_id=sid,
          budget=dict(limit_tokens=8192,tokenizer='o200k_base',allow_byte_fallback=False),focus_id=focus,
          grouping={'mode':'kind','kind':'file'},context_radius=1,filter=copy.deepcopy(DEFAULT_FILTER),pins=[],qi={'enabled':False,'max_diameter':2},cursor=None)
        response=svc.query('get_architecture_context',request)
        assert 'data' in response, response
        counter=TokenCounter(); data=response['data']; reduced=copy.deepcopy(response)
        for n in reduced['data']['nodes']:
            for k in ['entity_id','ast_body_hash','wl_3hop_hash']: n.pop(k,None)
            if n.get('source'): n['source'].pop('revision',None)
        for r in reduced['data']['relationships']: r.pop('witness_cursor',None)
        metrics=dict(request=request,focus_name=g.entities[focus].qualified_name,nodes=len(data['nodes']),relationships=len(data['relationships']),
           full_envelope_tokens=counter.count(response),without_duplicate_ids_node_hashes_revisions_initial_edge_cursors=counter.count(reduced),
           attribution='whole-envelope ablation; BPE costs non-additive; canonical primary IDs/handles retained')
        (out/'context-baseline.json').write_text(json.dumps(dict(metrics=metrics,response=response),indent=2),encoding='utf-8')
        print(json.dumps(metrics,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('label',choices=['baseline','after','context','density-after']);args=p.parse_args()
    if args.label=='context':context()
    elif args.label=='density-after':density_after()
    else:run(args.label)
