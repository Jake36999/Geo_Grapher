"""Standalone stdlib runner for an explicitly requested Python command.

Executed by the requested interpreter, not imported during repository ingestion.
"""
from __future__ import annotations
import dis,hashlib,json,os,runpy,sys,threading,time,traceback
from datetime import datetime,timezone,timedelta
from pathlib import Path

def stamp(dt):return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def verify_sources(config):
    for source in config['files']:
        root=Path(config['repo_roots'][source['repo_id']]).resolve()
        candidate=root.joinpath(*source['rel_path'].split('/')).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file() or candidate.stat().st_size>4194304:return False
        if hashlib.sha256(candidate.read_bytes()).hexdigest()!=source['sha256']:return False
    return True

class Recorder:
    def __init__(self,config):
        self.config=config;self.roots=[(rid,os.path.normcase(os.path.abspath(root))) for rid,root in config['repo_roots'].items()]
        self.started=datetime.now(timezone.utc);self.clock=time.monotonic();self.ended=None;self.stopped=False
        self.rows={};self.frames={};self.bytes=0;self.calls=0;self.resumes=0;self.native=0;self.outside=0;self.definition_frames=0;self.reasons=[]
        self.lock=threading.RLock();self.main_thread=threading.get_ident();self.prior=sys.getprofile();self.prior_threads=threading.getprofile()
        self.owner_pid=os.getpid()
        self.locations={}
        self.instrumentation={os.path.normcase(os.path.abspath(__file__)),os.path.normcase(os.path.abspath(str(Path(__file__).with_name('pytest_trace.py'))))}
        self.indexed={os.path.normcase(os.path.abspath(str(Path(config['repo_roots'][f['repo_id']])/f['rel_path']))) for f in config.get('files',[]) if f['rel_path'].endswith('.py')}
    def location(self,filename):
        if filename in self.locations:return self.locations[filename]
        if filename.startswith('<'):return None
        path=os.path.normcase(os.path.abspath(filename));matches=[]
        if path in self.instrumentation:return None
        for rid,root in self.roots:
            try:
                if os.path.commonpath([path,root])==root:matches.append((len(root),rid,os.path.relpath(path,root).replace('\\','/')))
            except ValueError:continue
        if not matches:result=None
        else:
            matches.sort(reverse=True)
            result=None if len(matches)>1 and matches[0][0]==matches[1][0] else matches[0][1:]
        self.locations[filename]=result
        while len(self.locations)>4096:self.locations.pop(next(iter(self.locations)))
        return result
    def stop(self,reason=None):
        if self.stopped:return
        self.stopped=True
        if reason:self.reasons.append(reason)
        self.ended=max(self.started+timedelta(microseconds=1),min(datetime.now(timezone.utc),self.started+timedelta(seconds=self.config['max_seconds'])))
    def profile(self,frame,event,arg):
        if os.getpid()!=self.owner_pid:
            sys.setprofile(None);threading.setprofile(None);return
        if self.stopped:
            sys.setprofile(self.prior if threading.get_ident()==self.main_thread else self.prior_threads);return
        try:
            with self.lock:
                if time.monotonic()-self.clock>=self.config['max_seconds']:self.stop('capture_duration_limit');return
                if event=='c_call':self.native+=1;return
                if event not in {'call','return'}:return
                fid=id(frame)
                if event=='return':
                    if fid not in self.frames:return
                    opcode=frame.f_code.co_code[frame.f_lasti] if frame.f_lasti>=0 else -1
                    if dis.opname[opcode]!='YIELD_VALUE':self.frames.pop(fid,None)
                    return
                callee=self.location(frame.f_code.co_filename)
                if not callee or os.path.normcase(os.path.abspath(frame.f_code.co_filename)) not in self.indexed:self.outside+=1;return
                # Class/module definition frames are not constructor/function
                # calls. They can still be the caller of a real callable frame.
                if not frame.f_code.co_flags&0x02:self.definition_frames+=1;return
                if fid in self.frames:self.resumes+=1;return
                if len(self.frames)>=10000:self.stop('live_frame_limit');return
                if self.calls>=self.config['max_events']:self.stop('logical_call_limit');return
                caller=frame.f_back
                if caller is None:self.outside+=1;return
                flags=frame.f_code.co_flags
                kind='async_generator_first_activation' if flags&0x200 else 'coroutine_first_activation' if flags&0x80 else 'generator_first_activation' if flags&0x20 else 'ordinary_call'
                row=dict(caller_path=caller.f_code.co_filename,caller_qualname=caller.f_code.co_qualname,caller_line=max(1,caller.f_lineno),
                    callee_path=frame.f_code.co_filename,callee_qualname=frame.f_code.co_qualname,callee_definition_line=frame.f_code.co_firstlineno,
                    callee_repo_id=callee[0],call_count=1,activation_kind=kind)
                caller_location=self.location(caller.f_code.co_filename)
                if caller_location:row['caller_repo_id']=caller_location[0]
                if any(len(row[k])>limit for k,limit in [('caller_path',4096),('callee_path',4096),('caller_qualname',2048),('callee_qualname',2048)]):self.stop('record_field_limit');return
                key=json.dumps({k:v for k,v in row.items() if k!='call_count'},sort_keys=True)
                if key not in self.rows:
                    if len(self.rows)>=100000:self.stop('record_count_limit');return
                    cost=len(json.dumps(row,sort_keys=True).encode('utf-8'))+32
                    if cost>16384:self.stop('record_field_limit');return
                    if self.bytes+cost>self.config['max_bytes']:self.stop('artifact_byte_limit');return
                    self.bytes+=cost;self.rows[key]=row
                else:self.rows[key]['call_count']+=1
                self.calls+=1;self.frames[fid]=frame
        except BaseException as exc:self.stop('profiler_error:'+type(exc).__name__)
    def run(self,command):
        code=0
        try:
            sys.setprofile(self.profile);threading.setprofile(self.profile)
            if not command:raise ValueError('A Python script, -m module or -c program is required')
            if command[0]=='-m':
                if len(command)<2:raise ValueError('Missing module name')
                sys.argv=command[1:];runpy.run_module(command[1],run_name='__main__',alter_sys=True)
            elif command[0]=='-c':
                if len(command)<2:raise ValueError('Missing Python program')
                sys.argv=['-c',*command[2:]];exec(compile(command[1],'<string>','exec'),{'__name__':'__main__'})
            else:
                sys.argv=command;sys.path.insert(0,str(Path(command[0]).resolve().parent));runpy.run_path(command[0],run_name='__main__')
        except SystemExit as exc:
            code=exc.code if isinstance(exc.code,int) else 0 if exc.code is None else 1
            if isinstance(exc.code,str):print(exc.code,file=sys.stderr)
        except KeyboardInterrupt:code=130
        except BaseException:traceback.print_exc();code=1
        finally:
            self.detect_replacement()
            self.stop();sys.setprofile(self.prior);threading.setprofile(self.prior_threads);self.frames.clear()
        return code
    def detect_replacement(self):
        if not self.stopped and (sys.getprofile()!=self.profile or threading.getprofile()!=self.profile):self.reasons.append('profile_hook_replaced')

def finalize_capture(config,recorder,code,matched):
    matched=matched and verify_sources(config)
    if not matched and 'source_mismatch_before_execution' not in recorder.reasons:recorder.reasons.append('source_changed_during_execution')
    raw=('\n'.join(json.dumps(row,sort_keys=True) for _,row in sorted(recorder.rows.items()))+'\n').encode('utf-8')
    # Empty captures contain no records, not an invented zero-count call.
    if not recorder.rows:raw=b''
    manifest=dict(format_version='python-call-trace-v1',environment=config['environment'],sources=config['sources'],repo_roots=config['repo_roots'],
        window=dict(start=stamp(recorder.started),end=stamp(recorder.ended or datetime.now(timezone.utc))),
        recorder=dict(name='geographer',version='setprofile-first-activation-v1',backend='sys.setprofile',python=sys.version,implementation_digest=config['recorder_build_digest']),
        coverage=dict(complete=not recorder.reasons and code==0,truncated=bool(recorder.reasons),process_scope='requested Python entrypoint until return; subprocesses/interpreter shutdown excluded',
            thread_scope='main and new Python threads until entrypoint returns; pre-existing threads/shutdown excluded',async_scope='first activation counted once; generator/coroutine resumes excluded; no task causality inference',
            limitations=[*recorder.reasons,'Only indexed Python-file callees under explicit repository roots are captured; external/native calls excluded',
                'Module/class definition frames and recorder implementation are excluded as callees; module/class bodies remain supported callers',
                'No latency quantiles recorded; segment timing is not end-to-end wall duration',
                *(['Command exited unsuccessfully; observations are incomplete'] if code else [])]),
        source_match=matched,trace_sha256=hashlib.sha256(raw).hexdigest(),exit_code=code,command_digest=config['command_digest'],
        statistics=dict(logical_calls=recorder.calls,resume_segments_ignored=recorder.resumes,native_calls_ignored=recorder.native,
            outside_scope_calls_ignored=recorder.outside,definition_frames_excluded=recorder.definition_frames,record_count=len(recorder.rows),dropped_events=None if recorder.reasons else 0))
    return raw,manifest

def main():
    config=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));command=sys.argv[2:]
    recorder=Recorder(config);matched=verify_sources(config)
    code=recorder.run(command) if matched else 2
    if os.getpid()!=recorder.owner_pid:return code
    if not matched:recorder.stop('source_mismatch_before_execution')
    raw,manifest=finalize_capture(config,recorder,code,matched)
    Path(config['trace_output']).write_bytes(raw);Path(config['manifest_output']).write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return code

if __name__=='__main__':raise SystemExit(main())
