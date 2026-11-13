"""No-model source and constant checks on the re-ingested gate copy."""
import argparse,json
from pathlib import Path
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.agent_requests import call_code

def main():
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise SystemExit('Use a new result path')
    cat=GraphCatalog(a.catalog);router=GraphRouter(cat,max_result_chars=7500);rows=[]
    try:
        for name in ('HELPER_TOOLS','MAX_EXTERNAL_RESULT','DEFAULT_CONTEXT_TOKENS'):
            found=call_code(router,'search_entities',dict(graph_id='librarian-v2',query=name))
            hit=found['entities'][0];eid=hit['entity_id'];gid=router.resolve('librarian-v2')
            with router.lease(gid) as svc:
                sid=cat.graph(gid)['snapshot_id'];g=svc.store.graph(sid);e=g.entities[eid]
                assert e.kind=='constant' and e.qualified_name.endswith('.'+name)
                assert any(r.subtype=='reads' and r.target_subject_id==eid for r in g.relationships.values())
                row=dict(name=name,entity_id=eid,cite_as=hit['cite_as'],kind=e.kind,source=hit['source'],
                    span=[e.start_line,e.end_line],helper_not_contracted=e.qi_cluster_id in (None,eid))
                assert row['helper_not_contracted']
            content=call_code(router,'get_entity_content',dict(graph_id='librarian-v2',entity_id=eid))
            row['content']=content['result']['data']['chunks'];assert row['content']
            rows.append(row);a.out.write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print('3/3 original constants rank first, return source and remain outside helper blocks')
    finally:router.close();cat.close()
if __name__=='__main__':main()
