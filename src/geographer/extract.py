"""Python facts, conservative lexical resolution and documentary incidences."""
from __future__ import annotations

import ast
import base64
import io
import re
import sys
import tokenize
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .cfg import CFG, UNBOUND, join, target_names
from .model import Graph, Entity, Relationship, Evidence, canonical, digest, entity_id, EXTRACTOR_VERSION
from .normalize import normalized_ast
from .scopes import ScopeIndex, Scope
from .source import Repository
from .incremental import PARSES
from .dispatch import StaticDispatch
from .claims import static_details, validate_details


@dataclass
class Binding:
    id: str
    name: str
    kind: str
    scope: Scope
    target: str | None = None
    module: str | None = None
    member: str | None = None


@dataclass
class Unit:
    repo: Repository
    path: str
    text: str
    tree: ast.Module
    scopes: ScopeIndex
    file_id: str
    modules: list[str]
    owners: dict[Scope, str] = field(default_factory=dict)
    bindings: dict[Scope, dict[str, set[str]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(set)))
    cfgs: dict[Scope, CFG] = field(default_factory=dict)
    final: dict[Scope, dict] = field(default_factory=dict)
    global_mutations: set[str] = field(default_factory=set)
    attribute_mutations: set[str] = field(default_factory=set)
    early_functions: dict[str, int] = field(default_factory=dict)


class PythonExtractor(StaticDispatch):
    def __init__(self, repositories: list[Repository], *, normal_forms=None):
        self.normal_forms=normal_forms or {};self.normal_reuse=0
        self.repositories = repositories
        if len({r.repo_id for r in repositories})!=len(repositories):raise ValueError('Duplicate repository namespaces')
        self.graph = Graph()
        self.failures = {r.repo_id: [] for r in repositories}
        self.units: list[Unit] = []
        self.module_map: dict[str, list[Unit]] = defaultdict(list)
        self.namespace_map: dict[str, set[str]] = defaultdict(set)
        self.bindings: dict[str, Binding] = {}
        self.unit_for_scope: dict[Scope, Unit] = {}
        self.binding_ids: dict[tuple[int, str], str] = {}
        self.binding_lines = {}
        self.repo_roots = {}
        self.dir_ids = {}
        self.seen_calls: set[ast.Call] = set()
        self.definition_nodes: dict[str, ast.AST] = {}
        self.tainted_modules: set[str] = set()
        self.entity_units = {}
        self.module_names_for_entity = defaultdict(list)

    def flags(self, path, text=""):
        parts = PurePosixPath(path).parts
        is_test = any(p in {"test", "tests", "testing"} for p in parts[:-1]) or parts[-1].startswith("test_") or parts[-1].endswith("_test.py")
        generated = any(p in {"generated", "_generated"} for p in parts[:-1]) or "@generated" in text[:1024] or "DO NOT EDIT" in text[:1024]
        return dict(is_test=int(is_test), is_generated=int(generated), is_vendor=int(any(p in {"vendor", "vendored", "third_party"} for p in parts[:-1])))

    def parent_directory(self, repo_id, path):
        parent = self.repo_roots[repo_id]
        current = []
        for segment in PurePosixPath(path).parts[:-1]:
            current.append(segment)
            key = (repo_id, "/".join(current))
            if key not in self.dir_ids:
                eid = entity_id(repo_id, "directory", key[1])
                self.graph.add(Entity(eid, repo_id, "directory", key[1].replace("/", "."), parent, language="none", rel_path=key[1]))
                self.dir_ids[key] = eid
            parent = self.dir_ids[key]
        return parent

    def extract(self) -> Graph:
        # Independent projects share only the synthetic workspace, never an
        # import namespace or documentary mention index. Linked repositories
        # must deliberately declare the same resolution group.
        groups=defaultdict(list)
        for repo in self.repositories:
            key=('linked',repo.resolution_group) if repo.resolution_group else ('isolated',repo.repo_id)
            groups[key].append(repo)
        if len(groups)>1:
            for key in sorted(groups):
                child=PythonExtractor(groups[key],normal_forms=self.normal_forms)
                graph=child.extract()
                for entity in graph.entities.values():
                    if entity.kind=='workspace' and entity.entity_id in self.graph.entities:continue
                    self.graph.add(entity)
                self.graph.relationships.update(graph.relationships)
                self.graph.evidence.update(graph.evidence)
                self.graph.incidences.extend(graph.incidences)
                self.graph.analyses.update(graph.analyses)
                self.failures.update(child.failures);self.normal_reuse+=child.normal_reuse
            self.graph.augment()
            return self.graph
        workspace = entity_id("@workspace", "root")
        self.graph.add(Entity(workspace, "@workspace", "workspace", "Workspace", None, sort="synthetic", language="none"))
        for repo in sorted(self.repositories, key=lambda r: r.repo_id):
            rid = entity_id(repo.repo_id, "repository")
            self.repo_roots[repo.repo_id] = rid
            self.graph.add(Entity(rid, repo.repo_id, "repository", repo.repo_id, workspace, language="none"))
            for path, data in sorted(repo.files.items()):
                self.inventory(repo, path, data)
        # All declarations/import bindings exist before resolving any cross-file call.
        for unit in self.units:
            self.index_bindings(unit)
        for unit in self.units:
            for scope in unit.scopes.scopes:
                for root in unit.attribute_mutations:
                    for bid in unit.bindings[scope].get(root, set()):
                        binding = self.bindings[bid]
                        if binding.kind == "module":
                            self.tainted_modules.add(binding.module)
        for unit in self.units:
            for scope, cfg in unit.cfgs.items():
                initial = {s.get_name(): frozenset({UNBOUND}) for s in scope.table.get_symbols() if s.is_parameter()}
                inputs, outputs = cfg.solve(initial)
                unit.final[scope] = inputs.get(cfg.exit, {})
        # Imported-member aliases can name modules too. Invalidate those exporters
        # after namespace bindings exist, including cross-file monkeypatches.
        for unit in self.units:
            for scope in unit.scopes.scopes:
                for name in unit.attribute_mutations:
                    for bid in unit.bindings[scope].get(name,()):
                        if self.bindings[bid].kind in {'module','member'}:
                            for target,_ in self.resolve_binding(bid):
                                self.tainted_modules.update(self.module_names_for_entity.get(target,()))
        self.build_class_index()
        for unit,source,node,targets in self.class_base_facts:
            for ordinal,(target,status) in enumerate(targets):
                self.emit(unit,source,target,'inherits',status,node,ordinal,
                    {'base':ast.unparse(node),'reason_codes':['STATIC_BASE_UNIQUE' if status=='exact' else 'UNSUPPORTED_ANALYSIS'],
                     'alternatives':[t for t,_ in targets]})
        self.mention_index=defaultdict(set)
        for eid,e in self.graph.entities.items():
            if e.kind in {'function','method','class'}:
                self.mention_index[e.qualified_name].add(eid);self.mention_index[e.qualified_name.rsplit('.',1)[-1]].add(eid)
        for unit in self.units:
            self.extract_relationships(unit)
            self.extract_code_documents(unit)
        self.extract_text_documents()
        self.graph.augment()
        return self.graph

    def inventory(self, repo, path, data):
        suffix = PurePosixPath(path).suffix
        parent = self.parent_directory(repo.repo_id, path)
        fid = entity_id(repo.repo_id, "file", path)
        if suffix in {".md", ".txt"}:
            self.graph.add(Entity(fid, repo.repo_id, "document", path, parent, sort="text", language="markdown" if suffix == ".md" else "text", rel_path=path,
                                  start_line=1, end_line=max(1, len(data.splitlines())), **self.flags(path)))
        else:
            self.graph.add(Entity(fid, repo.repo_id, "file", path, parent, rel_path=path, start_line=1, end_line=max(1, len(data.splitlines())),
                                  language="python" if suffix == ".py" else "javascript" if suffix in {".js", ".jsx"} else "typescript", **self.flags(path)))
        self.graph.analyses["source:" + fid] = dict(algorithm_version="source-bytes-v1", scope={"entity_id": fid},
                                                 result={"rel_path": path, "bytes_base64": base64.b64encode(data).decode("ascii")})
        if suffix != ".py":
            if suffix not in {".md", ".txt"}:
                self.fallback(repo, path, data, fid)
            return
        try:
            encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
            text = data.decode(encoding)
            tree = PARSES.parse(text,path)
            for value in ast.walk(tree):
                if isinstance(value,ast.Constant) and isinstance(value.value,str):value.value.encode('utf-8')
            scopes = ScopeIndex(tree, text, path)
        except (SyntaxError, UnicodeError, ValueError, RecursionError) as exc:
            self.failures[repo.repo_id].append(dict(rel_path=path, language="python", code=type(exc).__name__, message=str(exc)))
            return
        flags = self.flags(path, text)
        for key, val in flags.items():
            setattr(self.graph.entities[fid], key, val)
        modules = repo.modules(path)
        unit = Unit(repo, path, text, tree, scopes, fid, modules)
        self.units.append(unit)
        unit.owners[scopes.root] = fid
        for name in modules:
            self.module_map[name].append(unit)
            self.module_names_for_entity[fid].append(name)
            # Namespace package prefixes refer to real directory ownership entities.
            mp = name.split(".")
            parts = PurePosixPath(path).parts[:-1]
            for count in range(1, len(mp)):
                prefix = ".".join(mp[:count])
                matching = [eid for (rid, p), eid in self.dir_ids.items() if rid == repo.repo_id and p.split("/")[-count:] == mp[:count]]
                self.namespace_map[prefix].update(matching)
                for eid in matching:
                    if prefix not in self.module_names_for_entity[eid]:self.module_names_for_entity[eid].append(prefix)
        self.graph.analyses['declaration:'+fid]=dict(algorithm_version='declaration-v1',scope={'entity_id':fid},
            result={'signature':None,'docstring':ast.get_docstring(tree,clean=False)})
        duplicate = defaultdict(int)
        for scope in scopes.scopes:
            self.unit_for_scope[scope] = unit
            if scope is scopes.root:
                continue
            node = scope.node
            parent_scope = scope.parent
            assert parent_scope is not None
            owner = unit.owners[parent_scope]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                name = "<lambda>" if isinstance(node, ast.Lambda) else node.name
                kind = "class" if isinstance(node, ast.ClassDef) else "method" if isinstance(parent_scope.node, ast.ClassDef) else "function"
                signature = ast.dump(node.args, include_attributes=False) if hasattr(node, "args") else ""
                key = (owner, name, kind, signature)
                ordinal = duplicate[key]
                duplicate[key] += 1
                qualified = self.graph.entities[owner].qualified_name + "." + name + (f"#{ordinal}" if ordinal else "")
                eid = entity_id(repo.repo_id, path, qualified, kind, signature, ordinal)
                self.graph.add(Entity(eid, repo.repo_id, kind, qualified, owner, rel_path=path, start_line=node.lineno,
                                      end_line=node.end_lineno, **flags))
                unit.owners[scope] = eid
                self.definition_nodes[eid] = node
                self.entity_units[eid] = unit
                header=('class '+name+('('+', '.join(ast.unparse(b) for b in node.bases)+')' if node.bases else '') if isinstance(node,ast.ClassDef) else
                        ('async def ' if isinstance(node,ast.AsyncFunctionDef) else 'def ')+name+'('+ast.unparse(node.args)+')'+(' -> '+ast.unparse(node.returns) if getattr(node,'returns',None) else ''))
                self.graph.analyses['declaration:'+eid]=dict(algorithm_version='declaration-v1',scope={'entity_id':eid},
                    result={'signature':header,'docstring':None if isinstance(node,ast.Lambda) else ast.get_docstring(node,clean=False)})
                if kind in {"function", "method"}:
                    try:
                        if eid in self.normal_forms:
                            body_hash,rep=self.normal_forms[eid];self.normal_reuse+=1
                        else:body_hash, rep = normalized_ast(node, scopes)
                        self.graph.entities[eid].ast_body_hash = body_hash
                        self.graph.analyses["norm:" + eid] = dict(algorithm_version="py-ast-v1", scope={"entity_id": eid},
                                                                 result={"representation": rep, "grammar": f"{sys.version_info.major}.{sys.version_info.minor}"})
                    except (ValueError, RecursionError) as exc:
                        self.graph.analyses["norm-error:" + eid] = dict(algorithm_version="py-ast-v1", scope={"entity_id": eid}, result={"error": str(exc)})
            else:
                # Comprehensions are lexical scopes, not invented source-level functions.
                unit.owners[scope] = owner

    def absolute_module(self, unit, node):
        if not isinstance(node, ast.ImportFrom) or node.level == 0:
            return getattr(node, "module", None) or ""
        module = unit.modules[0] if unit.modules else ""
        package = module if unit.path.endswith("/__init__.py") or unit.path == "__init__.py" else module.rpartition(".")[0]
        parts = package.split(".") if package else []
        if node.level > len(parts):
            return "!invalid-relative"
        base = parts[:len(parts) - node.level + 1]
        return ".".join(base + ([node.module] if node.module else []))

    def index_bindings(self, unit):
        for scope in unit.scopes.scopes:
            for node in scope.nodes:
                if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                    symbol = scope.symbol(node.id)
                    if scope is not unit.scopes.root and symbol and symbol.is_global():
                        unit.global_mutations.add(node.id)
                entries = []
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    entries = [(node.name, "definition", unit.owners[unit.scopes.owner[node]], None, None)]
                elif isinstance(node, ast.Import):
                    entries = [(a.asname or a.name.split(".")[0], "module", None, a.name if a.asname else a.name.split(".")[0], None) for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    entries = [(a.asname or a.name, "member", None, self.absolute_module(unit, node), a.name) for a in node.names if a.name != "*"]
                else:
                    names = []
                    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.Delete)):
                        targets = node.targets if isinstance(node, (ast.Assign,ast.Delete)) else [node.target]
                        names = [n for t in targets for n in target_names(t)]
                        for t in targets:
                            for attr in ast.walk(t):
                                if isinstance(attr, ast.Attribute):
                                    root = attr
                                    while isinstance(root, ast.Attribute):
                                        root = root.value
                                    if isinstance(root, ast.Name):
                                        unit.attribute_mutations.add(root.id)
                    elif isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'setattr','delattr'} and node.args:
                        root=node.args[0]
                        while isinstance(root,ast.Attribute):root=root.value
                        if isinstance(root,ast.Name):unit.attribute_mutations.add(root.id)
                    elif isinstance(node, (ast.For, ast.AsyncFor)):
                        names = target_names(node.target)
                    elif isinstance(node, (ast.With, ast.AsyncWith)):
                        names = [n for i in node.items if i.optional_vars for n in target_names(i.optional_vars)]
                    elif isinstance(node, ast.ExceptHandler) and node.name:
                        names = [node.name]
                    elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                        names = [node.name]
                    elif isinstance(node, ast.MatchMapping) and node.rest:
                        names = [node.rest]
                    entries = [(name, "unknown", None, None, None) for name in names]
                for name, kind, target, module, member in entries:
                    bid = digest(unit.repo.repo_id, unit.path,
                                 [scope.table.get_name(), scope.table.get_lineno(), unit.scopes.scopes.index(scope)],
                                 type(node).__name__, getattr(node, "lineno", 0), getattr(node, "col_offset", 0), name)
                    self.bindings[bid] = Binding(bid, name, kind, scope, target, module, member)
                    self.binding_lines[bid] = getattr(node,'lineno',0)
                    self.binding_ids[(id(node), name)] = bid
                    unit.bindings[scope][name].add(bid)
                    symbol = scope.symbol(name)
                    if scope is not unit.scopes.root and symbol and symbol.is_global():
                        unit.global_mutations.add(name)
            if isinstance(scope.node, ast.Lambda):
                body = [ast.Expr(value=scope.node.body)]
            elif isinstance(scope.node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
                body = [ast.Expr(value=scope.node)]
            else:
                body = scope.node.body
            unit.cfgs[scope] = CFG(body, self.binding_ids)
        # Known module-initialization calls invalidate proofs that depend on
        # declarations not yet executed; propagate through local named helpers.
        def named_functions(name,where=None):
            where=where or unit.scopes.root
            symbol=where.symbol(name)
            if symbol and symbol.is_global():where=unit.scopes.root
            elif symbol and symbol.is_free():
                where=where.parent
                while where and (where.table.get_type()=='class' or name not in unit.bindings[where]):where=where.parent
            return [self.bindings[b].target for b in (unit.bindings[where].get(name,()) if where else ())
                    if self.bindings[b].kind=='definition' and isinstance(self.definition_nodes[self.bindings[b].target],(ast.FunctionDef,ast.AsyncFunctionDef))]
        for node in ast.walk(unit.tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and unit.scopes.by_node[node] is unit.scopes.root:
                for eid in named_functions(node.func.id):unit.early_functions[eid]=min(node.lineno,unit.early_functions.get(eid,node.lineno))
        changed=True
        while changed:
            changed=False
            for scope in unit.scopes.scopes:
                time=unit.early_functions.get(unit.owners[scope])
                if time is None:continue
                for node in scope.nodes:
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                        for eid in named_functions(node.func.id,scope):
                            if time<unit.early_functions.get(eid,float('inf')):unit.early_functions[eid]=time;changed=True

    def lookup(self, unit, scope, name, state):
        if name in state:
            return state[name]
        if scope is unit.scopes.root:
            return frozenset({UNBOUND})
        symbol = scope.symbol(name)
        if symbol and (symbol.is_parameter() or symbol.is_local() and scope is not unit.scopes.root):
            return frozenset({UNBOUND})
        if symbol and symbol.is_free():
            parent = scope.parent
            while parent:
                if parent.table.get_type() != "class" and name in unit.bindings[parent]:
                    # Captured cells can change after closure creation; retain candidates.
                    return frozenset(unit.bindings[parent][name] | {UNBOUND})
                parent = parent.parent
        stable = unit.final.get(unit.scopes.root, {}).get(name, frozenset({UNBOUND}))
        all_bindings = unit.bindings[unit.scopes.root].get(name, set())
        initialization=unit.early_functions.get(unit.owners[scope])
        if initialization is not None and any(self.binding_lines[b]>=initialization for b in all_bindings):
            return frozenset(set(stable)|all_bindings|{UNBOUND})
        if len(all_bindings) != 1 or name in unit.global_mutations:
            return frozenset(set(stable) | all_bindings | {UNBOUND})
        if any(s.reflective for s in unit.scopes.scopes):
            return frozenset(set(stable) | {UNBOUND})
        if any(module in self.tainted_modules for module in unit.modules):
            return frozenset(set(stable) | {UNBOUND})
        return stable

    def resolve_binding(self, bid, seen=None):
        seen = set() if seen is None else seen
        if bid == UNBOUND or bid in seen:
            return []
        seen = seen | {bid}
        b = self.bindings[bid]
        if b.kind == "definition":
            node = self.definition_nodes[b.target]
            return [(b.target, "candidate" if getattr(node, "decorator_list", []) else "exact")]
        if b.kind == "module":
            return [(u.file_id, "exact" if len(self.module_map[b.module]) == 1 else "candidate") for u in self.module_map.get(b.module, [])] or [(eid, "exact" if len(self.namespace_map[b.module]) == 1 else "candidate") for eid in sorted(self.namespace_map.get(b.module, set()))]
        if b.kind == "member":
            return self.resolve_member(b.module, [b.member], seen)
        return []

    def resolve_member(self, module, members, seen):
        guard=('module',module,tuple(members))
        if guard in seen:return []
        seen=seen|{guard}
        if not members:
            return [(u.file_id, "exact" if len(self.module_map[module]) == 1 else "candidate") for u in self.module_map.get(module, [])]
        result = [];export_declared=False
        for unit in self.module_map.get(module, []):
            root = unit.scopes.root
            # `from . import utils` inside pkg/__init__ is Python's from-list
            # submodule loading, not a concrete export that masks pkg.utils.
            declared=unit.bindings[root].get(members[0],set())
            export_declared |= any(not (self.bindings[b].kind=='member' and self.bindings[b].module==module and
                                        self.bindings[b].member==members[0]) for b in declared)
            bids = unit.final.get(root, {}).get(members[0], frozenset({UNBOUND}))
            ambiguous = (len(bids) != 1 or UNBOUND in bids or len(self.module_map[module]) != 1 or
                         len(unit.bindings[root].get(members[0], set())) != 1 or members[0] in unit.global_mutations or
                         module in self.tainted_modules)
            for bid in bids:
                for target, status in self.resolve_binding(bid, seen):
                    if len(members) == 1:
                        result.append((target, "candidate" if ambiguous else status))
                    else:
                        for eid,child_status in self.target_members(target,members[1:],seen):
                            result.append((eid,'candidate' if ambiguous or status=='candidate' else child_status))
        if result or export_declared:
            return result
        submodule = module + "." + members[0] if module else members[0]
        if submodule in self.module_map or submodule in self.namespace_map:
            if len(members) > 1:
                return self.resolve_member(submodule, members[1:], seen)
            return [(u.file_id, "exact" if len(self.module_map[submodule]) == 1 else "candidate") for u in self.module_map.get(submodule, [])] or [(eid, "exact" if len(self.namespace_map[submodule]) == 1 else "candidate") for eid in sorted(self.namespace_map[submodule])]
        return []

    def external(self, unit, scope, label, node):
        eid = entity_id(unit.repo.repo_id, unit.path, unit.owners[scope], "unresolved", label,
                        getattr(node, "lineno", 1), getattr(node, "col_offset", 0))
        if eid not in self.graph.entities:
            self.graph.add(Entity(eid, unit.repo.repo_id, "external_symbol", label, self.repo_roots[unit.repo.repo_id],
                                  sort="external", is_external=1, rel_path=unit.path,
                                  start_line=getattr(node, "lineno", 1), end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                                  **self.flags(unit.path)))
        return eid

    def emit(self, unit, source, target, subtype, status, node, ordinal=0, details=None):
        key = digest(EXTRACTOR_VERSION, unit.repo.repo_id, unit.path, source, subtype,
                     getattr(node, "lineno", 1), getattr(node, "col_offset", 0),
                     getattr(node, "end_lineno", 1), getattr(node, "end_col_offset", 0), ordinal, target)
        rid = "rel:" + key
        self.graph.relationships[rid] = Relationship(rid, source, target, source, target, subtype, status, key)
        category = {"exact": "ast_exact", "candidate": "static_candidate", "unresolved": "unresolved"}[status]
        ev = "evidence:" + digest(rid, category)
        claim=static_details(unit,source,subtype,node,details,status)
        validate_details(claim)
        self.graph.evidence[ev] = Evidence(ev, rid, category, unit.repo.repo_id, unit.repo.revision, unit.path,
                                        getattr(node, "lineno", 1), getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                                        canonical(claim))

    def call(self, unit, scope, node, state, force_uncertain=False):
        if node in self.seen_calls:
            return
        self.seen_calls.add(node)
        expression = node.func
        parts = []
        while isinstance(expression, ast.Attribute):
            parts.insert(0, expression.attr)
            expression = expression.value
        targets = []
        bids=frozenset()
        uncertain = force_uncertain or scope.reflective
        reasons=[]
        if force_uncertain:reasons.append('UNREACHABLE_SYNTAX')
        if scope.reflective:reasons.append('REFLECTIVE_CALL')
        if isinstance(expression, ast.Name):
            bids = self.lookup(unit, scope, expression.id, state)
            uncertain |= len(bids) != 1 or UNBOUND in bids or expression.id in unit.attribute_mutations
            if len(bids)!=1 or UNBOUND in bids:reasons.append('CFG_BRANCH_REBOUND')
            if expression.id in unit.global_mutations:reasons.append('GLOBAL_BINDING_MUTATED')
            if scope.symbol(expression.id) and scope.symbol(expression.id).is_free():reasons.append('CLOSURE_CELL_MUTABLE')
            if expression.id in unit.attribute_mutations:reasons.append('DYNAMIC_ATTR_DISPATCH')
            for bid in sorted(bids):
                if bid == UNBOUND:
                    continue
                binding = self.bindings[bid]
                if parts and binding.kind == "module":
                    targets.extend(self.resolve_member(binding.module, parts, {bid}))
                elif parts and binding.kind == 'member':
                    targets.extend(self.resolve_member(binding.module,[binding.member,*parts],{bid}))
                elif parts and binding.kind == 'definition':
                    targets.extend(self.target_members(binding.target,parts,{bid}))
                elif not parts:
                    targets.extend(self.resolve_binding(bid) if binding.kind != "module" else [])
                if binding.module and len(self.module_map.get(binding.module,[]))>1:reasons.append('AMBIGUOUS_MODULE_ROOT')
            if not targets:
                targets=self.receiver_targets(unit,scope,expression,parts)
                if targets:reasons=['POLYMORPHIC_MRO_CANDIDATE',*reasons]
        label = ast.unparse(node.func)
        source = unit.owners[scope]
        if not targets:
            targets = [(self.external(unit, scope, label, node), "unresolved")]
            reasons=[self.unresolved_reason(unit,scope,expression,parts),*reasons]
        elif uncertain:
            targets = [(target, "candidate") for target, _ in targets]
        targets = [(target, "candidate" if status == "exact" and self.graph.entities[target].kind not in {"function", "method", "class"} else status)
                   for target, status in targets]
        if isinstance(scope.node, ast.ClassDef):
            targets = [(target, "candidate" if self.definition_nodes.get(target) and self.definition_nodes[target].lineno > scope.node.lineno else status)
                       for target, status in targets]
        mro_classes=set()
        if scope.parent and isinstance(scope.parent.node,ast.ClassDef):mro_classes.add(unit.owners[scope.parent])
        for target,_ in targets:
            e=self.graph.entities[target]
            owner=target if e.kind=='class' else e.parent_id
            if owner in self.class_bases:mro_classes.add(owner)
        mro_provenance=[dict(entity_id=eid,analysis_id='mro:'+eid,algorithm_version='c3-static-v1',
                            mro=self.mros.get(eid),status='supported' if eid in self.mros else 'unsupported_or_inconsistent',
                            dispatch_world='open') for eid in sorted(mro_classes)]
        for ordinal, (target, status) in enumerate(sorted(set(targets))):
            target_node=self.definition_nodes.get(target)
            codes=list(reasons)
            if target_node and getattr(target_node,'decorator_list',[]):codes.insert(0,'DECORATOR_WRAPPED_BINDING')
            if status=='candidate' and not codes:codes=['POLYMORPHIC_MRO_CANDIDATE' if parts else 'CFG_BRANCH_REBOUND']
            if status=='exact':codes=['UNAMBIGUOUS_IMPORT_MEMBER' if parts or any(self.bindings[b].kind=='member' for b in bids if b!=UNBOUND) else 'LEXICAL_UNIQUE_BINDING']
            self.emit(unit, source, target, "calls", status, node, ordinal,
                      {"callee": label, "certainty_limited": bool(uncertain), 'reason_codes':codes,
                       'binding_state':[{'name':self.bindings[b].name,'kind':self.bindings[b].kind,
                                         'target':self.bindings[b].target,'module':self.bindings[b].module}
                                        for b in sorted(bids) if b!=UNBOUND],
                       'binding_may_be_unbound':UNBOUND in bids,
                       'mro_provenance':mro_provenance,
                       'alternatives':sorted({t for t,_ in targets})})

    def unresolved_reason(self,unit,scope,expression,parts):
        import builtins
        if any(isinstance(n,ast.ImportFrom) and any(a.name=='*' for a in n.names) for s in unit.scopes.scopes for n in s.nodes):return 'DYNAMIC_EXPORT_STAR'
        if scope.reflective:return 'REFLECTIVE_CALL'
        if isinstance(expression,ast.Name):
            for s in (scope,unit.scopes.root):
                for bid in unit.bindings[s].get(expression.id,()):
                    b=self.bindings[bid]
                    if b.module=='!invalid-relative' or b.module and b.module.startswith('!invalid-relative'):return 'MISSING_RELATIVE_IMPORT'
                    if b.module and b.module not in self.module_map and b.module not in self.namespace_map:return 'EXTERNAL_PACKAGE_UNINDEXED'
                    if b.kind=='member':return 'UNRESOLVED_IMPORT_MEMBER'
            sym=scope.symbol(expression.id)
            if not parts and hasattr(builtins,expression.id) and sym and sym.is_global() and not unit.bindings[unit.scopes.root].get(expression.id):return 'BUILTIN_SYMBOL'
        return 'DYNAMIC_ATTR_DISPATCH' if parts or not isinstance(expression,ast.Name) else 'UNSUPPORTED_ANALYSIS'

    def evaluate_calls(self,unit,scope,node,state):
        # Calls see the binding state when the callee is evaluated; argument writes
        # cannot retroactively change an already-loaded callee object.
        def visit(n):
            if unit.scopes.by_node.get(n) is not scope:return
            if isinstance(n,ast.NamedExpr):
                visit(n.value)
                for name in target_names(n.target):state[name]=frozenset({UNBOUND})
                return
            if isinstance(n,ast.Call):
                visit(n.func);callee_state=dict(state)
                for a in [*n.args,*(k.value for k in n.keywords)]:visit(a)
                self.call(unit,scope,n,callee_state);return
            for child in ast.iter_child_nodes(n):visit(child)
        visit(node)

    def extract_relationships(self, unit):
        for scope, cfg in unit.cfgs.items():
            initial = {s.get_name(): frozenset({UNBOUND}) for s in scope.table.get_symbols() if s.is_parameter()}
            for kind, node, state in cfg.event_states(initial):
                if kind == "import":
                    for ordinal, alias in enumerate(node.names):
                        local = alias.asname or (alias.name.split(".")[0] if isinstance(node, ast.Import) else alias.name)
                        bid = self.binding_ids.get((id(node), local))
                        targets = self.resolve_binding(bid) if bid else []
                        label = alias.name if isinstance(node, ast.Import) else self.absolute_module(unit, node) + "." + alias.name
                        if not targets:
                            targets = [(self.external(unit, scope, label, node), "unresolved")]
                        for target, status in sorted(set(targets)):
                            if status=='unresolved':
                                module=self.absolute_module(unit,node) if isinstance(node,ast.ImportFrom) else alias.name
                                reason=('DYNAMIC_EXPORT_STAR' if alias.name=='*' else 'MISSING_RELATIVE_IMPORT' if module=='!invalid-relative'
                                        else 'EXTERNAL_PACKAGE_UNINDEXED' if module not in self.module_map and module not in self.namespace_map
                                        else 'UNRESOLVED_IMPORT_MEMBER')
                            else:reason='UNAMBIGUOUS_IMPORT_MEMBER' if status=='exact' else 'AMBIGUOUS_MODULE_ROOT'
                            self.emit(unit, unit.owners[scope], target, "imports" if isinstance(node, ast.Import) else "imports_from", status, node, ordinal, {"import": label,'reason_codes':[reason],'alternatives':[t for t,_ in targets]})
                elif kind == "eval":
                    self.evaluate_calls(unit,scope,node,state)
        # Preserve statically present unreachable calls; never label them observed/exact.
        for node in ast.walk(unit.tree):
            if isinstance(node, ast.Call):
                scope = unit.scopes.by_node[node]
                self.call(unit, scope, node, {}, force_uncertain=True)

    def fragment(self, repo, path, parent, text, start, end, members, role="discusses"):
        fid = entity_id(repo.repo_id, path, "fragment", start, end, text)
        self.graph.add(Entity(fid, repo.repo_id, "fragment", path + f":{start}-{end}", parent, sort="text", language="text",
                              rel_path=path, start_line=start, end_line=end, **self.flags(path)))
        incidence = "incidence:" + digest(fid, role)
        for member in sorted(set(members)):
            self.graph.incidences.append(dict(incidence_id=incidence, fragment_id=fid, entity_id=member, role=role))
        tokens=set(re.findall(r'[A-Za-z_][A-Za-z0-9_.]*',text))
        associations={eid:('lexical_owner' if eid==parent else 'qualified_reference' if self.graph.entities[eid].qualified_name in tokens else
                          'ambiguous_short_name' if len(self.mention_index.get(self.graph.entities[eid].qualified_name.rsplit('.',1)[-1],()))>1 else 'short_name_mention') for eid in members}
        self.graph.analyses["text:" + fid] = dict(algorithm_version="documentary-v2", scope={"entity_id": fid}, result={"text": text,'associations':associations})
        return fid

    def mentions(self, text, default):
        tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", text))
        return {default} | {eid for token in tokens for eid in self.mention_index.get(token,())}

    def extract_code_documents(self, unit):
        for scope in unit.scopes.scopes:
            node = scope.node
            if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                doc = node.body[0]
                owner = unit.owners[scope]
                fid=self.fragment(unit.repo, unit.path, owner, doc.value.value, doc.lineno, doc.end_lineno,
                                  self.mentions(doc.value.value, owner), "documents")
                from .documents import parse_document,VERSION
                parsed=parse_document(doc.value.value.encode('utf-8'),unit.path+':'+str(doc.lineno)+'.md');parsed.pop('blocks')
                parsed['sections'][0]['fragment_ids']=[fid]
                self.graph.analyses['document:'+fid]=dict(algorithm_version=VERSION,scope={'entity_id':fid},result={
                    'document_id':fid,'coordinate_space':'decoded_docstring_value','source_fragment_id':fid,
                    'literal_start_line':doc.lineno,'literal_end_line':doc.end_lineno,**parsed})
        try:
            for token in tokenize.generate_tokens(io.StringIO(unit.text).readline):
                if token.type != tokenize.COMMENT:
                    continue
                # Attach to the narrowest containing entity; references form a hyperedge.
                candidates = [e for e in self.graph.entities.values() if e.repo_id == unit.repo.repo_id and e.rel_path == unit.path and
                              e.kind in {"file", "function", "method", "class"} and e.start_line <= token.start[0] <= e.end_line]
                owner = min(candidates, key=lambda e: (e.end_line - e.start_line, e.entity_id)).entity_id if candidates else unit.file_id
                self.fragment(unit.repo, unit.path, owner, token.string, token.start[0], token.end[0], self.mentions(token.string, owner), "rationale_for")
        except tokenize.TokenError:
            pass  # Syntax parsing already records invalid inputs; token streams can end in comments.

    def extract_text_documents(self):
        from .documents import parse_document,VERSION
        for repo in self.repositories:
            for path, data in sorted(repo.files.items()):
                if PurePosixPath(path).suffix not in {".md", ".txt"}:
                    continue
                try:
                    parsed = parse_document(data,path)
                except UnicodeError as exc:
                    self.failures[repo.repo_id].append(dict(rel_path=path, language="text", code="UnicodeError", message=str(exc)))
                    continue
                fid = entity_id(repo.repo_id, "file", path)
                sections={s['section_id']:s for s in parsed['sections']}
                for block in parsed.pop('blocks'):
                    fragment=self.fragment(repo,path,fid,block['text'],block['start_line'],block['end_line'],self.mentions(block['text'],fid))
                    sections[block['section_id']]['fragment_ids'].append(fragment)
                    self.graph.analyses['text:'+fragment]['result'].update(fragment_kind=block['kind'],section_id=block['section_id'])
                self.graph.analyses['document:'+fid]=dict(algorithm_version=VERSION,scope={'entity_id':fid},result={'document_id':fid,**parsed})

    def fallback(self, repo, path, data, fid):
        from .treesitter import extract_fallback
        try:
            extract_fallback(self.graph, repo, path, data, fid)
        except (ImportError, ValueError) as exc:
            self.failures[repo.repo_id].append(dict(rel_path=path, language=self.graph.entities[fid].language,
                                                   code="FallbackUnavailable" if isinstance(exc, ImportError) else "FallbackParseError", message=str(exc)))
