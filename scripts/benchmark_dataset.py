"""Explicit synthetic reference workload, never represented as extracted source."""
from pathlib import Path
import json,time,sys
from geographer.model import Graph,Entity,Relationship,Evidence,canonical
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.analysis import materialize_view

def create(path):
    started=time.perf_counter();g=Graph()
    g.add(Entity('bench:workspace','@workspace','workspace','Workspace',None,sort='synthetic',language='none'))
    g.add(Entity('bench:repo','benchmark','repository','Reference workload','bench:workspace',language='none'))
    for i in range(100):g.add(Entity(f'bench:file:{i:03}','benchmark','file',f'module_{i:03}.py','bench:repo',rel_path=f'module_{i:03}.py',start_line=1,end_line=500))
    # 50,000 includes scope atoms introduced on the 100 nonleaf files.
    count=49798
    for i in range(count):
        p=i%100;g.add(Entity(f'bench:fn:{i:05}','benchmark','function',f'module_{p:03}.py.function_{i:05}',f'bench:file:{p:03}',rel_path=f'module_{p:03}.py',start_line=2+i//100,end_line=2+i//100))
    for i in range(150000):
        u=i%count;family=i//count;v=(u+1+family*101)%count
        source=f'bench:fn:{u:05}';target=f'bench:fn:{v:05}';rid=f'bench:edge:{i:06}';p=u%100
        g.relationships[rid]=Relationship(rid,source,target,source,target,['calls','imports','references','calls'][family],'exact',f'fixture:{i}')
        eid=f'bench:evidence:{i:06}';g.evidence[eid]=Evidence(eid,rid,'ast_exact','benchmark','synthetic-v1',f'module_{p:03}.py',2+u//100,2+u//100,canonical({'synthetic_fixture':True,'seed':'geographer-benchmark-v1'}))
    g.augment();assert len(g.entities)==50000
    with SnapshotStore(path) as store:
        sid=store.begin([Repository('benchmark','synthetic-v1',{})],{'stage':3,'synthetic_fixture':True,'seed':'geographer-benchmark-v1'})
        store.write_graph(sid,g,{'benchmark':[]});materialize_view(store,sid,g,{'mode':'kind','kind':'repository'});store.publish(sid)
    report={'snapshot_id':sid,'entities':len(g.entities),'relationships':len(g.relationships),'evidence':len(g.evidence),'seed':'geographer-benchmark-v1','elapsed_seconds':time.perf_counter()-started,'synthetic':True}
    Path('output/benchmark-dataset.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':create(Path(sys.argv[1] if len(sys.argv)>1 else 'output/benchmark.sqlite'))
