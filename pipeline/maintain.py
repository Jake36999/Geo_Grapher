"""Offline corpus maintenance. Never invokes models or modifies raw research rows."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
try:
    from .artifacts import WORK_DIR,write_json
    from .corpus import refresh,stats
except ImportError:
    from artifacts import WORK_DIR,write_json
    from corpus import refresh,stats


def connect(path):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    conn=sqlite3.connect(path);conn.execute('PRAGMA foreign_keys=ON')
    return conn


def backup(conn,path):
    path=Path(path)
    if path.exists():raise ValueError('Backup destination already exists')
    path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as target:conn.backup(target)


def annotate(conn,*,kind,text,source_refs,expected_revision,author):
    """Explicit opt-in write: immutable, unreviewed documentary assertion."""
    if kind not in {'note','synthesis','contradiction'}:raise ValueError('Unknown annotation kind')
    if not text.strip() or len(text)>8000:raise ValueError('Annotation must contain 1..8000 characters')
    if not author.strip() or len(author)>120:raise ValueError('Author required, max 120 characters')
    if not isinstance(source_refs,list) or not 1<=len(source_refs)<=20:raise ValueError('1..20 source references required')
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        revision=conn.execute("SELECT value FROM corpus_metadata WHERE key='revision'").fetchone()[0]
        if revision!=expected_revision:raise ValueError('Stale corpus revision')
        tables={'document':'documents','section':'sections','claim':'claims'}
        grounded=[]
        for ref in source_refs:
            if not isinstance(ref,dict) or set(ref)!={'kind','id'} or ref['kind'] not in tables or type(ref['id']) is not int:raise ValueError('Invalid source reference')
            row=conn.execute('SELECT * FROM '+tables[ref['kind']]+' WHERE id=?',(ref['id'],)).fetchone()
            if not row:raise ValueError('Unknown source reference')
            # Archive the referenced row so future re-imports cannot silently
            # repoint an old conclusion at a different section/claim.
            columns=[d[0] for d in conn.execute('SELECT * FROM '+tables[ref['kind']]+' LIMIT 0').description]
            source=dict(zip(columns,row));encoded=json.dumps(source,sort_keys=True)
            if ref['kind']=='document':source_doc_id=ref['id']
            elif ref['kind']=='section':source_doc_id=source['doc_id']
            else:source_doc_id=conn.execute('SELECT doc_id FROM sections WHERE id=?',(source['section_id'],)).fetchone()[0]
            grounded.append(dict(ref,source_document_id=source_doc_id,source_record=source,source_sha256=hashlib.sha256(encoded.encode()).hexdigest()))
        refs=json.dumps(grounded,sort_keys=True)
        digest=hashlib.sha256(json.dumps([kind,text,refs,revision,author]).encode()).hexdigest()
        conn.execute('INSERT OR IGNORE INTO annotations(created_at,kind,text,source_refs_json,corpus_revision,author,digest) VALUES(?,?,?,?,?,?,?)',
            (datetime.now(timezone.utc).isoformat(),kind,text,refs,revision,author,digest))
        return dict(id=conn.execute('SELECT id FROM annotations WHERE digest=?',(digest,)).fetchone()[0],review_status='unreviewed',corpus_revision=revision)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db',type=Path,default=WORK_DIR/'doc_graph.db')
    sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('refresh');p.add_argument('--backup',type=Path,required=True);p.add_argument('--report',type=Path);p.add_argument('--alias-policy',type=Path,help='Graph-local reviewed alias policy; defaults to the reusable template')
    sub.add_parser('stats')
    p=sub.add_parser('annotate');p.add_argument('file',type=Path,help='JSON: kind,text,source_refs,expected_revision,author')
    p=sub.add_parser('pack');p.add_argument('query');p.add_argument('--limit',type=int,default=3)
    p=sub.add_parser('import-vectors');p.add_argument('file',type=Path,help='JSON: model,model_revision,records[{concept_id,input_text,vector}]')
    p=sub.add_parser('candidates');p.add_argument('--model',required=True);p.add_argument('--model-revision',required=True);p.add_argument('--threshold',type=float,default=.9);p.add_argument('--limit',type=int,default=50)
    args=ap.parse_args()
    with connect(args.db) as conn:
        if args.command=='refresh':
            backup(conn,args.backup)
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                before={t:conn.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('documents','sections','claims','concepts','doc_concepts','section_concepts')}
                result=refresh(conn,args.alias_policy) if args.alias_policy else refresh(conn)
                after={t:conn.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in before}
                if before!=after or conn.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Publication validation failed')
            result.update(raw_counts_unchanged=True,raw_counts=before,backup=str(args.backup.resolve()))
            if args.report:write_json(args.report,result)
        elif args.command=='stats':result=stats(conn)
        elif args.command=='annotate':result=annotate(conn,**json.loads(args.file.read_text(encoding='utf-8')))
        elif args.command=='import-vectors':
            from .embedding_candidates import import_vectors
            result=dict(imported=import_vectors(conn,**json.loads(args.file.read_text(encoding='utf-8'))))
        elif args.command=='candidates':
            from .embedding_candidates import propose
            result=propose(conn,model=args.model,model_revision=args.model_revision,threshold=args.threshold,limit=args.limit)
        else:
            from . import mcp_doc_graph as service
            from .query_context import API_VERSION,BUILD_ID
            service.DB_PATH=args.db
            conn.execute('BEGIN IMMEDIATE')
            revision=conn.execute("SELECT value FROM corpus_metadata WHERE key='revision'").fetchone()[0]
            key=hashlib.sha256(json.dumps([API_VERSION,BUILD_ID,args.query,args.limit]).encode()).hexdigest()
            cached=conn.execute('SELECT payload_json FROM topic_packs WHERE cache_key=? AND corpus_revision=?',(key,revision)).fetchone()
            result=json.loads(cached[0]) if cached else service._TOOLS['search_documents'](args.query,limit=args.limit)
            if 'error' in result:raise ValueError(result['error'])
            if not cached:conn.execute('INSERT OR REPLACE INTO topic_packs VALUES(?,?,?)',(key,revision,json.dumps(result)))
            result=dict(cache_key=key,corpus_revision=revision,cache_hit=bool(cached),payload=result)
    print(json.dumps(result,indent=2,ensure_ascii=True))


if __name__=='__main__':main()
