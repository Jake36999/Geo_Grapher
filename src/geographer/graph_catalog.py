"""Independent project stores and explicit, non-merging graph bridges."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime,timezone
import gc
import json
import os
from pathlib import Path
import sqlite3
import shutil
import threading
import time

from .model import canonical,digest
from .pipeline import ingest
from .store import SnapshotStore
from .source import Repository

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
CREATE TABLE IF NOT EXISTS bridge_bindings(
 bridge_id TEXT NOT NULL REFERENCES bridges(bridge_id) ON DELETE CASCADE,
 side TEXT NOT NULL CHECK(side IN ('source','target')),
 graph_id TEXT NOT NULL,ref TEXT NOT NULL,snapshot_id TEXT,paper_read_model TEXT,
 fingerprint_json TEXT NOT NULL CHECK(json_valid(fingerprint_json)),
 PRIMARY KEY(bridge_id,side)
) STRICT;
CREATE TABLE IF NOT EXISTS bridge_proposals(
 proposal_id TEXT PRIMARY KEY,source_graph TEXT NOT NULL,source_ref TEXT NOT NULL,
 target_graph TEXT NOT NULL,target_ref TEXT NOT NULL,kind TEXT NOT NULL,
 score REAL NOT NULL,features_json TEXT NOT NULL CHECK(json_valid(features_json)),
 status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected')),
 decided_at TEXT,decision_rationale TEXT
) STRICT;
CREATE TABLE IF NOT EXISTS artifact_justifications(
 artifact_id TEXT NOT NULL,clause_id TEXT NOT NULL,
 premise_id TEXT NOT NULL,
 premise_kind TEXT NOT NULL CHECK(premise_kind IN ('ground','upstream')),
 graph_id TEXT,ref TEXT,contract TEXT,baseline_snapshot_id TEXT,baseline_json TEXT,upstream_id TEXT,
 CHECK((premise_kind='ground' AND graph_id IS NOT NULL AND ref IS NOT NULL AND contract IS NOT NULL AND upstream_id IS NULL)
    OR (premise_kind='upstream' AND upstream_id IS NOT NULL AND graph_id IS NULL)),
 PRIMARY KEY(artifact_id,clause_id,premise_id)
) STRICT;
CREATE INDEX IF NOT EXISTS justifications_by_ground ON artifact_justifications(graph_id,ref) WHERE premise_kind='ground';
CREATE INDEX IF NOT EXISTS justifications_by_upstream ON artifact_justifications(upstream_id) WHERE premise_kind='upstream';
CREATE TABLE IF NOT EXISTS artifact_states(
 artifact_id TEXT PRIMARY KEY,artifact_kind TEXT NOT NULL CHECK(artifact_kind IN ('bridge','discovery_card','external')),
 state TEXT NOT NULL CHECK(state IN ('accepted','provisional_reanchored','suspect_stale','demoted_contestable')),
 updated_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS revision_ledger(
 event_id TEXT PRIMARY KEY,artifact_id TEXT NOT NULL,graph_id TEXT,old_snapshot_id TEXT,new_snapshot_id TEXT,
 prior_state TEXT NOT NULL,next_state TEXT NOT NULL,hop INTEGER NOT NULL,rationale_json TEXT NOT NULL CHECK(json_valid(rationale_json)),
 recorded_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS ledger_append_only_u BEFORE UPDATE ON revision_ledger BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_append_only_d BEFORE DELETE ON revision_ledger BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;
CREATE TABLE IF NOT EXISTS merge_receipts(
 plan_id TEXT PRIMARY KEY,graph_id TEXT NOT NULL REFERENCES graphs(graph_id),
 plan_json TEXT NOT NULL CHECK(json_valid(plan_json)),receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json))
) STRICT;
CREATE TRIGGER IF NOT EXISTS merge_receipts_no_update BEFORE UPDATE ON merge_receipts BEGIN SELECT RAISE(ABORT,'Merge receipts are immutable'); END;
CREATE TRIGGER IF NOT EXISTS merge_receipts_no_delete BEFORE DELETE ON merge_receipts BEGIN SELECT RAISE(ABORT,'Merge receipts are immutable'); END;
'''


CATALOG_TABLES=frozenset({'graphs','overlap_decisions','bridges','merge_receipts','bridge_bindings','bridge_proposals','artifact_justifications','artifact_states','revision_ledger'})


class CollisionReview(ValueError):
    def __init__(self,plan):
        self.plan=plan
        super().__init__('Root overlap requires an explicit keep_separate or child_module decision; no graph was imported')


class GraphCatalog:
    def __init__(self,path):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.connection=sqlite3.connect(self.path,check_same_thread=False,timeout=5)
        self.connection.row_factory=sqlite3.Row
        # The serving process and the Core's apply/import subprocesses share this file: readers must
        # not block a writer, and a writer waits briefly instead of failing (2026-11-17).
        self.connection.execute('PRAGMA busy_timeout=5000')
        self.connection.execute('PRAGMA journal_mode=WAL')
        names={r[0] for r in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if names-CATALOG_TABLES:
            self.connection.close();raise ValueError('This database is not a graph catalog; no tables were added')
        self.connection.executescript(DDL)
        self._bind_legacy_bridges()
        self.lock=threading.RLock()
        self.merge_lock=threading.Lock();self.import_lock=threading.Lock()
        self._copying=set()

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

    def owns_store(self,row):
        """True only for a store under <catalog_dir>/graphs/<graph_id>/; anything else is registered."""
        try:return Path(row['code_database']).resolve().is_relative_to((self.path.parent/'graphs'/row['graph_id']).resolve())
        except (OSError,ValueError):return False

    def bridge_count(self,graph_id):
        with self.lock:return self.connection.execute('SELECT count(*) FROM bridges WHERE source_graph=? OR target_graph=?',(graph_id,graph_id)).fetchone()[0]

    def copy_graph(self,graph_id,label):
        """Independent online copy of a graph's code store; paper corpora are not copied.

        The catalog lock is held only to validate and to publish; the (possibly
        very large) SQLite backup runs unlocked so hub queries are not stalled."""
        if not isinstance(label,str) or not label.strip() or len(label)>200:raise ValueError('label must be a non-empty string of at most 200 characters')
        label=label.strip()
        with self.lock:
            source=self.graph(graph_id);profile=json.loads(source['profile_json'])
            new_id='g_'+digest('copy-v1',graph_id,label,source['snapshot_id'])[:24]
            result=dict(graph_id=new_id,label=label,copied_from=graph_id,snapshot_id=source['snapshot_id'])
            if self.connection.execute('SELECT 1 FROM graphs WHERE graph_id=?',(new_id,)).fetchone():return result
            if new_id in self._copying:raise ValueError('GRAPH_BUSY: this copy is already in progress')
            self._copying.add(new_id)
            source_path=Path(source['code_database']).resolve();root_path=source['root_path'];snapshot_id=source['snapshot_id']
        try:
            database=(self.path.parent/'graphs'/new_id/'code.sqlite').resolve();database.parent.mkdir(parents=True,exist_ok=True)
            # Leftovers of an earlier failed delete/copy are never a valid base for the backup.
            for suffix in ('','-wal','-shm'):
                database.with_name(database.name+suffix).unlink(missing_ok=True)
            with closing(sqlite3.connect(source_path.as_uri()+'?mode=ro',uri=True)) as src:
                dst=sqlite3.connect(database)
                try:self._backup(src,dst)
                finally:dst.close()
            new_profile=dict(graph_kind='copy',copied_from=graph_id,owner_repo_ids=profile.get('owner_repo_ids',[graph_id]))
            if profile.get('stratum'):new_profile['stratum']=profile['stratum']
            with self.lock:
                # Lost race: the winner owns this directory (same id), so leave it alone.
                if self.connection.execute('SELECT 1 FROM graphs WHERE graph_id=?',(new_id,)).fetchone():return result
                with self.connection:
                    self.connection.execute('INSERT INTO graphs VALUES(?,?,?,?,?,NULL,?,?,?)',(new_id,'copy:'+new_id,root_path,label,str(database),
                        snapshot_id,canonical(new_profile),datetime.now(timezone.utc).isoformat()))
        except BaseException:
            # Only this call's own, unpublished directory may be removed.
            with self.lock:
                owned=not self.connection.execute('SELECT 1 FROM graphs WHERE graph_id=?',(new_id,)).fetchone()
                if owned:shutil.rmtree(database.parent,ignore_errors=True)
            raise
        finally:
            with self.lock:self._copying.discard(new_id)
        return result

    @staticmethod
    def _backup(src,dst):src.backup(dst)

    def _refuse_if_in_use(self,graph_id,protected):
        if graph_id in protected:raise ValueError('GRAPH_IN_USE: this is the hub primary graph')
        if self.connection.execute('SELECT 1 FROM merge_receipts WHERE graph_id=?',(graph_id,)).fetchone():
            raise ValueError('GRAPH_IN_USE: a merge receipt names this graph')
        for other in self.graphs():
            if other['graph_id']!=graph_id and any(s.get('graph_id')==graph_id for s in json.loads(other['profile_json']).get('source_graphs',[])):
                raise ValueError('GRAPH_IN_USE: it is a source of merged graph '+other['graph_id'])

    def delete_graph(self,graph_id,*,retire=None,protected=frozenset(),restore=None):
        """Remove a graph and its bridges; unlink only stores this catalog owns.

        `restore` (default: the owner's `unretire_graph` when `retire` is a bound
        router method) clears the router's deletion tombstone when we finish or fail."""
        if restore is None and retire is not None:restore=getattr(getattr(retire,'__self__',None),'unretire_graph',None)
        try:return self._delete_graph(graph_id,retire,protected)
        finally:
            if restore is not None:restore(graph_id)

    def _delete_graph(self,graph_id,retire,protected):
        with self.lock:
            row=self.graph(graph_id)
            self._refuse_if_in_use(graph_id,protected)  # Early: an obvious refusal retires nothing.
        if retire is not None:retire(graph_id)  # May raise GRAPH_BUSY before anything changes.
        with self.lock,self.connection:
            self.connection.execute('BEGIN IMMEDIATE')
            self._refuse_if_in_use(graph_id,protected)  # Re-checked: a merge may have landed during retire.
            removed=[r[0] for r in self.connection.execute('SELECT bridge_id FROM bridges WHERE source_graph=? OR target_graph=? ORDER BY bridge_id',(graph_id,graph_id))]
            self.connection.execute('DELETE FROM bridges WHERE source_graph=? OR target_graph=?',(graph_id,graph_id))
            for bid in removed:
                self.connection.execute('DELETE FROM artifact_justifications WHERE artifact_id=?',(bid,))
                self.connection.execute('DELETE FROM artifact_states WHERE artifact_id=?',(bid,))
            self.connection.execute('DELETE FROM overlap_decisions WHERE graph_a=? OR graph_b=?',(graph_id,graph_id))
            self.connection.execute('DELETE FROM graphs WHERE graph_id=?',(graph_id,))
        path=Path(row['code_database']);unlinked=[];kept=[]
        if not self.owns_store(row):
            kept.append(str(path.resolve()))
        else:
            path=path.resolve()
            if path.is_file():
                try:
                    with sqlite3.connect(path) as conn:conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                    conn.close()
                except sqlite3.Error:pass
            gc.collect()
            for target in (path,path.with_name(path.name+'-wal'),path.with_name(path.name+'-shm'),path.with_name(path.name+'.cursor-secret')):
                if not target.exists():continue
                for attempt in range(5):
                    try:target.unlink();unlinked.append(str(target));break
                    except FileNotFoundError:break
                    except PermissionError:
                        if attempt==4:kept.append(str(target))
                        else:time.sleep(0.05*2**attempt)
            try:path.parent.rmdir()
            except OSError:pass
        from .lineage import sweep
        swept=sweep(self,graph_id,row['snapshot_id'],None)
        return dict(deleted=graph_id,bridges_removed=removed,files_unlinked=unlinked,files_kept=kept,lineage=swept)

    def plan_root(self,root):
        path,key=self.root_identity(root)
        if not path.is_dir():raise ValueError('Project root must be an existing directory')
        collisions=[];existing=None
        for row in self.graphs():
            if row['root_key'].startswith(('merge:','store:','copy:')):continue
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
            prior=self.connection.execute('SELECT snapshot_id FROM graphs WHERE graph_id=?',(gid,)).fetchone()
            old_sid=prior[0] if prior else None
            now=datetime.now(timezone.utc).isoformat()
            self.connection.execute('INSERT INTO graphs VALUES(?,?,?,?,?,NULL,?,?,?) ON CONFLICT(graph_id) DO UPDATE SET label=excluded.label,snapshot_id=excluded.snapshot_id,profile_json=excluded.profile_json',
                (gid,os.path.normcase(plan['root_path']),plan['root_path'],label or Path(root).name,str(database),report['snapshot_id'],canonical(profile),now))
            for collision in undecided:
                a,b=sorted((gid,collision['graph_id']))
                self.connection.execute('INSERT INTO overlap_decisions VALUES(?,?,?,?)',(a,b,decision,now))
                if decision=='child_module':
                    parent,child=(collision['graph_id'],gid) if collision['relation']=='inside_existing_root' else (gid,collision['graph_id'])
                    self.add_bridge(parent,'root',child,'root','child_module','Operator declared a separate child module',[{'root_plan_id':plan['plan_id']}])
        result=dict(graph_id=gid,root_plan=plan,ingestion=report)
        if old_sid is not None and old_sid!=report['snapshot_id']:
            from .lineage import sweep
            # The snapshot is already published: a sweep failure must not report the import as failed.
            # States stay as they were (the sweep writes in one transaction); a later sweep re-evaluates.
            try:result['lineage']=sweep(self,gid,old_sid,report['snapshot_id'])
            except (ValueError,OSError,sqlite3.Error) as exc:result['lineage']=dict(error=f'LINEAGE_SWEEP_FAILED: {str(exc)[:300]}')
        return result

    def derive_graph(self,source_graph_id,*,exclude_rel_paths,label):
        """Prune by derivation (master G8): re-ingest the source root into a NEW graph with extra excludes.

        The source graph, its snapshots and its profile are unchanged. The derived graph skips root
        overlap review because it is explicitly derived (its profile says so); its id is deterministic,
        so deriving the same exclusion again refreshes it instead of duplicating it.
        """
        import re as _re
        if not isinstance(exclude_rel_paths,list) or not 1<=len(exclude_rel_paths)<=500:raise ValueError('exclude_rel_paths must list 1..500 relative paths')
        clean=set()
        for raw in exclude_rel_paths:
            if not isinstance(raw,str):raise ValueError('exclude_rel_paths must be strings')
            rel=raw.replace('\\','/').strip().rstrip('/')  # a leading '/' stays: absolute paths are refused below
            if not rel or len(rel)>400 or rel.startswith(('/','~')) or _re.match(r'^[A-Za-z]:',rel) or any(part in ('','.','..') for part in rel.split('/')):
                raise ValueError(f'Invalid relative path {raw[:80]!r}')
            clean.add(rel)
        if not isinstance(label,str) or not label.strip() or len(label)>120:raise ValueError('A label of 1..120 characters is required')
        source=self.graph(source_graph_id);profile=json.loads(source['profile_json'])
        if profile.get('graph_kind') in ('registered_store','copy') or profile.get('existing_store'):
            raise ValueError('Only graphs ingested from a project root can be pruned by derivation')
        root=Path(source['root_path'])
        if not root.is_dir():raise ValueError('Source root is not available for re-ingestion')
        new_id='g_'+digest('derived-v1',source_graph_id,sorted(clean))[:24]
        globs=sorted({g for rel in clean for g in (rel,rel+'/*')})
        excludes=sorted(set(profile.get('exclude_globs',[]))|set(globs))
        repository=Repository.from_directory(root,new_id,source_roots=tuple(profile.get('source_roots',[''])) or ('',),
            include_globs=tuple(profile.get('include_globs',['*'])) or ('*',),exclude_globs=tuple(excludes))
        repository.repo_id=new_id;repository.resolution_group=None
        database=self.path.parent/'graphs'/new_id/'code.sqlite';database.parent.mkdir(parents=True,exist_ok=True)
        with self.import_lock,SnapshotStore(database) as store:
            # Identical bytes: reuse the existing complete snapshot, as import_project does.
            row=store.connection.execute("SELECT s.snapshot_id FROM snapshots s JOIN snapshot_sets ss ON ss.snapshot_id=s.snapshot_id "
                "WHERE s.repo_id=? AND s.digest=? AND ss.status='complete' ORDER BY ss.created_at DESC LIMIT 1",(new_id,repository.content_digest)).fetchone()
            report=dict(snapshot_id=row[0],status='reused') if row else ingest(store,[repository],stage=3)
        derived=dict(graph_kind='derived',derived_from=source_graph_id,source_roots=list(repository.source_roots),
            include_globs=list(repository.include_globs),exclude_globs=excludes,owner_repo_ids=[new_id])
        if 'stratum' in profile:derived['stratum']=profile['stratum']
        now=datetime.now(timezone.utc).isoformat()
        with self.lock,self.connection:
            self.connection.execute('BEGIN IMMEDIATE')
            self.connection.execute('INSERT INTO graphs VALUES(?,?,?,?,?,NULL,?,?,?) ON CONFLICT(graph_id) DO UPDATE SET label=excluded.label,snapshot_id=excluded.snapshot_id,profile_json=excluded.profile_json',
                (new_id,'derived:'+new_id,str(root),label.strip(),str(database),report['snapshot_id'],canonical(derived),now))
        return dict(graph_id=new_id,derived_from=source_graph_id,exclude_globs=globs,ingestion=report)

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

    def set_stratum(self,graph_id,role,trust_tier,modality):
        """Record a graph's federation stratum under profile_json['stratum']."""
        from .federation import TIER_WEIGHT,MODALITIES
        if not isinstance(role,str) or not role.strip() or len(role)>64:raise ValueError('role must be a non-empty string of at most 64 characters')
        if trust_tier not in TIER_WEIGHT:raise ValueError(f'trust_tier must be one of {sorted(TIER_WEIGHT)}')
        if modality not in MODALITIES:raise ValueError(f'modality must be one of {sorted(MODALITIES)}')
        with self.lock,self.connection:
            self.connection.execute('BEGIN IMMEDIATE')
            row=self.connection.execute('SELECT profile_json FROM graphs WHERE graph_id=?',(graph_id,)).fetchone()
            if row is None:raise ValueError('Unknown graph_id')
            profile=json.loads(row[0]);profile['stratum']=dict(role=role,trust_tier=trust_tier,modality=modality)
            self.connection.execute('UPDATE graphs SET profile_json=? WHERE graph_id=?',(canonical(profile),graph_id))

    def add_bridge(self,source_graph,source_ref,target_graph,target_ref,kind,rationale,evidence,*,owner_decision=False):
        from .provenance import bridge_boundary
        if bridge_boundary(self,source_graph,target_graph):
            if kind != 'reference':raise ValueError('THIRD_PARTY_BRIDGE: only reference bridges may cross this boundary')
            if not owner_decision and not any(isinstance(e,dict) and e.get('owner_decision') is True for e in evidence or []):
                raise ValueError('OWNER_DECISION_REQUIRED: third-party reference bridge')
        if source_graph==target_graph:raise ValueError('Bridge endpoints must be different graphs')
        if kind not in {'child_module','reference','concept_equivalence','document_identity'}:raise ValueError('Unknown bridge kind')
        if not isinstance(rationale,str) or not rationale.strip() or len(rationale)>2000:raise ValueError('Bounded rationale required')
        if not isinstance(evidence,list) or not evidence or len(canonical(evidence))>8000:raise ValueError('Bounded provenance evidence required')
        if any(not isinstance(r,str) or not r or len(r)>300 for r in (source_ref,target_ref)):raise ValueError('Bounded endpoint references required')
        from .bridges import parse_ref,resolve_ref
        parse_ref(source_ref);parse_ref(target_ref)  # BRIDGE_REF_INVALID before any lookup (master G4)
        with self.lock:
            self.graph(source_graph);self.graph(target_graph)
            bindings=[('source',resolve_ref(self,source_graph,source_ref)),('target',resolve_ref(self,target_graph,target_ref))]
            bid='b_'+digest(source_graph,source_ref,target_graph,target_ref,kind,rationale,evidence)[:24]
            owned=not self.connection.in_transaction
            try:
                self.connection.execute('INSERT OR IGNORE INTO bridges VALUES(?,?,?,?,?,?,?,?,?)',
                    (bid,source_graph,source_ref,target_graph,target_ref,kind,rationale,canonical(evidence),datetime.now(timezone.utc).isoformat()))
                for side,b in bindings:
                    self.connection.execute('INSERT OR IGNORE INTO bridge_bindings VALUES(?,?,?,?,?,?,?)',
                        (bid,side,b['graph_id'],b['ref'],b['snapshot_id'],b['paper_read_model'],b['fingerprint_json']))
                from .lineage import bridge_clause,register
                register(self,bid,'bridge',[bridge_clause(bindings)])
                if owned:self.connection.commit()
            except BaseException:
                if owned:self.connection.rollback()
                raise
            return bid

    def _bind_legacy_bridges(self):
        """Bridges created before bindings existed: bind both sides to the graph's current snapshot, empty fingerprint."""
        rows=self.connection.execute("SELECT b.bridge_id,b.source_graph,b.source_ref,b.target_graph,b.target_ref FROM bridges b "
            "WHERE NOT EXISTS(SELECT 1 FROM bridge_bindings x WHERE x.bridge_id=b.bridge_id)").fetchall()
        if not rows:return
        with self.connection:
            for r in rows:
                for side,gid,ref in (('source',r['source_graph'],r['source_ref']),('target',r['target_graph'],r['target_ref'])):
                    g=self.connection.execute('SELECT snapshot_id FROM graphs WHERE graph_id=?',(gid,)).fetchone()
                    self.connection.execute('INSERT OR IGNORE INTO bridge_bindings VALUES(?,?,?,?,?,NULL,?)',(r['bridge_id'],side,gid,ref,g[0] if g else None,'{}'))

    def bindings(self,bridge_id):
        with self.lock:
            return {r['side']:dict(r) for r in self.connection.execute('SELECT * FROM bridge_bindings WHERE bridge_id=? ORDER BY side',(bridge_id,))}

    def propose_bridges(self,graph_a,graph_b,*,kind,limit=50):
        """Score reviewed-candidate bridges between two graphs; stores pending proposals, never creates a bridge."""
        from .bridges import alias_policy,code_candidates,paper_candidates,score_pairs
        if graph_a==graph_b:raise ValueError('Bridge endpoints must be different graphs')
        if kind not in {'reference','concept_equivalence','document_identity'}:raise ValueError('Unknown bridge kind')
        from .provenance import bridge_boundary
        if kind != 'reference' and bridge_boundary(self,graph_a,graph_b):return []
        if not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=500:raise ValueError('limit must be 1..500')
        policy=alias_policy();sides=[]
        for gid in (graph_a,graph_b):
            row=self.graph(gid)
            sides.append(paper_candidates(row['paper_database'],policy) if row['paper_database'] else
                         code_candidates(row['code_database'],row['snapshot_id'],policy) if row['snapshot_id'] else [])
        pairs=score_pairs(sides[0],sides[1],limit);out=[]
        with self.lock,self.connection:
            for p in pairs:
                pid='p_'+digest(graph_a,p['source_ref'],graph_b,p['target_ref'],kind)[:24]
                self.connection.execute('INSERT OR IGNORE INTO bridge_proposals VALUES(?,?,?,?,?,?,?,?,?,NULL,NULL)',
                    (pid,graph_a,p['source_ref'],graph_b,p['target_ref'],kind,p['score'],canonical(p['features']),'pending'))
                out.append(self.proposal(pid))
        return out

    def proposal(self,proposal_id):
        row=self.connection.execute('SELECT * FROM bridge_proposals WHERE proposal_id=?',(proposal_id,)).fetchone()
        if row is None:raise ValueError('Unknown proposal_id')
        return {**dict(row),'features':json.loads(row['features_json'])}

    def proposals(self,graph_ids,status='pending'):
        if not isinstance(graph_ids,list) or not 1<=len(graph_ids)<=19 or len(set(graph_ids))!=len(graph_ids):raise ValueError('Choose 1..19 distinct graph IDs')
        if status not in {'pending','accepted','rejected'}:raise ValueError('Unknown proposal status')
        slots=','.join('?' for _ in graph_ids)
        with self.lock:
            rows=self.connection.execute('SELECT proposal_id FROM bridge_proposals WHERE status=? AND source_graph IN ('+slots+') AND target_graph IN ('+slots+') ORDER BY score DESC,proposal_id',(status,*graph_ids,*graph_ids)).fetchall()
            return [self.proposal(r[0]) for r in rows]

    def review_proposal(self,proposal_id,decision,rationale):
        """An explicit operator decision; only 'accept' creates a bridge (with the proposal as evidence)."""
        if decision not in {'accept','reject'}:raise ValueError("decision must be 'accept' or 'reject'")
        if not isinstance(rationale,str) or not rationale.strip() or len(rationale)>2000:raise ValueError('Bounded rationale required')
        with self.lock,self.connection:
            self.connection.execute('BEGIN IMMEDIATE')
            p=self.proposal(proposal_id)
            if p['status']!='pending':raise ValueError('PROPOSAL_ALREADY_DECIDED')
            bid=None
            if decision=='accept':
                bid=self.add_bridge(p['source_graph'],p['source_ref'],p['target_graph'],p['target_ref'],p['kind'],rationale,
                                    [{'proposal_id':proposal_id,'features':p['features'],'score':p['score']}], owner_decision=True)
            self.connection.execute('UPDATE bridge_proposals SET status=?,decided_at=?,decision_rationale=? WHERE proposal_id=?',
                ('accepted' if decision=='accept' else 'rejected',datetime.now(timezone.utc).isoformat(),rationale,proposal_id))
        return {**self.proposal(proposal_id),'bridge_id':bid}

    def bridge_state(self,bridge_id):
        """Lineage state of a bridge (Task 5's artifact_states); 'accepted' until evaluated."""
        with self.lock:
            if not self.connection.execute('SELECT 1 FROM bridges WHERE bridge_id=?',(bridge_id,)).fetchone():raise ValueError('Unknown bridge_id')
            row=self.connection.execute("SELECT state FROM artifact_states WHERE artifact_kind='bridge' AND artifact_id=?",(bridge_id,)).fetchone()
            return row[0] if row else 'accepted'

    def bridges(self,graph_ids):
        if not isinstance(graph_ids,list) or not 1<=len(graph_ids)<=19 or len(set(graph_ids))!=len(graph_ids):raise ValueError('Choose 1..19 distinct graph IDs')
        for gid in graph_ids:self.graph(gid)
        slots=','.join('?' for _ in graph_ids)
        with self.lock:
            return [dict(r) for r in self.connection.execute('SELECT * FROM bridges WHERE source_graph IN ('+slots+') AND target_graph IN ('+slots+') ORDER BY bridge_id',(*graph_ids,*graph_ids))]
