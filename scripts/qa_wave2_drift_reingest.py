"""Reconstruct the recorded six-edit wave-2 source fixture from its pinned Git tree."""
import argparse,json,subprocess
from pathlib import Path
from geographer.pipeline import ingest
from geographer.source import Repository
from geographer.store import SnapshotStore
from geographer.drift import drift_report

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise SystemExit('Use a fresh fixture directory')
    a.out.mkdir(parents=True)
    rev='45d37319d0b221839aa76819f8deca45467e2d15'
    names=subprocess.check_output(['git','ls-tree','-r','--name-only',rev,'--','src/geographer'],text=True).splitlines()
    files={n.removeprefix('src/geographer/'):subprocess.check_output(['git','show',rev+':'+n]).replace(b'\r\n',b'\n').replace(b'\n',b'\r\n') for n in names if n.endswith('.py')}
    edited=dict(files);text=files['labels.py']
    edits=[(b'_stem_parts',b'_stem_tokens'),(b'def snippet(text:str,budget:int)',b'def snippet(text:str,budget:int,min_words:int=3)'),
        (b".get('start_line') or 0",b".get('start_line',0) or 0"),
        (b"return graph.__dict__.setdefault('_labels_cache',{})",b"return  graph.__dict__.setdefault('_labels_cache',{})  # cache note"),
        (b'def _is_spec(',b'\r\n\r\ndef _is_spec('),
        (b"return _file_name(owner) if owner.kind=='file' else _name(owner.qualified_name)",b"return _file_name(owner) if owner.kind=='file' else _plain(owner.qualified_name)")]
    for old,new in edits:
        if old not in text:raise ValueError('Pinned fixture changed: '+repr(old))
        text=text.replace(old,new)
    edited['labels.py']=text
    with SnapshotStore(a.out/'fixture.sqlite') as store:
        base=ingest(store,[Repository('wave2-drift','base',files)],stage=3)['snapshot_id']
        changed=ingest(store,[Repository('wave2-drift','edited',edited)],stage=3)['snapshot_id']
        report=drift_report(store,base,store,changed);g=store.graph(base)
        targets={g.entities[r['entity_id']].qualified_name:r['tier'] for r in report['entities'] if g.entities[r['entity_id']].qualified_name in
            {'labels.py.'+n for n in ('_stem_parts','snippet','_start','_cache','_is_spec','_owner_name')}}
    out=dict(revision=rev,base_snapshot=base,changed_snapshot=changed,targets=targets,**report)
    (a.out/'result.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(counts=report['counts'],targets=targets)))
if __name__=='__main__':main()
