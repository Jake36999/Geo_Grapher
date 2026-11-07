from collections import Counter, deque
from dataclasses import replace
from itertools import product
import json

from geographer.analysis import (TreeIndex,partition,project,tarjan,condensations,wl3,
    boundary_ratios,cayley_bounds,materialize_view,witness_page,DEFAULT_FILTER)
from geographer.model import Graph, Entity, Relationship
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore, PublicationError
import pytest


def tree_fixture():
    parents={'r':None,'a':'r','b':'r','a1':'a','a2':'a','b1':'b','b2':'b'}
    g=Graph()
    for eid,p in parents.items():
        g.add(Entity(eid,'@workspace' if p is None else 'repo','workspace' if p is None else 'directory',eid,p,
                     sort='synthetic' if p is None else 'entity'))
    g.augment()
    return g,parents


def test_exhaustive_residual_partitions_and_internal_edges():
    g,parents=tree_fixture();tree=TreeIndex(g)
    cases=0
    for bits in product([False,True],repeat=6):
        E={'r'}|{v for v,on in zip([x for x in parents if x!='r'],bits) if on}
        if any(v!='r' and parents[v] not in E for v in E):continue
        part=partition(g,'snapshot',{'mode':'mixed','revealed_ids':sorted(E)})
        members=[v for group in part.groups.values() for v in group]
        assert Counter(members)==Counter({v:1 for v in ['a1','a2','b1','b2']})
        assert len(part.representatives)==4
        cases+=1
    assert cases==25
    p=partition(g,'s',{'mode':'mixed','revealed_ids':['a1']})
    assert p.groups['a1']=={'a1'}
    assert sorted(len(m) for m in p.groups.values())==[1,1,2]
    assert 'a' not in p.groups and 'r' not in p.groups


def test_lca_doi_matches_naive_distances():
    g,_=tree_fixture();tree=TreeIndex(g)
    for u in g.entities:
        for v in g.entities:
            path_u=tree.ancestors(u);path_v=tree.ancestors(v)
            common=[p for p,q in zip(path_u,path_v) if p==q][-1]
            assert tree.lca(u,v)==common
            assert tree.distance(u,v)==len(path_u)+len(path_v)-2*(g.entities[common].depth+1)
        assert tree.context(u,0)==set(tree.ancestors(u))


def test_tarjan_quotient_cycle_trap_and_rank():
    vertices=['a1','a2','b1','b2'];edges=[('a1','b1'),('b2','a2')]
    assert all(len(c)==1 for c in tarjan(vertices,edges))
    result=condensations('s','v','f',vertices,edges)
    assert result['b1']['dag_rank']==1
    quotient=[('A','B'),('B','A')]
    assert tarjan(['A','B'],quotient)==[('A','B')]
    assert condensations('s','q','f',['A','B'],quotient)['A']['component_size']==2
    chain=[(str(i),str(i+1)) for i in range(5000)]
    assert len(tarjan([str(i) for i in range(5001)],chain))==5001


def metric_fixture():
    g=Graph()
    for v in ['a','b','c','isolated']:
        g.add(Entity(v,'repo','function',v,None))
    for rid,u,v,w in [('ab','a','b',2),('ba','b','a',1),('aa','a','a',3),('bc','b','c',4)]:
        g.relationships[rid]=Relationship(rid,u,v,u,v,'calls','exact',rid,weight=w)
    return g


def test_directed_and_undirected_degree_volume_metrics():
    g=metric_fixture()
    values={r['mode']:r for r in boundary_ratios(g,{'a','b'})}
    assert values['outgoing']['volume']==10 and values['outgoing']['ratio']==.4
    assert values['incoming']['volume']==6 and values['incoming']['ratio']==0
    assert values['undirected']['volume']==10 and values['undirected']['ratio']==.4
    assert all(r['ratio'] is None for r in boundary_ratios(g,{'isolated'}))
    bounds=cayley_bounds(g.entities,g.relationships.values())
    connected=next(r for r in bounds if r['n']==3)
    assert connected['m']==2 and connected['lower_bound']==.5
    assert connected['removed_self_loops']==1 and connected['collapsed_parallel_edges']==1
    assert next(r for r in bounds if r['n']==1)['status']=='not_applicable'


def test_wl_synchronous_directed_typed_and_multiplicity():
    g=metric_fixture()
    original=wl3(g)
    duplicate=replace(g.relationships['ab'],relationship_id='ab2',occurrence_key='ab2')
    g.relationships['ab2']=duplicate
    assert original['a']!=wl3(g)['a']
    g.relationships.pop('ab2')
    g.relationships['ab']=replace(g.relationships['ab'],subtype='imports')
    assert original['a']!=wl3(g)['a']
    g.relationships['ab']=replace(g.relationships['ab'],source_id='b',target_id='a',source_subject_id='b',target_subject_id='a',subtype='calls')
    assert original['a']!=wl3(g)['a']


def test_materialized_parallel_witnesses_keyset_and_publication(extract):
    graph,store,report=extract({'a.py':'def f(): pass\ndef g():\n f()\n f()\ng()\n'},publish=False)
    sid=report['snapshot_id']
    vid,part=materialize_view(store,sid,graph,{'mode':'kind','kind':'file'})
    row=store.connection.execute('SELECT * FROM quotient_projections WHERE view_id=?',(vid,)).fetchone()
    assert row['is_internal']==1 and row['witness_count']==3
    seen=[];after=''
    while True:
        page=witness_page(store,sid,vid,row['projection_id'],after,1)
        if not page:break
        seen.append(page[0]['relationship_id']);after=seen[-1]
    assert len(seen)==len(set(seen))==3
    assert not store.validate(sid)
    store.publish(sid)
    plan=store.connection.execute('EXPLAIN QUERY PLAN SELECT * FROM quotient_witness_map WHERE snapshot_id=? AND view_id=? AND projection_id=? AND relationship_id>? ORDER BY relationship_id LIMIT 10',(sid,vid,row['projection_id'],'' )).fetchall()
    assert any('INDEX' in str(tuple(r)) for r in plan)


def test_missing_witness_or_broken_scc_blocks_publication(extract):
    graph,store,report=extract({'a.py':'def f(): pass\nf()\n'},publish=False)
    sid=report['snapshot_id'];vid,_=materialize_view(store,sid,graph,{'mode':'atomic'})
    store.connection.execute('UPDATE level_scc_condensations SET dag_rank=999');store.connection.commit()
    with pytest.raises(PublicationError,match='SCC'):store.publish(sid)


def test_stage2_ingestion_computes_real_cached_values():
    with SnapshotStore() as store:
        report=ingest(store,[Repository('r','rev',{'a.py':b'def helper(): pass\ndef run(): helper()\n'})],stage=2)
        assert report['stage']==2 and report['status']=='complete'
        assert store.connection.execute('SELECT count(*) FROM analysis_views').fetchone()[0]==3
        assert store.connection.execute('SELECT count(*) FROM entities WHERE wl_3hop_hash IS NOT NULL').fetchone()[0]>=3
        assert store.connection.execute("SELECT count(*) FROM analysis_results WHERE algorithm_version='boundary-cayley-v1'").fetchone()[0]>0
        assert not store.validate(report['snapshot_id'])


def test_staged_projection_equals_direct_and_preserves_each_witness(extract):
    lib=Repository('library','r',{'lib.py':b'def f(): pass\n'},resolution_group='linked')
    g,_,_=extract({'app.py':'from lib import f\ndef run():\n f()\n f()\nrun()\n'},others=[lib],resolution_group='linked')
    fine=partition(g,'s',{'mode':'kind','kind':'file'})
    coarse=partition(g,'s',{'mode':'kind','kind':'repository'})
    a=project(g,fine,'fine');b=project(g,coarse,'coarse')
    fine_to_coarse={rep:coarse.representatives[next(iter(atoms))] for rep,atoms in fine.groups.items()}
    staged={}
    for row in a:
        key=(fine_to_coarse[row['source_rep_id']],fine_to_coarse[row['target_rep_id']],row['family'],row['subtype'],row['resolution_status'])
        staged.setdefault(key,set()).update(row['witnesses'])
    direct={(r['source_rep_id'],r['target_rep_id'],r['family'],r['subtype'],r['resolution_status']):set(r['witnesses']) for r in b}
    assert staged==direct
    assert sum(map(len,direct.values()))==len(set().union(*direct.values()))


def test_semantic_determinism_in_fresh_hash_seed_processes():
    import subprocess,sys,os
    program='''
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.pipeline import ingest
from geographer.model import canonical
with SnapshotStore() as s:
 r=ingest(s,[Repository('r','rev',{'a.py':b'def f(): pass\\ndef g(): f()\\n'})],stage=2)
 data=s.export(r['snapshot_id']);data['tables']['snapshot_sets'][0].pop('created_at')
 for table in ['analysis_views','view_representatives','partition_members','quotient_projections','quotient_witness_map','level_scc_condensations']:
  data[table]=sorted([dict(row) for row in s.connection.execute('SELECT * FROM '+table)],key=canonical)
 print(canonical(data))
'''
    results=[]
    for seed in ['1','2']:
        env={**os.environ,'PYTHONHASHSEED':seed}
        results.append(subprocess.run([sys.executable,'-c',program],env=env,check=True,capture_output=True,text=True).stdout)
    assert results[0]==results[1]
