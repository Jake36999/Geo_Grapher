"""Bounded T_S source folding; syntactic nesting is not control-flow proof."""
from __future__ import annotations
import ast,base64,hashlib,io,re,tokenize
from bisect import bisect_left
from .model import digest
from .packing import Unit

class SourceTree:
    version='source-context-v1'
    def __init__(self,raw,path,repo_id=''):
        encoding,_=tokenize.detect_encoding(io.BytesIO(raw).readline)
        self.text=raw.decode(encoding);self.lines=self.text.splitlines(keepends=True) or [''];self.entries=[]
        self.source_bytes=len(raw)
        self.identity=digest(repo_id,path,hashlib.sha256(raw).hexdigest())
        self.tree=ast.parse(self.text,filename=path)
        self.tokens=list(tokenize.generate_tokens(io.StringIO(self.text).readline))
        self.colons=[t for t in self.tokens if t.type==tokenize.OP and t.string==':'];self.colon_starts=[t.start for t in self.colons]
        self.root=self.add('module',1,max(1,len(self.lines)),None,None)
        def walk(node,parent):
            if not isinstance(node,ast.stmt):return
            start=min([node.lineno]+[d.lineno for d in getattr(node,'decorator_list',[])])
            entry=self.add(type(node).__name__,start,node.end_lineno,parent,node)
            bodies=[]
            if hasattr(node,'body') and isinstance(node.body,list):bodies.append(node.body)
            if isinstance(node,(ast.Try,ast.TryStar)):
                for handler in node.handlers:
                    h=self.add(type(handler).__name__,handler.lineno,handler.end_lineno,entry,handler)
                    for statement in handler.body:walk(statement,h)
            for name in ('orelse','finalbody'):
                body=getattr(node,name,[])
                if not body:continue
                first=body[0];keyword='finally' if name=='finalbody' else 'else'
                # elif is represented by its own AST If header, never fabricated.
                if isinstance(first,ast.If) and self.lines[first.lineno-1].lstrip().startswith('elif'):
                    bodies.append(body);continue
                line=next((i for i in range(first.lineno-1,node.lineno-1,-1) if re.match(r'^\s*'+keyword+r'\s*:',self.lines[i-1])),first.lineno)
                clause=self.add(keyword,line,body[-1].end_lineno,entry,None,header_end=line)
                for statement in body:walk(statement,clause)
            if isinstance(node,ast.Match):
                for case in node.cases:
                    start=case.pattern.lineno
                    clause=self.add('case',start,case.body[-1].end_lineno,entry,None,header_end=max(start,case.body[0].lineno-1))
                    for statement in case.body:walk(statement,clause)
            for body in bodies:
                for statement in body:walk(statement,entry)
        for node in self.tree.body:walk(node,self.root)

    def add(self,kind,start,end,parent,node,header_end=None):
        if header_end is None and node is not None:
            body=getattr(node,'body',None)
            if isinstance(node,ast.Match) and node.cases:body=[node.cases[0].pattern]
            if isinstance(body,list) and body:
                first=(body[0].lineno,body[0].col_offset)
                a=bisect_left(self.colon_starts,(getattr(node,'lineno',start),0));b=bisect_left(self.colon_starts,first)
                colons=self.colons[a:b]
                header_end=colons[-1].end[0] if colons else start
            else:header_end=start
        entry=dict(id='source:'+digest(self.identity,kind,start,end,len(self.entries)),kind=kind,start=start,end=end,parent=parent,
                   header_end=header_end or start,node=node,children=[],depth=parent['depth']+1 if parent else 0)
        self.entries.append(entry)
        if parent:parent['children'].append(entry)
        return entry

    def spine(self,start,end):
        containing=[e for e in self.entries if e['start']<=start and e['end']>=end]
        best=min(containing,key=lambda e:(e['end']-e['start'],-e['depth']))
        # A line-only focus that overlaps multiple same-line statements belongs
        # to their common parent; no invented column precision is claimed.
        ties=[e for e in containing if e['start']==best['start'] and e['end']==best['end'] and e['depth']==best['depth']]
        if len(ties)>1:
            common=None
            for e in ties:
                chain=set();current=e
                while current:chain.add(current['id']);current=current['parent']
                common=chain if common is None else common&chain
            best=max((e for e in self.entries if e['id'] in common),key=lambda e:e['depth'])
        result=[];current=best
        while current:result.append(current);current=current['parent']
        return list(reversed(result))

def build_source_plan(service,q,ctx):
    from .service import QueryError
    eid=q['entity_id'];g=ctx['g']
    if eid not in g.entities:raise QueryError('NOT_FOUND','Source entity unavailable')
    entity=g.entities[eid];source=ctx['sources'].get((entity.repo_id,entity.rel_path))
    if not source:raise QueryError('NOT_FOUND','Snapshot source bytes unavailable')
    raw=base64.b64decode(source['bytes_base64']);cache=ctx.setdefault('source_trees',{})
    key=(entity.repo_id,entity.rel_path,hashlib.sha256(raw).hexdigest())
    if key not in cache:
        try:cache[key]=SourceTree(raw,entity.rel_path,entity.repo_id)
        except (SyntaxError,ValueError,UnicodeError,tokenize.TokenError):
            plan=service._get_entity_content(q,ctx);plan.mandatory['source_context']=None
            plan.mandatory['coverage']['limitations'].append('Unsupported source tree: returned explicit source ranges only')
            return plan
        while len(cache)>8 or sum(t.source_bytes for t in cache.values())>8*1024*1024:
            cache.pop(next(iter(cache)))
    tree=cache[key];start=q['start_line'] or entity.start_line or 1;end=q['end_line'] or entity.end_line or len(tree.lines)
    if not 1<=start<=end<=len(tree.lines):raise QueryError('INVALID_REQUEST','Requested source range outside artifact')
    spine=tree.spine(start,end)
    # Entity content includes its declaration decorators when no explicit range
    # was requested. Every emitted segment still refers to original source lines.
    if q['start_line'] is None and entity.kind in {'function','method','class'}:
        entries=[e for e in tree.entries if e['node'] is not None and getattr(e['node'],'lineno',None)==entity.start_line and e['end']==end]
        if entries:start=min(start,entries[0]['start']);spine=tree.spine(start,end)
    def location(a,b):return dict(repo_id=entity.repo_id,revision=ctx['revmap'][entity.repo_id],rel_path=entity.rel_path,start_line=a,end_line=b)
    def segment(a,b):
        text=''.join(tree.lines[a-1:b]);return dict(source=location(a,b),text=text,sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),trust='untrusted_repository_content')
    headers=[];visible=set(range(start,end+1))
    for e in spine:
        if e['kind']=='module' or not e['start']<start:continue
        last=min(e['header_end'],start-1)
        if last>=e['start']:
            headers.append(segment(e['start'],last));visible.update(range(e['start'],last+1))
    omissions=[];i=1
    while i<=len(tree.lines):
        if i in visible:i+=1;continue
        a=i
        while i<=len(tree.lines) and i not in visible:i+=1
        handle=service._handle('source_range',dict(snapshot_id=q['snapshot_id'],entity_id=eid,start_line=a,end_line=i-1,content_kind='source'))
        omissions.append(dict(source=location(a,i-1),content_handle=handle,reason='folded'))
    data=service._payload(q['snapshot_id'],ctx,entity_id=eid,chunks=[],source_context=dict(enclosing_headers=headers,
        focal_segments=[segment(start,end)],focal_complete=True,sibling_stubs=[],omissions=omissions))
    data['nodes']=[service._node(ctx,eid)];units=[]
    if q['context_radius']==1:
        focus=spine[-1];siblings=focus['parent']['children'] if focus['parent'] else focus['children']
        for sibling in siblings:
            if sibling is focus or not (sibling['end']<start or sibling['start']>end):continue
            n=sibling['node'];sig=None;gist=None
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                sig=('async def ' if isinstance(n,ast.AsyncFunctionDef) else 'def ')+n.name+'('+ast.unparse(n.args)+')'
                if n.returns:sig+=' -> '+ast.unparse(n.returns)
                doc=ast.get_docstring(n,clean=False);gist=doc.splitlines()[0][:140] if doc else None
            elif isinstance(n,ast.ClassDef):sig='class '+n.name
            else:sig=''.join(tree.lines[sibling['start']-1:sibling['header_end']]).strip().splitlines()[0] if tree.lines else None
            owner_ids={e.entity_id for e in g.entities.values() if e.repo_id==entity.repo_id and e.rel_path==entity.rel_path and e.start_line==getattr(n,'lineno',-1)}
            calls=[];complete=bool(owner_ids)
            for r in g.relationships.values():
                if r.source_subject_id in owner_ids and r.subtype=='calls' and r.family=='static':
                    target=g.entities[r.target_subject_id];label=target.qualified_name+(' ['+r.resolution_status+']' if r.resolution_status!='exact' else '')
                    calls.append(label);complete&=r.resolution_status=='exact'
            calls=sorted(set(calls));complete&=len(calls)<=8
            handle=service._handle('source_range',dict(snapshot_id=q['snapshot_id'],entity_id=eid,start_line=sibling['start'],end_line=sibling['end'],content_kind='source'))
            stub=dict(source=location(sibling['start'],sibling['end']),signature=sig[:240] if sig else None,doc_gist=gist,
                      outgoing_call_names=calls[:8],calls_complete=complete,content_handle=handle)
            units.append(Unit('source-stub:'+sibling['id'],2,30,{'source_context.sibling_stubs':[stub]}))
    return service._plan('get_entity_content',q,data,units)
