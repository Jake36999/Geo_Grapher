"""entity-fingerprint-v1: per-entity hashes used by cross-snapshot drift and diff (master G2)."""
from __future__ import annotations

import ast
import base64
import copy
import hashlib
import json
from collections import defaultdict

from .model import Graph, canonical

ALGORITHM_VERSION = "entity-fingerprint-v1"
FINGERPRINT_KINDS = frozenset({"function", "method", "class"})
FIELDS = ("span_sha256", "ast_body_hash", "signature_hash", "ts_guard_hash", "exact_out_edges_hash", "wl_3hop_hash")
_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _sha(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def signature_hash(header: str, decorators: list[str]) -> str:
    return _sha(["sig-v1", header, list(decorators)])


def ts_guard_hash(clauses: list[list]) -> str:
    return _sha(["guard-v1", clauses])


def span_sha256(raw: bytes, start_line: int, end_line: int) -> str:
    lines = raw.splitlines(keepends=True)
    return hashlib.sha256(b"".join(lines[start_line - 1:end_line])).hexdigest()


def local_names(scope) -> set[str]:
    """Names bound in the entity's own scope (parameters included; free/global/nonlocal excluded)."""
    names = set()
    for symbol in scope.table.get_symbols():
        if symbol.is_local() and not (symbol.is_global() or symbol.is_nonlocal() or symbol.is_free()):
            names.add(symbol.get_name())
    return names


def _guards(node, lines):
    """Yield (clause_kind, expression) for one node."""
    if isinstance(node, ast.If):
        line = lines[node.lineno - 1] if lines and 0 < node.lineno <= len(lines) else ""
        yield ("elif" if line.lstrip().startswith("elif") else "if"), node.test
    elif isinstance(node, ast.While):
        yield "while", node.test
    elif isinstance(node, (ast.For, ast.AsyncFor)):
        yield "for_iter", node.iter
    elif isinstance(node, ast.Assert):
        yield "assert", node.test
    elif isinstance(node, ast.match_case):
        if node.guard is not None:
            yield "match_case_guard", node.guard
    elif isinstance(node, ast.IfExp):
        yield "ifexp", node.test
    elif isinstance(node, ast.comprehension):
        for test in node.ifs:
            yield "comp_if", test
    elif isinstance(node, ast.ExceptHandler):
        if node.type is not None:
            yield "except_type", node.type
    elif isinstance(node, ast.withitem):
        yield "with_item", node.context_expr


def guard_clauses(node, local_names: set[str], lines: list[str] | None = None) -> list[list]:
    """Pre-order guard clauses of the entity's own body: [kind, ordinal, guard_repr]."""
    found: list[tuple[str, ast.AST]] = []

    def walk(current):
        found.extend(_guards(current, lines))
        for child in ast.iter_child_nodes(current):
            if not isinstance(child, _NESTED):
                walk(child)

    body = node.body if isinstance(node.body, list) else [node.body]
    for statement in body:
        if not isinstance(statement, _NESTED):
            walk(statement)
    renames: dict[str, str] = {}

    def rename(current):
        if isinstance(current, ast.Name) and current.id in local_names:
            current.id = renames.setdefault(current.id, "v" + str(len(renames)))
        for child in ast.iter_child_nodes(current):
            rename(child)

    ordinals: dict[str, int] = defaultdict(int)
    clauses = []
    for kind, expression in found:
        expression = copy.deepcopy(expression)
        rename(expression)
        clauses.append([kind, ordinals[kind], ast.dump(expression, annotate_fields=False, include_attributes=False)])
        ordinals[kind] += 1
    return clauses


def _reason_codes(evidence_by_rel, relationship_id: str) -> list[str]:
    reasons = set()
    for evidence in evidence_by_rel.get(relationship_id, ()):
        try:
            details = json.loads(evidence.details_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(details, dict):
            continue
        if isinstance(details.get("reason_code"), str):
            reasons.add(details["reason_code"])
        extra = details.get("additional_reason_codes")
        if isinstance(extra, list):
            reasons.update(r for r in extra if isinstance(r, str))
    return sorted(reasons)


def _edge_index(graph: Graph):
    out = defaultdict(list)
    for rid in sorted(graph.relationships):
        r = graph.relationships[rid]
        if r.family == "static" and r.resolution_status == "exact":
            out[r.source_subject_id].append(r)
    evidence = defaultdict(list)
    for evid in sorted(graph.evidence):
        e = graph.evidence[evid]
        evidence[e.relationship_id].append(e)
    return out, evidence


def _out_hash(index, entity_id):
    out, evidence = index
    rows = sorted([r.target_subject_id, r.subtype, _reason_codes(evidence, r.relationship_id)] for r in out.get(entity_id, ()))
    return _sha(["out-v1", rows])


def exact_out_edges_hash(graph: Graph, entity_id: str) -> str:
    return _out_hash(_edge_index(graph), entity_id)


def complete_fingerprints(graph: Graph) -> None:
    """Fill the graph-derived fields of every fingerprint; idempotent, runs on ingest and merge."""
    if not graph.fingerprints:
        return
    index = _edge_index(graph)
    sources: dict[tuple[str, str], str] = {}
    for aid in sorted(graph.analyses):
        record = graph.analyses[aid]
        if record["algorithm_version"] == "source-bytes-v1":
            fid = record["scope"]["entity_id"]
            if fid in graph.entities:
                sources[(graph.entities[fid].repo_id, record["result"]["rel_path"])] = aid
    cache: dict[str, bytes] = {}
    for eid in sorted(graph.fingerprints):
        entity = graph.entities.get(eid)
        if entity is None or entity.kind not in FINGERPRINT_KINDS:
            continue
        row = graph.fingerprints[eid]
        aid = sources.get((entity.repo_id, entity.rel_path))
        span = None
        if aid is not None and entity.start_line is not None and entity.end_line is not None:
            if aid not in cache:
                cache[aid] = base64.b64decode(graph.analyses[aid]["result"]["bytes_base64"])
            span = span_sha256(cache[aid], entity.start_line, entity.end_line)
        row["span_sha256"] = span
        row["ast_body_hash"] = entity.ast_body_hash
        row["exact_out_edges_hash"] = _out_hash(index, eid)
        row["wl_3hop_hash"] = entity.wl_3hop_hash
