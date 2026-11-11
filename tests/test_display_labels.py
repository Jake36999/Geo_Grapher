import json
import os
import pathlib
import subprocess
import sys

import pytest

from geographer.labels import base_label, disambiguate, role_badge, snippet, truncate_label
from geographer.pipeline import ingest
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore
from test_stage4_geometry import viewport_request

ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_markdown_fragment_uses_heading_path(extract_markdown):
    g, fid = extract_markdown("# Guide\n## Install\nRun it.\n", line=3)
    assert base_label(g, fid) == "Guide › Install"

def test_fragment_label_edge_cases(extract_markdown):
    g, fid = extract_markdown("Intro text\n# A\n", line=1)
    assert base_label(g, fid) == "README.md · intro"
    g, fid = extract_markdown("#\nbody\n", line=2)
    assert base_label(g, fid) == "README.md · intro"
    g, fid = extract_markdown("plain words\n", line=1, name="notes.txt")
    assert base_label(g, fid) == "notes.txt · intro"

def test_docstring_fragment_label(extract_python):
    g, fid = extract_python('def run():\n    """Do it."""\n', fragment_of="run")
    assert base_label(g, fid) == "run · docstring"

def test_truncation_is_left_trimmed_and_valid_utf8():
    long = " › ".join(["Überschrift-" + "x" * 10] * 6)
    out = truncate_label(long)
    assert len(out) <= 48 and out.startswith("…") and out.encode("utf-8")

def frag(i, line, text, label="Setup"):
    return dict(id=i, kind="fragment", parent_id="d", qualified_name=i, source=dict(rel_path="a.md", start_line=line),
                display_label=label, label_text=text)

def test_fragments_under_same_heading_get_content_snippets():
    nodes = [frag("f1", 3, "Install the **package** with pip and then configure it."),
             frag("f2", 9, "Then run the `migrate` command against your database.")]
    assert disambiguate(nodes) == {"f1": "Setup · Install package pip configure",
                                   "f2": "Setup · run migrate command database"}

def test_snippet_collision_falls_back_to_numbering():
    nodes = [frag("f1", 3, "Install package pip wheel."), frag("f2", 9, "Install package pip wheel.")]
    out = disambiguate(nodes)
    assert out["f1"] == "Setup · Install package pip wheel" and out["f2"] == "Setup · Install package pip wheel (2)"

def test_snippet_respects_48_chars_and_minimum_three_words():
    nodes = [frag("f1", 3, "Configuration orchestration parameterisation internationalisation", label="A fairly long heading label here"),
             frag("f2", 9, "Other words entirely different here", label="A fairly long heading label here")]
    out = disambiguate(nodes)
    assert all(len(v) <= 48 for v in out.values()) and all(len(v.split(" · ")[1].split()) >= 3 or v.endswith("…") for v in out.values())

@pytest.mark.parametrize("src,qual,badge", [
    ("def main():\n    pass\n", "m.main", "Entry"),
    ("import click\n@click.command()\ndef go():\n    pass\n", "m.go", "Entry"),
    ("from pydantic import BaseModel\nclass Cfg(BaseModel):\n    x: int = 1\n", "m.Cfg", "Schema"),
    ("from dataclasses import dataclass\n@dataclass\nclass P:\n    x: int\n", "m.P", "Schema"),
    ("def validate_input(x):\n    return x\n", "m.validate_input", "Gate"),
    ("def load_config(p):\n    return open(p).read()\n", "m.load_config", "IO"),
    ("def _h(x):\n    return x\n", "m._h", "Util"),
])
def test_role_badges(extract_module, src, qual, badge):
    g, eid = extract_module(src, qual)
    assert role_badge(g, eid) == badge

def test_core_badge_from_in_degree(extract_module):
    src = "def core(x):\n    return x\n" + "".join(f"def c{i}():\n    return core({i})\n" for i in range(3))
    g, eid = extract_module(src, "m.core")
    assert role_badge(g, eid) == "Core"

def test_spec_badge_and_none(extract_markdown, extract_module):
    g, fid = extract_markdown("# Design\nText.\n", line=2, name="docs/DESIGN_SPECIFICATION.md")
    assert role_badge(g, fid) == "Spec"
    g, eid = extract_module("def plain(x):\n    return x + 1\n", "m.plain")
    assert role_badge(g, eid) is None

def test_duplicate_main_gets_minimal_ancestor_prefix():
    nodes = [dict(id="m1", kind="function", parent_id="p", qualified_name="pkg.cli.main", source=dict(rel_path="pkg/cli.py", start_line=1), display_label="main"),
             dict(id="m2", kind="function", parent_id="p", qualified_name="pkg.worker.main", source=dict(rel_path="pkg/worker.py", start_line=1), display_label="main")]
    assert disambiguate(nodes) == {"m1": "cli::main", "m2": "worker::main"}


def test_snippet_picks_content_words_within_budget():
    assert snippet("Install the **package** with pip and then configure it.", 40) == "Install package pip configure"
    assert snippet("Install package pip configure", 24) == "Install package pip"


def test_wire_schema_has_optional_display_label_and_role_badge():
    schema = json.loads((ROOT / "contracts/v1.1/generated/geographer.wire.schema.json").read_text())
    node = schema["$defs"]["NodeRecord"]
    assert {"display_label", "role_badge"} <= node["properties"].keys()
    assert not {"display_label", "role_badge"} & set(node["required"])
    flat = json.dumps(node["properties"]["display_label"])
    assert '"maxLength": 48' in flat
    badge = json.dumps(node["properties"]["role_badge"])
    for value in ("Entry", "Schema", "Gate", "IO", "Core", "Util", "Spec"):
        assert f'"{value}"' in badge
    assert '"null"' in badge


def test_label_text_never_on_wire():
    files = {"docs/guide.md": b"# Guide\n\nInstall the package with pip now.\n\nRun the migrate command today.\n",
             "app.py": b"def main():\n    return 1\n"}
    with SnapshotStore() as store:
        sid = ingest(store, [Repository("r", "rev", files)], stage=3)["snapshot_id"]
        svc = QueryService(store, secret=b"w" * 32)
        ctx = svc._context(sid)
        focus = next(e.entity_id for e in ctx["g"].entities.values() if e.qualified_name == "app.py.main")
        q = viewport_request(sid, focus)
        q.update(schema_version="1.1", identity_mode="canonical_map", grouping={"mode": "atomic"})
        result = svc.query("viewport_frame", q)
        assert "data" in result, result
        svc.wire11.validate("viewport_frame", "response", result)
        nodes = result["data"]["nodes"]
        assert nodes and not any("label_text" in n for n in nodes)
        by_name = {n["qualified_name"]: n for n in nodes}
        assert by_name["app.py.main"]["display_label"] == "main"
        assert by_name["app.py.main"]["role_badge"] == "Entry"
        fragments = [n for n in nodes if n["kind"] == "fragment"]
        labels = [n["display_label"] for n in fragments]
        assert fragments and all(len(x) <= 48 for x in labels) and len(set(labels)) == len(labels)
        assert not any(x.startswith("Documentation") for x in labels)


def test_stopwords_frozen_at_120_without_content_words():
    from geographer.labels import STOPWORDS
    assert len(STOPWORDS) == 120 == len(set(STOPWORDS))
    assert not {"package", "pip", "wheel", "install", "run", "migrate", "command", "database", "configure"} & set(STOPWORDS)


SCRIPT = r"""
import json
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.labels import base_label, role_badge
files = {"m.py": b"import click\n@click.command()\ndef go():\n    pass\nclass C(dict):\n    pass\n", "d.md": b"# A\n## B\ntext\n"}
with SnapshotStore() as store:
    report = ingest(store, [Repository("r", "rev", files)])
    g = store.graph(report["snapshot_id"], published_only=True)
    print(json.dumps({"roles": {k: v["result"] for k, v in sorted(g.analyses.items()) if k.startswith("role-inputs:")},
                      "labels": {e: [base_label(g, e), role_badge(g, e)] for e in sorted(g.entities) if g.entities[e].kind != "external_symbol"}}, sort_keys=True))
"""


def test_role_inputs_and_labels_are_hashseed_independent():
    outputs = []
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(ROOT / "src")}
        outputs.append(subprocess.run([sys.executable, "-c", SCRIPT], env=env, capture_output=True, check=True).stdout)
    assert outputs[0] == outputs[1] and b"click.command" in outputs[0]
