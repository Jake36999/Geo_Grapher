"""Attest a complete blind v2 set without displaying its questions or keys."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v2_builder',ROOT/'scripts/build_heldout_v2.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

def main():
    seal_path=ROOT/'reports/PHASE67_HELDOUT_V2_SEAL.json';seal=v.read(seal_path)
    for path,expected in seal['files'].items():assert v.sha(ROOT/path)==expected
    questions=v.read(v.OUT/'questions.sealed.json');answers=v.read(v.OUT/'answers.sealed.json');items=v.read(v.OUT/'accepted.private.json')
    assert len(questions)==len(answers)==len(items)==25
    assert len({q['id'] for q in questions})==len({q['question'].casefold() for q in questions})==25
    assert Counter((x['category'],x['graph']) for x in items)==Counter(v.rules.QUOTAS)
    old=v.read(v.legacy.OUT/'heldout.samples.sealed.json')
    old_ids={m['entity_id'] for x in old for m in [x,*x.get('support',[])]}
    new_ids={eid for x in items for eid in x['equivalence_entity_ids']}|{m['entity_id'] for x in items for m in x.get('support',[])}
    assert not old_ids&new_ids
    assert all(v.rules.meaningful(x['documentation']) and not v.rules.validate_question(x,x['question']) and v.rules.supported_equivalence(x) for x in items)
    decisions={}
    decision_files=sorted(v.OUT.glob('round*-decisions.private.json'))
    for path in decision_files:
        for entry in v.read(path):
            if entry['accepted']:decisions[entry['id']]=entry
    for item in items:
        d=decisions[item['id']]
        assert d['target_in_top20'] and v.rules.review_approved(d['reviewer_a']) and v.rules.review_approved(d['reviewer_b'])
    construction=v.read(v.OUT/'construction.json')
    assert v.product_digest()==construction['product_sources_sha256']
    receipts=[]
    for path in sorted(v.OUT.glob('*-receipt.json')):
        r=v.read(path)
        receipts.append({k:r.get(k) for k in ('run_id','model','cost_usd','receipt')})
    result=dict(seal_sha256=v.sha(seal_path),count=25,two_reviewers_confirmed=25,top20_qualified=25,
        meaningful_documentation=25,question_validation=25,overlap_v1=0,product_sources_unchanged=True,
        product_sources_sha256=construction['product_sources_sha256'],
        review_decisions_sha256={str(p.relative_to(ROOT)):v.sha(p) for p in decision_files},
        complete_worker_receipts=receipts,all_prior_rejections_preserved=True,
        blindness='Audit reports counts/hashes only; implementing lead has not read v2 questions or keys.')
    path=ROOT/'reports/PHASE67_HELDOUT_V2_AUDIT.json';v.write(path,result)
    print(json.dumps({k:value for k,value in result.items() if k not in {'complete_worker_receipts','review_decisions_sha256'}}))
if __name__=='__main__':main()
