import hashlib
import json
import sqlite3

import pytest

from pipeline.stage3_build_db import DDL, load_nodes_file
from pipeline.mcp_doc_graph import _provenance


@pytest.fixture
def artifact(tmp_path):
    original = tmp_path / 'original.pdf'
    original.write_bytes(b'original PDF fixture')
    converted = tmp_path / 'generated.md'
    converted.write_text('[page 1]\nFirst complete page.\n\n[page 2]\nLast complete page.', encoding='utf-8')
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    data = {'file_path': original.as_posix(), 'source': 'librarian_conversion',
        'producer': 'librarian-paper-conversion-v1', 'source_extractor_version': 'librarian-conversion-v1',
        'source_sha256': digest(original), 'page_count': 2, 'metadata': {'title': 'Full study'},
        'coverage': {'status': 'full_conversion', 'page_verification': False},
        'original': {'path': original.as_posix(), 'sha256': digest(original),
                     'authorship': 'third_party', 'evidence_id': 'a' * 32},
        'conversion': {'path': converted.as_posix(), 'sha256': digest(converted),
                       'authorship': 'generated', 'evidence_id': 'b' * 32},
        'sections': [{'position': 0, 'heading': 'Study', 'text': 'First complete page.\n\nLast complete page.',
                      'page_start': 1, 'page_end': 2, 'claims': [], 'concepts': []}]}
    path = tmp_path / 'study.nodes.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    conn = sqlite3.connect(tmp_path / 'paper.sqlite')
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    yield conn, path, data
    conn.close()


def test_conversion_import_keeps_original_pages_and_distinct_provenance(artifact):
    conn, path, _ = artifact
    load_nodes_file(path, conn)
    span = conn.execute('SELECT * FROM section_provenance').fetchone()
    assert (span['page_start'], span['page_end']) == (1, 2)
    assert span['coordinate_space'] == 'original_pdf_page_via_generated_conversion'
    provenance = _provenance(conn, 1)
    assert provenance['representation']['conversion']['authorship'] == 'generated'
    assert provenance['representation']['original']['authorship'] == 'third_party'
    assert provenance['coverage']['page_verification'] is False


def test_missing_original_catalogue_only_import_has_no_fabricated_sections(artifact):
    conn, path, data = artifact
    data.update(sections=[], coverage={'status': 'catalogue_only', 'page_verification': False})
    data.pop('original'); data.pop('conversion')
    path.write_text(json.dumps(data), encoding='utf-8')
    load_nodes_file(path, conn)
    assert conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0] == 1
    assert conn.execute('SELECT COUNT(*) FROM sections').fetchone()[0] == 0
    assert _provenance(conn, 1)['coverage']['status'] == 'catalogue_only'


def test_conversion_hash_mismatch_is_rejected_before_import(artifact):
    conn, path, data = artifact
    data['conversion']['sha256'] = '0' * 64
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='conversion'):
        load_nodes_file(path, conn)
    assert conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0] == 0


def test_note_only_paper_cli_projection_is_explicitly_catalogue_only(tmp_path):
    from pipeline.stage2_from_md import _convert_catalogue
    note = tmp_path / 'Study.md'
    note.write_text('---\ntype: source\nkind: paper\ntitle: Study\n---\n'
                    '## Bottom Line\nA note summary, not original pages.\n'
                    '## Claims\n- A note-derived claim.\n', encoding='utf-8')
    data = _convert_catalogue(note)
    assert data['coverage']['status'] == 'catalogue_only'
    assert data['coverage']['page_verification'] is False
    assert data['sections'] == []
    assert data['metadata']['title']


def test_catalogue_only_paper_remains_findable_without_inventing_source_text(artifact, monkeypatch):
    from pipeline import mcp_doc_graph as tools
    conn, path, data = artifact
    data.update(sections=[], coverage={'status': 'catalogue_only', 'page_verification': False})
    data.pop('original'); data.pop('conversion')
    path.write_text(json.dumps(data), encoding='utf-8')
    load_nodes_file(path, conn)
    conn.commit()
    monkeypatch.setattr(tools, 'DB_PATH', path.parent / 'paper.sqlite')
    found = tools._TOOLS['search_documents']('study')
    assert found['count'] == 1, found
    assert found['results'][0]['coverage_status'] == 'catalogue_only'
    outline = tools._TOOLS['get_outline']('Full study')
    assert outline['sections'] == [], outline


def test_paper_search_exposes_imported_use_history_without_claiming_live_sync(artifact, monkeypatch):
    from pipeline import mcp_doc_graph as tools
    conn, path, data = artifact
    data['catalogue'] = {'authorship': 'generated', 'captured_at': '2026-11-15T00:00:00Z',
        'use_rollup': {'authorship': 'generated', 'log_use_count': 2, 'application_count': 1,
                       'recent_uses': [{'used_for': 'A located comparison.'}], 'applications': []}}
    path.write_text(json.dumps(data), encoding='utf-8')
    load_nodes_file(path, conn)
    conn.commit()
    monkeypatch.setattr(tools, 'DB_PATH', path.parent / 'paper.sqlite')
    hit = tools._TOOLS['search_documents']('study')['results'][0]
    assert hit['use_rollup']['sources'][0]['history']['log_use_count'] == 2
    assert hit['use_rollup']['sources'][0]['history']['application_count'] == 1
    assert hit['use_rollup']['sources'][0]['captured_at'] == '2026-11-15T00:00:00Z'
    assert hit['use_rollup']['freshness'] == 'at graph import; not live session history'


def test_legacy_paper_search_says_use_history_is_unknown(artifact, monkeypatch):
    from pipeline import mcp_doc_graph as tools
    conn, path, _ = artifact
    load_nodes_file(path, conn)
    conn.commit()
    monkeypatch.setattr(tools, 'DB_PATH', path.parent / 'paper.sqlite')
    hit = tools._TOOLS['search_documents']('study')['results'][0]
    assert hit['use_rollup']['status'] == 'not_recorded'


def test_oversized_catalogue_metadata_is_rejected_before_import(artifact):
    conn, path, data = artifact
    data['catalogue'] = {'use_rollup': {'recent_uses': ['x' * 100000]}}
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='catalogue'):
        load_nodes_file(path, conn)
    assert conn.execute('SELECT count(*) FROM documents').fetchone()[0] == 0


def test_use_history_does_not_overflow_a_single_search_card(artifact, monkeypatch):
    from pipeline import mcp_doc_graph as tools
    conn, path, data = artifact
    data['catalogue'] = {'use_rollup': {'log_use_count': 50, 'application_count': 2,
                                      'recent_uses': [{'used_for': 'x' * 7000}]}}
    path.write_text(json.dumps(data), encoding='utf-8')
    load_nodes_file(path, conn)
    conn.commit()
    monkeypatch.setattr(tools, 'DB_PATH', path.parent / 'paper.sqlite')
    result = tools._TOOLS['search_documents']('study')
    history = result['results'][0]['use_rollup']
    assert len(json.dumps(history, ensure_ascii=True)) <= 2400
    assert history['sources'][0]['history']['log_use_count'] == 50
    assert history['details_truncated'] is True


def test_section_provenance_does_not_repeat_full_catalogue_history(artifact, monkeypatch):
    from pipeline import mcp_doc_graph as tools
    conn, path, data = artifact
    data['catalogue'] = {'use_rollup': {'log_use_count': 50, 'recent_uses': [{'used_for': 'x' * 7000}]}}
    path.write_text(json.dumps(data), encoding='utf-8')
    load_nodes_file(path, conn); conn.commit()
    monkeypatch.setattr(tools, 'DB_PATH', path.parent / 'paper.sqlite')
    out = tools._TOOLS['get_section']('Full study', section_id=1, max_chars=500)
    assert len(json.dumps(out, ensure_ascii=True)) <= 8000
    assert out['provenance']['catalogue_history_available'] is True
    assert 'catalogue' not in out['provenance']['coverage']


def test_standalone_paper_result_preserves_page_provenance_with_authorship(artifact, monkeypatch):
    from pipeline import mcp_doc_graph as tools
    conn, path, _ = artifact
    load_nodes_file(path, conn); conn.commit()
    monkeypatch.setattr(tools, 'DB_PATH', path.parent / 'paper.sqlite')
    section = tools._TOOLS['get_section']('doc:1', heading='Study')
    assert section['authorship'] == 'third_party'
    assert section['provenance']['location']['page_start'] == 1
    assert section['provenance']['representation']['conversion']['authorship'] == 'generated'
