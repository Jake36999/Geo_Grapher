"""py-ast-v1 structural normalisation; never execute the normalised result."""
from __future__ import annotations

import ast
import hashlib
import sys

from .model import canonical
from .scopes import ScopeIndex


def normalized_ast(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, scopes: ScopeIndex) -> tuple[str, str]:
    maps = {s: scopes.bindings(s) for s in scopes.scopes}

    def constant(value):
        if value is Ellipsis:
            return ["ellipsis", "Ellipsis"]
        if isinstance(value, bool) or value is None or isinstance(value, str):
            return [type(value).__name__, value]
        if isinstance(value, int):
            return ["int", str(value)]
        if isinstance(value, float):
            return ["float", value.hex()]
        if isinstance(value, complex):
            return ["complex", [value.real.hex(), value.imag.hex()]]
        if isinstance(value, bytes):
            return ["bytes", value.hex()]
        raise ValueError("Unsupported AST constant")

    def encode(value):
        if isinstance(value, list):
            return [encode(x) for x in value]
        if not isinstance(value, ast.AST):
            return value
        scope = scopes.by_node.get(value)
        renames = maps.get(scope, {})
        fields = []
        for name, item in ast.iter_fields(value):
            if name in {"type_comment", "type_ignores"}:
                continue
            if isinstance(value, ast.Constant) and name == "value":
                item = constant(item)
            elif value is node and name == "name":
                item = "__subject__"
            elif isinstance(value, ast.Name) and name == "id":
                item = renames.get(item, item)
            elif ((isinstance(value, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and name == "name") or
                  (isinstance(value, ast.MatchMapping) and name == "rest")) and item:
                item = renames.get(item, item)
            elif name == "body" and isinstance(value, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and isinstance(item, list):
                if item and isinstance(item[0], ast.Expr) and isinstance(item[0].value, ast.Constant) and isinstance(item[0].value.value, str):
                    item = item[1:]
            fields.append([name, encode(item)])
        return [type(value).__name__, fields]

    representation = canonical(["py-ast-v1", f"{sys.version_info.major}.{sys.version_info.minor}", encode(node)])
    return hashlib.sha256(representation.encode("utf-8")).hexdigest(), representation
