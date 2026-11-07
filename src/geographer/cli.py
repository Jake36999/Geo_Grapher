"""Local CLI. Repository source is never imported as part of ingestion."""
import argparse
import json
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
    graphs=sub.add_parser('ingest-graphs',help='One independent database/graph per project profile')
    graphs.add_argument('--manifest',type=Path,required=True);graphs.add_argument('--catalog',type=Path,required=True)
    graphs.add_argument('--on-overlap',choices=['keep_separate','child_module']);graphs.add_argument('--report',type=Path)
    graphserver=sub.add_parser('serve-graphs',help='Graph-scoped MCP and display-only multi-graph UI')
    graphserver.add_argument('--catalog',type=Path,required=True);graphserver.add_argument('--transport',choices=['stdio','http'],default='http');graphserver.add_argument('--port',type=int,default=8765)
    graphserver.add_argument('--ui-origin',help='Compatibility listener: redirect its viewer to this loopback origin')
    plan=sub.add_parser('plan-graph',help='Read-only root collision review before graph import')
    plan.add_argument('--catalog',type=Path,required=True);plan.add_argument('--root',type=Path,required=True)
    papers=sub.add_parser('attach-graph-papers',help='Bind an existing independent paper corpus to one graph')
    papers.add_argument('--catalog',type=Path,required=True);papers.add_argument('--graph-id',required=True);papers.add_argument('--database',type=Path,required=True)
    for name in ('plan-graph-merge','merge-graphs'):
        merging=sub.add_parser(name,help='Reviewed namespace-preserving physical merge into a new graph')
        merging.add_argument('--catalog',type=Path,required=True);merging.add_argument('--graph-id',action='append',required=True)
        merging.add_argument('--label',required=True);merging.add_argument('--report',type=Path)
        if name=='merge-graphs':merging.add_argument('--plan-id',required=True)
    args = parser.parse_args()
    if args.command in {'serve','serve-graphs'}:require_pinned_mcp()
    if args.command in {'ingest-graphs','serve-graphs','plan-graph','attach-graph-papers','plan-graph-merge','merge-graphs'}:
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
            elif args.command=='attach-graph-papers':catalog.attach_papers(args.graph_id,args.database);result=dict(graph_id=args.graph_id,papers_attached=True)
            else:
                from .graph_router import GraphRouter
                from .graph_server import create_graph_http,create_graph_mcp
                router=GraphRouter(catalog)
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
