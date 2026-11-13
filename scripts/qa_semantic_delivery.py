"""Measure real capped front-door delivery on disposable SQLite backups."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from eval_retrieval_offline import read_development
from geographer.agent_requests import call_code
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.semantic import load_encoder


def backup(source,destination):
    with sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True) as a,sqlite3.connect(destination) as b:a.backup(b)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('catalog','questions','cache','work','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--model',required=True);p.add_argument('--max-pages',type=int,choices=(1,2),default=1);args=p.parse_args()
    if args.work.exists() or args.out.exists():raise SystemExit('Preserve first delivery results; use a fresh work directory')
    questions,_=read_development(args.questions);args.work.mkdir(parents=True)
    encoder=load_encoder(args.model);catpath=args.work/'catalog.sqlite';backup(args.catalog,catpath)
    originals={};allowed=[]
    with sqlite3.connect(catpath) as c:
        c.row_factory=sqlite3.Row
        for label in sorted({q['graph'] for q in questions}):
            row=c.execute('SELECT * FROM graphs WHERE label=?',(label,)).fetchone()
            source=Path(row['code_database']);destination=args.work/(row['graph_id']+'-code.sqlite')
            originals[str(source)]=hashlib.sha256(source.read_bytes()).hexdigest();backup(source,destination)
            c.execute('UPDATE graphs SET code_database=? WHERE graph_id=?',(str(destination),row['graph_id']));allowed.append(row['graph_id'])
    records=[]
    catalog=GraphCatalog(catpath)
    try:
        router=GraphRouter(catalog,allowed=allowed,max_result_chars=7500,semantic=dict(cache=args.cache,encoder=encoder))
        try:
            for q in questions:
                pages=[];offset=None
                for _ in range(args.max_pages):
                    request=dict(graph_id=q['graph'],query=q['question'])
                    if offset is not None:request['offset']=offset
                    out=call_code(router,'search_entities',request);pages.append(out)
                    offset=out.get('next_offset')
                    if offset is None:break
                ids=list(dict.fromkeys(row['entity_id'] for page in pages for row in page['entities']))
                records.append(dict(id=q['id'],graph=q['graph'],characters=max(len(json.dumps(page,ensure_ascii=False)) for page in pages),pages=len(pages),
                    delivered=len(ids),target_delivered=bool(set(ids)&set(q['targets'])),entity_ids=ids,
                    omissions=out.get('search_hits_omitted',0),recoveries=out.get('recoveries',[])))
        finally:router.close()
    finally:catalog.close()
    if any(hashlib.sha256(Path(path).read_bytes()).hexdigest()!=before for path,before in originals.items()):raise RuntimeError('Original store changed during disposable QA')
    result=dict(records=records,target_delivered=sum(r['target_delivered'] for r in records),questions=len(records),
        all_within_cap=all(r['characters']<=7500 for r in records),canonical_unchanged=True,
        encoder_fingerprint=encoder.fingerprint,max_pages=args.max_pages,scope='Actual capped front door on disposable SQLite backups, verbatim question only, fixed page bound, no key-directed requests; not end-to-end agent answers.',paid_calls=0)
    with args.out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))

if __name__=='__main__':main()
