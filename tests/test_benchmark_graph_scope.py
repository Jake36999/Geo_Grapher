"""Wrong-graph accounting includes every explicit graph reference."""
import ast
from pathlib import Path


def helper():
    source=Path(__file__).resolve().parents[1]/'scripts/librarian_harness.py'
    node=next(n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='requested_graphs')
    namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
    return namespace['requested_graphs']


def test_arrays_and_comparison_fields_cannot_hide_wrong_graph_calls():
    resolve=helper();labels={'local':'g-local','other':'g-other'}
    assert resolve(dict(graph_ids=['local','other']),labels,['g-local'])==['g-local','g-other']
    assert resolve(dict(code_graph='local',paper_graph='other'),labels,['g-local'])==['g-other','g-local']
    assert resolve(dict(graph_id='mistyped'),labels,['g-local'])==['mistyped']


def test_implicit_pinned_scope_and_invalid_field_types_are_recorded_safely():
    resolve=helper()
    assert resolve({}, {}, ['g-local'])==['g-local']
    assert resolve(dict(graph_id={'bad':'type'}),{},['g-local'])==['g-local']
