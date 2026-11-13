"""Direct evaluator entry points cannot construct a paid provider without readiness."""
import ast
from pathlib import Path
import pytest

def test_provider_construction_is_blocked_before_network_or_credentials(monkeypatch):
    root=Path(__file__).parents[1];monkeypatch.syspath_prepend(str(root/'scripts'))
    source=root/'scripts/librarian_harness.py'
    node=next(n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='provider_for')
    class Forbidden:
        def from_settings(self,*a,**kw):pytest.fail('No provider before dry-run readiness')
    namespace=dict(PAID_PREFLIGHT=None,PAID_CONFIG=None,providers=Forbidden())
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
    with pytest.raises(ValueError,match='mandatory'):namespace['provider_for']('unreachable-model')
