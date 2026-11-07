"""SQLite snapshots: execute the approved DDL and validate before publication."""
from __future__ import annotations

from .resources import resource_root

import json
import math
import sqlite3
import hashlib
from dataclasses import asdict
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
from itertools import chain

from .model import Graph, Entity, Relationship, Evidence, canonical, digest, EXTRACTOR_VERSION
from .source import Repository, valid_path


class PublicationError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Snapshot publication rejected:\n" + "\n".join(problems))


class SnapshotStore:
    def __init__(self, path: str | Path = ":memory:", schema: Path | None = None, *, cache_mib: int = 64):
        self._columns={}
        self.connection = sqlite3.connect(str(path),check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        if type(cache_mib) is not int or not 1<=cache_mib<=256:raise ValueError('SQLite cache must be 1..256 MiB')
        self.cache_mib=cache_mib
        self.connection.execute(f'PRAGMA cache_size={-1024*cache_mib}')
        if sqlite3.sqlite_version_info < (3, 37):
            raise RuntimeError("SQLite >= 3.37 with JSON1 required")
        self.connection.execute("SELECT json_valid('{}')").fetchone()
        if not self.connection.execute("SELECT 1 FROM sqlite_master WHERE name='snapshot_sets'").fetchone():
            schema = schema or resource_root() / "contracts/geographer.schema.sql"
            self.connection.executescript(schema.read_text(encoding="utf-8"))
        if self.connection.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise RuntimeError("Unsupported database schema")
        # Runtime immutability enforcement supplements the unchanged normative DDL.
        for table in ("snapshots", "entities", "relationships", "evidence", "documentary_incidences"):
            for operation in ("INSERT", "UPDATE", "DELETE"):
                refs = ["NEW"] if operation == "INSERT" else ["OLD"] if operation == "DELETE" else ["OLD", "NEW"]
                condition = " OR ".join(f"EXISTS(SELECT 1 FROM snapshot_sets WHERE snapshot_id={ref}.snapshot_id AND status='complete')" for ref in refs)
                self.connection.execute(f"""CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation}
                  BEFORE {operation} ON {table} WHEN {condition}
                  BEGIN SELECT RAISE(ABORT,'Complete snapshot facts are immutable'); END""")
        self.connection.execute("""CREATE TRIGGER IF NOT EXISTS immutable_snapshot_status
          BEFORE UPDATE ON snapshot_sets WHEN OLD.status='complete'
          BEGIN SELECT RAISE(ABORT,'Complete snapshot manifests are immutable'); END""")
        self.connection.execute("""CREATE TRIGGER IF NOT EXISTS immutable_snapshot_delete
          BEFORE DELETE ON snapshot_sets WHEN OLD.status='complete'
          BEGIN SELECT RAISE(ABORT,'Complete snapshot manifests are immutable'); END""")
        self.connection.commit()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _insert(self, table: str, row: dict):
        if table not in self._columns:
            if table not in {r[0] for r in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
                raise ValueError('Unknown table')
            self._columns[table]={r[1] for r in self.connection.execute(f"PRAGMA table_info({table})")}
        allowed=self._columns[table]
        if not row or not set(row).issubset(allowed):
            raise ValueError(f"Invalid fields in {table} record")
        fields = ",".join(row)
        self.connection.execute(f"INSERT INTO {table}({fields}) VALUES({','.join('?' for _ in row)})", tuple(row.values()))

    def insert_many(self, table: str, rows):
        """Stream a homogeneous batch through executemany; caller owns transaction."""
        iterator=iter(rows);first=next(iterator,None)
        if first is None:return
        if table not in self._columns:
            if table not in {r[0] for r in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}:raise ValueError('Unknown table')
            self._columns[table]={r[1] for r in self.connection.execute(f'PRAGMA table_info({table})')}
        fields=tuple(first);keys=set(fields)
        if not fields or not keys<=self._columns[table]:raise ValueError('Invalid batch fields')
        def values():
            for row in chain((first,),iterator):
                if set(row)!=keys:raise ValueError('Heterogeneous batch fields')
                yield tuple(row[k] for k in fields)
        self.connection.executemany(f"INSERT INTO {table}({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",values())

    def begin(self, repositories: list[Repository], config: dict, snapshot_id: str | None = None) -> str:
        if len({r.repo_id for r in repositories}) != len(repositories):
            raise ValueError("Duplicate repository namespace")
        manifest = sorted((r.repo_id, r.revision, r.content_digest, list(r.source_roots)) for r in repositories)
        mh = digest(manifest, config)
        sid = snapshot_id or "snapshot:" + mh
        if self.connection.execute("SELECT 1 FROM snapshot_sets WHERE snapshot_id=?", (sid,)).fetchone():
            raise ValueError("Snapshot already exists; read it or choose a new build ID")
        with self.connection:
            self.connection.execute("INSERT INTO snapshot_sets VALUES(?,?,?,?,?)",
                                    (sid, mh, "building", datetime.now(timezone.utc).isoformat(), canonical(config)))
            for r in repositories:
                self.connection.execute("INSERT INTO snapshots VALUES(?,?,?,?,?,?)",
                                        (sid, r.repo_id, r.revision, r.content_digest, EXTRACTOR_VERSION, "[]"))
            self.connection.execute("INSERT INTO snapshots VALUES(?,?,?,?,?,?)",
                                    (sid, "@workspace", "manifest:" + mh, mh, EXTRACTOR_VERSION, "[]"))
        return sid

    def write_graph(self, sid: str, graph: Graph, failures: dict[str, list[dict]]):
        self.require_building(sid)
        with self.connection:
            for table, records in (("entities", graph.entities.values()), ("relationships", graph.relationships.values()),
                                   ("evidence", graph.evidence.values())):
                rows=iter(records)
                first=next(rows,None)
                if first is not None:
                    fields=['snapshot_id',*asdict(first)]
                    def values():
                        yield (sid,*asdict(first).values())
                        for record in rows:yield (sid,*asdict(record).values())
                    self.connection.executemany(f"INSERT INTO {table}({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",values())
            for incidence in graph.incidences:
                self._insert("documentary_incidences", {"snapshot_id": sid, **incidence})
            for aid, result in graph.analyses.items():
                self._insert("analysis_results", {"snapshot_id": sid, "analysis_id": aid,
                  "algorithm_version": result["algorithm_version"], "scope_json": canonical(result["scope"]),
                  "result_json": canonical(result["result"])})
            for repo, problems in failures.items():
                self.connection.execute("UPDATE snapshots SET parse_failures_json=? WHERE snapshot_id=? AND repo_id=?",
                                        (canonical(problems), sid, repo))

    def require_building(self, sid: str):
        row = self.connection.execute("SELECT status FROM snapshot_sets WHERE snapshot_id=?", (sid,)).fetchone()
        if row is None or row[0] != "building":
            raise ValueError("Snapshot is not building")

    def require_complete(self, sid: str):
        row = self.connection.execute("SELECT status FROM snapshot_sets WHERE snapshot_id=?", (sid,)).fetchone()
        if row is None or row[0] != "complete":
            raise ValueError("Snapshot is unavailable or unpublished")

    def validate(self, sid: str) -> list[str]:
        c = self.connection
        problems = []
        def bad(message):
            if len(problems) < 200:
                problems.append(message)
        if c.execute("PRAGMA foreign_key_check").fetchone():
            bad("foreign_key_check failed")
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            bad("integrity_check failed")
        snapshots = {r["repo_id"]: dict(r) for r in c.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (sid,))}
        for r in snapshots.values():
            for failure in json.loads(r["parse_failures_json"]):
                if not isinstance(failure, dict) or set(failure) != {"rel_path", "language", "code", "message"} or not all(isinstance(v, str) for v in failure.values()) or not valid_path(failure["rel_path"]):
                    bad("Invalid parse failure record")
        entities = {r["entity_id"]: dict(r) for r in c.execute("SELECT * FROM entities WHERE snapshot_id=?", (sid,))}
        children = defaultdict(list)
        roots = []
        for e in entities.values():
            if e['ast_body_hash'] is not None:
                cached=c.execute('SELECT algorithm_version,scope_json,result_json FROM analysis_results WHERE snapshot_id=? AND analysis_id=?',(sid,'norm:'+e['entity_id'])).fetchone()
                try:
                    representation=json.loads(cached['result_json'])['representation'] if cached else None
                    if cached is None or cached['algorithm_version']!='py-ast-v1' or json.loads(cached['scope_json'])!={'entity_id':e['entity_id']} or not isinstance(representation,str) or hashlib.sha256(representation.encode()).hexdigest()!=e['ast_body_hash']:
                        bad('Normalised AST hash/cache mismatch')
                except (KeyError,UnicodeError,TypeError):bad('Invalid normalisation cache')
            if e["parent_id"] is None:
                roots.append(e["entity_id"])
            else:
                children[e["parent_id"]].append(e["entity_id"])
                p = entities.get(e["parent_id"])
                if p is None or p["depth"] + 1 != e["depth"]:
                    bad("Invalid parent/depth: " + e["entity_id"])
                elif p["kind"] != "workspace" and p["repo_id"] != e["repo_id"]:
                    bad("Ownership crosses repository namespace")
        if len(roots) != 1 or entities.get(roots[0], {}).get("kind") != "workspace":
            bad("Expected one workspace root")
        visited = set()
        queue = list(roots)
        while queue:
            node = queue.pop()
            if node in visited:
                bad("Ownership cycle")
                continue
            visited.add(node)
            queue.extend(children[node])
        if visited != set(entities):
            bad("Disconnected/cyclic ownership tree")
        J = max(1, (max(1, len(entities)) - 1).bit_length() + 1)
        for e in entities.values():
            up = json.loads(e["ancestors_binary_lifting_json"])
            if len(up) != J or any(not isinstance(x, str) or x not in entities for x in up):
                bad("Invalid lifting array: " + e["entity_id"])
                continue
            expected = e["parent_id"] or e["entity_id"]
            if up[0] != expected:
                bad("Invalid immediate lifting ancestor")
            for j in range(1, J):
                prev = json.loads(entities[up[j-1]]["ancestors_binary_lifting_json"])
                if len(prev) <= j-1 or up[j] != prev[j-1]:
                    bad("Invalid binary lifting recurrence")
        rels = {r["relationship_id"]: dict(r) for r in c.execute("SELECT * FROM relationships WHERE snapshot_id=?", (sid,))}
        evs = defaultdict(list)
        for raw in c.execute("SELECT * FROM evidence WHERE snapshot_id=?", (sid,)):
            ev = dict(raw)
            evs[ev["relationship_id"]].append(ev)
            if ev["repo_id"] not in snapshots or ev["revision"] != snapshots[ev["repo_id"]]["revision"]:
                bad("Evidence revision mismatch")
            r = rels.get(ev["relationship_id"])
            if r:
                subject = entities.get(r["source_subject_id"])
                if subject and (subject["repo_id"] != ev["repo_id"] or subject["rel_path"] != ev["rel_path"]):
                    bad("Evidence source does not match relationship subject")
                allowed = {"exact": {"ast_exact", "history", "similarity"}, "candidate": {"static_candidate", "similarity", "history"},
                           "unresolved": {"unresolved"}, "observed": {"dynamic_observed"}, "declared": {"declared"}}
                if ev["category"] not in allowed[r["resolution_status"]]:
                    bad("Evidence category/status mismatch")
        for r in rels.values():
            if not evs[r["relationship_id"]]:
                bad("Relationship without evidence: " + r["relationship_id"])
            for endpoint, subject in ((r["source_id"], r["source_subject_id"]), (r["target_id"], r["target_subject_id"])):
                atom = entities.get(endpoint)
                if atom is None or children[endpoint]:
                    bad("Relationship endpoint is not a leaf")
                elif endpoint != subject and not (atom["kind"] == "scope_atom" and atom["parent_id"] == subject):
                    bad("Atom/subject mismatch")
                if atom is not None and atom["sort"] == "text":
                    bad("Document fragment in dependency graph")
        incidences = defaultdict(list)
        for r in c.execute("SELECT * FROM documentary_incidences WHERE snapshot_id=?", (sid,)):
            incidences[r["incidence_id"]].append(dict(r))
        for group in incidences.values():
            if len({(r["fragment_id"], r["role"]) for r in group}) != 1:
                bad("Inconsistent documentary hyperedge")
            fragment = entities.get(group[0]["fragment_id"], {})
            if fragment.get("sort") != "text" or fragment.get("kind") != "fragment":
                bad("Documentary hyperedge requires a text fragment")
        self._validate_derived(sid, entities, children, rels, evs, bad)
        return problems

    def _validate_derived(self, sid, entities, children, rels, evs, bad):
        c = self.connection
        from .analysis import eligible_entity, selected_relationships, condensations
        graph = None
        for view in c.execute("SELECT * FROM analysis_views WHERE snapshot_id=?", (sid,)).fetchall():
            if graph is None:
                graph = self.graph(sid,published_only=False)
            vid = view["view_id"]
            members = {r["atom_id"]: r["representative_id"] for r in c.execute(
                "SELECT * FROM partition_members WHERE snapshot_id=? AND view_id=?", (sid, vid))}
            reps = {r["representative_id"]: dict(r) for r in c.execute(
                "SELECT * FROM view_representatives WHERE snapshot_id=? AND view_id=?", (sid, vid))}
            filters=json.loads(view["filter_json"])
            if digest(filters)!=view["filter_hash"]:
                bad("View filter hash mismatch")
            universe = [eid for eid,e in graph.entities.items() if not children[eid] and eligible_entity(e,filters)]
            if set(universe) != set(members) or any(children[e] for e in members):
                bad("Partition does not exactly cover the declared leaf universe")
            member_counts=Counter(members.values())
            for rep, row in reps.items():
                if row["member_count"] != member_counts[rep]:
                    bad("Representative member_count mismatch")
            projected=[]
            seen_witnesses=set()
            for proj in c.execute("SELECT * FROM quotient_projections WHERE snapshot_id=? AND view_id=?", (sid, vid)):
                projected.append(dict(proj))
                witnesses = [r[0] for r in c.execute("SELECT relationship_id FROM quotient_witness_map WHERE snapshot_id=? AND view_id=? AND projection_id=?", (sid, vid, proj["projection_id"]))]
                seen_witnesses.update(witnesses)
                if len(witnesses) != proj["witness_count"] or sum(len(evs[r]) for r in witnesses) != proj["evidence_count"]:
                    bad("Quotient witness/evidence counts mismatch")
                if not math.isclose(sum(rels[r]["weight"] for r in witnesses), proj["aggregated_weight"], rel_tol=1e-10):
                    bad("Quotient aggregate weight mismatch")
                for rid in witnesses:
                    r = rels[rid]
                    source, target = members.get(r["source_id"]), members.get(r["target_id"])
                    if r["direction"] == "symmetric" and source and target:
                        source, target = sorted([source, target])
                    if (source, target) != (proj["source_rep_id"], proj["target_rep_id"]) or any(r[k] != proj[k] for k in ("family", "subtype", "direction", "resolution_status", "weight_unit")):
                        bad("Quotient witness projection/type mismatch")
            expected_witnesses={r.relationship_id for r in selected_relationships(graph,filters)}
            if seen_witnesses!=expected_witnesses:
                bad("Quotient witness map omits or invents eligible relationships")
            edges=[(r["source_rep_id"],r["target_rep_id"]) for r in projected if r["family"] in {"static","runtime"} and r["direction"]=="directed"]
            expected_scc=condensations(sid,vid,view["filter_hash"],reps,edges)
            actual_scc={r["representative_id"]:dict(r) for r in c.execute("SELECT * FROM level_scc_condensations WHERE snapshot_id=? AND view_id=?",(sid,vid))}
            if set(actual_scc)!=set(expected_scc):
                bad("SCC condensation membership incomplete")
            for rep,expected in expected_scc.items():
                if rep in actual_scc and any(actual_scc[rep][k]!=v for k,v in expected.items()):
                    bad("SCC membership/size/rank mismatch")
        layouts = defaultdict(list)
        for r in c.execute("SELECT * FROM layouts WHERE snapshot_id=?", (sid,)):
            layouts[(r["layout_version"], r["seed"])].append(dict(r))
        for rows in layouts.values():
            byid = {r["entity_id"]: r for r in rows}
            siblings = defaultdict(list)
            for eid, r in byid.items():
                if any(not math.isfinite(r[k]) for k in ("center_x", "center_y", "center_z", "radius")):
                    bad("Nonfinite layout")
                p = entities[eid]["parent_id"]
                if p in byid:
                    pr = byid[p]
                    distance = math.dist(tuple(r[k] for k in ("center_x", "center_y", "center_z")), tuple(pr[k] for k in ("center_x", "center_y", "center_z")))
                    if distance + r["radius"] > pr["radius"] - .35 + 1e-4:
                        bad("Layout containment violation")
                siblings[p].append(r)
            for group in siblings.values():
                for i, a in enumerate(group):
                    for b in group[i+1:]:
                        if math.dist(tuple(a[k] for k in ("center_x", "center_y", "center_z")), tuple(b[k] for k in ("center_x", "center_y", "center_z"))) < a["radius"] + b["radius"] + .2 - 1e-4:
                            bad("Layout sibling overlap")

    def publish(self, sid: str):
        self.require_building(sid)
        # An IMMEDIATE transaction prevents facts changing between validation and status update.
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            problems = self.validate(sid)
            if problems:
                raise PublicationError(problems)
            self.connection.execute("UPDATE snapshot_sets SET status='complete' WHERE snapshot_id=?", (sid,))
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def graph(self, sid: str, published_only=True) -> Graph:
        if published_only:
            self.require_complete(sid)
        g = Graph()
        for table, cls, collection in (("entities", Entity, g.entities), ("relationships", Relationship, g.relationships), ("evidence", Evidence, g.evidence)):
            key = {"entities": "entity_id", "relationships": "relationship_id", "evidence": "evidence_id"}[table]
            for raw in self.connection.execute(f"SELECT * FROM {table} WHERE snapshot_id=? ORDER BY {key}", (sid,)):
                record = dict(raw)
                record.pop("snapshot_id")
                collection[record[key]] = cls(**record)
        g.incidences = [{k: v for k, v in dict(r).items() if k != "snapshot_id"} for r in self.connection.execute(
            "SELECT * FROM documentary_incidences WHERE snapshot_id=? ORDER BY incidence_id,entity_id", (sid,))]
        for r in self.connection.execute("SELECT * FROM analysis_results WHERE snapshot_id=?", (sid,)):
            g.analyses[r["analysis_id"]] = {"algorithm_version": r["algorithm_version"], "scope": json.loads(r["scope_json"]), "result": json.loads(r["result_json"])}
        return g

    def export(self, sid: str) -> dict:
        self.require_complete(sid)
        tables = ("snapshot_sets", "snapshots", "entities", "relationships", "evidence", "documentary_incidences", "analysis_results")
        result = {}
        for table in tables:
            rows = [dict(r) for r in self.connection.execute(f"SELECT * FROM {table} WHERE snapshot_id=?", (sid,))]
            result[table] = sorted(rows, key=canonical)
        return {"schema_version": 1, "tables": result}

    def import_snapshot(self, archive: dict) -> str:
        if archive.get("schema_version") != 1:
            raise ValueError("Unsupported export version")
        tables = archive["tables"]
        sid = tables["snapshot_sets"][0]["snapshot_id"]
        with self.connection:
            for table in ("snapshot_sets", "snapshots", "entities", "relationships", "evidence", "documentary_incidences", "analysis_results"):
                for original in tables[table]:
                    row = dict(original)
                    if table == "snapshot_sets":
                        row["status"] = "building"
                    self._insert(table, row)
        self.publish(sid)
        return sid

    def merge(self, sources: list[tuple["SnapshotStore", str]], *, stage: int = 3) -> str:
        """Namespace-preserving fact union; no resolver rerun can reverse old facts."""
        if stage not in (1,2,3):raise ValueError('Invalid merge stage')
        graph = Graph()
        repos, failures = {}, {}
        for source, sid in sources:
            source.require_complete(sid)
            for raw in source.connection.execute("SELECT * FROM snapshots WHERE snapshot_id=? AND repo_id<>'@workspace'", (sid,)):
                row = dict(raw)
                repo = row["repo_id"]
                if repo in repos:
                    raise ValueError("Cannot merge duplicate repository namespace: " + repo)
                repos[repo] = row
                failures[repo] = json.loads(row["parse_failures_json"])
            incoming = source.graph(sid)
            for eid, e in incoming.entities.items():
                if e.kind == "workspace" and eid in graph.entities:
                    continue
                graph.add(e)
            graph.relationships.update(incoming.relationships)
            graph.evidence.update(incoming.evidence)
            graph.incidences.extend(incoming.incidences)
            for aid,result in incoming.analyses.items():
                # Source evidence survives; source-local query plans, partitions,
                # diagnostics and layout caches do not describe the new union.
                if result['algorithm_version'] in {'source-bytes-v1','py-ast-v1','documentary-v1','documentary-v2','documentary-tree-v1','source-context-v1','declaration-v1','c3-static-v1','tree-sitter-syntax-v1','runtime-collection-v1'}:
                    graph.analyses[aid]=result
        graph.augment()
        config = {"stage": stage, "merge": sorted((sid for _, sid in sources)), "mode": "disjoint_fact_union", "merge_version":"namespace-union-v2"}
        manifest = digest([(k, r["revision"], r["digest"]) for k, r in sorted(repos.items())], config)
        sid = "snapshot:" + manifest
        if self.connection.execute("SELECT 1 FROM snapshot_sets WHERE snapshot_id=? AND status='complete'",(sid,)).fetchone():return sid
        for entity in graph.entities.values():entity.qi_cluster_id=None;entity.wl_3hop_hash=None
        if stage>=2:
            from .analysis import prepare_analysis
            prepare_analysis(graph)
        if stage>=3:
            from .analysis import DEFAULT_FILTER
            from .contraction import contract_helpers
            membership,groups,certificate=contract_helpers(graph,sid)
            for eid,cluster in membership.items():graph.entities[eid].qi_cluster_id=cluster
            graph.analyses['qi:'+digest(DEFAULT_FILTER,2)]=dict(algorithm_version='helper_tree_balls_v1',scope={'filter':DEFAULT_FILTER,'max_diameter':2},result={'membership':membership,'groups':{r:sorted(m) for r,m in groups.items()},'certificate':certificate})
        with self.connection:
            self.connection.execute("INSERT INTO snapshot_sets VALUES(?,?,?,?,?)",
                                    (sid, manifest, "building", datetime.now(timezone.utc).isoformat(), canonical(config)))
            self.connection.execute("INSERT INTO snapshots VALUES(?,?,?,?,?,?)", (sid, "@workspace", "manifest:" + manifest, manifest, EXTRACTOR_VERSION, "[]"))
            for r in repos.values():
                self._insert("snapshots", {**r, "snapshot_id": sid})
        self.write_graph(sid, graph, failures)
        if stage>=2:
            from .analysis import materialize_view
            for grouping in ({'mode':'atomic'},{'mode':'kind','kind':'file'},{'mode':'kind','kind':'repository'}):materialize_view(self,sid,graph,grouping)
        self.publish(sid)
        return sid
