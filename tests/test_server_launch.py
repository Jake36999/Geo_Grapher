"""Servers refuse to start on an unpinned MCP major version, with an actionable message."""
import pytest
from geographer import cli


@pytest.mark.parametrize('found,ok', [('1.30.0', True), ('2.2.0', False), (None, False)])
def test_server_start_requires_pinned_mcp_major(monkeypatch, found, ok):
    import importlib.metadata as metadata
    def fake(name):
        if found is None:raise metadata.PackageNotFoundError(name)
        return found
    monkeypatch.setattr(metadata, 'version', fake)
    if ok:
        cli.require_pinned_mcp()
    else:
        with pytest.raises(SystemExit, match='wheel-env'):cli.require_pinned_mcp()
