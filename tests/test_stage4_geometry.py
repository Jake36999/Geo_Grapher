import copy
import math
import random

import pytest

from geographer.geometry import (pack_siblings,line_fallback,violations,knots_for,straighten,
    greville_project,spline_point,lane_samples,frame,dot,sub,norm,cross,EPS)
from geographer.analysis import DEFAULT_FILTER
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.service import QueryService
from geographer.tokens import TokenCounter


def test_packing_constraints_and_requested_noncollinear_fallback():
    rng=random.Random(42)
    for n in [1,2,3,4,12,35,129]:
        radii=[rng.uniform(.3,4) for _ in range(n)]
        positions,radius,used,error=pack_siblings([str(i) for i in range(n)],radii,200,'test')
        assert error<=EPS and violations(positions,radii,radius)<=EPS
        fallback,R=line_fallback(radii,seed='test')
        assert violations(fallback,radii,R)<=EPS
        if n>=3:assert norm(cross(sub(fallback[1],fallback[0]),sub(fallback[2],fallback[0])))>1e-9
    assert pack_siblings(['a','b','c'],[1,1,1],3,'seed',attempts=0)[2] is True


def test_clamped_greville_spline_endpoints_monotonicity_lanes_and_lens():
    points=[(0.,0.,0.),(20.,8.,1.),(-10.,-4.,2.),(5.,0.,0.)]
    p,knots=knots_for(len(points));_,normal,binormal=frame(points[0],points[-1])
    lens={'enabled':True,'center':[2.5,0,0],'radius':8.,'strength':.9}
    projected=greville_project(straighten(points,.8,lens),p,knots)
    assert spline_point(projected,p,knots,0)==points[0]
    assert spline_point(projected,p,knots,1)==points[-1]
    samples=[spline_point(projected,p,knots,i/100) for i in range(101)]
    assert all(abs(point[0]-5*i/100)<1e-10 for i,point in enumerate(samples))
    a=lane_samples(points,.8,normal,0,2,.08,lens=lens,segments=100)
    b=lane_samples(points,.8,normal,1,2,.08,lens=lens,segments=100)
    assert all(norm(sub(x,y))>0 for x,y in zip(a[1:-1],b[1:-1]))
    assert lane_samples(points,.8,normal,0,2,.08,segments=100,reversed=True)==list(reversed(lane_samples(points,.8,normal,0,2,.08,segments=100)))


def viewport_request(sid,focus,budget=32768):
    return dict(schema_version='1.0',request_id='viewport-test',snapshot_id=sid,budget=dict(limit_tokens=budget,tokenizer='o200k_base',allow_byte_fallback=False),
        focus_id=focus,revealed_ids=[],pins=[],context_radius=2,filter=copy.deepcopy(DEFAULT_FILTER),layout_version='sphere-pack-v1',seed='view-v1',beta=.8,
        edge_lens=dict(enabled=False,center=[0,0,0],radius=5.,strength=.8),node_budget=100,curve_budget=200,
        viewport=dict(width_px=1440,height_px=900,device_pixel_ratio=1),camera=dict(eye=[0,0,100],target=[0,0,0],up=[0,1,0],fov_y_degrees=45,near=.01,far=10000))


def test_arbitrary_depth_focus_retains_every_ancestor_and_three_point_lca():
    from geographer.viewport import control_polygon
    from geographer.analysis import partition,TreeIndex
    source=''.join('    '*i+f'class C{i}:\n' for i in range(16))+'    '*16+'def method(self):\n'+'    '*17+'def inner(): return 1\n'+'    '*17+'return inner()\n'
    with SnapshotStore() as store:
        sid=ingest(store,[Repository('r','rev',{'deep.py':source.encode(),'other.py':b'pass\n'})],stage=3)['snapshot_id']
        service=QueryService(store);ctx=service._context(sid);g=ctx['g'];tree=ctx['tree']
        focus=next(e.entity_id for e in g.entities.values() if e.qualified_name.endswith('.inner'))
        for focus_id in [tree.root,next(e.entity_id for e in g.entities.values() if e.rel_path=='deep.py' and e.kind=='file'),focus]:
            r=service.query('viewport_frame',viewport_request(sid,focus_id))
            assert 'error' not in r,r
            assert set(tree.ancestors(focus_id))<={n['id'] for n in r['data']['nodes']}
            assert set(tree.ancestors(focus_id))<={n['node_id'] for n in r['data']['spheres']}
        # Explicit N0=3 path: sibling endpoints retain their parent control point.
        repo=next(e.entity_id for e in g.entities.values() if e.kind=='repository')
        files=[e.entity_id for e in g.entities.values() if e.kind=='file']
        part=partition(g,sid,{'mode':'kind','kind':'file'})
        centres={tree.root:(0,0,0),repo:(1,0,0),files[0]:(2,1,0),files[1]:(2,-1,0)}
        assert control_polygon(tree,part,centres,*files)==[centres[files[0]],centres[repo],centres[files[1]]]


@pytest.mark.parametrize('version',['1.0','1.1'])
def test_viewport_each_page_has_nodes_spheres_and_filter_stability(version):
    source='\n'.join(f'def f{i}(): return f{i+1}()' for i in range(12))+'\ndef f12(): return 1\n'
    with SnapshotStore() as store:
        report=ingest(store,[Repository('r','rev',{'a.py':source.encode(),'tests/test_a.py':b'def check(): pass\n'})],stage=3)
        sid=report['snapshot_id'];svc=QueryService(store,secret=b'x'*32);ctx=svc._context(sid)
        focus=next(e.entity_id for e in ctx['g'].entities.values() if e.kind=='repository')
        req=viewport_request(sid,focus,8192)
        req['schema_version']=version
        if version=='1.1':req.update(grouping={'mode':'mixed','revealed_ids':[]},identity_mode='canonical_map')
        result=svc.query('viewport_frame',req)
        assert 'error' not in result,result
        first=result
        seen=set();pages=0
        while True:
            (svc.wire11 if version=='1.1' else svc.wire).validate('viewport_frame','response',result)
            assert TokenCounter().count(result)<=8192
            nodes={n['id'] for n in result['data']['nodes']};spheres={s['node_id'] for s in result['data']['spheres']}
            assert spheres<=nodes
            rels={r['id']:r for r in result['data']['relationships']}
            for curve in result['data']['curves']:
                relation=rels[curve['relationship_id']]
                assert relation['source'] in spheres and relation['target'] in spheres
            current={c['relationship_id'] for c in result['data']['curves']}
            assert not current&seen;seen|=current;pages+=1
            cursor=result['data']['completeness']['next_cursor']
            if cursor is None:break
            assert pages<20
            result=svc.query('viewport_frame',req,cursor_override=cursor)
            assert 'error' not in result,result
        assert len(seen)==12
        changed=copy.deepcopy(req);changed['filter']['include_tests']=True;changed['budget']['limit_tokens']=32768
        other=svc.query('viewport_frame',changed);assert 'error' not in other,other
        def centres(response):
            data=response['data'];ids=data.get('ids',{})
            return {ids.get(s['node_id'],s['node_id']):s['center'] for s in data['spheres']}
        before=centres(first)
        after=centres(other)
        assert all(before[k]==after[k] for k in before.keys()&after.keys())
        assert not store.validate(sid)
