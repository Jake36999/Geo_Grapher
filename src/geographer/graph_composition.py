"""Display-only frames; each graph retains its own partition and query scope."""
from copy import deepcopy
import math
import sqlite3

from .analysis import DEFAULT_FILTER


def display_data(result):
    """Decode only wire identity positions, never identifiers inside source/prose."""
    data=result['data'];ids=data.get('ids',{})
    fields={'id','entity_id','parent_id','node_id','source','target','canonical_source','canonical_target','relationship_id','view_id','projection_id'}
    def decode(value,key=''):
        if isinstance(value,list):return [decode(v,key) for v in value]
        if isinstance(value,dict):return {k:decode(v,k) for k,v in value.items()}
        return ids.get(value,value) if isinstance(value,str) and key in fields else value
    data=decode(data);revisions={r['repo_id']:r['revision'] for r in result.get('revisions',[])}
    for n in data['nodes']:
        if 'is_synthetic' in n:
            n.update(entity_id=None if n['is_synthetic'] else n['id'],depth=None,ast_body_hash=None,wl_3hop_hash=None,doi=None)
            if n.get('source'):n['source']['revision']=n['source'].get('revision_override') or revisions.get(n['repo_id'])
    for r in data['relationships']:r.update(view_id=data['view_id'],witness_cursor=None)
    return data


def hex_slots(count,spacing=7.):
    """Centre, then six hexagonal neighbours, then successive complete rings."""
    result=[(0.,0.,0.)];ring=1
    directions=((0,-1),(-1,0),(-1,1),(0,1),(1,0),(1,-1))
    while len(result)<count:
        q,r=ring,0
        for dq,dr in directions:
            for _ in range(ring):
                result.append((spacing*(q+r/2),0.,spacing*math.sqrt(3)/2*r))
                q+=dq;r+=dr
        ring+=1
    return result[:count]


def compose_frame(router, requests):
    if not isinstance(requests,list) or not 1<=len(requests)<=19:raise ValueError('Choose 1..19 graph frames explicitly')
    if any(not isinstance(r,dict) or not isinstance(r.get('graph_id'),str) for r in requests):raise ValueError('Each frame needs graph_id')
    ids=[r['graph_id'] for r in requests]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate graph frames')
    # Validate all graph identities before doing any expensive work.
    rows={gid:router.catalog.graph(gid) for gid in ids}
    frames=[]
    for request,world_center in zip(requests,hex_slots(len(requests))):
        gid=request['graph_id'];row=rows[gid];radius=2.5;lease=None
        try:
            lease,service=router.acquire(gid);sid=request.get('snapshot_id') or row['snapshot_id']
            with service.lock:
                ctx=service._context(sid);tree=ctx['tree'];graph=ctx['g']
                roots=sorted(e.entity_id for e in graph.entities.values() if e.kind=='repository')
                repository_labels={}
                for root_id in roots:
                    try:repository_labels[root_id]=router.catalog.graph(graph.entities[root_id].repo_id)['label']
                    except ValueError:repository_labels[root_id]=graph.entities[root_id].qualified_name
                focus=request.get('focus_id') or (roots[0] if len(roots)==1 else tree.root)
                breadth=request.get('context_radius',1)
                if type(breadth) is not int or breadth not in (0,1,2):raise ValueError('context_radius must be 0, 1 or 2')
                q=dict(schema_version='1.0',request_id='composed-viewport',snapshot_id=sid,
                    budget=dict(limit_tokens=32768,tokenizer='o200k_base',allow_byte_fallback=False),
                    focus_id=focus,revealed_ids=[],pins=[],context_radius=breadth,filter=deepcopy(request.get('filter',DEFAULT_FILTER)),
                    layout_version='sphere-pack-v1',seed='view-v1',beta=.8,
                    edge_lens=dict(enabled=False,center=[0,0,0],radius=5.,strength=.8),node_budget=120,curve_budget=200,
                    viewport=dict(width_px=1440,height_px=900,device_pixel_ratio=1),
                    camera=dict(eye=[0,0,100],target=[0,0,0],up=[0,1,0],fov_y_degrees=45,near=.01,far=10000))
                if request.get('grouping'):
                    q.update(schema_version='1.1',identity_mode='canonical_map',grouping=request['grouping'],model_digest=request.get('model_digest'))
                q['revealed_ids']=request.get('revealed_ids',[]);q['pins']=request.get('pins',[])
                result=service.query('viewport_frame',q)
            if 'error' in result:raise ValueError(result['error'].get('message','Frame unavailable'))
            data=display_data(result);root=next(s for s in data['spheres'] if s['node_id']==tree.root)
            if root['radius']<=0 or not math.isfinite(root['radius']):raise ValueError('Invalid graph enclosure')
            scale=radius/root['radius'];center=root['center']
            translation=[world_center[i]-scale*center[i] for i in range(3)]
            frames.append(dict(graph_id=gid,label=row['label'],snapshot_id=sid,focus_id=focus,root_id=tree.root,
                transform=dict(scale=scale,translation=translation),frame=data,budget=result.get('budget'),
                root_radius=radius,world_center=list(world_center),repository_labels=repository_labels))
        except (ValueError,KeyError,StopIteration,sqlite3.DatabaseError,OSError) as exc:
            frames.append(dict(graph_id=gid,label=row['label'],error=dict(code='FRAME_UNAVAILABLE',message=str(exc)[:300])))
        finally:
            if lease:router.release(lease)
    return dict(version='graph-composition-v1',composition='display_only',frames=frames,
        address_fields=['graph_id','snapshot_id','local_id'],scope_policy='independent_partitions_no_cross_graph_dependencies')
