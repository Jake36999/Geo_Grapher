import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from test_phase8_conversion_graph import artifact


@pytest.fixture
def publication(artifact, tmp_path):
    from geographer.graph_catalog import GraphCatalog
    from geographer.folder_review import apply_review
    _, original_artifact, data = artifact
    library = tmp_path / 'library'; derived = library / '.librarian/derived/paper-graph'
    derived.mkdir(parents=True)
    converted = library / '.librarian/conversions/fixture.md'; converted.parent.mkdir()
    converted.write_bytes(Path(data['conversion']['path']).read_bytes())
    data['conversion']['path'] = converted.as_posix()
    path = derived / 'fixture.nodes.json'; path.write_text(json.dumps(data))
    catalog = GraphCatalog(library / '.librarian/geographer/catalog.sqlite')
    # The folder decision precedes publication; the fixture original remains separate.
    apply_review(catalog, dict(library=str(library), decisions=[dict(source_root=str(tmp_path),
        path='.', status='accepted', decision=dict(purpose='research-docs', graph='papers', accepted_by='person'))]))
    request = dict(library=str(library), graph_label='papers', artifact=str(path),
                   artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    yield catalog, request, path, data
    catalog.close()


def test_publish_conversion_as_new_generation_and_preserve_previous(publication):
    from geographer.library_papers import publish
    catalog, request, path, data = publication
    first = publish(catalog, request)
    assert first['published'] and first['documents'] == 1
    previous = Path(first['paper_database']); previous_hash = hashlib.sha256(previous.read_bytes()).hexdigest()
    data['metadata']['title'] = 'Revised title'; path.write_text(json.dumps(data))
    request['artifact_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    second = publish(catalog, request)
    assert second['paper_database'] != str(previous)
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == previous_hash
    with sqlite3.connect(second['paper_database']) as conn:
        assert conn.execute('SELECT COUNT(*) FROM sections').fetchone()[0] == 1


def test_mismatched_artifact_is_refused_without_catalog_mutation(publication):
    from geographer.library_papers import publish
    catalog, request, path, data = publication
    request['artifact_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='ARTIFACT_STALE'):
        publish(catalog, request)
    assert catalog.graphs()[0]['paper_database'] is None


def test_paper_publication_cannot_cross_authorship_boundary(publication):
    from geographer.library_papers import publish
    catalog, request, path, data = publication
    data['original']['authorship'] = 'owner_created'; path.write_text(json.dumps(data))
    request['artifact_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='PAPER_SCOPE'):
        publish(catalog, request)
    assert catalog.graphs()[0]['paper_database'] is None


def test_paper_publication_honours_reviewed_source_exclusions(publication):
    from geographer.library_papers import publish
    catalog, request, _, data = publication
    graph = catalog.graphs()[0]; profile = json.loads(graph['profile_json'])
    profile['source_roots_reviewed'][0]['exclude_globs'] = ['original.pdf']
    with catalog.connection:
        catalog.connection.execute('UPDATE graphs SET profile_json=? WHERE graph_id=?',
            (json.dumps(profile), graph['graph_id']))
    with pytest.raises(ValueError, match='PAPER_SCOPE'):
        publish(catalog, request)
    assert catalog.graphs()[0]['paper_database'] is None
