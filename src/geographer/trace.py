"""Immutable, source-matched positive runtime observations. Never execute trace input."""
from __future__ import annotations
import ast,base64,hashlib,json,math,ntpath,posixpath,re
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import jsonschema
from .model import Relationship,Evidence,canonical,digest
from .resources import resource_root
from .source import valid_path
from .store import PublicationError

VERSION='python-call-trace-v1'
MAPPER='runtime-source-map-v1'
MAX_BYTES=64*1024*1024
MAX_RECORDS=100000

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key: '+key)
        result[key]=value
    return result

def utc(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z',value):raise ValueError('Collection timestamps require ISO UTC Z with at most microsecond precision')
    dt=datetime.fromisoformat(value[:-1]+'+00:00')
    if dt.tzinfo!=timezone.utc:raise ValueError('Collection timestamps require UTC')
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def validators():
    document=json.loads((resource_root()/'contracts/v1.1/geographer.trace.schema.json').read_text())
    return {name:jsonschema.Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':document['$defs']}) for name in ('Manifest','CallRecord')}

def source_manifest(store,sid):
    store.require_complete(sid)
    return {r['repo_id']:dict(revision=r['revision'],digest=r['digest']) for r in store.connection.execute("SELECT repo_id,revision,digest FROM snapshots WHERE snapshot_id=? AND repo_id<>'@workspace' ORDER BY repo_id",(sid,))}

def collections(store,sid,*,include_quarantine=True):
    expression='result_json' if include_quarantine else "json_remove(result_json,'$.quarantine')"
    return [json.loads(r[0]) for r in store.connection.execute(f"SELECT {expression} FROM analysis_results WHERE snapshot_id=? AND algorithm_version='runtime-collection-v1' ORDER BY analysis_id",(sid,))]

def relative_path(value,root):
    """Lexical mapping only. A trace never causes filesystem reads of its paths."""
    windows=bool(re.match(r'^[a-zA-Z]:[\\/]',value)) or value.startswith('\\\\')
    module=ntpath if windows else posixpath
    if module.isabs(value):
        if not root:return None
        if windows!=bool(re.match(r'^[a-zA-Z]:[\\/]',root)) and not (windows and root.startswith('\\\\')):return None
        try:
            value=module.normpath(value);root=module.normpath(root)
            if module.normcase(module.commonpath([root,value]))!=module.normcase(root):return None
            value=module.relpath(value,root)
        except ValueError:return None
    normalized=value.replace('\\','/')
    if not valid_path(normalized) or any(p in {'','.', '..'} for p in normalized.split('/')):return None
    return normalized

class TraceMapper:
    def __init__(self,store,sid,manifest):
        self.graph=store.graph(sid);self.manifest=manifest;self.index=defaultdict(list);self.folded=defaultdict(list);self.decorator_starts={}
        for e in self.graph.entities.values():
            if e.language=='python' and e.kind in {'file','class','function','method'}:
                self.index[(e.repo_id,e.rel_path)].append(e)
                self.folded[(e.repo_id,e.rel_path.casefold())].append(e)
        for v in self.graph.analyses.values():
            if v['algorithm_version']!='source-bytes-v1':continue
            owner=self.graph.entities[v['scope']['entity_id']]
            try:
                tree=ast.parse(base64.b64decode(v['result']['bytes_base64']))
                for n in ast.walk(tree):
                    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                        self.decorator_starts[(owner.repo_id,owner.rel_path,n.lineno)]=min([n.lineno]+[d.lineno for d in n.decorator_list])
            except (SyntaxError,ValueError):pass
        self.atoms={e.parent_id:e.entity_id for e in self.graph.entities.values() if e.kind=='scope_atom'}

    def resolve(self,row,side):
        path=row[side+'_path'];name=row[side+'_qualname'].replace('.<locals>.','.')
        repo=row.get(side+'_repo_id');candidates=[];safe=False
        namespaces=[repo] if repo else list(self.manifest['sources'])
        for rid in namespaces:
            if rid not in self.manifest['sources']:continue
            rel=relative_path(path,self.manifest['repo_roots'].get(rid));safe|=rel is not None
            if rel is None:continue
            windows=bool(re.match(r'^[a-zA-Z]:[\\/]',path)) or '\\' in path
            items=self.folded.get((rid,rel.casefold()),()) if windows else self.index.get((rid,rel),())
            for entity in items:
                if name=='<module>':match=entity.kind=='file'
                else:match=entity.qualified_name==name or entity.qualified_name==entity.rel_path+'.'+name
                if not match:continue
                if side=='caller':
                    if entity.start_line is None or not entity.start_line<=row['caller_line']<=entity.end_line:continue
                elif 'callee_definition_line' in row:
                    first=self.decorator_starts.get((rid,rel,entity.start_line),entity.start_line)
                    if row['callee_definition_line'] not in {first,entity.start_line}:continue
                candidates.append(entity)
        if len(candidates)==1:return candidates[0],None
        return None,'ambiguous_'+side if candidates else 'unmapped_'+side if safe else 'unsafe_or_outside_root_'+side

def parse_trace(raw,manifest):
    if len(raw)>MAX_BYTES:raise ValueError('Trace exceeds 64 MiB')
    checks=validators();checks['Manifest'].validate(manifest)
    if not manifest['source_match']:raise ValueError('Recorder source mismatch; ingestion refused')
    if manifest['coverage']['complete'] and manifest['coverage']['truncated']:raise ValueError('A truncated capture cannot claim complete coverage')
    if hashlib.sha256(raw).hexdigest()!=manifest['trace_sha256']:raise ValueError('Trace checksum mismatch')
    manifest=json.loads(canonical(manifest));manifest['window']={k:utc(v) for k,v in manifest['window'].items()}
    if manifest['window']['start']>=manifest['window']['end']:raise ValueError('Collection window must have positive duration')
    if set(manifest['repo_roots'])-set(manifest['sources']):raise ValueError('Unknown repository root namespace')
    rows=[];seen=set()
    for line,text in enumerate(raw.decode('utf-8-sig').splitlines(),1):
        if not text.strip():continue
        if len(rows)>=MAX_RECORDS:raise ValueError('Trace exceeds 100,000 records')
        if len(text.encode('utf-8'))>16384:raise ValueError('Trace record exceeds 16 KiB')
        row=json.loads(text,object_pairs_hook=unique_object);checks['CallRecord'].validate(row)
        if 'p95_ms' in row and not math.isfinite(row['p95_ms']):raise ValueError('Nonfinite latency')
        key=canonical({k:v for k,v in row.items() if k not in {'call_count','p95_ms'}})
        if key in seen:raise ValueError('Duplicate call record; repeated observations cannot be silently summed')
        seen.add(key);rows.append((line,row))
    if sum(r['call_count'] for _,r in rows)>9007199254740991:raise ValueError('Collection call-count total exceeds exact integer range')
    return manifest,rows

def ingest_trace(store,base_snapshot_id,raw,manifest,*,environment=None,start=None,end=None):
    """Publish a child in one IMMEDIATE transaction, including validation/status."""
    store.require_complete(base_snapshot_id);manifest,rows=parse_trace(raw,manifest)
    for provided,actual,label in ((environment,manifest['environment'],'environment'),(utc(start) if start else None,manifest['window']['start'],'start'),(utc(end) if end else None,manifest['window']['end'],'end')):
        if provided is not None and provided!=actual:raise ValueError('CLI '+label+' disagrees with the manifest')
    sources=source_manifest(store,base_snapshot_id)
    if manifest['sources']!=sources:raise ValueError('Trace source revisions/digests do not match the base snapshot')
    cid='collection:'+digest(manifest,MAPPER)
    inherited=collections(store,base_snapshot_id,include_quarantine=False)
    for old in inherited:
        if old['collection_id']==cid:
            full=json.loads(store.connection.execute("SELECT result_json FROM analysis_results WHERE snapshot_id=? AND analysis_id=?",(base_snapshot_id,cid)).fetchone()[0])
            return {**full,'snapshot_id':base_snapshot_id,'already_present':True}
        if old['environment']==manifest['environment'] and old['window']['start']<manifest['window']['end'] and manifest['window']['start']<old['window']['end']:
            raise ValueError('Overlapping/conflicting collection; explicit replacement/merge is not implemented')
    if len(inherited)>=256:raise ValueError('A snapshot supports at most 256 runtime collections')
    config=json.loads(store.connection.execute('SELECT config_json FROM snapshot_sets WHERE snapshot_id=?',(base_snapshot_id,)).fetchone()[0])
    from .incremental import build_digest
    mapper_build=build_digest(['trace.py'])
    config={**config,'parent_snapshot_id':base_snapshot_id,'runtime_collection_id':cid,'runtime_mapper_version':MAPPER,'runtime_mapper_build_digest':mapper_build}
    manifest_rows=sorted((rid,data['revision'],data['digest'],config.get('source_roots',{}).get(rid,[''])) for rid,data in sources.items())
    mh=digest(manifest_rows,config);sid='snapshot:'+mh
    if store.connection.execute("SELECT 1 FROM snapshot_sets WHERE snapshot_id=? AND status='complete'",(sid,)).fetchone():
        return {**next(c for c in collections(store,sid) if c['collection_id']==cid),'snapshot_id':sid,'already_present':True}
    mapper=TraceMapper(store,base_snapshot_id,manifest);rels=[];evidence=[];reasons=Counter();quarantine=[];quarantine_bytes=0;mapped_calls=0;quarantined_calls=0;comparisons=Counter();mapped_sites=set()
    static_calls=defaultdict(list)
    for r in mapper.graph.relationships.values():
        if r.family=='static' and r.subtype=='calls':static_calls[r.source_subject_id].append(r)
    static_lines=defaultdict(set)
    for e in mapper.graph.evidence.values():static_lines[e.relationship_id].add(e.start_line)
    for line,row in rows:
        caller,why=mapper.resolve(row,'caller');callee,other=mapper.resolve(row,'callee')
        if why or other:
            reason=why or other;reasons[reason]+=1;quarantined_calls+=row['call_count']
            entry=dict(line=line,reason=reason,record=row);cost=len(canonical(entry).encode('utf-8'))
            if len(quarantine)<1000 and quarantine_bytes+cost<=1024*1024:quarantine.append(entry);quarantine_bytes+=cost
            continue
        rid='relationship:'+digest('runtime-call-v1',cid,line,row)
        site=(caller.entity_id,row['caller_line'],callee.entity_id)
        if site in mapped_sites:raise ValueError('Duplicate normalized call site; observation aliases cannot be summed')
        mapped_sites.add(site)
        at_site=[r for r in static_calls[caller.entity_id] if row['caller_line'] in static_lines[r.relationship_id]]
        matching=[r for r in at_site if r.target_subject_id==callee.entity_id]
        comparison='matches_static_exact' if any(r.resolution_status=='exact' for r in matching) else 'matches_static_candidate' if any(r.resolution_status=='candidate' for r in matching) else 'differs_from_static_exact' if any(r.resolution_status=='exact' for r in at_site) else 'no_matching_static_target'
        comparisons[comparison]+=1
        rels.append(Relationship(rid,mapper.atoms.get(caller.entity_id,caller.entity_id),mapper.atoms.get(callee.entity_id,callee.entity_id),
            caller.entity_id,callee.entity_id,'calls','observed',cid+':'+str(line),family='runtime',weight=row['call_count'],weight_unit='call_count'))
        details=dict(claim_version='runtime-claim-v1',claim_kind='runtime_observation',reason_code='OBSERVED_IN_COLLECTION',producer=manifest['recorder'],
            static_comparison=dict(outcome=comparison,matching_relationship_ids=sorted(r.relationship_id for r in matching),
                other_exact_target_ids=sorted({r.target_subject_id for r in at_site if r.resolution_status=='exact' and r.target_subject_id!=callee.entity_id})),
            collection_id=cid,environment=manifest['environment'],source_match=True,record=row,record_line=line,
            limitations=['Positive first-activation adjacency only; no whole-path ordering or negative coverage inference',
                'Input p95 is producer-reported and is not averaged across records',*manifest['coverage']['limitations']])
        evidence.append(Evidence('evidence:'+digest(rid),rid,'dynamic_observed',caller.repo_id,sources[caller.repo_id]['revision'],caller.rel_path,row['caller_line'],row['caller_line'],canonical(details),
            extractor_version=MAPPER,trace_ref='trace:'+manifest['trace_sha256']+':'+str(line),window_start=manifest['window']['start'],window_end=manifest['window']['end']))
        mapped_calls+=row['call_count']
    report=dict(collection_id=cid,format_version=VERSION,mapper_version=MAPPER,mapper_build_digest=mapper_build,parent_snapshot_id=base_snapshot_id,
        environment=manifest['environment'],window=manifest['window'],source_match=True,coverage=manifest['coverage'],recorder=manifest['recorder'],
        repo_roots=manifest['repo_roots'],capture_statistics=manifest.get('statistics',{}),exit_code=manifest.get('exit_code'),command_digest=manifest.get('command_digest'),
        trace_sha256=manifest['trace_sha256'],sources=sources,input_records=len(rows),mapped_records=len(rels),quarantined_records=len(rows)-len(rels),
        input_call_count=mapped_calls+quarantined_calls,mapped_call_count=mapped_calls,quarantined_call_count=quarantined_calls,
        quarantine_reason_counts=dict(reasons),quarantine=quarantine,quarantine_complete=len(rows)-len(rels)==len(quarantine),static_comparison_record_counts=dict(comparisons))
    c=store.connection
    if c.in_transaction:raise ValueError('Commit the caller transaction before importing a trace')
    c.execute('BEGIN IMMEDIATE')
    try:
        c.execute('INSERT INTO snapshot_sets VALUES(?,?,?,?,?)',(sid,mh,'building',datetime.now(timezone.utc).isoformat(),canonical(config)))
        for table in ('snapshots','entities','relationships','evidence','documentary_incidences'):
            columns=[r[1] for r in c.execute('PRAGMA table_info('+table+')')];select=["?" if n=='snapshot_id' else n for n in columns]
            c.execute(f"INSERT INTO {table}({','.join(columns)}) SELECT {','.join(select)} FROM {table} WHERE snapshot_id=?",(sid,base_snapshot_id))
        c.execute("UPDATE snapshots SET revision=?,digest=? WHERE snapshot_id=? AND repo_id='@workspace'",('manifest:'+mh,mh,sid))
        # Source/static caches and prior runtime collections can be inherited;
        # view IDs, query handles and review artifacts cannot cross snapshots.
        static_versions=('source-bytes-v1','py-ast-v1','declaration-v1','documentary-tree-v1','documentary-v2','c3-static-v1','directed-wl3-v1','boundary-cayley-v1','helper_tree_balls_v1','runtime-collection-v1')
        marks=','.join('?' for _ in static_versions)
        c.execute(f'INSERT INTO analysis_results SELECT ?,analysis_id,algorithm_version,scope_json,result_json FROM analysis_results WHERE snapshot_id=? AND algorithm_version IN ({marks})',(sid,base_snapshot_id,*static_versions))
        store.insert_many('relationships',({'snapshot_id':sid,**asdict(r)} for r in rels))
        store.insert_many('evidence',({'snapshot_id':sid,**asdict(e)} for e in evidence))
        c.execute('INSERT INTO analysis_results VALUES(?,?,?,?,?)',(sid,cid,'runtime-collection-v1',canonical({'collection_id':cid}),canonical(report)))
        if config.get('stage',1)>=2:
            from .analysis import materialize_view
            graph=mapper.graph;graph.relationships.update((r.relationship_id,r) for r in rels);graph.evidence.update((e.evidence_id,e) for e in evidence)
            for grouping in ({'mode':'atomic'},{'mode':'kind','kind':'file'},{'mode':'kind','kind':'repository'}):materialize_view(store,sid,graph,grouping)
        problems=store.validate(sid)
        if problems:raise PublicationError(problems)
        c.execute("UPDATE snapshot_sets SET status='complete' WHERE snapshot_id=?",(sid,));c.commit()
    except BaseException:c.rollback();raise
    return {**report,'snapshot_id':sid,'already_present':False}

def read_artifacts(path,manifest_path=None):
    path=Path(path);sidecar=Path(manifest_path) if manifest_path else Path(str(path)+'.manifest.json')
    if path.stat().st_size>MAX_BYTES or sidecar.stat().st_size>1024*1024:raise ValueError('Trace/manifest file size limit exceeded')
    with path.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    with sidecar.open('rb') as stream:metadata=stream.read(1024*1024+1)
    if len(raw)>MAX_BYTES or len(metadata)>1024*1024:raise ValueError('Trace/manifest file size limit exceeded')
    return raw,json.loads(metadata.decode('utf-8'),object_pairs_hook=unique_object)
