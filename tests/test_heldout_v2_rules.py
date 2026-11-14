import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('v2rules',Path(__file__).parents[1]/'scripts/heldout_v2_rules.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_decorative_comment_cannot_qualify():
    assert not r.meaningful('-'*100+'\nRule identifiers\n'+'-'*100)
    assert r.meaningful('When an upload request omits its maximum capacity this constant supplies the fallback window in bytes so callers have a predictable bounded value instead of an unlimited allocation.')

def test_constant_question_must_request_a_constant_and_never_expose_key():
    item=dict(category='constants',equivalence_markers=['RUNNER','runner_entry'])
    assert r.validate_question(item,'Which function implements the sandbox job by reading its file and invoking the chosen module? Cite the source.')
    assert not r.validate_question(item,'Which named constant holds the sandbox runner that reads a job file, imports its module and calls its function? Cite the source.')
    assert 'identifier_leak' in r.validate_question(item,'Which named constant is RUNNER and what does the sandbox job define for its function? Cite the source.')

def test_both_reviewers_must_confirm_all_semantic_properties():
    good=dict(accept=True,grammatical=True,own_documentation=True,unambiguous_top20=True,equivalence_correct=True)
    assert r.review_approved(good)
    assert not r.review_approved({**good,'equivalence_correct':False})
    assert not r.review_approved({'accept':True})

def test_static_adjacency_is_not_inseparability_evidence():
    assert not r.partner_documented('Controls the upload capacity.','upload.py.send_upload')
    assert r.partner_documented('This capacity is applied by send_upload before a job is queued.','upload.py.send_upload')

def test_rule_alias_must_be_the_defined_subject_not_an_incidental_reference():
    assert r.defined_rule_id('R123: validates the deterministic flag.','functions')=='R123'
    assert r.defined_rule_id('Used when rule R123 needs a default.','functions') is None
    assert r.defined_rule_id('R123: external policy used here.','constants') is None
