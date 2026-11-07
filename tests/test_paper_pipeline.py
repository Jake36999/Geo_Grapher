"""Offline ingestion and paper-tool regressions; never call providers."""
import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from pipeline import corpus, stage3_build_db as db, stage2_extract_nodes as nodes, stage2_from_md as md
from pipeline import mcp_doc_graph as tools
from pipeline.artifacts import write_json
from pipeline.maintain import annotate
from geographer.source import Repository


def artifact(path, *, title='A sufficiently long research paper title', source='paper.pdf', concept='knowledge graph', text='An actual result.', year=2026):
    data=dict(file_path=source,metadata=dict(title=title,authors=['Doe, Jane'],year=year,abstract_summary='A summary.'),status='complete',sections=[dict(heading='Results',section_type='results',position=0,text='Useful section text',word_count=3,claims=[dict(text=text,claim_type='finding')],concepts=[dict(name=concept,definition='A definition',concept_type='term')])])
    write_json(path,data);return data


@pytest.fixture
def paper_db(tmp_path,monkeypatch):
    path=tmp_path/'papers.sqlite';conn=sqlite3.connect(path);conn.executescript(db.DDL)
    f=tmp_path/'paper.nodes.json';artifact(f);db.load_nodes_file(f,conn);conn.commit()
    monkeypatch.setattr(tools,'DB_PATH',path)
    yield conn,f
    conn.close()


def test_reimport_replaces_stale_edges_and_invalidates_cache(paper_db):
    conn,f=paper_db;rev=corpus.stats(conn)['revision'];conn.execute("INSERT INTO topic_packs VALUES('x',?,'{}')",(rev,));conn.commit()
    artifact(f,concept='PyTorch');db.load_nodes_file(f,conn)
    assert conn.execute('SELECT canonical_name FROM concepts').fetchall()==[('pytorch',)]
    assert conn.execute('SELECT count(*) FROM topic_packs').fetchone()[0]==0
    assert not conn.execute('PRAGMA foreign_key_check').fetchall()
    assert corpus.stats(conn)['revision']!=rev


def test_failed_reimport_is_atomic(paper_db):
    conn,f=paper_db;before=conn.execute('SELECT * FROM claims').fetchall();rev=corpus.stats(conn)['revision']
    data=artifact(f,concept='bad');data['sections'][0]['concepts']=[{'name':7}];write_json(f,data)
    with pytest.raises(AttributeError):db.load_nodes_file(f,conn)
    assert conn.execute('SELECT * FROM claims').fetchall()==before
    assert corpus.stats(conn)['revision']==rev


@pytest.mark.parametrize('flag', ['skipped','incomplete'])
def test_failed_extraction_never_published(paper_db,flag):
    conn,f=paper_db;data=artifact(f)
    if flag=='skipped':data['skipped']='too_large'
    else:data['status']='incomplete'
    write_json(f,data)
    with pytest.raises(ValueError):db.load_nodes_file(f,conn)
    assert conn.execute('SELECT count(*) FROM documents').fetchone()[0]==1


def test_cleanup_preserves_sources_and_distinguishes_variants(paper_db,tmp_path):
    conn,f=paper_db
    artifact(f,source='note.md',concept='knowledge graphs',year=2025,text='<bottom line: unread>');db.load_nodes_file(f,conn)
    artifact(f,source='third.pdf',title='A different sufficiently long research title',concept='truncated svd');db.load_nodes_file(f,conn)
    artifact(f,source='fourth.pdf',title='Another sufficiently long unique title',concept='svd');db.load_nodes_file(f,conn)
    result=corpus.stats(conn)
    assert result['documents']==4 and result['read_documents']==3
    assert result['quarantined_claims']==1
    assert result['concepts']-result['read_concepts']==1
    merged=conn.execute('SELECT year,metadata_json FROM read_documents WHERE id=1').fetchone()
    assert merged[0] is None and 'conflicts' in merged[1]
    assert conn.execute("SELECT count(*) FROM read_concepts WHERE canonical_name IN ('svd','truncated svd')").fetchone()[0]==2


def test_refresh_failure_rolls_back(paper_db,tmp_path):
    conn,_=paper_db;rev=corpus.stats(conn)['revision'];bad=tmp_path/'bad.json';bad.write_text('{}')
    with pytest.raises((KeyError,ValueError)):corpus.refresh(conn,bad)
    assert corpus.stats(conn)['revision']==rev


def test_query_cards_fts_paging_and_aliases(paper_db):
    conn,f=paper_db
    artifact(f,text='Retrieval augmented generation is discussed.',concept='knowledge graphs');db.load_nodes_file(f,conn);conn.commit()
    search=tools._TOOLS['search_documents']('retrieval augmented generation')
    assert search['count']==1 and search['ranking_basis']=='fts5_bm25'
    card=tools._TOOLS['get_document']('doc:1');assert 'claims' not in card and card['authors']==['Doe, Jane']
    full=tools._TOOLS['get_document']('doc:1',detail='claims');assert len(full['claims'])==1
    assert tools._TOOLS['get_concept']('knowledge graph')['matches']
    outline=tools._TOOLS['get_outline']('doc:1');sid=outline['sections'][0]['id']
    section=tools._TOOLS['get_section']('doc:1',section_id=sid,max_chars=4)
    assert section['text_truncated'] and section['next_text_offset']==4
    assert tools._TOOLS['get_concept']('RAG')['matches']==[]


@pytest.mark.parametrize('name,args', [('search_documents',dict(query='x',limit=-1)),('get_related',dict(title='x',limit=0)),('get_document',dict(title='x',detail='unknown')),('get_section',dict(title='x',text_offset=-1)),('find_by_concept',dict(concept='x',edge_type='anything'))])
def test_tool_validation(paper_db,name,args):
    assert tools._TOOLS[name](**args)['error']['code']=='INVALID_REQUEST'


def test_missing_db_not_created(tmp_path,monkeypatch):
    path=tmp_path/'missing.db';monkeypatch.setattr(tools,'DB_PATH',path)
    assert 'error' in tools._TOOLS['search_documents']('x');assert not path.exists()


def test_related_distinct_concepts(paper_db):
    conn,f=paper_db;artifact(f,source='second.pdf',title='Another sufficiently long distinct paper');db.load_nodes_file(f,conn)
    conn.execute("INSERT OR IGNORE INTO doc_concepts SELECT doc_id,concept_id,'mentions' FROM doc_concepts");corpus.refresh(conn);conn.commit()
    r=tools._TOOLS['get_related']('doc:1');assert r['related'][0]['shared_concepts']==1


def test_annotations_opt_in_revision_and_immutability(paper_db):
    conn,_=paper_db;rev=corpus.stats(conn)['revision']
    args=dict(kind='synthesis',text='An unverified interpretation.',source_refs=[dict(kind='document',id=1)],expected_revision=rev,author='test')
    result=annotate(conn,**args);assert result['review_status']=='unreviewed'
    assert annotate(conn,**args)['id']==result['id']
    with pytest.raises(sqlite3.IntegrityError):conn.execute("UPDATE annotations SET text='changed'")
    conn.rollback()
    with pytest.raises(ValueError):annotate(conn,**dict(args,expected_revision='stale'))


def test_structured_mcp_no_double_json(paper_db):
    if tools.SDK2:pytest.skip('SDK1 transport test')
    r=asyncio.run(tools.call_tool('get_document',{'title':'doc:1'}))
    assert r.structuredContent['id']=='doc:1' and r.content==[]


def test_markdown_fences_authors_and_full_sections(tmp_path):
    p=tmp_path/'note.md';body='x '*2500
    p.write_text('---\ntitle: Paper\nauthors: ["Doe, Jane", "Smith, John"]\n---\n## Claim\n'+body+'\n```markdown\n## Method\nnot a heading\n```\n## Method\n- Actual method\n',encoding='utf-8')
    r=md._convert_md(p);assert r['metadata']['authors']==['Doe, Jane','Smith, John']
    assert len(r['sections'][0]['text'])>4000
    assert 'not a heading' in r['sections'][0]['text']
    assert md._split_sections('## Claim\nfirst\n## Claim\nsecond')['claim']=='first\n\nsecond'


def test_directory_roots_and_missing_paths(tmp_path):
    (tmp_path/'src').mkdir();(tmp_path/'src'/'a.py').write_text('x=1');(tmp_path/'outside.py').write_text('x=2')
    r=Repository.from_directory(tmp_path,'test',source_roots=('src',));assert list(r.files)==['src/a.py']
    with pytest.raises(ValueError):Repository.from_directory(tmp_path/'missing','test')
    with pytest.raises(ValueError):Repository.from_directory(tmp_path,'test',source_roots=('../',))


def test_pdf_actual_page_numbers_short_and_long_sections(tmp_path,monkeypatch):
    from pipeline import stage1_extract_text as pdf
    monkeypatch.setattr(pdf,'fitz',SimpleNamespace(TEXT_PRESERVE_WHITESPACE=1))
    class Page:
        def __init__(self,text):self.text=text
        def get_text(self,mode,**kwargs):
            if mode=='text':return self.text
            return {'blocks':[{'type':0,'number':99,'lines':[{'spans':[dict(text=self.text,size=10,flags=0)]}]}]}
    p=tmp_path/'paper.pdf';p.write_bytes(b'fake')
    r=pdf._extract_document(p,[Page('short text'),Page('long text '*900)])
    assert r['sections'][0]['page_start']==1 and r['sections'][0]['page_end']==2
    assert len(r['sections'][0]['text'])>4000 and not r['sections'][0]['text_truncated']


def test_extractor_merges_duplicate_headings_by_position(tmp_path,monkeypatch):
    text=tmp_path/'a.text.json';out=tmp_path/'nodes';out.mkdir()
    write_json(text,dict(file_path='paper.pdf',sections=[dict(heading='Same',section_type='results',position=i,word_count=1,text='result') for i in (0,1)]))
    monkeypatch.setattr(nodes,'_call_a_metadata',lambda *a:({'title':'Paper'},10,2))
    monkeypatch.setattr(nodes,'_call_b_sections',lambda *a:({'sections':[dict(position=i,claims=[dict(text=str(i))],concepts=[]) for i in (1,0)]},20,3))
    spend=[0.0];assert nodes.process_paper(text,out,'test-model',1,1,'unused',spend)
    r=json.loads((out/'a.nodes.json').read_text());assert [s['claims'][0]['text'] for s in r['sections']]==['0','1']
    assert nodes.extraction_current(text,out,'test-model')
    assert not nodes.extraction_current(text,out,'other-model')
    assert spend[0]>0


def test_extractor_error_is_incomplete_and_usage_counted(tmp_path,monkeypatch):
    text=tmp_path/'b.text.json';out=tmp_path/'nodes';out.mkdir()
    write_json(text,dict(file_path='paper.pdf',sections=[dict(heading='Results',section_type='results',position=0,word_count=1,text='result')]))
    def fail(*a):raise nodes.ExtractionResponseError('bad JSON',{'prompt_tokens':100,'completion_tokens':30})
    monkeypatch.setattr(nodes,'_call_a_metadata',fail)
    monkeypatch.setattr(nodes,'_call_b_sections',lambda *a:pytest.fail('Must not call provider after failure'))
    spend=[0.0];assert not nodes.process_paper(text,out,'test-model',1,1,'unused',spend)
    r=json.loads((out/'b.nodes.json').read_text());assert r['status']=='incomplete' and r['usage']['input_tokens']==100 and spend[0]>0


def test_versioned_vectors_are_candidates_never_merges(paper_db):
    from pipeline.embedding_candidates import import_vectors,propose
    conn,f=paper_db;artifact(f,source='another.pdf',title='Another sufficiently long distinct paper',concept='different concept');db.load_nodes_file(f,conn)
    rows=conn.execute('SELECT id,canonical_name FROM read_concepts ORDER BY id').fetchall()
    records=[dict(concept_id=i,input_text=name,vector=[1.,0.]) for i,name in rows]
    assert import_vectors(conn,model='test-encoder',model_revision='pinned1',records=records)==2
    result=propose(conn,model='test-encoder',model_revision='pinned1');assert len(result['pairs'])==1
    assert conn.execute('SELECT count(*) FROM read_concepts').fetchone()[0]==2
    assert propose(conn,model='test-encoder',model_revision='pinned2')['eligible_vectors']==0
    conn.execute("UPDATE read_concepts SET canonical_name='changed' WHERE id=?",(rows[0][0],));conn.commit()
    assert propose(conn,model='test-encoder',model_revision='pinned1')['stale_vectors']==1
    with pytest.raises(ValueError):import_vectors(conn,model='test-encoder',model_revision='pinned1',records=records)


def test_refresh_quarantines_stubs_and_keeps_pytorch(paper_db):
    conn,f=paper_db;conn.execute("INSERT INTO documents(file_path,title) VALUES('stub.pdf',NULL)");conn.commit()
    corpus.refresh(conn)
    assert corpus.stats(conn)['quarantined_documents']==1
    assert conn.execute('SELECT count(*) FROM documents').fetchone()[0]==2
    artifact(f,concept='PyTorch');db.load_nodes_file(f,conn);conn.commit()
    assert tools._TOOLS['get_concept']('pytorch')['matches'][0]['quality']=='content'


def test_literal_wildcards_are_not_query_operators(paper_db):
    assert tools._TOOLS['search_documents']('" OR *')['count']==0
    assert tools._TOOLS['get_concept']('%')['matches']==[]


def test_unique_doi_requires_corroboration(paper_db):
    conn,f=paper_db
    conn.execute("UPDATE documents SET doi='10.fake/shared'");conn.commit()
    data=artifact(f,source='unrelated.pdf',title='An unrelated sufficiently long title');data['metadata'].update(doi='10.fake/shared',authors=['Other, Author']);write_json(f,data);db.load_nodes_file(f,conn)
    assert corpus.stats(conn)['read_documents']==2


def test_real_stdio_seven_tools_and_structured_errors(paper_db):
    import os,sys
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def exercise():
        env={**os.environ,'GEOGRAPHER_DOC_GRAPH_DB':str(tools.DB_PATH)}
        params=StdioServerParameters(command=sys.executable,args=[str(Path(tools.__file__).resolve())],env=env)
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer) as session:
                await session.initialize();listing=await session.list_tools();assert len(listing.tools)==10
                for item in listing.tools:
                    assert item.outputSchema
                for name,args in [('search_documents',{'query':'summary'}),('get_document',{'title':'doc:1'}),('get_outline',{'title':'doc:1'}),('get_section',{'title':'doc:1','heading':'Results'}),('get_concept',{'name':'knowledge graph'}),('find_by_concept',{'concept':'knowledge graph'}),('get_related',{'title':'doc:1'})]:
                    result=await session.call_tool(name,args)
                    assert result.structuredContent and not result.isError and not result.content
                result=await session.call_tool('get_document',{'title':'doc:9999'})
                assert result.isError and result.structuredContent['error']['code']=='INVALID_REQUEST'
    asyncio.run(exercise())


def test_annotations_surface_as_unreviewed_not_source_facts(paper_db):
    conn,_=paper_db;rev=corpus.stats(conn)['revision']
    claim=conn.execute('SELECT id FROM claims').fetchone()[0]
    annotate(conn,kind='note',text='An interpretation.',source_refs=[dict(kind='claim',id=claim)],expected_revision=rev,author='test')
    card=tools._TOOLS['get_document']('doc:1')
    assert card['annotations'][0]['review_status']=='unreviewed'
    assert card['claim_count']==1


@pytest.mark.parametrize('mutation',['empty_title','no_sections','duplicate_positions','bad_hash'])
def test_incomplete_legacy_artifact_cannot_publish(paper_db,mutation):
    conn,f=paper_db;data=artifact(f)
    if mutation=='empty_title':data['metadata']['title']=''
    elif mutation=='no_sections':data['sections']=[]
    elif mutation=='duplicate_positions':data['sections']*=2
    else:data['source_sha256']='fake'
    write_json(f,data)
    with pytest.raises(ValueError):db.load_nodes_file(f,conn)
    assert conn.execute('SELECT count(*) FROM documents').fetchone()[0]==1


def test_unchanged_import_retains_source_ids_and_revision(paper_db):
    conn,f=paper_db;before=conn.execute('SELECT * FROM claims').fetchall();rev=corpus.stats(conn)['revision']
    db.load_nodes_file(f,conn)
    assert conn.execute('SELECT * FROM claims').fetchall()==before
    assert corpus.stats(conn)['revision']==rev


def test_placeholder_only_document_is_not_a_complete_work(paper_db):
    conn,f=paper_db;data=artifact(f,source='unread.md',title='An unread sufficiently long distinct paper',text='<method: unread>');data['sections'][0]['text']='<method: unread>';write_json(f,data)
    db.load_nodes_file(f,conn)
    assert corpus.stats(conn)['quarantined_documents']==1
    assert corpus.stats(conn)['read_documents']==1
    assert conn.execute('SELECT count(*) FROM documents').fetchone()[0]==2


def test_extraction_dry_run_creates_no_output_or_calls(tmp_path,monkeypatch):
    textdir=tmp_path/'text';textdir.mkdir()
    write_json(textdir/'paper.text.json',dict(file_path='paper.pdf',sections=[dict(position=0,heading='Results',section_type='results',word_count=1,text='a result')]))
    monkeypatch.setattr('sys.argv',['stage2','--work-dir',str(tmp_path),'--dry-run'])
    monkeypatch.setattr(nodes,'_load_key',lambda:pytest.fail('No key access'))
    monkeypatch.setattr(nodes,'_call',lambda *a:pytest.fail('No network'))
    nodes.main();assert not (tmp_path/'nodes').exists()


def test_orchestrator_dry_run_does_not_extract(tmp_path,monkeypatch):
    from pipeline import run_pipeline
    calls=[]
    monkeypatch.setattr(run_pipeline,'run',lambda args:calls.append(args) or 0)
    monkeypatch.setattr('sys.argv',['pipeline','--work-dir',str(tmp_path),'--dry-run'])
    with pytest.raises(SystemExit) as exc:run_pipeline.main()
    assert exc.value.code==0
    assert len(calls)==1 and calls[0][0]=='stage2_extract_nodes.py' and '--dry-run' in calls[0]
