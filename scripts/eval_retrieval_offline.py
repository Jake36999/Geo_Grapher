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


def replay(questions,frozen):
    indices={};records=[]
    try:
        for q in questions:
            label=q['graph'];graph=frozen.graph(label)
            if not set(q['targets'])<=graph.entities.keys():raise ValueError('Target missing from frozen graph')
            if label not in indices:indices[label]=LexicalIndex(graph)
            cache={}
            def search(text):
                if text not in cache:cache[text]=indices[label].search(text,limit=200)
                return cache[text]
            primary=search(q['question'])
            def record(view,query,hits):
                ids=[h['node_id'] for h in hits] if hits and isinstance(hits[0],dict) else hits
                records.append(dict(id=q['id'],graph=label,view=view,query=query,rank=target_rank(ids,set(q['targets'])),top8=ids[:8]))
            record('question_text',q['question'],primary)
            queries=q.get('recorded_queries',[])
            for query in queries:
                hits=search(query);record('agent_queries',query,hits)
                # Equal query weights, fixed candidate depth, no knowledge of targets.
                record('proposed_verbatim_plus_guess',query,proposed_rrf([primary,hits]) if query!=q['question'] else hits)
        summary={view:metrics([r for r in records if r['view']==view]) for view in ('question_text','agent_queries','proposed_verbatim_plus_guess')}
        agent=[r for r in records if r['view']=='agent_queries']
        ids={r['id'] for r in agent}
        summary['any_agent_hit_per_question']=dict(hits=sum(any(r['id']==qid and r['rank'] is not None and r['rank']<=8 for r in agent) for qid in ids),total=len(ids))
        return dict(summary=summary,records=records,snapshots=dict(frozen.snapshots),
            interpretation='Raw candidate ranks, not capped wire delivery. Proposed RRF is a pre-product comparator, not yet the product recommended strategy.',
            configuration=dict(lexical_version=LexicalIndex.version,mode='hybrid',gamma=.8,lexical_k=60,multiquery_k=60,candidate_depth=200,paid_calls=0))
    finally:
        for index in indices.values():index.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--questions',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():raise SystemExit('Preserve first offline result: output already exists')
    questions,manifest=read_development(args.questions)
    with FrozenGraphs(args.catalog) as frozen:
        result=replay(questions,frozen)
        if manifest.get('snapshots') and manifest['snapshots']!=frozen.snapshots:raise ValueError('Frozen snapshot mismatch')
    result['input_sha256']=hashlib.sha256(args.questions.read_bytes()).hexdigest()
    with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
    print(json.dumps(result['summary']))

if __name__=='__main__':main()
