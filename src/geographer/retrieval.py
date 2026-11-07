"""Local lexical/documentary ranking and bounded typed subject-graph witnesses."""
from __future__ import annotations
import re,sqlite3,unicodedata
from collections import defaultdict,deque
from .analysis import selected_relationships,eligible_entity

def terms(text):
    original=unicodedata.normalize('NFC',text)
    split=re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|[_./]+',' ',original)
    return ' '.join(dict.fromkeys(re.findall(r'\w+',original.casefold())+re.findall(r'\w+',split.casefold())))

class LexicalIndex:
    version='lexical-fusion-v1'
    def __init__(self,graph):
        self.graph=graph;self.db=sqlite3.connect(':memory:',check_same_thread=False);self.available=True
        self.fragments={};self.associations=defaultdict(list)
        for row in graph.incidences:self.associations[row['fragment_id']].append(row['entity_id'])
        headings={}
        for value in graph.analyses.values():
            if value['algorithm_version']=='documentary-tree-v1':
                sections={s['section_id']:s for s in value['result']['sections']}
                for section in sections.values():
                    titles=[];current=section;seen=set()
                    while current and current['section_id'] not in seen:
                        seen.add(current['section_id']);titles.append(current['heading']);current=sections.get(current['parent_section_id'])
                    for fid in section['fragment_ids']:headings[fid]=' '.join(reversed(titles))
        for e in graph.entities.values():
            if e.kind=='fragment':
                value=graph.analyses.get('text:'+e.entity_id,{}).get('result',{})
                self.fragments[e.entity_id]=value
        try:
            self.db.execute('CREATE VIRTUAL TABLE formal USING fts5(entity_id UNINDEXED,name,path,signature)')
            self.db.execute('CREATE VIRTUAL TABLE informal USING fts5(fragment_id UNINDEXED,text,heading)')
            with self.db:
                self.db.executemany('INSERT INTO formal VALUES(?,?,?,?)',((e.entity_id,terms(e.qualified_name),terms(e.rel_path or ''),
                    terms(graph.analyses.get('declaration:'+e.entity_id,{}).get('result',{}).get('signature') or '')) for e in graph.entities.values() if e.sort!='text'))
                self.db.executemany('INSERT INTO informal VALUES(?,?,?)',((fid,terms(v.get('text','')),terms(headings.get(fid,''))) for fid,v in self.fragments.items()))
        except sqlite3.OperationalError as exc:
            self.db.close()
            if 'no such module' not in str(exc).lower() or 'fts5' not in str(exc).lower():raise
            self.available=False

    def close(self):
        if self.available:self.db.close()

    def search(self,query,repo_ids=(),kinds=(),*,mode='hybrid',gamma=.8,k=60,limit=200):
        if not 0<=gamma<=1 or k<=0:raise ValueError('Invalid fusion configuration')
        def eligible(eid):
            e=self.graph.entities[eid];return (not repo_ids or e.repo_id in repo_ids) and (not kinds or e.kind in kinds)
        exact=sorted(e.entity_id for e in self.graph.entities.values() if eligible(e.entity_id) and (query==e.entity_id or query==e.qualified_name))
        if not self.available:
            if not exact:raise ValueError('FTS5 unavailable; exact symbol lookup remains supported')
            return [dict(node_id=eid,score=1.,matched_fields=['qualified_name'],formal_rank=1,informal_rank=None,fragment_ids=[]) for eid in exact[:limit]]
        tokens=terms(query).split()
        if not tokens:raise ValueError('Search requires at least one term')
        if len(tokens)>64:raise ValueError('At most 64 distinct lexical terms are supported')
        match=' OR '.join('"'+t.replace('"','""')+'"' for t in tokens)
        formal={};informal={};support=defaultdict(list)
        # Explicit candidate bound; no hidden unbounded scan/learned retrieval.
        if mode!='documentation':
            rows=self.db.execute('SELECT entity_id FROM formal WHERE formal MATCH ? ORDER BY bm25(formal),entity_id LIMIT 2000',(match,))
            for (eid,) in rows:
                if eligible(eid):formal[eid]=len(formal)+1
        if mode!='lexical':
            rows=self.db.execute('SELECT fragment_id FROM informal WHERE informal MATCH ? ORDER BY bm25(informal),fragment_id LIMIT 2000',(match,))
            for rank,(fid,) in enumerate(rows,1):
                targets=[eid for eid in self.associations[fid] if self.graph.entities[eid].sort!='text' and eligible(eid)]
                if not targets and eligible(fid):targets=[fid]
                for eid in targets:
                    informal.setdefault(eid,rank)
                    if fid not in support[eid] and len(support[eid])<3:support[eid].append(fid)
        hits=[]
        for eid in set(exact)|set(formal)|set(informal):
            f=formal.get(eid);i=informal.get(eid)
            score=1. if eid in exact else (gamma/(k+f) if f else 0)+( (1-gamma)/(k+i) if i else 0)
            entity=self.graph.entities[eid];fields=[]
            if eid in exact or set(tokens)&set(terms(entity.qualified_name).split()):fields.append('qualified_name')
            if f and set(tokens)&set(terms(entity.rel_path or '').split()):fields.append('rel_path')
            signature=self.graph.analyses.get('declaration:'+eid,{}).get('result',{}).get('signature') or ''
            if f and set(tokens)&set(terms(signature).split()):fields.append('signature')
            if i:fields.append('doc_text')
            hits.append(dict(node_id=eid,score=score,matched_fields=fields,
                formal_rank=f,informal_rank=i,fragment_ids=support[eid]))
        return sorted(hits,key=lambda h:(-h['score'],h['node_id']))[:limit]


class TypedBridge:
    version='typed-bridge-v1'
    templates={'CALL_CHAIN_WITH_HELPERS':{'calls'},'INHERITANCE_AND_OVERRIDES':{'inherits'},
               'BOUNDARY_CROSSING_WITNESSES':{'calls','imports','imports_from','inherits'}}
    def __init__(self,graph,filters):
        self.graph=graph;self.adj=defaultdict(list)
        self.filters=filters;self.children=defaultdict(list)
        for e in graph.entities.values():self.children[e.parent_id].append(e.entity_id)
        for r in selected_relationships(graph,filters):
            if r.direction!='directed' or r.family not in {'static','runtime'}:continue
            self.adj[r.source_subject_id].append((r.target_subject_id,r,False))
        for items in self.adj.values():items.sort(key=lambda x:(x[0],x[1].relationship_id))

    def find(self,source,target,template='CALL_CHAIN_WITH_HELPERS',*,max_hops=4,max_expansions=20000,max_anchor_subjects=200,undirected=False,mapping=None,cancelled=lambda:False):
        if template not in self.templates or not 0<=max_hops<=64 or not 1<=max_expansions<=200000:raise ValueError('Invalid typed path bounds/template')
        boundary=template=='BOUNDARY_CROSSING_WITNESSES'
        if boundary and mapping is None:raise ValueError('Boundary template requires an explicit component mapping')
        if not 1<=max_anchor_subjects<=2000:raise ValueError('Invalid anchor expansion bound')
        result=dict(source=source,target=target,resolved_source=None,resolved_target=None,anchors_complete=True,
                    anchor_counts=dict(source_total=0,target_total=0,source_searched=0,target_searched=0),steps=[],outcome='no_path_within_scope',visited_states=0)
        if source not in self.graph.entities or target not in self.graph.entities:return {**result,'outcome':'unavailable_anchor'}
        def anchors(eid):
            e=self.graph.entities[eid]
            expand=e.kind in {'workspace','repository','directory','package','file'} or e.kind=='class' and template!='INHERITANCE_AND_OVERRIDES'
            candidates=[];stack=[eid]
            while stack:
                current=stack.pop();entity=self.graph.entities[current]
                if entity.kind in {'file','class','function','method','external_symbol'} and eligible_entity(entity,self.filters):candidates.append(current)
                if expand:stack.extend(self.children.get(current,()))
            return sorted(candidates)
        sources=anchors(source);targets=anchors(target)
        result['anchor_counts']=dict(source_total=len(sources),target_total=len(targets),source_searched=min(len(sources),max_anchor_subjects),target_searched=min(len(targets),max_anchor_subjects))
        result['anchors_complete']=len(sources)<=max_anchor_subjects and len(targets)<=max_anchor_subjects
        if not sources or not targets:return {**result,'outcome':'unavailable_anchor'}
        sources=sources[:max_anchor_subjects];targets=set(targets[:max_anchor_subjects])
        adj=self.adj
        if undirected:
            adj=defaultdict(list,{v:list(edges) for v,edges in self.adj.items()})
            for u,edges in self.adj.items():
                for v,r,_ in edges:adj[v].append((u,r,True))
            for edges in adj.values():edges.sort(key=lambda x:(x[0],x[1].relationship_id,x[2]))
        queue=deque((s,s,False,0,[]) for s in sources);seen={(s,False,0) for s in sources};at_limit=False
        while queue:
            if cancelled():return {**result,'outcome':'cancelled'}
            if result['visited_states']>=max_expansions:return {**result,'outcome':'search_limit_reached'}
            u,start,crossed,depth,path=queue.popleft();result['visited_states']+=1
            if u in targets and depth>0 and (crossed or not boundary):return {**result,'steps':path,'outcome':'found','resolved_source':start,'resolved_target':u}
            for v,r,reverse in adj.get(u,()):
                if r.subtype not in self.templates[template]:continue
                if depth>=max_hops:at_limit=True;continue
                known_u=mapping.get(u) if mapping else None;known_v=mapping.get(v) if mapping else None
                crosses=crossed or bool(known_u and known_v and known_u!='Unmapped' and known_v!='Unmapped' and known_u!=known_v)
                state=(v,crosses,depth+1)
                if state in seen:continue
                if len(seen)>=max_expansions:return {**result,'outcome':'search_limit_reached'}
                seen.add(state);queue.append((v,start,crosses,depth+1,path+[dict(relationship_id=r.relationship_id,traversal_reversed=reverse)]))
        return {**result,'outcome':'search_limit_reached' if not result['anchors_complete'] else 'hop_limit_reached' if at_limit else 'no_path_within_scope'}
