"""Local CLI. Repository source is never imported as part of ingestion."""
import argparse
import json
import os
import sys
from pathlib import Path

from .pipeline import ingest
from .source import Repository
from .store import SnapshotStore


PINNED_MCP_MAJOR=1


def require_pinned_mcp():
    """Fail fast with a fix instead of an ImportError deep in server start-up."""
    from importlib.metadata import PackageNotFoundError,version
    try:found=version('mcp')
    except PackageNotFoundError:found=None
    if found is None or int(found.split('.')[0])!=PINNED_MCP_MAJOR:
        raise SystemExit(f'Geo Grapher servers require mcp {PINNED_MCP_MAJOR}.x (pyproject pins 1.30.0); this interpreter has '
            f'{"no mcp package" if found is None else "mcp "+found}. Start them with output/wheel-env/Scripts/python.exe '
            'or scripts/start-servers.ps1.')


def main():
    parser = argparse.ArgumentParser(prog="geographer")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("ingest")
    command.add_argument("--repo", type=Path, required=True)
    command.add_argument("--repo-id", required=True)
    command.add_argument("--revision", help="Immutable Git commit; omit for a digested directory snapshot")
    command.add_argument("--source-root", action="append", default=[])
    command.add_argument("--database", type=Path, required=True)
    command.add_argument("--report", type=Path)
    command.add_argument("--stage", type=int, choices=[1,2,3], default=1)
    command.add_argument('--previous-snapshot',help='Reuse verified normal forms from this snapshot; re-resolve all cross-file bindings')
    cache=sub.add_parser("cache-tokenizers")
    cache.add_argument("--directory",type=Path)
    server=sub.add_parser("serve")
    server.add_argument('--database',type=Path,required=True)
    server.add_argument('--transport',choices=['stdio','http'],default='stdio')
    server.add_argument('--rules',type=Path,action='append',default=[])
    server.add_argument('--catalog',type=Path,help='Show the shared graph workspace at / while preserving this database API/MCP')
    server.add_argument('--host',default='127.0.0.1')
    server.add_argument('--port',type=int,default=8765)
    server.add_argument('--schema-version',choices=['1.0','1.1'],default='1.0',help='MCP stdio wire version; HTTP exposes both versions')
    tracing=sub.add_parser('ingest-trace',help='Import source-matched JSONL observations as an immutable child snapshot')
    tracing.add_argument('--database',type=Path,required=True)
    tracing.add_argument('--snapshot-id',required=True)
    tracing.add_argument('--trace',type=Path,required=True)
    tracing.add_argument('--manifest',type=Path)
    tracing.add_argument('--environment')
    tracing.add_argument('--start');tracing.add_argument('--end')
    tracing.add_argument('--report',type=Path)
    recorder=sub.add_parser('record-trace',help='Explicitly execute a Python command under bounded call recording')
    recorder.add_argument('--database',type=Path,required=True);recorder.add_argument('--snapshot-id',required=True)
    recorder.add_argument('--repo-root',action='append',required=True,help='Repository namespace and local root: ID=PATH')
    recorder.add_argument('--environment',required=True);recorder.add_argument('--output',type=Path,required=True)
    recorder.add_argument('--max-seconds',type=float,default=60);recorder.add_argument('--max-events',type=int,default=100000)
    recorder.add_argument('--max-bytes',type=int,default=64*1024*1024);recorder.add_argument('execution',nargs=argparse.REMAINDER)
    inspection=sub.add_parser('inspect-project',help='Bounded metadata-only format and size inventory; no extraction or execution')
    inspection.add_argument('--repo',type=Path,required=True);inspection.add_argument('--max-entries',type=int,default=20000);inspection.add_argument('--report',type=Path)
    workspace=sub.add_parser('ingest-workspace',help='Ingest explicit, nonoverlapping project roots; isolated unless resolution_group is declared')
    workspace.add_argument('--manifest',type=Path,required=True);workspace.add_argument('--database',type=Path,required=True)
    workspace.add_argument('--stage',type=int,choices=[1,2,3],default=1);workspace.add_argument('--report',type=Path)
    discovery=sub.add_parser('discovery-report',help='Deterministic discovery card (discovery-card-v1) as Markdown, optionally JSON')
    discovery.add_argument('--store',type=Path,required=True);discovery.add_argument('--snapshot');discovery.add_argument('--out',required=True,help='Markdown file, or - for stdout');discovery.add_argument('--json',type=Path)
    init=sub.add_parser('init-workspace',help='Plan disjoint graph partitions for any folder (workspace-init-v1); applies only with --apply or --yes')
    init.add_argument('--root',type=Path,required=True);init.add_argument('--catalog',type=Path,required=True)
    init.add_argument('--plan-out',default='-',help='Plan JSON file, or - for stdout');init.add_argument('--apply',type=Path,help='Apply every partition of this saved plan')
    init.add_argument('--yes',action='store_true',help='Scan and apply every proposed partition')
    diffg=sub.add_parser('diff-graphs',help='Fingerprint diff and quotient-cycle delta between two catalog graphs, as JSON')
    diffg.add_argument('--catalog',type=Path,required=True);diffg.add_argument('--graph-a',required=True);diffg.add_argument('--graph-b',required=True)
    diffg.add_argument('--out',type=Path,required=True)
    clones=sub.add_parser('clone-report',help='Cross-graph structural clones (py-ast-v1, signature+guard), as JSON')
    clones.add_argument('--catalog',type=Path,required=True);clones.add_argument('--graph-ids',required=True,help='Comma-separated, 2..8 graphs')
    clones.add_argument('--limit',type=int,default=200);clones.add_argument('--out',type=Path,required=True)
    drift=sub.add_parser('drift-report',help='Five-tier drift between two snapshots (master G3), as JSON')
    for side in ('a','b'):drift.add_argument(f'--store-{side}',type=Path,required=True);drift.add_argument(f'--snapshot-{side}',required=True)
    drift.add_argument('--out',type=Path,required=True)
    graphs=sub.add_parser('ingest-graphs',help='One independent database/graph per project profile')
    graphs.add_argument('--manifest',type=Path,required=True);graphs.add_argument('--catalog',type=Path,required=True)
    graphs.add_argument('--on-overlap',choices=['keep_separate','child_module']);graphs.add_argument('--report',type=Path)
    graphserver=sub.add_parser('serve-graphs',help='Graph-scoped MCP and display-only multi-graph UI')
    # Environment defaults let an MCP host (e.g. Librarian's curated list, whose
    # args cannot reference variables) configure a pinned launch per person.
    env_catalog=os.environ.get('GEOGRAPHER_CATALOG')
    graphserver.add_argument('--catalog',type=Path,default=Path(env_catalog) if env_catalog else None,required=not env_catalog,
        help='Graph catalog (default: $GEOGRAPHER_CATALOG)');graphserver.add_argument('--transport',choices=['stdio','http'],default='http');graphserver.add_argument('--port',type=int,default=8765)
    graphserver.add_argument('--ui-origin',help='Compatibility listener: redirect its viewer to this loopback origin')
    env_graphs=[g.strip() for g in os.environ.get('GEOGRAPHER_GRAPHS','').split(',') if g.strip()]
    graphserver.add_argument('--graph-id',action='append',dest='allow_graph',metavar='GRAPH_ID',default=None,
        help='Expose only this graph (repeatable; default: comma-separated $GEOGRAPHER_GRAPHS). '
             'Turns per-call scoping into an access boundary for this connection')
    graphserver.add_argument('--tools',default=os.environ.get('GEOGRAPHER_TOOLS') or None,
        help="Tool surface: 'all' (default), 'papers', 'code', or comma-separated tool names "
             "(default: $GEOGRAPHER_TOOLS). For hosts that offer an agent only a few tools per turn")
    env_cap=os.environ.get('GEOGRAPHER_MAX_RESULT_CHARS','').strip()
    graphserver.add_argument('--max-result-chars',type=int,default=int(env_cap) if env_cap.isdigit() else None,
        help="Fit paper results to a client's size cap (e.g. 7500 for Librarian) by paging whole items, never cutting JSON "
             "(default: $GEOGRAPHER_MAX_RESULT_CHARS)")
    plan=sub.add_parser('plan-graph',help='Read-only root collision review before graph import')
    plan.add_argument('--catalog',type=Path,required=True);plan.add_argument('--root',type=Path,required=True)
    papers=sub.add_parser('attach-graph-papers',help='Bind an existing independent paper corpus to one graph')
    papers.add_argument('--catalog',type=Path,required=True);papers.add_argument('--graph-id',required=True);papers.add_argument('--database',type=Path,required=True)
    stratum=sub.add_parser('set-graph-stratum',help='Record a graph trust tier and modality for federated search')
    stratum.add_argument('--catalog',type=Path,required=True);stratum.add_argument('--graph-id',required=True);stratum.add_argument('--role',required=True)
    from .federation import TIER_WEIGHT,MODALITIES
    stratum.add_argument('--trust-tier',required=True,choices=sorted(TIER_WEIGHT));stratum.add_argument('--modality',required=True,choices=sorted(MODALITIES))
    copying=sub.add_parser('copy-graph',help='Independent online copy of a graph code store under a new label')
    copying.add_argument('--catalog',type=Path,required=True);copying.add_argument('--graph-id',required=True);copying.add_argument('--label',required=True)
    deleting=sub.add_parser('delete-graph',help='Delete a graph and its bridges; only catalog-owned stores are unlinked')
    deleting.add_argument('--catalog',type=Path,required=True);deleting.add_argument('--graph-id',required=True);deleting.add_argument('--confirm-label',required=True)
    for name in ('plan-graph-merge','merge-graphs'):
        merging=sub.add_parser(name,help='Reviewed namespace-preserving physical merge into a new graph')
        merging.add_argument('--catalog',type=Path,required=True);merging.add_argument('--graph-id',action='append',required=True)
        merging.add_argument('--label',required=True);merging.add_argument('--report',type=Path)
        if name=='merge-graphs':merging.add_argument('--plan-id',required=True)
    args = parser.parse_args()
    if args.command in {'serve','serve-graphs'}:require_pinned_mcp()
    if args.command in {'ingest-graphs','serve-graphs','plan-graph','attach-graph-papers','set-graph-stratum','copy-graph','delete-graph','plan-graph-merge','merge-graphs'}:
        from .graph_catalog import GraphCatalog,CollisionReview
        if args.command!='ingest-graphs' and not args.catalog.is_file():raise ValueError('Graph catalog not found; no empty catalog was created')
        catalog=GraphCatalog(args.catalog)
        try:
            if args.command=='ingest-graphs':
                from .project_inputs import load_workspace_manifest
                raw_profile=json.loads(args.manifest.read_text(encoding='utf-8-sig'))
                entries=raw_profile['repositories']
                # Root review precedes content traversal, extraction and writes.
                for entry in entries:
                    root=Path(entry['path'])
                    if not root.is_absolute():root=args.manifest.resolve().parent/root
                    plan=catalog.plan_root(root)
                    if plan['requires_review'] and not args.on_overlap:raise CollisionReview(plan)
                repositories=load_workspace_manifest(args.manifest)
                reports=[]
                for repo,entry in zip(repositories,entries):
                    if repo.resolution_group:raise ValueError('Independent graphs do not share resolution_group; declare bridges instead')
                    root=Path(entry['path'])
                    if not root.is_absolute():root=args.manifest.resolve().parent/root
                    reports.append(catalog.import_project(root,repo,label=entry['repo_id'],decision=args.on_overlap))
                result=dict(graphs=reports,storage='independent_per_project',composition='display_only')
            elif args.command=='plan-graph':result=catalog.plan_root(args.root)
            elif args.command=='plan-graph-merge':
                from .graph_merge import plan_merge
                result=plan_merge(catalog,args.graph_id,args.label)
            elif args.command=='merge-graphs':
                from .graph_merge import execute_merge
                result=execute_merge(catalog,args.graph_id,args.label,args.plan_id)
            elif args.command=='copy-graph':result=catalog.copy_graph(args.graph_id,args.label)
            elif args.command=='delete-graph':
                if catalog.graph(args.graph_id)['label']!=args.confirm_label:raise ValueError('--confirm-label does not match the graph label')
                result=catalog.delete_graph(args.graph_id)
            elif args.command=='set-graph-stratum':
                catalog.set_stratum(args.graph_id,args.role,args.trust_tier,args.modality)
                result=dict(graph_id=args.graph_id,stratum=json.loads(catalog.graph(args.graph_id)['profile_json'])['stratum'])
            elif args.command=='attach-graph-papers':catalog.attach_papers(args.graph_id,args.database);result=dict(graph_id=args.graph_id,papers_attached=True)
            else:
                from .graph_router import GraphRouter
                from .graph_server import create_graph_http,create_graph_mcp
                router=GraphRouter(catalog,allowed=args.allow_graph or env_graphs or None,max_result_chars=args.max_result_chars,tools=args.tools)
                try:
                    if args.transport=='stdio':create_graph_mcp(router,port=args.port).run(transport='stdio')
                    else:
                        import uvicorn
                        uvicorn.run(create_graph_http(router,port=args.port,ui_origin=args.ui_origin),host='127.0.0.1',port=args.port)
                finally:router.close()
                return
            output=json.dumps(result,indent=2)
            if getattr(args,'report',None):args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(output+'\n',encoding='utf-8')
            print(output);return
        except CollisionReview as exc:
            print(json.dumps(dict(error='COLLISION_REVIEW_REQUIRED',plan=exc.plan,completed_graphs=locals().get('reports',[])),indent=2));raise SystemExit(2)
        finally:catalog.close()
    if args.command in {'inspect-project','ingest-workspace'}:
        from .project_inputs import inspect_project,load_workspace_manifest
        if args.command=='inspect-project':report=inspect_project(args.repo,max_entries=args.max_entries)
        else:
            repositories=load_workspace_manifest(args.manifest)
            args.database.parent.mkdir(parents=True,exist_ok=True)
            with SnapshotStore(args.database) as store:report=ingest(store,repositories,stage=args.stage)
            report['selection']=[dict(repo_id=r.repo_id,source_roots=list(r.source_roots),include_globs=list(r.include_globs),exclude_globs=list(r.exclude_globs),selected_files=len(r.files),resolution_group=r.resolution_group) for r in repositories]
            report['coverage']='explicit_profile_only_not_complete_project_inventory'
        output=json.dumps(report,indent=2,ensure_ascii=False)
        if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(output+'\n',encoding='utf-8')
        print(output);return
    if args.command=='init-workspace':
        from .graph_catalog import GraphCatalog
        from .model import canonical
        from .workspace_init import apply,scan
        if args.apply or args.yes:
            catalog=GraphCatalog(args.catalog)
            try:
                plan=json.loads(args.apply.read_text(encoding='utf-8')) if args.apply else scan(args.root,catalog)
                print(canonical(apply(catalog,plan,approved_keys={p['key'] for p in plan['partitions']})))
            finally:catalog.close()
            return
        plan=scan(args.root)
        if args.plan_out=='-':sys.stdout.buffer.write((canonical(plan)+'\n').encode('utf-8'))
        else:Path(args.plan_out).parent.mkdir(parents=True,exist_ok=True);Path(args.plan_out).write_text(canonical(plan)+'\n',encoding='utf-8')
        return
    if args.command in ('diff-graphs','clone-report'):
        from .cross_graph import clone_pairs,diff_graphs
        from .graph_catalog import GraphCatalog
        from .model import canonical
        if not args.catalog.is_file():raise SystemExit(f'Catalog not found: {args.catalog}')
        catalog=GraphCatalog(args.catalog)
        try:
            result=(diff_graphs(catalog,args.graph_a,args.graph_b) if args.command=='diff-graphs' else
                    clone_pairs(catalog,[g.strip() for g in args.graph_ids.split(',') if g.strip()],limit=args.limit))
        finally:catalog.close()
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(canonical(result)+'\n',encoding='utf-8');return
    if args.command=='drift-report':
        from .drift import drift_report
        from .model import canonical
        from .store import SnapshotStore
        for path in (args.store_a,args.store_b):
            if not path.is_file():raise SystemExit(f'Store not found: {path}')
        with SnapshotStore(args.store_a) as a,SnapshotStore(args.store_b) as b:
            report=drift_report(a,args.snapshot_a,b,args.snapshot_b)
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(canonical(report)+'\n',encoding='utf-8');return
    if args.command=='discovery-report':
        from .discovery import build_card,render_markdown
        from .model import canonical
        from .store import SnapshotStore
        if not args.store.is_file():raise ValueError('Store not found; no empty store was created')
        store=SnapshotStore(args.store)
        try:
            sid=args.snapshot or (store.connection.execute("SELECT snapshot_id FROM snapshot_sets WHERE status='complete' ORDER BY created_at DESC,snapshot_id DESC LIMIT 1").fetchone() or [None])[0]
            if sid is None:raise ValueError('No complete snapshot in store')
            card=build_card(store,sid);text=render_markdown(card)
        finally:store.close()
        if args.json:args.json.parent.mkdir(parents=True,exist_ok=True);args.json.write_text(canonical(card)+chr(10),encoding='utf-8',newline=chr(10))
        if args.out=='-':sys.stdout.buffer.write(text.encode('utf-8'));sys.stdout.buffer.flush()
        else:
            out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(text.encode('utf-8'))
        return
    if args.command=="cache-tokenizers":
        from .tokens import cache_weights
        print(json.dumps(cache_weights(args.directory),indent=2));return
    if args.command=='serve':
        from .server import serve
        serve(args.database,args.transport,args.rules,args.host,args.port,args.schema_version,catalog_path=args.catalog);return
    if args.command=='ingest-trace':
        from .trace import read_artifacts,ingest_trace
        raw,manifest=read_artifacts(args.trace,args.manifest)
        with SnapshotStore(args.database) as store:report=ingest_trace(store,args.snapshot_id,raw,manifest,environment=args.environment,start=args.start,end=args.end)
        output=json.dumps(report,indent=2,ensure_ascii=False)
        if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(output+'\n',encoding='utf-8')
        print(output);return
    if args.command=='record-trace':
        from .recording import record_command
        roots={}
        for value in args.repo_root:
            if '=' not in value:parser.error('--repo-root requires ID=PATH')
            rid,path=value.split('=',1)
            if rid in roots:parser.error('Duplicate --repo-root namespace')
            roots[rid]=path
        command=args.execution[1:] if args.execution and args.execution[0]=='--' else args.execution
        with SnapshotStore(args.database) as store:report=record_command(store,args.snapshot_id,roots,args.environment,args.output,command,max_seconds=args.max_seconds,max_events=args.max_events,max_bytes=args.max_bytes)
        print(json.dumps(report,indent=2));raise SystemExit(report['exit_code'])
    roots = tuple(args.source_root) or ("",)
    repo = Repository.from_git(args.repo, args.repo_id, args.revision, roots) if args.revision else Repository.from_directory(args.repo, args.repo_id, roots)
    args.database.parent.mkdir(parents=True, exist_ok=True)
    with SnapshotStore(args.database) as store:
        report = ingest(store, [repo], stage=args.stage,previous_snapshot_id=args.previous_snapshot)
    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
