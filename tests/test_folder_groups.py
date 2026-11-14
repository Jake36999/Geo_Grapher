import json
from pathlib import Path

import pytest

from geographer.graph_catalog import GraphCatalog


def test_two_accepted_folders_really_share_one_graph_without_cross_resolution(tmp_path):
    from geographer.folder_review import apply_review
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite')
    root = tmp_path / 'source'; root.mkdir()
    cards = []
    for name in ['vendor-a', 'vendor-b']:
        folder = root / name; folder.mkdir(); (folder / 'm.py').write_text('def f(x):\n    return x\n')
        cards.append(dict(source_root=str(root), path=name, status='accepted',
            decision=dict(purpose='third-party', graph='library-third-party', accepted_by='person')))
    result = apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=cards))
    assert len(result['graphs']) == len(cat.graphs()) == 1
    graph = cat.graphs()[0]; profile = json.loads(graph['profile_json'])
    assert len(profile['owner_repo_ids']) == 2
    assert profile['stratum']['role'] == 'third_party'
    from geographer.graph_router import GraphRouter
    with GraphRouter(cat).lease(graph['graph_id']) as svc:
        rows = list(svc.store.connection.execute("SELECT DISTINCT repo_id FROM entities WHERE snapshot_id=? AND kind='function'", (graph['snapshot_id'],)))
    assert len(rows) == 2


def test_child_override_is_not_also_ingested_into_parent(tmp_path):
    from geographer.folder_review import apply_review
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite'); root = tmp_path / 'source'; root.mkdir()
    (root / 'own.py').write_text('OUR_CODE = 1\n')
    third = root / 'vendor'; third.mkdir(); (third / 'm.py').write_text('UPSTREAM = 2\n')
    cards = [dict(source_root=str(root), path=path, status='accepted',
        decision=dict(purpose=purpose, graph=graph, accepted_by='person'))
        for path, purpose, graph in [('.', 'own-current', 'our-system'), ('vendor', 'third-party', 'references')]]
    apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=cards))
    own = next(g for g in cat.graphs() if g['label'] == 'our-system')
    from geographer.store import SnapshotStore
    with SnapshotStore(Path(own['code_database'])) as store:
        names = [r[0] for r in store.connection.execute('SELECT qualified_name FROM entities WHERE snapshot_id=?', (own['snapshot_id'],))]
    assert not any('UPSTREAM' in n for n in names)


def test_group_cannot_mix_current_system_and_external_strata(tmp_path):
    from geographer.folder_review import apply_review
    cat = GraphCatalog(tmp_path / 'catalog.sqlite')
    cards = [dict(source_root=str(tmp_path), path='.', status='accepted',
        decision=dict(purpose=p, graph='same', accepted_by='person')) for p in ['own-current', 'third-party']]
    with pytest.raises(ValueError, match='GROUP_STRATUM_CONFLICT'):
        apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=cards))
    assert not cat.graphs()


def test_excluding_last_member_hides_graph_without_deleting_snapshot(tmp_path):
    from geographer.folder_review import apply_review
    from geographer.graph_router import GraphRouter
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite'); root = tmp_path / 'source'; root.mkdir()
    (root / 'a.py').write_text('X = 1\n')
    card = dict(source_root=str(root), path='.', status='accepted',
                decision=dict(purpose='third-party', graph='references', accepted_by='person'))
    first = apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=[card]))
    database = Path(cat.graph(first['graphs'][0]['graph_id'])['code_database'])
    card['decision']['purpose'] = 'exclude'
    apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=[card]))
    router = GraphRouter(cat)
    assert router.summary()['graphs'] == []
    assert database.is_file()


def test_existing_project_graph_assignment_preserves_identity_and_original_source(tmp_path):
    from geographer.folder_review import apply_review
    from geographer.source import Repository
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite')
    original = tmp_path / 'original'; original.mkdir(); (original / 'old.py').write_text('ORIGINAL = 1\n')
    existing = cat.import_project(original, Repository.from_directory(original, 'existing'), label='chosen-existing')
    cat.set_stratum(existing['graph_id'], 'current', 'gold', 'code')
    extra = tmp_path / 'extra'; extra.mkdir(); (extra / 'new.py').write_text('ADDITIONAL = 2\n')
    result = apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=[dict(source_root=str(extra),
        path='.', status='accepted', decision=dict(purpose='own-current', graph='chosen-existing', accepted_by='person'))]))
    assert len(cat.graphs()) == 1 and result['graphs'][0]['graph_id'] == existing['graph_id']
    from geographer.graph_router import GraphRouter
    router = GraphRouter(cat)
    with router.lease(existing['graph_id']) as svc:
        names = [r[0] for r in svc.store.connection.execute('SELECT qualified_name FROM entities WHERE snapshot_id=?',
            (cat.graph(existing['graph_id'])['snapshot_id'],))]
    assert any('ORIGINAL' in n for n in names) and any('ADDITIONAL' in n for n in names)
    router.close()


def test_unchanged_review_groups_reuse_complete_snapshots(tmp_path):
    from geographer.folder_review import apply_review
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite'); root = tmp_path / 'source'; root.mkdir()
    (root / 'a.py').write_text('X = 1\n')
    request = dict(library=str(tmp_path / 'vault'), decisions=[dict(source_root=str(root), path='.', status='accepted',
        decision=dict(purpose='own-current', graph='own', accepted_by='person'))])
    first = apply_review(cat, request)
    second = apply_review(cat, request)
    assert first['graphs'][0]['snapshot_id'] == second['graphs'][0]['snapshot_id']


def test_third_party_graph_uses_reviewed_content_modality(tmp_path):
    from geographer.folder_review import apply_review
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite'); root = tmp_path / 'papers'; root.mkdir()
    (root / 'abstract.md').write_text('# Synthetic paper abstract\n')
    card = dict(source_root=str(root), path='.', status='accepted', partition=dict(stratum=dict(modality='paper')),
        decision=dict(purpose='third-party', graph='external-papers', accepted_by='person'))
    report = apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=[card]))
    assert report['graphs'][0]['stratum'] == dict(role='third_party', trust_tier='bronze', modality='paper')
