"""Run only the owner's preregistered three attempts; retain per-run cost receipts."""
import ast,hashlib,json,sqlite3,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/phase67-gates/wave4'
LEDGER=Path('D:/Librarian_V2/tmp/deepinfra-delegation/ledger.json')
PY='D:/Librarian_V2/.venv/Scripts/python.exe'
REPORT=ROOT/'reports/PHASE67_WAVE4_GATE.md'
CATALOG=Path('D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/catalog.sqlite')
WHEEL=OUT/'continuation-dist2/geo_grapher-0.1.1-py3-none-any.whl'
EXPECTED_WHEEL='07870422dcc7c758079929379ceb78015d6f8599a5016e13f093d8b1a25b3864'
EXPECTED_SNAPSHOT='snapshot:1703964f018a8f5981c139069836a87178098924bd94383d5788c083bb89c9bf'

def seal():
    wheel=hashlib.sha256(WHEEL.read_bytes()).hexdigest()
    with sqlite3.connect(CATALOG.resolve().as_uri()+'?mode=ro',uri=True) as connection:
        snapshot=connection.execute("SELECT snapshot_id FROM graphs WHERE label='librarian-v2'").fetchone()[0]
    if wheel!=EXPECTED_WHEEL or snapshot!=EXPECTED_SNAPSHOT:raise SystemExit('Registered wheel or snapshot changed; stop before dispatch')
    files=[ROOT/'scripts/librarian_harness.py',ROOT/'scripts/eval_graph_leakage.py',ROOT/'.superpowers/sdd/2026-11-11-phase6-7-04-wave4-librarian/budgeted_harness.py']
    harness={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    tree=ast.parse(files[0].read_text(encoding='utf-8'))
    questions=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CODE_BENCH' for t in n.targets))
    return dict(wheel_sha256=wheel,snapshot=snapshot,harness_sha256=harness,questions=questions,model='Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo',context_tokens=1048576,preset='lead',scoping='library',max_steps=12)


def main():
    paths=[OUT/f'code-continuation-cycle-run{i}.json' for i in (1,2,3)]
    if any(p.exists() for p in paths):raise SystemExit('Preserve the registered first runs; do not repeat this cycle')
    reserved=paths+[OUT/'code-continuation-cycle-summary.json']+[OUT/f'code-continuation-cycle-run{i}-cost.json' for i in (1,2,3)]
    seal_path=OUT/'code-continuation-cycle-seal.json'
    if any(p.exists() for p in reserved) or seal_path.exists():raise SystemExit('Cycle already started; preserve all first evidence and escalate')
    frozen=seal()
    with seal_path.open('x',encoding='utf-8') as output:json.dump(frozen,output,indent=2)
    results=[]
    for index,path in enumerate(paths,1):
        if seal()!=frozen:raise SystemExit('Frozen cycle inputs changed; no dispatch')
        before={r['run_id'] for r in json.loads(LEDGER.read_text())['calls']}
        cmd=[PY,'-I',str(ROOT/'.superpowers/sdd/2026-11-11-phase6-7-04-wave4-librarian/budgeted_harness.py'),
            'bench','--catalog',str(CATALOG),'--model','Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo',
            '--context-tokens','1048576','--preset','lead','--scoping','library','--launch','uvx',
            '--wheel',str(WHEEL),'--out',str(path)]
        with (ROOT/f'output/w4-continuation-cycle-run{index}.log').open('w',encoding='utf-8') as log:
            proc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        ledger=json.loads(LEDGER.read_text());new=[r for r in ledger['calls'] if r['run_id'] not in before and r['task']=='w4-benchmark' and r['pool']=='geo-grapher']
        receipt=dict(run=index,attempts=len(new),cost_usd=sum(r['charged_usd'] for r in new),run_ids=[r['run_id'] for r in new],pool=ledger['pools']['geo-grapher'])
        (OUT/f'code-continuation-cycle-run{index}-cost.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        if proc.returncode:raise SystemExit(f'Run {index} interrupted; preserve partial file and escalate, exit {proc.returncode}')
        if seal()!=frozen:raise SystemExit('Frozen cycle inputs changed during run; preserve evidence and escalate')
        rows=json.loads(path.read_text(encoding='utf-8'));assert len(rows)==5
        r=dict(run=index,file=path.name,markers=sum(len(q['markers_found']) for q in rows),
            calls=sum(q['tool_calls'] for q in rows),wrong_graph=sum(q['wrong_graph_calls'] for q in rows),
            withheld=sum(q['withheld_oversize'] for q in rows),tool_errors=sum(not c['success'] for q in rows for c in q['per_call']),
            cost_usd=receipt['cost_usd'])
        results.append(r)
        with REPORT.open('a',encoding='utf-8') as report:
            report.write(f"\nRegistered continuation run {index}: **{r['markers']}/5**, {r['calls']/5:.1f} calls/question, {r['wrong_graph']} wrong-graph, {r['withheld']} withheld, {r['tool_errors']} tool errors; metered planning-rate cost **${r['cost_usd']:.7f}** across {receipt['attempts']} HTTP attempts. First file: `{path.name}`.\n")
        print(json.dumps(r),flush=True)
    passed=all(r['markers']>=3 and r['wrong_graph']==r['withheld']==0 for r in results) and sum(r['markers'] for r in results)>=12 and sum(r['calls'] for r in results)/15<=8
    summary=dict(seal_file=seal_path.name,runs=results,total_markers=sum(r['markers'] for r in results),total=15,calls_per_question=sum(r['calls'] for r in results)/15,passed=passed)
    (OUT/'code-continuation-cycle-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with REPORT.open('a',encoding='utf-8') as report:report.write(f"\nContinuation cycle verdict: **{'PASS' if passed else 'FAIL; escalate; no extra model run'}**, {summary['total_markers']}/15 markers; {summary['calls_per_question']:.2f} calls/question across all 15 questions. All three rows above are retained.\n")
    print(json.dumps(summary),flush=True)
    raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
