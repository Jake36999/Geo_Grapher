"""Run with python -m evaluation.run; explicit model adapters are opt-in."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import platform
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

from geographer.incremental import build_digest
from geographer.model import canonical
from geographer.pipeline import ingest
from geographer.rules import ArchitectureRules
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.tokens import TokenCounter
from .harness import (ROOT,ARMS,load_suite,sha,retrieve,retrieval_metrics,grade,
                      model_prompt,run_model,distribution,schedule)


def run(output,*,repeats=3,seed=505,encoding='o200k_base',evidence_limit=8192,
        total_limit=16384,output_limit=1024,adapter_config=None):
    if not 1<=repeats<=30:raise ValueError('Repeats must be 1..30')
    if not 512<=evidence_limit<total_limit or not 128<=output_limit<total_limit:raise ValueError('Invalid token budgets')
    suite,files,source_digest=load_suite();counter=TokenCounter(encoding)
    config=None
    if adapter_config:
        config=json.loads(Path(adapter_config).read_text(encoding='utf-8'))
        if (set(config)-{'max_repairs'}!={'command','model','configuration','provider_spend_cap','max_run_spend'} or
            not isinstance(config['command'],list) or not config['command'] or
            not all(isinstance(s,str) and s for s in config['command']) or
            not isinstance(config['configuration'],dict) or not isinstance(config['model'],str) or not config['model'] or
            type(config['provider_spend_cap']) not in (int,float) or not 0<config['provider_spend_cap']<=100 or
            type(config['max_run_spend']) not in (int,float) or not 0<config['max_run_spend']<=100):
            raise ValueError('Invalid adapter configuration; explicit per-request and total spend caps <=100 required')
        if config.get('max_repairs',0) not in (0,1):raise ValueError('max_repairs must be 0 or 1')
        if config['provider_spend_cap']*repeats*len(suite['tasks'])*len(ARMS)*(1+config.get('max_repairs',0))>config['max_run_spend']:
            raise ValueError('Worst-case adapter spend exceeds explicit total run cap')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    vocabulary=sorted({fact for t in suite['tasks'] for fact in t['oracle']['facts']})
    tracemalloc.start();start=time.perf_counter()
    with SnapshotStore(output/'snapshot.sqlite') as store:
        # Rules are not source entities; their independent digest is scoped separately.
        repo=Repository('evaluation','fixture-v1',{p:b for p,b in files.items() if not p.endswith('.yaml')})
        ingestion=ingest(store,[repo],stage=3);sid=ingestion['snapshot_id']
        failures=store.validate(sid)
        if failures:raise AssertionError(failures)
        model=ArchitectureRules(files['geographer.rules.yaml'])
        svc=QueryService(store,rules=[model],secret=b'p55-reproducible-local-fixture-only')
        graph=svc._context(sid)['g'];index_ms=(time.perf_counter()-start)*1000
        records=[];order=schedule(suite['tasks'],repeats,seed)
        with (output/'transcripts.jsonl').open('w',encoding='utf-8') as archive:
            for trial,task,arm in order:
                evidence,trace=retrieve(svc,sid,model,graph,files,task,arm,counter,evidence_limit)
                prompt=model_prompt(task,evidence,vocabulary)
                model_record=dict(status='unverified',reason='No opt-in model adapter configured; offline retrieval is not an answer-quality comparison')
                if config:
                    model_record=run_model(config['command'],config,prompt,counter,total_limit,output_limit,max_repairs=config.get('max_repairs',0))
                    if model_record['status']=='recorded':model_record['grade']=grade(task,model_record['response']['answer'],evidence,files)
                record=dict(trial=trial,task_id=task['id'],category=task['category'],arm=arm,
                            evidence=evidence,retrieval=trace,metrics=retrieval_metrics(task,evidence,trace,counter),
                            prompt_sha256=sha(canonical(prompt).encode()),
                            canonical_prompt_tokens=counter.count(prompt),
                            model=model_record)
                archive.write(canonical(record)+'\n');archive.flush();records.append(record)
        _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        summaries={}
        for arm in ARMS:
            subset=[r for r in records if r['arm']==arm]
            summaries[arm]=dict(samples=len(subset),tasks=len(suite['tasks']),
                evidence_tokens=distribution([r['metrics']['evidence_tokens'] for r in subset]),
                canonical_prompt_tokens=distribution([r['canonical_prompt_tokens'] for r in subset]),
                citation_span_recall_mean=statistics.mean(r['metrics']['citation_span_recall'] for r in subset),
                relevant_entity_recall_mean=(statistics.mean(r['metrics']['relevant_entity_recall'] for r in subset if r['metrics']['relevant_entity_recall'] is not None)
                                            if any(r['metrics']['relevant_entity_recall'] is not None for r in subset) else None),
                search_reciprocal_rank_mean=(statistics.mean(r['metrics']['ranked_search_reciprocal_rank'] or 0 for r in subset)
                                            if any(r['retrieval']['search_ranking'] for r in subset) else None),
                witness_pair_recall_mean=(statistics.mean(r['metrics']['witness_pair_recall'] for r in subset if r['metrics']['witness_pair_recall'] is not None)
                                          if any(r['metrics']['witness_pair_recall'] is not None for r in subset) else None),
                latency_ms=distribution([r['metrics']['elapsed_ms'] for r in subset]),
                retrieval_errors=sum(len(r['metrics']['retrieval_errors']) for r in subset),
                omitted_bundles=sum(r['metrics']['omitted_bundles'] for r in subset),
                model_status_counts={status:sum(r['model']['status']==status for r in subset) for status in sorted({r['model']['status'] for r in subset})},
                graded_answers=[dict(task_id=r['task_id'],trial=r['trial'],**r['model']['grade']) for r in subset if 'grade' in r['model']])
        manifest=dict(version='phase5-evaluation-v1',source_lock_sha256=sha((ROOT/'sources.lock.json').read_bytes()),
            task_manifest_sha256=sha((ROOT/'tasks.json').read_bytes()),source_manifest=source_digest,
            implementation_digest=build_digest(),harness_sha256={p.name:sha(p.read_bytes()) for p in sorted(ROOT.glob('*.py'))},
            snapshot_id=sid,ingestion=ingestion,publication_validation=failures,
            protocol='one-shot fixed retrieval policies; no agent tools after evidence delivery',
            arms=list(ARMS),repeats=repeats,random_seed=seed,tokenizer=encoding,weights_digest=counter.sha,
            evidence_limit=evidence_limit,total_input_output_limit=total_limit,reserved_output=output_limit,
            adapter_configuration=config,max_provider_spend=(config['provider_spend_cap']*len(order)*(1+config.get('max_repairs',0)) if config else 0),
            source_file_cap=3,service_call_cap=3,index_cost_ms=index_ms,tracemalloc_peak_bytes=peak,
            instrumentation='tracemalloc enabled, shared caches, randomized order; no cold latency or process RSS claim',
            environment=dict(python=sys.version,platform=platform.platform(),machine=platform.machine(),
                             packages={name:importlib.metadata.version(name) for name in ('tiktoken','mcp','pydantic')}),
            model_evaluation='recorded outcomes, including errors' if config else 'unverified_no_adapter_configured',
            limitations=['12 small manually authored development tasks; no held-out superiority claim or imported accuracy target',
                'Repeated identical tasks are not independent population samples; descriptive distributions only, no confidence interval claim',
                'Table and architecture share extraction, independent source oracles do not',
                'Flat search has source snippets, not ranked entity records; entity ranking metrics are not task correctness',
                'Closed-label facts are strict structured scoring, not semantic grading of free prose; additional explanation needs human review',
                'Whole-envelope local JSON and provider input/output are separate ledgers; adapter must enforce provider cap and output bound',
                'Remote adapter is trusted execution; adapter must archive actual provider usage/identity and enforce its stated spend cap',
                'Index cost includes ingestion and service graph setup, not lazily built per-query FTS cost',
                'No human/AT, target-device C14, final-build soak or whole-repository model result is implied'])
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        (output/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
        print(json.dumps(dict(output=str(output.resolve()),model_evaluation=manifest['model_evaluation'],arms=summaries),indent=2))
    return manifest,summaries


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeats',type=int,default=3);p.add_argument('--seed',type=int,default=505)
    p.add_argument('--encoding',choices=['o200k_base','cl100k_base'],default='o200k_base')
    p.add_argument('--evidence-limit',type=int,default=8192);p.add_argument('--total-limit',type=int,default=16384)
    p.add_argument('--output-limit',type=int,default=1024);p.add_argument('--adapter-config',type=Path)
    args=p.parse_args();run(args.output,repeats=args.repeats,seed=args.seed,encoding=args.encoding,
        evidence_limit=args.evidence_limit,total_limit=args.total_limit,output_limit=args.output_limit,adapter_config=args.adapter_config)


if __name__=='__main__':main()
