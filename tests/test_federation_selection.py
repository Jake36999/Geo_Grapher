"""pc-mckp-v1 federation: intent, utility, exact permutation-invariant selection, strata."""
import itertools,json,sys
from pathlib import Path

import pytest
from geographer.federation import intent,utility,select,Candidate
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.tokens import TokenCounter

sys.path.insert(0,str(Path(__file__).parent))
from test_graph_catalog import import_graph


def test_intent_classifier():
    assert intent("parse_document")=="identifier" and intent("GraphRouter.query")=="identifier"
    assert intent("how are graphs isolated")=="conceptual" and intent("legacy solver notes")=="historical"


def test_volume_dampener_prefers_small_curated_store():
    small=utility("gold_paper","paper","conceptual",0.55,[1,2,3],0)
    big=utility("bronze_transcript","transcript","conceptual",85.32,[1,2,3,4,5],0)
    assert small>big


def test_select_is_permutation_invariant():
    cands=[Candidate(g,t,tok,u) for g,t,tok,u in [
        ("g_a","full",1800,9000),("g_a","compact",700,6000),
        ("g_b","full",1600,8000),("g_b","compact",600,5000),
        ("g_c","full",2500,3000),("g_c","compact",900,1500)]]
    results={tuple(sorted(select(list(p),3000).items())) for p in itertools.permutations(cands)}
    assert len(results)==1


def test_select_tie_break_is_deterministic():
    cands=[Candidate("g_a","full",100,50),Candidate("g_b","full",100,50)]
    results={tuple(sorted(select(list(p),100).items())) for p in itertools.permutations(cands)}
    assert results=={(("g_a","full"),("g_b","omit"))}


def test_select_is_exact_not_greedy():
    cands=[Candidate("g_a","full",3000,100),Candidate("g_b","full",1500,60),Candidate("g_c","full",1500,60)]
    assert select(cands,3000)=={"g_a":"omit","g_b":"full","g_c":"full"}


def test_pc_mckp_degenerate_inputs():
    assert select([],4096)=={}
    assert select([Candidate("g_a","full",5000,10),Candidate("g_a","compact",3000,5)],2048)=={"g_a":"omit"}
    assert select([Candidate("g_a","full",100,0),Candidate("g_a","compact",50,0)],4096)=={"g_a":"omit"}


def test_utility_rejects_unknown_enums():
    with pytest.raises(ValueError):utility("platinum","code","identifier",1.,[1],0)
    with pytest.raises(ValueError):utility("gold","video","identifier",1.,[1],0)


@pytest.fixture
def two(tmp_path):
    catalog=GraphCatalog(tmp_path/'catalog'/'catalog.sqlite')
    a=import_graph(catalog,tmp_path/'a','A');b=import_graph(catalog,tmp_path/'b','B')
    router=GraphRouter(catalog)
    yield catalog,router,a['graph_id'],b['graph_id']
    router.close();catalog.close()


def test_set_stratum_writes_profile_json_and_validates(two):
    catalog,_,a,_b=two
    before=json.loads(catalog.graph(a)['profile_json'])
    catalog.set_stratum(a,'primary','gold','code')
    after=json.loads(catalog.graph(a)['profile_json'])
    assert after['stratum']=={'role':'primary','trust_tier':'gold','modality':'code'}
    assert {k:v for k,v in after.items() if k!='stratum'}==before
    for bad in (('primary','platinum','code'),('primary','gold','video'),('','gold','code')):
        with pytest.raises(ValueError):catalog.set_stratum(a,*bad)
    with pytest.raises(ValueError):catalog.set_stratum('g_nope','primary','gold','code')
    assert json.loads(catalog.graph(a)['profile_json'])==after


def fake_query(sizes,hits_for=None):
    """Envelopes whose size scales with limit; `sizes` maps graph_id to padding words per result."""
    def fake(gid,operation,req):
        n=min(req['limit'],(hits_for or {}).get(gid,req['limit']))
        hits=[dict(node_id=f'n{i}') for i in range(n)]
        nodes=[dict(id=f'n{i}',qualified_name=f'pkg.item{i}') for i in range(n)]
        return dict(graph_id=gid,graph_label=gid,result=dict(data=dict(hits=hits,nodes=nodes,pad='x '*(sizes[gid]*n))))
    return fake


def test_federation_response_carries_selection_and_is_order_independent(two):
    _,router,a,b=two
    outcomes=[]
    for order in ([a,b],[b,a]):
        r=router.federated_search(order,'methods',limit_tokens=4096)
        assert r['ranking']=='independent_per_graph_no_global_rank'
        assert r['selection']['method']=='pc-mckp-v1'
        assert set(r['selection']['tiers'])==set(r['selection']['utility'])=={a,b}
        assert set(r['selection']['tiers'].values())=={'full'} and r['results']
        assert r['used_tokens']==TokenCounter().count(r)<=4096
        outcomes.append((sorted(x['graph_id'] for x in r['results']),r['omitted'],r['selection']))
    assert outcomes[0]==outcomes[1]


def test_all_full_is_chosen_when_it_fits(two,monkeypatch):
    catalog,router,a,b=two
    monkeypatch.setattr(router,'query',fake_query({a:100,b:100}))
    r=router.federated_search([a,b],'research',limit_tokens=2048)
    assert r['selection']['tiers']=={a:'full',b:'full'} and r['omitted']==[]
    assert r['used_tokens']<=2048


def test_tight_budget_degrades_to_compact_when_full_does_not_fit(two,monkeypatch):
    catalog,router,a,b=two
    monkeypatch.setattr(router,'query',fake_query({a:220,b:220}))
    roomy=router.federated_search([a,b],'research',limit_tokens=32768)
    assert set(roomy['selection']['tiers'].values())=={'full'}
    tight=router.federated_search([a,b],'research',limit_tokens=2048)
    assert tight['used_tokens']==TokenCounter().count(tight)<=2048
    tiers=tight['selection']['tiers']
    assert 'compact' in set(tiers.values()) and set(tiers.values())!={'full'}
    reasons={o['graph_id']:o['reason'] for o in tight['omitted']}
    for gid,tier in tiers.items():
        assert reasons.get(gid)=={'compact':'budget_compact_only','omit':'budget_omitted'}.get(tier)


def test_order_independent_real_choice_under_tight_budget(two,monkeypatch):
    catalog,router,a,b=two
    catalog.set_stratum(a,'primary','gold','code');catalog.set_stratum(b,'primary','bronze','code')
    monkeypatch.setattr(router,'query',fake_query({a:120,b:700}))
    outcomes=[]
    for order in ([a,b],[b,a]):
        r=router.federated_search(order,'research',limit_tokens=2048)
        assert r['used_tokens']<=2048
        outcomes.append((r['results'],r['omitted'],r['selection']))
    assert outcomes[0]==outcomes[1]
    tiers=outcomes[0][2]['tiers']
    assert tiers[a]=='full' and tiers[b]!='full'


def test_healthy_graph_without_hits_is_omitted_as_no_relevant_hits(two,monkeypatch):
    catalog,router,a,b=two
    monkeypatch.setattr(router,'query',fake_query({a:50,b:50},hits_for={b:0}))
    r=router.federated_search([a,b],'research',limit_tokens=4096)
    assert r['selection']['tiers']=={a:'full',b:'omit'} and r['selection']['utility'][b]==0
    assert r['omitted']==[dict(graph_id=b,reason='no_relevant_hits')]


def test_paper_only_graph_defaults_to_silver_paper(two,tmp_path):
    import sqlite3
    catalog,router,a,b=two
    path=tmp_path/'papers.sqlite';conn=sqlite3.connect(path);conn.execute('CREATE TABLE read_documents(id INTEGER)');conn.commit();conn.close()
    catalog.attach_papers(a,path)
    assert router._stratum(catalog.graph(a))==('silver','paper')
    assert router._stratum(catalog.graph(b))==('silver','code')
    catalog.set_stratum(a,'primary','gold','doc')
    assert router._stratum(catalog.graph(a))==('gold','doc')


def test_cli_set_graph_stratum(two,monkeypatch,capsys):
    catalog,_,a,_b=two
    from geographer import cli
    monkeypatch.setattr(sys,'argv',['geographer','set-graph-stratum','--catalog',str(catalog.path),'--graph-id',a,'--role','primary','--trust-tier','bronze','--modality','doc'])
    cli.main()
    assert json.loads(capsys.readouterr().out)['stratum']=={'role':'primary','trust_tier':'bronze','modality':'doc'}
    assert json.loads(catalog.graph(a)['profile_json'])['stratum']=={'role':'primary','trust_tier':'bronze','modality':'doc'}
