import os
from pathlib import Path

import pytest

from geographer.workspace_init import scan


def test_metadata_inventory_plans_without_a_second_walk(tmp_path, monkeypatch):
    (tmp_path / 'src').mkdir()
    inventory = {'version': 'folder-inventory-v1', 'root': str(tmp_path.resolve()),
                 'fingerprint': 'shared-survey', 'entries': [['src/', 0, 0], ['src/a.py', 12, 123]],
                 'credential_refusals': {'count': 1, 'paths': ['Frank.env']}}
    monkeypatch.setattr(os, 'walk', lambda *a, **k: pytest.fail('second walk'))
    result = scan(tmp_path, inventory=inventory)
    assert result['shared_survey_fingerprint'] == 'shared-survey'
    assert result['partitions'][0]['file_counts']['.py'] == 1
    assert result['credential_refusals']['paths'] == ['Frank.env']


def test_same_size_edit_invalidates_geo_plan(tmp_path):
    path = tmp_path / 'a.py'; path.write_text('X = 1\n')
    first = scan(tmp_path)
    before = path.stat().st_mtime_ns
    path.write_text('X = 2\n'); os.utime(path, ns=(before + 10000000, before + 10000000))
    assert scan(tmp_path)['plan_id'] != first['plan_id']


def test_suggestions_are_explained_and_third_party_is_bronze(tmp_path):
    for folder, file in [('third_party_research/repos/CSIKit-main', 'a.py'),
                         ('repos/library', 'a.py'), ('papers', 'a.pdf'),
                         ('exports', 'raw.pcap'), ('graphify-out', 'a.py'),
                         ('librarian-app', 'a.md'), ('test-results', 'result.md')]:
        path = tmp_path / folder / file; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic')
    result = scan(tmp_path)
    parts = {p['key']: p for p in result['partitions']}
    third = parts['third_party_research']
    assert third['stratum'] == {'role': 'third_party', 'trust_tier': 'bronze', 'modality': 'code'}
    assert third['suggestion']['purpose'] == 'third-party'
    assert third['suggestion']['reasons']
    assert parts['papers']['stratum']['modality'] == 'paper'
    assert parts['exports']['suggestion']['purpose'] == 'data'
    assert {'graphify-out', 'librarian-app', 'test-results'} <= {p['rel'] for p in result['excluded']}


def test_inventory_rejects_escape_and_wrong_root(tmp_path):
    for root, name in [(str(tmp_path), '../elsewhere.md'), (str(tmp_path / 'other'), 'x.md')]:
        with pytest.raises(ValueError, match='INVENTORY'):
            scan(tmp_path, inventory={'version': 'folder-inventory-v1', 'root': root,
                 'fingerprint': 'x', 'entries': [[name, 1, 0]]})


def test_empty_folders_and_binary_files_are_excluded_with_reasons(tmp_path):
    (tmp_path / 'New folder').mkdir()
    (tmp_path / 'backups').mkdir()
    (tmp_path / 'backups/model.blend1').write_bytes(b'synthetic')
    (tmp_path / 'logs.log').write_text('synthetic')
    plan = scan(tmp_path)
    excluded = {e['rel']: e['reason'] for e in plan['excluded']}
    assert excluded['New folder'] == 'empty folder'
    assert 'backups/model.blend1' in excluded and 'logs.log' in excluded


def test_folder_counts_and_size_cover_data_and_paper_content(tmp_path):
    (tmp_path / 'papers').mkdir(); (tmp_path / 'papers/a.pdf').write_bytes(b'synthetic-pdf')
    paper = next(p for p in scan(tmp_path)['partitions'] if p['key'] == 'papers')
    assert paper['bytes'] == len(b'synthetic-pdf')


def test_shared_inventory_apply_rejects_a_new_file_before_import(tmp_path):
    from geographer.workspace_init import apply, HYGIENE_DIRS
    from geographer.folder_inventory import collect
    from geographer.graph_catalog import GraphCatalog
    root = tmp_path / 'source'; root.mkdir(); (root / 'a.py').write_text('X=1\n')
    data = collect(root, HYGIENE_DIRS); data['fingerprint'] = 'native-survey'
    plan = scan(root, inventory=data)
    (root / 'new.py').write_text('Y=2\n')
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite')
    with pytest.raises(ValueError, match='PLAN_STALE'):
        apply(cat, plan, approved_keys={'residual'}, inventory=data)
    assert cat.graphs() == []
