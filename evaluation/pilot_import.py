"""Grade archived actual subagent answers; never synthesizes participant answers."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .harness import load_suite,grade,sha
from geographer.tokens import TokenCounter


def run(directory):
    directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    suite,files,_=load_suite();tasks={t['id']:t for t in suite['tasks']};counter=TokenCounter();results=[]
    for item in manifest['items']:
        path=Path(item['path']);input_raw=path.read_bytes()
        if sha(input_raw)!=item['sha256']:raise ValueError('Pilot input hash mismatch')
        prompt=json.loads(input_raw);answer_path=directory/(item['name']+'.answer.json')
        if not answer_path.exists():
            results.append(dict(name=item['name'],status='missing_response'));continue
        answer_raw=answer_path.read_bytes();answer=json.loads(answer_raw)
        task_id=item['name'].split('-',1)[0];task=tasks[task_id]
        if prompt['question']!=task['question']:raise ValueError('Pilot question mismatch')
        rendered_input_tokens=len(counter.encoding.encode_ordinary(input_raw.decode('utf-8')))
        rendered_answer_tokens=len(counter.encoding.encode_ordinary(answer_raw.decode('utf-8')))
        results.append(dict(name=item['name'],status='actual_subagent_response',answer_sha256=sha(answer_raw),
            canonical_prompt_tokens=item['canonical_prompt_tokens'],rendered_input_file_tokens=rendered_input_tokens,
            rendered_answer_tokens=rendered_answer_tokens,within_visible_region_cap=rendered_input_tokens+rendered_answer_tokens<=manifest['visible_input_output_cap'],
            within_output_cap=rendered_answer_tokens<=manifest['output_limit'],grade=grade(task,answer,prompt['evidence'],files)))
    report=dict(protocol='p55-subagent-pilot-v1',results=results,
        limitations=['Actual independent Codex subagents, no inherited parent conversation; two tasks, two arms, one trial',
                     'Inputs read with one tool call; model version/provider usage/system/tool framing not exposed, so whole-provider-token acceptance remains open',
                     'This is an authorized small pilot, not the deferred DeepInfra benchmark or a superiority study',
                     'rubric v2 corrects false negatives from extra valid scope labels; strict v1 fact-set matches are retained',
                     'The rubric revision occurred after pilot answers; scores are diagnostic, not held-out confirmation'])
    (directory/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args();run(args.directory)
