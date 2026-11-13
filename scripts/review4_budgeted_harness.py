"""Run one immutable registered phase with owner-capped HTTP and episode receipts."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import threading
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'output/phase67-gates/lib-wave4/src'),str(ROOT/'scripts'),'D:/Librarian_V2/scripts']
import delegate_deepinfra as delegation
import librarian_harness as harness
from eval_readiness import fingerprint,require
from eval_spending import approved_budget,reserve_cost,settlement
from resource_librarian import providers


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EvaluationMeter(providers.DispatchGate):
    def __init__(self,registration,phase,*,receipt_root=None):
        self.registration_path=Path(registration).resolve();self.registration=read(self.registration_path)
        if self.registration.get('status')!='registered':raise ValueError('A frozen registered phase is mandatory')
        self.registration_sha=sha(self.registration_path);self.phase_id=phase;self.phase=self.registration['phases'][phase]
        self.approval_path=ROOT/'reports/PHASE67_REVIEW4_BUDGET_APPROVAL.json';self.approval=read(self.approval_path)
        self.ceiling=approved_budget(self.approval)
        if self.registration['model']!='Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo':raise ValueError('This workflow authorises only the frozen code model')
        card=read(ROOT/'reports/PHASE67_REVIEW4_MODEL_CARD.json')['metadata']['pricing']
        if self.registration['rate_card']['input_per_1m']!=card['input_tokens'] or self.registration['rate_card']['output_per_1m']!=card['output_tokens']:
            raise ValueError('Registered rates differ from the verified public model card')
        with delegation.ledger_lock(delegation.DEFAULT_LEDGER):
            committed=delegation.pool_committed(delegation.read_ledger(delegation.DEFAULT_LEDGER,'geo-grapher',self.ceiling),'geo-grapher')
        expected=self.phase['estimated_remaining_usd']
        if committed-self.approval['starting_committed_usd']+expected>self.approval['workflow_cap_usd']:
            raise ValueError('Updated workflow estimate exceeds the owner cap; stop for owner approval')
        self.receipt_root=Path(receipt_root or delegation.DEFAULT_OUTPUT_DIR)
        self.receipt_root.mkdir(parents=True,exist_ok=True)
        self.active=None;self.episodes=0;self.started=False;self.lock=threading.RLock()

    def check(self):
        require(harness.PAID_PREFLIGHT,harness.PAID_CONFIG)
        if sha(self.registration_path)!=self.registration_sha:raise ValueError('Registration changed after launch')
        if fingerprint(self.registration['source_inputs'])!=self.registration['source_inputs']:raise ValueError('Registered candidate changed')
        config=harness.PAID_CONFIG
        for key,value in self.phase['configuration'].items():
            if config.get(key)!=value:raise ValueError('Registered configuration mismatch: '+key)
        for label,scope in config['graph_scope'].items():
            if self.registration['graph_scope'].get(label)!=scope:raise ValueError('Registered graph snapshot changed')

    def before(self,method,url,body,sent_bytes):
        if not isinstance(body,dict) or not url.rstrip('/').endswith('/chat/completions'):return None
        with self.lock:
            try:self.check()
            except (ValueError,OSError) as exc:raise providers.ProviderError(str(exc),category='route_configuration') from exc
            if self.active is None:raise providers.ProviderError('No active registered episode',category='route_configuration')
            if url.rstrip('/')!='https://api.deepinfra.com/v1/openai/chat/completions' or body.get('model')!=self.registration['model'] or body.get('temperature')!=.2:
                raise providers.ProviderError('Frozen model/route/temperature mismatch',category='route_configuration')
            if body.get('service_tier') not in (None,'default'):raise providers.ProviderError('Unregistered service tier',category='route_configuration')
            rate=self.registration['rate_card']
            reserve=reserve_cost(body,rate,sent_bytes=sent_bytes)
            if not self.started:
                marker=Path(self.phase['started_receipt'])
                marker.parent.mkdir(parents=True,exist_ok=True)
                try:
                    with marker.open('x',encoding='utf-8') as f:json.dump(dict(registration_sha256=self.registration_sha,started_at=delegation.utc_now()),f)
                except FileExistsError as exc:raise providers.ProviderError('This registered phase already started; no redispatch',category='route_configuration') from exc
                self.started=True
            run_id='review4-http-'+uuid.uuid4().hex[:20];path=self.receipt_root/(run_id+'.receipt.json')
            raw=json.dumps(body,sort_keys=True,ensure_ascii=False).encode('utf-8')
            loop=getattr(self.active['harness'],'current_loop',None)
            recovery=loop.ctx.extras.get('_code_recovery') if loop is not None else None
            recovery_ordinal=recovery.extra_model_calls if recovery is not None else 0
            entry=dict(run_id=run_id,pool='geo-grapher',task='review4-'+self.phase_id,task_id='review4-code-evaluation',
                role='runtime_benchmark',agent='codex',model=body['model'],temperature=body['temperature'],
                request_sha256=hashlib.sha256(raw).hexdigest(),started_at=delegation.utc_now(),timeout_s=180,
                status='started',acceptance='not_reviewed',reserve_usd=reserve,charged_usd=reserve,cost_basis='reserve',receipt=str(path),
                episode_run_id=self.active['id'],episode_receipt=str(self.active['receipt']),
                recovery_model_ordinal=recovery_ordinal,recovery_phase=('shared_revision' if recovery.revision_done else 'FP7') if recovery_ordinal else '')
            try:
                delegation.reserve_call(delegation.DEFAULT_LEDGER,'geo-grapher',self.ceiling,entry,reserve,1.,task_cap_usd=self.approval['workflow_cap_usd'])
            except SystemExit as exc:
                self.active['dispatch_blocked']=True
                raise providers.ProviderError('Owner ledger admission blocked: '+str(exc),category='route_configuration') from exc
            delegation.atomic_json(path,dict(entry,rate_card=rate,max_output_tokens=body.get('max_tokens',4096)))
            self.active['http_receipts'].append(str(path))
            return entry,path

    def after(self,ticket,error,reply):
        if ticket is None:return
        entry,path=ticket;rate=self.registration['rate_card']
        usage=(reply or {}).get('usage',{}) if isinstance(reply,dict) else {}
        charge,basis=settlement(usage,rate,entry['reserve_usd']) if error is None else (entry['reserve_usd'],'reserve')
        status='completed' if error is None else 'uncertain'
        record=dict(entry,status=status,usage=usage,charged_usd=charge,cost_basis=basis,rate_card=rate,
            returned_model=reply.get('model') if isinstance(reply,dict) else None)
        delegation.atomic_json(path,record)
        if isinstance(reply,dict):delegation.atomic_json(path.with_suffix('.response.json'),reply)
        delegation.settle_call(delegation.DEFAULT_LEDGER,'geo-grapher',self.ceiling,entry['run_id'],status=status,
            charged_usd=charge,cost_basis=basis,receipt_path=str(path))

    def run_episode(self,original,instance,*args,**kwargs):
        # The mandatory dry run executes first, without a key or paid provider.
        if harness.PAID_PREFLIGHT is None:return original(instance,*args,**kwargs)
        self.check()
        if self.active is not None or self.episodes>=self.phase['episodes']:raise ValueError('Registered episode bound exceeded')
        self.episodes+=1;episode_id=uuid.uuid4().hex
        directory=Path(self.phase['episode_directory']);directory.mkdir(parents=True,exist_ok=True)
        path=directory/(episode_id+'.json')
        active=dict(id=episode_id,receipt=path,harness=instance,http_receipts=[])
        self.active=active;result=None;failure=None
        try:
            result=original(instance,*args,**kwargs)
            result['episode_receipt']=str(path)
            result['dispatch_blocked']=bool(active.get('dispatch_blocked'))
            return result
        except BaseException as exc:
            failure=dict(type=type(exc).__name__,message=str(exc)[:300]);raise
        finally:
            records=[read(p) for p in active['http_receipts']]
            value=dict(episode_run_id=episode_id,phase=self.phase_id,registration_sha256=self.registration_sha,
                question_sha256=hashlib.sha256(str(kwargs.get('research_question') or '').encode()).hexdigest(),
                status='failed' if failure else 'completed',failure=failure,http_receipts=active['http_receipts'],
                charged_usd=sum(r['charged_usd'] for r in records),http_attempts=len(records),
                recovery_http_attempts=sum(bool(r.get('recovery_phase')) for r in records),
                recovery_episode_id=(result or {}).get('recovery_episode_id'),recoveries=(result or {}).get('recoveries',[]),
                dispatch_blocked=bool(active.get('dispatch_blocked')),
                first_attempt=(result or {}).get('first_attempt',dict(answer='',status='not_produced')),
                recovery_steps=(result or {}).get('recovery_steps'),recovery_model_calls=(result or {}).get('recovery_model_calls'))
            with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False)
            self.active=None


def main():
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--registration',type=Path,required=True);p.add_argument('--phase',required=True)
    options,remaining=p.parse_known_args();meter=EvaluationMeter(options.registration,options.phase)
    output_parser=argparse.ArgumentParser(add_help=False);output_parser.add_argument('--out',type=Path,required=True)
    output_options,_=output_parser.parse_known_args(remaining)
    if output_options.out.resolve()!=Path(meter.phase['out']).resolve():raise ValueError('Registered output path mismatch')
    if '--resume' in remaining:raise ValueError('Registered phases cannot resume or replace first results')
    original=harness.Harness.run
    harness.Harness.run=lambda instance,*a,**kw:meter.run_episode(original,instance,*a,**kw)
    harness.load_key=lambda:delegation.load_key(delegation.DEFAULT_KEY_FILE)
    previous=providers.set_dispatch_gate(meter);sys.argv=[sys.argv[0],*remaining]
    try:harness.main()
    finally:providers.set_dispatch_gate(previous)

if __name__=='__main__':main()
