"""Pre-generation held-out eligibility, wording and equivalence rules."""
from collections import Counter
import re

SEED=20261114
REVISION=2
QUOTAS={('constants','librarian-v2'):6,('constants','ToolSet'):4,
        ('functions','librarian-v2'):5,('functions','ToolSet'):5,
        ('behaviors','librarian-v2'):3,('behaviors','ToolSet'):2}

def meaningful(text):
    # Decorative rulers cannot make an item eligible.
    words=re.findall(r'[A-Za-z][A-Za-z_-]{2,}',text)
    return len(words)>=20 and len(set(w.casefold() for w in words))>=12

def markers(entity,names):
    full=entity['qualified_name'];short=full.rsplit('.',1)[-1]
    result=[full]
    if names[short]==1 and (len(short)>=6 and '_' in short or re.fullmatch(r'[A-Z][A-Z0-9_]{3,}',short)):
        result.append(short)
    tail='.'.join(full.split('.')[-2:])
    if not tail.startswith('py.'):result.append(tail)
    return sorted(set(result))

def validate_question(item,question):
    reasons=[]
    if not isinstance(question,str) or not 60<=len(question)<=600:return ['length_or_type']
    if not re.search(r'\bcit(?:e|ation)\b',question,re.I):reasons.append('missing_source_citation_request')
    if item['category']=='constants' and not re.search(r'\bconstant\b',question,re.I):reasons.append('wrong_granularity_constant_not_requested')
    if item['category'] in {'functions','behaviors'} and not re.search(r'\b(?:function|method)\b',question,re.I):reasons.append('function_or_method_not_requested')
    for marker in item['equivalence_markers']:
        # Uppercase identifiers are case-sensitive; ordinary English nouns
        # such as "runner" must not be replaced into garbled grammar.
        if re.search(r'(?<!\w)'+re.escape(marker)+r'(?!\w)',question):reasons.append('identifier_leak');break
    if re.search(r'\bthe\s+the\b|the documented implementation',question,re.I):reasons.append('mechanically_garbled_question')
    return sorted(set(reasons))

def review_approved(review):
    return (isinstance(review,dict) and review.get('accept') is True and
            all(review.get(k) is True for k in ('grammatical','own_documentation','unambiguous_top20','equivalence_correct')))

def partner_documented(documentation,qualified_name):
    short=qualified_name.rsplit('.',1)[-1]
    return bool(re.search(r'(?:alias(?:es)?|delegates?\s+to|implemented\s+by|applied\s+(?:by|in)|used\s+(?:by|in))[^.\n]{0,120}(?<!\w)'+re.escape(short)+r'(?!\w)',documentation,re.I))

def supported_equivalence(item):
    return all(partner_documented(item['documentation'],m['qualified_name']) for m in item['equivalence_members'] if m['entity_id']!=item['entity_id'])

def defined_rule_id(documentation,category):
    if category=='constants':return None
    match=re.match(r'\s*(R\d{3,4})\s*[:\u2013-]',documentation)
    return match.group(1) if match else None
