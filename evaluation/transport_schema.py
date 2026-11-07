"""Explicit provider-schema adaptation; full local constraints remain authoritative.

This is a configurable transport profile, not a claim about every provider/model.
It neither discovers models nor downgrades response modes or makes API requests.
"""
from __future__ import annotations
import ast
import copy
from geographer.model import canonical
from .harness import sha


def subject_names(evidence):
    names={r['qualified_name'] for r in evidence['scope'].get('anchor_identities',[])
           if r.get('basis')=='snapshot_identity_only' and r.get('kind') in {'function','method','class'}}
    for r in evidence['records']:
        if r.get('kind')=='service':
            names.update(n['qualified_name'] for n in r['envelope'].get('data',{}).get('nodes',[]) if n['kind'] in {'function','method','class'})
        elif r.get('kind')=='directed_table':names.update(n['qualified_name'] for n in r['nodes'])
        elif r.get('kind')=='source' and r['path'].endswith('.py') and r['start']==1:
            text=r.get('text') if 'text' in r else ''.join(line['text'] for line in r.get('lines',[]))
            try:tree=ast.parse(text)
            except (SyntaxError,ValueError):continue
            class Visitor(ast.NodeVisitor):
                def __init__(self):self.stack=[]
                def visit_FunctionDef(self,node):
                    self.stack.append(node.name);names.add(r['path']+'.'+'.'.join(self.stack));self.generic_visit(node);self.stack.pop()
                visit_AsyncFunctionDef=visit_FunctionDef
                visit_ClassDef=visit_FunctionDef
            Visitor().visit(tree)
    return sorted(names)


def check_path_enum_feasibility(prompt,schema):
    """Public requested endpoints must be representable, including negative tasks.

    This checks legal identities only. It does not assert a connecting path or
    supply an answer oracle. Never fix a failure by copying a hidden golden.
    """
    allowed=schema['properties']['paths']['items']['items'].get('enum')
    if allowed is None:return
    requested=prompt.get('answer_contract',{}).get('requested_paths',[])
    missing=sorted({r[k] for r in requested for k in ('source','target') if r[k] not in allowed})
    if missing:raise ValueError('PATH_ENUM_INFEASIBLE: public requested identities excluded: '+', '.join(missing))


def compile_transport_schema(prompt,unsupported_keywords=('uniqueItems',)):
    """Return a strict response_format with evidence-grounded enums and an audit.

    Strip only schema KEYWORDS at schema positions; a property named uniqueItems
    or a value in an enum is ordinary data and must never be removed.
    """
    removable={'uniqueItems','maxItems','minItems','minimum','maximum','minLength','maxLength','pattern'}
    unsupported=set(unsupported_keywords)
    if not unsupported<=removable:raise ValueError('Unsafe or unknown transport-schema omission')
    schema=copy.deepcopy(prompt['answer_schema']);properties=schema['properties']
    facts=prompt.get('shared_label_vocabulary',[])
    if facts:properties['facts']['items']['enum']=sorted(set(facts))
    paths=sorted({r['path'] for r in prompt['evidence']['records'] if r.get('kind')=='source'})
    if paths:properties['citations']['items']['properties']['path']['enum']=paths
    subjects=subject_names(prompt['evidence'])
    if subjects:properties['paths']['items']['items']['enum']=subjects
    requested=prompt.get('answer_contract',{}).get('requested_paths')
    if requested is not None:properties['paths']['maxItems']=min(properties['paths'].get('maxItems',10),len(requested))
    if prompt.get('answer_contract',{}).get('path_semantics')=='direct_call':properties['paths']['items']['maxItems']=2
    check_path_enum_feasibility(prompt,schema)
    removed=[]
    def visit(node,pointer=''):
        if isinstance(node,bool):return node
        result={}
        for key,value in node.items():
            at=pointer+'/'+key.replace('~','~0').replace('/','~1')
            if key in unsupported:
                removed.append(dict(pointer=at,keyword=key,value=value));continue
            if key in {'properties','$defs','definitions','patternProperties','dependentSchemas'}:
                result[key]={name:visit(child,at+'/'+name.replace('~','~0').replace('/','~1')) for name,child in value.items()}
            elif key in {'items','additionalProperties','contains','not','if','then','else','propertyNames'} and isinstance(value,(dict,bool)):
                result[key]=visit(value,at)
            elif key in {'allOf','anyOf','oneOf','prefixItems'}:
                result[key]=[visit(child,at+'/'+str(i)) for i,child in enumerate(value)]
            else:result[key]=copy.deepcopy(value)
        return result
    wire=visit(schema)
    return dict(profile='explicit-keyword-omissions-v1',
        response_format=dict(type='json_schema',json_schema=dict(name='geographer_actor_answer',strict=True,schema=wire)),
        removed_constraints=removed,full_specialized_schema=schema,
        full_schema_sha256=sha(canonical(schema).encode()),transport_schema_sha256=sha(canonical(wire).encode()),
        validation_required='Full original JSON schema plus evidence grounding; transport omissions never relax local acceptance',
        fallback_policy='No automatic json_object downgrade; record negotiated mode and every failed request')
