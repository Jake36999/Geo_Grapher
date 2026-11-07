"""Independent, deliberately narrow source oracle for pinned module-function calls.

This is not an all-Python truth oracle. It excludes module/global mutation,
reflection, attribute writes, decorators, local/free bindings and early module
execution. Labels come from AST+symtable source, never resolver classifications.
"""
from __future__ import annotations
import ast,collections,json,sys,symtable,tokenize,io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from geographer.source import Repository
from geographer.store import SnapshotStore
from phase5_measure import TOOLSET,COMMIT

def run():
    repo=Repository.from_git(TOOLSET,'ToolSet',COMMIT,('aletheia_toolchain','local_tool_assist_mcp'))
    parsed={}
    for path,raw in repo.files.items():
        if path.endswith('.py'):
            enc,_=tokenize.detect_encoding(io.BytesIO(raw).readline);text=raw.decode(enc)
            parsed[path]=(ast.parse(text),symtable.symtable(text,path,'exec'))
    written_attrs={n.attr for tree,_ in parsed.values() for n in ast.walk(tree)
                   if isinstance(n,ast.Attribute) and isinstance(n.ctx,(ast.Store,ast.Del))}
    expected={}
    def local_walk(root):
        yield root
        for child in ast.iter_child_nodes(root):
            if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)):continue
            yield from local_walk(child)
    for path,(tree,table) in parsed.items():
        defs=collections.defaultdict(list)
        for n in tree.body:
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and not n.decorator_list:defs[n.name].append(n)
        globals_written={name for n in ast.walk(tree) if isinstance(n,ast.Global) for name in n.names}
        if any(isinstance(n,ast.Name) and n.id in {'eval','exec','globals','locals','vars','__dict__','setattr','delattr'} for n in ast.walk(tree)):continue
        module_names=[]
        for n in local_walk(tree):
            if isinstance(n,ast.Name) and isinstance(n.ctx,(ast.Store,ast.Del)):module_names.append(n.id)
            if isinstance(n,(ast.Import,ast.ImportFrom)):
                module_names.extend(a.asname or a.name.split('.')[0] for a in n.names)
        early=[n.lineno for n in local_walk(tree) if isinstance(n,ast.Call)]
        for fn in [n for group in defs.values() for n in group]:
            candidates=[t for t in table.get_children() if t.get_name()==fn.name and t.get_lineno()==fn.lineno]
            if len(candidates)!=1:continue
            st=candidates[0]
            for call in local_walk(fn):
                if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name):continue
                name=call.func.id
                if len(defs.get(name,[]))!=1 or name in globals_written or name in written_attrs or name in module_names:continue
                target=defs[name][0]
                if early and min(early)<=target.lineno:continue
                try:symbol=st.lookup(name)
                except KeyError:continue
                if not symbol.is_global():continue
                expected[(path,call.lineno,call.col_offset)]=(path,target.lineno,target.name)
    out=ROOT/'output/phase5';before=json.loads((out/'baseline-triage.json').read_text(encoding='utf-8'));after=json.loads((out/'after-triage.json').read_text(encoding='utf-8'))
    results={}
    for name,artifact in [('baseline',before),('after',after)]:
        with SnapshotStore(out/f'{name}.sqlite') as store:
            graph=store.graph(artifact['ingestion']['snapshot_id'])
        sites={(r['site'][1],r['site'][4],r['site'][5]):r for r in artifact['site_records']}
        matched=0;exact=0;wrong_exact=[]
        for key,target in expected.items():
            record=sites.get(key)
            if not record:continue
            matched+=1
            actual={(graph.entities[t].rel_path,graph.entities[t].start_line,graph.entities[t].qualified_name.rsplit('.',1)[-1]) for t in record['targets']}
            if record['status']=='exact':
                if actual=={target}:exact+=1
                else:wrong_exact.append(dict(site=key,expected=target,actual=sorted(actual)))
        results[name]=dict(labelled_sites=len(expected),emitted_labelled_sites=matched,correct_exact=exact,wrong_exact=wrong_exact,
                           supported_subset_exact_recall=exact/len(expected) if expected else None)
    assert expected and not results['after']['wrong_exact'],results
    artifact=dict(scope='unique same-file module functions under the documented conservative exclusions; not whole-repository precision or recall',
                  results=results,expected=[dict(site=k,target=v) for k,v in sorted(expected.items())])
    (out/'independent-oracle.json').write_text(json.dumps(artifact,indent=2),encoding='utf-8')
    print(json.dumps(results,indent=2))
if __name__=='__main__':run()
