"""Opt-in local embeddings over immutable source; no hosted encoder adapter."""
from __future__ import annotations
import ast
from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import math
import platform
from pathlib import Path
import re
import sqlite3
import time
from .model import canonical,digest
from .retrieval import terms

REPRESENTATION='entity-semantic-v1'
KINDS=frozenset({'constant','function','method','class'})
MAX_TEXT=8000
MAX_QUERY=10000


def validate_spec(spec):
    """Pure syntax validation before source access or optional imports."""
    if not isinstance(spec,str):raise ValueError('A local encoder specification is required')
    kind,_,value=spec.partition(':')
    if kind not in {'model2vec','fastembed'} or not value or '://' in value:
        raise ValueError('Only local model2vec/fastembed model directories are allowed')
    model,path=('',value) if kind=='model2vec' else value.partition('@')[::2]
    if kind=='fastembed' and (not path or not re.fullmatch(r'[\w.-]+/[\w.-]+',model)):
        raise ValueError('Use local fastembed:model-name@absolute-directory')
    if not Path(path).is_absolute():raise ValueError('Encoder requires an absolute local model directory')
    return kind,model,path


@dataclass(frozen=True)
class LocalEncoder:
    fingerprint: str
    encode: object
    metadata: dict


def load_encoder(spec):
    kind,model,path=validate_spec(spec)
    directory=Path(path)
    if not directory.is_dir():raise ValueError('Local model directory does not exist; provision weights explicitly')
    assets={str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.rglob('*'))
        if p.is_file() and '.cache' not in p.relative_to(directory).parts and p.suffix in {'.json','.safetensors','.onnx','.bin','.txt','.model'}}
    if not assets:raise ValueError('Local model directory has no model assets')
    versions={name:importlib.metadata.version(name) for name in ('numpy',kind,'tokenizers')}
    if kind=='fastembed':versions['onnxruntime']=importlib.metadata.version('onnxruntime')
    metadata=dict(kind=kind,model=model,assets=assets,versions=versions,python=platform.python_version(),machine=platform.machine(),max_tokens=512,normalization='l2-finite-zero-omit-v1',
        implementation=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if kind=='model2vec':
        from model2vec import StaticModel
        loaded=StaticModel.from_pretrained(directory,normalize=False)
        encode=lambda texts:loaded.encode(list(texts),max_length=512)
    else:
        from fastembed import TextEmbedding
        loaded=TextEmbedding(model_name=model,specific_model_path=str(directory),local_files_only=True,providers=['CPUExecutionProvider'])
        encode=lambda texts:list(loaded.embed(list(texts)))
    return LocalEncoder(digest(metadata),encode,metadata)


def descriptions_for(graph):
    from .agent_scent import SourceScent
    sources={(graph.entities[v['scope']['entity_id']].repo_id,v['result']['rel_path']):v['result'] for v in graph.analyses.values()
        if v['algorithm_version']=='source-bytes-v1' and v['scope'].get('entity_id') in graph.entities}
    return SourceScent(dict(g=graph,sources=sources,evidence={}))


def entity_text(graph,eid,descriptions=None):
    descriptions=descriptions or descriptions_for(graph)
    e=graph.entities[eid]
    if e.kind not in KINDS:raise ValueError('Semantic representation requires a code declaration')
    lines=descriptions.source(e.repo_id,e.rel_path)
    comment=''.join(lines[descriptions.comment_start(e)-1:(e.start_line or 1)-1])
    declaration=graph.analyses.get('declaration:'+eid,{}).get('result',{})
    literal=''
    if e.kind=='constant' and lines and e.start_line and e.end_line:
        try:
            tree=ast.parse(''.join(lines[e.start_line-1:e.end_line]))
            node=tree.body[0]
            if isinstance(node,(ast.Assign,ast.AnnAssign)) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):
                literal=node.value.value
        except (ValueError,SyntaxError,MemoryError,RecursionError):pass
    # Field caps are applied before canonical serialization and inference. No
    # imports, evaluation or source execution is necessary for string literals.
    fields=dict(version=REPRESENTATION,name=terms(e.qualified_name)[-600:],
        signature=(declaration.get('signature') or descriptions.signature(e))[:600],
        documentation=descriptions.documentation(e)[:2600],comments=comment[:1000],literal=literal[:2600],parent_path=(e.rel_path or '')[-300:])
    text=canonical(fields)
    truncated=len(text)>MAX_TEXT or len(literal)>2600 or len(comment)>1000 or len(descriptions.documentation(e))>2600
    text=text[:MAX_TEXT]
    return dict(text=text,sha256=hashlib.sha256(text.encode()).hexdigest(),truncated=truncated)


def representations(graph):
    descriptions=descriptions_for(graph)
    return {eid:entity_text(graph,eid,descriptions) for eid,e in sorted(graph.entities.items()) if e.kind in KINDS}


def normalized(vector,dimension=None):
    values=[float(x) for x in vector]
    if not values or dimension is not None and len(values)!=dimension or not all(math.isfinite(x) for x in values):
        raise ValueError('Semantic vectors must be finite and have one consistent dimension')
    norm=math.sqrt(math.fsum(x*x for x in values))
    if not math.isfinite(norm):raise ValueError('Semantic vector norm must be finite')
    return [x/norm for x in values] if norm else None


class SemanticCache:
    """One write-once population path; queries load a verified read-only copy."""
    @staticmethod
    def identity(graph,snapshot,encoder):
        texts=representations(graph)
        hashes={eid:row['sha256'] for eid,row in texts.items()}
        return texts,dict(snapshot=snapshot,encoder=encoder.fingerprint,representation=REPRESENTATION,texts=hashes)

    @classmethod
    def build(cls,path,graph,snapshot,encoder):
        started=time.perf_counter();path=Path(path)
        texts,identity=cls.identity(graph,snapshot,encoder);key=digest(identity)
        if path.exists():
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as c:
                exists=c.execute('SELECT 1 FROM namespaces WHERE namespace=?',(key,)).fetchone()
            if exists:
                cached=cls.load(path,graph,snapshot,encoder)
                return dict(entities=len(texts),encoded=0,zero_vectors=len(texts)-len(cached.vectors),seconds=time.perf_counter()-started,bytes=path.stat().st_size,namespace=key)
        rows=[];dimension=None;zero=0
        keys=list(texts)
        for start in range(0,len(keys),256):
            batch=keys[start:start+256]
            vectors=list(encoder.encode([texts[eid]['text'] for eid in batch]))
            if len(vectors)!=len(batch):raise ValueError('Encoder returned wrong vector batch size')
            for eid,raw in zip(batch,vectors):
                raw=list(raw)
                if dimension is None:dimension=len(raw)
                vector=normalized(raw,dimension)
                if vector is None:zero+=1
                rows.append((eid,texts[eid]['sha256'],canonical(vector)))
        metadata=dict(identity=identity,dimension=dimension,vector_digest=digest(rows),zero_vectors=zero,texts_truncated=sum(row['truncated'] for row in texts.values()))
        path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE IF NOT EXISTS namespaces(namespace TEXT PRIMARY KEY, metadata_json TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS embeddings(namespace TEXT NOT NULL,entity_id TEXT NOT NULL,text_hash TEXT NOT NULL,vector_json TEXT NOT NULL,PRIMARY KEY(namespace,entity_id))')
            c.execute('BEGIN IMMEDIATE')
            prior=c.execute('SELECT metadata_json FROM namespaces WHERE namespace=?',(key,)).fetchone()
            if prior:
                if prior[0]!=canonical(metadata):raise ValueError('Conflicting immutable semantic namespace')
            else:
                c.execute('INSERT INTO namespaces VALUES(?,?)',(key,canonical(metadata)))
                c.executemany('INSERT INTO embeddings VALUES(?,?,?,?)',[(key,*row) for row in rows])
        return dict(entities=len(texts),encoded=len(rows),zero_vectors=zero,seconds=time.perf_counter()-started,bytes=path.stat().st_size,namespace=key,texts_truncated=metadata['texts_truncated'])

    @classmethod
    def load(cls,path,graph,snapshot,encoder):
        texts,identity=cls.identity(graph,snapshot,encoder);key=digest(identity)
        with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as c:
            c.execute('PRAGMA query_only=ON')
            found=c.execute('SELECT metadata_json FROM namespaces WHERE namespace=?',(key,)).fetchone()
            if not found:raise ValueError('Semantic namespace missing: verify snapshot, model and representation membership')
            metadata=json.loads(found[0])
            rows=c.execute('SELECT entity_id,text_hash,vector_json FROM embeddings WHERE namespace=? ORDER BY entity_id',(key,)).fetchall()
        if metadata['identity']!=identity or {row[0]:row[1] for row in rows}!=identity['texts']:
            raise ValueError('Semantic representation membership mismatch')
        vectors={}
        for eid,_,raw in rows:
            value=json.loads(raw)
            if value is not None:
                vector=normalized(value,metadata['dimension'])
                if vector is None:raise ValueError('Corrupt zero semantic vector')
                vectors[eid]=vector
        if metadata['vector_digest']!=digest(rows):raise ValueError('Semantic vector digest mismatch')
        result=cls();result.graph=graph;result.encoder=encoder;result.vectors=vectors;result.metadata=metadata;result.namespace=key
        return result

    def search(self,query,kinds=(),limit=200):
        if not isinstance(query,str) or not query.strip() or len(query)>MAX_QUERY:raise ValueError('Semantic query must contain 1..10000 characters')
        if type(limit) is not int or not 1<=limit<=200:raise ValueError('Semantic candidate limit must be 1..200')
        raw=list(self.encoder.encode([query]))
        if len(raw)!=1:raise ValueError('Encoder returned wrong query batch size')
        vector=normalized(raw[0],self.metadata['dimension'])
        if vector is None:return []
        values=[]
        for eid,other in self.vectors.items():
            if kinds and self.graph.entities[eid].kind not in kinds:continue
            cosine=math.fsum(a*b for a,b in zip(vector,other))
            values.append(dict(node_id=eid,score=0.,semantic_score=cosine,matched_fields=['semantic'],fragment_ids=[]))
        return sorted(values,key=lambda row:(-row['semantic_score'],row['node_id']))[:limit]
