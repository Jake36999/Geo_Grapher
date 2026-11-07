"""Actor retrieval completeness, revision safety and read-side performance guards."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_paper_pipeline import artifact, paper_db
from pipeline import corpus, mcp_doc_graph as service, stage3_build_db as ingest
from pipeline.artifacts import write_json
from pipeline.maintain import annotate


def test_response_identity_and_stale_page_rejection(paper_db):
    conn,path=paper_db
    first=service._TOOLS['get_document']('doc:1')
    context=first['context'];assert context['api_version']=='paper-tools-v4' and len(context['server_build'])==12
    artifact(path,text='A changed result.');ingest.load_nodes_file(path,conn);conn.commit()
    stale=service._TOOLS['get_document']('doc:1',expected_revision=context['corpus_revision'])
    assert stale['error']['code']=='STALE_CORPUS'
    assert stale['context']['corpus_revision']!=context['corpus_revision']
    fresh=service._TOOLS['get_document']('doc:1');assert 'error' not in fresh


def test_search_matches_inflected_forms(paper_db):
    conn,path=paper_db
    artifact(path,text='A social network of correspondents shaped the outcome.');ingest.load_nodes_file(path,conn);conn.commit()
    for query in ('networks','network','networked'):
        result=service._TOOLS['search_documents'](query)
        assert [d['id'] for d in result['results']]==['doc:1'],(query,result)


def test_concept_and_document_ids_are_typed(paper_db):
    conn,_=paper_db
    concept=service._TOOLS['get_concept']('knowledge graph')['matches'][0]
    assert concept['id'].startswith('concept:') and concept['definition_source_document_id']=='doc:1'
    assert all(r['source_id'].startswith('concept:') and r['target_id'].startswith('concept:') for r in concept['related_concepts'])
    found=service._TOOLS['find_by_concept']('knowledge graph')
    assert found['matched_concepts'][0]['id']==concept['id'] and found['documents'][0]['id']=='doc:1'
    document=service._TOOLS['get_document']('doc:1')
    assert document['concepts'][0]['id']==concept['id']


def test_search_cards_show_matching_claim_excerpt_only_for_claim_hits(paper_db):
    conn,path=paper_db
    artifact(path,text='Correspondents formed a network across three ports.');ingest.load_nodes_file(path,conn);conn.commit()
    card=service._TOOLS['search_documents']('networks')['results'][0]
    assert '«network»' in card['matched_claim_excerpt']
    title_only=service._TOOLS['search_documents']('sufficiently')['results'][0]
    assert 'matched_claim_excerpt' not in title_only


def test_newer_corpus_than_server_asks_for_a_restart_not_a_refresh(paper_db):
    conn,_=paper_db
    conn.execute("UPDATE corpus_metadata SET value='paper-read-v99' WHERE key='read_model_version'");conn.commit()
    error=service._TOOLS['search_documents']('graph')['error']
    assert error['code']=='READ_MODEL_OUTDATED' and 'restart' in error['message'] and 'Do not refresh' in error['message']
    conn.execute("UPDATE corpus_metadata SET value='paper-read-v1' WHERE key='read_model_version'");conn.commit()
    assert 'maintain refresh' in service._TOOLS['search_documents']('graph')['error']['message']


def test_concept_miss_points_to_full_text_search(paper_db):
    assert 'search_documents' in service._TOOLS['find_by_concept']('networks')['hint']
    assert 'search_documents' in service._TOOLS['get_concept']('networks')['hint']
    assert 'hint' not in service._TOOLS['get_concept']('knowledge graph')


def test_refresh_upgrades_an_unstemmed_index(paper_db):
    conn,_=paper_db
    conn.execute('DROP TABLE document_search')
    conn.execute('CREATE VIRTUAL TABLE document_search USING fts5(doc_id UNINDEXED,title,abstract,claims,concepts)')
    conn.execute("UPDATE corpus_metadata SET value='paper-read-v3' WHERE key='read_model_version'");conn.commit()
    assert service._TOOLS['search_documents']('graphs')['error']['code']=='READ_MODEL_OUTDATED'
    corpus.refresh(conn);conn.commit()
    sql=conn.execute("SELECT sql FROM sqlite_master WHERE name='document_search'").fetchone()[0]
    assert 'porter' in sql and service._TOOLS['search_documents']('graphs')['results'][0]['id']=='doc:1'


def test_claim_pages_recover_full_text_and_all_sources(paper_db):
    conn,path=paper_db;text='Evidence the authors report: '+'long result '*300
    artifact(path,text=text);ingest.load_nodes_file(path,conn)
    artifact(path,source='note.md',text=text);ingest.load_nodes_file(path,conn);conn.commit()
    outline=service._TOOLS['get_outline']('doc:1')
    sections=outline['sections'];assert len(sections)==2
    # A duplicate occurrence must remain discoverable from either source section.
    for section in sections:
        result=service._TOOLS['get_section']('doc:1',section_id=section['id'])
        assert len(result['claims'])==1 and result['claims'][0]['text_truncated']
    handle=result['claims'][0]['content_handle'];offset=0;parts=[]
    while True:
        result=service._TOOLS['get_claim']('doc:1',handle,text_offset=offset,max_chars=1000)
        parts.append(result['text'])
        assert result['evidence_count']==2
        if result['next_text_offset'] is None:break
        offset=result['next_text_offset']
    assert ''.join(parts)==text.removeprefix('Evidence the authors report: ').strip()
    original=result['evidence'][0]['source_claim_id']
    source=service._TOOLS['get_claim']('doc:1',handle,source_claim_id=original,max_chars=8000)
    assert source['representation']=='original_extracted_claim' and source['text']==text
    assert source['evidence'][0]['provenance']['coverage']['status']=='legacy_unverified'


@pytest.mark.parametrize('identity',['claim:99999999','claim:-1','claim:999999999999999999999999999','garbage'])
def test_bad_claim_handles_are_structured_errors(paper_db,identity):
    assert 'error' in service._TOOLS['get_claim']('doc:1',identity)


def test_claims_cannot_be_read_through_unrelated_work(paper_db):
    conn,path=paper_db;cid=conn.execute('SELECT id FROM claims').fetchone()[0]
    artifact(path,source='other.pdf',title='An entirely different long research title');ingest.load_nodes_file(path,conn);conn.commit()
    assert 'error' in service._TOOLS['get_claim']('doc:2','claim:'+str(cid))


def test_search_modes_aliases_and_exact_title_priority(paper_db):
    conn,path=paper_db
    title='Retrieval augmented generation methods'
    artifact(path,title=title,text='retrieval augmented generation',concept='generative ai');ingest.load_nodes_file(path,conn)
    artifact(path,source='other.pdf',title='A different long distinct paper title',text='retrieval methods');ingest.load_nodes_file(path,conn);conn.commit()
    any_results=service._TOOLS['search_documents']('retrieval augmented generation',match_mode='any')
    all_results=service._TOOLS['search_documents']('retrieval augmented generation',match_mode='all')
    phrase_results=service._TOOLS['search_documents']('retrieval augmented generation',match_mode='phrase')
    assert any_results['count']==2 and all_results['count']==1 and phrase_results['count']==1
    assert service._TOOLS['search_documents']('genai')['results'][0]['id']=='doc:1'
    assert service._TOOLS['search_documents'](title)['results'][0]['title']==title
    conn.execute("UPDATE corpus_metadata SET value='literal_fallback' WHERE key='search_backend'");conn.commit()
    assert service._TOOLS['search_documents']('augmented generation',match_mode='all')['count']==1
    assert service._TOOLS['search_documents']('genai')['count']==1
    assert 'error' in service._TOOLS['search_documents']('test',match_mode='unknown')


def test_concept_matches_page_without_silent_omissions(paper_db):
    conn,path=paper_db
    for i in range(8):
        artifact(path,source=f'paper{i}.pdf',title=f'A distinct research publication number {i}',concept=f'method {i}')
        ingest.load_nodes_file(path,conn)
    conn.commit()
    first=service._TOOLS['get_concept']('method')
    assert first['concept_match_count']==8 and first['concept_pagination']['next_offset']==5
    second=service._TOOLS['get_concept']('method',concept_offset=5,expected_revision=first['context']['corpus_revision'])
    assert len(second['matches'])==3 and not second['concept_pagination']['truncated']
    assert {r['name'] for r in first['matches']+second['matches']}=={f'method {i}' for i in range(8)}
    docs=service._TOOLS['find_by_concept']('method',concept_offset=5)
    assert docs['concept_match_count']==8 and len(docs['matched_concepts'])==3


def test_typed_concept_relation_does_not_merge_identity(paper_db):
    conn,path=paper_db
    for term in ('svd','truncated svd'):
        artifact(path,source=term+'.pdf',title='A research publication about '+term,concept=term);ingest.load_nodes_file(path,conn)
    conn.commit()
    result=service._TOOLS['get_concept']('truncated svd')['matches'][0]
    assert result['related_concepts'][0]['relation']=='variant_of'
    assert result['related_concepts'][0]['source']=='truncated svd' and result['related_concepts'][0]['target']=='svd'
    assert service._TOOLS['get_concept']('svd')['matches'][0]['id']!=result['id']


def test_placeholder_sections_are_explicit_and_optional(paper_db):
    conn,path=paper_db;data=artifact(path)
    data['sections'].append(dict(heading='Unread',section_type='methods',position=1,text='<method: unread>',claims=[],concepts=[]))
    write_json(path,data);ingest.load_nodes_file(path,conn);conn.commit()
    outline=service._TOOLS['get_outline']('doc:1');assert len(outline['sections'])==1 and outline['excluded_placeholder_sections']==1
    all_sections=service._TOOLS['get_outline']('doc:1',include_placeholders=True)
    unread=next(s for s in all_sections['sections'] if s['quality']=='placeholder')
    assert service._TOOLS['get_section']('doc:1',section_id=unread['id'])['quality']=='placeholder'


def test_noop_refresh_skips_derived_writes_and_keeps_packs(paper_db):
    conn,path=paper_db;rev=corpus.stats(conn)['revision']
    conn.execute("INSERT INTO topic_packs VALUES('cached',?,'{}')",(rev,));conn.commit()
    changes=conn.total_changes;result=corpus.refresh(conn)
    assert result['refresh_mode']=='unchanged' and conn.total_changes==changes
    assert conn.execute('SELECT count(*) FROM topic_packs').fetchone()[0]==1
    assert conn.execute("SELECT type FROM sqlite_master WHERE name='read_doc_concepts'").fetchone()[0]=='table'
    plan=' '.join(str(tuple(r)) for r in conn.execute('EXPLAIN QUERY PLAN SELECT * FROM read_doc_concepts WHERE concept_id=1'))
    assert 'idx_read_dc_concept' in plan


def test_health_separates_scope_and_detects_outdated_models(paper_db,monkeypatch):
    conn,path=paper_db;status=service._TOOLS['get_corpus_status']()
    assert status['read_model_current'] and status['active_concepts']==1
    assert not status['server']['sources_changed_since_start']
    monkeypatch.setattr(service,'source_build',lambda:'changed')
    assert service._TOOLS['get_corpus_status']()['server']['sources_changed_since_start']
    conn.execute("UPDATE corpus_metadata SET value='paper-read-v2' WHERE key='read_model_version'");conn.commit()
    assert not service._TOOLS['get_corpus_status']()['read_model_current']
    assert service._TOOLS['get_document']('doc:1')['error']['code']=='READ_MODEL_OUTDATED'


def test_annotations_and_archive_survive_reimport_with_paging(paper_db):
    conn,path=paper_db;old='Old source assertion. '*100
    artifact(path,text=old);ingest.load_nodes_file(path,conn);conn.commit()
    rev=corpus.stats(conn)['revision'];cid=conn.execute('SELECT id FROM claims').fetchone()[0]
    note='A provisional synthesis. '*200
    annotation=annotate(conn,kind='synthesis',text=note,source_refs=[dict(kind='claim',id=cid)],expected_revision=rev,author='test')
    artifact(path,text='A new source assertion.');ingest.load_nodes_file(path,conn);conn.commit()
    page=service._TOOLS['get_annotations']('doc:1',annotation_id=annotation['id'],max_chars=8000)
    item=page['annotations'][0]
    assert item['text']==note and not item['matches_current_revision'] and item['review_status']=='unreviewed'
    offset=0;parts=[];archive=None
    while True:
        result=service._TOOLS['get_annotations']('doc:1',annotation_id=annotation['id'],source_index=0,text_offset=offset,max_chars=300)
        archive=result['annotations'][0]['archived_source'];parts.append(archive['text'])
        if archive['next_text_offset'] is None:break
        offset=archive['next_text_offset']
    assert ''.join(parts)==old
    record=dict(archive['metadata']);record[archive['text_field']]=''.join(parts)
    assert hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()==archive['record_sha256']
    assert service._TOOLS['get_document']('doc:1',detail='claims')['claims'][0]['text']=='A new source assertion.'


def test_annotation_read_requires_scope_and_explicit_text_continuation(paper_db):
    assert 'error' in service._TOOLS['get_annotations']('doc:1',source_index=0)
    assert 'error' in service._TOOLS['get_annotations']('doc:1',text_offset=10)
    assert 'error' in service._TOOLS['get_annotations']('doc:1',annotation_id=999)


def test_response_context_isolated_across_parallel_queries(paper_db):
    rev=service._TOOLS['get_corpus_status']()['context']['corpus_revision']
    def query(index):return service._TOOLS['get_document']('doc:1',expected_revision=rev if index%2==0 else 'stale')
    with ThreadPoolExecutor(max_workers=4) as workers:rows=list(workers.map(query,range(12)))
    assert all(r['context']['corpus_revision']==rev for r in rows)
    assert all(('error' in r)==bool(i%2) for i,r in enumerate(rows))


def test_reviewed_alias_merges_all_normalized_variants(paper_db):
    conn,path=paper_db
    for index,term in enumerate(('retrieval-augmented generation','retrieval augmented generation','retrieval augmented generation rag')):
        artifact(path,source=f'rag{index}.pdf',title=f'A distinct publication about retrieval {index}',concept=term)
        ingest.load_nodes_file(path,conn)
    conn.commit()
    result=service._TOOLS['get_concept']('rag')
    assert len(result['matches'])==1 and result['matches'][0]['document_count']==3
    assert service._TOOLS['find_by_concept']('retrieval-augmented generation')['count']==3


@pytest.mark.parametrize('conflict',['overlap','nonidentity','missing_basis'])
def test_invalid_alias_policy_rolls_back_without_graph_changes(paper_db,tmp_path,conflict):
    conn,_=paper_db;revision=corpus.stats(conn)['revision']
    policy=dict(version='test',groups=[dict(canonical='svd',aliases=['truncated svd'],basis='review')],related_not_identical=[],ranking_exclusions=[])
    if conflict=='overlap':policy['groups'].append(dict(canonical='another',aliases=['truncated svd'],basis='review'))
    elif conflict=='nonidentity':policy['related_not_identical']=[dict(source='truncated svd',target='svd',relation='variant_of',basis='not identical')]
    else:policy['groups'][0]['basis']=''
    path=tmp_path/'bad-policy.json';write_json(path,policy)
    with pytest.raises(ValueError):corpus.refresh(conn,path)
    assert corpus.stats(conn)['revision']==revision


def test_related_page_order_and_counts_are_distinct(paper_db):
    conn,path=paper_db
    for index in range(3):
        artifact(path,source=f'other{index}.pdf',title=f'Another distinct research publication {index}')
        ingest.load_nodes_file(path,conn)
    conn.commit()
    first=service._TOOLS['get_related']('doc:1',limit=1)
    assert first['total_related']==3 and first['pagination']['next_offset']==1
    second=service._TOOLS['get_related']('doc:1',limit=2,offset=1,expected_revision=first['context']['corpus_revision'])
    assert len({r['id'] for r in first['related']+second['related']})==3
    assert all(r['shared_concepts']==1 and r['shared_preview_complete'] for r in first['related']+second['related'])


def test_annotation_page_snapshot_excludes_concurrent_appends(paper_db):
    conn,_=paper_db;rev=corpus.stats(conn)['revision']
    def add(text):return annotate(conn,kind='note',text=text,source_refs=[dict(kind='document',id=1)],expected_revision=rev,author='test')['id']
    oldest=add('First note');newer=add('Second note')
    first=service._TOOLS['get_annotations']('doc:1',limit=1)
    latest=add('Concurrent new note')
    second=service._TOOLS['get_annotations']('doc:1',offset=1,limit=1,as_of_id=first['as_of_id'],expected_revision=rev)
    assert first['annotations'][0]['id']==newer and second['annotations'][0]['id']==oldest
    assert first['as_of_id']<latest
    assert 'error' in service._TOOLS['get_annotations']('doc:1',offset=1)
