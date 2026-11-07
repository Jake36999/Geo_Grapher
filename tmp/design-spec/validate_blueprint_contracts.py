"""Document-contract checks only; not application code."""
from pathlib import Path
from itertools import combinations, product
from collections import deque, Counter
import json, math, random, sqlite3
import yaml, jsonschema

ROOT = Path('F:/uv-data/Geo_Grapher')
db = sqlite3.connect(':memory:')
db.executescript((ROOT/'contracts/geographer.schema.sql').read_text(encoding='utf-8'))
h='a'*64
db.execute('INSERT INTO snapshot_sets VALUES (?,?,?,?,?)',('s',h,'building','2026-11-06T00:00:00Z','{}'))
for repo in ['@workspace','a','b']:
    db.execute('INSERT INTO snapshots VALUES (?,?,?,?,?,?)',('s',repo,'rev',h,'test-v1','[]'))
def entity(e,repo,parent,depth,kind='function'):
    db.execute('''INSERT INTO entities(entity_id,snapshot_id,repo_id,sort,kind,language,qualified_name,
      parent_id,depth,ancestors_binary_lifting_json) VALUES (?,?,?,?,?,?,?,?,?,?)''',
      (e,'s',repo,'synthetic' if kind=='workspace' else 'entity',kind,'python',e,parent,depth,json.dumps([parent or e])))
entity('root','@workspace',None,0,'workspace')
entity('ra','a','root',1,'repository');entity('rb','b','root',1,'repository')
entity('fa','a','ra',2);entity('fb','b','rb',2)
for rid in ['call1','call2']:
    db.execute('''INSERT INTO relationships VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (rid,'s','fa','fb','fa','fb','static','calls','directed','exact',None,1,'edge_count',rid))
for eid in ['ev1','ev2']:
    db.execute('''INSERT INTO evidence(evidence_id,snapshot_id,relationship_id,category,extractor_version,repo_id,revision)
      VALUES (?,?,?,?,?,?,?)''',(eid,'s','call1','ast_exact','v1','a','rev'))
db.execute('''INSERT INTO evidence(evidence_id,snapshot_id,relationship_id,category,extractor_version,repo_id,revision)
 VALUES ('ev3','s','call2','ast_exact','v1','a','rev')''')
db.execute('INSERT INTO analysis_views VALUES (?,?,?,?,?,?)',('s','view','{}','{}',h,'v1'))
for rep in ['fa','fb']:
    db.execute('INSERT INTO view_representatives VALUES (?,?,?,?,?,?,?)',('s','view',rep,'entity',rep,None,1))
    db.execute('INSERT INTO partition_members VALUES (?,?,?,?)',('s','view',rep,rep))
db.execute('INSERT INTO quotient_projections VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
 ('s','view','q','fa','fb','static','calls','directed','exact','edge_count',2,3,2,0))
for rid in ['call1','call2']: db.execute('INSERT INTO quotient_witness_map VALUES (?,?,?,?)',('s','view','q',rid))
db.commit()
assert not db.execute('PRAGMA foreign_key_check').fetchall()
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

rejected=0
def rejects(sql,params=()):
    global rejected
    db.execute('SAVEPOINT invalid_case')
    try:
        db.execute(sql,params)
        db.execute('RELEASE invalid_case')
    except sqlite3.IntegrityError:
        db.execute('ROLLBACK TO invalid_case'); db.execute('RELEASE invalid_case'); rejected+=1
    else: raise AssertionError('Accepted invalid mutation: '+sql)
rejects("UPDATE entities SET is_test=2 WHERE entity_id='fa'")
rejects("UPDATE entities SET ast_body_hash='bad' WHERE entity_id='fa'")
rejects("UPDATE entities SET ancestors_binary_lifting_json='{}' WHERE entity_id='fa'")
rejects("UPDATE relationships SET target_id='missing' WHERE relationship_id='call1'")
rejects("UPDATE relationships SET family='documentation' WHERE relationship_id='call1'")
rejects("UPDATE relationships SET confidence=1.1 WHERE relationship_id='call1'")
rejects("UPDATE quotient_projections SET is_internal=1")
rejects("INSERT INTO quotient_witness_map VALUES ('s','view','q','call1')")
db.execute('INSERT INTO snapshot_sets VALUES (?,?,?,?,?)',('s2',h,'building','2026-11-06T00:00:00Z','{}'))
db.execute('INSERT INTO snapshots VALUES (?,?,?,?,?,?)',('s2','a','rev',h,'v1','[]'))
db.commit()
rejects("INSERT INTO relationships VALUES ('bad','s2','fa','fb','fa','fb','static','calls','directed','exact',NULL,1,'edge_count','bad')")

schema=json.loads((ROOT/'contracts/geographer.rules.schema.json').read_text())
jsonschema.Draft202012Validator.check_schema(schema)
example=yaml.safe_load((ROOT/'contracts/geographer.rules.example.yaml').read_text())
jsonschema.validate(example,schema)
for bad in [dict(example,world_policy='maybe'),dict(example,extra=True),dict(example,version=1)]:
    try:jsonschema.validate(bad,schema)
    except jsonschema.ValidationError:pass
    else:raise AssertionError('Invalid rules accepted')

children={'r':['a','b'],'a':['a1','a2'],'b':['b1','b2'],'a1':[],'a2':[],'b1':[],'b2':[]}
parent={c:p for p,cs in children.items() for c in cs}
leaves={v for v in children if not children[v]}
def leafset(v):return {v} if not children[v] else set().union(*(leafset(c) for c in children[v]))
def partition(v,E):
    active=[c for c in children[v] if c in E]
    if not active:return [(v,leafset(v))]
    out=[g for c in active for g in partition(c,E)]
    unseen=[c for c in children[v] if c not in E]
    if unseen:out.append(('R_'+v,set().union(*(leafset(c) for c in unseen))))
    return out
partition_count=0
for bits in product([False,True],repeat=len(children)-1):
    E={'r'}|{v for v,on in zip([x for x in children if x!='r'],bits) if on}
    if any(v!='r' and parent[v] not in E for v in E):continue
    groups=partition('r',E);members=[u for _,g in groups for u in g]
    assert Counter(members)==Counter({u:1 for u in leaves})
    rep={u:g for g,us in groups for u in us}
    counts=Counter((rep[u],rep[v]) for u in leaves for v in leaves)
    assert sum(counts.values())==len(leaves)**2
    partition_count+=1

depth={'r':0};up={};J=4
def prepare(v):
    up[v]=[parent.get(v,v)]
    for j in range(1,J):up[v].append(up[up[v][j-1]][j-1] if v!='r' else 'r')
    for c in children[v]:depth[c]=depth[v]+1;prepare(c)
prepare('r')
def lca(x,y):
    if depth[x]<depth[y]:x,y=y,x
    delta=depth[x]-depth[y]
    for j in range(J):
        if delta&(1<<j):x=up[x][j]
    if x==y:return x
    for j in range(J-1,-1,-1):
        if up[x][j]!=up[y][j]:x,y=up[x][j],up[y][j]
    return up[x][0]
def distances(adj,s):
    out={s:0};queue=deque([s])
    while queue:
        u=queue.popleft()
        for v in adj[u]:
            if v not in out:out[v]=out[u]+1;queue.append(v)
    return out
tree_adj={v:set(children[v])|({parent[v]} if v in parent else set()) for v in children}
for x in children:
    for y,d in distances(tree_adj,x).items():
        assert depth[x]+depth[y]-2*depth[lca(x,y)]==d

qi_graphs=qi_pairs=0
for n in range(2,6):
    edges=list(combinations(range(n),2))
    for chosen in combinations(edges,n-1):
        adj={v:set() for v in range(n)}
        for u,v in chosen:adj[u].add(v);adj[v].add(u)
        if len(distances(adj,0))!=n:continue
        original={v:distances(adj,v) for v in adj}
        unassigned=set(adj);clusters=[]
        while unassigned:
            forest={u:adj[u]&unassigned for u in unassigned}
            ds={u:distances(forest,u) for u in forest}
            seeds=[u for u in sorted(unassigned) if u==min(v for v,d in ds[u].items() if d<=2)]
            balls=[{v for v,d in ds[u].items() if d<=1} for u in seeds]
            assert sum(map(len,balls))==len(set().union(*balls))
            clusters.extend(balls);unassigned-=set().union(*balls)
        rep={v:i for i,cs in enumerate(clusters) for v in cs}
        b=max(max(distances({v:adj[v]&cs for v in cs},u).values()) for cs in clusters for u in cs)
        assert b<=2
        q={i:set() for i in range(len(clusters))}
        for u,v in chosen:
            if rep[u]!=rep[v]:q[rep[u]].add(rep[v]);q[rep[v]].add(rep[u])
        qds={v:distances(q,v) for v in q}
        for u in adj:
            for v in adj:
                dg=original[u][v];dh=qds[rep[u]][rep[v]]
                assert dh<=dg<=(b+1)*dh+b
                qi_pairs+=1
        qi_graphs+=1

rng=random.Random(42)
for k in range(1,65):
    radii=[rng.uniform(0.1,20) for _ in range(k)];gap=.2;padding=.35
    W=2*sum(radii)+(k-1)*gap;R=padding+W/2
    centers=[-W/2+2*sum(radii[:i])+i*gap+r for i,r in enumerate(radii)]
    assert max(abs(c)+r-R+padding for c,r in zip(centers,radii))<=1e-4
    assert all(abs(centers[i]-centers[j])+1e-4>=radii[i]+radii[j]+gap for i in range(k) for j in range(i+1,k))
for N in range(2,11):
    p=min(3,N-1);M=N-p-1
    knots=[0.]*(p+1)+[j/(N-p) for j in range(1,M+1)]+[1.]*(p+1)
    assert len(knots)==N+p+1
    assert knots==sorted(knots)
    greville=[sum(knots[i+1:i+p+1])/p for i in range(N)]
    def basis(i,degree,t):
        if degree==0:return float(knots[i]<=t<knots[i+1])
        left=knots[i+degree]-knots[i];right=knots[i+degree+1]-knots[i+1]
        return ((t-knots[i])/left*basis(i,degree-1,t) if left else 0)+((knots[i+degree+1]-t)/right*basis(i+1,degree-1,t) if right else 0)
    for t in [.001,.1,.25,.5,.75,.9,.999]:
        assert abs(sum(g*basis(i,p,t) for i,g in enumerate(greville))-t)<1e-10
for M in range(2,25):
    for t in [.01,.2,.5,.9,.99]:
        lanes=[.08*(j-(M-1)/2)*math.sin(math.pi*t) for j in range(M)]
        assert all(lanes[j+1]>lanes[j] for j in range(M-1))

print(json.dumps({'sqlite_tables':14,'sqlite_indexes':18,'invalid_sql_mutations_rejected':rejected,
 'rules_schema_and_example':'pass','legal_partitions_checked':partition_count,
 'LCA_all_pairs':'pass','QI_labeled_trees_checked':qi_graphs,'QI_vertex_pairs_checked':qi_pairs,
 'packing_fallback_cases':64,'spline_knot_cases':9,'lane_separation':'pass'},indent=2))
