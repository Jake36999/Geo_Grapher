"""Explicit opt-in only: pytest -p geographer.pytest_trace --geographer-trace-output ..."""
import sys,threading,os
import pytest
from .recording import capture_config,publish_capture,validate_output
from .store import SnapshotStore
from .trace_runner import Recorder,verify_sources,finalize_capture

def pytest_addoption(parser):
    group=parser.getgroup('geographer observations')
    group.addoption('--geographer-trace-output')
    group.addoption('--geographer-trace-database')
    group.addoption('--geographer-trace-snapshot')
    group.addoption('--geographer-trace-root',action='append',default=[])
    group.addoption('--geographer-trace-environment',default='pytest')
    group.addoption('--geographer-trace-max-seconds',type=float,default=60.)
    group.addoption('--geographer-trace-max-events',type=int,default=100000)
    group.addoption('--geographer-trace-max-bytes',type=int,default=64*1024*1024)

def pytest_sessionstart(session):
    config=session.config;output=config.getoption('--geographer-trace-output')
    if not output:return
    database=config.getoption('--geographer-trace-database');sid=config.getoption('--geographer-trace-snapshot')
    if not database or not sid:raise pytest.UsageError('Geographer trace output requires database, snapshot and root mappings')
    roots={}
    for value in config.getoption('--geographer-trace-root'):
        if '=' not in value:raise pytest.UsageError('Geographer trace root requires ID=PATH')
        rid,path=value.split('=',1)
        if rid in roots:raise pytest.UsageError('Duplicate Geographer root')
        roots[rid]=path
    try:
        with SnapshotStore(database) as store:
            options=capture_config(store,sid,roots,config.getoption('--geographer-trace-environment'),['pytest',*config.invocation_params.args],
                max_seconds=config.getoption('--geographer-trace-max-seconds'),max_events=config.getoption('--geographer-trace-max-events'),max_bytes=config.getoption('--geographer-trace-max-bytes'))
        rec=Recorder(options)
        validate_output(options,output)
        if not verify_sources(options):
            rec.stop('source_mismatch_before_execution');raw,manifest=finalize_capture(options,rec,2,False);publish_capture(output,raw,manifest)
            raise pytest.UsageError('Geographer source mismatch; recording and test execution refused')
    except ValueError as exc:raise pytest.UsageError(str(exc)) from exc
    config._geographer_capture=(output,options,rec)
    sys.setprofile(rec.profile);threading.setprofile(rec.profile)

def finish(config,code):
    state=getattr(config,'_geographer_capture',None)
    if state is None:return
    config._geographer_capture=None;output,options,rec=state
    if os.getpid()!=rec.owner_pid:return
    rec.detect_replacement();rec.stop();sys.setprofile(rec.prior);threading.setprofile(rec.prior_threads);rec.frames.clear()
    raw,manifest=finalize_capture(options,rec,int(code),True)
    manifest['recorder']['name']='geographer-pytest'
    manifest['coverage']['process_scope']='pytest session through sessionfinish; subprocesses/shutdown excluded'
    manifest['coverage']['thread_scope']='main and new Python threads until pytest sessionfinish; pre-existing threads/shutdown excluded'
    publish_capture(output,raw,manifest)

def pytest_sessionfinish(session,exitstatus):finish(session.config,exitstatus)
def pytest_unconfigure(config):finish(config,1)
