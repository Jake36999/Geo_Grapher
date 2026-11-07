"""Join AST lexical scopes to CPython symbol tables, including hidden scopes."""
from __future__ import annotations

import ast
import symtable
from dataclasses import dataclass, field


@dataclass(eq=False)
class Scope:
    node: ast.AST
    table: symtable.SymbolTable
    parent: Scope | None
    children: list[Scope] = field(default_factory=list)
    nodes: list[ast.AST] = field(default_factory=list)
    protected: set[str] = field(default_factory=set)
    reflective: bool = False
    complex_flow: bool = False

    def symbol(self, name):
        try:
            return self.table.lookup(name)
        except KeyError:
            return None


class ScopeIndex:
    def __init__(self, tree: ast.Module, text: str, filename: str):
        self.root = Scope(tree, symtable.symtable(text, filename, "exec"), None)
        self.scopes = [self.root]
        self.by_node: dict[ast.AST, Scope] = {}
        self.owner: dict[ast.AST, Scope] = {tree: self.root}
        self.used_tables: set[int] = set()
        self.visit(tree, self.root)
        for scope in self.scopes:
            self._protect(scope)
        # A captured binding cannot be alpha-renamed independently of its closure.
        for scope in self.scopes:
            for symbol in scope.table.get_symbols():
                if symbol.is_free():
                    p = scope.parent
                    while p:
                        candidate = p.symbol(symbol.get_name())
                        if candidate and candidate.is_local() and p.table.get_type() != "class":
                            p.protected.add(symbol.get_name())
                            break
                        p = p.parent
        for scope in self.scopes:
            p = scope.parent
            while p:
                if p.reflective:
                    scope.reflective = True
                p = p.parent

    def _new(self, node, parent, name, kind="function"):
        candidates = [t for t in parent.table.get_children() if t.get_id() not in self.used_tables and
                      t.get_name() == name and t.get_type() == kind and t.get_lineno() == node.lineno]
        if not candidates:
            raise ValueError(f"Cannot join symtable scope {name}:{node.lineno}")
        table = candidates[0]
        self.used_tables.add(table.get_id())
        scope = Scope(node, table, parent)
        parent.children.append(scope)
        self.scopes.append(scope)
        self.owner[node] = scope
        return scope

    def visit(self, node, scope):
        self.by_node[node] = scope
        scope.nodes.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            name = "lambda" if isinstance(node, ast.Lambda) else node.name
            inner = self._new(node, scope, name)
            for decorator in getattr(node, "decorator_list", []):
                self.visit(decorator, scope)
            args = node.args
            for default in [*args.defaults, *(x for x in args.kw_defaults if x is not None)]:
                self.visit(default, scope)
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs, *([args.vararg] if args.vararg else []), *([args.kwarg] if args.kwarg else [])]:
                self.by_node[arg] = inner
                inner.nodes.append(arg)
                if arg.annotation:
                    self.visit(arg.annotation, scope)
            if getattr(node, "returns", None):
                self.visit(node.returns, scope)
            for child in node.body if not isinstance(node, ast.Lambda) else [node.body]:
                self.visit(child, inner)
            return
        if isinstance(node, ast.ClassDef):
            inner = self._new(node, scope, node.name, "class")
            for child in [*node.bases, *node.keywords, *node.decorator_list]:
                self.visit(child, scope)
            for child in node.body:
                self.visit(child, inner)
            return
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            name = {ast.ListComp: "listcomp", ast.SetComp: "setcomp", ast.DictComp: "dictcomp", ast.GeneratorExp: "genexpr"}[type(node)]
            self.visit(node.generators[0].iter, scope)
            inner = self._new(node, scope, name)
            for i, gen in enumerate(node.generators):
                self.visit(gen.target, inner)
                if i:
                    self.visit(gen.iter, inner)
                for condition in gen.ifs:
                    self.visit(condition, inner)
            for key in ("elt", "key", "value"):
                child = getattr(node, key, None)
                if child is not None:
                    self.visit(child, inner)
            return
        for child in ast.iter_child_nodes(node):
            self.visit(child, scope)

    def _protect(self, scope):
        reflection = {"locals", "globals", "vars", "eval", "exec", "__dict__"}
        for node in scope.nodes:
            if isinstance(node, ast.Name) and node.id in reflection or isinstance(node, ast.Attribute) and node.attr == "__dict__":
                scope.reflective = True
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                scope.reflective = True
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scope.protected.add(node.name)
            if isinstance(node, ast.Call):
                scope.protected.update(n.id for n in ast.walk(node.func) if isinstance(n, ast.Name))
            if isinstance(node, (ast.Try, ast.TryStar, ast.Match, ast.NamedExpr, ast.Await, ast.Yield, ast.YieldFrom)):
                # Diagnostic only: certainty is determined per binding by the CFG.
                scope.complex_flow = True
            if isinstance(node, ast.arg) and node.annotation:
                scope.protected.update(n.id for n in ast.walk(node.annotation) if isinstance(n, ast.Name))
            if isinstance(node, ast.AnnAssign):
                scope.protected.update(n.id for n in ast.walk(node.annotation) if isinstance(n, ast.Name))
            if isinstance(node, ast.ExceptHandler) and node.type:
                scope.protected.update(n.id for n in ast.walk(node.type) if isinstance(n, ast.Name))
            if isinstance(node, ast.MatchClass):
                scope.protected.update(n.id for n in ast.walk(node.cls) if isinstance(n, ast.Name))

    def bindings(self, scope: Scope) -> dict[str, str]:
        if scope.reflective:
            return {}
        result = {}
        for node in scope.nodes:
            names = []
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                names = [node.id]
            elif isinstance(node, ast.ExceptHandler) and node.name:
                names = [node.name]
            elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
                names = [node.name]
            elif isinstance(node, ast.MatchMapping) and node.rest:
                names = [node.rest]
            for name in names:
                symbol = scope.symbol(name)
                if symbol and symbol.is_local() and not (symbol.is_parameter() or symbol.is_imported() or symbol.is_global() or symbol.is_nonlocal() or symbol.is_free()) and name not in scope.protected and name not in result:
                    result[name] = "v" + str(len(result))
        return result
