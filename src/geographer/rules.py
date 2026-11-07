"""Strict versioned architecture rules; missing evidence never proves nonexecution."""
from __future__ import annotations

from .resources import resource_root

from concurrent.futures import ProcessPoolExecutor, TimeoutError
import json
import multiprocessing
from pathlib import Path
import re

import jsonschema
import yaml
from yaml.tokens import AliasToken,AnchorToken,TagToken

from .analysis import subject_graph,DEFAULT_FILTER
from .model import digest


class RuleConflict(ValueError):pass


class StrictLoader(yaml.SafeLoader):
    def construct_mapping(self,node,deep=False):
        mapping={}
        for key_node,value_node in node.value:
            key=self.construct_object(key_node,deep=deep)
            if key=='<<' or key in mapping:raise RuleConflict("Duplicate or merged YAML key")
            mapping[key]=self.construct_object(value_node,deep=deep)
        return mapping

# YAML 1.2 core scalars: yes/on and dates remain strings, not YAML 1.1 bool/date objects.
StrictLoader.yaml_implicit_resolvers={key:[(tag,pattern) for tag,pattern in values if tag not in
    {'tag:yaml.org,2002:bool','tag:yaml.org,2002:timestamp','tag:yaml.org,2002:int','tag:yaml.org,2002:float'}]
    for key,values in yaml.SafeLoader.yaml_implicit_resolvers.items()}
StrictLoader.add_implicit_resolver('tag:yaml.org,2002:bool',re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$'),list('tTfF'))
StrictLoader.add_implicit_resolver('tag:yaml.org,2002:int',re.compile(r'^[-+]?(?:[0-9][0-9_]*|0o[0-7_]+|0x[0-9a-fA-F_]+)$'),list('-+0123456789'))
StrictLoader.add_implicit_resolver('tag:yaml.org,2002:float',re.compile(r'^[-+]?(?:(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?|[0-9]+[eE][-+]?[0-9]+)$'),list('-+0123456789.'))
def _integer(loader,node):
    value=loader.construct_scalar(node).replace('_','');sign=-1 if value.startswith('-') else 1
    value=value.lstrip('+-')
    return sign*int(value[2:] if value.startswith(('0x','0o')) else value,16 if value.startswith('0x') else 8 if value.startswith('0o') else 10)
StrictLoader.add_constructor('tag:yaml.org,2002:int',_integer)


def glob_regex(pattern):
    if pattern.startswith('/') or '\\' in pattern or ':' in pattern or any(p in {'.','..',''} for p in pattern.split('/')) or any(c in pattern for c in '[]{}'):
        raise RuleConflict("Unsupported path glob")
    parts=pattern.split('/');result=''
    for i,part in enumerate(parts):
        if part=='**':result+='(?:[^/]+/)*' if i<len(parts)-1 else '.*'
        else:
            if '**' in part:raise RuleConflict("** must be a complete segment")
            result+=''.join('[^/]*' if c=='*' else '[^/]' if c=='?' else re.escape(c) for c in part)
            if i<len(parts)-1:result+='/'
    return re.compile('^'+result+'$')


def validate_regex(pattern):
    from re import _parser
    if len(pattern)>1024:raise RuleConflict("Regex exceeds limit")
    if re.search(r'\((?!\?:)',pattern):raise RuleConflict("Only noncapturing regex groups are supported")
    try:tree=_parser.parse(pattern,0)
    except re.error as exc:raise RuleConflict(str(exc)) from exc
    allowed={'LITERAL','NOT_LITERAL','ANY','IN','RANGE','CATEGORY','BRANCH','SUBPATTERN','MAX_REPEAT','MIN_REPEAT','AT'}
    def visit(nodes,in_repeat=False):
        for op,args in nodes:
            name=str(op)
            if name not in allowed:raise RuleConflict("Unsupported regex construct: "+name)
            if name in {'MAX_REPEAT','MIN_REPEAT'}:
                if in_repeat:raise RuleConflict("Nested regex quantification is unsupported")
                visit(args[2],True)
            elif name=='SUBPATTERN':
                if args[0] is not None or args[1] or args[2]:raise RuleConflict("Captures/flags are unsupported")
                visit(args[3],in_repeat)
            elif name=='BRANCH':
                for branch in args[1]:visit(branch,in_repeat)
            elif name=='IN':visit(args,in_repeat)
    visit(tree)


def _ready(event):event.set()


def _regex_batch(pattern,names):
    compiled=re.compile(pattern)
    return [compiled.fullmatch(name) is not None for name in names]


def bounded_regex_matches(pattern,names,timeout=.1):
    context=multiprocessing.get_context('spawn');ready=context.Event()
    executor=ProcessPoolExecutor(max_workers=1,mp_context=context,initializer=_ready,initargs=(ready,))
    # Start worker before the bounded matching clock; Windows spawn is not matching work.
    try:
        warmup=executor.submit(_regex_batch,'',[])
        if not ready.wait(10):raise RuleConflict("Regex worker did not initialise")
        warmup.result(timeout=10)
        return executor.submit(_regex_batch,pattern,names).result(timeout=timeout)
    except TimeoutError as exc:
        for process in (executor._processes or {}).values():process.terminate()
        raise RuleConflict("Regex mapping batch exceeded 100 ms") from exc
    finally:executor.shutdown(wait=False,cancel_futures=True)


class ArchitectureRules:
    def __init__(self,raw:bytes,schema_path=None):
        if len(raw)>1048576:raise RuleConflict("Rules exceed 1 MiB")
        try:
            text=raw.decode('utf-8')
            if any(isinstance(t,(AliasToken,AnchorToken,TagToken)) for t in yaml.scan(text)):
                raise RuleConflict("YAML aliases, anchors and tags are forbidden")
            self.model=yaml.load(text,Loader=StrictLoader)
            schema_path=schema_path or resource_root()/'contracts/geographer.rules.schema.json'
            jsonschema.validate(self.model,json.loads(schema_path.read_text()))
        except (yaml.YAMLError,jsonschema.ValidationError,UnicodeError,TypeError) as exc:raise RuleConflict(str(exc)) from exc
        components=self.model['components'];rules=self.model['rules']
        if len(components)>256 or len(rules)>4096 or any(len(c['selectors'])>128 for c in components):raise RuleConflict("Rules collection limit exceeded")
        self.components={c['id']:c for c in components}
        if len(self.components)!=len(components) or len({r['id'] for r in rules})!=len(rules):raise RuleConflict("Duplicate rule/component ID")
        pairs=set()
        for rule in rules:
            if rule['source'] not in self.components or rule['target'] not in self.components:raise RuleConflict("Unknown rule component")
            pair=(rule['source'],rule['target'])
            if pair in pairs:raise RuleConflict("Conflicting or redundant ordered-pair rules")
            pairs.add(pair)
        for c in components:
            for selector in c['selectors']:
                if 'path_glob' in selector:glob_regex(selector['path_glob'])
                if 'qualified_name_regex' in selector:validate_regex(selector['qualified_name_regex'])
        self.digest=digest(self.model)
        self._maps={}

    def map_entities(self,graph,snapshot_id):
        if snapshot_id in self._maps:return self._maps[snapshot_id]
        matches={eid:set() for eid,e in graph.entities.items() if e.sort not in {'synthetic','text'}}
        for component in self.model['components']:
            for selector in component['selectors']:
                path=glob_regex(selector['path_glob']) if 'path_glob' in selector else None
                ids=[eid for eid in matches if graph.entities[eid].repo_id==selector['repo_id'] and
                     (path is None or graph.entities[eid].rel_path is not None and path.fullmatch(graph.entities[eid].rel_path))]
                outcomes=bounded_regex_matches(selector['qualified_name_regex'],[graph.entities[eid].qualified_name for eid in ids]) if 'qualified_name_regex' in selector else [True]*len(ids)
                for eid,yes in zip(ids,outcomes):
                    if yes:matches[eid].add(component['id'])
        if any(len(v)>1 for v in matches.values()):raise RuleConflict("An entity maps to multiple conceptual components")
        mapping={eid:next(iter(values),'Unmapped') for eid,values in matches.items()}
        for eid,e in graph.entities.items():
            if e.kind=='scope_atom':mapping[eid]=mapping.get(e.parent_id,'Unmapped')
        self._maps[snapshot_id]=mapping
        return mapping

    def check(self,graph,snapshot_id,scope_members,coverage,filters=None):
        mapping=self.map_entities(graph,snapshot_id)
        _,rels=subject_graph(graph,filters or DEFAULT_FILTER)
        pairs={}
        for r in rels:
            if r.source_subject_id in scope_members:
                pair=(mapping.get(r.source_subject_id,'Unmapped'),mapping.get(r.target_subject_id,'Unmapped'))
                pairs.setdefault(pair,[]).append(r.relationship_id)
        rulemap={(r['source'],r['target']):r for r in self.model['rules']}
        active_sources={mapping[e] for e in scope_members if e in mapping}
        relevant=set(pairs)|{p for p in rulemap if p[0] in active_sources}
        findings=[]
        for pair in sorted(relevant):
            rule=rulemap.get(pair);witnesses=sorted(pairs.get(pair,[]))
            limitations=list(coverage['limitations'])
            complete=coverage['status']=='complete_for_declared_static_subset'
            if 'Unmapped' in pair:status='unmapped'
            elif rule:
                kind=rule['type']
                if kind=='require':status='match' if witnesses else 'missing_required' if complete else 'inconclusive'
                elif kind=='allow':status='allowed_present' if witnesses else 'allowed_not_present'
                else:status='forbidden_present' if witnesses else 'forbidden_absent' if complete else 'inconclusive'
            else:status='forbidden_present' if self.model['world_policy']=='closed' else 'unclassified'
            findings.append(dict(id='finding:'+digest(self.digest,pair,status),model_digest=self.digest,rule_id=rule['id'] if rule else None,
                source_component_id='view:component:'+digest(self.digest,pair[0]),target_component_id='view:component:'+digest(self.digest,pair[1]),
                status=status,rationale=rule['rationale'] if rule else 'No explicit rule for this pair',witness_count=len(witnesses),
                witness_projection_ids=[],witness_handle='handle:rule:'+digest(snapshot_id,self.digest,pair) if witnesses else None,
                limitations=limitations))
        return mapping,findings
