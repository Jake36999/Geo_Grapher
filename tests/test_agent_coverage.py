"""Coverage describes bytes returned, never an undisclosed enclosing source span."""
import hashlib
import json
from geographer.agent_coverage import coverage_metadata


def test_content_ranges_hash_exact_returned_bytes_and_preserve_gaps():
    data = {'entity_id': 'entity:a', 'chunks': [
        {'source': {'start_line': 1, 'end_line': 2}, 'text': 'one\r\ntwo\r\n'},
        {'source': {'start_line': 3, 'end_line': 3}, 'text': 'three\n'},
        {'source': {'start_line': 6, 'end_line': 6}, 'text': 'six\n'},
    ], 'completeness': {'truncated': True}}
    out = coverage_metadata('get_entity_content', data, (1, 6))
    assert out['coverage'] == [
        dict(entity_id='entity:a', start_line=1, end_line=3, truncated=True,
             sha256=hashlib.sha256(b'one\r\ntwo\r\nthree\n').hexdigest()),
        dict(entity_id='entity:a', start_line=6, end_line=6, truncated=True,
             sha256=hashlib.sha256(b'six\n').hexdigest())]
    assert out['coverage_truncated'] is False


def test_complete_requested_subrange_and_metadata_bound():
    data = {'entity_id': 'entity:a', 'chunks': [
        {'source': {'start_line': n, 'end_line': n}, 'text': str(n)} for n in range(1, 41, 2)],
        'completeness': {'truncated': True}}
    out = coverage_metadata('get_entity_content', data, (1, 40))
    assert len(out['coverage']) == 16 and out['coverage_truncated'] is True
    data['chunks'] = [{'source': {'start_line': 20, 'end_line': 20}, 'text': 'a'}]
    data['completeness']['truncated'] = False
    out = coverage_metadata('get_entity_content', data, (20, 20))
    assert out['coverage'][0]['truncated'] is False
    assert coverage_metadata('get_entity_content', {'chunks': []}, None)['coverage'] == []


def test_missing_source_lines_are_truncated_even_without_upstream_flag():
    data = {'entity_id': 'entity:a', 'chunks': [
        {'source': {'start_line': 2, 'end_line': 2}, 'text': 'only middle\n'}],
        'completeness': {'truncated': False}}
    assert coverage_metadata('get_entity_content', data, (1, 5))['coverage'][0]['truncated']


def test_search_hashes_actual_metadata_without_claiming_source_delivery():
    node = {'entity_id': 'entity:a', 'qualified_name': 'm.py.A',
            'source': {'start_line': 10, 'end_line': 70}}
    hit = {'entity_id': 'entity:a', 'score': 1}
    data = {'nodes': [node], 'hits': [hit], 'completeness': {'truncated': False}}
    out = coverage_metadata('search_entities', data, None)
    row = out['coverage'][0]
    assert row['start_line'] is None and row['end_line'] is None
    raw = json.dumps({'node': node, 'hit': hit}, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    assert row['sha256'] == hashlib.sha256(raw.encode()).hexdigest()
    assert row['entity_id'] == 'entity:a' and not row['truncated']
