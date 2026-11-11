"""Deterministic display labels (display-label-v1) and role badges (role-badge-v1).

Everything here is a pure function of stored facts: no clocks, randomness or
hash(). Frame-level disambiguation lives in ``disambiguate`` and is called by
the viewport over the node set of one frame.
"""
from __future__ import annotations
import fnmatch,re
from collections import defaultdict
from pathlib import PurePosixPath

LIMIT=48
SEP=' › '
LABELLED_KINDS=frozenset({'fragment','function','method','class','file'})

# Frozen: 120 common English function words. Never add content words
# (package, pip, wheel, install, run, migrate, command, database, configure, ...).
STOPWORDS=tuple(sorted(set("""
a an the and or but if then else when with without against of to in on at by for from as is are was were be been being
it its this that these those you your we our they their he she his her not no can will would should could may might must
do does did done have has had into onto over under than so such via per using use used
i me my us them him who whom which what where why how also just very more most some any all each both
only own same too about above after again before below between during off out up down through until while there here
other because
""".split())))
_STOP=frozenset(STOPWORDS)
_WORD=re.compile(r"[A-Za-z][A-Za-z0-9_'-]{1,}")
_MARKDOWN=re.compile(r'[#*_>\[\]()!`]')


def truncate_label(text:str,limit:int=LIMIT)->str:
    """Left-trim whole ' › ' segments first, then characters, prefixing an ellipsis."""
    if len(text)<=limit:return text
    segments=text.split(SEP)
    while len(segments)>1 and len('…'+SEP.join(segments))>limit:segments.pop(0)
    out='…'+SEP.join(segments)
    if len(out)>limit:out='…'+out[1:][-(limit-1):] if limit>1 else '…'
    return out


def content_words(text:str)->list[str]:
    return [w for w in _WORD.findall(_MARKDOWN.sub(' ',text or '')) if w.lower() not in _STOP]


def snippet(text:str,budget:int)->str:
    """First 4 content words (at least 3) whose space-joined length fits ``budget``.

    When even 3 words do not fit, the 3 words are returned anyway so the caller
    can shrink the label part instead.
    """
    words=content_words(text)
    for n in (4,3):
        chosen=' '.join(words[:n])
        if len(words)>=3 and len(chosen)<=budget:return chosen
    return ' '.join(words[:3])


def _cache(graph)->dict:
    return graph.__dict__.setdefault('_labels_cache',{})


def _name(qualified:str)->str:
    return qualified.rsplit('.',1)[-1]


def _plain(qualified:str)->str:
    return re.sub(r'#\d+$','',_name(qualified))


def _sections(graph,doc_id):
    cache=_cache(graph).setdefault('sections',{})
    if doc_id not in cache:
        result=graph.analyses.get('document:'+doc_id,{}).get('result',{})
        cache[doc_id]={s['section_id']:s for s in result.get('sections',[])}
    return cache[doc_id]


def _file_name(e)->str:
    return PurePosixPath(e.rel_path).name if e.rel_path else _name(e.qualified_name)


def _owner_name(owner)->str:
    return _file_name(owner) if owner.kind=='file' else _name(owner.qualified_name)


def base_label(graph,entity_id:str)->str:
    """Label for one entity, <= 48 chars, before frame-level disambiguation."""
    e=graph.entities[entity_id]
    if e.kind in {'function','method','class'}:return truncate_label(_name(e.qualified_name))
    if e.kind=='file':return truncate_label(_file_name(e))
    if e.kind=='fragment':
        owner=graph.entities[e.parent_id]
        if graph.analyses.get('document:'+entity_id,{}).get('result',{}).get('coordinate_space')=='decoded_docstring_value':
            return truncate_label(_owner_name(owner)+' · docstring')
        section_id=graph.analyses.get('text:'+entity_id,{}).get('result',{}).get('section_id')
        if section_id is None:return truncate_label(_owner_name(owner)+' · comment')
        sections=_sections(graph,e.parent_id);chain=[];seen=set();cursor=sections.get(section_id)
        while cursor is not None and cursor['section_id'] not in seen:
            seen.add(cursor['section_id'])
            if cursor['heading']:chain.append(cursor['heading'])
            cursor=sections.get(cursor['parent_section_id'])
        if not chain:return truncate_label(_file_name(owner)+' · intro')
        return truncate_label(SEP.join(reversed(chain)))
    return truncate_label(e.qualified_name.split('/')[-1].split('.')[-1] or e.qualified_name)


def _start(node)->int:
    return (node.get('source') or {}).get('start_line') or 0


def _suffix_labels(items,parts_of,join,name)->dict[str,str]:
    """Shortest path suffix (k>=1) making every colliding label unique; else numbering."""
    ordered=sorted(items,key=lambda n:(_start(n),n['id']))
    for k in range(1,max(len(parts_of(n)) for n in ordered)+1):
        labels={n['id']:join(parts_of(n)[-k:],name) for n in ordered}
        if len(set(labels.values()))==len(labels):return labels
    seen=defaultdict(int);out={}
    for n in ordered:
        label=join(parts_of(n),name);seen[label]+=1;count=seen[label]
        out[n['id']]=label if count==1 else truncate_label(label,LIMIT-len(f' ({count})'))+f' ({count})'
    return out


def _stem_parts(node):
    path=(node.get('source') or {}).get('rel_path')
    if not path:return ['']
    p=PurePosixPath(path);return [*p.parent.parts,p.stem]


def _dir_parts(node):
    path=(node.get('source') or {}).get('rel_path')
    return list(PurePosixPath(path).parent.parts) if path else []


def disambiguate(nodes:list[dict])->dict[str,str]:
    """Labels for one viewport frame, keyed by node id (nodes without a display_label are omitted)."""
    out={n['id']:n['display_label'] for n in nodes if n.get('display_label')}
    # Code entities: frame-wide collisions on (kind, label) take the minimal ancestor prefix.
    groups=defaultdict(list)
    for n in nodes:
        if n['id'] in out and n['kind'] in {'function','method','class'}:groups[(n['kind'],out[n['id']])].append(n)
    for (_,label),members in sorted(groups.items()):
        if len(members)>1:
            for nid,value in _suffix_labels(members,_stem_parts,lambda parts,name:'::'.join([p for p in parts if p]+[name]),label).items():out[nid]=truncate_label(value)
    # Files: the same rule over directories.
    groups=defaultdict(list)
    for n in nodes:
        if n['id'] in out and n['kind']=='file':groups[out[n['id']]].append(n)
    for label,members in sorted(groups.items()):
        if len(members)>1:
            for nid,value in _suffix_labels(members,_dir_parts,lambda parts,name:'/'.join([*parts,name]),label).items():out[nid]=truncate_label(value)
    # Fragments: siblings sharing a label gain a content snippet, then numbering.
    def siblings():
        found=defaultdict(list)
        for n in nodes:
            if n['id'] in out and n['kind']=='fragment':found[(str(n.get('parent_id')),out[n['id']])].append(n)
        return sorted(found.items())
    for (_,label),members in siblings():
        if len(members)<2:continue
        for n in members:
            text=n.get('label_text') or '';budget=LIMIT-len(label)-3;words=snippet(text,budget)
            if not words:continue
            head=label if len(words)<=budget else truncate_label(label,max(1,LIMIT-3-len(words)))
            joined=f'{head} · {words}'
            out[n['id']]=joined if len(joined)<=LIMIT else joined[:LIMIT-1]+'…'
    for (_,label),members in siblings():
        members.sort(key=lambda n:(_start(n),n['id']))
        for index,n in enumerate(members[1:],2):out[n['id']]=truncate_label(label,LIMIT-len(f' ({index})'))+f' ({index})'
    return out


# ---------------------------------------------------------------- role badges
_ENTRY_SUFFIXES=('.command','.group','.route','.get','.post','.put','.patch','.delete','.task','.callback')
_SCHEMA_BASES=frozenset({'BaseModel','TypedDict','NamedTuple','Enum','IntEnum','StrEnum','Protocol'})
_SCHEMA_DECORATORS=frozenset({'dataclass','dataclasses.dataclass','attr.s','attrs.define'})
_GATE=('validate','check','verify','ensure','assert','guard','require')
_IO=('read','write','load','save','fetch','open','dump','export','download','upload','connect')
_IO_EXTERNAL=('open','io.','sqlite3.','requests.','urllib.','http.','socket.','subprocess.','shutil.','pathlib.')
_UTIL_STEMS=frozenset({'util','utils','helpers','common'})


def _bare(text:str)->str:
    """Drop call arguments and subscripts: 'click.command(name="x")' -> 'click.command'."""
    return re.split(r'[(\[]',text,maxsplit=1)[0].strip()


def _degrees(graph):
    """Exact static in/out degree (same-repository callers) and external call targets per entity."""
    cache=_cache(graph);key=(len(graph.relationships),len(graph.entities))
    if cache.get('degrees_key')!=key:
        incoming=defaultdict(set);outgoing=defaultdict(set);external=defaultdict(set)
        for rid in sorted(graph.relationships):
            r=graph.relationships[rid]
            if r.family!='static' or r.resolution_status!='exact':continue
            a,b=graph.entities.get(r.source_subject_id),graph.entities.get(r.target_subject_id)
            if a is None or b is None or a.entity_id==b.entity_id:continue
            if b.is_external:external[a.entity_id].add(b.qualified_name);continue
            if a.is_external or a.repo_id!=b.repo_id:continue
            incoming[b.entity_id].add(a.entity_id);outgoing[a.entity_id].add(b.entity_id)
        cache.update(degrees_key=key,degrees=(incoming,outgoing,external),badges={})
    return cache['degrees']


def role_badge(graph,entity_id:str)->str|None:
    """role-badge-v1: rules in order, first match wins; every input is a stored fact."""
    degrees=_degrees(graph);badges=_cache(graph)['badges']
    if entity_id not in badges:badges[entity_id]=_role_badge(graph,entity_id,*degrees)
    return badges[entity_id]


def _role_badge(graph,eid,incoming,outgoing,external):
    e=graph.entities[eid];path=e.rel_path or '';parts=PurePosixPath(path).parts if path else ();filename=parts[-1] if parts else ''
    callable_=e.kind in {'function','method'}
    inputs=graph.analyses.get('role-inputs:'+eid,{}).get('result',{})
    decorators=[_bare(d) for d in inputs.get('decorators',[])];bases={_bare(b).rsplit('.',1)[-1] for b in inputs.get('bases',[])}
    name=_plain(e.qualified_name);indeg=len(incoming.get(eid,()));outdeg=len(outgoing.get(eid,()))
    if callable_ and (name in {'main','cli'} or any(d.endswith(_ENTRY_SUFFIXES) for d in decorators) or filename=='__main__.py'):return 'Entry'
    if e.kind=='class' and (_SCHEMA_BASES&bases or _SCHEMA_DECORATORS&set(decorators)):return 'Schema'
    if callable_ and name.startswith(_GATE):return 'Gate'
    if callable_ and (name.startswith(_IO) or any(t.startswith(_IO_EXTERNAL) for t in external.get(eid,()))):return 'IO'
    if e.kind in {'function','method','class'} and indeg>=3 and indeg>=outdeg:return 'Core'
    if callable_ and (name.startswith('_') and not (name.startswith('__') and name.endswith('__')) and outdeg<=1 or
                      PurePosixPath(filename).stem in _UTIL_STEMS):return 'Util'
    if e.kind in {'document','fragment'} and parts and _is_spec(parts):return 'Spec'
    return None


def _is_spec(parts)->bool:
    if any(p.lower() in {'docs','spec','design','rfc'} for p in parts[:-1]):return True
    upper=parts[-1].upper()
    return fnmatch.fnmatchcase(upper,'SPEC*.MD') or upper.endswith('_SPECIFICATION.MD') or fnmatch.fnmatchcase(upper,'ADR*.MD')
