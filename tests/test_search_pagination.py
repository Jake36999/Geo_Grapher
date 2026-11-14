"""Capped search must make omitted ranked candidates reachable."""
import json
from geographer.agent_requests import call_code
from geographer.source import Repository
from test_agent_scent import world


def test_pages_expose_all_ranked_hits_without_repeats_and_preserve_cap(world,tmp_path):
    root=tmp_path/'pagination';root.mkdir()
    (root/'long_documented_operations.py').write_text('\n'.join(
        f'def orchard_capacity_operation_with_a_descriptive_name_{i}(value):\n    """Compute the orchard capacity and preserve the documented bounded upload fallback behavior."""\n    return value + {i}\n' for i in range(10)),encoding='utf-8')
    router=world[0]
    gid=router.catalog.import_project(root,Repository.from_directory(root,'pages'),label='pages')['graph_id']
    offset=0;seen=[]
    for page in range(10):
        out=call_code(router,'search_entities',dict(graph_id=gid,query='orchard capacity',kinds=['function'],offset=offset))
        ids=[r['entity_id'] for r in out['entities']]
        assert not set(ids)&set(seen)
        assert len(json.dumps(out,ensure_ascii=False))<=7500
        if page==0:assert len(ids)<8 and out['next_offset']==len(ids)
        seen+=ids
        if 'next_offset' not in out:break
        assert out['next_offset']>offset
        offset=out['next_offset']
    assert len(seen)==10
