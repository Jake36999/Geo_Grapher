"""Optional L2 must preserve source privacy, immutable caches and graph scope."""
import hashlib
import json
import sqlite3
import sys
from types import SimpleNamespace
import pytest


def api():
    from geographer import semantic
    return semantic


def encoder(fingerprint='fixture-model'):
    def encode(texts):
        return [[1.,0.] if any(term in text.lower() for term in ('orchard','apple')) else [0.,1.] for text in texts]
    return SimpleNamespace(fingerprint=fingerprint,encode=encode)


def test_hosted_specs_rejected_before_optional_imports_or_filesystem(monkeypatch):
    semantic=api()
    monkeypatch.setitem(sys.modules,'model2vec',None)
    for spec in ('api:openai:text-embedding','https://host/embed','model2vec:https://host/model','remote:model'):
        with pytest.raises(ValueError,match='local'):semantic.validate_spec(spec)


def test_representation_contains_own_comment_and_literal_without_execution(extract):
    semantic=api()
    graph,_,_=extract({'m.py':'# Orchard instructions for the field reader.\nRULES = "Pick the apple before its seeds fall."\nraise RuntimeError("SOURCE MUST NEVER RUN")\n'})
    eid=next(e.entity_id for e in graph.entities.values() if e.kind=='constant')
    value=semantic.entity_text(graph,eid)
    assert 'Orchard instructions' in value['text'] and 'Pick the apple' in value['text']
    assert value['sha256']==hashlib.sha256(value['text'].encode()).hexdigest()
    assert semantic.entity_text(graph,eid)==value


def test_cache_is_write_once_and_read_only_queries_find_local_synonyms(extract,tmp_path):
    semantic=api()
    graph,_,report=extract({'m.py':'def harvest():\n    """Pick an apple in the orchard."""\n    return 1\n\ndef network():\n    """Open a socket to the network."""\n    return 2\n'})
    eid=next(e.entity_id for e in graph.entities.values() if e.qualified_name.endswith('.harvest'))
    path=tmp_path/'semantic.sqlite'
    stats=semantic.SemanticCache.build(path,graph,report['snapshot_id'],encoder())
    assert stats['entities']==2 and stats['encoded']==2
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    # A cache hit may not invoke the document encoder again.
    no_document_encoding=SimpleNamespace(fingerprint='fixture-model',encode=lambda texts:(_ for _ in ()).throw(AssertionError('re-encoded documents')))
    assert semantic.SemanticCache.build(path,graph,report['snapshot_id'],no_document_encoding)['encoded']==0
    cache=semantic.SemanticCache.load(path,graph,report['snapshot_id'],encoder())
    assert cache.search('orchard')[0]['node_id']==eid
    assert cache.search('orchard',kinds=['class'])==[]
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    with pytest.raises(ValueError,match='snapshot|namespace'):semantic.SemanticCache.load(path,graph,'other-snapshot',encoder())
    with pytest.raises(ValueError,match='model|namespace'):semantic.SemanticCache.load(path,graph,report['snapshot_id'],encoder('different-model'))


def test_cache_rejects_corrupt_vectors_and_never_returns_other_graph(extract,tmp_path):
    semantic=api()
    graph,_,report=extract({'m.py':'def orchard():\n    """Apple harvest."""\n    pass\n'})
    other,_,_=extract({'other.py':'def orchard():\n    """Apple harvest."""\n    pass\n'},repo_id='other')
    path=tmp_path/'semantic.sqlite'
    semantic.SemanticCache.build(path,graph,report['snapshot_id'],encoder())
    with pytest.raises(ValueError,match='membership|representation'):semantic.SemanticCache.load(path,other,report['snapshot_id'],encoder())
    with sqlite3.connect(path) as c:c.execute("UPDATE embeddings SET vector_json='[NaN,0]'")
    with pytest.raises(ValueError,match='finite|digest|vector'):semantic.SemanticCache.load(path,graph,report['snapshot_id'],encoder())


def test_zero_vectors_are_omitted_and_query_bounds_are_explicit(extract,tmp_path):
    semantic=api()
    graph,_,report=extract({'m.py':'def nothing():\n    """No vector."""\n    pass\n'})
    zero=SimpleNamespace(fingerprint='zero-model',encode=lambda texts:[[0.,0.] for _ in texts])
    path=tmp_path/'semantic.sqlite'
    stats=semantic.SemanticCache.build(path,graph,report['snapshot_id'],zero)
    assert stats['zero_vectors']==1
    cache=semantic.SemanticCache.load(path,graph,report['snapshot_id'],zero)
    assert cache.search('anything')==[]
    with pytest.raises(ValueError,match='query'):cache.search('x'*10001)
    with pytest.raises(ValueError,match='limit'):cache.search('q',limit=201)


def test_ingest_can_embed_before_publication_without_changing_default(extract,tmp_path):
    from geographer.pipeline import ingest
    from geographer.source import Repository
    from geographer.store import SnapshotStore
    path=tmp_path/'at-ingest.sqlite'
    with SnapshotStore() as store:
        report=ingest(store,[Repository('r','rev',{'m.py':b'def pick():\n    """Orchard apple."""\n    pass\n'})],
            semantic=dict(cache=path,encoder=encoder()))
        assert report['semantic']['encoded']==1
        assert store.connection.execute('SELECT status FROM snapshot_sets WHERE snapshot_id=?',(report['snapshot_id'],)).fetchone()[0]=='complete'
        assert api().SemanticCache.load(path,store.graph(report['snapshot_id']),report['snapshot_id'],encoder()).search('apple')


def test_channel_fusion_preserves_exact_priority_and_records_match(extract,tmp_path):
    from geographer.retrieval import LexicalIndex
    from geographer.search_fusion import rank_queries
    graph,_,report=extract({'m.py':'def harvest():\n    """Gather a crop."""\n    pass\n\ndef orchard():\n    """Apple field."""\n    pass\n'})
    path=tmp_path/'cache.sqlite';semantic=api()
    semantic.SemanticCache.build(path,graph,report['snapshot_id'],encoder())
    cache=semantic.SemanticCache.load(path,graph,report['snapshot_id'],encoder())
    index=LexicalIndex(graph)
    try:
        result=rank_queries(index,['m.py.harvest'],semantic=cache)
        assert result['hits'][0]['node_id']==next(e.entity_id for e in graph.entities.values() if e.qualified_name=='m.py.harvest')
        assert all(h['match'] in {'lexical','semantic','both'} for h in result['hits'])
        assert result['semantic_enabled'] is True
    finally:index.close()


def test_default_front_door_does_not_open_semantic_cache(tmp_path,monkeypatch):
    from test_agent_scent import world
    from geographer.agent_requests import call_code
    # Use the existing public fixture's underlying generator with a local path.
    fixture=world.__wrapped__(tmp_path)
    router,_,_=next(fixture)
    monkeypatch.setattr(api().SemanticCache,'load',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('default opened semantic cache')))
    try:assert call_code(router,'search_entities',dict(graph_id='scent',query='UPLOAD_BYTES'))['entities']
    finally:
        with pytest.raises(StopIteration):next(fixture)


def test_enabled_front_door_keeps_caps_and_reports_channel_provenance(tmp_path):
    from test_agent_scent import world
    from geographer.agent_requests import call_code
    from geographer.tokens import TokenCounter
    fixture=world.__wrapped__(tmp_path);router,ids,_=next(fixture)
    path=tmp_path/'vectors.sqlite';enc=encoder()
    gid=router.resolve('scent');sid=router.catalog.graph(gid)['snapshot_id']
    try:
        with router.lease(gid) as svc:api().SemanticCache.build(path,svc.store.graph(sid),sid,enc)
        router.semantic_config=dict(cache=path,encoder=enc)
        out=call_code(router,'search_entities',dict(graph_id='scent',query='UPLOAD_BYTES'))
        assert out['entities'][0]['entity_id']==ids['UPLOAD_BYTES']
        assert out['result']['data']['semantic']['namespace']
        assert all(h['match'] in {'lexical','semantic','both'} for h in out['result']['data']['hits'])
        assert len(json.dumps(out,ensure_ascii=False))<=7500
        assert TokenCounter().count(out)==out['routing_budget']['used_tokens']
    finally:
        with pytest.raises(StopIteration):next(fixture)
