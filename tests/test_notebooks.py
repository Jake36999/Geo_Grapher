"""Jupyter notebook extraction with stdlib json only (ipynb-v1)."""
import ast
import hashlib
import json

import pytest

from geographer.notebooks import CellSpan, NotebookFormatError, NotebookSource, to_virtual_source

NB = {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": [
    {"cell_type": "markdown", "metadata": {}, "source": ["# Solver\n", "Uses `step` to advance.\n"]},
    {"cell_type": "code", "metadata": {}, "execution_count": 1,
     "outputs": [{"output_type": "stream", "text": "SECRET OUTPUT"}],
     "source": ["%matplotlib inline\n", "import math\n", "def step(x):\n", "    return math.sqrt(x)\n"]},
    {"cell_type": "code", "metadata": {}, "execution_count": 2, "outputs": [], "source": "!pip install foo\nprint(step(4))\n"},
    {"cell_type": "code", "metadata": {}, "execution_count": 3, "outputs": [], "source": ["def broken(:\n"]},
    {"cell_type": "raw", "metadata": {}, "source": "raw ) text ("}]}


def raw(nb=NB):
    return json.dumps(nb).encode("utf-8")


def test_virtual_source_is_valid_python_and_comments_magics():
    src = to_virtual_source(raw(), "nb.ipynb")
    assert isinstance(src, NotebookSource)
    ast.parse(src.python_text)
    assert src.python_text.endswith("\n")
    assert "# %matplotlib inline" in src.python_text and "# !pip install foo" in src.python_text
    assert "SECRET OUTPUT" not in src.python_text
    assert [c.cell_type for c in src.cells] == ["markdown", "code", "code", "code", "raw"]
    assert src.notebook_sha256 == hashlib.sha256(raw()).hexdigest()


def test_headers_and_cell_spans_are_one_based_and_point_at_the_header():
    src = to_virtual_source(raw(), "nb.ipynb")
    lines = src.python_text.split("\n")
    for c in src.cells:
        assert isinstance(c, CellSpan) and 1 <= c.start_line <= c.end_line
        assert lines[c.start_line - 1].startswith(f"# %% [cell {c.index}] {c.cell_type}")
    code = src.cells[1]
    body = lines[code.start_line:code.end_line]
    assert body == ["# %matplotlib inline", "import math", "def step(x):", "    return math.sqrt(x)"]
    assert [c.index for c in src.cells] == [0, 1, 2, 3, 4]
    assert all(a.end_line < b.start_line for a, b in zip(src.cells, src.cells[1:]))


def test_markdown_and_raw_cells_are_commented_out():
    src = to_virtual_source(raw(), "nb.ipynb")
    lines = src.python_text.split("\n")
    md = src.cells[0]
    assert lines[md.start_line:md.end_line] == ["# # Solver", "# Uses `step` to advance."]
    rw = src.cells[4]
    assert all(l.startswith("#") for l in lines[rw.start_line - 1:rw.end_line])


def test_unparsed_code_cell_is_commented_with_marked_header():
    src = to_virtual_source(raw(), "nb.ipynb")
    lines = src.python_text.split("\n")
    bad = src.cells[3]
    assert lines[bad.start_line - 1] == "# %% [cell 3] code (unparsed)"
    assert lines[bad.start_line] == "# def broken(:"
    assert src.unparsed == (3,)
    assert "def step(x):" in src.python_text  # the rest survives


def test_cell_text_returns_the_original_cell_text():
    src = to_virtual_source(raw(), "nb.ipynb")
    assert src.cell_text(0) == "# Solver\nUses `step` to advance.\n"
    assert src.cell_text(2) == "!pip install foo\nprint(step(4))\n"


@pytest.mark.parametrize("data", [
    b"{not json",
    json.dumps({"nbformat": 3, "cells": []}).encode(),
    json.dumps({"nbformat": 4}).encode(),
    json.dumps({"nbformat": 4, "cells": "nope"}).encode(),
    json.dumps([1, 2]).encode(),
])
def test_invalid_notebooks_raise_format_error(data):
    with pytest.raises(NotebookFormatError):
        to_virtual_source(data, "bad.ipynb")


def test_empty_cell_and_missing_trailing_newline():
    nb = {"nbformat": 4, "cells": [{"cell_type": "code", "source": []},
                                   {"cell_type": "code", "source": "x = 1"}]}
    src = to_virtual_source(raw(nb), "e.ipynb")
    ast.parse(src.python_text)
    assert src.python_text.endswith("x = 1\n")
    assert src.cells[0].start_line == src.cells[0].end_line == 1


def test_deterministic():
    assert to_virtual_source(raw(), "nb.ipynb") == to_virtual_source(raw(), "nb.ipynb")


# --- integration: the real ingest pipeline -------------------------------------------------
import base64

from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore


def ingest_dir(path, files):
    path.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (path / name).write_bytes(data)
    store = SnapshotStore(":memory:")
    sid = ingest(store, [Repository.from_directory(path, "repo")], stage=3)["snapshot_id"]
    failures = [f for row in store.connection.execute("SELECT parse_failures_json FROM snapshots WHERE snapshot_id=?", (sid,))
                for f in json.loads(row[0])]
    return store.graph(sid), failures


def test_notebook_function_is_extracted_with_virtual_line_numbers(tmp_path):
    g, _ = ingest_dir(tmp_path, {"nb.ipynb": raw()})
    step = next(e for e in g.entities.values() if e.qualified_name.endswith("step"))
    assert step.kind == "function" and step.rel_path == "nb.ipynb"
    nb_file = next(e for e in g.entities.values() if e.kind == "file" and e.rel_path == "nb.ipynb")
    src = g.analyses["source:" + nb_file.entity_id]["result"]
    assert src["coordinate_space"] == "ipynb-python-v1" and src["notebook_sha256"] == hashlib.sha256(raw()).hexdigest()
    text = base64.b64decode(src["bytes_base64"]).decode("utf-8").split("\n")
    assert text[step.start_line - 1] == "def step(x):"
    assert "SECRET OUTPUT" not in base64.b64decode(src["bytes_base64"]).decode("utf-8")


def test_markdown_cell_is_one_fragment_and_scaffolding_is_not(tmp_path):
    g, _ = ingest_dir(tmp_path, {"nb.ipynb": raw()})
    frags = [e for e in g.entities.values() if e.kind == "fragment" and e.rel_path == "nb.ipynb"]
    texts = [g.analyses["text:" + f.entity_id]["result"]["text"] for f in frags]
    assert texts.count("# Solver\nUses `step` to advance.\n") == 1
    assert not any("%% [cell" in t or t.lstrip().startswith("# # Solver") for t in texts)
    md = next(f for f in frags if "Solver" in g.analyses["text:" + f.entity_id]["result"]["text"])
    assert g.analyses["document:" + md.entity_id]["result"]["coordinate_space"] == "ipynb-markdown-cell"


def test_unparsed_cell_is_a_soft_failure_and_the_rest_survives(tmp_path):
    g, failures = ingest_dir(tmp_path, {"nb.ipynb": raw()})
    assert any(e.qualified_name.endswith("step") for e in g.entities.values())
    assert any(f.get("code") == "SyntaxError" and "cell 3" in f.get("message", "") for f in failures)


def test_invalid_notebook_is_a_parse_failure_with_a_file_entity(tmp_path):
    g, failures = ingest_dir(tmp_path, {"bad.ipynb": b"{not json", "ok.py": b"def f():\n    return 1\n"})
    assert any(f.get("code") == "NotebookFormatError" and f.get("rel_path") == "bad.ipynb" for f in failures)
    assert any(e.kind == "file" and e.rel_path == "bad.ipynb" for e in g.entities.values())
    assert any(e.qualified_name.endswith(".f") for e in g.entities.values())
