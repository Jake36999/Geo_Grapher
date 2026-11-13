"""Constants are original source entities, not inferred answers."""
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.agent_requests import call_code
from geographer.drift import tier

SOURCE=b'# Tools available to workers.\nHELPER_TOOLS: tuple[str, ...] = ("read", "search")\n"Worker tool names."\nclass Limits:\n    MAX_SIZE = 7500\ndef selected():\n    return HELPER_TOOLS, Limits.MAX_SIZE\ndef local():\n    TEMP = 1\n    return TEMP\n'

def test_constant_inventory_source_reads_and_search(tmp_path):
    root=tmp_path/'repo';root.mkdir();(root/'m.py').write_bytes(SOURCE)
    cat=GraphCatalog(tmp_path/'cat.sqlite');row=cat.import_project(root,Repository.from_directory(root,'r'),label='constants')
    router=GraphRouter(cat)
    try:
        with router.lease(row['graph_id']) as svc:
            g=svc.store.graph(cat.graph(row['graph_id'])['snapshot_id']);constants=[e for e in g.entities.values() if e.kind=='constant']
            assert {e.qualified_name for e in constants}=={'m.py.HELPER_TOOLS','m.py.Limits.MAX_SIZE'}
            helper=next(e for e in constants if e.qualified_name.endswith('HELPER_TOOLS'))
            assert helper.start_line==helper.end_line==2
            assert g.entities[helper.parent_id].kind=='file'
            assert any(i['entity_id']==helper.entity_id for i in g.incidences)
            reads=[r for r in g.relationships.values() if r.subtype=='reads']
            assert {g.entities[r.target_subject_id].qualified_name for r in reads}=={e.qualified_name for e in constants}
            assert all(g.entities[r.source_subject_id].qualified_name.endswith('.selected') for r in reads)
        found=call_code(router,'search_entities',dict(graph_id='constants',query='HELPER_TOOLS'))
        assert found['entities'][0]['entity_id']==helper.entity_id
        assert found['result']['data']['hits'][0]['score']==1.0
        content=call_code(router,'get_entity_content',dict(graph_id='constants',entity_id=helper.entity_id,start_line=2,end_line=2))
        chunks=content['result']['data']['chunks']
        assert ''.join(c['text'] for c in chunks)==SOURCE.decode().splitlines(keepends=True)[1]
    finally:router.close();cat.close()

def test_constant_value_fingerprint_drift_and_v10_compatibility(tmp_path):
    with SnapshotStore(tmp_path/'drift.sqlite') as store:
        ids=[];graphs=[]
        for version,value in [('a',1),('b',2)]:
            sid=ingest(store,[Repository('r',version,{'m.py':f'LIMIT = {value}\n'.encode()})],stage=3)['snapshot_id']
            ids.append(sid);graphs.append(store.graph(sid))
        a,b=graphs;eid=next(e.entity_id for e in a.entities.values() if e.kind=='constant')
        assert eid in b.entities
        assert a.fingerprints[eid]['span_sha256'] and b.fingerprints[eid]['ast_body_hash']
        assert tier(a.fingerprints[eid],b.fingerprints[eid],1,1,False)=='BODY_REFACTOR'
        from geographer.service import QueryService
        svc=QueryService(store)
        svc.active_snapshot=ids[1];svc.active_version='1.0'
        assert svc._node(svc._context(ids[1]),eid)['kind']=='fragment'


def test_full_preceding_comment_block_is_constant_documentation(extract):
    from geographer.retrieval import LexicalIndex
    source = '# Used when upload route has no declared window.\n# Values are measured in bytes.\nBUFFER_LIMIT = 4096\n\n# Unrelated preceding statement.\nOTHER = 2 # do not associate with next constant\nNEXT = 3\n'
    graph, _, _ = extract({'limits.py': source})
    constants = {e.qualified_name.rsplit('.', 1)[-1]: e for e in graph.entities.values() if e.kind == 'constant'}
    fragments = {e.entity_id: e for e in graph.entities.values() if e.kind == 'fragment'}
    def lines(name):
        return {fragments[i['fragment_id']].start_line for i in graph.incidences
                if i['entity_id'] == constants[name].entity_id and i['role'] == 'rationale_for'}
    assert lines('BUFFER_LIMIT') == {1, 2}
    assert 6 not in lines('NEXT')
    index = LexicalIndex(graph)
    try:
        hits = index.search('upload route window', kinds=['constant'], mode='documentation')
        assert hits and hits[0]['node_id'] == constants['BUFFER_LIMIT'].entity_id
        assert hits[0]['fragment_ids']
    finally:
        index.close()
