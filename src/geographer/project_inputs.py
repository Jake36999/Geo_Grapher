"""Bounded, metadata-only project inspection and explicit multi-root profiles."""
from collections import Counter
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import time

from .source import EXCLUDED,SUPPORTED,Repository,valid_path


def inspect_project(path, *, max_entries=20000, max_seconds=10):
    if type(max_entries) is not int or max_entries<1 or max_seconds<=0:raise ValueError('Positive inspection budgets required')
    root=Path(path).resolve()
    if not root.is_dir():raise ValueError('Project directory not found')
    started=time.monotonic();stack=[root];extensions=Counter();pruned=Counter();oversized=[];count=0;complete=True
    # Build products and vault machinery are inventory exclusions, not an
    # assertion that their content was ingested or scientifically classified.
    excluded=EXCLUDED|{'.pytest_cache','.mypy_cache','.ruff_cache','.evidence','.librarian','.obsidian','build','dist'}
    while stack and complete:
        directory=stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if count>=max_entries or time.monotonic()-started>max_seconds:complete=False;break
                    count+=1
                    if entry.is_symlink() or getattr(entry.stat(follow_symlinks=False),'st_file_attributes',0)&0x400:
                        pruned['symlink_or_junction']+=1;continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name in excluded:pruned[entry.name]+=1
                        else:stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        suffix=Path(entry.name).suffix.lower() or '[no extension]';extensions[suffix]+=1
                        if suffix in SUPPORTED and entry.stat().st_size>4194304 and len(oversized)<10:
                            oversized.append(Path(entry.path).relative_to(root).as_posix())
        except (OSError,PermissionError):pruned['unreadable_directory']+=1;complete=False
    return dict(root=str(root),inspection='metadata_only_no_source_execution',complete=complete,entries_seen=count,
        elapsed_seconds=round(time.monotonic()-started,3),format_counts=dict(sorted(extensions.items())),
        supported_format_counts={k:v for k,v in sorted(extensions.items()) if k in SUPPORTED},
        unhandled_format_counts={k:v for k,v in sorted(extensions.items()) if k not in SUPPORTED},
        pruned=dict(pruned),oversized_supported_examples=oversized,
        limitations=['Counts exclude pruned directories; incomplete inspections are not full inventories','PDFs, experimental arrays, CSV/JSON datasets and images are not parsed by the canonical source extractor'])


def load_workspace_manifest(path):
    path=Path(path).resolve();data=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict) or set(data)!={'version','repositories'} or data['version']!=1:raise ValueError('Expected version=1 and repositories')
    entries=data['repositories']
    if not isinstance(entries,list) or not 1<=len(entries)<=16:raise ValueError('Select 1..16 project roots')
    ids=set();roots=[];repositories=[]
    for entry in entries:
        allowed={'repo_id','path','source_roots','include_globs','exclude_globs','resolution_group','max_files','max_total_bytes'}
        if not isinstance(entry,dict) or set(entry)-allowed or not {'repo_id','path'}<=set(entry):raise ValueError('Unknown or missing project profile fields')
        rid=entry['repo_id']
        if not isinstance(rid,str) or rid in ids:raise ValueError('Unique string repo_id required')
        root=Path(entry['path']);root=(path.parent/root).resolve() if not root.is_absolute() else root.resolve()
        if not root.is_dir():raise ValueError('Missing project root: '+str(root))
        if any(root.is_relative_to(other) or other.is_relative_to(root) for other in roots):raise ValueError('Project roots must be distinct and nonoverlapping; use source_roots within one project')
        for field in ('source_roots','include_globs','exclude_globs'):
            value=entry.get(field,[])
            if not isinstance(value,list) or any(not isinstance(p,str) for p in value):raise ValueError(field+' must be a string list')
        for field,default,maximum in [('max_files',1000,100000),('max_total_bytes',16777216,536870912)]:
            value=entry.get(field,default)
            if type(value) is not int or not 1<=value<=maximum:raise ValueError('Invalid '+field)
        repo=Repository.from_directory(root,rid,tuple(entry.get('source_roots',[''])),
            resolution_group=entry.get('resolution_group'),include_globs=tuple(entry.get('include_globs',['*'])),
            exclude_globs=tuple(entry.get('exclude_globs',[])),max_files=entry.get('max_files',1000),max_total_bytes=entry.get('max_total_bytes',16777216))
        if not repo.files:raise ValueError('Project profile selects no supported files: '+rid)
        repositories.append(repo);ids.add(rid);roots.append(root)
    return repositories
