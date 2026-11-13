"""Deterministic bounded query fusion and source-derived search observations."""
from collections import Counter
import re
from .retrieval import QUERY_STOP_WORDS,terms

RRF_K=60
LOW_SCORE=.012
CONTENT_STOP=QUERY_STOP_WORDS|frozenset('cite source sources please identifier named define defines defined function constant implementation documented documentation code'.split())


def content_words(text):
    return {t for t in terms(text).split() if len(t)>2 and t not in CONTENT_STOP and not t.isdigit()}


def fuse(lists):
    if len(lists)==1:return lists[0]
    merged={}
    for hits in lists:
        seen=set()
        for rank,h in enumerate(hits,1):
            eid=h['node_id']
            if eid in seen:continue
            seen.add(eid)
            row=merged.setdefault(eid,dict(node_id=eid,score=0.,matched_fields=[],fragment_ids=[],formal_rank=None,informal_rank=None,exact=False))
            row['score']+=1/(RRF_K+rank)/len(lists)
            row['exact']|=h['score']==1.
            for field in ('matched_fields','fragment_ids'):row[field]=sorted(set(row[field])|set(h.get(field,[])))
            for field in ('formal_rank','informal_rank'):
                if h.get(field) is not None:row[field]=min(row[field],h[field]) if row[field] is not None else h[field]
    for row in merged.values():
        if row.pop('exact'):row['score']=1.
    return sorted(merged.values(),key=lambda h:(-h['score'],h['node_id']))


def queries(query,also=()):
    if not isinstance(query,str) or not query.strip():raise ValueError('query must be a nonempty string')
    if not isinstance(also,(list,tuple)) or len(also)>2 or any(not isinstance(x,str) or not x.strip() for x in also):
        raise ValueError('also accepts at most two nonempty query strings')
    return list(dict.fromkeys([query,*also]))


def rank_queries(index,texts,*,semantic=None,kinds=()):
    """The same bounded product ranking is used by the front door and replay."""
    lexical=[];vectors=[];channels=[]
    for text in texts:
        hits=index.search(text,kinds=kinds,limit=200)
        lexical.append(hits)
        if semantic is None:channels.append(hits)
        else:
            candidates=semantic.search(text,kinds=kinds,limit=200)
            vectors.append(candidates);channels.append(fuse([hits,candidates]))
    ranked=fuse(channels)
    if semantic is not None:
        lex_ids={h['node_id'] for hits in lexical for h in hits}
        sem_ids={h['node_id'] for hits in vectors for h in hits}
        for h in ranked:
            eid=h['node_id'];h['match']='both' if eid in lex_ids and eid in sem_ids else 'lexical' if eid in lex_ids else 'semantic'
    return dict(hits=ranked,lexical_hits=fuse(lexical),semantic_hits=fuse(vectors) if vectors else [],
        semantic_enabled=semantic is not None,query_count=len(texts))


def observation(hits,question,descriptions,*,query=None):
    words=content_words(question)
    top=hits[:3]
    overlaps=[]
    for h in hits[:8]:
        previous=descriptions.g.analyses.get('declaration:'+h['node_id'],{}).get('result',{})
        card=descriptions.card(h['node_id'],query if query is not None else question,previous,h)
        overlaps.append(len(words&content_words((card.get('doc_gist') or '')+' '+(card.get('why') or ''))))
    score=hits[0]['score'] if hits else 0.
    exact=score==1.
    low=not exact and (score<LOW_SCORE or not any(n>=2 for n in overlaps))
    result=dict(low_confidence=low,confidence=dict(algorithm='preview-confidence-v1',top_score=score,threshold=LOW_SCORE,max_doc_overlap=max(overlaps,default=0)))
    if low:
        ctx=descriptions.ctx
        if 'hint_term_frequency' not in ctx:
            frequency=Counter()
            for e in descriptions.g.entities.values():
                if e.kind not in {'constant','function','method','class'}:continue
                frequency.update(content_words(e.qualified_name+' '+descriptions.documentation(e)))
            ctx['hint_term_frequency']=frequency
        frequency=ctx['hint_term_frequency'];candidates=set()
        for h in top:
            e=descriptions.g.entities[h['node_id']]
            candidates|=content_words(e.qualified_name+' '+descriptions.documentation(e))
        informative=sorted(candidates-words,key=lambda term:(frequency[term],term))[:6]
        result['try']=[('Keep the question verbatim; add '+ ' '.join(informative[:3]))[:160],
            ('Try a documented name or phrase: '+' '.join(informative[3:] or informative[:3]))[:160]]
    return result
