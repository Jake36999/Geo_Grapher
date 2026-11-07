"""Versioned workspace artifacts; review decisions never mutate extracted facts."""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timezone
import ast,base64,json
from .analysis import DEFAULT_FILTER,selected_relationships,eligible_entity
from .model import canonical,digest
from .rules import ArchitectureRules,RuleConflict
from .service import QueryError

def model_catalog(service):
    return [dict(digest=m.digest,world_policy=m.model['world_policy']) for m in service.rules.values()]

def load_rules(service,sid,text,activate=True):
    if not isinstance(text,str) or len(text.encode('utf-8'))>262144:raise ValueError('Rules text must be at most 256 KiB')
    ctx=service._context(sid);model=ArchitectureRules(text.encode('utf-8'))
    mapping=model.map_entities(ctx['g'],sid)  # Validate overlap before publication.
    if activate:
        if model.digest not in service.rules and len(service.rules)>=32:raise ValueError('The workspace retains at most 32 rule models')
        # Retain CLI-loaded predecessors too, so activating a new model cannot
        # strand a saved view that referred to the previous startup model.
        with service.store.connection:
            for retained in [*service.rules.values(),model]:
                service.store.connection.execute('INSERT OR IGNORE INTO analysis_results VALUES(?,?,?,?,?)',
                    (sid,'rules-model:'+retained.digest,'rules-model-v1',canonical({'snapshot_id':sid}),canonical({'text':canonical(retained.model)})))
        service.rules[model.digest]=model
    return dict(model_digest=model.digest,world_policy=model.model['world_policy'],activated=activate,
        mapped=sum(v!='Unmapped' for v in mapping.values()),unmapped=sum(v=='Unmapped' for v in mapping.values()),models=model_catalog(service))

def recover_rules(service):
    for row in service.store.connection.execute("SELECT result_json FROM analysis_results WHERE algorithm_version='rules-model-v1' ORDER BY analysis_id"):
        model=ArchitectureRules(json.loads(row[0])['text'].encode('utf-8'))
        if model.digest not in service.rules and len(service.rules)>=32:raise ValueError('Persisted model retention exceeds 32')
        service.rules[model.digest]=model

def overlay(service,sid,overlay_id):
    if not overlay_id:return None
    row=service.store.connection.execute("SELECT result_json FROM analysis_results WHERE snapshot_id=? AND analysis_id=? AND algorithm_version='semantic-overlay-v1'",(sid,overlay_id)).fetchone()
    if not row:raise QueryError('NOT_FOUND','Overlay unavailable or belongs to another snapshot')
    return json.loads(row[0])

def append_annotation(service,sid,entity_id,text,decision='pending',previous=None):
    ctx=service._context(sid)
    if entity_id not in ctx['g'].entities:raise ValueError('Annotation target is outside snapshot')
    if not isinstance(text,str) or not text.strip() or len(text)>2000:raise ValueError('Annotation text must contain 1–2000 characters')
    if decision not in {'pending','accepted','rejected'}:raise ValueError('Invalid review decision')
    prior=overlay(service,sid,previous);records=list(prior['records']) if prior else []
    if len(records)>=200:raise ValueError('Overlay record limit reached')
    record=dict(entity_id=entity_id,text=text,decision=decision,claim_kind='reviewed_annotation',
        producer='workspace-user',trust='untrusted_repository_content',created_at=datetime.now(timezone.utc).isoformat())
    record['record_id']='annotation:'+digest(record)
    record['supersedes_record_id']=next((r['record_id'] for r in reversed(records) if r['entity_id']==entity_id),None)
    value=dict(algorithm_version='semantic-overlay-v1',base_snapshot_id=sid,previous_overlay_id=previous,records=records+[record],
        producer='workspace-user',producer_version='workspace-review-v1',created_at=record['created_at'],content_digest=digest(records+[record]))
    oid='overlay:'+digest(value);value['overlay_id']=oid
    service.store.connection.execute('INSERT OR IGNORE INTO analysis_results VALUES(?,?,?,?,?)',
        (sid,oid,'semantic-overlay-v1',canonical({'snapshot_id':sid}),canonical(value)))
    return value

def triage(service,sid,filters,focus=None,pins=(),model_digest=None,after=None,limit=10,queue='unknown_locality'):
    if type(limit) is not int or not 1<=limit<=100 or queue not in {'internal_candidates','unknown_locality','unmapped'}:raise ValueError('Invalid triage bounds/queue')
    ctx=service._context(sid);g=ctx['g'];mapping={}
    if model_digest:
        if model_digest not in service.rules:raise ValueError('Rules model not loaded')
        mapping=service.rules[model_digest].map_entities(g,sid)
    selected=list(selected_relationships(g,{**filters,'resolution_statuses':['exact','candidate','unresolved']}))
    degree=Counter();seen=defaultdict(set);groups={};focuses=set()
    for anchor in [focus,*pins]:
        if anchor is None:continue
        if anchor not in g.entities:raise ValueError('Triage anchor is outside snapshot')
        focuses.update(ctx['tree'].descendants(anchor))
    for r in selected:
        if r.family!='static':continue
        evidence=ctx['evidence'][r.relationship_id];details=json.loads(evidence[0].details_json) if evidence else {}
        occurrence=details.get('occurrence_id',r.relationship_id)
        for eid in {r.source_subject_id,r.target_subject_id}:seen[eid].add(occurrence)
        if r.subtype!='calls' or r.resolution_status=='exact':continue
        target=g.entities[r.target_subject_id]
        category='internal_candidates' if r.resolution_status=='candidate' and not target.is_external else 'external_builtin' if details.get('reason_code') in {'EXTERNAL_PACKAGE_UNINDEXED','BUILTIN_SYMBOL'} else 'unknown_locality'
        row=groups.setdefault(occurrence,dict(occurrence_id=occurrence,entity_id=r.source_subject_id,queue=category,
            line=evidence[0].start_line if evidence else None,reason_codes=set(),relationship_ids=[],alternatives=[],boundary=False))
        if category=='internal_candidates':row['queue']=category
        row['reason_codes'].add(details.get('reason_code','legacy_reason_unavailable'))
        row['relationship_ids'].append(r.relationship_id);row['alternatives'].append(r.target_subject_id)
        u,v=mapping.get(r.source_subject_id),mapping.get(r.target_subject_id)
        row['boundary']|=bool(u and v and u!='Unmapped' and v!='Unmapped' and u!=v)
    for eid,items in seen.items():degree[eid]=len(items)
    if queue=='unmapped':
        if not model_digest:raise ValueError('Unmapped queue requires a rules model')
        groups={eid:dict(occurrence_id=eid,entity_id=eid,queue='unmapped',line=g.entities[eid].start_line,
            reason_codes={'UNMAPPED_COMPONENT'},relationship_ids=[],alternatives=[],boundary=False) for eid,c in mapping.items() if c=='Unmapped' and g.entities[eid].sort=='entity' and g.entities[eid].kind!='scope_atom' and eligible_entity(g.entities[eid],filters)}
    rows=[]
    for row in groups.values():
        if row['queue']!=queue:continue
        row.update(reason_codes=sorted(row['reason_codes']),relationship_ids=sorted(set(row['relationship_ids'])),alternatives=sorted(set(row['alternatives'])),
            focus_relevant=row['entity_id'] in focuses or bool(set(row['alternatives'])&focuses),incident_occurrences=degree[row['entity_id']],target_degree=None)
        rows.append(row)
    rows.sort(key=lambda r:(not r['focus_relevant'],not r['boundary'],-r['incident_occurrences'],r['occurrence_id']))
    identity=digest(sid,filters,focus,sorted(pins),model_digest,queue,'ambiguity-triage-v1')
    if after:
        cursor=service.read_handle(after)
        if cursor.get('query_digest')!=identity:raise ValueError('Triage page scope changed')
        position=next((i+1 for i,r in enumerate(rows) if r['occurrence_id']==cursor['after']),None)
        if position is None:raise ValueError('Triage cursor no longer available')
    else:position=0
    page=rows[position:position+limit]
    next_cursor=service._handle('triage_page',dict(query_digest=identity,after=page[-1]['occurrence_id'])) if position+limit<len(rows) else None
    return dict(algorithm_version='ambiguity-triage-v1',queue=queue,total=len(rows),items=page,next_cursor=next_cursor,
        ordering='focus/pin relevance, witnessed boundary, distinct incident occurrences, occurrence ID')

def investigation(service,q,ctx):
    """Read-only source/process cards: lexical order is explicitly not execution order."""
    eid=q['entity_id'];g=ctx['g'];e=g.entities[eid];sections=[];fragments=set()
    for incidence in g.incidences:
        if incidence['entity_id']==eid:fragments.add(incidence['fragment_id'])
    if e.kind=='fragment':fragments.add(eid)
    for value in g.analyses.values():
        if value['algorithm_version']!='documentary-tree-v1':continue
        result=value['result']
        byid={s['section_id']:s for s in result['sections']};selected=set()
        for section in byid.values():
            if set(section['fragment_ids'])&fragments:
                current=section
                while current and current['section_id'] not in selected:
                    selected.add(current['section_id']);current=byid.get(current['parent_section_id'])
        for section in result['sections']:
            if section['section_id'] in selected:
                sections.append(dict(section_id=section['section_id'],parent_section_id=section['parent_section_id'],heading=section['heading'],
                    fragment_ids=sorted(set(section['fragment_ids'])&fragments),coordinate_space=result.get('coordinate_space','artifact_bytes')))
    steps=[];source=ctx['sources'].get((e.repo_id,e.rel_path));gaps=[]
    if source and e.language=='python':
        try:
            root=ast.parse(base64.b64decode(source['bytes_base64']));matches=[n for n in ast.walk(root) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.lineno==e.start_line]
            body=matches[0].body if matches else root.body if e.kind=='file' else []
            for node in body[:32]:steps.append(dict(start_line=node.lineno,end_line=node.end_lineno,kind=type(node).__name__,basis='syntax'))
            if len(body)>32:gaps.append('Statement list limited to 32 direct statements')
        except (SyntaxError,ValueError):gaps.append('Source syntax unavailable')
    calls=sorted(r.relationship_id for r in g.relationships.values() if r.source_subject_id==eid and r.subtype=='calls')
    return dict(algorithm_version='process-evidence-v1',documentary_sections=sections[:32],
        statement_steps=steps,call_relationship_ids=calls[:32],overlay=overlay(service,q['snapshot_id'],q.get('overlay_id')),
        limitations=gaps+['Lexical statement order is not an execution sequence','Preconditions, postconditions and pattern predicates are not inferred',
            'Static call adjacency does not establish invocation order']+(['Call list limited to 32 relationships'] if len(calls)>32 else [])+
            (['Documentary hierarchy limited to 32 sections'] if len(sections)>32 else []))
