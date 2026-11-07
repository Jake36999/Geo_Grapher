"""Bounded mixed-detail viewport frames; geometry never invents graph membership."""
from __future__ import annotations

from collections import defaultdict,Counter
import json

from .analysis import TreeIndex,partition,DEFAULT_FILTER,project,selected_relationships
from .geometry import pack_tree,frame,knots_for,norm,sub,EPS,size_preference
from .model import canonical,digest
from .packing import Unit
from .service import QueryError

ALL_ENTITIES={**DEFAULT_FILTER,'include_tests':True,'include_generated':True,'include_vendor':True,'include_external':True}


def scene_count(tree,revealed):
    return len(revealed)+sum(0<sum(c in revealed for c in tree.children[p])<len(tree.children[p]) for p in revealed)


def effective_expansion(ctx,q):
    g=ctx['g'];tree=ctx['tree'];focus=q['focus_id']
    if focus not in g.entities:raise QueryError('NOT_FOUND','Focus is outside snapshot')
    protected=set(tree.ancestors(focus))
    protected.update(eid for eid in tree.children[tree.root] if g.entities[eid].kind=='repository')
    for eid in q['pins']:
        if eid not in g.entities:raise QueryError('NOT_FOUND','Pin is outside snapshot')
        protected.update(tree.ancestors(eid))
    requested=set(protected)
    for eid in q['revealed_ids']:
        if eid not in g.entities:raise QueryError('NOT_FOUND','Revealed entity is outside snapshot')
        requested.update(tree.ancestors(eid))
    automatic={eid for eid in tree.context(focus,q['context_radius']) if g.entities[eid].sort=='entity' and not g.entities[eid].is_external}
    if g.entities[focus].repo_id!='@workspace':
        automatic={eid for eid in automatic if g.entities[eid].repo_id==g.entities[focus].repo_id or g.entities[eid].kind=='repository'}
    full=requested|automatic
    if scene_count(tree,protected)>q['node_budget']:
        raise QueryError('INVALID_REQUEST','node_budget cannot retain the selected ancestor/pin paths')
    revealed=set(protected)
    active={p:sum(c in revealed for c in tree.children[p]) for p in revealed}
    count=scene_count(tree,revealed)
    def try_add(eid):
        nonlocal count
        missing=[p for p in tree.ancestors(eid) if p not in revealed]
        delta=0;changes={}
        for child in missing:
            parent=tree.parents[child]
            k=len(tree.children[parent]);a=changes.get(parent,active.get(parent,0))
            delta+=1+int(0<a+1<k)-int(0<a<k)
            changes[parent]=a+1
        if count+delta>q['node_budget']:return
        revealed.update(missing);active.update(changes)
        for p in missing:active.setdefault(p,0)
        count+=delta
    for candidates in (requested-protected,automatic-requested):
        for eid in sorted(candidates,key=lambda e:(tree.distance(e,focus),g.entities[e].depth,e)):
            try_add(eid)
    return revealed,protected,max(0,scene_count(tree,full)-scene_count(tree,revealed))


def display_hierarchy(ctx,part,revealed):
    tree=ctx['tree'];children={p:[] for p in revealed}
    for p in revealed:
        if tree.parents[p] in revealed:children[tree.parents[p]].append(p)
    for rep in part.groups:
        if part.kinds[rep]!='entity':
            parent=part.shells[rep];children.setdefault(parent,[]).append(rep);children[rep]=[]
    for values in children.values():values.sort()
    counts={p:len(tree.leaves(p)) for p in revealed}
    counts.update({rep:len(members) for rep,members in part.groups.items()})
    # Content is a display sizing signal, not new dependency membership/degree.
    # Text nodes have no subject atoms, yet may represent hundreds of lines.
    for p in revealed:
        e=ctx['g'].entities[p]
        if e.kind in {'document','fragment'}:
            counts[p]=max(counts.get(p,1),1+max(0,(e.end_line or 0)-(e.start_line or 0))//12)
    aggregates={rep for rep,members in part.groups.items() if len(members)>1}
    return children,counts,aggregates


def display_radii(ctx,counts):
    """File-relative display units. These never become graph weights or degree.

    A small file starts at radius 1; its symbols are fractions of that unit.
    Actual enclosing radii still grow as necessary to contain packed children.
    """
    import math
    result={}
    for eid,count in counts.items():
        e=ctx['g'].entities.get(eid)
        if e is None:radius=.35*size_preference(count)
        else:
            lines=max(1,(e.end_line or 0)-(e.start_line or 0)+1)
            if e.is_external or e.kind=='external_symbol':radius=.20
            elif e.kind=='parameter':radius=.12
            elif e.kind in {'attribute','constant'}:radius=.18
            elif e.kind=='scope_atom':radius=min(.55,.16+.09*math.log1p(lines/12))
            elif e.kind in {'function','method'}:radius=min(.8,.28+.16*math.log1p(lines/8))
            elif e.kind=='class':radius=min(1.4,.6+.14*math.log1p(lines/20))
            elif e.kind=='fragment':radius=min(1.1,.3+.18*math.log1p(lines/24))
            elif e.kind in {'file','document'}:radius=min(3.2,1+.22*math.log1p(lines/50)+.10*math.log1p(min(count,10000)))
            else:radius=size_preference(count)
        result[eid]=radius
    return result


def control_polygon(tree,part,centres,a,b):
    def chain(rep):
        return tree.ancestors(rep) if rep in tree.parents else tree.ancestors(part.shells[rep])+[rep]
    left,right=chain(a),chain(b)
    common=0
    while common<min(len(left),len(right)) and left[common]==right[common]:common+=1
    lca=left[common-1]
    ids=list(reversed(left[common-1:]))+right[common:]
    original_count=len(ids)
    pairs=[]
    for eid in ids:
        point=centres[eid]
        if not pairs or norm(sub(pairs[-1][1],point))>1e-12:pairs.append((eid,point))
    if original_count>3:
        pairs=[pair for i,pair in enumerate(pairs) if pair[0]!=lca or i==0 or i==len(pairs)-1]
    points=[p for _,p in pairs]
    if len(points)<2:points=[centres[a],centres[b]]
    return points


def build_frame(service,q,ctx):
    g=ctx['g'];tree=ctx['tree'];sid=q['snapshot_id']
    if q.get('model_digest') and q['model_digest'] not in service.rules:raise QueryError('NOT_FOUND','Selected rules model unavailable')
    if q.get('grouping',{}).get('mode')=='conceptual' and q.get('model_digest') and q['grouping']['model_digest']!=q['model_digest']:raise QueryError('INVALID_REQUEST','Conflicting selected and conceptual model digests')
    revealed,protected,lod_omitted=effective_expansion(ctx,q)
    grouping=q.get('grouping',{'mode':'mixed','revealed_ids':sorted(revealed)})
    if grouping['mode']=='mixed':grouping={'mode':'mixed','revealed_ids':sorted(revealed)}
    if grouping['mode']=='conceptual':
        baseline=service._conceptual_partition({**q,'filter':ALL_ENTITIES},ctx)
        part=service._conceptual_partition(q,ctx)
    else:
        baseline=partition(g,sid,grouping,ALL_ENTITIES,tree=tree)
        part=partition(g,sid,grouping,q['filter'],tree=tree)
    if grouping['mode']!='mixed':
        # T_display is a view-local tree. Canonical ownership remains unchanged.
        # Bound geometry independently of the full, persisted partition.
        admitted=set(protected)
        def anchor(rep):return rep if rep in g.entities else baseline.shells[rep]
        mapping=baseline.representatives;incident=Counter()
        for rel in selected_relationships(g,{**ALL_ENTITIES,'resolution_statuses':['exact','candidate','unresolved']}):
            for rep in {mapping.get(rel.source_id),mapping.get(rel.target_id)}:
                if rep is not None:incident[rep]+=1
        relevant={mapping[a] for eid in [q['focus_id'],*q['pins']] for a in tree.leaves(eid) if a in mapping}
        focused_repo=g.entities[q['focus_id']].repo_id
        explicit_repos={g.entities[eid].repo_id for eid in [*q['pins'],*q['revealed_ids']] if eid in g.entities and g.entities[eid].kind not in {'repository','workspace'}}
        scope={focused_repo,*explicit_repos}
        def in_scope(rep):
            # Synthetic (conceptual/unmapped) groups hang off the workspace root;
            # judge them by the repositories of their member atoms instead.
            if rep not in g.entities:return any(g.entities[a].repo_id in scope for a in baseline.groups[rep] if a in g.entities)
            return g.entities[anchor(rep)].repo_id in scope
        # Unindexed external placeholders must not displace the focused code's
        # groups merely because their containment path is shallower. This order
        # uses a fixed static universe, so toggling query filters preserves layout.
        for rep in sorted(baseline.groups,key=lambda r:(r not in relevant,g.entities[r].is_external if r in g.entities else False,-incident[r],tree.distance(anchor(r),q['focus_id']),r)):
            if focused_repo!='@workspace' and not in_scope(rep) and rep not in protected:continue
            branch=set(tree.ancestors(anchor(rep)))|{rep}
            if len(admitted|branch)<=q['node_budget']:admitted.update(branch)
        lod_omitted=len(set(baseline.groups)-admitted)
        revealed={eid for eid in admitted if eid in g.entities}
    else:admitted=None
    if not part.groups:raise QueryError('INVALID_REQUEST','Filters exclude all entities')
    vid=service._persist_partition(sid,ctx,part,q['filter'],'viewport-partition-v1')
    partition_digest=digest({rep:sorted(members) for rep,members in sorted(part.groups.items())})
    geometry_key='layout:'+digest(sid,grouping,q['seed'],'content-orbits-v3',sorted(admitted) if admitted is not None else None)
    # Cache is per expansion state, not filter/camera/beta. Filters therefore fade
    # existing groups without changing all coordinates or running global physics.
    layout=ctx.setdefault('layouts',{}).get(geometry_key)
    if layout is None:
        hierarchy,counts,aggregate=display_hierarchy(ctx,baseline,revealed)
        if admitted is not None:
            hierarchy={p:[c for c in children if c in admitted] for p,children in hierarchy.items() if p in admitted}
            counts={p:n for p,n in counts.items() if p in admitted}
            aggregate&=admitted
        try:layout=pack_tree(hierarchy,tree.root,counts,q['seed'],aggregate,display_radii(ctx,counts))
        except ValueError as exc:raise QueryError('LAYOUT_FAILED',str(exc)) from exc
        ctx['layouts'][geometry_key]=layout
        while len(ctx['layouts'])>16:ctx['layouts'].pop(next(iter(ctx['layouts'])))
        seed=q['seed']+':'+digest(grouping,'content-orbits-v3')
        with service.store.connection:
            for eid,centre in layout.centres.items():
                if eid in g.entities:
                    service.store.connection.execute('INSERT OR IGNORE INTO layouts VALUES(?,?,?,?,?,?,?,?)',
                        (sid,'sphere-pack-v1',seed,eid,*centre,layout.radii[eid]))
    visible=set(part.groups)
    for rep in part.groups:
        anchor=rep if rep in g.entities else part.shells[rep]
        visible.update(tree.ancestors(anchor))
    visible.update(protected)
    visible&=set(layout.centres)
    if q['focus_id'] not in visible:raise QueryError('INVALID_REQUEST','Filters exclude the focus')
    nodes={eid:service._node(ctx,eid,part=part,focus=q['focus_id']) for eid in visible}
    spheres={eid:dict(node_id=eid,center=list(layout.centres[eid]),radius=layout.radii[eid],
                      role='representative' if eid in part.groups else 'context_shell') for eid in visible}
    data=service._payload(sid,ctx,layout_version='sphere-pack-v1',partition_digest=partition_digest,spheres=[],curves=[],
        packing=dict(tolerance=EPS,fallback_parent_ids=[eid for eid in layout.fallback if eid in visible],max_violation=layout.max_violation),
        scene_completeness=dict(omitted_spheres=lod_omitted,omitted_curves=0))
    data['view_id']=vid
    required=set(protected)&visible
    for eid in sorted(required):data['nodes'].append(nodes[eid]);data['spheres'].append(spheres[eid])
    units=[]
    for eid in sorted(visible-required):
        tier=2 if q['schema_version']=='1.1' else 1 if eid in part.groups else 2
        units.append(Unit('sphere:'+eid,tier,80,dict(nodes=[nodes[eid]],spheres=[spheres[eid]])))
    rows=[dict(row) for row in service.store.connection.execute('SELECT * FROM quotient_projections WHERE snapshot_id=? AND view_id=? ORDER BY projection_id',(sid,vid))]
    hidden_relationships=sum(r['source_rep_id'] not in visible or r['target_rep_id'] not in visible for r in rows)
    rows=[r for r in rows if r['source_rep_id'] in visible and r['target_rep_id'] in visible]
    pairs=defaultdict(list)
    for row in rows:pairs[tuple(sorted((row['source_rep_id'],row['target_rep_id'])))].append(row)
    curve_candidates=[]
    for (a,b),group in sorted(pairs.items()):
        group.sort(key=lambda r:(r['source_rep_id']!=a,r['family'],r['subtype'],r['resolution_status'],r['projection_id']))
        points=control_polygon(tree,part,layout.centres,a,b) if a!=b else [layout.centres[a],layout.centres[a]]
        degree,knots=knots_for(len(points));_,normal,binormal=frame(layout.centres[a],layout.centres[b],a+b)
        for index,row in enumerate(group):
            summary=service._summary(sid,vid,row)
            ids={row['source_rep_id'],row['target_rep_id']}
            if q['schema_version']=='1.1':
                for rep in list(ids):
                    anchor=rep if rep in g.entities else part.shells[rep]
                    ids.update(set(tree.ancestors(anchor))&visible)
            records=dict(nodes=[nodes[eid] for eid in sorted(ids)],spheres=[spheres[eid] for eid in sorted(ids)],relationships=[summary])
            # Internal roll-ups remain inspector/matrix items, not one artificial
            # recursion loop per hidden call. Draw only actual single-subject recursion.
            recursive=a==b and service.store.connection.execute('''SELECT 1 FROM quotient_witness_map w JOIN relationships r
                ON r.snapshot_id=w.snapshot_id AND r.relationship_id=w.relationship_id
                WHERE w.snapshot_id=? AND w.view_id=? AND w.projection_id=? AND r.source_subject_id<>r.target_subject_id LIMIT 1''',
                (sid,vid,row['projection_id'])).fetchone() is None
            if a!=b or recursive:
                curve=dict(relationship_id=row['projection_id'],canonical_source=a,canonical_target=b,reversed=row['source_rep_id']!=a,
                    control_points=[list(p) for p in points],degree=degree,knots=knots,normal=list(normal),binormal=list(binormal),
                    lane_index=index,lane_count=len(group),lane_spacing=.08,sample_count=48)
                curve_candidates.append((row,records,curve))
            else:units.append(Unit('internal:'+row['projection_id'],2,100,records))
    curve_candidates.sort(key=lambda item:(tree.distance(q['focus_id'],part.shells.get(item[0]['source_rep_id']) or tree.root),item[0]['projection_id']))
    for index,(row,records,curve) in enumerate(curve_candidates):
        if index<q['curve_budget']:records['curves']=[curve]
        units.append(Unit('curve:'+row['projection_id'],1,200,records))
    data['scene_completeness']['omitted_curves']=hidden_relationships+max(0,len(curve_candidates)-q['curve_budget'])
    if lod_omitted:data['coverage']['limitations'].append('Some expanded branches were collapsed into exact residual groups to respect the scene budget' if grouping['mode']=='mixed' else 'Some complete representatives and their relationships are outside the scene budget; the stored partition remains complete')
    plan=service._plan('viewport_frame',q,data,units,vid,'viewport')
    plan.totals.update(spheres=len(spheres),curves=min(len(curve_candidates),q['curve_budget']))
    return plan
