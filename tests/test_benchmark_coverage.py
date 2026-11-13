"""The benchmark keeps bounded delivery evidence instead of full tool text."""
import ast
import json
from pathlib import Path
import re


def recorder():
    source = Path(__file__).resolve().parents[1] / 'scripts/librarian_harness.py'
    node = next(n for n in ast.parse(source.read_text(encoding='utf-8')).body
                if isinstance(n, ast.FunctionDef) and n.name == 'call_record')
    namespace = {'json': json, 're': re}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['call_record']


def test_per_call_keeps_coverage_without_source_text():
    row = dict(entity_id='entity:abc', start_line=2, end_line=5, truncated=True, sha256='a' * 64)
    body = {'coverage': [row], 'coverage_truncated': False,
            'result': {'data': {'chunks': [{'text': 'PRIVATE-SOURCE-TEXT'}]}}}
    saved = recorder()('get_entity_content', {}, {'content': json.dumps(body)})
    assert saved['coverage'] == [row] and saved['coverage_truncated'] is False
    assert 'PRIVATE-SOURCE-TEXT' not in json.dumps(saved)


def test_untrusted_metadata_is_bounded_and_never_misreported_as_complete():
    row = dict(entity_id='entity:abc', start_line=None, end_line=None, truncated=False, sha256='b' * 64)
    saved = recorder()('search_entities', {}, {'content': json.dumps({'coverage': [row] * 40})})
    assert len(saved['coverage']) == 16 and saved['coverage_truncated']
    bad = recorder()('search_entities', {}, {'coverage': [{'text': 'untrusted'}]})
    assert bad['coverage'] == [] and bad['coverage_truncated']
    missing = recorder()('search_entities', {}, {'coverage': [
        {'entity_id': 'entity:a', 'sha256': 'a' * 64, 'truncated': False}]})
    assert missing['coverage'] == [] and missing['coverage_truncated']
