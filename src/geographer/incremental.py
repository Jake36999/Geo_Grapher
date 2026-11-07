"""Content-addressed reuse with conservative cross-file invalidation.

Source/grammar equality permits normal-form reuse, never binding-result reuse.
All import resolution, CFG bindings, documentary incidences and derived graphs
are rebuilt, since a changed exporter can affect otherwise unchanged importers.
"""
from __future__ import annotations
import ast,base64,hashlib,json,sys,threading
from collections import OrderedDict
from pathlib import Path
from .model import digest

def build_digest(names=None):
    package=Path(__file__).resolve().parent
    files=sorted(package.glob('*.py')) if names is None else [package/name for name in names]
    return digest([(p.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in files])

def normalizer_build_digest():return build_digest(['normalize.py','scopes.py','model.py'])

class ParseCache:
    def __init__(self,max_entries=256,max_source_bytes=16*1024*1024):
        self.entries=OrderedDict();self.bytes=0;self.hits=0;self.misses=0
        self.max_entries=max_entries;self.max_bytes=max_source_bytes;self.lock=threading.RLock()
    def parse(self,text,path):
        raw=text.encode('utf-8');key=digest('ast-cache-v1',sys.version,path,hashlib.sha256(raw).hexdigest())
        with self.lock:
            if key in self.entries:
                self.hits+=1;self.entries.move_to_end(key);return self.entries[key][0]
        tree=ast.parse(text,filename=path,type_comments=True)
        with self.lock:
            self.misses+=1
            if len(raw)<=self.max_bytes:
                if key not in self.entries:self.entries[key]=(tree,len(raw));self.bytes+=len(raw)
                while len(self.entries)>self.max_entries or self.bytes>self.max_bytes:
                    _,(_,size)=self.entries.popitem(last=False);self.bytes-=size
        return tree

PARSES=ParseCache()

def previous_normal_forms(store,snapshot_id,repositories):
    store.require_complete(snapshot_id)
    prior=store.connection.execute('SELECT config_json FROM snapshot_sets WHERE snapshot_id=?',(snapshot_id,)).fetchone()
    config=json.loads(prior[0]);compatible=(config.get('grammar')==f'{sys.version_info.major}.{sys.version_info.minor}' and config.get('normalization_version')=='py-ast-v1' and config.get('normalizer_build_digest')==normalizer_build_digest())
    sources={};unchanged=set();changed=[];added=[]
    for row in store.connection.execute("SELECT e.repo_id,e.rel_path,a.result_json FROM entities e JOIN analysis_results a ON a.snapshot_id=e.snapshot_id AND a.analysis_id='source:'||e.entity_id WHERE e.snapshot_id=?",(snapshot_id,)):
        sources[(row[0],row[1])]=base64.b64decode(json.loads(row[2])['bytes_base64'],validate=True)
    fresh={(r.repo_id,p):data for r in repositories for p,data in r.files.items()}
    for key,data in fresh.items():
        if key not in sources:added.append(key)
        elif sources[key]!=data:changed.append(key)
        else:unchanged.add(key)
    removed=sorted(sources.keys()-fresh.keys());normal_forms={}
    if compatible:
        for row in store.connection.execute("SELECT e.entity_id,e.repo_id,e.rel_path,e.ast_body_hash,a.result_json FROM entities e JOIN analysis_results a ON a.snapshot_id=e.snapshot_id AND a.analysis_id='norm:'||e.entity_id WHERE e.snapshot_id=? AND e.ast_body_hash IS NOT NULL",(snapshot_id,)):
            if (row[1],row[2]) in unchanged:
                rep=json.loads(row[4])['representation']
                if hashlib.sha256(rep.encode('utf-8')).hexdigest()==row[3]:normal_forms[row[0]]=(row[3],rep)
    report=dict(previous_snapshot_id=snapshot_id,changed_files=sorted(changed),added_files=sorted(added),removed_files=removed,unchanged_files=len(unchanged),
                compatible_normalizer=compatible,reused_normal_forms=0,invalidation='all_bindings_imports_documents_and_derived_graphs',
                layout_policy='new_snapshot_expansion_layout_key; no stale layouts copied')
    return normal_forms,report
