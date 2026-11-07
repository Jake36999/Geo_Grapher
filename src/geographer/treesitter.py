"""Extensible syntactic fallback. Facts remain candidates without a language resolver.

The local Graphify adapter design was inspected as a reference; this implementation
does not import its graph model or copy its label-based symbol resolution.
"""
from __future__ import annotations

from importlib import import_module, metadata
from pathlib import PurePosixPath, Path
import hashlib

from .model import Entity, Relationship, Evidence, canonical, digest, entity_id

ADAPTERS = {
    ".js": ("tree_sitter_javascript", "language", "javascript"),
    ".jsx": ("tree_sitter_javascript", "language", "javascript"),
    ".ts": ("tree_sitter_typescript", "language_typescript", "typescript"),
    ".tsx": ("tree_sitter_typescript", "language_tsx", "typescript"),
}


def extract_fallback(graph, repo, path, data, file_id):
    from tree_sitter import Language, Parser
    package, factory, language = ADAPTERS[PurePosixPath(path).suffix]
    grammar = import_module(package)
    parser = Parser(Language(getattr(grammar, factory)()))
    tree = parser.parse(data)
    if tree.root_node.has_error:
        raise ValueError("Tree-sitter reported syntax errors; no complete fallback facts published")
    graph.analyses["adapter:" + file_id] = dict(algorithm_version="tree-sitter-syntax-v1", scope={"entity_id": file_id},
        result={"adapter": package, "grammar_version": metadata.version(package.replace("_", "-")),
                "grammar_digest": digest(package, metadata.version(package.replace("_", "-")),
                    [(p.name, hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(Path(grammar.__file__).parent.iterdir())
                     if p.suffix in {".pyd", ".so", ".py"}]),
                "resolver_capability": "syntactic_candidate_only"})
    def text(node):
        return data[node.start_byte:node.end_byte].decode("utf-8")
    source_flags={key:getattr(graph.entities[file_id],key) for key in ('is_test','is_generated','is_vendor')}
    def walk(node, owner):
        new_owner = owner
        if node.type in {"function_declaration", "generator_function_declaration", "method_definition", "class_declaration"}:
            name = node.child_by_field_name("name")
            if name:
                kind = "class" if node.type == "class_declaration" else "method" if node.type == "method_definition" else "function"
                eid = entity_id(repo.repo_id, path, kind, text(name), node.start_byte)
                graph.add(Entity(eid, repo.repo_id, kind, graph.entities[owner].qualified_name + "." + text(name), owner,
                                 language=language, rel_path=path, start_line=node.start_point.row+1, end_line=node.end_point.row+1,**source_flags))
                new_owner = eid
        if node.type in {"call_expression", "new_expression", "import_statement"}:
            target_node = node.child_by_field_name("function") or node.child_by_field_name("constructor") or node.child_by_field_name("source")
            label = text(target_node) if target_node else text(node)
            target = entity_id(repo.repo_id, path, "fallback-reference", node.start_byte, label)
            graph.add(Entity(target, repo.repo_id, "external_symbol", label, file_id, language=language,
                             sort="external", is_external=1, rel_path=path, start_line=node.start_point.row+1, end_line=node.end_point.row+1,**source_flags))
            rid = "rel:" + digest("tree-sitter-syntax-v1", repo.repo_id, path, node.start_byte, node.type)
            subtype = "imports" if node.type == "import_statement" else "calls"
            graph.relationships[rid] = Relationship(rid, owner, target, owner, target, subtype, "candidate", rid[4:])
            ev = "evidence:" + digest(rid)
            graph.evidence[ev] = Evidence(ev, rid, "static_candidate", repo.repo_id, repo.revision, path,
                                         node.start_point.row+1, node.end_point.row+1,
                                         canonical({"callee": label, "adapter": package, "capability": "syntactic_candidate_only",
                                           'claim_version':'claim-details-v1','claim_kind':'syntax','producer':package,
                                           'producer_version':metadata.version(package.replace('_','-')),
                                           'reason_code':'TREESITTER_SYNTACTIC_ONLY','additional_reason_codes':[],
                                           'occurrence_id':'occurrence:'+digest(repo.repo_id,repo.revision,path,node.start_byte,node.end_byte,node.type),
                                           'assumptions':['syntax occurrence only; no language binding proof'],
                                           'source_span':{'start_line':node.start_point.row+1,'end_line':node.end_point.row+1,
                                                          'start_byte':node.start_byte,'end_byte':node.end_byte},
                                           'source_digest':hashlib.sha256(data).hexdigest()}),
                                         extractor_version="tree-sitter-syntax-v1")
        for child in node.named_children:
            walk(child, new_owner)
    walk(tree.root_node, file_id)
