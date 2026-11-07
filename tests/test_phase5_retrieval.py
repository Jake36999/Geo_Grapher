"""KG2–KG5 source-independent fixtures and bounded path reference oracles."""
import copy
from collections import deque
import pytest
from geographer.documents import parse_document
from geographer.retrieval import LexicalIndex,TypedBridge
from geographer.analysis import DEFAULT_FILTER,wl3,boundary_ratios
from geographer.model import Graph,Entity,Relationship

def test_document_headings_and_code_are_separate():
    raw=b'# Root\n\n### Skipped\ntext\n\n```md\n# Not a heading\n```\n\n    # Indented\n\nRepeat\n------\n\n## Repeat\n\n<div>\n# HTML content\n</div>\n'
    doc=parse_document(raw,'notes.md');sections=doc['sections']
    assert [s['heading'] for s in sections]==['','Root','Skipped','Repeat','Repeat']
    assert sections[2]['parent_section_id']==sections[1]['section_id']
    assert len({s['section_id'] for s in sections})==len(sections)
    assert all(raw[s['start_byte']:s['end_byte']] for s in sections)
    assert len(parse_document(b'# plain\nbody','notes.txt')['sections'])==1

def test_documentary_tree_does_not_change_code_hashes_or_dependency_degree(extract):
    code={'a.py':'def f(): pass\ndef g(): f()\n'}
    a,_,_=extract(code);b,_,_=extract({**code,'notes.md':'# Subsystem\n\nf uses g\n\n## Details\n\ng calls f is a documentary assertion\n'})
    assert set(a.relationships)==set(b.relationships)
    assert wl3(a)==wl3(b)
    subjects={e.entity_id for e in a.entities.values() if e.kind in {'file','function'}}
    assert boundary_ratios(a,subjects)==boundary_ratios(b,subjects)
    for eid,e in a.entities.items():
        if e.sort=='entity':assert e.parent_id==b.entities[eid].parent_id
    assert any(v['algorithm_version']=='documentary-tree-v1' for v in b.analyses.values())

def test_exact_lookup_cannot_be_outranked_by_prose_and_subtokens_work(extract):
    g,_,_=extract({'a.py':'def HTTPServer_build(value: int) -> int:\n """Construct a network listener."""\n return value\n',
                   'notes.md':'# Network listeners\n\nHTTPServer_build constructs a listener.\n'})
    index=LexicalIndex(g)
    try:
        target=next(e.entity_id for e in g.entities.values() if e.qualified_name=='a.py.HTTPServer_build')
        assert index.search('a.py.HTTPServer_build')[0]['node_id']==target
        assert any(h['node_id']==target for h in index.search('HTTP server build'))
        hits=index.search('network listener');assert any(h['node_id']==target and h['informal_rank'] for h in hits)
        assert hits==index.search('network listener')
        with pytest.raises(ValueError):index.search('x',gamma=2)
    finally:index.close()

def fixture_graph():
    g=Graph()
    for name in 'abcd':g.add(Entity(name,'r','function',name,None))
    for rid,u,v,kind in [('ab','a','b','calls'),('bc','b','c','calls'),('ca','c','a','calls'),('bd','b','d','inherits')]:
        g.relationships[rid]=Relationship(rid,u,v,u,v,kind,'exact',rid)
    return g

def test_typed_bridge_direction_limits_and_original_witnesses():
    bridge=TypedBridge(fixture_graph(),DEFAULT_FILTER)
    path=bridge.find('a','c');assert [s['relationship_id'] for s in path['steps']]==['ab','bc']
    assert path['outcome']=='found'
    assert bridge.find('a','c',max_hops=1)['outcome']=='hop_limit_reached'
    assert bridge.find('d','b')['outcome']=='no_path_within_scope'
    path=bridge.find('d','b','INHERITANCE_AND_OVERRIDES',undirected=True)
    assert path['steps']==[{'relationship_id':'bd','traversal_reversed':True}]
    assert bridge.find('a','c',max_expansions=1)['outcome']=='search_limit_reached'
    assert bridge.find('a','c',cancelled=lambda:True)['outcome']=='cancelled'
    assert bridge.find('missing','b')['outcome']=='unavailable_anchor'

def test_boundary_fsm_tracks_crossing_state_not_only_nodes():
    bridge=TypedBridge(fixture_graph(),DEFAULT_FILTER)
    assert bridge.find('a','c','BOUNDARY_CROSSING_WITNESSES',mapping={'a':'X','b':'X','c':'Y'})['outcome']=='found'
    assert bridge.find('a','c','BOUNDARY_CROSSING_WITNESSES',mapping={'a':'X','b':'X','c':'Unmapped'})['outcome']!='found'
    with pytest.raises(ValueError):bridge.find('a','c','BOUNDARY_CROSSING_WITNESSES')

def test_calls_never_use_inheritance_as_an_execution_bridge():
    bridge=TypedBridge(fixture_graph(),DEFAULT_FILTER)
    assert bridge.find('a','d')['outcome']!='found'

def test_small_graph_reachability_matches_independent_calls_bfs():
    g=fixture_graph();bridge=TypedBridge(g,DEFAULT_FILTER)
    for source in 'abcd':
        for target in 'abcd':
            q=deque([(source,0)]);visited={(source,0)};found=False
            while q:
                u,depth=q.popleft()
                if u==target and depth>0:found=True;break
                if depth==4:continue
                for r in g.relationships.values():
                    if r.subtype=='calls' and r.source_id==u and (r.target_id,depth+1) not in visited:
                        visited.add((r.target_id,depth+1));q.append((r.target_id,depth+1))
            assert (bridge.find(source,target)['outcome']=='found')==found
