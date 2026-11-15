"""One diagnostic A/B and one sealed quality cycle; no automatic repeat path."""
import argparse
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tokenize

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/phase67-gates/code-quality-track'
LIB=ROOT/'output/phase67-gates/lib-wave4'
PY='D:/Librarian_V2/.venv/Scripts/python.exe'
CATALOG=Path('D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/catalog.sqlite')
LEDGER=Path('D:/Librarian_V2/tmp/deepinfra-delegation/ledger.json')
WHEEL=OUT/'quality-dist/geo_grapher-0.1.1-py3-none-any.whl'
SEAL=ROOT/'reports/PHASE67_CODE_QUALITY_HELDOUT_SEAL.json'
REGISTRATION=ROOT/'reports/PHASE67_CODE_QUALITY_FINAL_REGISTRATION.json'
REPORT=ROOT/'reports/PHASE67_CODE_QUALITY_TRACK.md'
GATE=ROOT/'reports/PHASE67_WAVE4_GATE.md'
WRAPPER=ROOT/'.superpowers/sdd/2026-11-11-phase6-7-04-wave4-librarian/budgeted_harness.py'
MODEL='Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def create(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False)
def append(text):
    for path in (REPORT,GATE):
        with path.open('a',encoding='utf-8') as f:f.write('\n'+text+'\n')

def frozen():
    seal=read(SEAL)
    for name,expected in seal['files'].items():
        if sha(ROOT/name)!=expected:raise SystemExit('Held-out seal mismatch; no dispatch')
    with sqlite3.connect(CATALOG.resolve().as_uri()+'?mode=ro',uri=True) as db:
        snapshots={label:db.execute('SELECT snapshot_id FROM graphs WHERE label=?',(label,)).fetchone()[0] for label in seal['snapshots']}
    if snapshots!=seal['snapshots']:raise SystemExit('Frozen snapshot mismatch')
    source={str(p.relative_to(LIB/'src')):sha(p) for p in sorted((LIB/'src').rglob('*.py'))}
    # Only public route configuration is loaded. No question/key content is read.
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from resource_librarian.agent_runtime import DEFAULT_PROFILES;print(json.dumps(DEFAULT_PROFILES["code-research"].route_policy,sort_keys=True))'
    policy=json.loads(subprocess.check_output([PY,'-I','-c',code,str(LIB/'src')],cwd='F:/uv-data',text=True))
    if policy.get('temperature')!=0.2:raise SystemExit('Production code profile must use temperature 0.2')
    harness=[ROOT/'scripts/librarian_harness.py',ROOT/'scripts/eval_graph_leakage.py',WRAPPER,Path(__file__).resolve()]
    return dict(track='post-wave4-code-quality',wheel_sha256=sha(WHEEL),wheel=str(WHEEL),
        librarian_runtime_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),
        harness_sha256={str(p.relative_to(ROOT)):sha(p) for p in harness},heldout_seal_sha256=sha(SEAL),
        heldout_files=seal['files'],snapshots=snapshots,model=MODEL,context_tokens=1048576,preset='lead',scoping='library',
        max_steps=12,final_synthesis='existing guarded tool-free step-limit synthesis only',production_route_policy=policy,
        dispatch_meter_sha256=sha(Path('D:/Librarian_V2/scripts/delegate_deepinfra.py')),
        dev_pass=15,heldout_pass=68,heldout_per_run=22,wrong_graph=0,withheld=0,max_mean_calls=8,
        heldout_scoring='case-sensitive defining identifier with word boundaries; key loaded only after all six raw runs finish',
        cycle_count=1,episodes=90,no_repeated_cycles=True)

def dispatch(label,questions=None,self_check=None):
    path=OUT/(label+'.json');cost_path=OUT/(label+'-cost.json')
    if path.exists() or cost_path.exists():raise SystemExit('First result already exists; no repeat')
    before={r['run_id'] for r in read(LEDGER)['calls']}
    cmd=[PY,'-I',str(WRAPPER),'bench','--catalog',str(CATALOG),'--model',MODEL,'--context-tokens','1048576',
         '--preset','lead','--scoping','library','--launch','uvx','--wheel',str(WHEEL),'--out',str(path)]
    if questions:cmd+=['--question-file',str(questions)]
    if self_check is not None:cmd+=['--self-check','on' if self_check else 'off']
    with (OUT/(label+'.log')).open('x',encoding='utf-8') as log:
        proc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    ledger=read(LEDGER);calls=[r for r in ledger['calls'] if r['run_id'] not in before and r['pool']=='geo-grapher']
    temperatures=sorted({r.get('temperature') for r in calls},key=str)
    create(cost_path,dict(label=label,cost_usd=sum(r['charged_usd'] for r in calls),attempts=len(calls),run_ids=[r['run_id'] for r in calls],temperatures=temperatures,exit_code=proc.returncode))
    if proc.returncode:raise SystemExit('Interrupted batch: preserve partial evidence; no restart')
    if temperatures!=[0.2]:raise SystemExit('Actual HTTP temperature differs from production; preserve evidence and stop')
    return read(path),read(cost_path)

def metrics(rows):
    return dict(correct=sum(bool(r.get('markers_found')) for r in rows),total=len(rows),calls=sum(r['tool_calls'] for r in rows),
        wrong_graph=sum(r['wrong_graph_calls'] for r in rows),withheld=sum(r['withheld_oversize'] for r in rows),
        tool_errors=sum(not c['success'] for r in rows for c in r['per_call']),
        self_check_rejected=sum(r.get('self_check_rejected',0) for r in rows))

def ab():
    baseline=frozen();create(OUT/'ab-started.json',baseline)
    results=[]
    for enabled in (False,True):
        if frozen()!=baseline:raise SystemExit('A/B candidate changed')
        rows,cost=dispatch('ab-'+('on' if enabled else 'off'),self_check=enabled)
        if len(rows)!=5:raise SystemExit('Incomplete diagnostic run')
        result=dict(enabled=enabled,**metrics(rows),cost_usd=cost['cost_usd']);results.append(result)
        append('Diagnostic P3 A/B '+('ON' if enabled else 'OFF')+': `'+json.dumps(result,sort_keys=True)+'`.')
        print(json.dumps(result),flush=True)
    off,on=results
    keep=(on['correct']>off['correct'] and on['wrong_graph']==on['withheld']==on['self_check_rejected']==0 and on['calls']/5<=8)
    create(OUT/'ab-summary.json',dict(runs=results,keep_p3=keep))
    append('Diagnostic A/B decision: **'+('retain P3' if keep else 'do not retain P3')+'** under the predeclared criterion. No repeat A/B.')

def register():
    candidate=frozen();create(REGISTRATION,candidate)
    append('## Registered single final quality-track cycle\n\nRegistration: `reports/'+REGISTRATION.name+'`, SHA256 `'+sha(REGISTRATION)+'`. '
        'This is the only authorised quality-track cycle: dev 15/15; held-out >=68/75 and >=22/25 per run; zero wrong-graph/withheld; mean calls <=8. '
        '90 episodes, three runs each, at the registered production profile. No product changes, replacement questions or extra cycle; stop whatever the result.')
    print(json.dumps(dict(registered=True,sha256=sha(REGISTRATION),production_route_policy=candidate['production_route_policy'])))

SOURCE_CACHE={}

def source_lines(graph,entity_id,source=None):
    """Read original frozen source, never a working tree or regenerated index."""
    source=source or {};key=(graph,entity_id,source.get('repo_id'),source.get('rel_path'))
    if key not in SOURCE_CACHE:
        with sqlite3.connect(CATALOG.resolve().as_uri()+'?mode=ro',uri=True) as catalog:
            path,sid=catalog.execute('SELECT code_database,snapshot_id FROM graphs WHERE label=?',(graph,)).fetchone()
        with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as db:
            repo,relpath=db.execute('SELECT repo_id,rel_path FROM entities WHERE snapshot_id=? AND entity_id=?',(sid,entity_id)).fetchone()
            repo=source.get('repo_id',repo);relpath=source.get('rel_path',relpath)
            rows=db.execute("SELECT a.result_json FROM analysis_results a JOIN entities e ON e.snapshot_id=a.snapshot_id AND e.entity_id=json_extract(a.scope_json,'$.entity_id') WHERE a.snapshot_id=? AND a.algorithm_version='source-bytes-v1' AND e.repo_id=? AND json_extract(a.result_json,'$.rel_path')=?",(sid,repo,relpath)).fetchall()
            if len(rows)!=1:raise ValueError('Source provenance is not unique in the frozen snapshot')
            raw=base64.b64decode(json.loads(rows[0][0])['bytes_base64'])
            encoding,_=tokenize.detect_encoding(io.BytesIO(raw).readline)
            SOURCE_CACHE[key]=(relpath,raw.decode(encoding).splitlines(keepends=True))
    return SOURCE_CACHE[key]

def verify_delivery(coverage,key):
    verified=[];invalid=[]
    for row in coverage:
        if row['start_line'] is None:continue
        try:
            path,lines=source_lines(key['graph'],key['entity_id'],row.get('source'))
            a,b=row['start_line'],row['end_line']
            matches=1<=a<=b<=len(lines) and hashlib.sha256(''.join(lines[a-1:b]).encode('utf-8')).hexdigest()==row['sha256']
            if not matches:raise ValueError('Returned range hash does not match snapshot bytes')
            verified.append(dict(row,source_path=path,definition_line_returned=path==key['source'] and a<=key['span'][0]<=b))
        except (ValueError,TypeError,IndexError,sqlite3.Error) as exc:
            invalid.append(dict(row,verification_error=str(exc)[:200]))
    return verified,invalid

def score_heldout(rows,keys):
    import re
    scored=[]
    for row in rows:
        key=keys[row['question_id']];marker=key['marker'];found=bool(re.search(r'(?<!\w)'+re.escape(marker)+r'(?!\w)',row['answer']))
        coverage=[c for call in row['per_call'] for c in call.get('coverage',[]) if c['entity_id']==key['entity_id']]
        supplemental=any(key['entity_id'] in call.get('supplemental_entities',[]) for call in row['per_call'])
        verified,invalid=verify_delivery(coverage,key)
        delivered=bool(verified)
        limited=any(c.get('coverage_truncated') for c in row['per_call'])
        classification=None if found else 'delivered_not_used' if delivered else 'unknown_invalid_coverage' if invalid else 'retrieved_not_opened' if coverage or supplemental else 'unknown_clipped_evidence' if limited else 'not_retrieved'
        scored.append(dict(row,markers=[marker],markers_found=[marker] if found else [],coverage_classification=classification,
                           target_entity_id=key['entity_id'],target_source=key['source'],target_span=key['span'],target_coverage=coverage,
                           verified_target_source=verified,invalid_target_source=invalid,
                           definition_line_returned=any(c['definition_line_returned'] for c in verified)))
    return scored

def cycle():
    registered=read(REGISTRATION)
    if frozen()!=registered:raise SystemExit('Registered product changed before dispatch')
    state=OUT/'final-cycle-state.json';create(state,dict(status='running',registration_sha256=sha(REGISTRATION)))
    complete=False
    try:
        batches=[]
        for index in (1,2,3):
            for group,total in [('dev',5),('heldout',25)]:
                if frozen()!=registered:raise SystemExit('Frozen input changed; stop without replacement')
                rows,cost=dispatch(f'final-{group}-run{index}',OUT/'heldout.questions.sealed.json' if group=='heldout' else None)
                if len(rows)!=total:raise SystemExit('Incomplete run; preserve evidence')
                batches.append((group,index,rows,cost))
                print(json.dumps(dict(collected=group,run=index,episodes=len(rows),cost_usd=cost['cost_usd'])),flush=True)
        if frozen()!=registered:raise SystemExit('Frozen input changed during collection')
        # First key read: all 90 episodes have finished. Never use it for prompts.
        keys={k['id']:k for k in read(OUT/'heldout.answers.sealed.json')}
        summaries=[]
        for group,index,rows,cost in batches:
            if group=='heldout':
                rows=score_heldout(rows,keys);create(OUT/f'final-heldout-run{index}-scored.json',rows)
            result=dict(group=group,run=index,**metrics(rows),cost_usd=cost['cost_usd']);summaries.append(result)
            append('Final quality cycle '+group+' run '+str(index)+': `'+json.dumps(result,sort_keys=True)+'`.')
        dev=[r for r in summaries if r['group']=='dev'];heldout=[r for r in summaries if r['group']=='heldout']
        dev_correct=sum(r['correct'] for r in dev);heldout_correct=sum(r['correct'] for r in heldout);mean=sum(r['calls'] for r in summaries)/90
        passed=(dev_correct==15 and heldout_correct>=68 and all(r['correct']>=22 for r in heldout)
                and all(r['wrong_graph']==r['withheld']==0 for r in summaries) and mean<=8
                and sum(r['calls'] for r in dev)/15<=8 and sum(r['calls'] for r in heldout)/75<=8)
        summary=dict(runs=summaries,development_correct=dev_correct,development_total=15,heldout_correct=heldout_correct,heldout_total=75,
                     calls_per_question=mean,passed=passed,cost_usd=sum(r['cost_usd'] for r in summaries),evaluation_closed=True,no_repeat=True)
        create(OUT/'final-cycle-summary.json',summary);complete=True
        append('Final quality-track verdict: **'+('PASS' if passed else 'FAIL')+'**. `'+json.dumps(summary,sort_keys=True)+'`. Evaluation is closed; no further model dispatch. Wave-4 release gate remains closed at 12/15.')
        print(json.dumps(summary),flush=True)
    finally:
        state.write_text(json.dumps(dict(status='closed',complete=complete,no_repeat=True),indent=2),encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['ab','register','cycle']);a=p.parse_args()
    {'ab':ab,'register':register,'cycle':cycle}[a.mode]()
