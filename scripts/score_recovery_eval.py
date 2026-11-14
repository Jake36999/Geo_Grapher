"""Score only closed, complete registered collections; retain first drafts separately."""
from collections import Counter,defaultdict
import argparse
import json
from pathlib import Path
from register_recovery_eval import ROOT,write_new
from eval_readiness import fingerprint

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def validate_seal(seal,root):
    import hashlib
    for relative,expected in seal['files'].items():
        path=(root/relative).resolve()
        if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Sealed file changed; scoring blocked')

def correct(answer,key):
    hits=[m for m in key['markers'] if m in answer]
    return len(hits)==len(key['markers']) if key.get('legacy_marker_required') else bool(hits)

def main():
    p=argparse.ArgumentParser();p.add_argument('registration',type=Path);a=p.parse_args()
    reg=read(a.registration);directory=a.registration.parent;state=read(directory/(reg['stage']+'.cycle-state.json'))
    if state.get('status')!='closed' or not state.get('complete'):raise ValueError('No keys before complete collection closure')
    if fingerprint(reg['source_inputs'])!=reg['source_inputs']:raise ValueError('Candidate changed during collection')
    all_rows={name:read(phase['out']) for name,phase in reg['phases'].items()}
    for name,rows in all_rows.items():
        expected=read(reg['phases'][name]['configuration']['question_file'])
        if [r['question_id'] for r in rows]!=[q['id'] for q in expected]:raise ValueError('Question sequence mismatch')
    keys={q['id']:q for q in read(ROOT/'data/eval/code-research/development30.json')['questions']}
    if reg['stage']=='final':
        # First key read occurs here, after all six raw collections and closure checks.
        validate_seal(reg['heldout_seal'],ROOT)
        keys.update({q['id']:q for q in read(directory/'heldout-v2/answers.sealed.json')})
    summaries=[];scored=[];patterns=defaultdict(Counter)
    for name,rows in all_rows.items():
        for row in rows:
            key=keys[row['question_id']];row['correct']=correct(row['answer'],key)
            first=row.get('first_attempt',{});eligible=first.get('status')=='unrecovered_draft'
            row['first_attempt_correct']=correct(first.get('answer',''),key) if eligible else None
            row['phase']=name
            for recovery in row.get('recoveries',[]):
                counter=patterns[recovery['pattern']];counter['triggered']+=1
                counter['signal_resolved']+=recovery.get('outcome')=='resolved';counter['final_correct']+=row['correct']
                counter['eligible_first_draft']+=eligible
                counter['wrong_to_right']+=eligible and not row['first_attempt_correct'] and row['correct']
            scored.append(row)
        summaries.append(dict(phase=name,total=len(rows),correct=sum(r['correct'] for r in rows),
            first_attempt_correct=sum(r['first_attempt_correct'] is True for r in rows),first_attempt_eligible=sum(r['first_attempt_correct'] is not None for r in rows),
            calls=sum(r['tool_calls'] for r in rows),wrong_graph=sum(r['wrong_graph_calls'] for r in rows),
            withheld=sum(r['withheld_oversize'] for r in rows),tool_errors=sum(r['tool_errors'] for r in rows),
            cost_usd=sum(read(r['episode_receipt'])['charged_usd'] for r in rows)))
    count=sum(r['total'] for r in summaries);calls=sum(r['calls'] for r in summaries)
    passed=None
    if reg['stage']=='final':
        held=[r for r in summaries if 'heldout' in r['phase']];dev=[r for r in summaries if '-dev-' in r['phase']]
        passed=sum(r['correct'] for r in held)>=64 and all(r['correct']>=20 for r in held) and all(r['correct']==5 for r in dev)
        passed=passed and not sum(r['wrong_graph']+r['withheld'] for r in summaries) and calls/count<=10
    report=dict(stage=reg['stage'],runs=summaries,patterns=dict(patterns),passed=passed,mean_calls=calls/count,
        interpretation='Pattern outcomes are runtime signals; co-occurring recoveries are not independent causal attribution. Early recovered/no-draft episodes have no invented counterfactual first-attempt score.')
    if reg['stage']=='ab':
        off,on=summaries;report['fp4_keep_default']=on['correct']>off['correct'] and on['wrong_graph']<=off['wrong_graph'] and on['withheld']<=off['withheld']
    write_new(directory/(reg['stage']+'.scored.json'),scored);write_new(directory/(reg['stage']+'.summary.json'),report)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
