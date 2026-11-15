"""No-network fixture for the registered meter; never reserves the real pool."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'output/phase67-gates/lib-wave4/src')]
import review4_budgeted_harness as meter_module
from eval_readiness import REQUIRED,graph_scope,ticket


def main():
    h=meter_module.harness;d=meter_module.delegation;seen=[]
    original_reserve,original_settle=d.reserve_call,d.settle_call
    d.reserve_call=lambda *a,**kw:seen.append(('reserve',a,kw))
    d.settle_call=lambda *a,**kw:seen.append(('settle',a,kw))
    try:
        with tempfile.TemporaryDirectory(prefix='review4-meter-fixture-') as temp:
            root=Path(temp);source=root/'input.txt';source.write_text('frozen')
            catalog=root/'catalog.sqlite'
            with sqlite3.connect(catalog) as c:
                c.execute('CREATE TABLE graphs(label TEXT,graph_id TEXT,snapshot_id TEXT,code_database TEXT)')
                c.execute('INSERT INTO graphs VALUES(?,?,?,?)',('local','g','s','code.sqlite'))
            c.close()
            config=dict(catalog=str(catalog),graph_scope=graph_scope(catalog,['local']))
            h.PAID_CONFIG=config;h.PAID_PREFLIGHT=ticket(config,{k:True for k in REQUIRED},[source])
            phase=dict(configuration=config,episodes=1,out=str(root/'result.json'),started_receipt=str(root/'started.json'),
                episode_directory=str(root/'episodes'),estimated_remaining_usd=.001)
            registration=dict(status='registered',model='Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo',
                rate_card=dict(input_per_1m=.3,output_per_1m=1.),source_inputs=h.PAID_PREFLIGHT['inputs'],graph_scope=config['graph_scope'],phases={'fixture':phase})
            path=root/'registration.json';path.write_text(json.dumps(registration))
            meter=meter_module.EvaluationMeter(path,'fixture',receipt_root=root/'http')
            body=dict(model=registration['model'],temperature=.2,max_tokens=4096,messages=[])
            recovery=dict(pattern='FP6',trigger_value={'error_code':'INVALID_GRAPH_REQUEST'},action='scoped_candidates',outcome='resolved')
            def run(instance,provider,**kwargs):
                request=meter.before('POST','https://api.deepinfra.com/v1/openai/chat/completions',body,100)
                meter.after(request,None,dict(model=body['model'],usage=dict(prompt_tokens=100,completion_tokens=20)))
                return dict(answer='fixture',recoveries=[recovery],first_attempt=dict(answer='fixture',status='produced_after_early_recovery'),
                    recovery_steps=0,recovery_model_calls=0,recovery_episode_id='fixture-runtime')
            result=meter.run_episode(run,SimpleNamespace(),None,research_question='generic fixture')
            receipt=json.loads(Path(result['episode_receipt']).read_text())
            assert receipt['recoveries']==[recovery] and receipt['first_attempt']['status']=='produced_after_early_recovery'
            assert receipt['http_attempts']==1 and abs(receipt['charged_usd']-.00005)<1e-12
            assert seen[0][1][2]==14.24739611 and seen[1][1][2]==14.24739611
            try:meter.run_episode(run,SimpleNamespace(),None,research_question='again')
            except ValueError:pass
            else:raise AssertionError('Episode limit was not enforced')
            source.write_text('changed')
            try:meter.check()
            except ValueError:pass
            else:raise AssertionError('Changed source was not blocked')
            assert len(seen)==2
    finally:d.reserve_call,d.settle_call=original_reserve,original_settle
    print(json.dumps(dict(passed=True,paid_provider_calls=0,real_pool_mutations=0,ceiling=14.24739611,episode_receipt=True,source_freeze=True)))

if __name__=='__main__':main()
