"""Physical corpus union with remapped IDs and explicit, non-equivalent origins."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .stage3_build_db import DDL
from .corpus import DDL as READ_DDL, READ_MODEL_VERSION, _statements, refresh

SOURCE_TABLES=('documents','sections','claims','concepts','doc_concepts','section_concepts',
    'import_manifests','section_provenance','annotations','document_origins','concept_origins','annotation_origins')


def exists(conn, table):
    return bool(conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone())


def _identity(conn):
    model=conn.execute("SELECT value FROM corpus_metadata WHERE key='read_model_version'").fetchone()
    if not model or model[0]!=READ_MODEL_VERSION:raise ValueError(f'Paper {READ_MODEL_VERSION} read models are required; refresh the source corpus first')
    revision=conn.execute("SELECT value FROM corpus_metadata WHERE key='revision'").fetchone()
    if not revision:raise ValueError('Paper read models must be refreshed before merging')
    h=hashlib.sha256()
    for table in SOURCE_TABLES:
        if exists(conn,table):
            h.update(table.encode())
            for row in conn.execute('SELECT * FROM '+table+' ORDER BY 1,2'):
                h.update(json.dumps(list(row),ensure_ascii=False,separators=(',',':')).encode());h.update(b'\n')
    return dict(corpus_revision=revision[0],source_digest=h.hexdigest())


def source_identity(path):
    if not path.is_file():raise ValueError('Paper source missing')
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
        conn.execute('BEGIN')
        return _identity(conn)


def merge_corpora(sources, destination):
    """Copies original rows, manifests and archived annotations; rebuilds read/FTS
    tables. Concept homonyms and equal DOI/title works remain origin scoped.
    No new equivalence, embeddings or model assertions are manufactured.
    """
    identity=json.dumps([(s['graph_id'],s['paper_identity']) for s in sources],sort_keys=True)
    if destination.exists():
        with closing(sqlite3.connect(destination.resolve().as_uri()+'?mode=ro',uri=True)) as existing:
            row=existing.execute("SELECT value FROM corpus_metadata WHERE key='merge_sources'").fetchone()
            if row and row[0]==identity:return
        raise ValueError('Destination paper generation already exists with a different identity')
    fd,name=tempfile.mkstemp(prefix='papers-building-',suffix='.sqlite',dir=destination.parent);os.close(fd)
    policy={'version':'origin-scoped-union-v1','groups':[],'ranking_exclusions':[],'related_not_identical':[]}
    with closing(sqlite3.connect(name)) as out:
        out.row_factory=sqlite3.Row;out.executescript(DDL)
        for sql in _statements(READ_DDL):out.execute(sql)
        out.executescript('''
        CREATE TABLE document_origins(doc_id INTEGER PRIMARY KEY REFERENCES documents(id),source_graph TEXT NOT NULL,source_id INTEGER NOT NULL,original_path TEXT NOT NULL,source_revision TEXT NOT NULL);
        CREATE TABLE concept_origins(concept_id INTEGER PRIMARY KEY REFERENCES concepts(id),source_graph TEXT NOT NULL,source_id INTEGER NOT NULL,original_name TEXT NOT NULL,source_revision TEXT NOT NULL);
        CREATE TABLE annotation_origins(annotation_id INTEGER PRIMARY KEY REFERENCES annotations(id),source_graph TEXT NOT NULL,source_id INTEGER NOT NULL,source_digest TEXT NOT NULL);
        ''')
        maps={}
        def insert(table,row):
            columns=list(row)
            cur=out.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',tuple(row.values()))
            return cur.lastrowid
        for source in sources:
            gid=source['graph_id'];path=Path(source['paper_database'])
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as incoming:
                incoming.row_factory=sqlite3.Row;incoming.execute('BEGIN')
                if _identity(incoming)!=source['paper_identity']:raise ValueError('Paper source changed since merge review')
                revision=source['paper_identity']['corpus_revision']
                mapping={t:{} for t in ('documents','sections','claims','concepts')};maps[gid]=mapping
                for table in mapping:
                    for raw in incoming.execute('SELECT * FROM '+table+' ORDER BY id'):
                        row=dict(raw);old=row.pop('id')
                        if table=='documents':
                            original=row['file_path'];row['file_path']=gid+'::'+original
                        if table=='sections':row['doc_id']=mapping['documents'][row['doc_id']]
                        if table=='claims':row['section_id']=mapping['sections'][row['section_id']]
                        if table=='concepts':
                            original=row['canonical_name'];row['canonical_name']=gid+' / '+original
                            row['aliases']=json.dumps(sorted(set(json.loads(row['aliases'] or '[]')+[original])))
                            if row['def_doc_id'] is not None:row['def_doc_id']=mapping['documents'][row['def_doc_id']]
                        new=insert(table,row);mapping[table][old]=new
                        if table=='documents':
                            origin=incoming.execute('SELECT * FROM document_origins WHERE doc_id=?',(old,)).fetchone() if exists(incoming,'document_origins') else None
                            out.execute('INSERT INTO document_origins VALUES(?,?,?,?,?)',(new,origin['source_graph'] if origin else gid,origin['source_id'] if origin else old,origin['original_path'] if origin else original,origin['source_revision'] if origin else revision))
                        if table=='concepts':
                            origin=incoming.execute('SELECT * FROM concept_origins WHERE concept_id=?',(old,)).fetchone() if exists(incoming,'concept_origins') else None
                            out.execute('INSERT INTO concept_origins VALUES(?,?,?,?,?)',(new,origin['source_graph'] if origin else gid,origin['source_id'] if origin else old,origin['original_name'] if origin else original,origin['source_revision'] if origin else revision))
                for table,refs in (('doc_concepts',{'doc_id':'documents','concept_id':'concepts'}),('section_concepts',{'section_id':'sections','concept_id':'concepts'}),('import_manifests',{'doc_id':'documents'}),('section_provenance',{'section_id':'sections'})):
                    if exists(incoming,table):
                        for raw in incoming.execute('SELECT * FROM '+table):
                            row=dict(raw)
                            for key,target in refs.items():row[key]=mapping[target][row[key]]
                            insert(table,row)
                # Preserve reviewed equivalences only inside each source origin.
                canonical_names={}
                for canon in incoming.execute('SELECT id,canonical_name,quality FROM read_concepts ORDER BY id'):
                    members=incoming.execute('SELECT c.canonical_name FROM concepts c JOIN concept_members m ON m.concept_id=c.id WHERE m.canonical_id=? ORDER BY c.id',(canon['id'],)).fetchall()
                    names=[gid+' / '+r[0] for r in members]
                    if names:
                        canonical_name=gid+' / '+canon['canonical_name'];canonical_names[canon['id']]=canonical_name
                        policy['groups'].append(dict(canonical=canonical_name,aliases=names,basis='Preserved equivalence from '+gid+' at '+revision))
                        if canon['quality']!='content':policy['ranking_exclusions'].append(canonical_name)
                if exists(incoming,'read_concept_relations'):
                    for relation in incoming.execute('SELECT * FROM read_concept_relations ORDER BY source_id,target_id,relation'):
                        policy['related_not_identical'].append(dict(source=canonical_names[relation['source_id']],target=canonical_names[relation['target_id']],relation=relation['relation'],basis='Preserved from '+gid+': '+relation['basis']))
                if exists(incoming,'annotations'):
                    for raw in incoming.execute('SELECT * FROM annotations ORDER BY id'):
                        row=dict(raw);old=row.pop('id');old_digest=row['digest'];refs=json.loads(row['source_refs_json'])
                        for ref in refs:
                            ref['origin']=dict(graph_id=gid,id=ref['id'],source_document_id=ref.get('source_document_id'),corpus_revision=row['corpus_revision'])
                            table={'document':'documents','section':'sections','claim':'claims'}[ref['kind']]
                            ref['id']=mapping[table].get(ref['id'])
                            ref['source_document_id']=mapping['documents'].get(ref.get('source_document_id'))
                            # Archived source_record/hash deliberately remain original.
                        row['source_refs_json']=json.dumps(refs);row['digest']=hashlib.sha256((gid+old_digest).encode()).hexdigest()
                        new=insert('annotations',row)
                        out.execute('INSERT INTO annotation_origins VALUES(?,?,?,?)',(new,gid,old,old_digest))
        policy_path=Path(name+'.policy.json');policy_path.write_text(json.dumps(policy),encoding='utf-8')
        try:refresh(out,policy_path)
        finally:policy_path.unlink(missing_ok=True)
        out.execute('INSERT OR REPLACE INTO corpus_metadata VALUES(?,?)',('origin_alias_policy',json.dumps(policy)))
        out.execute('INSERT OR REPLACE INTO corpus_metadata VALUES(?,?)',('merge_sources',identity))
        if out.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Merged corpus foreign key violation')
        out.commit();out.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Merged corpus integrity check failed')
    os.replace(name,destination)
