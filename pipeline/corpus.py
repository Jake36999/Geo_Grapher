"""Auditable read models over preserved paper sources. No network/model calls."""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
import re
import sqlite3
from pathlib import Path
try:from .artifacts import authors_list
except ImportError:from artifacts import authors_list

ALIAS_FILE=Path(__file__).with_name('concept_aliases.json')
READ_MODEL_VERSION='paper-read-v4'
DDL='''
CREATE TABLE IF NOT EXISTS corpus_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS document_members(doc_id INTEGER PRIMARY KEY REFERENCES documents(id),canonical_id INTEGER NOT NULL REFERENCES documents(id),basis TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS document_quality(doc_id INTEGER PRIMARY KEY REFERENCES documents(id),status TEXT NOT NULL,reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claim_quality(claim_id INTEGER PRIMARY KEY REFERENCES claims(id) ON DELETE CASCADE,status TEXT NOT NULL,clean_text TEXT NOT NULL,reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS section_quality(section_id INTEGER PRIMARY KEY REFERENCES sections(id) ON DELETE CASCADE,status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS concept_members(concept_id INTEGER PRIMARY KEY REFERENCES concepts(id),canonical_id INTEGER NOT NULL REFERENCES concepts(id),basis TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS read_documents(id INTEGER PRIMARY KEY,title TEXT,authors TEXT,year INTEGER,venue TEXT,doi TEXT,abstract_summary TEXT,page_count INTEGER,file_path TEXT,primary_source_id INTEGER,source_count INTEGER,claim_count INTEGER,metadata_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS read_concepts(id INTEGER PRIMARY KEY,canonical_name TEXT,aliases TEXT,definition TEXT,concept_type TEXT,def_doc_id INTEGER,quality TEXT,original_ids_json TEXT);
CREATE TABLE IF NOT EXISTS read_claims(id INTEGER PRIMARY KEY,section_id INTEGER,text TEXT,claim_type TEXT,doc_id INTEGER,source_ids_json TEXT);
CREATE TABLE IF NOT EXISTS read_concept_relations(source_id INTEGER NOT NULL,target_id INTEGER NOT NULL,relation TEXT NOT NULL,basis TEXT NOT NULL,PRIMARY KEY(source_id,target_id,relation));
CREATE INDEX IF NOT EXISTS idx_read_claim_doc ON read_claims(doc_id);
CREATE TABLE IF NOT EXISTS topic_packs(cache_key TEXT PRIMARY KEY,corpus_revision TEXT NOT NULL,payload_json TEXT NOT NULL CHECK(json_valid(payload_json)));
CREATE TABLE IF NOT EXISTS annotations(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('note','synthesis','contradiction')),text TEXT NOT NULL,source_refs_json TEXT NOT NULL CHECK(json_valid(source_refs_json)),corpus_revision TEXT NOT NULL,author TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'unreviewed',digest TEXT UNIQUE NOT NULL);
CREATE TRIGGER IF NOT EXISTS annotations_no_update BEFORE UPDATE ON annotations BEGIN SELECT RAISE(ABORT,'Annotations are append-only'); END;
CREATE TRIGGER IF NOT EXISTS annotations_no_delete BEFORE DELETE ON annotations BEGIN SELECT RAISE(ABORT,'Annotations are append-only'); END;
'''


def _statements(ddl):
    # Complete statements, including trigger bodies; executescript would commit
    # an existing writer transaction and break atomic source/read-side updates.
    current=''
    for line in ddl.splitlines(keepends=True):
        current+=line
        if sqlite3.complete_statement(current):
            yield current;current=''
    if current.strip():raise ValueError('Incomplete corpus DDL')


def norm(value):return ' '.join(re.findall(r'\w+',str(value or '').casefold()))


def validate_policy(policy):
    """Reject ambiguous equivalence declarations before rebuilding any tables."""
    if not isinstance(policy,dict) or not isinstance(policy.get('version'),str):raise ValueError('Alias policy version required')
    if not isinstance(policy.get('groups'),list):raise ValueError('Alias groups must be a list')
    owners={}
    for group in policy['groups']:
        if not isinstance(group,dict) or not isinstance(group.get('canonical'),str) or not norm(group['canonical']):raise ValueError('Canonical concept name required')
        if not isinstance(group.get('aliases'),list) or not isinstance(group.get('basis'),str) or not group['basis'].strip():raise ValueError('Aliases and review basis required')
        owner=norm(group['canonical'])
        for name in [group['canonical'],*group['aliases']]:
            if not isinstance(name,str) or not norm(name):raise ValueError('Nonempty concept aliases required')
            key=norm(name)
            if key in owners and owners[key]!=owner:raise ValueError('Alias belongs to conflicting canonical groups: '+name)
            owners[key]=owner
    for relation in policy.get('related_not_identical',[]):
        if relation.get('relation') not in {'variant_of','specialization_of','related_to'}:raise ValueError('Unknown concept relation type')
        source=norm(relation.get('source'));target=norm(relation.get('target'))
        if not source or not target or not isinstance(relation.get('basis'),str) or not relation['basis'].strip():raise ValueError('Relation endpoints and basis required')
        if owners.get(source,source)==owners.get(target,target):raise ValueError('Nonidentity relation conflicts with alias equivalence')
    if not isinstance(policy.get('ranking_exclusions'),list) or any(not isinstance(n,str) or not norm(n) for n in policy['ranking_exclusions']):raise ValueError('Invalid ranking exclusions')


def identifier(value):
    value=str(value or '').strip().casefold()
    for prefix in ('https://doi.org/','http://doi.org/','doi:'):
        if value.startswith(prefix):value=value[len(prefix):]
    return value


def cleaned_claim(text):
    text=str(text or '').strip()
    if not text or re.fullmatch(r'<[^>]*\bunread\b[^>]*>',text,re.I|re.S):return '', 'placeholder'
    if text.casefold() in {'evidence the authors report:','evidence the authors report','method:','claim:'}:return '', 'template_header'
    cleaned=re.sub(r'^Evidence the authors report:\s*','',text,flags=re.I)
    return cleaned,'label_prefix_removed' if cleaned!=text else 'content'


def _union(parents,a,b):
    a=_root(parents,a);b=_root(parents,b)
    parents[max(a,b)]=min(a,b)


def _root(parents,x):
    while parents[x]!=x:parents[x]=parents[parents[x]];x=parents[x]
    return x


def _revision(conn,docs,sections,claims,concepts,policy):
    fingerprint=[READ_MODEL_VERSION,docs,sections,claims,concepts,policy,
        list(map(tuple,conn.execute('SELECT * FROM doc_concepts ORDER BY doc_id,concept_id,edge_type'))),
        list(map(tuple,conn.execute('SELECT * FROM section_concepts ORDER BY section_id,concept_id')))]
    for table in ('import_manifests','section_provenance','document_origins','concept_origins'):
        if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():
            fingerprint.append(list(map(tuple,conn.execute('SELECT * FROM '+table+' ORDER BY 1'))))
    return hashlib.sha256(json.dumps(fingerprint,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def refresh(conn,alias_file=ALIAS_FILE):
    conn.execute('SAVEPOINT corpus_refresh')
    try:
        result=_refresh(conn,alias_file)
        conn.execute('RELEASE corpus_refresh')
        return result
    except BaseException:
        conn.execute('ROLLBACK TO corpus_refresh');conn.execute('RELEASE corpus_refresh');raise


def _refresh(conn,alias_file=ALIAS_FILE):
    """Writer-owned transaction/savepoint; preserves all raw source rows.

    Rebuilds deterministic read tables/FTS once per import batch. This is not an
    LLM re-extraction or a sublinear update algorithm. Query-time work stays small.
    """
    for sql in _statements(DDL):conn.execute(sql)
    previous=conn.row_factory;conn.row_factory=sqlite3.Row
    try:
        docs=[dict(r) for r in conn.execute('SELECT * FROM documents ORDER BY id')]
        sections=[dict(r) for r in conn.execute('SELECT * FROM sections ORDER BY id')]
        claims=[dict(r) for r in conn.execute('SELECT * FROM claims ORDER BY id')]
        concepts=[dict(r) for r in conn.execute('SELECT * FROM concepts ORDER BY id')]
        saved=conn.execute("SELECT value FROM corpus_metadata WHERE key='origin_alias_policy'").fetchone()
        policy=json.loads(saved[0]) if saved and Path(alias_file)==ALIAS_FILE else json.loads(Path(alias_file).read_text(encoding='utf-8'))
        validate_policy(policy)
        revision=_revision(conn,docs,sections,claims,concepts,policy)
        previous_revision=conn.execute("SELECT value FROM corpus_metadata WHERE key='revision'").fetchone()
        previous_model=conn.execute("SELECT value FROM corpus_metadata WHERE key='read_model_version'").fetchone()
        incidence=conn.execute("SELECT type FROM sqlite_master WHERE name='read_doc_concepts'").fetchone()
        if previous_revision and previous_revision[0]==revision and previous_model and previous_model[0]==READ_MODEL_VERSION and incidence and incidence[0]=='table':
            return dict(stats(conn),refresh_mode='unchanged')
        for table in ('document_members','document_quality','claim_quality','section_quality','concept_members','read_documents','read_concept_relations','read_concepts','read_claims'):
            conn.execute('DELETE FROM '+table)
        by_doc=defaultdict(list)
        for s in sections:by_doc[s['doc_id']].append(s)
        section_sources={s['id']:s['doc_id'] for s in sections}
        section_ok={s['id']:bool(str(s['text'] or '').strip() and not re.fullmatch(r'<[^>]*unread[^>]*>',str(s['text']).strip(),re.I|re.S)) for s in sections}
        active={d['id'] for d in docs if any(section_ok[s['id']] for s in by_doc[d['id']])}
        for d in docs:
            conn.execute('INSERT INTO document_quality VALUES(?,?,?)',(d['id'],'active' if d['id'] in active else 'quarantined',
                'source content present' if d['id'] in active else ('Only empty/unread placeholder sections' if by_doc[d['id']] else 'No extracted sections; skipped/incomplete source, not a complete indexed paper')))
        origins={r[0]:r[1] for r in conn.execute('SELECT doc_id,source_graph FROM document_origins')} if conn.execute("SELECT 1 FROM sqlite_master WHERE name='document_origins'").fetchone() else {}
        parents={d['id']:d['id'] for d in docs};titles=defaultdict(list);ids={}
        for d in docs:
            if d['id'] not in active:continue
            title=norm(d['title']);doi=identifier(d['doi'])
            if doi:
                other=ids.get((origins.get(d['id']),doi))
                if other and (title==norm(other['title']) or {norm(a) for a in authors_list(d['authors'])} & {norm(a) for a in authors_list(other['authors'])}):
                    _union(parents,d['id'],other['id'])
                ids[(origins.get(d['id']),doi)]=d
            if len(title)<20:continue
            authors={norm(a) for a in authors_list(d['authors'])}
            for other in titles[(origins.get(d['id']),title)]:
                if doi and identifier(other['doi']) and doi!=identifier(other['doi']):continue
                if authors & {norm(a) for a in authors_list(other['authors'])}:_union(parents,d['id'],other['id'])
            titles[(origins.get(d['id']),title)].append(d)
        groups=defaultdict(list)
        for d in docs:
            canonical=_root(parents,d['id'])
            conn.execute('INSERT INTO document_members VALUES(?,?,?)',(d['id'],canonical,'same_identifier_or_title_and_author_overlap' if canonical!=d['id'] else 'source_identity'))
            if d['id'] in active:groups[canonical].append(d)
        for s in sections:
            conn.execute('INSERT INTO section_quality VALUES(?,?)',(s['id'],'content' if section_ok[s['id']] else 'placeholder'))
        dedup={}
        for c in claims:
            text,reason=cleaned_claim(c['text']);status='content' if text else 'quarantined'
            conn.execute('INSERT INTO claim_quality VALUES(?,?,?,?)',(c['id'],status,text,reason))
            source=section_sources.get(c['section_id'])
            if source not in active or not text:continue
            canonical=_root(parents,source);key=(canonical,' '.join(text.split()),c['claim_type'])
            if key in dedup:dedup[key]['sources'].append(c['id'])
            else:dedup[key]=dict(row=c,text=text,doc_id=canonical,sources=[c['id']])
        for value in dedup.values():
            c=value['row'];conn.execute('INSERT INTO read_claims VALUES(?,?,?,?,?,?)',(c['id'],c['section_id'],value['text'],c['claim_type'],value['doc_id'],json.dumps(value['sources'])))
        for canonical,members in groups.items():
            primary=max(members,key=lambda d:(Path(d['file_path']).suffix.lower()=='.pdf',sum(len(s['text'] or '') for s in by_doc[d['id']]),-d['id']))
            fields={};origins={};conflicts={}
            for key in ('title','authors','year','venue','doi','abstract_summary'):
                values=[(d[key],d['id']) for d in [primary,*sorted((m for m in members if m['id']!=primary['id']),key=lambda d:d['id'])] if d[key] not in (None,'','[]')]
                if key=='abstract_summary':values=[(v,i) for v,i in values if not re.fullmatch(r'<[^>]*unread[^>]*>',str(v),re.I|re.S)]
                fields[key],origins[key]=values[0] if values else (None,None)
                if key=='year' and len({v for v,_ in values})>1:
                    conflicts[key]=[dict(value=v,source_document_id=i) for v,i in values];fields[key]=None;origins[key]=None
            title=fields['title'] or Path(primary['file_path']).stem
            claim_count=conn.execute('SELECT count(*) FROM read_claims WHERE doc_id=?',(canonical,)).fetchone()[0]
            metadata=dict(field_sources=origins,conflicts=conflicts,source_document_ids=[d['id'] for d in members],
                          title_is_filename_fallback=not bool(fields['title']),abstract_missing=not bool(fields['abstract_summary']))
            conn.execute('INSERT INTO read_documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (canonical,title,json.dumps(authors_list(fields['authors'])),fields['year'],fields['venue'],fields['doi'],fields['abstract_summary'],
                 primary['page_count'],primary['file_path'],primary['id'],len(members),claim_count,json.dumps(metadata)))
        cp={c['id']:c['id'] for c in concepts};by_name=defaultdict(list);alias_basis={}
        for c in concepts:by_name[norm(c['canonical_name'])].append(c['id'])
        for group in policy['groups']:
            matched=sorted({cid for n in [group['canonical'],*group['aliases']] for cid in by_name[norm(n)]})
            for cid in matched[1:]:_union(cp,matched[0],cid)
            for cid in matched:alias_basis[cid]=group['basis']
        cg=defaultdict(list)
        for c in concepts:
            canon=_root(cp,c['id']);cg[canon].append(c)
            conn.execute('INSERT INTO concept_members VALUES(?,?,?)',(c['id'],canon,alias_basis.get(c['id'],'source_identity')))
        preferred={norm(g['canonical']):g for g in policy['groups']}
        for canon,members in cg.items():
            primary=next((c for c in members if norm(c['canonical_name']) in preferred),members[0])
            aliases=sorted({c['canonical_name'] for c in members}|{a for c in members for a in authors_list(c['aliases'])})
            canonical_name=primary['canonical_name']
            for group in policy['groups']:
                if {norm(c['canonical_name']) for c in members} & {norm(n) for n in [group['canonical'],*group['aliases']]}:
                    canonical_name=group['canonical'];aliases=sorted(set(aliases)|{group['canonical'],*group['aliases']});break
            quality='ranking_excluded_by_policy' if norm(canonical_name) in {norm(n) for n in policy['ranking_exclusions']} else 'content'
            definition_source=next((c for c in [primary,*members] if c['definition']),primary)
            conn.execute('INSERT INTO read_concepts VALUES(?,?,?,?,?,?,?,?)',(canon,canonical_name,json.dumps(aliases),definition_source['definition'],primary['concept_type'],definition_source['def_doc_id'],quality,json.dumps([c['id'] for c in members])))
        canonical_names={norm(r['canonical_name']):r['id'] for r in conn.execute('SELECT id,canonical_name FROM read_concepts')}
        for relation in policy.get('related_not_identical',[]):
            source=canonical_names.get(norm(relation['source']));target=canonical_names.get(norm(relation['target']))
            if source is not None and target is not None and source!=target:
                conn.execute('INSERT INTO read_concept_relations VALUES(?,?,?,?)',(source,target,relation['relation'],relation['basis']))
        conn.execute('DROP VIEW IF EXISTS read_sections')
        conn.execute('CREATE VIEW read_sections AS SELECT s.id,m.canonical_id doc_id,s.doc_id source_doc_id,s.heading,s.section_type,s.position,s.text,s.word_count,sq.status quality FROM sections s JOIN document_members m ON m.doc_id=s.doc_id JOIN document_quality q ON q.doc_id=s.doc_id JOIN section_quality sq ON sq.section_id=s.id WHERE q.status=\'active\'')
        incidence=conn.execute("SELECT type FROM sqlite_master WHERE name='read_doc_concepts'").fetchone()
        if incidence and incidence[0]=='view':conn.execute('DROP VIEW read_doc_concepts')
        conn.execute('CREATE TABLE IF NOT EXISTS read_doc_concepts(doc_id INTEGER NOT NULL,concept_id INTEGER NOT NULL,edge_type TEXT NOT NULL CHECK(edge_type IN (\'defines\',\'mentions\')),PRIMARY KEY(doc_id,concept_id,edge_type)) WITHOUT ROWID')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_read_dc_concept ON read_doc_concepts(concept_id,doc_id)')
        conn.execute('DELETE FROM read_doc_concepts')
        conn.execute('''INSERT INTO read_doc_concepts SELECT DISTINCT dm.canonical_id doc_id,cm.canonical_id concept_id,dc.edge_type
            FROM doc_concepts dc JOIN document_members dm ON dm.doc_id=dc.doc_id JOIN concept_members cm ON cm.concept_id=dc.concept_id
            JOIN document_quality dq ON dq.doc_id=dc.doc_id WHERE dq.status='active' AND EXISTS(
              SELECT 1 FROM sections s JOIN section_concepts sc ON sc.section_id=s.id JOIN section_quality sq ON sq.section_id=s.id
              WHERE s.doc_id=dc.doc_id AND sc.concept_id=dc.concept_id AND sq.status='content')''')
        try:
            # Rebuilt in full each refresh; recreate so a tokenizer change always applies.
            # Porter stemming lets plurals/inflections match ("networks" ~ "network").
            conn.execute('DROP TABLE IF EXISTS document_search')
            conn.execute("CREATE VIRTUAL TABLE document_search USING fts5(doc_id UNINDEXED,title,abstract,claims,concepts,tokenize='porter unicode61')")
            for d in conn.execute('SELECT * FROM read_documents').fetchall():
                text='\n'.join(r[0] for r in conn.execute('SELECT text FROM read_claims WHERE doc_id=?',(d['id'],)))
                terms=' '.join(r[0]+' '+r[1] for r in conn.execute('SELECT DISTINCT c.canonical_name,c.aliases FROM read_doc_concepts dc JOIN read_concepts c ON c.id=dc.concept_id WHERE dc.doc_id=?',(d['id'],)))
                conn.execute('INSERT INTO document_search VALUES(?,?,?,?,?)',(d['id'],d['title'],d['abstract_summary'] or '',text,terms))
            search='fts5_bm25'
        except sqlite3.OperationalError as exc:
            if 'no such module' not in str(exc):raise
            search='literal_fallback'
        conn.execute('INSERT OR REPLACE INTO corpus_metadata VALUES(?,?)',('revision',revision))
        conn.execute('INSERT OR REPLACE INTO corpus_metadata VALUES(?,?)',('read_model_version',READ_MODEL_VERSION))
        conn.execute('INSERT OR REPLACE INTO corpus_metadata VALUES(?,?)',('search_backend',search))
        conn.execute('DELETE FROM topic_packs WHERE corpus_revision<>?',(revision,))
        return dict(stats(conn),refresh_mode='rebuilt')
    finally:conn.row_factory=previous


def stats(conn):
    result={t:conn.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('documents','read_documents','claims','read_claims','concepts','read_concepts')}
    result['quarantined_documents']=conn.execute("SELECT count(*) FROM document_quality WHERE status='quarantined'").fetchone()[0]
    result['quarantined_claims']=conn.execute("SELECT count(*) FROM claim_quality WHERE status='quarantined'").fetchone()[0]
    result['shared_concepts']=conn.execute('SELECT count(*) FROM (SELECT concept_id FROM read_doc_concepts GROUP BY concept_id HAVING count(DISTINCT doc_id)>1)').fetchone()[0]
    result['isolated_works']=conn.execute('SELECT count(*) FROM read_documents d WHERE NOT EXISTS(SELECT 1 FROM read_doc_concepts a JOIN read_doc_concepts b ON a.concept_id=b.concept_id AND a.doc_id<>b.doc_id WHERE a.doc_id=d.id)').fetchone()[0]
    result['revision']=conn.execute("SELECT value FROM corpus_metadata WHERE key='revision'").fetchone()[0]
    return result
