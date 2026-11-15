"""Replay development queries only; verify source contexts against frozen bytes."""
import argparse,hashlib,json,re
from pathlib import Path
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.agent_requests import call_code
from geographer.agent_scent import scent

ROOT=Path(__file__).resolve().parents[1]
QUERIES=[('loop fallback context window','DEFAULT_CONTEXT_TOKENS'),('How does the loop choose its fallback context window','DEFAULT_CONTEXT_TOKENS'),
         ('MCP structured results bounding','MAX_EXTERNAL_RESULT'),('How are external MCP structured results bounded','MAX_EXTERNAL_RESULT'),
         ('Clerk run and check one task','run_one'),('delegate cap concurrent tier 1 helpers','HELPER_TOOLS')]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='development-scent-oracles.json');args=parser.parse_args()
    cat=GraphCatalog('D:/Librarian_V2/tmp/geo-grapher-wave4-continuation-stores/catalog.sqlite');router=GraphRouter(cat);router.max_result_chars=7500
    rows=[]
    try:
        for query,target in QUERIES:
            out=call_code(router,'search_entities',dict(graph_id='librarian-v2',query=query))
            nodes={n['entity_id']:n for n in out['result']['data']['nodes']}
            hits=[nodes[h['entity_id']] for h in out['result']['data']['hits']]
            node=next((n for n in hits if n['qualified_name'].rsplit('.',1)[-1]==target),None)
            terms=re.findall(r'\w+',query.casefold());card=node.get('summary',{}) if node else {}
            passed=bool(node and any(t in ((card.get('doc_gist') or '')+' '+(card.get('why') or '')).casefold() for t in terms))
            rows.append(dict(query=query,target=target,rank=hits.index(node)+1 if node else None,passed=passed,card=card,chars=len(json.dumps(out,ensure_ascii=False))))
        for target,required in [('DEFAULT_CONTEXT_TOKENS',[133,139,578]),('MAX_EXTERNAL_RESULT',[47,491])]:
            found=call_code(router,'search_entities',dict(graph_id='librarian-v2',query=target))
            module='loop.py.' if target=='DEFAULT_CONTEXT_TOKENS' else 'mcp_client.py.'
            eid=next(e['entity_id'] for e in found['entities'] if e['qualified_name'].endswith(module+target));out=call_code(router,'get_entity_content',dict(graph_id='librarian-v2',entity_id=eid))
            chunks=out['result']['data']['chunks']
            with router.lease(router.resolve('librarian-v2')) as svc:
                src=scent(svc._context(out['snapshot_id'] if 'snapshot_id' in out else cat.graph(router.resolve('librarian-v2'))['snapshot_id']))
                hashes=all(c['text']==''.join(src.source(c['source']['repo_id'],c['source']['rel_path'])[c['source']['start_line']-1:c['source']['end_line']])
                           and hashlib.sha256(c['text'].encode()).hexdigest()==r['sha256'] for c,r in zip(chunks,out['coverage']))
            rows.append(dict(target=target,required_lines=required,coverage=out['coverage'],passed=hashes and all(any(c['source']['start_line']<=line<=c['source']['end_line'] for c in chunks) for line in required),chars=len(json.dumps(out,ensure_ascii=False))))
        path=ROOT/'output/phase67-gates/code-quality-track'/args.out
        with path.open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2)
        print(json.dumps({'passed':sum(r['passed'] for r in rows),'total':len(rows),'file':str(path)}))
        if not all(r['passed'] for r in rows):raise SystemExit(1)
    finally:router.close();cat.close()
if __name__=='__main__':main()
