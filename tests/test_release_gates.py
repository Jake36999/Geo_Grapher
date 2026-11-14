"""Release gates must work without user stores or historical timing rescoring."""
import importlib
import hashlib
import json
import sqlite3
import tomllib
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_release_version_is_consistent():
    import geographer
    version=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
    assert version==geographer.__version__=='0.2.0'

def test_stable_contract_manifest_covers_every_contract_byte():
    base=ROOT/'contracts/v1.1'
    manifest=json.loads((base/'RELEASE_MANIFEST.json').read_text())
    assert manifest['status']=='stable' and manifest['future_changes']=='v1.2'
    expected={str(p.relative_to(base)).replace('\\','/') for p in base.rglob('*')
              if p.is_file() and p.name!='RELEASE_MANIFEST.json'}
    assert set(manifest['sha256'])==expected
    assert all(hashlib.sha256((base/name).read_bytes()).hexdigest()==sha
               for name,sha in manifest['sha256'].items())

def test_wheel_declares_every_frozen_contract_file():
    package=tomllib.loads((ROOT/'pyproject.toml').read_text())['tool']['setuptools']['data-files']
    shipped={name for names in package.values() for name in names}
    manifest=json.loads((ROOT/'contracts/v1.1/RELEASE_MANIFEST.json').read_text())
    assert {'contracts/v1.1/'+name for name in manifest['sha256']} <= shipped
    assert 'contracts/v1.1/RELEASE_MANIFEST.json' in shipped

@pytest.mark.parametrize('samples,passed',[
    ([2.0,2.9,3.4],True),([2.0,3.0,3.1],False),
    ([2.0,2.9,3.5],False),([2.0,2.9],False),
    ([2.0,float('nan'),2.9],False),([2.0,-1.0,2.9],False),
])
def test_c14_uses_strict_median_max_and_three_finite_samples(samples,passed):
    gate=importlib.import_module('scripts.qa_c14')
    assert gate.passes(samples) is passed

def test_presets_have_a_self_contained_default_catalog(tmp_path):
    from scripts.qa_mcp_presets import make_fixture
    catalog=make_fixture(tmp_path)
    with sqlite3.connect(catalog) as c:
        rows=c.execute('SELECT label,code_database,paper_database FROM graphs').fetchall()
    assert {r[0] for r in rows}=={'librarian-v2','ToolSet','ai-research-papers'}
    assert all(Path(r[1]).is_file() for r in rows)
    papers=next(r[2] for r in rows if r[0]=='ai-research-papers')
    with sqlite3.connect(papers) as c:
        assert c.execute('SELECT count(*) FROM read_documents').fetchone()[0]>=1
