"""A loaded graph is held in a compact view form (owner, 2026-11-17: 12-14 KB of RAM per entity, 5.4 GB for
six graphs). Evidence, analyses and fingerprints are read from the store only when something needs them, and
the entity form drops the binary-lifting table. The gate is parity: every operation must answer
byte-for-byte as it does from the full load."""
import copy
import json
import tracemalloc

import pytest

from geographer.analysis import DEFAULT_FILTER, TreeIndex
from geographer.lazygraph import LazyTable
from geographer.pipeline import ingest
from geographer.service import QueryService
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.tokens import TokenCounter

FILES = {
    'lib.py': b'''def target(value: int) -> int:
    """Return the input value. This sentence is secondary."""
    return value

def helper(value):
    return target(value)

class Box:
    def open(self, value):
        return helper(value)

    def close(self):
        return target(0)

def run(value):
    if value:
        return Box().open(value)
    return 0
''',
    'util/more.py': b'''from lib import run, helper

def again(value):
    return run(helper(value))
''',
    'notes.md': b'# Network listener\n\nThe run function performs network work.\n\n## Details\n\nhelper calls target\n',
    'docs/guide.md': b'# Guide\n\nUse `again` and `Box.open` together.\n',
}


@pytest.fixture
def pair(tmp_path):
    path = tmp_path / 'graph.sqlite'
    writer = SnapshotStore(path)
    sid = ingest(writer, [Repository('r', 'rev', FILES)], stage=3)['snapshot_id']
    writer.close()
    stores = [SnapshotStore(path), SnapshotStore(path)]
    full = QueryService(stores[0], secret=b'x' * 32, view_context=False)
    view = QueryService(stores[1], secret=b'x' * 32, view_context=True)
    yield full, view, sid
    for store in stores:
        store.close()


def base(sid, limit=8192):
    return dict(schema_version='1.1', request_id='view-test', snapshot_id=sid, identity_mode='canonical_map',
                budget=dict(limit_tokens=limit, tokenizer='o200k_base', allow_byte_fallback=False))


def entity(service, sid, name):
    return next(e.entity_id for e in service._context(sid)['g'].entities.values() if e.qualified_name == name)


def viewport(sid, focus, radius=2, grouping=None, layout='sphere-pack-v1'):
    q = dict(schema_version='1.0', request_id='view-test', snapshot_id=sid,
             budget=dict(limit_tokens=32768, tokenizer='o200k_base', allow_byte_fallback=False),
             focus_id=focus, revealed_ids=[], pins=[], context_radius=radius, filter=copy.deepcopy(DEFAULT_FILTER),
             layout_version=layout, seed='view-v1', beta=.8,
             edge_lens=dict(enabled=False, center=[0, 0, 0], radius=5., strength=.8), node_budget=100, curve_budget=200,
             viewport=dict(width_px=1440, height_px=900, device_pixel_ratio=1),
             camera=dict(eye=[0, 0, 100], target=[0, 0, 0], up=[0, 1, 0], fov_y_degrees=45, near=.01, far=10000))
    if grouping:
        q.update(schema_version='1.1', grouping=grouping, layout_version='sphere-affinity-v1', identity_mode='canonical_map')
    return q


def frames(service, sid):
    """The requests the workspace sends while a graph is open."""
    root = next(e.entity_id for e in service._context(sid)['g'].entities.values() if e.kind == 'repository')
    run = entity(service, sid, 'lib.py.run')
    return [
        ('root radius 1', 'viewport_frame', viewport(sid, root, 1)),
        ('root radius 2', 'viewport_frame', viewport(sid, root, 2)),
        ('function radius 2', 'viewport_frame', viewport(sid, run, 2)),
        ('kind/file grouping', 'viewport_frame', viewport(sid, root, 1, dict(mode='kind', kind='file'))),
        ('atomic grouping', 'viewport_frame', viewport(sid, root, 1, dict(mode='atomic'))),
    ]


def details(service, sid):
    """Requests that read evidence, analyses, source bytes and fingerprints."""
    run = entity(service, sid, 'lib.py.run')
    target = entity(service, sid, 'lib.py.target')
    context = {**base(sid), 'focus_id': run, 'grouping': {'mode': 'kind', 'kind': 'file'}, 'context_radius': 1,
               'filter': copy.deepcopy(DEFAULT_FILTER), 'pins': [], 'qi': {'enabled': False, 'max_diameter': 2}, 'cursor': None}
    out = [('architecture context', 'get_architecture_context', context),
           ('search', 'search_entities', {**base(sid), 'query': 'lib.py.target', 'mode': 'hybrid', 'repo_ids': [],
                                            'kinds': [], 'limit': 20, 'cursor': None}),
           ('search prose', 'search_entities', {**base(sid), 'query': 'network listener', 'mode': 'hybrid', 'repo_ids': [],
                                                  'kinds': [], 'limit': 20, 'cursor': None}),
           ('source', 'get_entity_content', {**base(sid), 'entity_id': target, 'content_kind': 'source', 'start_line': None,
                                             'end_line': None, 'context_mode': 'range', 'context_radius': 0, 'cursor': None}),
           ('dependants', 'find_dependants', {**base(sid), 'entity_id': target, 'direction': 'incoming',
                                              'filter': copy.deepcopy(DEFAULT_FILTER), 'max_depth': 3, 'max_results': 20, 'cursor': None}),
           ('similar code', 'find_similar_code', {**base(sid), 'entity_id': target, 'mode': 'exact_normalized_ast',
                                                  'repo_ids': [], 'limit': 10, 'cursor': None})]
    return out


def answer(service, op, request):
    result = service.query(op, copy.deepcopy(request))
    return json.dumps(result, sort_keys=True, default=str)


def test_every_operation_answers_identically_from_the_view_context(pair):
    full, view, sid = pair
    for (name, op, request), (_, _, same) in zip(frames(full, sid) + details(full, sid), frames(view, sid) + details(view, sid)):
        assert request == same, name
        a, b = answer(full, op, request), answer(view, op, request)
        assert '"error"' not in a, (name, a[:300])
        assert a == b, f'{name}: the view context answered differently'


def test_witnesses_match_after_the_context_has_been_used(pair):
    full, view, sid = pair
    run = entity(full, sid, 'lib.py.run')
    context = {**base(sid), 'focus_id': run, 'grouping': {'mode': 'kind', 'kind': 'file'}, 'context_radius': 1,
               'filter': copy.deepcopy(DEFAULT_FILTER), 'pins': [], 'qi': {'enabled': False, 'max_diameter': 2}, 'cursor': None}
    graph = full.query('get_architecture_context', context)['data']
    assert answer(view, 'get_architecture_context', context) == answer(full, 'get_architecture_context', context)
    relation = graph['relationships'][0]
    inspection = {**base(sid), 'view_id': graph['view_id'], 'projection_id': graph['ids'][relation['id']], 'relationship_id': None,
                  'evidence_page_size': 2, 'evidence_cursor': None, 'page_size': 2, 'cursor': None}
    assert answer(view, 'inspect_relationship_witnesses', inspection) == answer(full, 'inspect_relationship_witnesses', inspection)


def test_a_frame_reads_no_evidence_analyses_or_fingerprints(pair):
    full, view, sid = pair
    g = view._context(sid)['g']
    for name, op, request in frames(view, sid):
        assert 'error' not in view.query(op, copy.deepcopy(request)), name
    assert isinstance(g.evidence, LazyTable) and isinstance(g.analyses, LazyTable)
    assert not g.evidence.loaded, 'a frame filled the whole evidence table'
    assert not g.analyses.loaded, 'a frame filled the whole analyses table'
    assert not g.fingerprints.loaded, 'a frame filled the fingerprints'
    assert view._context(sid)['evidence'].loaded is False and view._context(sid)['sources'].loaded is False


def test_detail_operations_fill_only_what_they_need_and_the_full_service_is_unchanged(pair):
    full, view, sid = pair
    assert not hasattr(full._context(sid)['g'].evidence, 'loaded')      # the full load is still plain dicts
    g = view._context(sid)['g']
    for name, op, request in details(view, sid):
        assert 'error' not in view.query(op, copy.deepcopy(request)), name
    assert g.evidence.loaded or g.analyses.loaded                        # detail operations do read them


def test_lazy_tables_behave_like_the_dicts_they_replace(pair):
    full, view, sid = pair
    plain, lazy = full._context(sid)['g'], view._context(sid)['g']
    for table in ('evidence', 'analyses'):
        a, b = getattr(plain, table), getattr(lazy, table)
        assert list(a) == list(b), f'{table}: key order differs'
        assert len(a) == len(b) and set(a) == set(b)
        some = next(iter(a))
        assert a[some] == b[some] and a.get(some) == b.get(some) and (some in b) and ('nope' not in b)
        assert b.get('nope') is None and b.get('nope', 7) == 7
        with pytest.raises(KeyError):
            b['nope']
        assert list(a.items()) == list(b.items()) and list(a.values()) == list(b.values())
        assert dict(b) == a and b == a
    assert dict(lazy.fingerprints) == dict(plain.fingerprints)


def test_point_lookups_do_not_fill_the_table(pair):
    full, view, sid = pair
    lazy = view._context(sid)['g'].analyses
    assert not lazy.loaded
    key = next(iter(full._context(sid)['g'].analyses))
    assert lazy[key] == full._context(sid)['g'].analyses[key]
    assert lazy.get('text:no-such-entity') is None and ('text:no-such-entity' not in lazy)
    assert not lazy.loaded
    list(lazy.values())
    assert lazy.loaded


def test_the_view_graph_is_the_same_graph_without_the_ancestor_table(pair):
    full, view, sid = pair
    a, b = full._context(sid)['g'], view._context(sid)['g']
    assert list(a.entities) == list(b.entities) and list(a.relationships) == list(b.relationships)
    for eid, e in a.entities.items():
        v = b.entities[eid]
        assert (e.kind, e.qualified_name, e.parent_id, e.depth, e.rel_path, e.repo_id, e.sort, e.is_external) == \
               (v.kind, v.qualified_name, v.parent_id, v.depth, v.rel_path, v.repo_id, v.sort, v.is_external)
        assert v.ancestors_binary_lifting_json == '[]'      # not held; the tree walks parent pointers instead
    assert a.relationships == b.relationships
    assert a.incidences == b.incidences


def test_tree_distances_match_the_binary_lifting_table(pair):
    full, view, sid = pair
    a, b = full._context(sid)['tree'], view._context(sid)['tree']
    assert isinstance(a, TreeIndex) and b.up is None and a.up
    ids = sorted(a.parents)
    for x in ids:
        for y in ids:
            assert a.lca(x, y) == b.lca(x, y)
            assert a.distance(x, y) == b.distance(x, y)


def test_the_view_form_holds_much_less_per_entity(tmp_path):
    files = {f'pkg/m{i}.py': ('\n'.join(f'def f{i}_{j}(x):\n    """Doc {i} {j}."""\n    return x + {j}\n' for j in range(12))).encode()
             for i in range(30)}
    path = tmp_path / 'big.sqlite'
    writer = SnapshotStore(path)
    sid = ingest(writer, [Repository('r', 'rev', files)], stage=3)['snapshot_id']
    writer.close()
    sizes = {}
    for name, flag in (('full', False), ('view', True)):
        store = SnapshotStore(path)
        service = QueryService(store, secret=b'x' * 32, view_context=flag)
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()[0]
        ctx = service._context(sid)
        sizes[name] = (tracemalloc.get_traced_memory()[0] - before) / len(ctx['g'].entities)
        tracemalloc.stop()
        del ctx
        service.cache.clear()
        store.close()
    assert sizes['view'] < 0.6 * sizes['full'], sizes
