"""Free, read-only development replay. Never opens the sealed v2 set."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from offline_graphs import FrozenGraphs
from geographer.retrieval import LexicalIndex


def read_development(path):
    path=Path(path).resolve()
    seal=json.loads((ROOT/'reports/PHASE67_HELDOUT_V2_SEAL.json').read_text(encoding='utf-8'))
    forbidden=set(seal['files'].values())
    if 'heldout-v2' in str(path).casefold() or hashlib.sha256(path.read_bytes()).hexdigest() in forbidden:
        raise ValueError('Sealed v2 is forbidden in development/offline evaluation')
    value=json.loads(path.read_text(encoding='utf-8'))
    rows=value['questions'] if isinstance(value,dict) else value
    seen=set()
    for row in rows:
        if row['id'] in seen or not row['targets'] or not row['question'].strip():
            raise ValueError('Unique questions and nonempty equivalence targets required')
        seen.add(row['id'])
    return rows,value.get('manifest',{}) if isinstance(value,dict) else {}


def proposed_rrf(lists,k=60):
    """Pre-L1 comparator only; this does not silently change product ranking."""
    scores={}
    for hits in lists:
        seen=set()
        for rank,hit in enumerate(hits,1):
            eid=hit['node_id']
            if eid in seen:continue
            seen.add(eid);scores[eid]=scores.get(eid,0)+1/(k+rank)
    return [eid for eid in sorted(scores,key=lambda eid:(-scores[eid],eid))]


def target_rank(ids,targets):
    return next((n for n,eid in enumerate(ids,1) if eid in targets),None)


def metrics(rows):
    n=len(rows)
    return dict(count=n,**{f'recall@{k}':dict(hits=sum(r['rank'] is not None and r['rank']<=k for r in rows),
        total=n,rate=sum(r['rank'] is not None and r['rank']<=k for r in rows)/n if n else None) for k in (1,3,8)})


def replay(questions,frozen,product=False,semantic_by_graph=None,simulate_runtime=False):
    indices={};records=[];recoveries=[];semantic_recoveries=[];runtime_records=[];scents={}
    try:
        for q in questions:
            label=q['graph'];graph=frozen.graph(label)
            if not set(q['targets'])<=graph.entities.keys():raise ValueError('Target missing from frozen graph')
            if label not in indices:indices[label]=LexicalIndex(graph)
            semantic=(semantic_by_graph or {}).get(label)
            cache={}
            def search(text):
                if text not in cache:
                    if semantic is None:cache[text]=indices[label].search(text,limit=200)
                    else:
                        from geographer.search_fusion import rank_queries
                        cache[text]=rank_queries(indices[label],[text],semantic=semantic)['hits']
                return cache[text]
            primary=search(q['question'])
            if product and label not in scents:
                from geographer.agent_scent import SourceScent
                sources={(graph.entities[v['scope']['entity_id']].repo_id,v['result']['rel_path']):v['result'] for v in graph.analyses.values()
                    if v['algorithm_version']=='source-bytes-v1' and v['scope'].get('entity_id') in graph.entities}
                scents[label]=SourceScent(dict(g=graph,sources=sources,evidence={}))
            def record(view,query,hits):
                ids=[h['node_id'] for h in hits] if hits and isinstance(hits[0],dict) else hits
                records.append(dict(id=q['id'],graph=label,view=view,query=query,rank=target_rank(ids,set(q['targets'])),top8=ids[:8]))
            record('question_text',q['question'],primary)
            if semantic is not None:record('lexical_question_text',q['question'],indices[label].search(q['question'],limit=200))
            queries=q.get('recorded_queries',[])
            for query in queries:
                hits=search(query);record('agent_queries',query,hits)
                # Equal query weights, fixed candidate depth, no knowledge of targets.
                record('proposed_verbatim_plus_guess',query,proposed_rrf([primary,hits]) if query!=q['question'] else hits)
                if product:
                    from geographer.search_fusion import rank_queries,observation
                    texts=list(dict.fromkeys([q['question'],query]))
                    fused=rank_queries(indices[label],texts,semantic=semantic)['hits']
                    record('product_recommended',query,fused)
                    obs=observation(hits,q['question'],scents[label],query=query)
                    trigger=obs['low_confidence']
                    before=target_rank([h['node_id'] for h in hits],set(q['targets']))
                    after=target_rank([h['node_id'] for h in (fused if trigger else hits)],set(q['targets']))
                    recoveries.append(dict(id=q['id'],query=query,pattern='FP1',trigger=trigger,trigger_value=obs['confidence'],
                        original_correct=before is not None and before<=8,rank_before=before,rank_after=after))
                    if semantic is not None:
                        lexical=indices[label].search(query,limit=200)
                        record('lexical_agent_queries',query,lexical)
                        semhits=semantic.search(query)
                        lexical_obs=observation(lexical,q['question'],scents[label],query=query)
                        disagree={h['node_id'] for h in lexical[:8]}!={h['node_id'] for h in semhits[:8]}
                        fired=lexical_obs['low_confidence'] and disagree
                        prior=target_rank([h['node_id'] for h in lexical],set(q['targets']))
                        next_rank=target_rank([h['node_id'] for h in (hits if fired else lexical)],set(q['targets']))
                        semantic_recoveries.append(dict(id=q['id'],query=query,pattern='FP2',trigger=fired,
                            trigger_value=dict(lexical_confidence=lexical_obs['confidence'],top8_disagree=disagree),
                            original_correct=prior is not None and prior<=8,rank_before=prior,rank_after=next_rank))
                    if simulate_runtime:
                        from types import SimpleNamespace
                        from geographer.search_recovery import META,search as runtime_search
                        router=SimpleNamespace()
                        config=dict(episode_id='offline-episode',question=q['question'],mode='defer',remaining_steps=3)
                        token=META.set(config)
                        try:
                            first,initial=runtime_search(router,None,indices[label],[query],scents[label],semantic=semantic)
                            config['mode']='auto'
                            final,receipt=runtime_search(router,None,indices[label],[query],scents[label],semantic=semantic)
                        finally:META.reset(token)
                        before=target_rank([h['node_id'] for h in first['hits']],set(q['targets']))
                        after=target_rank([h['node_id'] for h in final['hits']],set(q['targets']))
                        runtime_records.append(dict(id=q['id'],query=query,rank_before=before,rank_after=after,
                            recoveries=receipt['recoveries'],steps=receipt['recovery_steps_consumed'],pending=initial['recovery_pending']))
        summary={view:metrics([r for r in records if r['view']==view]) for view in ('question_text','agent_queries','proposed_verbatim_plus_guess')}
        if product:
            summary['product_recommended']=metrics([r for r in records if r['view']=='product_recommended'])
            original_right=sum(r['original_correct'] for r in recoveries)
            triggers=sum(r['trigger'] for r in recoveries)
            false=sum(r['trigger'] and r['original_correct'] for r in recoveries)
            summary['FP1_simulation']=dict(episodes=len(recoveries),triggers=triggers,
                trigger_rate=triggers/len(recoveries) if recoveries else None,false_triggers=false,
                false_trigger_rate_given_original_correct=false/original_right if original_right else None,
                false_trigger_fraction_of_triggers=false/triggers if triggers else None,
                before=metrics([dict(rank=r['rank_before']) for r in recoveries]),
                after=metrics([dict(rank=r['rank_after']) for r in recoveries]),
                simulation='Product confidence detector and fusion; episode scheduling/shared recovery ledger not yet enabled in front door.')
        if semantic_by_graph:
            for view in ('lexical_question_text','lexical_agent_queries'):summary[view]=metrics([r for r in records if r['view']==view])
            right=sum(r['original_correct'] for r in semantic_recoveries)
            fired=sum(r['trigger'] for r in semantic_recoveries)
            false=sum(r['trigger'] and r['original_correct'] for r in semantic_recoveries)
            summary['FP2_simulation']=dict(episodes=len(semantic_recoveries),triggers=fired,
                trigger_rate=fired/len(semantic_recoveries) if semantic_recoveries else None,
                false_triggers=false,false_trigger_rate_given_original_correct=false/right if right else None,
                false_trigger_fraction_of_triggers=false/fired if fired else None,
                before=metrics([dict(rank=r['rank_before']) for r in semantic_recoveries]),
                after=metrics([dict(rank=r['rank_after']) for r in semantic_recoveries]),
                simulation='Lexical weak-preview confidence plus lexical/semantic top-8 disagreement; one local semantic-fusion action. Not live episode scheduling.')
        if simulate_runtime:
            patterns={}
            for pattern in ('FP1','FP2'):
                fired=[r for r in runtime_records if any(x['pattern']==pattern for x in r['recoveries'])]
                originally_right=[r for r in runtime_records if r['rank_before'] is not None and r['rank_before']<=8]
                false=sum(r in originally_right for r in fired)
                patterns[pattern]=dict(triggers=len(fired),total=len(runtime_records),false_triggers=false,
                    false_trigger_rate_given_original_correct=false/len(originally_right) if originally_right else None,
                    resolved_by_runtime_signal=sum(x['outcome']=='resolved' for r in fired for x in r['recoveries'] if x['pattern']==pattern))
            summary['runtime_search_recovery']=dict(before=metrics([dict(rank=r['rank_before']) for r in runtime_records]),
                after=metrics([dict(rank=r['rank_after']) for r in runtime_records]),patterns=patterns,
                extra_steps=sum(r['steps'] for r in runtime_records),max_extra_steps=max((r['steps'] for r in runtime_records),default=0),
                scope='Actual front-door search recovery function with deferred first pass then one auto action; raw candidates, no agent answers or wire packing.')
        agent=[r for r in records if r['view']=='agent_queries']
        ids={r['id'] for r in agent}
        summary['any_agent_hit_per_question']=dict(hits=sum(any(r['id']==qid and r['rank'] is not None and r['rank']<=8 for r in agent) for qid in ids),total=len(ids))
        return dict(summary=summary,records=records,recovery_simulation=recoveries+semantic_recoveries,runtime_search_simulation=runtime_records,snapshots=dict(frozen.snapshots),
            interpretation='Raw candidate ranks, not capped wire delivery. Product recommended uses the shared product ranker. Question/agent views use enabled channels; lexical views are retained separately when semantic is on. FP1 and FP2 simulations are separate, not cumulative episode success.',
            configuration=dict(lexical_version=LexicalIndex.version,mode='hybrid',gamma=.8,lexical_k=60,multiquery_k=60,candidate_depth=200,paid_calls=0))
    finally:
        for index in indices.values():index.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--questions',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--product-l1',action='store_true')
    p.add_argument('--semantic-model');p.add_argument('--semantic-cache',type=Path)
    p.add_argument('--simulate-runtime',action='store_true')
    args=p.parse_args()
    if args.out.exists():raise SystemExit('Preserve first offline result: output already exists')
    questions,manifest=read_development(args.questions)
    with FrozenGraphs(args.catalog) as frozen:
        semantic_by_graph=None
        if args.semantic_model or args.semantic_cache:
            if not args.semantic_model or not args.semantic_cache:raise ValueError('Supply model and prebuilt semantic cache together')
            from geographer.semantic import load_encoder,SemanticCache
            encoder=load_encoder(args.semantic_model)
            semantic_by_graph={label:SemanticCache.load(args.semantic_cache,frozen.graph(label),frozen.snapshots[label],encoder) for label in sorted({q['graph'] for q in questions})}
        result=replay(questions,frozen,args.product_l1 or semantic_by_graph is not None or args.simulate_runtime,semantic_by_graph,args.simulate_runtime)
        if semantic_by_graph:result['semantic_namespaces']={label:cache.namespace for label,cache in semantic_by_graph.items()}
        if manifest.get('snapshots') and manifest['snapshots']!=frozen.snapshots:raise ValueError('Frozen snapshot mismatch')
    result['input_sha256']=hashlib.sha256(args.questions.read_bytes()).hexdigest()
    sources=[ROOT/'scripts/eval_retrieval_offline.py',ROOT/'scripts/offline_graphs.py',*sorted((ROOT/'src/geographer').glob('*.py'))]
    result['implementation_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
    print(json.dumps(result['summary']))

if __name__=='__main__':main()
