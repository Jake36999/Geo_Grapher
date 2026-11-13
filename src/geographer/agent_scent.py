"""Bounded descriptions derived only from immutable snapshot source and reads."""
import base64
from collections import defaultdict
import hashlib
import io
import re
import tokenize


class SourceScent:
    def __init__(self, ctx):
        self.ctx=ctx;self.g=ctx['g'];self.lines={};self.docs=defaultdict(list)
        self.reads=defaultdict(list);self.constants=defaultdict(set);self.read_status={}
        for link in self.g.incidences:self.docs[link['entity_id']].append(link)
        for rel in self.g.relationships.values():
            if rel.family!='static' or rel.subtype!='reads' or rel.resolution_status not in {'exact','candidate'}:continue
            constant=self.g.entities.get(rel.target_subject_id)
            if not constant or constant.kind!='constant':continue
            self.constants[rel.source_subject_id].add(constant.entity_id)
            self.read_status[(rel.source_subject_id,constant.entity_id)]=rel.resolution_status
            for ev in ctx['evidence'].get(rel.relationship_id,[]):
                if ev.start_line and ev.rel_path:
                    self.reads[constant.entity_id].append((rel.source_subject_id,ev.repo_id,ev.rel_path,ev.start_line,rel.resolution_status))
        for eid, values in self.reads.items():self.reads[eid]=sorted(set(values),key=lambda x:(self.g.entities[x[0]].qualified_name,x[2],x[3]))

    def source(self, repo, path):
        key=(repo,path)
        if key not in self.lines:
            stored=self.ctx['sources'].get(key)
            if not stored:self.lines[key]=[]
            else:
                raw=base64.b64decode(stored['bytes_base64'])
                encoding,_=tokenize.detect_encoding(io.BytesIO(raw).readline)
                self.lines[key]=raw.decode(encoding).splitlines(keepends=True)
        return self.lines[key]

    def comment_start(self,e):
        lines=self.source(e.repo_id,e.rel_path);start=e.start_line
        if not lines or not start:return start or 1
        # A contiguous preceding block cannot absorb inline/unrelated comments.
        while start>1 and lines[start-2].lstrip().startswith('#'):start-=1
        return start

    def documentation(self,e):
        if e.kind=='constant':
            lines=self.source(e.repo_id,e.rel_path)
            return ' '.join(line.lstrip().removeprefix('#').strip() for line in lines[self.comment_start(e)-1:e.start_line-1])
        declaration=self.g.analyses.get('declaration:'+e.entity_id,{}).get('result',{})
        if declaration.get('docstring'):return declaration['docstring']
        parts=[]
        for link in self.docs[e.entity_id]:
            f=self.g.entities.get(link['fragment_id'])
            if f and f.parent_id==e.entity_id:
                parts.append(self.g.analyses.get('text:'+f.entity_id,{}).get('result',{}).get('text',''))
        return ' '.join(parts)

    def signature(self,e):
        lines=self.source(e.repo_id,e.rel_path)
        return lines[e.start_line-1].strip() if lines and e.start_line else ''

    def card(self,eid,query,previous,hit):
        e=self.g.entities[eid];docs=self.documentation(e)
        signature=(self.signature(e) if e.kind=='constant' else previous.get('signature')) or ''
        terms=re.findall(r'\w+',query.casefold())
        choices=[('comment' if e.kind=='constant' else 'docstring',docs),('signature',signature),('name',e.qualified_name),('path',e.rel_path or '')]
        # Only describe a field that actually contains a query term.
        field,text=next(((k,t) for k,t in choices if any(v in t.casefold() for v in terms)),('name',e.qualified_name))
        position=min((text.casefold().find(t) for t in terms if t in text.casefold()),default=0)
        snippet=' '.join(text[max(0,position-20):].split())[:90]
        gist=re.split(r'(?<=[.!?])\s',docs.strip(),maxsplit=1)[0][:65] or None
        card=dict(signature=signature[:80] or None,doc_gist=gist,why=(field+': '+snippet)[:100],trust='untrusted_repository_content')
        if e.kind=='constant':
            reads=self.reads[eid];readers=sorted(set((self.g.entities[x[0]].qualified_name,x[3]) for x in reads))
            card['used_by']=dict(count=len({x[0] for x in reads}),readers=[f'{name}:{line}' for name,line in readers[:2]],
                                 resolution='candidate' if any(x[4]=='candidate' for x in reads) else 'exact')
        # Approximately 300 source characters per hit, including reader descriptors.
        def size():return sum(len(str(card.get(k) or '')) for k in ('signature','doc_gist','why','used_by'))
        if 'used_by' in card:
            readers=card['used_by']['readers']
            for i,reader in enumerate(readers):
                if len(reader)>48:readers[i]='…'+reader[-47:]
        for key in ('doc_gist','why','signature'):
            if size()<=300:break
            text=card[key] or '';card[key]=text[:max(0,len(text)-(size()-300))] or None
        return card

    def context(self,eid):
        e=self.g.entities[eid]
        if e.kind!='constant':return None
        # At most 31 definition/comment lines plus three three-line use sites.
        start=max(self.comment_start(e),e.start_line-30)
        end=min(e.end_line,start+30)
        ranges=[(e.repo_id,e.rel_path,start,end,'definition','')];left=40-(end-start+1)
        for owner,repo,path,line,status in self.reads[eid]:
            if len(ranges)==4 or left<1:break
            lines=self.source(repo,path);a=max(1,line-1);b=min(len(lines),line+1,a+left-1)
            if any(repo==r[0] and path==r[1] and a<=r[3] and b>=r[2] for r in ranges):continue
            if b<a:continue
            ranges.append((repo,path,a,b,'usage',self.g.entities[owner].qualified_name,status));left-=b-a+1
        return ranges

    def chunk(self,eid,descriptor):
        repo,path,a,b,kind,owner=descriptor[:6]
        text=''.join(self.source(repo,path)[a-1:b])
        return dict(entity_id=eid,source=dict(repo_id=repo,revision=self.ctx['revmap'][repo],rel_path=path,start_line=a,end_line=b),
                    text=text,sha256=hashlib.sha256(text.encode()).hexdigest(),trust='untrusted_repository_content',
                    context_kind=kind,enclosing_function=owner,resolution_status=descriptor[6] if len(descriptor)>6 else 'definition')

    def calls_constants(self,eid):
        e=self.g.entities[eid]
        if e.kind not in {'function','method'} or (e.end_line or 0)-(e.start_line or 0)>=60:return []
        return [dict(entity_id=cid,qualified_name=self.g.entities[cid].qualified_name,signature=self.signature(self.g.entities[cid])[:80],
                     resolution_status=self.read_status[(eid,cid)],
                     trust='untrusted_repository_content') for cid in sorted(self.constants[eid])[:8]]


def scent(ctx):
    if 'agent_scent' not in ctx:ctx['agent_scent']=SourceScent(ctx)
    return ctx['agent_scent']
