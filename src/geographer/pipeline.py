"""Stage-gated, immutable ingestion orchestration."""
from __future__ import annotations

import sys
import time

from .extract import PythonExtractor
from .model import EXTRACTOR_VERSION, digest
from .source import Repository
from .store import SnapshotStore


def ingest(store: SnapshotStore, repositories: list[Repository], *, snapshot_id: str | None = None,
           publish: bool = True, stage: int = 1, previous_snapshot_id: str | None = None) -> dict:
    if stage not in (1,2,3):
        raise ValueError("Only Stage 1, Stage 2 or Stage 3 pipelines are available")
    if not repositories or len({r.repo_id for r in repositories})!=len(repositories):raise ValueError('Unique repository namespaces required')
    started = time.perf_counter()
    from .incremental import build_digest,normalizer_build_digest
    config = {"stage": stage, "runtime": sys.version, "grammar": f"{sys.version_info.major}.{sys.version_info.minor}",
              "implementation_digest":build_digest(),"normalizer_build_digest":normalizer_build_digest(),
              "extractor_version": EXTRACTOR_VERSION, "normalization_version": "py-ast-v1",
              "source_roots": {r.repo_id: list(r.source_roots) for r in repositories},
              "repository_isolation":{r.repo_id:{"resolution_group":r.resolution_group,"include_globs":list(r.include_globs),"exclude_globs":list(r.exclude_globs)} for r in repositories},
              "default_filter": {"families": ["static"], "statuses": ["exact"], "include_tests": False,
                                 "include_generated": False, "include_vendor": False, "include_external": True},
              "resource_limits": {"max_file_bytes": 4194304},
              "schema_digest": digest(store.connection.execute("SELECT sql FROM sqlite_master WHERE name='entities'").fetchone()[0])}
    normal_forms={};incremental=None
    if previous_snapshot_id:
        from .incremental import previous_normal_forms
        normal_forms,incremental=previous_normal_forms(store,previous_snapshot_id,repositories)
    sid = store.begin(repositories, config, snapshot_id)
    extractor = PythonExtractor(repositories,normal_forms=normal_forms)
    graph = extractor.extract()
    if stage >= 2:
        from .analysis import prepare_analysis
        prepare_analysis(graph)
    if stage >= 3:
        from .analysis import DEFAULT_FILTER
        from .contraction import contract_helpers
        membership,groups,certificate=contract_helpers(graph,sid)
        for eid,cluster in membership.items():graph.entities[eid].qi_cluster_id=cluster
        graph.analyses['qi:'+digest(DEFAULT_FILTER,2)]=dict(algorithm_version='helper_tree_balls_v1',scope={'filter':DEFAULT_FILTER,'max_diameter':2},
             result={'membership':membership,'groups':{r:sorted(m) for r,m in groups.items()},'certificate':certificate})
    if incremental:
        incremental['reused_normal_forms']=extractor.normal_reuse
        graph.analyses['incremental:'+digest(previous_snapshot_id)]=dict(algorithm_version='conservative-rebuild-v1',scope={'previous_snapshot_id':previous_snapshot_id},result=incremental)
    store.write_graph(sid, graph, extractor.failures)
    if stage >= 2:
        from .analysis import materialize_view
        for grouping in ({"mode":"atomic"},{"mode":"kind","kind":"file"},{"mode":"kind","kind":"repository"}):
            materialize_view(store,sid,graph,grouping)
    if publish:
        store.publish(sid)
    counts = {table: store.connection.execute(f"SELECT count(*) FROM {table} WHERE snapshot_id=?", (sid,)).fetchone()[0]
              for table in ("entities", "relationships", "evidence", "documentary_incidences")}
    statuses = dict(store.connection.execute("SELECT resolution_status,count(*) FROM relationships WHERE snapshot_id=? GROUP BY resolution_status", (sid,)))
    return {"snapshot_id": sid, "stage": stage, "status": "complete" if publish else "building",
            "counts": counts, "relationship_statuses": statuses, "parse_failures": extractor.failures,
            "elapsed_seconds": round(time.perf_counter() - started, 4), "incremental": incremental,
            "repositories": [{"repo_id": r.repo_id, "revision": r.revision, "digest": r.content_digest} for r in repositories]}
