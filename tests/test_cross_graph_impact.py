import json
import shutil
import subprocess
import sys
import pytest
from test_bridges import hub_with_code_and_papers
from geographer.graph_router import GraphRouter
from geographer.source import Repository
from geographer.store import SnapshotStore


@pytest.fixture
def impact_world(hub_with_code_and_papers, tmp_path):
    cat,c,p,f = hub_with_code_and_papers
    with SnapshotStore(cat.graph(c)['code_database']) as store:
        entities=store.graph(cat.graph(c)['snapshot_id']).entities
        f=next(e.entity_id for e in entities.values() if e.qualified_name.endswith('.entity_linking'))
        g=next(e.entity_id for e in entities.values() if e.qualified_name.endswith('.knowledge_graph'))
    root=tmp_path/'transcript'; root.mkdir(); (root/'README.md').write_text('Transcript')
    t=cat.import_project(root,Repository.from_directory(root,'transcript'),label='transcript')['graph_id']
    profile=json.loads(cat.graph(t)['profile_json']); profile['stratum']={'trust_tier':'bronze_transcript','modality':'transcript'}
    cat.connection.execute('UPDATE graphs SET profile_json=? WHERE graph_id=?',(json.dumps(profile),t));cat.connection.commit()
    shutil.copyfile(tmp_path/'papers.sqlite',tmp_path/'transcript.sqlite')
    cat.attach_papers(t,tmp_path/'transcript.sqlite')
    def add(a,ar,b,br): return cat.add_bridge(a,ar,b,br,'reference','Reviewed pilot',[{'note':'operator'}])
    add(p,'doc:1#claim:3',c,'entity:'+f)
    add(p,'doc:1#claim:3',t,'doc:1')
    add(t,'doc:1',c,'entity:'+g)
    stale=add(p,'doc:2',c,'entity:'+g)
    cat.connection.execute("UPDATE artifact_states SET state='demoted_contestable' WHERE artifact_id=?",(stale,));cat.connection.commit()
    return cat,c,p,t,f,g,stale


def test_impact_costs_pinning_and_stale_exclusion(impact_world):
    from geographer.cross_graph import bridge_impact
    cat,c,p,t,f,g,stale=impact_world
    out=bridge_impact(cat,(p,'doc:1#claim:3'))
    reached={(r['graph_id'],r['ref']):r for r in out['dependants']}
    assert reached[c,'entity:'+f]['cost']==0.2
    assert reached[c,'entity:'+g]['cost']==1.2
    assert all(step['id']!=stale for r in out['dependants'] for step in r['path'])
    pinned=bridge_impact(cat,(p,'doc:1#claim:3'),pinned_graphs={t})
    assert next(r['cost'] for r in pinned['dependants'] if r['graph_id']==c and r['ref']=='entity:'+g)==0.4
    assert out==bridge_impact(cat,(p,'doc:1#claim:3'))


def test_conformance_uses_reviewed_bridges_and_cites(impact_world):
    from geographer.cross_graph import conformance
    cat,c,p,t,f,g,stale=impact_world
    out=conformance(cat,p,c)
    assert out['bridges_considered']==2
    assert any(r['state']=='VERIFIED_IMPLEMENTATION' and r['code_ref']=='entity:'+f for r in out['findings'])
    assert any(r['state']=='STALE_BRIDGE' and r['bridge_id']==stale for r in out['findings'])
    assert any(r['state']=='SPECIFICATION_ABSENCE' for r in out['findings'])
    assert all(cite.startswith(('papers/','code/')) for r in out['findings'] for cite in r['cite_as'])


def test_zero_bridges_means_no_invented_conformance(hub_with_code_and_papers):
    from geographer.cross_graph import conformance
    cat,c,p,_=hub_with_code_and_papers
    out=conformance(cat,p,c)
    assert out['findings']==[] and out['bridges_considered']==0 and out['hint']


def test_router_modes_are_scoped_and_budgeted(impact_world):
    cat,c,p,t,f,g,_=impact_world
    router=GraphRouter(cat,allowed={p,c},max_result_chars=7500)
    impact=router.analyze_cross_graphs([p,c],'bridge_impact',start={'graph_id':p,'ref':'doc:1#claim:3'},limit_tokens=1800)
    assert all(n['graph_id']!=t for n in impact['nodes'])
    assert impact['used_tokens']<=1800 and len(json.dumps(impact,ensure_ascii=False))<=7500
    theory=router.analyze_cross_graphs([c,p],'theory_conformance',theory_graph=p,code_graph=c,limit_tokens=1800)
    assert theory['items']
    router.close()


def test_modes_are_byte_deterministic_across_processes(impact_world):
    cat,c,p,t,_,_,_=impact_world
    path=cat.connection.execute('PRAGMA database_list').fetchone()[2]
    script="""import json,sys
from geographer.graph_catalog import GraphCatalog
from geographer.cross_graph import bridge_impact,conformance
cat=GraphCatalog(sys.argv[1])
print(json.dumps([bridge_impact(cat,(sys.argv[2],'doc:1#claim:3')),conformance(cat,sys.argv[2],sys.argv[3])],sort_keys=True))
cat.close()
"""
    cmd=[sys.executable,'-c',script,path,p,c]
    assert subprocess.check_output(cmd)==subprocess.check_output(cmd)


def test_conformance_uses_top_abbs_unbridged_entities(impact_world,monkeypatch):
    from geographer import discovery
    from geographer.cross_graph import conformance
    cat,c,p,_,_,_,_=impact_world
    with SnapshotStore(cat.graph(c)['code_database']) as store:
        file_id=next(e.entity_id for e in store.graph(cat.graph(c)['snapshot_id']).entities.values() if e.kind=='file')
    monkeypatch.setattr(discovery,'_boundary_bottlenecks',lambda g:[dict(entity_id=file_id,abbs=10)])
    assert any(r['state']=='UNDOCUMENTED_DIVERGENCE' and r['code_ref']=='entity:'+file_id for r in conformance(cat,p,c)['findings'])


def test_starting_at_code_walks_dependants_without_bridge(impact_world):
    from geographer.cross_graph import bridge_impact
    cat,c,p,t,f,g,_=impact_world
    out=bridge_impact(cat,(c,'entity:'+f),max_hops=1)
    assert any(r['ref']=='entity:'+g and r['cost']==1 for r in out['dependants'])
