"""Versioned actor records, scoped aliases and evidence-grounded previews."""
from __future__ import annotations
import ast,base64,json,re
from collections import Counter,defaultdict
from .analysis import DEFAULT_FILTER,selected_relationships
from .model import digest

REFS={'id','node_id','entity_id','source','target','parent_id','source_subject_id','target_subject_id','projection_id','relationship_id',
      'focus_id','representative_focus_id','start_id','scope_id','component_id','source_component_id','target_component_id','canonical_source','canonical_target','doc_handle','resolved_source','resolved_target'}
ARRAY_REFS={'ancestor_ids','evidence_ids','witness_path_ids','witness_projection_ids','fragment_ids','fallback_parent_ids','call_relationship_ids','alternatives','relationship_ids'}

class ActorEncoder:
    version='actor-records-v1'
    def __init__(self,service,ctx,view_id,filters=None,context_shells=True):
        self.service=service;self.ctx=ctx;self.g=ctx['g'];self.sid=service.active_snapshot;self.view_id=view_id
        self.aliases={};self.canonical={};self.nodes={};self.summaries={};self.members=defaultdict(list)
        self.context_shells=context_shells
        self.identity_scope=service._handle('identity_scope',dict(snapshot_id=self.sid,view_id=view_id,algorithm_version=self.version))
        for prefix,ids in [('n',self.g.entities),('w',self.g.relationships),('e',self.g.evidence)]:
            for i,eid in enumerate(sorted(ids),1):self.register(eid,prefix+str(i))
        if view_id:
            for i,row in enumerate(service.store.connection.execute('SELECT representative_id FROM view_representatives WHERE snapshot_id=? AND view_id=? ORDER BY representative_id',(self.sid,view_id)),1):
                if row[0] not in self.aliases:self.register(row[0],'g'+str(i))
            for i,row in enumerate(service.store.connection.execute('SELECT projection_id FROM quotient_projections WHERE snapshot_id=? AND view_id=? ORDER BY projection_id',(self.sid,view_id)),1):self.register(row[0],'p'+str(i))
            for row in service.store.connection.execute('SELECT representative_id,atom_id FROM partition_members WHERE snapshot_id=? AND view_id=? ORDER BY representative_id,atom_id',(self.sid,view_id)):self.members[row[0]].append(row[1])
        self.degree=Counter();self.crossing=Counter();rep={atom:r for r,atoms in self.members.items() for atom in atoms}
        for rel in selected_relationships(self.g,filters or DEFAULT_FILTER):
            owners={self.owner(rel.source_id),self.owner(rel.target_id)}
            for eid in owners:self.degree[eid]+=1
            if rep.get(rel.source_id)!=rep.get(rel.target_id):
                for eid in owners:self.crossing[eid]+=1
        self.docs=defaultdict(list)
        for eid,e in self.g.entities.items():
            if e.kind=='fragment':self.docs[e.parent_id].append(eid)
        self.files={}

    def register(self,canonical,alias):
        if alias in self.canonical and self.canonical[alias]!=canonical:raise ValueError('Actor alias collision')
        self.aliases[canonical]=alias;self.canonical[alias]=canonical;return alias

    def ref(self,eid):
        if eid is None:return None
        if eid not in self.aliases:
            alias=self.register(eid,'a'+digest(eid)[:16])
            key='actor-alias:'+self.identity_scope+':'+alias
            c=self.service.store.connection
            c.execute('INSERT OR IGNORE INTO analysis_results VALUES(?,?,?,?,?)',(self.sid,key,'actor-alias-v1',json.dumps({'identity_scope':self.identity_scope}),json.dumps({'canonical_id':eid})))
            stored=json.loads(c.execute('SELECT result_json FROM analysis_results WHERE snapshot_id=? AND analysis_id=?',(self.sid,key)).fetchone()[0])
            if stored['canonical_id']!=eid:raise ValueError('Persistent actor alias collision')
        return self.aliases[eid]

    def owner(self,eid):
        e=self.g.entities[eid];return e.parent_id if e.kind=='scope_atom' else eid

    def declaration(self,eid):
        eid=self.owner(eid);e=self.g.entities[eid]
        value=self.g.analyses.get('declaration:'+eid,{}).get('result')
        if value:return value
        # Immutable legacy snapshots can be described from their stored bytes;
        # deriving a descriptor never writes new canonical facts.
        key=(e.repo_id,e.rel_path)
        if key not in self.files:
            found={}
            source=self.ctx.get('sources',{}).get(key)
            if source:
                try:
                    tree=ast.parse(base64.b64decode(source['bytes_base64']))
                    found[('file',1)]={'signature':None,'docstring':ast.get_docstring(tree,clean=False)}
                    for node in ast.walk(tree):
                        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                            sig=('class '+node.name+('('+', '.join(ast.unparse(b) for b in node.bases)+')' if node.bases else '') if isinstance(node,ast.ClassDef) else
                                 ('async def ' if isinstance(node,ast.AsyncFunctionDef) else 'def ')+node.name+'('+ast.unparse(node.args)+')'+(' -> '+ast.unparse(node.returns) if node.returns else ''))
                            found[('class' if isinstance(node,ast.ClassDef) else 'function',node.lineno)]={'signature':sig,'docstring':ast.get_docstring(node,clean=False)}
                except (SyntaxError,ValueError,UnicodeError):pass
            self.files[key]=found
        return self.files[key].get(('function' if e.kind=='method' else e.kind,e.start_line),{})

    def summary(self,eid):
        owner=self.owner(eid);decl=self.declaration(eid);signature=decl.get('signature')
        text=decl.get('docstring')
        if not text and self.g.entities[eid].kind=='fragment':text=self.g.analyses.get('text:'+eid,{}).get('result',{}).get('text')
        gist=re.split(r'(?<=[.!?])\s',text.strip(),maxsplit=1)[0] if text and text.strip() else None
        docid=eid if self.g.entities[eid].kind=='fragment' else next(iter(sorted(self.docs.get(owner,[]))),None)
        return dict(signature=signature[:240] if signature else None,doc_gist=gist[:140] if gist else None,
                    doc_handle=docid,truncated=bool(signature and len(signature)>240 or gist and len(gist)>140))

    def node(self,node):
        eid=node['id']
        if eid in self.nodes:return self.nodes[eid]
        members=self.members.get(eid)
        normalized_members=False
        container=node['kind'] in {'workspace','repository','directory','package','residual','qi','conceptual','unmapped','document'}
        if members is None and container and node['membership_handle']:
            listed=self.service.read_handle(node['membership_handle']).get('members',[]);atoms=set()
            for member in listed:
                children=self.ctx['tree'].children.get(member,[])
                if not children:atoms.add(member)
                else:atoms.update(c for c in children if self.g.entities[c].kind=='scope_atom')
            members=sorted(atoms)
            normalized_members=True
        representation='group' if members is not None and (len(members)>1 or container) else 'context_shell' if self.context_shells and self.view_id and members is None and self.ctx['tree'].children.get(eid) else 'atomic'
        preview=None
        if representation=='group':
            owners=sorted({self.owner(a) for a in members},key=lambda a:(-self.crossing[a],-self.degree[a],a))
            examples=[]
            for a in owners[:5]:
                e=self.g.entities[a];sig=self.declaration(a).get('signature')
                examples.append(dict(id=a,qualified_name=e.qualified_name,kind=e.kind,signature=sig[:240] if sig else None))
            preview=dict(kind_counts=dict(Counter(self.g.entities[self.owner(a)].kind for a in members)),top_exemplars=examples,exemplars_complete=len(examples)==len(members))
        result={k:node[k] for k in ('id','kind','sort','repo_id','language','qualified_name','parent_id','source','flags','member_count','membership_handle')}
        result.update(is_synthetic=node['entity_id'] is None or node['sort']=='synthetic',representation=representation,
            summary=self.summary(eid) if eid in self.g.entities else dict(signature=None,doc_gist=None,doc_handle=None,truncated=False),group_preview=preview)
        if representation=='context_shell':result['member_count']=0;result['membership_handle']=None
        elif members is not None:
            result['member_count']=len(members)
            if normalized_members or len(members)>1 and not result['membership_handle']:result['membership_handle']=self.service._handle('members',dict(members=members))
        self.nodes[eid]=result;return result

    def relationship(self,row):
        rid=row['id']
        if rid in self.summaries:return self.summaries[rid]
        ids=[r[0] for r in self.service.store.connection.execute('SELECT relationship_id FROM quotient_witness_map WHERE snapshot_id=? AND view_id=? AND projection_id=? ORDER BY relationship_id',(self.sid,self.view_id,rid))]
        reasons=Counter();preview=[]
        for original in ids:
            rel=self.g.relationships[original];evidence=self.ctx['evidence'][original]
            first=evidence[0] if evidence else None
            details=json.loads(first.details_json) if first else {}
            reason=details.get('reason_code','OBSERVED_IN_COLLECTION' if rel.family=='runtime' else 'DECLARED_RULE' if rel.family=='expected' else 'legacy_reason_unavailable')
            reasons[reason]+=1
            if len(preview)<3:preview.append(dict(relationship_id=original,source_qualname=self.g.entities[rel.source_subject_id].qualified_name,
                target_qualname=self.g.entities[rel.target_subject_id].qualified_name,line=first.start_line if first else None,reason_code=reason))
        if len(ids)!=row['witness_count']:raise ValueError('Projection witness count mismatch')
        result={k:v for k,v in row.items() if k not in {'view_id','witness_cursor'}}
        result.update(witness_preview=preview,reason_counts=dict(reasons),preview_complete=len(preview)==len(ids))
        self.summaries[rid]=result;return result

    def encode(self,value,key=None):
        if isinstance(value,list):return [self.ref(v) if key in ARRAY_REFS and isinstance(v,str) else self.encode(v) for v in value]
        if isinstance(value,dict):
            result={k:self.encode(v,k) for k,v in value.items()}
            if {'repo_id','rel_path','start_line','end_line','revision'}<=result.keys():
                revision=result.pop('revision')
                if revision!=self.ctx['revmap'].get(result['repo_id']):result['revision_override']=revision
            return result
        return self.ref(value) if key in REFS and isinstance(value,str) and not value.startswith('handle:') else value

    def records(self,collection,records):
        return [self.encode(self.node(r) if collection=='nodes' else self.relationship(r) if collection=='relationships' else r) for r in records]

    def prepare(self,plan):
        if getattr(plan,'actor_encoder',None):return plan
        for k,v in list(plan.mandatory.items()):
            if isinstance(v,list) and (not v or isinstance(v[0],dict)):plan.mandatory[k]=self.records(k,v)
            else:plan.mandatory[k]=self.encode(v,k)
        for unit in plan.units:
            unit.records={k:self.records(k,v) for k,v in unit.records.items()}
        plan.evidence_plans={self.ref(k):v for k,v in plan.evidence_plans.items()}
        plan.actor_encoder=self
        return plan

    def envelope_data(self,data,include_ids=False):
        used=set()
        def visit(value,key=None):
            if isinstance(value,dict):
                for k,v in value.items():
                    if k!='ids':visit(v,k)
            elif isinstance(value,list):
                for v in value:visit(v,key)
            elif (key in REFS or key in ARRAY_REFS) and isinstance(value,str) and value in self.canonical:used.add(value)
        visit(data)
        return {**data,'identity_scope':self.identity_scope,'ids':{alias:self.canonical[alias] for alias in sorted(used)} if include_ids else {}}

def resolve_request_aliases(service,ctx,request):
    """Explicit scope binding survives memory-cache eviction; no guessing IDs."""
    from .service import QueryError
    scope_id=request.get('alias_scope')
    if not scope_id:return request
    scope=service.read_handle(scope_id)
    if scope.get('snapshot_id')!=request['snapshot_id']:raise QueryError('SNAPSHOT_MISMATCH','Alias scope belongs to another snapshot')
    if scope.get('algorithm_version')!=ActorEncoder.version:raise QueryError('INVALID_REQUEST','Unsupported alias scope version')
    view=scope.get('view_id')
    if 'view_id' in request and request['view_id']!=view:raise QueryError('INVALID_CURSOR','Projection alias belongs to another view')
    arrays=ctx.setdefault('identity_arrays',{})
    def resolve(alias):
        if alias is None:return None
        match=re.fullmatch(r'([nwegp])([1-9][0-9]*)',alias)
        if match:
            prefix=match[1];key=(prefix,view if prefix in {'g','p'} else None)
            if key not in arrays:
                if prefix in {'n','w','e'}:arrays[key]=sorted({'n':ctx['g'].entities,'w':ctx['g'].relationships,'e':ctx['g'].evidence}[prefix])
                else:
                    table,column=('view_representatives','representative_id') if prefix=='g' else ('quotient_projections','projection_id')
                    arrays[key]=[r[0] for r in service.store.connection.execute(f'SELECT {column} FROM {table} WHERE snapshot_id=? AND view_id=? ORDER BY {column}',(request['snapshot_id'],view))]
                while len(arrays)>12:arrays.pop(next(iter(arrays)))
            index=int(match[2])-1;values=arrays[key]
            if index>=len(values):raise QueryError('NOT_FOUND','Alias unavailable; refresh its scope')
            value=values[index]
            if prefix=='g' and value in ctx['g'].entities:raise QueryError('NOT_FOUND','Alias unavailable')
            return value
        if re.fullmatch(r'a[0-9a-f]{16}',alias):
            row=service.store.connection.execute('SELECT result_json FROM analysis_results WHERE snapshot_id=? AND analysis_id=? AND algorithm_version=?',
                (request['snapshot_id'],'actor-alias:'+scope_id+':'+alias,'actor-alias-v1')).fetchone()
            if row:return json.loads(row[0])['canonical_id']
        raise QueryError('INVALID_REQUEST','Scoped references must be valid aliases; omit alias_scope for canonical IDs')
    request=dict(request)
    for key in ('entity_id','focus_id','scope_id','projection_id','relationship_id'):
        if key in request:request[key]=resolve(request[key])
    for key in ('pins','revealed_ids'):
        if key in request:request[key]=[resolve(v) for v in request[key]]
    if 'grouping' in request and request['grouping']['mode']=='mixed':request['grouping']={**request['grouping'],'revealed_ids':[resolve(v) for v in request['grouping']['revealed_ids']]}
    return request
