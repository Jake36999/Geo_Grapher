"""Deterministic documentary hierarchy, separate from canonical code ownership."""
from __future__ import annotations
import hashlib,re
from .model import digest

VERSION='documentary-tree-v1'

def parse_document(raw:bytes,path:str):
    text=raw.decode('utf-8-sig');lines=text.splitlines();raw_lines=raw.splitlines(keepends=True)
    offsets=[0]
    for line in raw_lines:offsets.append(offsets[-1]+len(line))
    sha=hashlib.sha256(raw).hexdigest();root='section:'+digest(path,sha,'root')
    sections=[dict(section_id=root,parent_section_id=None,level=0,heading='',start_line=1,end_line=max(1,len(lines)),fragment_ids=[])]
    stack=[sections[0]];blocks=[];buffer=[];start=1;fence=None;front=False;html=None
    def flush():
        nonlocal buffer
        if buffer:blocks.append(dict(kind='paragraph',start_line=start,end_line=start+len(buffer)-1,text='\n'.join(buffer),section_id=stack[-1]['section_id']));buffer=[]
    i=0
    while i<len(lines):
        line=lines[i];n=i+1
        if i==0 and line.strip()=='---':front=True
        elif front and line.strip() in {'---','...'}:front=False;i+=1;continue
        marker=re.match(r'^ {0,3}(`{3,}|~{3,})',line)
        if marker and not front:
            token=marker[1]
            if fence is None:fence=(token[0],len(token))
            elif token[0]==fence[0] and len(token)>=fence[1] and not line[marker.end():].strip():fence=None
            if not buffer:start=n
            buffer.append(line);i+=1;continue
        heading=None;span=1
        if line.lstrip().startswith('<!--'):html='-->'
        tag=re.match(r'^ {0,3}<(script|pre|style|textarea|div|section|table|details)(?:\s|>)',line,re.I)
        if tag:html='</'+tag[1].lower()+'>'
        opaque=html is not None
        if html and html in line.lower():html=None
        if path.endswith('.md') and not opaque and not front and fence is None and not line.startswith(('    ','\t')):
            match=re.match(r'^ {0,3}(#{1,6})(?:[ \t]+(.*?)|[ \t]*)$',line)
            if match:heading=(len(match[1]),re.sub(r'[ \t]+#+[ \t]*$','',match[2] or '').strip())
            elif line.strip() and i+1<len(lines) and re.fullmatch(r' {0,3}(?:=+|-+)[ \t]*',lines[i+1]):
                heading=(1 if lines[i+1].lstrip().startswith('=') else 2,line.strip());span=2
        if heading:
            flush();level,title=heading
            while len(stack)>1 and stack[-1]['level']>=level:stack.pop()['end_line']=n-1
            section=dict(section_id='section:'+digest(path,sha,n,title),parent_section_id=stack[-1]['section_id'],level=level,
                         heading=title,start_line=n,end_line=max(1,len(lines)),fragment_ids=[])
            sections.append(section);stack.append(section)
            blocks.append(dict(kind='heading',start_line=n,end_line=n+span-1,text='\n'.join(lines[i:i+span]),section_id=section['section_id']))
            i+=span;continue
        if not line.strip() and fence is None:flush()
        else:
            if not buffer:start=n
            buffer.append(line)
        i+=1
    flush()
    for section in sections:
        section['start_byte']=offsets[min(section['start_line']-1,len(offsets)-1)]
        section['end_byte']=offsets[min(section['end_line'],len(offsets)-1)]
    return dict(algorithm_version=VERSION,parser_version='markdown-structure-v1',artifact_digest=sha,root_section_id=root,
                sections=sections,blocks=blocks,limitations=['Structural Markdown subset: HTML blocks and extension-specific heading constructs are not interpreted'])
