"""Deterministic, loss-disclosed repair context from already delivered evidence."""
from __future__ import annotations
from collections import Counter
import copy
from geographer.model import canonical
from .harness import sha


def build_repair_prompt(original,answer,issues):
    prompt=copy.deepcopy(original)
    records=prompt['evidence']['records']
    compact=(prompt.get('answer_contract',{}).get('path_semantics')=='direct_call'
             and any(r.get('kind')=='source' for r in records))
    removed=[]
    if compact:
        removed=[r for r in records if r.get('kind')!='source']
        prompt['evidence']['records']=[r for r in records if r.get('kind')=='source']
    prompt['previous_answer']=copy.deepcopy(answer)
    prompt['validation_issues']=copy.deepcopy(issues)
    prompt['repair_instructions']=[
        'Return the COMPLETE corrected answer JSON, not a patch. Correct the listed public contract/evidence issues only.',
        'Use only the supplied original source and scope. Do not assume a documentary conclusion merely because a label exists; abstain if it cannot be determined.',
        'Preserve supported claims, original citations and requested path direction. No new tools or evidence are available in this repair.',
    ]
    prompt['repair_context']=dict(policy='source-only-direct-call-v1' if compact else 'full-original-context-v1',
        original_prompt_sha256=sha(canonical(original).encode()),
        omitted_record_count=len(removed),omitted_kinds=dict(Counter(r.get('kind','unknown') for r in removed)),
        source_policy='All originally delivered source records retained verbatim; no source added or fetched',
        scope_policy='Original snapshot/filter/model/runtime scope and identity-only anchors retained')
    return prompt
