"""Prepare at most one oracle-free repair per failed recorded answer. No API calls.

python -m evaluation.prepare_repairs --directory ORIGINAL_RUN --output NEW_DIRECTORY
Each model subdirectory is a normal handoff consumable by evaluation.handoff score.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from geographer.model import canonical
from geographer.tokens import TokenCounter
from .grounding import validate_actor_answer
from .harness import sha,strict_json
from .repair_context import build_repair_prompt
from .transport_schema import compile_transport_schema


def prepare(directory,output):
    directory=Path(directory);output=Path(output)
    manifest=json.loads((directory/'handoff/manifest.json').read_text(encoding='utf-8'))
    raw=(directory/'handoff/requests.jsonl').read_bytes()
    if sha(raw)!=manifest['requests_sha256']:raise ValueError('Original request digest mismatch')
    requests={q['eval_id']:q for q in map(strict_json,raw.splitlines())}
    output.mkdir(parents=True,exist_ok=False);summary=[]
    for result_path in sorted((directory/'results').glob('*/results.jsonl')):
        plans=[];rows=[];seen=set();models=set()
        for line in result_path.read_bytes().splitlines():
            result=strict_json(line);eid=result['eval_id']
            if eid in seen:raise ValueError('Duplicate original result ID')
            seen.add(eid);models.add(result['model'])
            if eid not in requests:raise ValueError('Unknown original result ID')
            original=requests[eid]
            if result['prompt_sha256']!=original['prompt_sha256']:raise ValueError('Original prompt/result mismatch')
            if sha(canonical(original['prompt']).encode())!=original['prompt_sha256']:raise ValueError('Original prompt hash mismatch')
            if result.get('attempts') or result.get('repair_index',0):
                rows.append(dict(eval_id=eid,status='repair_limit_requires_review'));continue
            issues=validate_actor_answer(result['answer'],original['prompt'])
            if not issues:
                rows.append(dict(eval_id=eid,status='no_repair_needed'));continue
            if any(not i['retryable'] for i in issues):
                rows.append(dict(eval_id=eid,status='retrieval_blocked',issues=issues));continue
            usage=result['usage']
            if any(type(usage[k]) is not int or usage[k]<0 for k in ('input_tokens','output_tokens')):raise ValueError('Invalid recorded usage')
            counter=TokenCounter(original['tokenizer'])
            first_local=counter.count(original)+counter.count(result)
            first_provider=usage['input_tokens']+usage['output_tokens']
            first_output=max(counter.count(result['answer']),usage['output_tokens'])
            remaining=original['total_input_output_limit']-max(first_local,first_provider)
            remaining_output=original['max_output_tokens']-first_output
            if remaining<=0 or remaining_output<128:
                rows.append(dict(eval_id=eid,status='budget_blocked',issues=issues));continue
            prompt=build_repair_prompt(original['prompt'],result['answer'],issues)
            compiled=compile_transport_schema(prompt)
            request=dict(eval_id=eid,task_id=original['task_id'],arm=original['arm'],model=result['model'],
                prompt=prompt,prompt_sha256=sha(canonical(prompt).encode()),repair_index=1,
                max_output_tokens=remaining_output,total_input_output_limit=remaining,tokenizer=original['tokenizer'],
                response_format=compiled['response_format'],
                schema_transport={k:compiled[k] for k in ('profile','removed_constraints','full_schema_sha256','transport_schema_sha256','validation_required','fallback_policy')},
                parent=dict(prompt_sha256=original['prompt_sha256'],provider_request_id=result['provider_request_id'],
                            result_sha256=sha(canonical(result).encode())),
                budget_ledger=dict(first_local_tokens=first_local,first_provider_usage=copy.deepcopy(usage),
                    first_answer_local_tokens=counter.count(result['answer']),original_total_limit=original['total_input_output_limit'],
                    original_output_limit=original['max_output_tokens']))
            needed=counter.count(request)+remaining_output+256
            if needed>remaining:
                rows.append(dict(eval_id=eid,status='budget_blocked',required_local_reservation=needed,remaining_limit=remaining,issues=issues));continue
            plans.append(request)
            rows.append(dict(eval_id=eid,status='repair_prepared',issues=issues,
                repair_request_local_tokens=counter.count(request),remaining_total_limit=remaining,
                remaining_output_limit=remaining_output,first_provider_tokens=first_provider,
                omitted_records=prompt['repair_context']['omitted_record_count']))
        if len(models)>1:raise ValueError('Mixed models in a result file')
        missing=sorted(set(requests)-seen)
        rows.extend(dict(eval_id=eid,status='original_result_missing') for eid in missing)
        target=output/result_path.parent.name;target.mkdir()
        data=''.join(canonical(q)+'\n' for q in plans).encode()
        (target/'requests.jsonl').write_bytes(data)
        child_manifest=copy.deepcopy(manifest)
        child_manifest.update(request_count=len(plans),requests_sha256=sha(data),evaluation_stage='bounded_repair',
            source_run=str(directory.resolve()),original_results_sha256=sha(result_path.read_bytes()),
            original_results_path=str(result_path.resolve()),model=next(iter(models),None),
            model_execution='not_performed',max_additional_attempts=1,
            notes=['Only public validators selected repairs; no answer oracle or grader was used',
                   'Original one-shot scores/results remain unchanged; score these as a separate repair stage',
                   'Each request limit is the remaining original budget, not a fresh budget',
                   'User-owned harness must enforce API spend, record all attempts and preserve provider usage'])
        (target/'manifest.json').write_text(json.dumps(child_manifest,indent=2),encoding='utf-8')
        summary.append(dict(folder=result_path.parent.name,model=next(iter(models),None),repair_requests=len(plans),outcomes=rows))
    report=dict(protocol='bounded-recorded-repair-v1',models=summary,model_execution='not_performed',
        limitations=['A local validation pass is not independent answer correctness',
                     'Preflight token counts are local canonical JSON; provider usage must also stay within the remaining cap',
                     'No actual repair outcome, accuracy improvement or billable request is claimed'])
    (output/'repair-plan.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=prepare(args.directory,args.output)
    print(json.dumps([dict(model=m['model'],repair_requests=m['repair_requests']) for m in report['models']],indent=2))
