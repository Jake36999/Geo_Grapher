"""Pinned ToolSet re-ingestion and reuse of the pre-existing independent source oracle.

Does not execute ToolSet. Historical P5.0/P5.1 evidence is never overwritten.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import subprocess

from geographer.incremental import build_digest
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from .harness import sha

COMMIT='f8bc1ec4c54884293dace635275e95c685b03371'
SOURCE_DIGEST='e50bcf9c66d7cbf4e2d0ef15b1274f3ba918197abaee87e508f7f1f0e365261e'


def run(output,path,oracle_path):
    repository_path=Path(path)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    before=subprocess.check_output(['git','-C',str(repository_path),'status','--porcelain'])
    repo=Repository.from_git(repository_path,'ToolSet',COMMIT,('aletheia_toolchain','local_tool_assist_mcp'))
    if repo.content_digest!=SOURCE_DIGEST:raise ValueError('Pinned source manifest mismatch')
    oracle_raw=Path(oracle_path).read_bytes();oracle=json.loads(oracle_raw)
    with SnapshotStore(output/'toolset.sqlite') as store:
        ingestion=ingest(store,[repo],stage=3);sid=ingestion['snapshot_id'];graph=store.graph(sid)
        sites=defaultdict(list);records=[]
        for evidence in graph.evidence.values():
            r=graph.relationships[evidence.relationship_id]
            if r.subtype!='calls':continue
            d=json.loads(evidence.details_json)
            sites[d['occurrence_id']].append((r,evidence,d))
        for occurrence,items in sorted(sites.items()):
            statuses={r.resolution_status for r,_,_ in items}
            status='exact' if statuses=={'exact'} else 'candidate' if 'candidate' in statuses else 'unresolved'
            locality='known_internal_target' if all(not graph.entities[r.target_subject_id].is_external for r,_,_ in items) else 'unknown_target_locality'
            records.append(dict(occurrence_id=occurrence,path=items[0][1].rel_path,source_span=items[0][2]['source_span'],
                status=status,locality=locality,reasons=sorted({d['reason_code'] for _,_,d in items}),
                targets=sorted({r.target_subject_id for r,_,_ in items})))
        by_span=defaultdict(list)
        for items in sites.values():
            for r,e,d in items:by_span[(e.rel_path,d['source_span']['start_byte'])].append(r)
        results=[]
        for label in oracle['expected']:
            path,line,column=label['site'];target=tuple(label['target'])
            raw=repo.files[path];lines=raw.splitlines(keepends=True)
            offset=sum(len(s) for s in lines[:line-1])+column
            actual=by_span.get((path,offset),[])
            targets={(graph.entities[r.target_subject_id].rel_path,graph.entities[r.target_subject_id].start_line,
                      graph.entities[r.target_subject_id].qualified_name.rsplit('.',1)[-1]) for r in actual}
            exact=bool(actual) and all(r.resolution_status=='exact' for r in actual)
            results.append(dict(site=label['site'],expected=label['target'],emitted=bool(actual),
                                correct_exact=exact and targets=={target},wrong_exact=exact and targets!={target},
                                actual_targets=sorted(targets)))
        if any(r['wrong_exact'] for r in results):raise AssertionError('Independent supported-subset oracle regression')
        counts=Counter((r['status'],r['locality']) for r in records)
        reasons=Counter(reason for r in records for reason in r['reasons'])
        validation=store.validate(sid)
        if validation:raise AssertionError(validation)
        after=subprocess.check_output(['git','-C',str(repository_path),'status','--porcelain'])
        if before!=after:raise AssertionError('ToolSet worktree changed')
        report=dict(commit=COMMIT,source_digest=repo.content_digest,implementation_digest=build_digest(),ingestion=ingestion,
            worktree_unchanged=True,worktree_status_sha256=sha(before),
            publication_validation=validation,runtime_workload_executed=False,call_sites=len(records),
            call_site_counts=[dict(status=s,locality=l,count=n) for (s,l),n in sorted(counts.items())],reason_counts=dict(sorted(reasons.items())),
            independent_oracle=dict(path=str(oracle_path),sha256=sha(oracle_raw),scope=oracle['scope'],
                labelled_sites=len(results),correct_exact=sum(r['correct_exact'] for r in results),
                wrong_exact=sum(r['wrong_exact'] for r in results),emitted=sum(r['emitted'] for r in results)),
            limitations=['Inherited P5.1 independent labels are reused against the pinned source; not whole-repository precision/recall',
                         'Per-occurrence emitted reasons/locality are measurements of resolver output, not correctness labels',
                         'No ToolSet program, production workload or model task was executed'])
        (output/'occurrences.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
        (output/'oracle-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        (output/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repository',type=Path,default=Path('D:/Aletheia_project/DEV_TOOLS/ToolSet'))
    p.add_argument('--oracle',type=Path,default=Path('output/phase5/independent-oracle.json'))
    args=p.parse_args();run(args.output,args.repository,args.oracle)
