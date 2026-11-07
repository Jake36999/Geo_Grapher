"""Offline, versioned concept vectors and review-only cosine candidates.

Vectors must be supplied by an operator. This module neither downloads models
nor calls providers, and a candidate never changes concept identity.
"""
import hashlib
import json
import math


def import_vectors(conn, *, model, model_revision, records):
    if not model.strip() or not model_revision.strip():raise ValueError('Pinned model and revision required')
    if not isinstance(records,list) or not 1<=len(records)<=10000:raise ValueError('1..10000 vectors required')
    prepared=[];dimension=None;seen=set()
    for record in records:
        cid=record['concept_id'];vector=record['vector']
        if type(cid) is not int or cid in seen:raise ValueError('Unique integer concept IDs required')
        seen.add(cid)
        row=conn.execute('SELECT canonical_name FROM read_concepts WHERE id=?',(cid,)).fetchone()
        if not row:raise ValueError('Unknown concept')
        text=row[0]
        if record.get('input_text')!=text:raise ValueError('Vector input must exactly match current canonical name')
        if not isinstance(vector,list) or not 1<=len(vector)<=8192 or any(type(x) not in (int,float) or not math.isfinite(x) for x in vector):raise ValueError('Invalid finite vector')
        if dimension is None:dimension=len(vector)
        if len(vector)!=dimension:raise ValueError('Inconsistent vector dimensions')
        length=math.sqrt(sum(x*x for x in vector))
        if not math.isfinite(length) or length==0:raise ValueError('Invalid vector norm')
        digest=hashlib.sha256(text.encode()).hexdigest()
        prepared.append((model,model_revision,cid,digest,len(vector),json.dumps([x/length for x in vector])))
    with conn:
        conn.execute('CREATE TABLE IF NOT EXISTS concept_vectors(model TEXT NOT NULL,model_revision TEXT NOT NULL,concept_id INTEGER NOT NULL,input_sha256 TEXT NOT NULL,dimensions INTEGER NOT NULL,vector_json TEXT NOT NULL CHECK(json_valid(vector_json)),PRIMARY KEY(model,model_revision,concept_id))')
        existing=conn.execute('SELECT DISTINCT dimensions FROM concept_vectors WHERE model=? AND model_revision=?',(model,model_revision)).fetchall()
        if existing and any(r[0]!=dimension for r in existing):raise ValueError('Pinned model dimensions changed')
        conn.executemany('INSERT OR REPLACE INTO concept_vectors VALUES(?,?,?,?,?,?)',prepared)
    return len(prepared)


def propose(conn, *, model, model_revision, threshold=0.9, limit=50):
    if not 0<=threshold<=1 or type(limit) is not int or not 1<=limit<=200:raise ValueError('Invalid candidate bounds')
    rows=conn.execute('SELECT v.concept_id,c.canonical_name,v.input_sha256,v.vector_json FROM concept_vectors v JOIN read_concepts c ON c.id=v.concept_id WHERE model=? AND model_revision=? ORDER BY v.concept_id',(model,model_revision)).fetchall()
    if len(rows)>2000:raise ValueError('Offline pair scan limited to 2000 concepts; use ANN candidate import for larger corpora')
    current=[(r[0],r[1],json.loads(r[3])) for r in rows if hashlib.sha256(r[1].encode()).hexdigest()==r[2]]
    pairs=[]
    for i,a in enumerate(current):
        for b in current[i+1:]:
            if len(a[2])!=len(b[2]):raise ValueError('Incompatible model vectors')
            score=sum(x*y for x,y in zip(a[2],b[2]))
            if score>=threshold:pairs.append(dict(left_id=a[0],left=a[1],right_id=b[0],right=b[1],cosine=round(score,6),review_status='unreviewed_candidate_not_equivalence'))
    pairs.sort(key=lambda p:(-p['cosine'],p['left_id'],p['right_id']))
    return dict(model=model,model_revision=model_revision,eligible_vectors=len(current),stale_vectors=len(rows)-len(current),pairs=pairs[:limit],truncated=len(pairs)>limit)
