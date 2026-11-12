"""Typed bridge endpoints, snapshot bindings and reviewed candidate scoring (master G4; U12).

A bridge endpoint is one of:
- ``entity:<entity_id>``;
- ``doc:<N>``, ``doc:<N>#claim:<M>`` or ``doc:<N>#section:<M>``;
- ``concept:<N>``;
- ``root``.

Endpoints are resolved against a graph's current code snapshot or paper read model and bound
with a fingerprint, so a later re-ingest can be checked for drift (lineage, Task 5). Proposals
are only candidates: nothing becomes a bridge without an explicit review.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

REF_KINDS = ("entity", "doc", "claim", "section", "concept", "root")
_POS = r"[1-9][0-9]{0,11}"
_DOC = re.compile(rf"^doc:({_POS})(?:#(claim|section):({_POS}))?$")
_CONCEPT = re.compile(rf"^concept:({_POS})$")
_ENTITY = re.compile(r"^entity:([A-Za-z0-9][A-Za-z0-9:_.\-]{0,280})$")
_CITE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+|https?://[^\s\"'<>)]+)", re.I)
ALIAS_FILE = Path(__file__).resolve().parents[2] / "pipeline" / "concept_aliases.json"
PSI = 0.25          # homonym firewall: name-only matches are scaled by Ψ
MIN_SCORE = 0.30    # proposals below this are not stored


def parse_ref(ref: str) -> tuple[str, dict]:
    """Return ``(kind, parts)`` for a bridge endpoint, or raise ``ValueError('BRIDGE_REF_INVALID')``."""
    if not isinstance(ref, str) or len(ref) > 300:
        raise ValueError("BRIDGE_REF_INVALID")
    if ref == "root":
        return "root", {}
    if m := _DOC.match(ref):
        doc = int(m.group(1))
        if m.group(2):
            return m.group(2), {"doc": doc, m.group(2): int(m.group(3))}
        return "doc", {"doc": doc}
    if m := _CONCEPT.match(ref):
        return "concept", {"concept": int(m.group(1))}
    if (m := _ENTITY.match(ref)) and ".." not in m.group(1):
        return "entity", {"entity": m.group(1)}
    raise ValueError("BRIDGE_REF_INVALID")


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _papers(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def paper_read_model(con) -> str:
    row = con.execute("SELECT value FROM corpus_metadata WHERE key='revision'").fetchone() if con.execute(
        "SELECT 1 FROM sqlite_master WHERE name='corpus_metadata'").fetchone() else None
    return row[0] if row else "unversioned"


def _doc_sources(con, doc: int) -> list[int]:
    row = con.execute("SELECT metadata_json,primary_source_id FROM read_documents WHERE id=?", (doc,)).fetchone()
    if row is None:
        return []
    try:
        ids = json.loads(row[0] or "{}").get("source_document_ids") or []
    except ValueError:
        ids = []
    return sorted({int(i) for i in ids if isinstance(i, int)} | ({row[1]} if isinstance(row[1], int) else set()) | {doc})


def resolve_ref(catalog, graph_id: str, ref: str) -> dict:
    """Resolve ``ref`` in the graph's current snapshot or paper read model.

    Returns ``{graph_id, ref, snapshot_id, paper_read_model, fingerprint_json}``. Raises
    ``ValueError('BRIDGE_ENDPOINT_UNRESOLVED')``.
    """
    kind, parts = parse_ref(ref)
    row = catalog.graph(graph_id)
    out = dict(graph_id=graph_id, ref=ref, snapshot_id=None, paper_read_model=None, fingerprint_json="{}")
    if kind in ("entity", "root"):
        out["snapshot_id"] = row["snapshot_id"]
        if kind == "root":
            if row["paper_database"] and not row["snapshot_id"]:
                with _papers(row["paper_database"]) as con:
                    out["paper_read_model"] = paper_read_model(con)
            return out
        from .store import SnapshotStore
        if not row["snapshot_id"]:
            raise ValueError("BRIDGE_ENDPOINT_UNRESOLVED")
        with SnapshotStore(row["code_database"]) as store:
            found = store.connection.execute("SELECT 1 FROM entities WHERE snapshot_id=? AND entity_id=?",
                                             (row["snapshot_id"], parts["entity"])).fetchone()
            if not found:
                raise ValueError("BRIDGE_ENDPOINT_UNRESOLVED")
            fp = (store.fingerprints(row["snapshot_id"]) or {}).get(parts["entity"]) or {}
        out["fingerprint_json"] = json.dumps(dict(sorted(fp.items())), sort_keys=True, separators=(",", ":"))
        return out
    if not row["paper_database"]:
        raise ValueError("BRIDGE_ENDPOINT_UNRESOLVED")
    with _papers(row["paper_database"]) as con:
        out["paper_read_model"] = paper_read_model(con)
        fingerprint = {}
        if kind == "concept":
            hit = con.execute("SELECT canonical_name FROM read_concepts WHERE id=?", (parts["concept"],)).fetchone()
        else:
            hit = con.execute("SELECT title FROM read_documents WHERE id=?", (parts["doc"],)).fetchone()
            if hit and kind == "claim":
                hit = con.execute("SELECT text FROM read_claims WHERE id=? AND doc_id=?", (parts["claim"], parts["doc"])).fetchone()
                if hit:
                    fingerprint = {"claim_text_sha256": _sha(hit[0])}
            elif hit and kind == "section":
                sources = _doc_sources(con, parts["doc"])
                hit = con.execute("SELECT heading FROM sections WHERE id=? AND doc_id IN (%s)" % ",".join("?" * len(sources)),
                                  (parts["section"], *sources)).fetchone()
        if hit is None:
            raise ValueError("BRIDGE_ENDPOINT_UNRESOLVED")
    out["fingerprint_json"] = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
    return out


def score_candidate(features: dict) -> float:
    """0.45·alias_overlap + 0.35·shared_citation + 0.20·neighbour_jaccard, ×Ψ when only names agree."""
    a, c, n = (float(features.get(k, 0)) for k in ("alias_overlap", "shared_citation", "neighbour_jaccard"))
    if not all(0 <= x <= 1 for x in (a, c, n)):
        raise ValueError("features must lie in [0,1]")
    score = 0.45 * a + 0.35 * c + 0.20 * n
    if c == 0 and n == 0:
        score *= PSI
    return round(score, 6)


# --- candidate generation ------------------------------------------------------------------------

def alias_policy(path: Path = ALIAS_FILE) -> dict[str, str]:
    """normalised alias -> normalised canonical, from the reviewed alias groups."""
    try:
        groups = json.loads(path.read_text(encoding="utf-8")).get("groups", [])
    except (OSError, ValueError):
        return {}
    out = {}
    for g in groups:
        canon = normalise(g.get("canonical", ""))
        for alias in [g.get("canonical", ""), *g.get("aliases", [])]:
            if normalise(alias):
                out[normalise(alias)] = canon
    return out


def normalise(name: str) -> str:
    """Lowercase words: splits snake_case, camelCase and punctuation; drops a leading underscore."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name or "")
    return " ".join(w for w in re.split(r"[^A-Za-z0-9]+", name.lower()) if w)


def _names(raw: list[str], policy: dict) -> frozenset:
    out = set()
    for r in raw:
        n = normalise(r)
        if n:
            out.add(policy.get(n, n))
    return frozenset(out)


def cite_key(value: str) -> str:
    """Comparable citation: a DOI (also out of a doi.org URL) or a URL, lowercased, trailing punctuation dropped."""
    v = (value or "").strip().rstrip(".,;").lower()
    m = re.search(r"(?:doi\.org/|^doi:\s*)(10\.\d{4,9}/\S+)$", v)
    return m.group(1) if m else v


def _jaccard(a, b) -> float:
    return round(len(a & b) / len(a | b), 6) if a | b else 0.0


def paper_candidates(paper_database: str, policy: dict) -> list[dict]:
    """Concept and section endpoints of a paper graph: names, citations, 1-hop neighbour names."""
    out = []
    with _papers(paper_database) as con:
        docs = {r[0]: {r[1]} - {None, ""} for r in con.execute("SELECT id,doi FROM read_documents")}
        has = lambda t: con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (t,)).fetchone()
        concept_docs: dict[int, set] = {}
        if has("read_doc_concepts"):
            for cid, did in con.execute("SELECT concept_id,doc_id FROM read_doc_concepts"):
                concept_docs.setdefault(cid, set()).add(did)
        concepts = {}
        for cid, name, aliases, def_doc in con.execute("SELECT id,canonical_name,aliases,def_doc_id FROM read_concepts ORDER BY id"):
            try:
                extra = json.loads(aliases) if aliases else []
            except ValueError:
                extra = []
            concepts[cid] = (name, [a for a in extra if isinstance(a, str)], def_doc)
        doc_concepts: dict[int, set] = {}
        for cid, ds in concept_docs.items():
            for d in ds:
                doc_concepts.setdefault(d, set()).add(cid)
        for cid, (name, aliases, def_doc) in sorted(concepts.items()):
            ds = concept_docs.get(cid, set()) | ({def_doc} if def_doc else set())
            neighbours = {concepts[o][0] for d in ds for o in doc_concepts.get(d, ()) if o != cid and o in concepts}
            cites = {c for d in ds for c in docs.get(d, ())}
            out.append(dict(ref=f"concept:{cid}", names=_names([name, *aliases], policy),
                            citations=frozenset(cite_key(c) for c in cites), neighbours=_names(sorted(neighbours), policy)))
        if has("sections"):
            source_to_doc = {}
            for did in docs:
                for s in _doc_sources(con, did):
                    source_to_doc.setdefault(s, did)
            for sid, src_doc, heading in con.execute("SELECT id,doc_id,heading FROM sections WHERE heading IS NOT NULL ORDER BY id"):
                did = source_to_doc.get(src_doc)
                if did is None or not normalise(heading):
                    continue
                neighbours = {concepts[o][0] for o in doc_concepts.get(did, ()) if o in concepts}
                out.append(dict(ref=f"doc:{did}#section:{sid}", names=_names([heading], policy),
                                citations=frozenset(cite_key(c) for c in docs.get(did, ())), neighbours=_names(sorted(neighbours), policy)))
    return out


def code_candidates(code_database: str, snapshot_id: str, policy: dict) -> list[dict]:
    """Function, method, class and file endpoints of a code graph."""
    from .store import SnapshotStore
    import base64
    out = []
    with SnapshotStore(code_database) as store:
        g = store.graph(snapshot_id)
        neighbours: dict[str, set] = {}
        for r in g.relationships.values():
            if r.family == "static" and r.resolution_status == "exact" and r.source_subject_id != r.target_subject_id:
                neighbours.setdefault(r.source_subject_id, set()).add(r.target_subject_id)
                neighbours.setdefault(r.target_subject_id, set()).add(r.source_subject_id)
        sources = {}
        for record in g.analyses.values():
            if record["algorithm_version"] == "source-bytes-v1":
                sources[record["result"]["rel_path"]] = record["result"]["bytes_base64"]
        lines: dict[str, list[str]] = {}
        short = lambda e: e.qualified_name.rsplit("/", 1)[-1].rsplit(".", 1)[-1] if e.kind != "file" else Path(e.rel_path or "").stem
        for eid in sorted(g.entities):
            e = g.entities[eid]
            if e.kind not in {"function", "method", "class", "file"} or e.is_external or e.is_test or e.is_generated or e.is_vendor:
                continue
            text = ""
            if e.rel_path in sources and e.start_line and e.end_line:
                if e.rel_path not in lines:
                    lines[e.rel_path] = base64.b64decode(sources[e.rel_path]).decode("utf-8", "replace").splitlines()
                text = "\n".join(lines[e.rel_path][e.start_line - 1:e.end_line])
            names = sorted(short(g.entities[n]) for n in neighbours.get(eid, ()) if n in g.entities and not g.entities[n].is_external)
            out.append(dict(ref=f"entity:{eid}", names=_names([short(e)], policy),
                            citations=frozenset(cite_key(m) for m in _CITE.findall(text)),
                            neighbours=_names(names, policy)))
    return out


def score_pairs(left: list[dict], right: list[dict], limit: int) -> list[dict]:
    """Pairs sharing at least one normalised name; scored, firewall applied, ≥ MIN_SCORE, best first."""
    index: dict[str, list[int]] = {}
    for j, r in enumerate(right):
        for n in r["names"]:
            index.setdefault(n, []).append(j)
    pairs = []
    for a in left:
        for j in sorted({j for n in a["names"] for j in index.get(n, ())}):
            b = right[j]
            features = dict(alias_overlap=_jaccard(a["names"], b["names"]),
                            shared_citation=1 if a["citations"] & b["citations"] else 0,
                            neighbour_jaccard=_jaccard(a["neighbours"], b["neighbours"]))
            score = score_candidate(features)
            if score >= MIN_SCORE:
                pairs.append(dict(source_ref=a["ref"], target_ref=b["ref"], score=score, features=features))
    pairs.sort(key=lambda p: (-p["score"], p["source_ref"], p["target_ref"]))
    return pairs[:limit]
