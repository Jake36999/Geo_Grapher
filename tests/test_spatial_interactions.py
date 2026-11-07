"""Geometry remains finite, compact and independent of graph semantics."""
import math
from geographer.geometry import compact_fallback,violations,EPS,norm,sub,cross,size_preference
from geographer.graph_composition import hex_slots
from geographer.analysis import TreeIndex,partition,subject_graph
from geographer.model import Entity,Graph
from geographer.viewport import display_hierarchy,display_radii


def test_high_fanout_fallback_uses_three_dimensions_instead_of_a_chain():
    radii=[1.]*362;ids=[str(i) for i in range(362)]
    centres,radius=compact_fallback(ids,radii)
    assert violations(centres,radii,radius)<=EPS
    assert radius<30 # The old line was over 390 units in radius.
    spans=[max(c[j] for c in centres)-min(c[j] for c in centres) for j in range(3)]
    assert max(spans)/min(spans)<3
    # A compact box is still wrong: points must not accumulate on its six faces.
    low=[min(c[j] for c in centres) for j in range(3)]
    high=[max(c[j] for c in centres) for j in range(3)]
    near_faces=sum(any(min(c[j]-low[j],high[j]-c[j])<.02*spans[j] for j in range(3)) for c in centres)
    assert near_faces/len(centres)<.25
    assert len({round(c[0],7) for c in centres})>.9*len(centres)
    assert compact_fallback(ids,radii)==(centres,radius)
    small,_=compact_fallback(['a','b','c'],[1.,1.,1.])
    assert norm(cross(sub(small[1],small[0]),sub(small[2],small[0])))>1e-8


def test_variable_radius_compact_fallback_preserves_padding_and_separation():
    radii=[.12,8.,.6,1.,3.]*30
    centres,radius=compact_fallback([str(i) for i in range(len(radii))],radii)
    assert violations(centres,radii,radius)<=EPS
    assert math.isfinite(radius)


def test_hexagonal_initial_centre_and_five_neighbours_then_outer_ring():
    slots=hex_slots(19)
    assert slots[0]==(0.,0.,0.)
    assert all(abs(norm(p)-7)<1e-10 for p in slots[1:7])
    assert len(set(slots))==19
    assert all(norm(sub(a,b))>=7-1e-9 for i,a in enumerate(slots) for b in slots[i+1:])
    assert hex_slots(6)==slots[:6]


def test_document_content_changes_display_weight_without_creating_dependency_atoms():
    graph=Graph()
    graph.add(Entity('root','@workspace','workspace','Workspace',None))
    graph.add(Entity('repo','r','repository','Repository','root'))
    graph.add(Entity('short','r','fragment','Short','repo',sort='text',start_line=1,end_line=12))
    graph.add(Entity('long','r','fragment','Long','repo',sort='text',start_line=1,end_line=600))
    graph.add(Entity('code','r','function','function','repo',start_line=1,end_line=2))
    graph.augment();tree=TreeIndex(graph)
    part=partition(graph,'snapshot',{'mode':'atomic'})
    children,counts,aggregates=display_hierarchy({'g':graph,'tree':tree},part,set(graph.entities))
    assert size_preference(counts['long'])>size_preference(counts['short'])
    assert len(graph.relationships)==0
    assert 'long' not in subject_graph(graph)[0]
    from geographer.geometry import pack_tree
    layout=pack_tree(children,tree.root,counts,'content-test',aggregates)
    assert layout.radii['long']>layout.radii['short']


def test_file_relative_radii_and_automatic_enclosure_growth():
    from geographer.geometry import pack_tree,PADDING
    graph=Graph()
    graph.add(Entity('root','@workspace','workspace','Workspace',None))
    graph.add(Entity('repo','r','repository','Repository','root'))
    graph.add(Entity('file','r','file','large.py','repo',start_line=1,end_line=1000))
    for i in range(80):graph.add(Entity('f'+str(i),'r','function','f'+str(i),'file',start_line=1,end_line=10))
    graph.add(Entity('external','r','external_symbol','unindexed','repo',sort='external',is_external=1))
    graph.augment();tree=TreeIndex(graph);part=partition(graph,'snapshot',{'mode':'atomic'})
    children,counts,aggregate=display_hierarchy({'g':graph,'tree':tree},part,set(graph.entities))
    preferred=display_radii({'g':graph},counts)
    assert preferred['external']<preferred['f0']<preferred['file']
    layout=pack_tree(children,tree.root,counts,'file-size-test',aggregate,preferred)
    assert layout.radii['file']>preferred['file']
    for parent,items in children.items():
        for child in items:
            assert norm(sub(layout.centres[child],layout.centres[parent]))+layout.radii[child]<=layout.radii[parent]-PADDING+EPS
    assert not graph.relationships # Sizing does not create dependency facts.


def test_large_spherical_fallback_batches_still_separate_all_original_nodes():
    radii=[.15,.3,1.1,.6]*160
    centres,radius=compact_fallback([str(i) for i in range(len(radii))],radii,seed='large')
    assert len(centres)==len(radii)
    assert violations(centres,radii,radius)<=EPS
