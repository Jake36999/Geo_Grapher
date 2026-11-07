"""Canonical, snapshot-independent records and deterministic identities."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any

EXTRACTOR_VERSION = "python-ast-symtable-v3-isolated"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(*parts: Any) -> str:
    return hashlib.sha256(canonical(list(parts)).encode("utf-8")).hexdigest()


def entity_id(*parts: Any) -> str:
    return "entity:" + digest(*parts)


@dataclass
class Entity:
    entity_id: str
    repo_id: str
    kind: str
    qualified_name: str
    parent_id: str | None
    sort: str = "entity"
    language: str = "python"
    rel_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    depth: int = 0
    ancestors_binary_lifting_json: str = "[]"
    is_test: int = 0
    is_generated: int = 0
    is_vendor: int = 0
    is_external: int = 0
    ast_body_hash: str | None = None
    wl_3hop_hash: str | None = None
    qi_cluster_id: str | None = None


@dataclass
class Relationship:
    relationship_id: str
    source_id: str
    target_id: str
    source_subject_id: str
    target_subject_id: str
    subtype: str
    resolution_status: str
    occurrence_key: str
    family: str = "static"
    direction: str = "directed"
    confidence: float | None = None
    weight: float = 1.0
    weight_unit: str = "edge_count"


@dataclass
class Evidence:
    evidence_id: str
    relationship_id: str
    category: str
    repo_id: str
    revision: str
    rel_path: str | None
    start_line: int | None
    end_line: int | None
    details_json: str
    extractor_version: str = EXTRACTOR_VERSION
    confidence: float | None = None
    trace_ref: str | None = None
    window_start: str | None = None
    window_end: str | None = None


@dataclass
class Graph:
    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    incidences: list[dict] = field(default_factory=list)
    analyses: dict[str, dict] = field(default_factory=dict)

    def add(self, value: Entity) -> str:
        old = self.entities.get(value.entity_id)
        if old is not None and asdict(old) != asdict(value):
            raise ValueError(f"Identity collision: {value.entity_id}")
        self.entities[value.entity_id] = value
        return value.entity_id

    def augment(self) -> None:
        """Atomise nonleaf dependency subjects and build the required lifting cache."""
        children: dict[str, list[str]] = {e: [] for e in self.entities}
        for e in self.entities.values():
            if e.parent_id is not None:
                children[e.parent_id].append(e.entity_id)
        subjects = {x for r in self.relationships.values() for x in (r.source_subject_id, r.target_subject_id)}
        # Eligible nonleaf subjects retain a self atom even with no current incident edge.
        subjects |= {e.entity_id for e in self.entities.values() if e.kind in
                     {"file", "class", "function", "method"}}
        atoms = {}
        for sid in sorted(subjects):
            if children[sid]:
                owner = self.entities[sid]
                aid = entity_id("scope-atom-v1", sid)
                if aid in self.entities:
                    atoms[sid] = aid
                    continue
                self.add(Entity(aid, owner.repo_id, "scope_atom", owner.qualified_name + ".<scope>",
                                sid, sort="synthetic", language=owner.language, rel_path=owner.rel_path,
                                start_line=owner.start_line, end_line=owner.end_line,
                                is_test=owner.is_test, is_generated=owner.is_generated,
                                is_vendor=owner.is_vendor))
                children[sid].append(aid)
                children[aid] = []
                atoms[sid] = aid
        for r in self.relationships.values():
            r.source_id = atoms.get(r.source_subject_id, r.source_subject_id)
            r.target_id = atoms.get(r.target_subject_id, r.target_subject_id)
        roots = [e.entity_id for e in self.entities.values() if e.parent_id is None]
        if len(roots) != 1:
            raise ValueError("Expected one workspace root")
        J = max(1, (max(1, len(self.entities)) - 1).bit_length() + 1)
        up: dict[str, list[str]] = {}
        stack = [(roots[0], 0)]
        while stack:
            sid, depth = stack.pop()
            parent = self.entities[sid].parent_id or sid
            row = [parent]
            for j in range(1, J):
                row.append(row[j-1] if parent == sid else up[row[j-1]][j-1])
            up[sid] = row
            self.entities[sid].depth = depth
            self.entities[sid].ancestors_binary_lifting_json = canonical(row)
            stack.extend((child, depth + 1) for child in reversed(sorted(children[sid])))
