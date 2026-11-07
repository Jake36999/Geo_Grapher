from itertools import combinations
from pathlib import Path
import copy
import hashlib

import pytest

from geographer.contraction import contract_helpers,distances
from geographer.cursors import CursorPlans,InvalidCursor
from geographer.model import Graph,Entity,Relationship,canonical
from geographer.rules import ArchitectureRules,RuleConflict,glob_regex
from geographer.tokens import TokenCounter,TokenizerUnavailable,weight_path
from geographer.wire import WireContracts


def test_offline_encodings_match_official_tiktoken(monkeypatch,tmp_path):
    import requests,urllib.request,tiktoken
    monkeypatch.setenv('TIKTOKEN_CACHE_DIR',str(tmp_path))
    for name in ['o200k_base','cl100k_base']:
        source=Path(__file__).resolve().parents[1]/'assets/tiktoken'/f'{name}.tiktoken'
        url=f'https://openaipublic.blob.core.windows.net/encodings/{name}.tiktoken'
        (tmp_path/hashlib.sha1(url.encode()).hexdigest()).write_bytes(source.read_bytes())
        (tmp_path/f'{name}.tiktoken').write_bytes(source.read_bytes())
    def forbidden(*a,**kw):raise AssertionError('Network access during offline counting')
    monkeypatch.setattr(requests,'get',forbidden);monkeypatch.setattr(urllib.request,'urlopen',forbidden)
    sample={'text':'κόσμος 中文 ∀x <|endoftext|> <|fim_prefix|>','values':[True,None,3.5]}
    for name in ['o200k_base','cl100k_base']:
        counter=TokenCounter(name,directory=tmp_path)
        assert counter.exact
        assert counter.count(sample)==len(tiktoken.get_encoding(name).encode_ordinary(canonical(sample)))
    missing=tmp_path/'missing'
    assert not TokenCounter('o200k_base',True,missing).exact
    with pytest.raises(TokenizerUnavailable):TokenCounter('o200k_base',False,missing)


def test_cursor_lru_ttl_and_snapshot_binding():
    now=[0]
    cache=CursorPlans(secret=b'x'*32,max_plans=2,ttl_seconds=10,clock=lambda:now[0])
    a=cache.create('s','a','v','items',[],{},{});cursor=cache.cursor(a,[])
    assert cache.resume(cursor,'s','a')[0] is a
    with pytest.raises(InvalidCursor):cache.resume(cursor,'other','a')
    cache.create('s','b','v','items',[],{},{});cache.create('s','c','v','items',[],{},{});
    with pytest.raises(InvalidCursor):cache.resume(cursor,'s','a')
    c=cache.plans[('s','c')];cursor=cache.cursor(c,[]);now[0]=11
    with pytest.raises(InvalidCursor):cache.resume(cursor,'s','c')


def test_cursor_total_unit_retention_limit():
    cache=CursorPlans(secret=b'x'*32,max_plans=100,max_units=10,max_total_units=3)
    cache.create('s','a','v','items',[1,2],{},{});cache.create('s','b','v','items',[3,4],{},{})
    assert list(cache.plans)==[('s','b')]
    with pytest.raises(ValueError):cache.create('s','c','v','items',[1,2,3,4],{},{})


@pytest.mark.parametrize('exports',["__all__ = '_first'", "__all__ = ['_first']; __all__.append('_second')", "__all__: list[str] = ['_first', '_second']"])
def test_dynamic_and_annotated_exports_protect_helper_contraction(exports):
    from geographer.pipeline import ingest
    from geographer.source import Repository
    from geographer.store import SnapshotStore
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'a.py':(exports+'\ndef _first(): return 1\ndef _second(): return _first()\n').encode()})],stage=2)['snapshot_id']
        graph=store.graph(sid);_,groups,_=contract_helpers(graph,sid,diameter=2)
        assert all(len(members)==1 for members in groups.values())


def test_actual_contraction_bounds_exhaustive_small_trees():
    total=0
    for n in range(2,6):
        for edges in combinations(list(combinations(range(n),2)),n-1):
            adj={str(v):set() for v in range(n)}
            for u,v in edges:adj[str(u)].add(str(v));adj[str(v)].add(str(u))
            if len(distances(adj,'0'))!=n:continue
            g=Graph()
            for v in adj:g.add(Entity(v,'repo','function','module._h'+v,None))
            for i,(u,v) in enumerate(edges):g.relationships[str(i)]=Relationship(str(i),str(u),str(v),str(u),str(v),'calls','exact',str(i))
            mapping,groups,report=contract_helpers(g,'snapshot',diameter=2)
            q={v:set() for v in groups}
            for u,v in edges:
                a,b=mapping[str(u)],mapping[str(v)]
                if a!=b:q[a].add(b);q[b].add(a)
            for u in adj:
                original=distances(adj,u);quotient=distances(q,mapping[u])
                for v in adj:
                    dg,dh=original[v],quotient[mapping[v]]
                    assert dh<=dg<=report['A']*dh+report['B']
            assert report['measured_max_intrinsic_diameter']<=2
            assert len(mapping)==n;total+=1
    assert total==145


RULES=b'''version: "1.0"
world_policy: open
components:
  - id: a
    selectors: [{repo_id: repo, path_glob: "src/**/a.py"}]
  - id: b
    selectors: [{repo_id: repo, qualified_name_regex: "module[.].*"}]
rules:
  - {id: needs_b, type: require, source: a, target: b, rationale: yes}
'''


def test_rules_yaml12_globs_and_validation():
    model=ArchitectureRules(RULES)
    assert model.model['rules'][0]['rationale']=='yes'
    assert glob_regex('src/**/a.py').fullmatch('src/a.py')
    assert glob_regex('src/**/a.py').fullmatch('src/x/y/a.py')
    for raw in [RULES+b'world_policy: closed\n',RULES.replace(b'world_policy: open',b'world_policy: &x open'),
                RULES.replace(b'"module[.].*"',b'"(a+)+"'),RULES.replace(b'source: a',b'source: missing')]:
        with pytest.raises(RuleConflict):ArchitectureRules(raw)


def test_regex_mapping_batch_and_overlap():
    g=Graph();g.add(Entity('one','repo','function','module.target',None,rel_path='src/a.py'))
    model=ArchitectureRules(RULES)
    with pytest.raises(RuleConflict,match='multiple'):model.map_entities(g,'s')


def test_strict_runtime_models_are_from_all_eight_contracts():
    w=WireContracts()
    assert len(w.adapters)==16
    assert set(w.document['operations'])=={'search_entities','get_architecture_context','inspect_relationship_witnesses',
        'get_entity_content','find_dependants','check_architecture','find_similar_code','viewport_frame'}


def test_missing_required_is_inconclusive_when_analysis_incomplete():
    model=ArchitectureRules(RULES.replace(b'qualified_name_regex: "module[.].*"',b'path_glob: "storage/**"'))
    g=Graph();g.add(Entity('one','repo','function','module.target',None,rel_path='src/a.py'))
    partial=dict(status='partial',limitations=['Reflection unresolved'])
    _,findings=model.check(g,'s',{'one'},partial)
    assert findings[0]['status']=='inconclusive' and findings[0]['witness_count']==0
    complete=dict(status='complete_for_declared_static_subset',limitations=[])
    _,findings=model.check(g,'s',{'one'},complete)
    assert findings[0]['status']=='missing_required'
    assert not g.relationships
