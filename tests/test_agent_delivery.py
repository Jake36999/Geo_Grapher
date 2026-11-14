"""Actual flat response coverage participates in the complete response cap."""
import hashlib
import json
from test_task_packets import packet_world
from geographer.agent_requests import call_code
from geographer.tokens import TokenCounter


def test_flat_content_and_search_report_actual_coverage(packet_world):
    cat, router, gid, ids = packet_world
    router.max_result_chars = 7500
    found = call_code(router, 'search_entities', {'graph_id': 'code', 'query': 'm.py.f'})
    assert found['coverage'] and found['coverage'][0]['start_line'] is None
    out = call_code(router, 'get_entity_content', {'graph_id': 'code', 'entity_id': ids['f']})
    chunks = out['result']['data']['chunks']
    assert out['coverage'] == [dict(entity_id=ids['f'], start_line=1, end_line=2, truncated=False,
        sha256=hashlib.sha256(''.join(c['text'] for c in chunks).encode()).hexdigest())]
    for result in (found, out):
        assert len(json.dumps(result, ensure_ascii=False)) <= 7500
        assert result['routing_budget']['used_tokens'] == TokenCounter().count(result)
