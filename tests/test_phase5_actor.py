"""Actor wire, epistemic previews, source folding, and exact budget invariants."""
from __future__ import annotations
import copy,json
import pytest
from geographer.source_context import SourceTree
from starlette.testclient import TestClient
from geographer.analysis import DEFAULT_FILTER
from geographer.pipeline import ingest
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.tokens import TokenCounter
from geographer.server import create_http_app

def test_source_tree_preserves_decorators_multiline_and_clause_spines():
    raw='''@decorate
async def run(
    value: str,
):
    try:
        match value:
            case (
                "α"
            ):
                return value
            case _: return None
    except ValueError:
        raise
    finally:
        cleanup()
'''.encode('utf-8')
    tree=SourceTree(raw,'unicode.py','r')
    spine=tree.spine(10,10)
    assert [e['kind'] for e in spine]==['module','AsyncFunctionDef','Try','Match','case','Return']
    function=spine[1];assert function['start']==1 and function['header_end']==4
    assert spine[-2]['header_end']==9
    assert tree.spine(11,11)[-1]['kind']=='Return'
    assert tree.spine(13,13)[-2]['kind']=='ExceptHandler'
    assert tree.spine(15,15)[-2]['kind']=='finally'
    assert ''.join(tree.lines).encode('utf-8')==raw

def test_source_tree_line_only_focus_and_empty_artifact_are_honest():
    tree=SourceTree(b'x=1; y=2\n','inline.py','r')
    assert tree.spine(1,1)[-1]['kind']=='module'
    empty=SourceTree(b'','empty.py','r')
    assert empty.lines==[''] and empty.spine(1,1)==[empty.root]

@pytest.fixture
def actor():
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'lib.py':b'''def target(value: int) -> int:
    """Return the input value. This sentence is secondary."""
    return value

def helper(value):
    return target(value)

def run(value):
    if value:
        return helper(value)
    return 0
''','notes.md':b'# Network listener\n\nThe run function performs network work.\n\n## Details\n\nhelper calls target\n'})],stage=3)['snapshot_id']
        svc=QueryService(store,secret=b'x'*32)
        yield svc,sid

def base(sid,limit=8192,tokenizer='o200k_base'):
    return dict(schema_version='1.1',request_id='actor-test',snapshot_id=sid,identity_mode='canonical_map',budget=dict(limit_tokens=limit,tokenizer=tokenizer,allow_byte_fallback=False))

def id_of(svc,sid,name):return next(e.entity_id for e in svc._context(sid)['g'].entities.values() if e.qualified_name==name)

def checked(svc,op,q):
    result=svc.query(op,q);assert 'data' in result,result
    svc.wire11.validate(op,'response',result)
    assert TokenCounter(q['budget']['tokenizer']).count(result)<=q['budget']['limit_tokens']
    data=result['data'];ids={n['id'] for n in data['nodes']}
    assert all(r['source'] in ids and r['target'] in ids for r in data['relationships']+data['witnesses'])
    assert ids<=data['ids'].keys()
    return result

def context(svc,sid,limit=8192):
    return {**base(sid,limit), 'focus_id':id_of(svc,sid,'lib.py.run'),'grouping':{'mode':'kind','kind':'file'},'context_radius':1,
        'filter':copy.deepcopy(DEFAULT_FILTER),'pins':[],'qi':{'enabled':False,'max_diameter':2},'cursor':None}

def test_rich_context_has_no_initial_cursors_or_node_fingerprints(actor):
    svc,sid=actor;q=context(svc,sid);result=checked(svc,'get_architecture_context',q);data=result['data']
    assert data['relationships']
    for n in data['nodes']:
        assert not {'entity_id','ast_body_hash','wl_3hop_hash'}&n.keys()
        if n['source']:assert 'revision' not in n['source']
        if n['group_preview']:assert sum(n['group_preview']['kind_counts'].values())==n['member_count']
    for r in data['relationships']:
        assert 'witness_cursor' not in r and 'view_id' not in r
        assert sum(r['reason_counts'].values())==r['witness_count']
        assert r['preview_complete']==(r['witness_count']<=3)
        assert len({w['relationship_id'] for w in r['witness_preview']})==len(r['witness_preview'])
    again=checked(svc,'get_architecture_context',{**q,'request_id':'different'})
    assert again['data']['ids']==data['ids']
    # Returned mutable objects do not contaminate the retained query plan.
    result['data']['nodes'][0]['qualified_name']='corrupted'
    assert all(n['qualified_name']!='corrupted' for n in checked(svc,'get_architecture_context',q)['data']['nodes'])

def test_search_descriptors_and_documentary_relevance(actor):
    svc,sid=actor
    q={**base(sid),'query':'lib.py.target','mode':'hybrid','repo_ids':[],'kinds':[],'limit':20,'cursor':None}
    result=checked(svc,'search_entities',q);hit=result['data']['hits'][0]
    node=next(n for n in result['data']['nodes'] if n['id']==hit['node_id'])
    assert node['summary']['signature']=='def target(value: int) -> int'
    assert node['summary']['doc_gist']=='Return the input value.'
    assert result['data']['ids'][node['id']]==id_of(svc,sid,'lib.py.target')
    q['query']='network listener';result=checked(svc,'search_entities',q)
    assert any(h['informal_rank'] for h in result['data']['hits'])

def test_complete_typed_path_has_all_original_witnesses(actor):
    svc,sid=actor;q=context(svc,sid)
    q['pins']=[id_of(svc,sid,'lib.py.target')]
    q['path_request']=dict(template='CALL_CHAIN_WITH_HELPERS',max_hops=4,max_expansions=20000,undirected=False,boundary_model_digest=None)
    result=checked(svc,'get_architecture_context',q)
    path=result['data']['paths'][0];assert path['outcome']=='found' and len(path['steps'])==2
    assert {s['relationship_id'] for s in path['steps']}<={w['id'] for w in result['data']['witnesses']}

def test_source_folding_preserves_focal_bytes_headers_and_omission_handles(actor):
    svc,sid=actor
    q={**base(sid),'entity_id':id_of(svc,sid,'lib.py.run'),'content_kind':'source','start_line':10,'end_line':10,
        'context_mode':'source-context-v1','context_radius':1,'cursor':None}
    result=checked(svc,'get_entity_content',q);fold=result['data']['source_context']
    assert result['data']['chunks']==[] and fold['focal_complete']
    assert fold['focal_segments'][0]['text']=='        return helper(value)\n'
    assert any('def run(value)' in h['text'] for h in fold['enclosing_headers'])
    assert any('if value:' in h['text'] for h in fold['enclosing_headers'])
    assert fold['omissions'] and svc.read_handle(fold['omissions'][0]['content_handle'])['content_kind']=='source'

def test_source_entity_siblings_are_optional_grounded_stubs(actor):
    svc,sid=actor
    q={**base(sid),'entity_id':id_of(svc,sid,'lib.py.run'),'content_kind':'source','start_line':None,'end_line':None,
        'context_mode':'source-context-v1','context_radius':1,'cursor':None}
    result=checked(svc,'get_entity_content',q);fold=result['data']['source_context']
    assert fold['focal_segments'][0]['text'].startswith('def run(value):')
    assert any(s['signature'].startswith('def helper') for s in fold['sibling_stubs'])

@pytest.mark.parametrize('tokenizer',['o200k_base','cl100k_base'])
def test_actor_full_envelope_budgets_and_error_version(actor,tokenizer):
    svc,sid=actor
    for limit in (256,768,1536,3072,8192):
        q=context(svc,sid,limit);q['budget']['tokenizer']=tokenizer
        result=svc.query('get_architecture_context',q)
        assert result['schema_version']=='1.1'
        if 'error' in result:assert result['error']['code']=='BUDGET_TOO_SMALL'
        else:checked(svc,'get_architecture_context',q)

def test_http_versions_are_explicit_and_resources_stay_shared(actor):
    svc,sid=actor;q=context(svc,sid)
    with TestClient(create_http_app(svc),base_url='http://127.0.0.1:8765') as client:
        response=client.post('/api/v1.1/get_architecture_context',json=q)
        assert response.status_code==200,response.json()
        assert response.json()['schema_version']=='1.1'
        assert client.post('/api/v1/get_architecture_context',json=q).status_code==400

def test_all_shared_operations_serve_strict_actor_records(actor):
    svc,sid=actor;focus=id_of(svc,sid,'lib.py.target')
    graph=checked(svc,'get_architecture_context',context(svc,sid))['data'];relation=graph['relationships'][0]
    projection=graph['ids'][relation['id']]
    inspection={**base(sid),'view_id':graph['view_id'],'projection_id':projection,'relationship_id':None,
                'evidence_page_size':2,'evidence_cursor':None,'page_size':2,'cursor':None}
    result=checked(svc,'inspect_relationship_witnesses',inspection)
    for w in result['data']['witnesses']:assert result['data']['ids'][w['id']].startswith('rel:')
    checked(svc,'get_entity_content',{**base(sid),'entity_id':focus,'content_kind':'source','start_line':None,'end_line':None,
        'context_mode':'range','context_radius':0,'cursor':None})
    checked(svc,'find_dependants',{**base(sid),'entity_id':focus,'direction':'incoming','filter':copy.deepcopy(DEFAULT_FILTER),'max_depth':3,'max_results':20,'cursor':None})
    checked(svc,'find_similar_code',{**base(sid),'entity_id':focus,'mode':'exact_normalized_ast','repo_ids':[],'limit':10,'cursor':None})
    from geographer.rules import ArchitectureRules
    model=ArchitectureRules(b'''version: "1.0"
world_policy: open
components:
  - id: code
    selectors: [{repo_id: r, path_glob: "lib.py"}]
rules:
  - {id: require_self, type: require, source: code, target: code, rationale: "Fixture"}
''')
    svc.rules[model.digest]=model
    root=next(e.entity_id for e in svc._context(sid)['g'].entities.values() if e.kind=='repository')
    checked(svc,'check_architecture',{**base(sid),'model_digest':model.digest,'scope_id':root,'filter':copy.deepcopy(DEFAULT_FILTER),
        'include_satisfied':True,'page_size':20,'cursor':None})

def test_actor_continuations_preserve_evidence_identity(actor):
    svc,sid=actor;data=checked(svc,'get_architecture_context',context(svc,sid))['data'];r=data['relationships'][0]
    q={**base(sid),'view_id':data['view_id'],'projection_id':data['ids'][r['id']],'relationship_id':None,'evidence_page_size':1,'evidence_cursor':None,'page_size':1,'cursor':None}
    seen=set();evidence_seen=set()
    for _ in range(20):
        result=checked(svc,'inspect_relationship_witnesses',q)
        ids={result['data']['ids'][w['id']] for w in result['data']['witnesses']}
        evidence_ids={e['id'] for e in result['data']['evidence_handles']}
        assert not evidence_ids&evidence_seen
        if ids&seen:assert evidence_ids  # repeated definitions close newly paged evidence
        seen|=ids;evidence_seen|=evidence_ids
        cursor=result['data']['completeness']['next_cursor']
        if not cursor:break
        q['cursor']=cursor
    assert len(seen)==r['witness_count']

def test_actor_byte_bound_includes_alias_table(actor,tmp_path):
    svc,sid=actor;svc.token_directory=tmp_path;q=context(svc,sid)
    q['budget'].update(allow_byte_fallback=True,limit_tokens=8192)
    response=svc.query('get_architecture_context',q)
    assert 'data' in response,response
    from geographer.model import canonical
    assert response['budget']['guarantee']=='byte_bound' and len(canonical(response).encode('utf-8'))<=8192

def test_compact_aliases_are_directly_reusable_and_survive_memory_eviction(actor):
    svc,sid=actor;q=context(svc,sid);q.pop('identity_mode')
    data=svc.query('get_architecture_context',q)['data']
    assert data['ids']=={} and data['identity_scope'].startswith('handle:identity_scope:')
    relation=data['relationships'][0];scope=data['identity_scope'];svc.handles.clear();svc.cache.clear()
    inspection={**base(sid),'alias_scope':scope,'view_id':data['view_id'],'projection_id':relation['id'],'relationship_id':None,
        'evidence_page_size':1,'evidence_cursor':None,'page_size':2,'cursor':None}
    result=checked(svc,'inspect_relationship_witnesses',inspection)
    assert result['data']['witnesses']
    request={**base(sid),'alias_scope':result['data']['identity_scope'],'entity_id':result['data']['nodes'][0]['id'],
        'content_kind':'source','context_mode':'range','context_radius':0,'start_line':None,'end_line':None,'cursor':None}
    checked(svc,'get_entity_content',request)

def test_alias_scope_cannot_cross_snapshots(actor):
    svc,sid=actor;data=checked(svc,'get_architecture_context',context(svc,sid))['data']
    other=ingest(svc.store,[Repository('r','other',{'a.py':b'def other(): pass\n'})])['snapshot_id']
    q={**base(other),'alias_scope':data['identity_scope'],'entity_id':data['nodes'][0]['id'],'content_kind':'source',
        'context_mode':'range','context_radius':0,'start_line':None,'end_line':None,'cursor':None}
    assert svc.query('get_entity_content',q)['error']['code']=='SNAPSHOT_MISMATCH'
