"""Oracle-free evidence validators suitable for a task-local repair callback.

These checks reject malformed/unsupported presentation; they cannot certify an
explanation's semantics or turn a syntax match into exact static resolution.
"""
from __future__ import annotations
import ast
import jsonschema

CONTEXT_NAMESPACES={'basis','direction','scope','execution','static_call','runtime','absence'}
TASK_NAMESPACES={
    'implementation':{'implementation','signature'},'cross_subsystem':{'caller','callee'},
    'callers_callees':{'caller','callee'},'impact':{'impact'},
    'quotient_cycle':{'grouping','quotient_cycle','leaf_cycle'},
    'rule_violation':{'rule','status','rationale'},'helper_retry':{'retry','retry_count'},
    'inherited_dispatch':{'inherits','dispatch'},'stale_documentation':{'document','immediate_callee'},
    'same_name':{'callee','not_callee'},'disconnected':{'path'},'honest_abstention':set(),
}


def answer_contract(category):
    """Public task-type constraints, not selected answers or hidden truth labels."""
    namespaces=TASK_NAMESPACES.get(category)
    basis={'stale_documentation':['basis:source'],'helper_retry':['basis:source_control_flow'],
           'cross_subsystem':['basis:static']}.get(category,[])
    return dict(version='grounded-actor-prompt-v4.1',path_elements='code_subject_qualified_name',
                fact_namespaces=sorted(namespaces|CONTEXT_NAMESPACES) if namespaces is not None else None,
                documentary_required=category=='stale_documentation',required_answer_facts=basis,
                required_answer_namespaces=(['document','immediate_callee'] if category=='stale_documentation' else
                                            ['caller','callee'] if category=='callers_callees' else []),
                allowed_basis_labels=basis or ['basis:source','basis:static'],
                path_semantics='direct_call' if category in {'callers_callees','stale_documentation','same_name'} else 'dependency_chain')


def source_text(record):
    if 'text' in record:return record['text']
    return ''.join(row['text'] for row in record.get('lines',[]))


def validate_actor_answer(answer,prompt):
    issues=[]
    def issue(code,message,retryable=True):issues.append(dict(code=code,message=message,retryable=retryable))
    try:jsonschema.validate(answer,prompt['answer_schema'])
    except jsonschema.ValidationError as exc:
        issue('ANSWER_SCHEMA',exc.message);return issues
    evidence=prompt['evidence'];sources=[r for r in evidence['records'] if r.get('kind')=='source']
    source_by_path={r['path']:r for r in sources}
    vocabulary=set(prompt.get('shared_label_vocabulary',[]))
    invalid=[f for f in answer['facts'] if f not in vocabulary]
    if invalid:issue('FACT_VOCABULARY',f'Facts must be complete vocabulary strings including prefix; remove unknown labels: {invalid}')
    namespaces=prompt.get('answer_contract',{}).get('fact_namespaces')
    unrelated=[f for f in answer['facts'] if namespaces is not None and f.split(':',1)[0] not in namespaces]
    if unrelated:issue('FACT_TASK_SCOPE',f'These label namespaces do not answer this public task type; remove them: {unrelated}')
    if answer['status']=='answer':
        missing=[f for f in prompt.get('answer_contract',{}).get('required_answer_facts',[]) if f not in answer['facts']]
        if missing:issue('MISSING_PROVENANCE',f'Include the required public provenance labels as well as your conclusion: {missing}. Minimal does not mean omitting the evidence basis.')
        required_namespaces=prompt.get('answer_contract',{}).get('required_answer_namespaces')
        if required_namespaces is None:
            required_namespaces=['document','immediate_callee'] if prompt.get('answer_contract',{}).get('documentary_required') else []
        absent=[n for n in required_namespaces if not any(f.partition(':')[0]==n for f in answer['facts'])]
        if absent:issue('MISSING_ASSESSMENT',f'The public task requires an explicit assessment in these label namespaces: {absent}. Choose supported conclusions from the vocabulary, or abstain if undetermined; do not assume a conclusion merely to fill the shape.')
    requested=prompt.get('answer_contract',{}).get('requested_paths')
    if requested is not None:
        if len(answer['paths'])>len(requested):issue('EXTRA_PATH','Return only paths requested by the public focus/pin anchors; do not add other helpful-looking dependency paths.')
        pairs={(r['source'],r['target']) for r in requested}
        for path in answer['paths']:
            if (path[0],path[-1]) not in pairs:issue('PATH_ANCHORS','A returned path must connect a requested source/target pair in order, not an unrelated pair.')
            if prompt.get('answer_contract',{}).get('path_semantics')=='direct_call' and len(path)!=2:
                issue('DIRECT_PATH_LENGTH','A requested direct-call path has exactly two subjects: caller and immediate callee.')
        if answer['status']=='answer' and prompt.get('answer_contract',{}).get('path_semantics')=='direct_call':
            targets={r['target'] for r in requested}
            ends={(p[0],p[-1]) for p in answer['paths']}
            for fact in answer['facts']:
                prefix,_,target=fact.partition(':')
                if prefix not in {'immediate_callee','callee'}:continue
                if target not in targets:
                    issue('CALLEE_TASK_SCOPE',f'{fact} does not name a requested direct-call target. Remove unrelated callee claims; do not add unrequested paths.')
                elif not any((r['source'],target) in ends for r in requested if r['target']==target):
                    issue('CALLEE_PATH_CONSISTENCY',f'{fact} must agree with the final subject of its requested caller path. Correct the inconsistent fields from evidence; do not invent or silently rewrite the path.')
    for key in answer['scope']:
        if answer['scope'][key]!=evidence['scope'].get(key):issue('STALE_SCOPE',f'Scope field {key} must match the delivered evidence scope.')
    for c in answer['citations']:
        record=source_by_path.get(c['path'])
        if record is None:
            code_subject_file=next((p for p in source_by_path if c['path'].startswith(p+'.')),None)
            if code_subject_file:issue('CITATION_FILE_PATH',f"citations[].path is a file path, not a subject qualified_name. Use the delivered file {code_subject_file!r}; keep the subject name only in paths[] and claims.")
            else:issue('SOURCE_NOT_DELIVERED',f"No original source was delivered for {c['path']}. Retrieve it or abstain.",False)
        elif not record['start']<=c['start']<=c['end']<=record['end']:
            issue('CITATION_RANGE',f"Citation {c['path']}:{c['start']}-{c['end']} is outside delivered absolute lines {record['start']}-{record['end']}.")
    known={r['qualified_name'] for r in evidence['scope'].get('anchor_identities',[])
           if r.get('basis')=='snapshot_identity_only' and r.get('kind') in {'function','method','class'}}
    calls=[];bases=[]
    for record in evidence['records']:
        if record.get('kind')=='service':
            data=record['envelope'].get('data',{})
            known.update(n['qualified_name'] for n in data.get('nodes',[]) if n['kind'] in {'function','method','class'})
        elif record.get('kind')=='directed_table':known.update(n['qualified_name'] for n in record['nodes'])
    for record in sources:
        if not record['path'].endswith('.py'):continue
        # Only parse complete files. A partial/folded chunk requires explicit
        # witness evidence; never guess ownership by dedenting a source fragment.
        if record['start']!=1:continue
        try:tree=ast.parse(source_text(record))
        except (SyntaxError,ValueError):continue
        imported={}
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                for alias in node.names:imported.setdefault(alias.asname or alias.name,set()).add(alias.name)
        aliases={name:next(iter(values)) for name,values in imported.items() if len(values)==1}
        class Visitor(ast.NodeVisitor):
            def __init__(self):self.stack=[]
            def visit_FunctionDef(self,node):
                self.stack.append(node.name);known.add(record['path']+'.'+'.'.join(self.stack));self.generic_visit(node);self.stack.pop()
            visit_AsyncFunctionDef=visit_FunctionDef
            def visit_ClassDef(self,node):
                self.stack.append(node.name);name=record['path']+'.'+'.'.join(self.stack);known.add(name)
                for base in node.bases:
                    target=ast.unparse(base).split('.')[-1]
                    bases.append((name,aliases.get(target,target),record['path'],base.lineno,base.end_lineno))
                self.generic_visit(node);self.stack.pop()
            def visit_Call(self,node):
                if self.stack:
                    callee=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else None
                    if callee:
                        if isinstance(node.func,ast.Name):callee=aliases.get(callee,callee)
                        calls.append((record['path']+'.'+'.'.join(self.stack),callee,record['path'],node.lineno,node.end_lineno))
                self.generic_visit(node)
        Visitor().visit(tree)
    for path in answer['paths']:
        for qname in path:
            if qname not in known:
                issue('PATH_IDENTITY',f'Path element {qname!r} is not a delivered code-subject qualified_name. Use e.g. app/service.py.process, not app/service.py; never invent a symbol suffix.')
        # Malformed requested paths need an answer repair, not a claim that the
        # correct source is missing. Ground steps after identity/anchor repair.
        if requested is not None and (path[0],path[-1]) not in {(r['source'],r['target']) for r in requested}:continue
        if prompt.get('answer_contract',{}).get('path_semantics')=='direct_call' and len(path)!=2:continue
        for u,v in zip(path,path[1:]):
            if u not in known or v not in known:continue
            candidates=[(p,start,end) for caller,callee,p,start,end in calls+bases if caller==u and callee==v.rsplit('.',1)[-1]]
            # Preview metadata is useful for locating original content but does
            # not replace a delivered source line or a source citation.
            if not candidates:
                issue('WITNESS_SOURCE_GAP',f'No delivered original call/base expression grounds {u} -> {v}. Retrieve its original witness/source or abstain.',False)
            elif not any(c['path']==p and c['start']<=start and c['end']>=end for p,start,end in candidates for c in answer['citations']):
                locations=', '.join(f'{p}:{start}-{end}' for p,start,end in candidates)
                issue('CALL_SITE_CITATION',f'For {u} -> {v}, cite the actual call/base expression at {locations}; an import or def header does not ground this edge.')
    if 'document:stale' in answer['facts'] or (answer['status']=='answer' and prompt.get('answer_contract',{}).get('documentary_required')):
        docs=[r for r in sources if r['path'].endswith(('.md','.txt')) or r.get('content_kind')=='documentation']
        if not docs:issue('DOCUMENT_SOURCE_GAP','A stale-document claim requires original documentary content and contradictory current source. Retrieve documentary support or abstain.',False)
        elif not any(c['path']==r['path'] for r in docs for c in answer['citations']):
            issue('DOCUMENT_CITATION','You claimed document:stale. Cite its original documentary span as well as contradictory current source, or abstain.')
        else:
            for c in answer['citations']:
                record=source_by_path.get(c['path'],{})
                anchors=record.get('section_citation_anchors',[])
                covering=[a for a in anchors if a['start']<=c['start']<=c['end']<=a['end']]
                if covering:
                    anchor=min(covering,key=lambda a:a['end']-a['start'])
                    if c['start']>anchor['start'] or c['end']<anchor['end']:
                        issue('DOCUMENT_SECTION_CONTEXT',f"Preserve the cited documentary section's heading and complete claim paragraph: {c['path']}:{anchor['start']}-{anchor['end']} ({anchor['heading']}).")
    return issues


def validation_callback(prompt):
    """Task-local hook: callable(answer) -> repair message or None.

    Safe to pass to a librarian Profile/runner's validator hook. No generic
    librarian schema checker, transport or unrelated path task is modified.
    """
    def validate(answer):
        problems=validate_actor_answer(answer,prompt)
        if not problems:return None
        return '\n'.join(p['code']+': '+p['message'] for p in problems)
    return validate
