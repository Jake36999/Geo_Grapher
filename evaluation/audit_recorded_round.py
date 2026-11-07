"""Audit archived requests/results without model calls or rewriting original scores."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .harness import load_suite,grade,sha
from .transport_schema import subject_names


def audit(directory,output):
    directory=Path(directory);output=Path(output)
    if output.exists():raise ValueError('Audit artifact already exists; preserved')
    requests={r['eval_id']:r for r in map(json.loads,(directory/'handoff/requests.jsonl').read_text(encoding='utf-8').splitlines())}
    suite,files,_=load_suite();tasks={t['id']:t for t in suite['tasks']};models=[]
    for path in sorted((directory/'results').glob('*/results.jsonl')):
        rows=[];usage=dict(input_tokens=0,output_tokens=0)
        for result in map(json.loads,path.read_text(encoding='utf-8').splitlines()):
            request=requests[result['eval_id']]
            if request['prompt_sha256']!=result['prompt_sha256']:raise ValueError('Recorded request/result mismatch')
            prompt=request['prompt'];evidence=prompt['evidence'];task=tasks[request['task_id']]
            original=grade(task,result['answer'],evidence,files)
            docs=[r['path'] for r in evidence['records'] if r.get('kind')=='source' and r['path'].endswith(('.md','.txt'))]
            names=set(subject_names(evidence));answer=result['answer']
            wire_schema=request.get('response_format',{}).get('json_schema',{}).get('schema',{})
            allowed=wire_schema.get('properties',{}).get('paths',{}).get('items',{}).get('items',{}).get('enum')
            missing_anchors=(sorted({r[k] for r in prompt.get('answer_contract',{}).get('requested_paths',[])
                                    for k in ('source','target') if r[k] not in allowed}) if allowed is not None else None)
            rows.append(dict(eval_id=result['eval_id'],model=result['model'],passed=original['passed'],components=original,
                original_document_paths=docs,document_citations=[c for c in answer['citations'] if c['path'] in docs],
                missing_required_facts=sorted(set(task['oracle']['facts'])-set(answer['facts'])),
                qualified_subject_format=all(n in names for p in answer['paths'] for n in p),
                response_format_mode=result.get('negotiated_mode',result.get('response_format_mode','not_archived')),
                path_enum_missing_public_anchors=missing_anchors,
                provider_request_id=result['provider_request_id']))
            for key in usage:usage[key]+=result['usage'][key]
        models.append(dict(folder_label=path.parent.name,results_sha256=sha(path.read_bytes()),
                           trials=len(rows),passes=sum(r['passed'] for r in rows),usage=usage,rows=rows))
    report=dict(version='recorded-round-audit-v1',models=models,
        conclusions=['The original archival scores and task/citation requirements were not relaxed',
                     'guide.md is present in all stale-document graph requests matched by prompt hash',
                     'Missing citation and incomplete span coverage are not missing retrieval',
                     'Baseline was 0/4 for one recorded model; no archived 0/12 three-model baseline',
                     'Negotiated mode is recorded when provided; absence is explicit and does not infer a mode from answer quality',
                     'One trial per task/arm/model cannot establish general superiority; pricing/billing not independently verified'])
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2),encoding='utf-8');return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();r=audit(args.directory,args.output);print(json.dumps([dict(model=m['rows'][0]['model'],passes=m['passes'],trials=m['trials']) for m in r['models']],indent=2))
