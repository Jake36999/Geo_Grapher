"""Owner option (a): score retrieved supporting documents separately from answer markers."""
import argparse,json,sqlite3
from pathlib import Path

# Frozen benchmark markers include two quantities, not document IDs.
SUPPORT={'115':115,'doc:1':1,'108':108,'85':115,'229':229,'152':152,'234':2}

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--catalog',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise SystemExit('Refusing to replace a score; use a new output path')
    with sqlite3.connect(a.catalog.resolve().as_uri()+'?mode=ro',uri=True) as c:
        db=c.execute('SELECT paper_database FROM graphs WHERE label=?',('ai-research-papers',)).fetchone()[0]
    with sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True) as c:
        sources=[dict(id=r[0],title=r[1],abstract=r[2]) for r in c.execute('SELECT id,title,abstract_summary FROM read_documents WHERE id IN (2,115)')]
    rows=[]
    for r in json.loads(a.input.read_text(encoding='utf-8')):
        got=set(r['retrieved']['ai-research-papers'])
        rows.append(dict(question=r['question'],markers=r['markers'],supporting_documents=[SUPPORT[m] for m in r['markers']],
            retrieval=sum(SUPPORT[m] in got for m in r['markers']),answer=len(r['markers_found']),total=len(r['markers'])))
    result=dict(protocol='owner-option-a',source=str(a.input),support_map=SUPPORT,support_provenance=sources,questions=rows,
        retrieval=sum(r['retrieval'] for r in rows),answer=sum(r['answer'] for r in rows),total=sum(r['total'] for r in rows))
    result['passed']=result['retrieval']==7 and result['answer']>=6
    a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('retrieval','answer','total','passed')}))

if __name__=='__main__':main()
