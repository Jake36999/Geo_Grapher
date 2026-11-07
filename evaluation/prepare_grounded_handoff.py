"""Prepare just four revised prompts for the user-owned harness, without API calls."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from geographer.incremental import build_digest
from geographer.pipeline import ingest
from geographer.rules import ArchitectureRules
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.tokens import TokenCounter
from .harness import ROOT,load_suite,retrieve,sha
from .handoff import export


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    suite,files,_=load_suite();tasks={t['id']:t for t in suite['tasks']};counter=TokenCounter();rows=[]
    with SnapshotStore(output/'snapshot.sqlite') as store:
        repo=Repository('evaluation','fixture-v1',{p:b for p,b in files.items() if not p.endswith('.yaml')})
        sid=ingest(store,[repo],stage=3)['snapshot_id'];model=ArchitectureRules(files['geographer.rules.yaml'])
        service=QueryService(store,rules=[model]);graph=store.graph(sid)
        for tid in ('direction','stale_document'):
            for arm in ('flat_search','architecture_documents_paths'):
                evidence,trace=retrieve(service,sid,model,graph,files,tasks[tid],arm,counter)
                rows.append(dict(trial=0,task_id=tid,arm=arm,evidence=evidence,retrieval=trace))
        (output/'transcripts.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        failures=store.validate(sid)
        if failures:raise ValueError(failures)
        manifest=dict(task_manifest_sha256=sha((ROOT/'tasks.json').read_bytes()),source_lock_sha256=sha((ROOT/'sources.lock.json').read_bytes()),
            tokenizer='o200k_base',reserved_output=1024,total_input_output_limit=16384,implementation_digest=build_digest(),
            publication_validation=failures,model_execution='not_performed',generation='small-grounding-remediation-v1')
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        requests=export(output,output/'handoff')
        summary=[dict(eval_id=q['eval_id'],canonical_request_tokens=counter.count(q),
            source_paths=[r['path'] for r in q['prompt']['evidence']['records'] if r['kind']=='source']) for q in requests]
        (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(prepare(a.output),indent=2))
