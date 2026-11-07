"""Export bounded prompts for a user-owned harness; import actual pinned results.

No network access or model execution. Example:
python -m evaluation.handoff export --run output/phase5/p55-final-o200k --output NEW_DIR
python -m evaluation.handoff score --handoff NEW_DIR --results actual.jsonl --model PINNED_MODEL
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .harness import load_suite,model_prompt,sha,strict_json,grade
from geographer.model import canonical
from geographer.tokens import TokenCounter


def export(run_dir,output,tasks=('direction','stale_document'),arms=('flat_search','architecture_documents_paths')):
    run_dir=Path(run_dir);output=Path(output)
    suite,_,_=load_suite();by_task={t['id']:t for t in suite['tasks']}
    vocabulary=sorted({f for t in suite['tasks'] for f in t['oracle']['facts']})
    manifest=json.loads((run_dir/'manifest.json').read_text(encoding='utf-8'))
    if manifest['task_manifest_sha256']!=sha((Path(__file__).parent/'tasks.json').read_bytes()):raise ValueError('Task manifest mismatch')
    output.mkdir(parents=True,exist_ok=False);requests=[];counter=TokenCounter(manifest['tokenizer'])
    for line in (run_dir/'transcripts.jsonl').read_text(encoding='utf-8').splitlines():
        record=json.loads(line)
        if record['trial']!=0 or record['task_id'] not in tasks or record['arm'] not in arms:continue
        prompt=model_prompt(by_task[record['task_id']],record['evidence'],vocabulary)
        request=dict(eval_id=f"0/{record['task_id']}/{record['arm']}",task_id=record['task_id'],arm=record['arm'],
            prompt=prompt,prompt_sha256=sha(canonical(prompt).encode()),max_output_tokens=manifest['reserved_output'],
            total_input_output_limit=manifest['total_input_output_limit'],tokenizer=manifest['tokenizer'])
        from .transport_schema import compile_transport_schema
        compiled=compile_transport_schema(prompt)
        request['response_format']=compiled['response_format']
        request['schema_transport']=dict(profile=compiled['profile'],removed_constraints=compiled['removed_constraints'],
            full_schema_sha256=compiled['full_schema_sha256'],transport_schema_sha256=compiled['transport_schema_sha256'],
            validation_required=compiled['validation_required'],fallback_policy=compiled['fallback_policy'])
        if counter.count(request)+request['max_output_tokens']+256>request['total_input_output_limit']:raise ValueError('Handoff prompt exceeds budget')
        requests.append(request)
    if len(requests)!=len(tasks)*len(arms):raise ValueError('Incomplete handoff selection')
    (output/'requests.jsonl').write_text(''.join(canonical(q)+'\n' for q in requests),encoding='utf-8')
    (output/'manifest.json').write_text(json.dumps(dict(protocol='deepinfra-handoff-v1',source_run=str(run_dir.resolve()),
        request_count=len(requests),requests_sha256=sha((output/'requests.jsonl').read_bytes()),
        source_lock_sha256=manifest['source_lock_sha256'],task_manifest_sha256=manifest['task_manifest_sha256'],
        model_execution='not_performed_by_export',default_scope='small 2-task x 2-arm pilot; larger study shelved by user'),indent=2),encoding='utf-8')
    return requests


def score(directory,result_path,model):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('evaluation_stage')=='bounded_repair':
        if sha(Path(manifest['original_results_path']).read_bytes())!=manifest['original_results_sha256']:
            raise ValueError('Original result receipt changed; repair budget lineage is stale')
    raw=(directory/'requests.jsonl').read_bytes()
    if sha(raw)!=manifest['requests_sha256']:raise ValueError('Handoff request digest mismatch')
    from .harness import ROOT
    if manifest['source_lock_sha256']!=sha((ROOT/'sources.lock.json').read_bytes()) or manifest['task_manifest_sha256']!=sha((ROOT/'tasks.json').read_bytes()):
        raise ValueError('Handoff source/task baseline mismatch')
    suite,files,_=load_suite();tasks={t['id']:t for t in suite['tasks']}
    requests={q['eval_id']:q for q in map(strict_json,raw.splitlines())};returned={};unknown=[]
    for line in Path(result_path).read_bytes().splitlines():
        if not line.strip():continue
        response=strict_json(line);eid=response['eval_id']
        if eid in returned:raise ValueError('Duplicate result ID')
        if eid not in requests:unknown.append(eid)
        returned[eid]=response
    outcomes=[]
    for eid,request in requests.items():
        result=returned.get(eid)
        if result is None:outcomes.append(dict(eval_id=eid,status='missing_result'));continue
        try:
            usage=result['usage'];answer=result['answer'];counter=TokenCounter(request['tokenizer'])
            valid_identity=(result['model']==model and result['prompt_sha256']==request['prompt_sha256'] and
                            isinstance(result['provider_request_id'],str) and bool(result['provider_request_id']))
            if request.get('model') is not None:valid_identity=valid_identity and result['model']==request['model']
            if any(type(usage[k]) is not int or usage[k]<0 for k in ('input_tokens','output_tokens')):raise ValueError('Invalid usage')
            local_total=counter.count(request)+counter.count(result)
            within_budget=(local_total<=request['total_input_output_limit'] and
                counter.count(answer)<=request['max_output_tokens'] and
                usage['input_tokens']+usage['output_tokens']<=request['total_input_output_limit'] and
                usage['output_tokens']<=request['max_output_tokens'])
            cumulative=None
            ledger=request.get('budget_ledger')
            if ledger:
                parent_usage=ledger['first_provider_usage']
                cumulative=dict(local_tokens=ledger['first_local_tokens']+local_total,
                    provider_tokens=parent_usage['input_tokens']+parent_usage['output_tokens']+usage['input_tokens']+usage['output_tokens'],
                    provider_output_tokens=parent_usage['output_tokens']+usage['output_tokens'],
                    local_answer_tokens=ledger['first_answer_local_tokens']+counter.count(answer))
                within_budget=within_budget and max(cumulative['local_tokens'],cumulative['provider_tokens'])<=ledger['original_total_limit']
                within_budget=within_budget and max(cumulative['provider_output_tokens'],cumulative['local_answer_tokens'])<=ledger['original_output_limit']
            if not valid_identity or not within_budget:
                outcomes.append(dict(eval_id=eid,status='identity_or_budget_failed',local_total_tokens=local_total));continue
            from .grounding import validate_actor_answer
            outcome=dict(eval_id=eid,status='recorded',local_total_tokens=local_total,provider_usage=usage,
                grounding_issues=validate_actor_answer(answer,request['prompt']),
                grade=grade(tasks[request['task_id']],answer,request['prompt']['evidence'],files))
            outcome['accepted']=outcome['grade']['passed'] and not outcome['grounding_issues']
            if cumulative:outcome['cumulative_budget']=cumulative
            outcomes.append(outcome)
        except (KeyError,TypeError,ValueError) as exc:outcomes.append(dict(eval_id=eid,status='invalid_result',error=str(exc)))
    report=dict(protocol='deepinfra-handoff-v1',model=model,results_sha256=sha(Path(result_path).read_bytes()),
                evaluation_stage=manifest.get('evaluation_stage','one_shot'),
                outcomes=outcomes,unknown_result_ids=unknown,
                limitations=['User-owned harness must enforce actual provider spend/output caps and archive provider requests',
                             'Reported provider usage/identity are trusted harness attestations, not independently verified billing',
                             'No missing, invalid or over-budget result is silently scored as a success'])
    destination=directory/('scores-'+sha(Path(result_path).read_bytes())[:16]+'.json')
    if destination.exists():raise ValueError('Score artifact already exists; preserved')
    destination.write_text(json.dumps(report,indent=2),encoding='utf-8');return report


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    ex=sub.add_parser('export');ex.add_argument('--run',type=Path,required=True);ex.add_argument('--output',type=Path,required=True)
    sc=sub.add_parser('score');sc.add_argument('--handoff',type=Path,required=True);sc.add_argument('--results',type=Path,required=True);sc.add_argument('--model',required=True)
    a=p.parse_args();result=export(a.run,a.output) if a.action=='export' else score(a.handoff,a.results,a.model)
    print(json.dumps(dict(exported_requests=len(result)) if a.action=='export' else result,indent=2))
