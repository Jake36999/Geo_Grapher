"""Replay the product FP9 detector on closed development evidence; no dispatch."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'output/phase67-gates/lib-wave4/src'))
from resource_librarian.code_recovery import protocol_request_format
from score_recovery_eval import correct
from register_recovery_eval import write_new

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--annotations',type=Path,default=ROOT/'data/eval/code-research/protocol-request-annotations.json');a=p.parse_args()
    directory=ROOT/'output/phase67-gates/review4'
    for stage in ('ab','pilot'):
        state=read(directory/(stage+'.cycle-state.json'))
        if state.get('status')!='closed' or not state.get('complete'):raise ValueError('Closed development collections required')
    annotations=read(a.annotations)['positive_episodes']
    keys={q['id']:q for q in read(ROOT/'data/eval/code-research/development30.json')['questions']}
    rows=read(directory/'ab.scored.json')+read(directory/'pilot.scored.json')
    confusion=Counter();summaries={};details=[]
    for row in rows:
        phase=row['phase'];qid=row['question_id'];fmt=protocol_request_format(row['answer']);detected=bool(fmt)
        expected=qid in annotations[phase]
        confusion[('true_' if detected==expected else 'false_')+('positive' if detected else 'negative')]+=1
        draft=row.get('first_attempt',{}).get('answer','')
        after=draft if detected and draft.strip() else ('' if detected else row['answer'])
        summary=summaries.setdefault(phase,dict(total=0,original_correct=0,offline_counterfactual_correct=0,triggered=0))
        summary['total']+=1;summary['original_correct']+=row['correct'];summary['offline_counterfactual_correct']+=correct(after,keys[qid]);summary['triggered']+=detected
        details.append(dict(phase=phase,id=qid,format=fmt,annotated=expected,prior_draft_available=bool(draft.strip()),
            original_correct=row['correct'],offline_counterfactual_correct=correct(after,keys[qid])))
    result=dict(paid_provider_calls=0,annotations=str(a.annotations.resolve()),confusion=dict(confusion),phases=summaries,rows=details,
        warning='Offline counterfactual retains recorded prior drafts. It is not a paid rerun, original-result rescore, or prediction of stochastic final-cycle accuracy.')
    write_new(a.out,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
