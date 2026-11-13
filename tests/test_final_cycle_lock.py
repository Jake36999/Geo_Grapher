"""A final-cycle marker prevents dispatch even if someone invokes the runner again."""
import importlib.util
from pathlib import Path
import pytest


def test_closed_final_cycle_never_dispatches_or_changes_marker(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'scripts/run_wave4_final_code_cycle.py'
    spec = importlib.util.spec_from_file_location('final_cycle', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    closed = tmp_path / 'closed.json'
    closed.write_text('{"status":"closed"}')
    monkeypatch.setattr(module, 'CLOSED', closed)
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: pytest.fail('must not dispatch'))
    with pytest.raises(SystemExit, match='closed or already started'):
        module.main()
    assert closed.read_text() == '{"status":"closed"}'
