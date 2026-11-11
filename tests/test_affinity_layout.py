import math
import shutil
import sqlite3
import time
from pathlib import Path

import pytest

from geographer.geometry import pack_siblings_affinity, layout_bands, violations, pack_siblings, unit, dot

IDS = [f"n{i}" for i in range(10)]
RADII = [0.4] * 10
# hub n0 coupled to n1..n4; pairs n5-n6 and n7-n8 coupled; n9 isolated (with external calls)
AFF = {("n0", f"n{i}"): 3.0 for i in range(1, 5)} | {("n5", "n6"): 2.0, ("n7", "n8"): 2.0}
EXT = {"n9": 4.0, "n0": 2.0}


def test_bands_follow_master_g14():
    b = layout_bands(IDS, AFF, EXT)
    assert b["n0"][0] == "core" and 0.05 <= b["n0"][1] <= 0.42
    assert b["n5"][0] == "mantle" and 0.42 <= b["n5"][1] <= 0.72
    assert b["n7"][0] == "mantle" and b["n8"][0] == "mantle"
    assert b["n9"][0] == "crust" and 0.72 <= b["n9"][1] < 0.95
    assert layout_bands(IDS, AFF, {})["n9"] == ("crust", 0.95)


def test_no_overlap_and_containment():
    centres, radius, fallback, err = pack_siblings_affinity(IDS, RADII, 10, "s", AFF, EXT)
    assert violations(centres, RADII, radius) <= 1e-4


def test_radial_order_core_mantle_crust():
    centres, radius, *_ = pack_siblings_affinity(IDS, RADII, 10, "s", AFF, EXT)
    r = {i: math.sqrt(dot(c, c)) / radius for i, c in zip(IDS, centres)}
    mantle = [r[i] for i in ("n5", "n6", "n7", "n8")]
    assert r["n0"] < min(mantle) and max(mantle) < r["n9"]


def _angular_gap(**kw):
    centres, *_ = pack_siblings_affinity(IDS, RADII, 10, "s", AFF, EXT, **kw)
    bands = layout_bands(IDS, AFF, EXT)
    d = {i: unit(c) for i, c in zip(IDS, centres) if bands[i][1] > 0.42}
    pairs = [(a, b) for a in sorted(d) for b in sorted(d) if a < b]
    affine = [dot(d[a], d[b]) for a, b in pairs if (a, b) in AFF]
    zero = [dot(d[a], d[b]) for a, b in pairs if (a, b) not in AFF]
    assert len(affine) >= 2
    return sum(affine) / len(affine), sum(zero) / len(zero)


def test_affine_pairs_cluster_by_angle():
    # F6: directions are only meaningful outside the core band.
    affine, zero = _angular_gap()
    print("default radius cosines", affine, zero)
    assert affine > zero


def test_affine_pairs_cluster_by_angle_with_slack():
    affine, zero = _angular_gap(preferred_radius=4.0)
    assert affine > zero


def test_input_order_invariant_and_deterministic():
    a = pack_siblings_affinity(IDS, RADII, 10, "s", AFF, EXT)
    perm = list(reversed(IDS))
    b = pack_siblings_affinity(perm, [0.4] * 10, 10, "s", AFF, EXT)
    assert dict(zip(IDS, a[0])) == dict(zip(perm, b[0]))


def test_no_affinity_degenerates_to_valid_layout():
    centres, radius, fallback, err = pack_siblings_affinity(IDS, RADII, 10, "s", {}, {})
    assert violations(centres, RADII, radius) <= 1e-4 and all(layout_bands(IDS, {}, {})[i] == ("crust", 0.95) for i in IDS)


def test_large_sibling_count_skips_relaxation_but_stays_valid():
    ids = [f"m{i:03d}" for i in range(400)]
    centres, radius, *_ = pack_siblings_affinity(ids, [0.2] * 400, 400, "s", {}, {})
    assert violations(centres, [0.2] * 400, radius) <= 1e-4


def test_old_layout_version_unchanged(frame_for):
    old = frame_for(grouping={"mode": "atomic"})                  # requests sphere-pack-v1
    assert old["layout_version"] == "sphere-pack-v1"
    new = frame_for(grouping={"mode": "atomic"}, layout_version="sphere-affinity-v1")
    assert new["layout_version"] == "sphere-affinity-v1" and new["spheres"] != old["spheres"]


def test_affinity_version_rejected_on_v1_0_request(frame_for):
    from conftest import viewport_request
    frame_for(grouping={"mode": "atomic"})
    svc = frame_for.svc
    sid = next(iter(svc.store.connection.execute("SELECT snapshot_id FROM snapshots")))[0]
    root = next(e.entity_id for e in svc._context(sid)["g"].entities.values() if e.kind == "repository")
    req = viewport_request(sid, root)
    req["layout_version"] = "sphere-affinity-v1"
    result = svc.query("viewport_frame", req)
    assert "error" in result


TOOLSET = Path("F:/uv-data/Geo_Grapher/output/toolset.sqlite")


@pytest.mark.integration
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.skipif(not TOOLSET.exists(), reason="ToolSet gate store absent")
def test_affinity_layout_latency_toolset(tmp_path):
    from geographer.service import QueryService
    from geographer.store import SnapshotStore
    from conftest import viewport_request
    copy = tmp_path / "toolset.sqlite"
    shutil.copy(TOOLSET, copy)
    store = SnapshotStore(copy)
    try:
        svc = QueryService(store, secret=b"x" * 32)
        sid = store.connection.execute("SELECT snapshot_id FROM snapshots ORDER BY rowid DESC LIMIT 1").fetchone()[0]
        ctx = svc._context(sid)
        root = next(e.entity_id for e in ctx["g"].entities.values() if e.kind == "repository")
        req = viewport_request(sid, root)
        req.update(schema_version="1.1", grouping={"mode": "atomic"}, layout_version="sphere-affinity-v1")
        t = time.perf_counter()
        result = svc.query("viewport_frame", req)
        elapsed = time.perf_counter() - t
        assert "error" not in result, result
        assert elapsed <= 3.0, elapsed
    finally:
        store.close()
