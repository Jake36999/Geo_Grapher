"""Opt-in subprocess recording: command arguments are never shell interpolated."""
from __future__ import annotations
import base64,hashlib,json,subprocess,sys,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from .model import digest
from .trace import source_manifest,MAX_BYTES

def capture_config(store,sid,repo_roots,environment,command,*,max_seconds=60.,max_events=100000,max_bytes=MAX_BYTES):
    if not command:raise ValueError('Pass an explicit Python command after --')
    if not isinstance(environment,str) or not 1<=len(environment)<=128:raise ValueError('Invalid environment name')
    if not 1e-6<=max_seconds<=3600 or type(max_events) is not int or not 1<=max_events<=1000000 or type(max_bytes) is not int or not 1024<=max_bytes<=MAX_BYTES:raise ValueError('Invalid recorder limits')
    sources=source_manifest(store,sid)
    if set(repo_roots)!=set(sources):raise ValueError('Supply exactly one --repo-root ID=PATH for every snapshot repository')
    roots={rid:str(Path(root).resolve()) for rid,root in repo_roots.items()}
    paths=[Path(root) for root in roots.values()]
    if any(a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(paths) for b in paths[i+1:]):raise ValueError('Recorder repository roots must be disjoint; namespace ownership would be ambiguous')
    files=[]
    for row in store.connection.execute("SELECT scope_json,result_json FROM analysis_results WHERE snapshot_id=? AND algorithm_version='source-bytes-v1'",(sid,)):
        owner=store.connection.execute('SELECT repo_id,rel_path FROM entities WHERE snapshot_id=? AND entity_id=?',(sid,json.loads(row[0])['entity_id'])).fetchone()
        value=json.loads(row[1]);files.append(dict(repo_id=owner['repo_id'],rel_path=owner['rel_path'],sha256=hashlib.sha256(base64.b64decode(value['bytes_base64'])).hexdigest()))
    for rid,source in sources.items():
        if digest(sorted((f['rel_path'],f['sha256']) for f in files if f['repo_id']==rid))!=source['digest']:raise ValueError('Snapshot source-byte cache does not match its repository digest')
    build=digest([(name,hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()) for name in ('recording.py','trace_runner.py','pytest_trace.py')])
    return dict(repo_roots=roots,files=files,sources=sources,environment=environment,max_seconds=max_seconds,max_events=max_events,max_bytes=max_bytes,command_digest=digest(command),recorder_build_digest=build)

def publish_capture(output,raw,manifest):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    sidecar=Path(str(output)+'.manifest.json')
    for destination,data in [(output,raw),(sidecar,json.dumps(manifest,indent=2).encode('utf-8'))]:
        temporary_path=None
        try:
            with tempfile.NamedTemporaryFile(dir=output.parent,prefix='.geographer-',suffix='.partial',delete=False) as stream:
                temporary_path=Path(stream.name);stream.write(data)
            if temporary_path.resolve().parent!=output.parent.resolve():raise ValueError('Temporary artifact escaped output directory')
            temporary_path.replace(destination)
        finally:
            if temporary_path is not None and temporary_path.exists():temporary_path.unlink()
    return sidecar

def validate_output(options,output):
    targets={Path(output).resolve(),Path(str(output)+'.manifest.json').resolve()}
    if any((Path(options['repo_roots'][f['repo_id']])/f['rel_path']).resolve() in targets for f in options['files']):raise ValueError('Trace output would overwrite indexed source')

def record_command(store,sid,repo_roots,environment,output,command,*,max_seconds=60.,max_events=100000,max_bytes=MAX_BYTES):
    options=capture_config(store,sid,repo_roots,environment,command,max_seconds=max_seconds,max_events=max_events,max_bytes=max_bytes)
    validate_output(options,output)
    roots=options['repo_roots'];sources=options['sources']
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='geographer-record-') as directory:
        temporary=Path(directory);trace_out=temporary/'trace.jsonl';manifest_out=temporary/'manifest.json'
        config={**options,'trace_output':str(trace_out),'manifest_output':str(manifest_out)}
        config_file=temporary/'config.json';config_file.write_text(json.dumps(config),encoding='utf-8')
        args=list(command[1:]);flags=[]
        while args and args[0] in {'-u','-B','-I','-E','-s','-S'}:flags.append(args.pop(0))
        if not args or args[0].startswith('-') and args[0] not in {'-m','-c'}:raise ValueError('Recorder supports Python script, -m, -c and -u/-B/-I/-E/-s/-S flags')
        started=datetime.now(timezone.utc)
        result=subprocess.Popen([command[0],*flags,str(Path(__file__).with_name('trace_runner.py')),str(config_file),*args],shell=False)
        try:result.wait()
        except KeyboardInterrupt:
            # Console interrupts normally reach both processes. Allow the child
            # to restore hooks/finalize before removing its temporary directory.
            try:result.wait(timeout=5)
            except (subprocess.TimeoutExpired,KeyboardInterrupt):
                result.terminate()
                try:result.wait(timeout=5)
                except (subprocess.TimeoutExpired,KeyboardInterrupt):result.kill();result.wait()
        if not trace_out.exists() or not manifest_out.exists():
            # A hard exit/crash cannot run Python finally blocks. Publish an
            # honest empty failed capture, never stale output from a prior run.
            raw=b'';ended=max(datetime.now(timezone.utc),started+timedelta(microseconds=1))
            manifest=dict(format_version='python-call-trace-v1',environment=environment,sources=sources,repo_roots=roots,
                window=dict(start=started.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),end=ended.strftime('%Y-%m-%dT%H:%M:%S.%fZ')),
                recorder=dict(name='geographer',version='setprofile-first-activation-v1',backend='sys.setprofile',python='child terminated'),source_match=False,
                coverage=dict(complete=False,truncated=True,process_scope='child terminated',thread_scope='unknown',async_scope='unknown',limitations=['No finalized capture: hard exit, crash or runner failure']),
                trace_sha256=hashlib.sha256(raw).hexdigest(),exit_code=result.returncode,command_digest=digest(command))
        else:raw=trace_out.read_bytes();manifest=json.loads(manifest_out.read_text(encoding='utf-8'))
        # Write from finalized temporary artifacts; the checksum detects any
        # interrupted publication between the two destination replacements.
        sidecar=publish_capture(output,raw,manifest)
    return dict(trace=str(output),manifest=str(sidecar),exit_code=result.returncode,coverage=manifest['coverage'],source_match=manifest['source_match'])
