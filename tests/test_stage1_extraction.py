import ast
import json

from geographer.source import Repository
from geographer.scopes import ScopeIndex
from geographer.normalize import normalized_ast
from conftest import calls


def test_direction_identity_parallel_sites_and_round_trip(extract):
    graph, store, report = extract({"a.py": "def f(): pass\ndef g():\n f()\n f()\ng()\n", "b.py": "def f(): pass\n"},
                                 others=[Repository("second", "r2", {"a.py": b"def f(): pass\ndef g(): f()\n"})])
    assert calls(graph).count(("a.py.g", "a.py.f", "exact")) == 3
    first = [r for r in graph.relationships.values() if graph.entities[r.source_subject_id].repo_id == "repo"]
    assert len(first) == 3
    assert all(r.direction == "directed" for r in first)
    fs = [e for e in graph.entities.values() if e.kind == "function" and e.qualified_name.endswith(".f")]
    assert len({e.entity_id for e in fs}) == 3
    from geographer.store import SnapshotStore
    with SnapshotStore() as reloaded:
        sid = reloaded.import_snapshot(store.export(report["snapshot_id"]))
        assert reloaded.export(sid) == store.export(sid)
        assert calls(reloaded.graph(sid)) == calls(graph)


def test_cross_repository_imports_and_reexports(extract):
    lib = Repository("library", "r2", {"pkg/__init__.py": b"from .core import target\n", "pkg/core.py": b"def target(): pass\n"},resolution_group="linked")
    graph, _, _ = extract({"app.py": "from pkg import target\nimport pkg.core as core\ndef run():\n target()\n core.target()\n"}, others=[lib], resolution_group="linked")
    assert calls(graph).count(("app.py.run", "pkg/core.py.target", "exact")) == 2
    for r in graph.relationships.values():
        assert r.family == "static"
        assert graph.entities[r.source_id].kind not in {"fragment", "document"}
    assert {r.subtype for r in graph.relationships.values()} >= {"calls", "imports", "imports_from"}


def test_duplicate_module_roots_remain_ambiguous(extract):
    lib = Repository("other", "r", {"lib.py": b"def target(): pass\n"},resolution_group="linked")
    graph, _, _ = extract({"lib.py": "def target(): pass\n", "app.py": "from lib import target\ntarget()\n"}, others=[lib], resolution_group="linked")
    cs = [r for r in graph.relationships.values() if r.subtype == "calls"]
    assert len(cs) == 2
    assert all(r.resolution_status == "candidate" for r in cs)
    assert {graph.entities[r.target_subject_id].repo_id for r in cs} == {"repo", "other"}


def test_shadowing_and_execution_order(extract):
    graph, _, _ = extract({"a.py": "target()\ndef target(): pass\ndef param(target): target()\ndef local():\n target()\n target=1\ndef alias():\n other=target\n other()\n"})
    assert len(calls(graph)) == 4
    assert all(status == "unresolved" for _, _, status in calls(graph))


def test_cfg_loop_fixed_point_and_break_continue(extract):
    graph, _, _ = extract({"a.py": "def run(flag):\n def target(): pass\n while flag:\n  target=0\n  if flag: continue\n  break\n target()\n"})
    assert [(source, target) for source, target, status in calls(graph) if status == "exact"] == []
    assert any(status == "candidate" for _, _, status in calls(graph))
    # Independent CFG assertion: loop header gets both definition and assignment.
    from geographer.extract import PythonExtractor
    ex = PythonExtractor([Repository("x", "r", {"a.py": b"def run(flag):\n x=0\n while flag:\n  x=1\n x()\n"})])
    ex.extract()
    scope = next(s for s in ex.units[0].scopes.scopes if s.table.get_name() == "run")
    cfg = ex.units[0].cfgs[scope]
    assert cfg.iterations > len(cfg.blocks)


def test_decorators_dynamic_dispatch_and_rebinding(extract):
    graph, _, _ = extract({"a.py": "def decorate(f): return f\n@decorate\ndef wrapped(): pass\ndef plain(): pass\ndef run(obj):\n wrapped()\n obj.method()\n getattr(obj,'method')()\n plain()\ndef change():\n global plain\n plain=1\n"})
    assert ("a.py.run", "a.py.wrapped", "candidate") in calls(graph)
    assert ("a.py.run", "a.py.plain", "candidate") in calls(graph)
    assert not any(status == "exact" for _, _, status in calls(graph))
    assert len([r for r in graph.relationships.values() if r.subtype == "calls"]) == 5


def test_reexport_cycle_is_not_an_exact_target(extract):
    graph, _, report = extract({"pkg/__init__.py": "from .a import f\n", "pkg/a.py": "from .b import f\n", "pkg/b.py": "from .a import f\n", "app.py": "from pkg import f\nf()\n"})
    assert not report["parse_failures"]["repo"]
    assert all(status == "unresolved" for _, _, status in calls(graph))


def test_scope_atoms_and_documentary_hyperedge(extract):
    graph, _, _ = extract({"a.py": 'def alpha():\n """alpha uses beta"""\n beta()\ndef beta(): pass\n# alpha beta\n',
                           "notes.md": "# Architecture\n\nalpha discusses beta\n"})
    assert graph.incidences
    groups = {}
    for incidence in graph.incidences:
        groups.setdefault(incidence["incidence_id"], set()).add(incidence["entity_id"])
    assert any(len(group) >= 2 for group in groups.values())
    assert any(e.kind == "scope_atom" for e in graph.entities.values())
    parents = {e.parent_id for e in graph.entities.values()}
    for r in graph.relationships.values():
        assert r.source_id not in parents and r.target_id not in parents
        assert r.family == "static"
    alpha = next(e for e in graph.entities.values() if e.kind == "function" and e.qualified_name.endswith(".alpha"))
    assert alpha.ast_body_hash is not None


def normal(source):
    tree = ast.parse(source, type_comments=True)
    scopes = ScopeIndex(tree, source, "fixture.py")
    return normalized_ast(tree.body[0], scopes)


def test_normalization_alpha_renaming_docstrings_and_literals():
    a = normal('def one(arg):\n """one"""\n x=arg+1\n return x\n')
    b = normal('def two(arg):\n # comment\n """two"""\n renamed=arg+1\n return renamed\n')
    assert a == b
    assert a != normal('def one(changed):\n x=changed+1\n return x\n')
    assert a != normal('def one(arg):\n x=arg+2\n return x\n')
    assert normal('def f():\n return "runtime"\n') != normal('def f():\n return "different"\n')
    assert normal('def f():\n return foo()\n') != normal('def f():\n return bar()\n')


def test_normalization_closure_reflection_and_call_bindings():
    assert normal('def f():\n x=1\n def g(): return x\n return g\n') != normal('def f():\n y=1\n def g(): return y\n return g\n')
    assert normal('def f():\n x=1\n return locals()\n') != normal('def f():\n y=1\n return locals()\n')
    assert normal('def f():\n cb=1\n return cb()\n') != normal('def f():\n other=1\n return other()\n')


def test_hidden_scopes_comprehensions_lambdas_and_nonlocal(extract):
    source = "def target(): pass\ndef outer(xs):\n captured=1\n def nested():\n  nonlocal captured\n  captured=2\n  return target()\n result=[target() for x in xs if target()]\n callback=lambda: target()\n return callback\n"
    graph, _, report = extract({"a.py": source})
    assert not report["parse_failures"]["repo"]
    assert len(calls(graph)) == 4


def test_parse_failures_and_source_do_not_execute(extract, tmp_path):
    marker = tmp_path / "executed"
    source = f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n"
    graph, store, report = extract({"valid.py": source, "bad.py": "def f(:\n"})
    assert not marker.exists()
    assert len(report["parse_failures"]["repo"]) == 1
    assert store.connection.execute("SELECT status FROM snapshot_sets").fetchone()[0] == "complete"
    source_records = [r for r in graph.analyses.values() if r["algorithm_version"] == "source-bytes-v1"]
    assert len(source_records) == 2


def test_same_start_nested_calls_are_distinct(extract):
    graph, _, _ = extract({"a.py": "def factory(): pass\nfactory()()\n"})
    assert len(calls(graph)) == 2


def test_known_global_deletion_and_module_patches_are_not_exact(extract):
    graph, _, _ = extract({'lib.py': 'def f(): pass\n', 'app.py': 'import lib\nlib.f=0\n',
        'run.py': 'import lib\ndef f(): pass\ndef change():\n global f\n del f\ndef run():\n f()\n lib.f()\n lib()\n'})
    found = calls(graph)
    assert ('run.py.run','run.py.f','candidate') in found
    assert ('run.py.run','lib.py.f','candidate') in found
    assert not any(status=='exact' for _,_,status in found)


def test_exported_symbol_precedes_same_named_submodule(extract):
    graph, _, _ = extract({'pkg/__init__.py': 'def f(): pass\n', 'pkg/f.py': 'pass\n',
                           'app.py': 'from pkg import f\nf()\n'})
    assert ('app.py','pkg/__init__.py.f','exact') in calls(graph)


def test_test_flags_are_segment_based(extract):
    graph, _, _ = extract({"tests/a.py": "def f(): pass\n", "contest/a.py": "def f(): pass\n", "latest/a.py": "def f(): pass\n"})
    flags = {e.rel_path: e.is_test for e in graph.entities.values() if e.kind == "function"}
    assert flags == {"tests/a.py": 1, "contest/a.py": 0, "latest/a.py": 0}


def test_tree_sitter_fallback_is_candidate_only(extract):
    graph, _, report = extract({"a.js": "function run() { external(); }\n"})
    assert not report["parse_failures"]["repo"]
    assert any(e.kind == "function" and e.language == "javascript" for e in graph.entities.values())
    assert all(status == "candidate" for _, _, status in calls(graph))
    assert any(v["result"].get("resolver_capability") == "syntactic_candidate_only" for v in graph.analyses.values())


def test_typescript_tsx_and_fallback_flag_inheritance(extract):
    graph,_,report=extract({'tests/a.ts':'function run(x: number): number { return external(x); }',
                           'vendor/view.tsx':'class Panel { render() { return <div>{render()}</div>; } }'})
    assert not report['parse_failures']['repo']
    assert any(e.kind=='function' and e.language=='typescript' for e in graph.entities.values())
    assert all(e.is_test for e in graph.entities.values() if e.rel_path=='tests/a.ts')
    assert all(e.is_vendor for e in graph.entities.values() if e.rel_path=='vendor/view.tsx')
    assert all(status=='candidate' for _,_,status in calls(graph))
