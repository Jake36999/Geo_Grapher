"""P5.0 additive contract gates; original contracts stay byte-identical."""
import hashlib
import json
from pathlib import Path
import jsonschema
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_original_engineering_baseline_unchanged():
    baseline=json.loads((ROOT/'contracts/v1.1/baseline-digests.json').read_text())
    assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected for path,expected in baseline.items())

def test_v11_all_operations_and_schema_provenance():
    schema=json.loads((ROOT/'contracts/v1.1/generated/geographer.wire.schema.json').read_text())
    assert schema['contract_sha256']==hashlib.sha256((ROOT/'contracts/v1.1/geographer.wire.d.ts').read_bytes()).hexdigest()
    assert set(schema['operations'])=={'search_entities','get_architecture_context','inspect_relationship_witnesses','get_entity_content','find_dependants','check_architecture','find_similar_code','viewport_frame'}
    jsonschema.Draft202012Validator.check_schema(schema)
    node=schema['$defs']['NodeRecord']['properties']
    assert {'summary','group_preview','is_synthetic'}<=node.keys()
    assert not {'entity_id','ast_body_hash','wl_3hop_hash'}&node.keys()
    assert 'witness_cursor' not in schema['$defs']['RelationshipSummary']['properties']

def test_preview_and_summary_bounds_are_executable():
    schema=json.loads((ROOT/'contracts/v1.1/generated/geographer.wire.schema.json').read_text())
    def validator(name):return jsonschema.Draft202012Validator({'$ref':'#/$defs/'+name,'$defs':schema['$defs']})
    summary=dict(signature='def f(x):',doc_gist='Returns an item.',doc_handle=None,truncated=False)
    validator('NodeSummary').validate(summary)
    with pytest.raises(jsonschema.ValidationError): validator('NodeSummary').validate({**summary,'doc_gist':'x'*141})
    props=schema['$defs']['RelationshipSummary']['properties']
    assert props['witness_preview']['maxItems']==3
    assert schema['$defs']['GroupPreview']['properties']['top_exemplars']['maxItems']==5
    with pytest.raises(jsonschema.ValidationError): validator('NodeSummary').validate({**summary,'unapproved':1})
    with pytest.raises(jsonschema.ValidationError): validator('GroupPreview').validate(dict(kind_counts={'function':-1},top_exemplars=[],exemplars_complete=False))
    with pytest.raises(jsonschema.ValidationError): validator('GroupPreview').validate(dict(kind_counts={'function':2.5},top_exemplars=[],exemplars_complete=False))
