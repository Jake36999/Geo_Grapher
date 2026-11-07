"""Versioned static claim provenance; proof assumptions are not probabilities."""
from __future__ import annotations
import ast
import hashlib
import io
import tokenize
from .model import digest

CLAIM_VERSION = 'claim-details-v1'
RESOLVER_VERSION = 'lexical-cfg-v2'
REASONS = frozenset({
    'LEXICAL_UNIQUE_BINDING','UNAMBIGUOUS_IMPORT_MEMBER','STATIC_MRO_UNIQUE','STATIC_BASE_UNIQUE',
    'CFG_BRANCH_REBOUND','POLYMORPHIC_MRO_CANDIDATE','DECORATOR_WRAPPED_BINDING',
    'CLOSURE_CELL_MUTABLE','AMBIGUOUS_MODULE_ROOT','TREESITTER_SYNTACTIC_ONLY',
    'EXTERNAL_PACKAGE_UNINDEXED','BUILTIN_SYMBOL','MISSING_RELATIVE_IMPORT',
    'DYNAMIC_ATTR_DISPATCH','REFLECTIVE_CALL','DYNAMIC_EXPORT_STAR','UNSUPPORTED_ANALYSIS',
    'UNREACHABLE_SYNTAX','GLOBAL_BINDING_MUTATED',
    'UNRESOLVED_IMPORT_MEMBER',
})

def source_cache(raw,text):
    encoding,_=tokenize.detect_encoding(io.BytesIO(raw).readline)
    codec='utf-8' if encoding=='utf-8-sig' else encoding
    starts=[];position=0
    for line in raw.splitlines(keepends=True):starts.append(position);position+=len(line)
    return dict(codec=codec,starts=starts,lines=[line.encode('utf-8') for line in text.splitlines(keepends=True)],
                source_digest=hashlib.sha256(raw).hexdigest())

def source_span(raw: bytes, text: str, node, cache=None):
    """CPython AST columns are UTF-8 byte columns, even for non-UTF8 sources."""
    cache=cache or source_cache(raw,text)
    def offset(line,col):
        prefix=cache['lines'][line-1][:col].decode('utf-8')
        bom=3 if line==1 and raw.startswith(b'\xef\xbb\xbf') else 0
        return cache['starts'][line-1]+bom+len(prefix.encode(cache['codec']))
    start=node.lineno;end=getattr(node,'end_lineno',start)
    return dict(start_line=start,end_line=end,start_byte=offset(start,node.col_offset),
                end_byte=offset(end,getattr(node,'end_col_offset',node.col_offset)))

def static_details(unit, source, subtype, node, details, status):
    details=dict(details or {})
    reasons=list(dict.fromkeys(details.pop('reason_codes', [])))
    primary=reasons[0] if reasons else ('UNSUPPORTED_ANALYSIS' if status=='unresolved' else
             'CFG_BRANCH_REBOUND' if status=='candidate' else 'UNAMBIGUOUS_IMPORT_MEMBER' if subtype.startswith('imports') else 'LEXICAL_UNIQUE_BINDING')
    if primary not in REASONS or any(r not in REASONS for r in reasons):raise ValueError('Unknown static reason code')
    raw=unit.repo.files[unit.path]
    if not hasattr(unit,'claim_source_cache'):unit.claim_source_cache=source_cache(raw,unit.text)
    cache=unit.claim_source_cache
    span=source_span(raw,unit.text,node,cache)
    occurrence='occurrence:'+digest(unit.repo.repo_id,unit.repo.revision,unit.path,source,subtype,span,
                                    details.get('import',details.get('callee',details.get('base',''))))
    details.update(claim_version=CLAIM_VERSION,claim_kind='static_conclusion',producer='python-ast-symtable',
      producer_version=RESOLVER_VERSION,resolver=RESOLVER_VERSION,occurrence_id=occurrence,
      reason_code=primary,additional_reason_codes=sorted(set(reasons)-{primary}),
      assumptions=['indexed source revisions and declared source roots','standard import/lexical semantics for supported constructs',
                   'module functions use initialized-module globals except detected early named calls; callback/cyclic initialization is unsupported',
                   'unindexed runtime monkeypatches are not excluded by static analysis'],
      source_digest=cache['source_digest'],source_span=span,
      syntax=dict(kind=type(node).__name__,text=raw[span['start_byte']:span['end_byte']].decode(cache['codec'])),
      alternatives=sorted(set(details.get('alternatives',[]))))
    return details

def validate_details(value):
    if value.get('claim_version')!=CLAIM_VERSION or value.get('claim_kind')!='static_conclusion':raise ValueError('Unsupported static claim')
    if value.get('reason_code') not in REASONS:raise ValueError('Unknown primary reason')
    if any(r not in REASONS for r in value.get('additional_reason_codes',[])):raise ValueError('Unknown secondary reason')
    span=value['source_span']
    if not 0<=span['start_byte']<=span['end_byte']:raise ValueError('Invalid source span')
    if not value.get('occurrence_id') or not value.get('assumptions'):raise ValueError('Missing provenance')
