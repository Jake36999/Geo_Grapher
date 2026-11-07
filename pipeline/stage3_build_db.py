"""Stage 3 — Nodes JSON → SQLite knowledge graph.

Reads all <work_dir>/nodes/*.nodes.json and upserts into <db_path>.

Schema:
  documents  — one row per PDF
  sections   — one row per section
  claims     — one row per extracted claim
  concepts   — deduplicated by canonical_name
  doc_concepts   — document ↔ concept edges (defines | mentions)
  section_concepts — section ↔ concept cross-references

Usage:
  python stage3_build_db.py --work-dir work --db doc_graph.db
  python stage3_build_db.py --work-dir work --db doc_graph.db --file "Paper.pdf"
  python stage3_build_db.py --work-dir work --db doc_graph.db --show-stats
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
try:from .artifacts import WORK_DIR,authors_list
except ImportError:from artifacts import WORK_DIR,authors_list

DEFAULT_DB = WORK_DIR/'doc_graph.db'

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documents (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  file_path        TEXT    UNIQUE NOT NULL,
  doi              TEXT,
  title            TEXT,
  authors          TEXT,   -- JSON array
  year             INTEGER,
  venue            TEXT,
  abstract_summary TEXT,
  page_count       INTEGER
);

CREATE TABLE IF NOT EXISTS sections (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id       INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  heading      TEXT,
  section_type TEXT,
  position     INTEGER,
  text         TEXT,
  word_count   INTEGER
);

CREATE TABLE IF NOT EXISTS claims (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
  text       TEXT    NOT NULL,
  claim_type TEXT
);

CREATE TABLE IF NOT EXISTS concepts (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_name TEXT UNIQUE NOT NULL,
  aliases        TEXT,   -- JSON array
  definition     TEXT,
  concept_type   TEXT,
  def_doc_id     INTEGER REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS doc_concepts (
  doc_id     INTEGER NOT NULL REFERENCES documents(id)  ON DELETE CASCADE,
  concept_id INTEGER NOT NULL REFERENCES concepts(id)   ON DELETE CASCADE,
  edge_type  TEXT    NOT NULL CHECK(edge_type IN ('defines','mentions')),
  PRIMARY KEY (doc_id, concept_id, edge_type)
);

CREATE TABLE IF NOT EXISTS section_concepts (
  section_id INTEGER NOT NULL REFERENCES sections(id)  ON DELETE CASCADE,
  concept_id INTEGER NOT NULL REFERENCES concepts(id)  ON DELETE CASCADE,
  PRIMARY KEY (section_id, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_sections_doc    ON sections(doc_id);
CREATE INDEX IF NOT EXISTS idx_claims_section  ON claims(section_id);
CREATE INDEX IF NOT EXISTS idx_dc_doc          ON doc_concepts(doc_id);
CREATE INDEX IF NOT EXISTS idx_dc_concept      ON doc_concepts(concept_id);
CREATE INDEX IF NOT EXISTS idx_sc_section      ON section_concepts(section_id);
CREATE INDEX IF NOT EXISTS idx_sc_concept      ON section_concepts(concept_id);

CREATE TABLE IF NOT EXISTS import_manifests (
  doc_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  artifact_sha256 TEXT NOT NULL CHECK(length(artifact_sha256)=64),
  source_sha256 TEXT,
  source_kind TEXT NOT NULL,
  producer TEXT NOT NULL,
  coverage_json TEXT NOT NULL CHECK(json_valid(coverage_json))
);
CREATE TABLE IF NOT EXISTS section_provenance (
  section_id INTEGER PRIMARY KEY REFERENCES sections(id) ON DELETE CASCADE,
  page_start INTEGER CHECK(page_start IS NULL OR page_start>=1),
  page_end INTEGER CHECK(page_end IS NULL OR page_end>=page_start),
  coordinate_space TEXT NOT NULL,
  claim_basis TEXT NOT NULL
);
"""


def _normalise_concept(name: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace."""
    n = name.lower().strip()
    n = re.sub(r"[^\w\s-]", "", n)
    n = re.sub(r"\s+", " ", n)
    return n.strip()


def _upsert_concept(cur: sqlite3.Cursor, raw_name: str, definition: str | None,
                    concept_type: str, doc_id: int) -> int:
    canon = _normalise_concept(raw_name)
    if not canon:
        return -1

    cur.execute("SELECT id, definition, def_doc_id FROM concepts WHERE canonical_name=?", (canon,))
    row = cur.fetchone()
    if row:
        cid, existing_def, existing_doc = row
        if not existing_def and definition:
            cur.execute("UPDATE concepts SET definition=?, def_doc_id=? WHERE id=?",
                        (definition, doc_id, cid))
        return cid
    else:
        cur.execute(
            "INSERT INTO concepts (canonical_name, aliases, definition, concept_type, def_doc_id) "
            "VALUES (?,?,?,?,?)",
            (canon, json.dumps([raw_name]), definition, concept_type, doc_id if definition else None)
        )
        return cur.lastrowid


def load_nodes_file(nodes_path: Path, conn: sqlite3.Connection, *, refresh_read_models=True) -> None:
    # A failed document import must not leak its deletes/partial inserts into
    # the next document's commit, including when an outer transaction exists.
    conn.execute('PRAGMA foreign_keys=ON')
    if conn.execute('PRAGMA foreign_keys').fetchone()[0]!=1:raise ValueError('Paper import requires foreign_keys=ON before transaction start')
    conn.execute('SAVEPOINT paper_import')
    try:
        _load_nodes_file(nodes_path,conn)
        if refresh_read_models:
            try:from .corpus import refresh
            except ImportError:from corpus import refresh
            refresh(conn)
        conn.execute('RELEASE paper_import')
    except BaseException:
        conn.execute('ROLLBACK TO paper_import');conn.execute('RELEASE paper_import');raise


def _load_nodes_file(nodes_path: Path, conn: sqlite3.Connection) -> None:
    data = json.loads(nodes_path.read_text(encoding="utf-8"))
    if data.get('skipped') or data.get('status')=='incomplete':raise ValueError('Incomplete/skipped extraction is not a publishable document')
    file_path = data["file_path"]
    meta      = data.get("metadata", {})
    sections  = data.get("sections", [])
    if not isinstance(file_path,str) or not file_path.strip():raise ValueError('Source file_path required')
    if not isinstance(meta,dict) or not isinstance(meta.get('title'),str) or not meta['title'].strip():raise ValueError('Nonempty document title required')
    if not isinstance(sections,list) or not sections:raise ValueError('At least one extracted section required')
    positions=[s.get('position') for s in sections]
    if any(type(p) is not int or p<0 for p in positions) or len(set(positions))!=len(positions):raise ValueError('Unique nonnegative section positions required')
    if data.get('source_sha256') is not None and not re.fullmatch('[0-9a-f]{64}',data['source_sha256']):raise ValueError('Invalid source SHA-256')

    cur = conn.cursor()

    artifact_digest=hashlib.sha256(nodes_path.read_bytes()).hexdigest()
    current=cur.execute('SELECT m.artifact_sha256 FROM import_manifests m JOIN documents d ON d.id=m.doc_id WHERE d.file_path=?',(file_path,)).fetchone()
    if current and current[0]==artifact_digest:return

    # Upsert document
    cur.execute(
        """INSERT INTO documents (file_path, doi, title, authors, year, venue, abstract_summary,page_count)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(file_path) DO UPDATE SET
             doi=excluded.doi, title=excluded.title, authors=excluded.authors,
             year=excluded.year, venue=excluded.venue,
             abstract_summary=excluded.abstract_summary,page_count=excluded.page_count""",
        (
            file_path,
            meta.get("doi"),
            meta.get("title"),
            json.dumps(authors_list(meta.get("authors", []))),
            meta.get("year"),
            meta.get("venue"),
            meta.get("abstract_summary"),
            data.get('page_count'),
        ),
    )
    cur.execute("SELECT id FROM documents WHERE file_path=?", (file_path,))
    doc_id = cur.fetchone()[0]
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='import_manifests'").fetchone():
        cur.execute('INSERT OR REPLACE INTO import_manifests VALUES(?,?,?,?,?,?)',
            (doc_id,artifact_digest,data.get('source_sha256'),
             data.get('source','legacy_artifact'),data.get('producer',data.get('model_id','legacy_unknown')),
             json.dumps(dict(data.get('coverage',{'status':'legacy_unverified','limitations':['No extraction/source coverage manifest']}),extracted_at=data.get('extracted_at')))))

    # Delete old sections (re-import is clean)
    cur.execute("DELETE FROM sections WHERE doc_id=?", (doc_id,))
    cur.execute("DELETE FROM doc_concepts WHERE doc_id=?", (doc_id,))
    # Definitions owned by a re-imported document may have disappeared. Do not
    # keep them as if newly confirmed; another explicit definition may refill.
    cur.execute('UPDATE concepts SET definition=NULL,def_doc_id=NULL WHERE def_doc_id=?',(doc_id,))

    doc_concept_cache: set[tuple[int, str]] = set()

    for s in sections:
        cur.execute(
            "INSERT INTO sections (doc_id, heading, section_type, position, text, word_count) "
            "VALUES (?,?,?,?,?,?)",
            (doc_id, s.get("heading"), s.get("section_type"), s.get("position"),
             s.get("text"), s.get("word_count")),
        )
        sec_id = cur.lastrowid
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='section_provenance'").fetchone():
            reliable=data.get('source_extractor_version')=='paper-text-v2'
            cur.execute('INSERT INTO section_provenance VALUES(?,?,?,?,?)',
                (sec_id,s.get('page_start') if reliable else None,s.get('page_end') if reliable else None,
                 'heuristic_pdf_section' if reliable else 'stored_section_text',
                 'note_assertion' if data.get('source')=='md_import' else 'model_extracted_documentary_assertion'))

        # Claims
        for c in s.get("claims", []):
            if c.get("text", "").strip():
                cur.execute(
                    "INSERT INTO claims (section_id, text, claim_type) VALUES (?,?,?)",
                    (sec_id, c["text"], c.get("claim_type")),
                )

        # Concepts
        for concept in s.get("concepts", []):
            raw_name = concept.get("name", "").strip()
            if not raw_name:
                continue
            cid = _upsert_concept(
                cur, raw_name,
                concept.get("definition"),
                concept.get("concept_type", "term"),
                doc_id,
            )
            if cid < 0:
                continue

            # Section ↔ concept
            cur.execute(
                "INSERT OR IGNORE INTO section_concepts (section_id, concept_id) VALUES (?,?)",
                (sec_id, cid),
            )

            # Doc ↔ concept
            edge_type = "defines" if concept.get("definition") else "mentions"
            if (cid, edge_type) not in doc_concept_cache:
                cur.execute(
                    "INSERT OR IGNORE INTO doc_concepts (doc_id, concept_id, edge_type) VALUES (?,?,?)",
                    (doc_id, cid, edge_type),
                )
                doc_concept_cache.add((cid, edge_type))

    # Unused concepts must not survive solely as stale search hits. Foreign-key
    # checks keep shared concepts and concepts still defined by other docs.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='concept_members'").fetchone():
        cur.execute('DELETE FROM concept_members')  # rebuilt once before writer publication
    cur.execute('DELETE FROM concepts WHERE NOT EXISTS(SELECT 1 FROM doc_concepts dc WHERE dc.concept_id=concepts.id) AND NOT EXISTS(SELECT 1 FROM section_concepts sc WHERE sc.concept_id=concepts.id)')
    if conn.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Paper graph foreign-key validation failed')


def print_stats(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for table in ("documents", "sections", "claims", "concepts",
                  "doc_concepts", "section_concepts"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table:<22} {cur.fetchone()[0]:>6} rows")

    cur.execute("SELECT section_type, COUNT(*) FROM sections GROUP BY section_type ORDER BY 2 DESC")
    rows = cur.fetchall()
    if rows:
        print("\n  Section types:")
        for stype, cnt in rows[:10]:
            print(f"    {str(stype):<20} {cnt:>5}")

    cur.execute("SELECT concept_type, COUNT(*) FROM concepts GROUP BY concept_type ORDER BY 2 DESC")
    rows = cur.fetchall()
    if rows:
        print("\n  Concept types:")
        for ctype, cnt in rows:
            print(f"    {str(ctype):<20} {cnt:>5}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 3 — nodes JSON → SQLite")
    ap.add_argument("--work-dir",   default=str(WORK_DIR), help="Root work directory")
    ap.add_argument("--db",         default=None, help="SQLite database path; defaults to work-dir/doc_graph.db")
    ap.add_argument("--file",       default=None,            help="Process only this PDF filename (stem)")
    ap.add_argument("--show-stats", action="store_true",     help="Print DB stats and exit")
    args = ap.parse_args()

    nodes_dir = Path(args.work_dir) / "nodes"
    db_path   = Path(args.db) if args.db else Path(args.work_dir)/'doc_graph.db'
    if args.show_stats and not db_path.is_file():raise SystemExit(f'Database not found: {db_path}')
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if args.show_stats:
        conn=sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True)
        print(f"\nDatabase: {db_path}")
        print_stats(conn)
        conn.close()
        return

    conn = sqlite3.connect(str(db_path))
    conn.executescript(DDL)

    if not nodes_dir.exists():
        sys.exit(f"Stage-2 output not found: {nodes_dir} — run stage2 first")

    if args.file:
        stem = Path(args.file).stem + ".nodes.json"
        node_files = [nodes_dir / stem]
        if not node_files[0].exists():
            sys.exit(f"Stage-2 file not found: {node_files[0]}")
    else:
        node_files = sorted(nodes_dir.glob("*.nodes.json"))

    print(f"Database: {db_path}")
    print(f"Loading {len(node_files)} node file(s)...")

    loaded = failed = 0
    conn.execute('BEGIN')
    for f in node_files:
        try:
            load_nodes_file(f, conn,refresh_read_models=False)
            loaded += 1
            print(f"  ok  {f.stem}")
        except Exception as exc:
            failed += 1
            print(f"  FAILED {f.stem}: {exc}")

    try:
        try:from .corpus import refresh
        except ImportError:from corpus import refresh
        refresh(conn);conn.commit()
    except BaseException:
        conn.rollback();raise

    print(f"\nLoaded {loaded}  failed {failed}")
    print("\nDatabase stats:")
    print_stats(conn)
    conn.close()
    if failed:raise SystemExit(1)


if __name__ == "__main__":
    main()
