"""Actual registry/MCP dry runs for the funded code-evaluation paths."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import uuid
from eval_readiness import ticket


def objects(value):
    if isinstance(value,str):
        try:yield from objects(json.loads(value))
        except ValueError:pass
    elif isinstance(value,dict):
        yield value
        for key,item in value.items():
            if key not in {'text','why','doc_gist'}:yield from objects(item)
    elif isinstance(value,list):
        for item in value:yield from objects(item)


def preflight(args,out):
    import librarian_harness as h
    from resource_librarian.providers import Provider,Reply,ToolCall
    if args.mode!='bench' or args.preset not in {'lead','code'} or args.scoping!='library':
        raise ValueError('This paid path has no qualified no-model fixture; dispatch blocked')
    if args.bundles!='off' or args.wheel is None or args.launch!='uvx':raise ValueError('Funded preflight requires the exact installed wheel, uvx and tool preset')
    config={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items() if k not in {'dry_run','out','resume'}}
    labels=[args.graph_label]
    if args.question_file:
        questions=json.loads(args.question_file.read_text(encoding='utf-8'))
        labels=sorted({q['graph'] for q in questions})
    targets={}
    from eval_readiness import graph_scope
    config['graph_scope']=graph_scope(args.catalog,labels)
    with sqlite3.connect(args.catalog.resolve().as_uri()+'?mode=ro',uri=True) as catalog:
        for label in labels:
            row=catalog.execute('SELECT graph_id,code_database,snapshot_id FROM graphs WHERE label=?',(label,)).fetchone()
            if row is None or not row[1]:raise ValueError('Code dry-run graph is unavailable')
            with sqlite3.connect(Path(row[1]).resolve().as_uri()+'?mode=ro',uri=True) as db:
                entities=db.execute("SELECT e.qualified_name,a.result_json FROM entities e JOIN analysis_results a ON a.snapshot_id=e.snapshot_id AND a.analysis_id='declaration:'||e.entity_id WHERE e.snapshot_id=? AND e.kind='function' AND e.is_test=0 AND e.is_external=0 AND e.end_line-e.start_line BETWEEN 1 AND 8 ORDER BY e.qualified_name",(row[2],)).fetchall()
            from resource_librarian.code_recovery import words
            chosen=next(((name,json.loads(raw).get('docstring','')) for name,raw in entities
                if isinstance(json.loads(raw).get('docstring'),str) and len(words(json.loads(raw)['docstring'][:65]))>=2),None)
            if chosen is None:raise ValueError('No short documented source fixture in graph')
            targets[label]=dict(name=chosen[0],question=f'Which implementation matches {chosen[0]}? {chosen[1][:65]}')
    temperatures=[]
    class Offline(Provider):
        name='no-model-readiness'
        def __init__(self,kind='fp3'):self.temperatures=[];self.kind=kind
        def chat(self,system,messages,tools,max_tokens=4096,temperature=None):
            self.temperatures.append(temperature)
            temperatures.append(temperature)
            # Each episode is a new Loop; decide from its actual message ledger.
            user=next(m['content'] for m in messages if m.get('role')=='user')
            label=next(label for label in labels if f"Graph: '{label}'" in user)
            returned=[m for m in messages if m.get('role')=='tool']
            names={spec.name.rsplit('__',1)[-1]:spec.name for spec in tools}
            if not tools:
                if self.kind=='xml':return Reply(text='<tool_call><function=get_entity_content></function></tool_call>')
                records=[item for message in returned for item in objects(message.get('content',''))]
                found=next((item for item in records if item.get('qualified_name')==targets[label]['name'] and item.get('entity_id')),None)
                return Reply(text=f"The directly defining implementation is {targets[label]['name']}. {found.get('cite_as','')}" if found else 'Evidence incomplete; source not yet gathered.')
            if not returned:return Reply(tool_calls=[ToolCall('list',names['list_graphs'],{})])
            if len(returned)==1:return Reply(tool_calls=[ToolCall('search',names['search_entities'],dict(graph_id=label,query=targets[label]['name']))])
            records=[item for message in returned for item in objects(message.get('content',''))]
            found=next(item for item in records if item.get('qualified_name')==targets[label]['name'] and item.get('entity_id'))
            if len(returned)==2 and self.kind=='fp4':return Reply(tool_calls=[ToolCall('source',names['get_entity_content'],dict(graph_id=label,entity_id=found['entity_id']))])
            return Reply(text='The defining implementation is not yet established.')
    from eval_readiness import REQUIRED
    checks={k:False for k in REQUIRED}
    provider=Offline();rows=[]
    with tempfile.TemporaryDirectory(prefix='geo-preflight-') as temp:
        root=Path(temp)
        for index,label in enumerate(labels):
            harness=h.Harness(args.catalog.resolve(),root/f'single-{index}',args.scoping,args.launch,False,args.context_tokens,
                              args.preset,label,args.wheel,None if args.self_check is None else args.self_check=='on',**h.semantic_options(args))
            try:
                result=harness.run(provider,f"Graph: '{label}'. Inspect this generic code definition.",server='geo_code',research_question=targets[label]['question'])
                assert len(result['per_call'])==3 and all(c['success'] for c in result['per_call'])
                assert result['recovery_steps']==2 and result['recovery_model_calls']==1
                assert result['first_attempt']['status']=='unrecovered_draft'
                assert any(r['pattern']=='FP3' and r['outcome']=='resolved' for r in result['recoveries']), dict(answer=result['answer'][:250],recoveries=result['recoveries'],stopped=result['stopped'])
                opened=harness.run(Offline('fp4'),f"Graph: '{label}'. Inspect this generic code definition.",server='geo_code',research_question=targets[label]['question'])
                from resource_librarian.agent_runtime import DEFAULT_PROFILES
                expected=(args.self_check=='on') if args.self_check is not None else bool(DEFAULT_PROFILES['code-research'].route_policy.get('answer_self_check',False))
                assert any(r['pattern']=='FP4' for r in opened['recoveries'])==expected
                assert opened['recovery_model_calls']==int(expected),dict(recoveries=opened['recoveries'],enabled=opened['self_check_enabled'],answer=opened['answer'][:250])
                limited=harness.run(Offline(),f"Graph: '{label}'. Inspect this generic code definition.",max_steps=1,server='geo_code',research_question=targets[label]['question'])
                assert limited['completed_at_step_limit'] and limited['recovery_model_calls']==1
                assert any(r['pattern']=='FP7' for r in limited['recoveries'])
                protocol=harness.run(Offline('xml'),f"Graph: '{label}'. Inspect this generic code definition.",server='geo_code',research_question=targets[label]['question'])
                assert any(r['pattern']=='FP9' and r['action']=='retain_prior_answer' and r['outcome']=='resolved' for r in protocol['recoveries'])
                assert protocol['answer']==protocol['first_attempt']['answer'] and '<tool_call>' not in protocol['answer']
                assert protocol['recovery_steps']==2 and protocol['recovery_model_calls']==1
                checks['protocol_answer_guard']=True
                assert not result['librarian_tools_used'] and not result['withheld_oversize']
                graphs=json.loads(harness.call('list_graphs',{},'geo_code')['content'])['graphs']
                assert {g['label'] for g in graphs}=={label}
                rows.append(dict(graph=label,calls=3,success=True))
            finally:harness.close()
        # Exercise the real batch function and graph switching with generic
        # questions only. No sealed question text or answer key is used here.
        fixture=root/'fixture.json'
        fixture.write_text(json.dumps([dict(id=f'preflight-{i}',graph=label,question=targets[label]['question']) for i,label in enumerate(labels)]),encoding='utf-8')
        fixture_args=deepcopy(args);fixture_args.question_file=fixture;fixture_args.resume=False
        h.question_batch(fixture_args,root/'batch.json',provider_override=provider)
        batch=json.loads((root/'batch.json').read_text(encoding='utf-8'))
        assert len(batch)==len(labels) and all(all(c['success'] for c in r['per_call']) for r in batch)
        assert all(r['recovery_steps']==2 and r['recovery_model_calls']==1 for r in batch)
    literal={'content':json.dumps({'result':{'data':{'chunks':[{'text':'EXTERNAL_RESULT_TOO_LARGE'}]}}})}
    assert not h.call_record('source',{},literal)['withheld']
    assert h.call_record('source',{},dict(error=dict(code='EXTERNAL_RESULT_TOO_LARGE')))['withheld']
    assert temperatures and all(t==0.2 for t in temperatures)
    checks={k:True for k in checks}
    paths=[Path(h.__file__),Path(__file__),Path(__file__).with_name('eval_readiness.py'),args.wheel]
    paths.extend(sorted((h.ROOT/'output/phase67-gates/lib-wave4/src').rglob('*.py')))
    if args.question_file:paths.append(args.question_file)
    if getattr(args,'semantic_cache',None):paths.append(args.semantic_cache)
    if getattr(args,'semantic_model',None):
        # The actual installed server has already validated and loaded this
        # local-only specification. Fingerprint its assets without importing
        # Geo Grapher or optional encoders into the Librarian environment.
        kind,_,value=args.semantic_model.partition(':')
        directory=value.rsplit('@',1)[-1] if kind=='fastembed' else value
        paths.extend(p for p in sorted(Path(directory).rglob('*')) if p.is_file() and '.cache' not in p.relative_to(directory).parts)
    wrapper=h.ROOT/'scripts/review4_budgeted_harness.py'
    if wrapper.exists():paths.append(wrapper)
    spending=h.ROOT/'scripts/eval_spending.py'
    if spending.exists():paths.append(spending)
    value=ticket(config,checks,paths)
    directory=out.parent/'preflights';directory.mkdir(parents=True,exist_ok=True)
    path=directory/(out.stem+'-'+uuid.uuid4().hex[:10]+'.json')
    with path.open('x',encoding='utf-8') as f:json.dump(dict(value,exercised=rows),f,indent=2)
    print(json.dumps(dict(preflight_passed=True,paid_provider_calls=0,receipt=str(path))),flush=True)
    return value,config
