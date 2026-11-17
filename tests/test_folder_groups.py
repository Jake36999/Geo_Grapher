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
    assert profile['stratum']['authorship'] == 'third_party'
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
    assert report['graphs'][0]['stratum'] == dict(role='third_party', trust_tier='bronze', modality='paper',
                                               authorship='third_party')


def test_agent_policy_decisions_from_the_owning_core_apply_but_unvouched_ones_do_not(tmp_path):
    """Librarian agent mode (owner, 2026-11-15): the Core records accepted_by='agent-policy' with
    its policy only after checking the library's promotion.mode; anything else is still refused."""
    from geographer.folder_review import apply_review
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite'); root = tmp_path / 'source'; root.mkdir()
    (root / 'own.py').write_text('OUR_CODE = 1\n')
    card = lambda decision: [dict(source_root=str(root), path='.', status='accepted', decision=decision)]
    policy = dict(mode='agent', rule='unambiguous suggestion, not sensitive')
    result = apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=card(
        dict(purpose='own-current', graph='our-system', accepted_by='agent-policy', policy=policy))))
    assert [g['label'] for g in cat.graphs()] == ['our-system'] and result['graphs']
    for bad in (dict(purpose='own-current', graph='x', accepted_by='agent-policy'),            # no policy record
                dict(purpose='own-current', graph='x', accepted_by='agent-policy', policy=dict(mode='person')),
                dict(purpose='own-current', graph='x', accepted_by='model')):
        with pytest.raises(ValueError, match='FOLDER_REVIEW_REQUIRED'):
            apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=card(bad)))


def _names(cat, label):
    from geographer.store import SnapshotStore
    graph = next(g for g in cat.graphs() if g['label'] == label)
    with SnapshotStore(Path(graph['code_database'])) as store:
        return [r[0] for r in store.connection.execute('SELECT qualified_name FROM entities WHERE snapshot_id=?',
                                                       (graph['snapshot_id'],))]


def test_withheld_and_sibling_partition_folders_stay_out_of_the_parents_graph(tmp_path):
    """2026-11-17: accepting a parent walked into child folders held for a person's review."""
    from geographer.folder_review import apply_review
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite'); root = tmp_path / 'source'; root.mkdir()
    (root / 'own.py').write_text('OUR_CODE = 1\n')
    for name, constant in [('held', 'HELD_UPSTREAM'), ('partition', 'PARTITION_UPSTREAM')]:
        (root / name).mkdir(); (root / name / 'm.py').write_text(f'{constant} = 2\n')
    card = dict(source_root=str(root), path='.', status='accepted',
                partition=dict(exclude_globs=['partition', 'partition/*']),
                decision=dict(purpose='own-current', graph='our-system', accepted_by='person'))
    apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=[card], withheld=[str(root / 'held')]))
    names = _names(cat, 'our-system')
    assert any('OUR_CODE' in n for n in names)
    assert not any('HELD_UPSTREAM' in n or 'PARTITION_UPSTREAM' in n for n in names)


def test_withheld_must_be_a_list_of_paths(tmp_path):
    from geographer.folder_review import apply_review
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite')
    with pytest.raises(ValueError, match='FOLDER_WITHHELD'):
        apply_review(cat, dict(library=str(tmp_path / 'vault'), decisions=[], withheld=[3]))


def test_secret_store_names_are_refused_like_the_librarian_refuses_them():
    from geographer.credentials import credential_path
    for name in ('x.sqlite.cursor-secret', 'api_secret', 'secrets.json', '.netrc', 'sub/credentials.json', '.pgpass'):
        assert credential_path(name), name
    for name in ('credentials.py', 'secret_sharing.pdf', 'docs/secrets-of-csi.md'):
        assert not credential_path(name), name


def test_common_words_do_not_link_prose_to_symbols_unless_marked_as_code():
    """2026-11-17: symbols named `to`, `which`, `set` drew thousands of false incidences."""
    from geographer.extract import mention_tokens
    tokens = mention_tokens("Set the value to which we run, then call `set` and run() and the open method; target_fn too.")
    assert {"set", "run", "open", "target_fn"} <= tokens                      # marked, or not common
    assert not {"Set", "the", "value", "to", "which", "we", "then", "call", "and"} & tokens
    assert "pkg.to" in mention_tokens("see pkg.to for details")              # dotted names always link


def test_a_run_of_comment_lines_is_one_fragment():
    """2026-11-17: every `#` line became its own entity."""
    from geographer.pipeline import ingest
    from geographer.source import Repository
    from geographer.store import SnapshotStore
    code = b'# first line of a note\n# second line\n# third line\nVALUE = 1\n\n\n# a separate note\ndef f():\n    return VALUE\n'
    with SnapshotStore() as store:
        sid = ingest(store, [Repository('r', 'rev', {'m.py': code})], stage=3)['snapshot_id']
        rows = store.connection.execute(
            "SELECT start_line, end_line FROM entities WHERE snapshot_id=? AND kind='fragment' ORDER BY start_line", (sid,)).fetchall()
    assert [tuple(r) for r in rows] == [(1, 3), (7, 7)]


def test_the_catalogue_uses_a_write_ahead_log_and_waits_for_a_busy_writer(tmp_path):
    cat = GraphCatalog(tmp_path / 'catalog/catalog.sqlite')
    assert cat.connection.execute('PRAGMA journal_mode').fetchone()[0].lower() == 'wal'
    assert cat.connection.execute('PRAGMA busy_timeout').fetchone()[0] == 5000
