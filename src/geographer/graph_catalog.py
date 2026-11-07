"""Independent project stores and explicit, non-merging graph bridges."""
from __future__ import annotations
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sqlite3
import threading

from .model import canonical,digest
from .pipeline import ingest
from .store import SnapshotStore

DDL='''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS graphs(
 graph_id TEXT PRIMARY KEY,root_key TEXT NOT NULL UNIQUE,root_path TEXT NOT NULL,
 label TEXT NOT NULL,code_database TEXT NOT NULL UNIQUE,paper_database TEXT UNIQUE,
 snapshot_id TEXT,profile_json TEXT NOT NULL CHECK(json_valid(profile_json)),created_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS overlap_decisions(
 graph_a TEXT NOT NULL REFERENCES graphs(graph_id),graph_b TEXT NOT NULL REFERENCES graphs(graph_id),
 decision TEXT NOT NULL CHECK(decision IN ('keep_separate','child_module')),created_at TEXT NOT NULL,
 PRIMARY KEY(graph_a,graph_b)
) STRICT;
CREATE TABLE IF NOT EXISTS bridges(
 bridge_id TEXT PRIMARY KEY,source_graph TEXT NOT NULL REFERENCES graphs(graph_id),source_ref TEXT NOT NULL,
 target_graph TEXT NOT NULL REFERENCES graphs(graph_id),target_ref TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('child_module','reference','concept_equivalence','document_identity')),
 rationale TEXT NOT NULL,evidence_json TEXT NOT NULL CHECK(json_valid(evidence_json)),created_at TEXT NOT NULL,
 CHECK(source_graph<>target_graph)
) STRICT;
CREATE TABLE IF NOT EXISTS merge_receipts(
 plan_id TEXT PRIMARY KEY,graph_id TEXT NOT NULL REFERENCES graphs(graph_id),
 plan_json TEXT NOT NULL CHECK(json_valid(plan_json)),receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json))
) STRICT;
CREATE TRIGGER IF NOT EXISTS merge_receipts_no_update BEFORE UPDATE ON merge_receipts BEGIN SELECT RAISE(ABORT,'Merge receipts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS merge_receipts_no_delete BEFORE DELETE ON merge_receipts BEGIN SELECT RAISE(ABORT,'Merge receipts are immutable'); END;
'''


class CollisionReview(ValueError):
    def __init__(self,plan):
        self.plan=plan
        super().__init__('Root overlap requires an explicit keep_separate or child_module decision; no graph was imported')


class GraphCatalog:
    def __init__(self,path):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.connection=sqlite3.connect(self.path,check_same_thread=False)
        self.connection.row_factory=sqlite3.Row
        names={r[0] for r in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if names-{'graphs','overlap_decisions','bridges','merge_receipts'}:
            self.connection.close();raise ValueError('This database is not a graph catalog; no tables were added')
        self.connection.executescript(DDL)
        self.lock=threading.RLock()
        self.merge_lock=threading.Lock();self.import_lock=threading.Lock()

    def close(self):self.connection.close()

    @staticmethod
    def root_identity(root):
        path=Path(root).resolve()
        return path,os.path.normcase(str(path))

    def graph(self,graph_id):
        with self.lock:
            row=self.connection.execute('SELECT * FROM graphs WHERE graph_id=?',(graph_id,)).fetchone()
            if row is None:raise ValueError('Unknown graph_id')
            return dict(row)

    def graphs(self):
        with self.lock:return [dict(r) for r in self.connection.execute('SELECT * FROM graphs ORDER BY label,graph_id')]

    def register_existing_store(self,path):
        """Expose an already indexed main database without re-ingestion or ID rewriting."""
        path=Path(path).resolve()
        with self.lock,self.connection:
            existing=self.connection.execute('SELECT graph_id FROM graphs WHERE code_database=?',(str(path),)).fetchone()
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as source:
                sid=source.execute("SELECT snapshot_id FROM snapshot_sets WHERE status='complete' ORDER BY created_at DESC,snapshot_id DESC LIMIT 1").fetchone()
                if not sid:raise ValueError('Main store has no published snapshot')
                owners=sorted(r[0] for r in source.execute("SELECT DISTINCT repo_id FROM snapshots WHERE repo_id<>'@workspace'"))
            if existing:
                row=self.graph(existing[0]);profile=json.loads(row['profile_json'])
                if profile.get('existing_store'):
                    if owners!=profile['owner_repo_ids']:raise ValueError('Registered store ownership changed')
                    self.connection.execute('UPDATE graphs SET snapshot_id=? WHERE graph_id=?',(sid[0],existing[0]))
                return existing[0]
            for row in self.graphs():
                other=Path(row['code_database'])
                if other.is_file() and other.samefile(path):return row['graph_id']
            gid='g_'+digest('registered-store-v1',os.path.normcase(str(path)))[:24]
            if self.connection.execute('SELECT 1 FROM graphs WHERE graph_id=?',(gid,)).fetchone():raise ValueError('Existing-store graph identity collision')
            profile=canonical(dict(graph_kind='registered_store',owner_repo_ids=owners,existing_store=True))
            self.connection.execute('INSERT INTO graphs VALUES(?,?,?,?,?,NULL,?,?,?)',(gid,'store:'+os.path.normcase(str(path)),str(path),', '.join(owners),str(path),sid[0],profile,datetime.now(timezone.utc).isoformat()))
            return gid

    def plan_root(self,root):
        path,key=self.root_identity(root)
        if not path.is_dir():raise ValueError('Project root must be an existing directory')
        collisions=[];existing=None
        for row in self.graphs():
            if row['root_key'].startswith(('merge:','store:')):continue
            other=Path(row['root_path'])
            if key==row['root_key']:existing=row['graph_id']
            elif path.is_relative_to(other):collisions.append(dict(graph_id=row['graph_id'],relation='inside_existing_root'))
            elif other.is_relative_to(path):collisions.append(dict(graph_id=row['graph_id'],relation='contains_existing_root'))
        facts=dict(root_path=str(path),existing_graph_id=existing,collisions=collisions)
        candidate=existing or 'g_'+digest(key)[:24]
        with self.lock:
            known={(r[0],r[1]) for r in self.connection.execute('SELECT graph_a,graph_b FROM overlap_decisions')}
        requires_review=any(tuple(sorted((candidate,c['graph_id']))) not in known for c in collisions)
        return dict(**facts,plan_id=digest(facts),requires_review=requires_review,choices=['keep_separate','child_module'] if collisions else [],
            merge_policy='No automatic merge. A merge needs a separately reviewed migration plan; existing graphs/snapshots remain immutable.')

    def _review(self,root,decision):
        plan=self.plan_root(root)
        with self.lock:
            known={(r['graph_a'],r['graph_b']) for r in self.connection.execute('SELECT graph_a,graph_b FROM overlap_decisions')}
            gid=plan['existing_graph_id'] or 'g_'+digest(os.path.normcase(plan['root_path']))[:24]
            occupied=self.connection.execute('SELECT root_key FROM graphs WHERE graph_id=?',(gid,)).fetchone()
        if occupied and occupied[0]!=os.path.normcase(plan['root_path']):raise ValueError('Graph identity collision; existing store was not modified')
        undecided=[c for c in plan['collisions'] if tuple(sorted((gid,c['graph_id']))) not in known]
        if undecided and decision not in {'keep_separate','child_module'}:raise CollisionReview(plan)
        return plan,gid,undecided

    def import_project(self,root,repository,*,label=None,decision=None,expected_plan=None,stage=3):
        plan,gid,_=self._review(root,decision)
        if expected_plan is not None and expected_plan!=plan['plan_id']:raise ValueError('Root plan changed; review overlaps again')
        database=self.path.parent/'graphs'/gid/'code.sqlite';database.parent.mkdir(parents=True,exist_ok=True)
        # Each graph has its own namespace even if different roots use the
        # same caller-provided repository label or identical source bytes.
        repository.repo_id=gid;repository.resolution_group=None
        from .incremental import build_digest
        implementation=build_digest();report=None
        # Long ingestion runs outside the catalog write transaction; an
        # unregistered snapshot is harmless and is reused by a later import.
        with self.import_lock,SnapshotStore(database) as store:
            for row in store.connection.execute("SELECT s.snapshot_id,ss.config_json FROM snapshots s JOIN snapshot_sets ss ON ss.snapshot_id=s.snapshot_id WHERE s.repo_id=? AND s.digest=? AND ss.status='complete' ORDER BY ss.created_at DESC",(gid,repository.content_digest)):
                config=json.loads(row['config_json']);policy=config.get('repository_isolation',{}).get(gid,{})
                if config.get('implementation_digest')==implementation and config.get('stage')==stage and config.get('source_roots',{}).get(gid)==list(repository.source_roots) and policy.get('include_globs')==list(repository.include_globs) and policy.get('exclude_globs')==list(repository.exclude_globs):
                    report=dict(snapshot_id=row['snapshot_id'],status='reused',repositories=[dict(repo_id=gid,digest=repository.content_digest)]);break
            if report is None:report=ingest(store,[repository],stage=stage)
        profile=dict(source_roots=list(repository.source_roots),include_globs=list(repository.include_globs),exclude_globs=list(repository.exclude_globs))
        # Publish in a short writer transaction, re-checking overlaps so a root
        # registered meanwhile still requires review.
        with self.lock,self.connection:
            self.connection.execute('BEGIN IMMEDIATE')
            current,_,undecided=self._review(root,decision)
            if current['plan_id']!=plan['plan_id']:raise ValueError('Root plan changed during ingestion; review overlaps again')
            now=datetime.now(timezone.utc).isoformat()
            self.connection.execute('INSERT INTO graphs VALUES(?,?,?,?,?,NULL,?,?,?) ON CONFLICT(graph_id) DO UPDATE SET label=excluded.label,snapshot_id=excluded.snapshot_id,profile_json=excluded.profile_json',
                (gid,os.path.normcase(plan['root_path']),plan['root_path'],label or Path(root).name,str(database),report['snapshot_id'],canonical(profile),now))
            for collision in undecided:
                a,b=sorted((gid,collision['graph_id']))
                self.connection.execute('INSERT INTO overlap_decisions VALUES(?,?,?,?)',(a,b,decision,now))
                if decision=='child_module':
                    parent,child=(collision['graph_id'],gid) if collision['relation']=='inside_existing_root' else (gid,collision['graph_id'])
                    self.add_bridge(parent,'root',child,'root','child_module','Operator declared a separate child module',[{'root_plan_id':plan['plan_id']}])
        return dict(graph_id=gid,root_plan=plan,ingestion=report)

    def attach_papers(self,graph_id,path):
        path=Path(path).resolve()
        if not path.is_file():raise ValueError('Paper database does not exist')
        # Do not share a physical paper corpus between project identities.
        with self.lock,self.connection:
            self.graph(graph_id)
            other=self.connection.execute('SELECT graph_id FROM graphs WHERE paper_database=? AND graph_id<>?',(str(path),graph_id)).fetchone()
            if other:raise ValueError('Paper database already belongs to another graph')
            for row in self.connection.execute('SELECT paper_database FROM graphs WHERE graph_id<>? AND paper_database IS NOT NULL',(graph_id,)):
                if Path(row[0]).is_file() and Path(row[0]).samefile(path):raise ValueError('Paper database is a physical alias of another graph store')
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as papers:
                if not papers.execute("SELECT 1 FROM sqlite_master WHERE name='read_documents'").fetchone():raise ValueError('Paper read model missing')
            self.connection.execute('UPDATE graphs SET paper_database=? WHERE graph_id=?',(str(path),graph_id))

    def add_bridge(self,source_graph,source_ref,target_graph,target_ref,kind,rationale,evidence):
        if source_graph==target_graph:raise ValueError('Bridge endpoints must be different graphs')
        if kind not in {'child_module','reference','concept_equivalence','document_identity'}:raise ValueError('Unknown bridge kind')
        if not isinstance(rationale,str) or not rationale.strip() or len(rationale)>2000:raise ValueError('Bounded rationale required')
        if not isinstance(evidence,list) or not evidence or len(canonical(evidence))>8000:raise ValueError('Bounded provenance evidence required')
        if any(not isinstance(r,str) or not r or len(r)>300 for r in (source_ref,target_ref)):raise ValueError('Bounded endpoint references required')
        with self.lock:
            self.graph(source_graph);self.graph(target_graph)
            bid='b_'+digest(source_graph,source_ref,target_graph,target_ref,kind,rationale,evidence)[:24]
            owned=not self.connection.in_transaction
            try:
                self.connection.execute('INSERT OR IGNORE INTO bridges VALUES(?,?,?,?,?,?,?,?,?)',
                    (bid,source_graph,source_ref,target_graph,target_ref,kind,rationale,canonical(evidence),datetime.now(timezone.utc).isoformat()))
                if owned:self.connection.commit()
            except BaseException:
                if owned:self.connection.rollback()
                raise
            return bid

    def bridges(self,graph_ids):
        if not isinstance(graph_ids,list) or not 1<=len(graph_ids)<=19 or len(set(graph_ids))!=len(graph_ids):raise ValueError('Choose 1..19 distinct graph IDs')
        for gid in graph_ids:self.graph(gid)
        slots=','.join('?' for _ in graph_ids)
        with self.lock:
            return [dict(r) for r in self.connection.execute('SELECT * FROM bridges WHERE source_graph IN ('+slots+') AND target_graph IN ('+slots+') ORDER BY bridge_id',(*graph_ids,*graph_ids))]
