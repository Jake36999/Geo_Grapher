"""A loaded graph costs about 12-14 KB of RAM per entity (measured 2026-11-17: 5.4 GB for six
Nonlinear Field Lab graphs). The router therefore keeps at most `max_loaded` graphs resident,
drops the least recently used idle one, and the display limits follow the same number."""
import pytest
from starlette.testclient import TestClient

from geographer.graph_catalog import GraphCatalog
from geographer.graph_composition import compose_frame
from geographer.graph_router import DEFAULT_MAX_LOADED, GraphRouter
from geographer.graph_server import create_graph_http
from geographer.source import Repository


def make_catalog(tmp_path, names):
    catalog = GraphCatalog(tmp_path / 'catalog' / 'catalog.sqlite')
    ids = []
    for name in names:
        root = tmp_path / name
        root.mkdir()
        (root / 'app.py').write_text('def entry():\n    return 1\n', encoding='utf-8')
        ids.append(catalog.import_project(root, Repository.from_directory(root, name), label=name)['graph_id'])
    return catalog, ids


@pytest.fixture
def five(tmp_path):
    catalog, ids = make_catalog(tmp_path, ('Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon'))
    routers = []

    def build(**kwargs):
        router = GraphRouter(catalog, **kwargs)
        routers.append(router)
        return router
    yield catalog, ids, build
    for router in routers:
        router.close()
    catalog.close()


def loaded(router):
    return [key[0] for key in router.services]


def touch(router, graph_id):
    with router.lease(graph_id):
        pass


def test_default_cap_is_three(five):
    catalog, ids, build = five
    assert DEFAULT_MAX_LOADED == 3
    router = build()
    assert router.max_loaded == 3
    for gid in ids[:4]:
        touch(router, gid)
    assert len(router.services) == 3


def test_least_recently_used_idle_graph_is_dropped(five):
    catalog, ids, build = five
    router = build()
    for gid in ids[:3]:
        touch(router, gid)
    touch(router, ids[0])            # Alpha is recent again; Beta is now the oldest
    touch(router, ids[3])
    assert sorted(loaded(router)) == sorted([ids[0], ids[2], ids[3]])


def test_a_leased_graph_is_never_dropped(five):
    catalog, ids, build = five
    router = build()
    key, service = router.acquire(ids[0])         # the oldest, and in use
    for gid in ids[1:4]:
        touch(router, gid)
    assert ids[0] in loaded(router)
    assert ids[1] not in loaded(router)           # the oldest idle graph went instead
    assert len(router.services) == 3
    assert service.store.connection.execute('SELECT 1').fetchone()   # its store is still open
    router.release(key)


def test_the_cap_is_soft_while_every_graph_is_in_use_and_enforced_at_release(five):
    catalog, ids, build = five
    router = build()
    held = [router.acquire(gid) for gid in ids[:4]]
    assert len(router.services) == 4              # nothing idle to drop
    router.release(held[0][0])
    assert ids[0] not in loaded(router)           # least recently used idle graph goes at release
    assert len(router.services) == 3
    for key, _ in held[1:]:
        router.release(key)
    assert len(router.services) == 3


def test_eviction_frees_the_loaded_context_and_tells_listeners(five):
    catalog, ids, build = five
    router = build()
    dropped = []
    router.on_evict.append(dropped.append)
    first = router.acquire(ids[0])
    service = first[1]
    service._context(catalog.graph(ids[0])['snapshot_id'])
    assert service.cache                            # a whole graph is held in memory
    router.release(first[0])
    for gid in ids[1:4]:
        touch(router, gid)
    assert not service.cache                        # dropped with the service, not left to the collector
    assert [key[0] for key in dropped] == [ids[0]]


def test_cap_is_configurable_and_validated(five, monkeypatch):
    catalog, ids, build = five
    assert build(max_loaded=2).max_loaded == 2
    for bad in (0, 9, 'two', 2.5, True):
        with pytest.raises(ValueError, match='max_loaded'):
            build(max_loaded=bad)
    monkeypatch.setenv('GEOGRAPHER_MAX_LOADED_GRAPHS', '2')
    assert build().max_loaded == 2
    monkeypatch.setenv('GEOGRAPHER_MAX_LOADED_GRAPHS', 'lots')
    with pytest.raises(ValueError, match='GEOGRAPHER_MAX_LOADED_GRAPHS'):
        build()


def test_composition_refuses_more_graphs_than_the_cap(five):
    catalog, ids, build = five
    router = build()
    assert len(compose_frame(router, [dict(graph_id=g) for g in ids[:3]])['frames']) == 3
    with pytest.raises(ValueError, match='at most 3 graphs'):
        compose_frame(router, [dict(graph_id=g) for g in ids[:4]])
    wide = build(max_loaded=5)
    assert len(compose_frame(wide, [dict(graph_id=g) for g in ids])['frames']) == 5
    assert len(wide.services) == 5


def test_composing_the_same_set_twice_does_not_reload_graphs(five):
    catalog, ids, build = five
    router = build()
    opened = []
    original = router._open

    def counting(graph_id):
        before = set(router.services)
        result = original(graph_id)
        opened.extend(k for k in router.services if k not in before)
        return result
    router._open = counting
    request = [dict(graph_id=g) for g in ids[:3]]
    compose_frame(router, request)
    compose_frame(router, request)
    assert len(opened) == 3                          # three loads, once each


def test_http_reports_the_cap_and_active_set_follows_it(five):
    catalog, ids, build = five
    router = build()
    with TestClient(create_graph_http(router), base_url='http://127.0.0.1:8774') as client:
        assert client.get('/api/workspace/context').json()['max_graphs'] == 3
        assert client.put('/api/workspace/active-graphs', json=dict(graph_ids=ids[:3])).status_code == 200
        refused = client.put('/api/workspace/active-graphs', json=dict(graph_ids=ids[:4]))
        assert refused.status_code == 400
        assert 'at most 3' in refused.json()['error']
        frame = client.post('/api/graphs/frame', json=dict(graphs=[dict(graph_id=g) for g in ids[:4]]))
        assert frame.status_code == 400
        assert 'at most 3 graphs' in frame.json()['error']
