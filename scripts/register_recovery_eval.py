"""Seal one evaluation stage; never inspect held-out questions or answer keys."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from eval_readiness import fingerprint, graph_scope

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/phase67-gates/review4'
MODEL='Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo'
CATALOG=Path('D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/catalog.sqlite')
SEMDIR=Path('D:/Librarian_V2/tmp/geo-grapher-review4-models/potion-base-8M')
SEMCACHE=Path('D:/Librarian_V2/tmp/geo-grapher-review4-semantic-cache/qualified.sqlite')
SEMPY=Path('D:/Librarian_V2/tmp/geo-grapher-review4-semantic-env/Scripts/python.exe')
LIB=ROOT/'output/phase67-gates/lib-wave4'

def write_new(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,ensure_ascii=False)

def configuration(wheel,questions,self_check):
    return dict(mode='bench',catalog=str(CATALOG),model=MODEL,context_tokens=1048576,
        preset='lead',scoping='library',launch='uvx',bundles='off',wheel=str(wheel),
        question_file=str(questions),self_check=self_check,
        semantic_model='model2vec:'+str(SEMDIR),semantic_cache=str(SEMCACHE),semantic_python=str(SEMPY))

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['ab','pilot','final'])
    p.add_argument('--wheel',type=Path,required=True);p.add_argument('--estimated-remaining',type=float,required=True)
    a=p.parse_args();wheel=a.wheel.resolve()
    dev=ROOT/'data/eval/code-research/development30.questions.json'
    original=ROOT/'data/eval/code-research/original5.questions.json'
    heldout=OUT/'heldout-v2/questions.sealed.json'
    if a.stage=='ab':specs=[('ab-off',dev,'off',30),('ab-on',dev,'on',30)]
    elif a.stage=='pilot':specs=[('pilot',dev,'on',30)]
    else:specs=[(f'final-{group}-{run}',question,'on',count) for run in (1,2,3)
                for group,question,count in [('heldout',heldout,25),('dev',original,5)]]
    phases={};paths=[wheel,SEMCACHE,*SEMDIR.rglob('*')]
    paths=[x for x in paths if x.is_file()]
    paths+=list((ROOT/'src/geographer').rglob('*.py'))+list((LIB/'src').rglob('*.py'))
    paths+=list((ROOT/'scripts').glob('*.py'))
    paths+=[ROOT/'reports/PHASE67_REVIEW4_BUDGET_APPROVAL.json',ROOT/'reports/PHASE67_REVIEW4_MODEL_CARD.json',
            ROOT/'data/eval/code-research/development30.json',ROOT/'reports/PHASE67_HELDOUT_V2_SEAL.json']
    remaining=a.estimated_remaining
    for name,question,check,count in specs:
        config=configuration(wheel,question,check);paths.append(question)
        phases[name]=dict(configuration=config,episodes=count,out=str(OUT/(name+'.raw.json')),
            started_receipt=str(OUT/(name+'.started.json')),episode_directory=str(OUT/'episodes'/name),
            estimated_remaining_usd=remaining)
        # Planning only: actual ledger spend is checked again before every phase.
        remaining=max(0.,remaining-count*.03284740496)
    seal=json.loads((ROOT/'reports/PHASE67_HELDOUT_V2_SEAL.json').read_text(encoding='utf-8'))
    value=dict(status='registered',stage=a.stage,registered_at=datetime.now(timezone.utc).isoformat(),
        model=MODEL,rate_card=dict(input_per_1m=.3,output_per_1m=1.),
        source_inputs=fingerprint(paths),graph_scope=graph_scope(CATALOG,['ToolSet','librarian-v2']),phases=phases,
        heldout_seal=seal,temperature=.2,ordinary_step_limit=12,extra_step_limit=3,extra_model_invocation_limit=2,
        scoring='Original five: all frozen legacy markers; repaired dev/v2: any sealed equivalence marker, case-sensitive substring. No post-run key edits or citation-based score overrides.',
        fp4_decision='Keep default self-check only if paired ON yields at least one net additional correct answer and no additional wrong-graph/withheld. Pilot/final explicitly enable all recoveries as owner requested; report default recommendation separately.',
        pass_marks=dict(heldout_overall=64,heldout_each_run=20,development_each_run=5,wrong_graph=0,withheld=0,mean_calls_max=10),
        closure='Exactly one cycle. Collect all raw batches before opening v2 keys; stop afterwards whatever result. No replacement, resume, merge or push.')
    destination=OUT/(a.stage+'.registration.json');write_new(destination,value)
    print(json.dumps(dict(registration=str(destination),phases=list(phases),estimated_remaining_usd=a.estimated_remaining)))

if __name__=='__main__':main()
