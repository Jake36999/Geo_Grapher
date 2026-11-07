"""sphere-pack-v1 and endpoint-exact, separated clamped B-spline tracks."""
from __future__ import annotations

from dataclasses import dataclass
import math

from .model import digest

EPS=1e-4
PADDING=.35
GAP=.2
GOLDEN=math.pi*(3-math.sqrt(5))

def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def mul(a,s):return tuple(x*s for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def norm(a):return math.sqrt(dot(a,a))
def unit(a):
    length=norm(a)
    return mul(a,1/length) if length>1e-12 else (1.,0.,0.)
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def size_preference(count):return 1+.35*math.log1p(min(count,10000))


def frame(a,b,seed=''):
    delta=sub(b,a)
    if norm(delta)<1e-12:
        h=digest('frame-v1',seed);delta=tuple(int(h[i:i+8],16)/2**31-1 for i in (0,8,16))
    tangent=unit(delta)
    axes=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
    axis=min(enumerate(axes),key=lambda pair:(abs(dot(tangent,pair[1])),pair[0]))[1]
    normal=unit(cross(tangent,axis));binormal=cross(tangent,normal)
    return tangent,normal,binormal


def violations(centres,radii,parent_radius):
    maximum=max((norm(c)+r+PADDING-parent_radius for c,r in zip(centres,radii)),default=0.)
    for i in range(len(radii)):
        for j in range(i+1,len(radii)):
            a,b=centres[i],centres[j];dx=a[0]-b[0];dy=a[1]-b[1];dz=a[2]-b[2]
            squared=dx*dx+dy*dy+dz*dz;required=radii[i]+radii[j]+GAP
            if squared<required*required:maximum=max(maximum,required-math.sqrt(squared))
    return max(0.,maximum)


def line_fallback(radii,preference=1.,seed=''):
    """Feasible x ordering plus user-requested tiny transverse helical stagger."""
    if not radii:return [],preference
    width=2*sum(radii)+(len(radii)-1)*GAP
    amplitude=min(min(radii),1.)*.001 if len(radii)>1 else 0.
    phase=2*math.pi*int(digest(seed,'line-stagger')[:16],16)/2**64
    centres=[];before=0.
    for i,radius in enumerate(radii):
        x=-width/2+2*before+i*GAP+radius
        centres.append((x,amplitude*math.cos(phase+i*GOLDEN),amplitude*math.sin(phase+i*GOLDEN)))
        before+=radius
    # Stagger cannot reduce pairwise x separation; recompute exact containment.
    parent=max(preference,PADDING+max(norm(c)+r for c,r in zip(centres,radii)))
    return centres,parent


def compact_fallback(ids,radii,preference=1.,seed=''):
    """Radius-aware spherical packing; no rows, shelves or lattice coordinates.

    For each direction, intersect its ray with previously placed spheres enlarged
    by the incoming radius and gap. The first free radial interval is feasible.
    Batching bounds the local solver size at high fan-out; batches are geometry
    only, never synthetic entities or semantic groups.
    """
    if not radii:return [],preference
    if len(ids)!=len(radii) or any(not math.isfinite(r) or r<=0 for r in radii):raise ValueError('Invalid child radii')
    K=len(ids);order=sorted(range(K),key=lambda i:(-radii[i],ids[i]));centres=[None]*K
    if K>512:
        batches=[order[i:i+128] for i in range(0,K,128)];local=[];bounds=[]
        for i,batch in enumerate(batches):
            points,radius=compact_fallback([ids[j] for j in batch],[radii[j] for j in batch],0.,seed+':batch:'+str(i))
            local.append(points);bounds.append(radius)
        offsets,_=compact_fallback([ids[b[0]] for b in batches],bounds,0.,seed+':batches')
        for batch,points,offset in zip(batches,local,offsets):
            for j,p in zip(batch,points):centres[j]=add(offset,p)
    else:
        stride=max(1,int(K*.6180339887498949))
        while math.gcd(stride,K)>1:stride+=1
        phase=2*math.pi*int(digest(seed,ids,'spherical-orbits-v3')[:16],16)/2**64
        placed=[]
        for index,i in enumerate(order):
            k=index*stride%K;z=1-2*(k+.5)/K;theta=phase+k*GOLDEN
            direction=(math.sqrt(max(0.,1-z*z))*math.cos(theta),math.sqrt(max(0.,1-z*z))*math.sin(theta),z)
            intervals=[]
            for j in placed:
                c=centres[j];along=dot(direction,c);perpendicular=max(0.,dot(c,c)-along*along)
                required=radii[i]+radii[j]+GAP+EPS*.1
                if perpendicular<required*required:
                    half=math.sqrt(required*required-perpendicular)
                    if along+half>=0:intervals.append((along-half,along+half))
            distance=0.
            for low,high in sorted(intervals):
                if low>distance:break
                if high>=distance:distance=high+EPS*.1
            centres[i]=mul(direction,distance);placed.append(i)
    low=[min(c[j]-r for c,r in zip(centres,radii)) for j in range(3)]
    high=[max(c[j]+r for c,r in zip(centres,radii)) for j in range(3)]
    middle=tuple((a+b)/2 for a,b in zip(low,high))
    centres=[sub(c,middle) for c in centres]
    return centres,max(preference,PADDING+max(norm(c)+r for c,r in zip(centres,radii)))


def pack_siblings(ids,radii,count,seed,*,attempts=8,sweeps=256,preferred_radius=None):
    if len(ids)!=len(radii) or any(not math.isfinite(r) or r<=0 for r in radii):raise ValueError('Invalid child radii')
    preference=size_preference(count) if preferred_radius is None else preferred_radius
    if not radii:return [],1.,False,0.
    radius=max(preference,PADDING+max(radii),PADDING+(sum((r+GAP/2)**3 for r in radii)/.35)**(1/3))
    phase=2*math.pi*int(digest(seed,ids)[:16],16)/2**64
    centres=[];K=len(ids)
    for i,r in enumerate(radii):
        z=1-2*(i+.5)/K;theta=phase+i*GOLDEN
        direction=(math.sqrt(1-z*z)*math.cos(theta),math.sqrt(1-z*z)*math.sin(theta),z)
        centres.append(mul(direction,.8*max(0.,radius-PADDING-r)) if K>1 else (0.,0.,0.))
    # Bound worst-case quadratic work. High fan-out is still feasible using the
    # deterministic fallback; normal UI scenes aggregate those children first.
    budget=min(attempts*sweeps,max(0,1000000//max(1,K*(K-1)//2)))
    for attempt in range(attempts):
        for _ in range(min(sweeps,budget)):
            budget-=1
            for i in range(K):
                for j in range(i+1,K):
                    a,b=centres[i],centres[j];dx=b[0]-a[0];dy=b[1]-a[1];dz=b[2]-a[2]
                    squared=dx*dx+dy*dy+dz*dz;required=radii[i]+radii[j]+GAP
                    if squared<required*required:
                        distance=math.sqrt(squared);shift=.5*(required-distance)
                        if distance>1e-12:
                            inv=1/distance;ox=(dx*inv)*shift;oy=(dy*inv)*shift;oz=(dz*inv)*shift
                        else:ox,oy,oz=mul(frame((0,0,0),(0,0,0),ids[i]+ids[j])[0],shift)
                        centres[i]=(a[0]-ox,a[1]-oy,a[2]-oz);centres[j]=(b[0]+ox,b[1]+oy,b[2]+oz)
            for i,r in enumerate(radii):
                allowed=radius-PADDING-r;distance=norm(centres[i])
                if distance>allowed:centres[i]=mul(centres[i],allowed/distance)
            error=violations(centres,radii,radius)
            if error<=EPS:return centres,radius,False,error
            if budget<=0:break
        if budget<=0:break
        radius*=1.15;centres=[mul(c,1.15) for c in centres]
    centres,radius=compact_fallback(ids,radii,preference,seed)
    error=violations(centres,radii,radius)
    if error>EPS or not math.isfinite(radius) or radius>1e12:raise ValueError('No valid bounded layout')
    return centres,radius,True,error


@dataclass
class Packing:
    centres:dict
    radii:dict
    fallback:list
    max_violation:float


def pack_tree(children,root,counts,seed,aggregate=(),preferred_radii=None):
    """Bottom-up radius solve followed by top-down rigid subtree translation."""
    order=[];stack=[root]
    while stack:
        p=stack.pop();order.append(p);stack.extend(reversed(sorted(children.get(p,[]))))
    radii={};local={};fallback=[];maximum=0.;aggregate=set(aggregate);preferred_radii=preferred_radii or {}
    if any(not math.isfinite(r) or r<=0 for r in preferred_radii.values()):raise ValueError('Invalid preferred radius')
    for p in reversed(order):
        cs=sorted(children.get(p,[]))
        if not cs:
            radii[p]=preferred_radii.get(p,size_preference(counts.get(p,1)) if p in aggregate or counts.get(p,1)>1 else 1.)
            continue
        offsets,radius,used,error=pack_siblings(cs,[radii[c] for c in cs],counts.get(p,1),seed+':'+p,preferred_radius=preferred_radii.get(p))
        radii[p]=radius;local.update(zip(cs,offsets));maximum=max(maximum,error)
        if used:fallback.append(p)
    centres={root:(0.,0.,0.)}
    for p in order:
        for c in sorted(children.get(p,[])):centres[c]=add(centres[p],local[c])
    if any(abs(x)>1e12 for c in centres.values() for x in c):raise ValueError('Layout exceeds finite coordinate bounds')
    return Packing(centres,radii,sorted(fallback),maximum)


def knots_for(N):
    if N<2:raise ValueError('Spline requires at least two points')
    degree=min(3,N-1);M=N-degree-1
    return degree,[0.]*(degree+1)+[j/(N-degree) for j in range(1,M+1)]+[1.]*(degree+1)


def straighten(points,beta,lens=None):
    if not 0<=beta<=1:raise ValueError('Bundling strength must be 0..1')
    N=len(points)
    if N<2:raise ValueError('Degenerate control polygon')
    result=[]
    for i,p in enumerate(points):
        local=beta
        if lens and lens['enabled']:
            q=min(1.,max(0.,norm(sub(p,lens['center']))/lens['radius']))
            weight=1-3*q*q+2*q*q*q
            local*=1-lens['strength']*weight
        chord=add(points[0],mul(sub(points[-1],points[0]),i/(N-1)))
        result.append(add(mul(p,local),mul(chord,1-local)))
    return result


def greville_project(points,degree,knots):
    tangent=unit(sub(points[-1],points[0]));delta=sub(points[-1],points[0])
    return [add(p,mul(tangent,dot(sub(add(points[0],mul(delta,sum(knots[i+1:i+degree+1])/degree)),p),tangent)))
            for i,p in enumerate(points)]


def spline_point(points,degree,knots,t):
    if t<=0:return tuple(points[0])
    if t>=1:return tuple(points[-1])
    N=len(points);span=next((i for i in range(degree,N) if knots[i]<=t<knots[i+1]),N-1)
    d=[tuple(points[span-degree+j]) for j in range(degree+1)]
    for r in range(1,degree+1):
        for j in range(degree,r-1,-1):
            k=span-degree+j;denominator=knots[k+degree-r+1]-knots[k]
            alpha=(t-knots[k])/denominator if denominator else 0.
            d[j]=add(mul(d[j-1],1-alpha),mul(d[j],alpha))
    return d[degree]


def lane_samples(points,beta,normal,lane_index,lane_count,spacing,*,lens=None,segments=48,reversed=False):
    degree,knots=knots_for(len(points));control=greville_project(straighten(points,beta,lens),degree,knots)
    out=[]
    for i in range(segments+1):
        t=i/segments;point=spline_point(control,degree,knots,t);delta=spacing
        if lens and lens['enabled']:
            q=min(1.,norm(sub(point,lens['center']))/lens['radius']);delta*=1+lens['strength']*(1-3*q*q+2*q*q*q)
        out.append(add(point,mul(normal,math.sin(math.pi*t)*delta*(lane_index-(lane_count-1)/2))))
    return list(out.__reversed__()) if reversed else out
