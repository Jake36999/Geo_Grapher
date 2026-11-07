"""Reviewed, non-destructive physical unions of immutable project snapshots."""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .model import canonical, digest
from .store import SnapshotStore


def _paper_identity(path):
    if not path:return None
    from pipeline.corpus_merge import source_identity
    return source_identity(Path(path))


def plan_merge(catalog, graph_ids, label):
    if not isinstance(graph_ids,list) or not 2<=len(graph_ids)<=8 or len(set(graph_ids))!=len(graph_ids):
        raise ValueError('Select 2..8 distinct source graphs')
    if not isinstance(label,str) or not label.strip() or len(label)>120:raise ValueError('A destination label of 1..120 characters is required')
    sources=[];owners=set()
    for gid in sorted(graph_ids):
        row=catalog.graph(gid)
        path=Path(row['code_database']).resolve()
        if not path.is_file():raise ValueError('Source graph store missing')
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as conn:
            if not conn.execute("SELECT 1 FROM snapshot_sets WHERE snapshot_id=? AND status='complete'",(row['snapshot_id'],)).fetchone():raise ValueError('Source head is not published')
            repos=sorted(r[0] for r in conn.execute("SELECT repo_id FROM snapshots WHERE snapshot_id=? AND repo_id<>'@workspace'",(row['snapshot_id'],)))
        expected=json.loads(row['profile_json']).get('owner_repo_ids',[gid])
        if set(repos)!=set(expected):raise ValueError('Source namespace ownership mismatch')
        if owners.intersection(repos):raise ValueError('Source graphs contain overlapping repository namespaces; choose disjoint sources')
        owners.update(repos)
        sources.append(dict(graph_id=gid,label=row['label'],snapshot_id=row['snapshot_id'],repo_ids=repos,
            code_database=str(path),paper_database=row['paper_database'],paper_identity=_paper_identity(row['paper_database'])))
    gid='g_'+digest('derived-merge-v1',sorted(graph_ids),label.strip())[:24]
    try:occupied=catalog.graph(gid)
    except ValueError:occupied=None
    if occupied:
        profile=json.loads(occupied['profile_json'])
        if occupied['root_key']!='merge:'+gid or occupied['label']!=label.strip() or sorted(s['graph_id'] for s in profile.get('source_graphs',[]))!=sorted(graph_ids):
            raise ValueError('Destination graph identity collision; existing stores were not modified')
    facts=dict(version='graph-merge-v1',destination_graph_id=gid,label=label.strip(),sources=sources,
        owner_repo_ids=sorted(owners),policy='namespace_preserving_union_no_new_inferred_edges',
        source_disposition='preserved',derived_analyses='recomputed_stage_3',
        paper_policy='origin_scoped_documents_and_concepts_no_cross_origin_equivalence')
    return dict(**facts,plan_id=digest(facts),warnings=[
        'This creates a new graph. Original graphs, snapshots and paper corpora are retained.',
        'Existing entity namespaces are preserved. Imports are not re-resolved across projects.',
        'Document/concept identities remain distinct across source origins; no synonym merge is implied.'])


def execute_merge(catalog, graph_ids, label, expected_plan):
    # Metadata registration is the only publication point. Files left by an
    # interrupted build remain unpublished and can be inspected/retried.
    # Long extraction/analysis holds only the merge lock: ordinary graph queries
    # can continue. Source heads are checked again in the publication transaction.
    with catalog.merge_lock:
        plan=plan_merge(catalog,graph_ids,label)
        if not isinstance(expected_plan,str) or expected_plan!=plan['plan_id']:raise ValueError('Merge plan changed or was not reviewed; generate a fresh plan')
        with catalog.lock:
            receipt=catalog.connection.execute('SELECT receipt_json FROM merge_receipts WHERE plan_id=?',(expected_plan,)).fetchone()
        if receipt:return json.loads(receipt[0])
        gid=plan['destination_graph_id'];directory=catalog.path.parent/'graphs'/gid
        directory.mkdir(parents=True,exist_ok=True)
        # One immutable paper generation per plan; historical generations remain.
        papers=[s for s in plan['sources'] if s['paper_database']]
        paper_path=directory/('papers-'+expected_plan+'.sqlite') if papers else None
        if papers:
            from pipeline.corpus_merge import merge_corpora
            merge_corpora(papers,paper_path)
        # Each generation has its own file. A failed/stale build cannot add a
        # published snapshot to an already registered destination's live store.
        database=directory/('code-'+expected_plan+'.sqlite')
        with ExitStack() as stack:
            sources=[(stack.enter_context(SnapshotStore(s['code_database'])),s['snapshot_id']) for s in plan['sources']]
            target=stack.enter_context(SnapshotStore(database))
            sid=target.merge(sources,stage=3)
            if target.validate(sid):raise ValueError('Merged snapshot validation failed')
            counts={t:target.connection.execute('SELECT count(*) FROM '+t+' WHERE snapshot_id=?',(sid,)).fetchone()[0] for t in ('entities','relationships','evidence','documentary_incidences')}
        # Detect a paper edit during copying; never publish a mixed generation.
        now=datetime.now(timezone.utc).isoformat()
        profile=dict(graph_kind='merged',owner_repo_ids=plan['owner_repo_ids'],source_graphs=plan['sources'],merge_plan_id=expected_plan)
        receipt=dict(plan_id=expected_plan,graph_id=gid,snapshot_id=sid,counts=counts,source_graph_ids=sorted(graph_ids),sources_preserved=True,papers_merged=bool(papers),created_at=now)
        with catalog.lock,catalog.connection:
            catalog.connection.execute('BEGIN IMMEDIATE')
            if plan_merge(catalog,graph_ids,label)['plan_id']!=expected_plan:raise ValueError('Source changed while merging; destination remains unpublished')
            previous=catalog.connection.execute('SELECT receipt_json FROM merge_receipts WHERE plan_id=?',(expected_plan,)).fetchone()
            if previous:return json.loads(previous[0])
            catalog.connection.execute('INSERT INTO graphs VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(graph_id) DO UPDATE SET code_database=excluded.code_database,snapshot_id=excluded.snapshot_id,paper_database=excluded.paper_database,profile_json=excluded.profile_json',
                (gid,'merge:'+gid,'Merged: '+', '.join(s['label'] for s in plan['sources']),label.strip(),str(database),str(paper_path) if paper_path else None,sid,canonical(profile),now))
            catalog.connection.execute('INSERT INTO merge_receipts VALUES(?,?,?,?)',(expected_plan,gid,canonical(plan),canonical(receipt)))
        return receipt
