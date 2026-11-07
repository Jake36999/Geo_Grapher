"""Independent P5.1/KG1 positive and false-exact regression oracles."""
import json
import pytest
from conftest import calls
from geographer.claims import validate_details

def details(g,subtype='calls'):
    return [(g.relationships[e.relationship_id],json.loads(e.details_json)) for e in g.evidence.values()
            if g.relationships[e.relationship_id].subtype==subtype]

def test_async_try_and_suspension_do_not_taint_unmodified_imports(extract):
    g,_,_=extract({'lib.py':'def target(): pass\n','app.py':'''from lib import target
async def run(flag):
 try:
  target()
  await flag
  target()
 except Exception:
  target()
def gen():
 yield 1
 target()
'''})
    assert len([x for x in calls(g) if x[2]=='exact'])==4
    assert all(v['reason_code']=='UNAMBIGUOUS_IMPORT_MEMBER' for r,v in details(g))

def test_local_branch_rebinding_keeps_import_candidate(extract):
    g,_,_=extract({'lib.py':'def target(): pass\n','app.py':'''def run(flag):
 from lib import target
 if flag: target=flag
 target()
'''})
    assert ('app.py.run','lib.py.target','candidate') in calls(g)
    assert any(d['reason_code']=='CFG_BRANCH_REBOUND' for r,d in details(g))

def test_recursive_imported_module_class_and_deep_members(extract):
    g,_,_=extract({'pkg/__init__.py':'from . import utils\n','pkg/utils.py':'''def work(): pass
class Store:
 class Nested:
  @staticmethod
  def open(): pass
''','app.py':'''from pkg import utils
from pkg.utils import Store
def run():
 utils.work()
 Store.Nested.open()
 Store.Nested.missing()
'''})
    assert ('app.py.run','pkg/utils.py.work','exact') in calls(g)
    assert ('app.py.run','pkg/utils.py.Store.Nested.open','candidate') in calls(g)
    assert any(t=='Store.Nested.missing' and s=='unresolved' for _,t,s in calls(g))

def test_exported_unknown_precedes_same_named_submodule(extract):
    g,_,_=extract({'pkg/__init__.py':'utils=0\n','pkg/utils.py':'def work(): pass\n','app.py':'from pkg import utils\nutils.work()\n'})
    assert all(s=='unresolved' for _,_,s in calls(g))

def test_c3_diamond_receivers_and_override_alternatives(extract):
    g,_,_=extract({'a.py':'''class A:
 def work(this): pass
 def run(this): this.work()
class B(A):
 def work(this): pass
class C(A): pass
class D(B,C):
 @classmethod
 def build(kls): kls.work()
'''})
    found=calls(g)
    assert ('a.py.A.run','a.py.A.work','candidate') in found
    assert ('a.py.A.run','a.py.B.work','candidate') in found
    assert ('a.py.D.build','a.py.B.work','candidate') in found
    assert any(d['mro_provenance'] and d['reason_code']=='POLYMORPHIC_MRO_CANDIDATE' for _,d in details(g))
    d=next(e.entity_id for e in g.entities.values() if e.qualified_name=='a.py.D')
    assert [g.entities[x].qualified_name for x in g.analyses['mro:'+d]['result']['mro']]==['a.py.D','a.py.B','a.py.C','a.py.A']
    inherits=[r for r in g.relationships.values() if r.subtype=='inherits']
    assert len(inherits)==4 and all(r.resolution_status=='exact' for r in inherits)

@pytest.mark.parametrize('header,body',[
 ('class C:','@staticmethod\n def run(obj): obj.method()'),
 ('class C:','def run(self):\n  self=0\n  self.method()'),
])
def test_static_or_reassigned_receiver_does_not_guess_target(extract,header,body):
    g,_,_=extract({'a.py':header+'\n def method(self): pass\n '+body+'\n'})
    assert all(s=='unresolved' for _,_,s in calls(g))

def test_inconsistent_and_dynamic_mro_are_reported_not_exact_dispatch(extract):
    g,_,_=extract({'a.py':'''class X: pass
class Y: pass
class A(X,Y): pass
class B(Y,X): pass
class Z(A,B):
 def run(self): self.missing()
class Dynamic(factory()): pass
'''})
    z=next(e.entity_id for e in g.entities.values() if e.qualified_name=='a.py.Z')
    assert g.analyses['mro:'+z]['result']['status']=='unsupported_or_inconsistent'
    assert not any(s=='exact' for _,_,s in calls(g))

@pytest.mark.parametrize('expression',['(target := other, target())','(target := other) and target()','target((target := other))'])
def test_walrus_evaluation_order_never_resolves_new_callee_as_old_exact(extract,expression):
    g,_,_=extract({'a.py':f'def target(*args): pass\ndef run(other):\n {expression}\n'})
    # Walrus makes target a local for the whole function, including callee load.
    assert not any(s=='exact' for _,_,s in calls(g))

def test_loaded_local_callee_is_not_changed_by_argument_walrus(extract):
    g,_,_=extract({'a.py':'def run(other):\n def target(*args): pass\n target((target := other))\n target()\n'})
    assert ('a.py.run','a.py.run.target','exact') in calls(g)
    assert len([x for x in calls(g) if x[2]=='exact'])==1

def test_handler_cleanup_and_closure_mutation_not_exact(extract):
    g,_,_=extract({'a.py':'''def target(): pass
def run():
 try: pass
 except Exception as target: pass
 target()
def outer():
 def callback(): pass
 def inner(): callback()
 callback=0
 inner()
'''})
    assert not any(src=='a.py.run' and s=='exact' for src,_,s in calls(g))
    assert not any(src=='a.py.outer.inner' and s=='exact' for src,_,s in calls(g))

@pytest.mark.parametrize('mutation',['utils.work=0','del utils.work','setattr(utils,"work",0)'])
def test_member_module_monkeypatch_is_cross_file_conservative(extract,mutation):
    g,_,_=extract({'pkg/__init__.py':'','pkg/utils.py':'def work(): pass\ndef run(): work()\n',
                   'patch.py':'from pkg import utils\n'+mutation+'\n',
                   'app.py':'from pkg import utils\ndef run(): utils.work()\n'})
    assert not any(s=='exact' and t=='pkg/utils.py.work' for _,t,s in calls(g))

def test_occurrence_shared_by_alternatives_and_exact_original_unicode_bytes(extract):
    source='# coding: utf-8\r\ndef café(): pass\r\ndef run(flag):\r\n if flag: café=0\r\n café()\r\n café()\r\n'
    g,_,_=extract({'a.py':source})
    ids=[]
    for r,d in details(g):
        validate_details(d);span=d['source_span'];raw=source.encode()
        assert raw[span['start_byte']:span['end_byte']].decode()=='café()'
        assert d['syntax']['text']=='café()'
        ids.append(d['occurrence_id'])
    assert len(ids)==2 and len(set(ids))==2

def test_builtin_parameter_and_external_import_causes_are_distinct(extract):
    g,_,_=extract({'a.py':'import missing_pkg\nprint(1)\nmissing_pkg.run()\ndef f(print): print()\n'})
    reasons=[d['reason_code'] for _,d in details(g)]
    assert reasons.count('BUILTIN_SYMBOL')==1
    assert 'EXTERNAL_PACKAGE_UNINDEXED' in reasons
    assert 'UNSUPPORTED_ANALYSIS' in reasons

def test_tree_sitter_claim_is_syntax_not_a_python_proof(extract):
    g,_,_=extract({'a.js':'function run() { missing(); }'})
    assert all(d['reason_code']=='TREESITTER_SYNTACTIC_ONLY' and d['claim_kind']=='syntax' for _,d in details(g))

def test_shared_visibility_presets_exclude_only_advertised_internal_scope(extract):
    from geographer.visibility import visibility_filter
    from geographer.analysis import selected_relationships
    g,_,_=extract({'a.py':'class C:\n def method(self): pass\n def run(self): self.method()\n',
                   'b.js':'function run() { missing(); }'})
    internal=list(selected_relationships(g,visibility_filter('internal_candidates')))
    assert internal and all(not g.entities[r.target_id].is_external for r in internal)
    assert any(r.resolution_status=='candidate' for r in internal)
    assert any(g.entities[r.target_id].is_external for r in selected_relationships(g,visibility_filter('all_uncertainty')))
    assert visibility_filter('exact')['resolution_statuses']==['exact']

def test_candidate_alternatives_share_one_target_independent_occurrence(extract):
    from geographer.source import Repository
    other=Repository('other','r',{'lib.py':b'def target(): pass\n'},resolution_group='linked')
    g,_,_=extract({'lib.py':'def target(): pass\n','app.py':'from lib import target\ntarget()\n'},others=[other],resolution_group='linked')
    claims=details(g)
    assert len(claims)==2
    assert len({d['occurrence_id'] for _,d in claims})==1
    assert all(d['reason_code']=='AMBIGUOUS_MODULE_ROOT' and len(d['alternatives'])==2 for _,d in claims)

def test_nonclass_base_is_not_an_exact_inheritance_conclusion(extract):
    g,_,_=extract({'a.py':'def base(): pass\nclass C(base): pass\n'})
    assert all(r.resolution_status!='exact' for r in g.relationships.values() if r.subtype=='inherits')

def test_known_early_module_call_downgrades_later_declarations_through_helpers(extract):
    g,_,_=extract({'a.py':'def helper(): late()\ndef run(): helper()\nrun()\ndef late(): pass\n'})
    assert ('a.py.helper','a.py.late','candidate') in calls(g)
    assert ('a.py.run','a.py.helper','exact') in calls(g)
    nested,_,_=extract({'a.py':'def run():\n def inner(): late()\n inner()\nrun()\ndef late(): pass\n'})
    assert ('a.py.run.inner','a.py.late','candidate') in calls(nested)

@pytest.mark.parametrize('raw',[
    b'\xef\xbb\xbfdef f(): pass\nf()\n',
    '# coding: latin-1\ndef caf\u00e9(): pass\ncaf\u00e9()\n'.encode('latin-1'),
])
def test_original_encoded_source_byte_spans(extract,raw):
    g,_,_=extract({'a.py':raw})
    for _,d in details(g):
        span=d['source_span'];snippet=raw[span['start_byte']:span['end_byte']]
        assert snippet in {b'f()',b'caf\xe9()'}

def test_noncallable_class_slot_masks_inherited_method(extract):
    g,_,_=extract({'a.py':'class A:\n def work(self): pass\nclass B(A):\n work=0\n def run(self): self.work()\n'})
    assert ('a.py.B.run','self.work','unresolved') in calls(g)
    assert not any(src=='a.py.B.run' and target=='a.py.A.work' for src,target,_ in calls(g))
