"""Stage 2b — Convert pre-processed .md research notes → nodes JSON.

Reads structured .md files from D:\\Resource-Library\\06-Papers and writes
.nodes.json files into work/nodes/ in the same format as stage2_extract_nodes.py.

MD format expected:
  ---
  uuid: "..."
  title: "..."
  authors: [...]
  year: ...
  venue: "..."
  identifier_kind: "doi" | "arxiv"
  identifier: "..."
  primary_topic: "..."
  ---

  ## Bottom Line
  <abstract_summary>

  ## Claim
  [categorized list with quotes OR block quote]

  ## Method
  <methodology text>

  ## Evidence & Limits
  <evidence/limitations text>

Usage:
  python stage2_from_md.py --notes-dir "D:/Resource-Library/06-Papers" --work-dir work
  python stage2_from_md.py --notes-dir "D:/Resource-Library/06-Papers" --work-dir work --dry-run
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import re
import yaml
try:from .artifacts import WORK_DIR,write_json,digest_file,authors_list
except ImportError:from artifacts import WORK_DIR,write_json,digest_file,authors_list
import sys
from pathlib import Path

NOTES_DIR_DEFAULT = "D:/Resource-Library/06-Papers"


# ── YAML frontmatter parser ───────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text) from an MD file with YAML fences."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_raw = text[3:end].strip()
    body   = text[end + 4:].strip()
    fm=yaml.safe_load(fm_raw) or {}
    if not isinstance(fm,dict):raise ValueError('Note frontmatter must be a mapping')
    return fm, body


# ── Section extractor ─────────────────────────────────────────────────────────

_SECTION_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


def _split_sections(body: str) -> dict[str, str]:
    """Split body into {section_heading: content} dict."""
    # Mask fenced code at identical offsets so embedded Markdown is source text.
    masked=[];fence=None
    for line in body.splitlines(keepends=True):
        marker=re.match(r"^ {0,3}(`{3,}|~{3,})",line)
        if marker:
            token=marker.group(1)
            if fence is None:fence=token
            elif token[0]==fence[0] and len(token)>=len(fence):fence=None
            masked.append(''.join('\n' if c=='\n' else ' ' for c in line))
        elif fence:masked.append(''.join('\n' if c=='\n' else ' ' for c in line))
        else:masked.append(line)
    headings = list(_SECTION_RE.finditer(''.join(masked)))
    sections: dict[str, str] = {}
    for i, m in enumerate(headings):
        heading = m.group(1).strip()
        start   = m.end()
        end     = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        sections[heading.lower()] = '\n\n'.join(filter(None,[sections.get(heading.lower(),''),body[start:end].strip()]))
    return sections


# ── Claim extraction ──────────────────────────────────────────────────────────

_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)", re.MULTILINE)
_CATEGORY_CLAIM_RE = re.compile(
    r"\*\*(.+?)\*\*\s*\(category\s*\w+\)\s*-\s*(.+?)(?=\n\s*[-*>]|\n\n|\Z)",
    re.DOTALL,
)


def _extract_claims(claim_text: str) -> list[dict]:
    """Extract claims from the ## Claim section. Handles both formats."""
    claims: list[dict] = []

    # Format A: "**Term** (category X) - Description" bullets with quotes
    cat_matches = _CATEGORY_CLAIM_RE.findall(claim_text)
    if cat_matches:
        for name, desc in cat_matches:
            text = f"{name.strip()}: {desc.strip()}"
            text = re.sub(r"\s+", " ", text).strip()
            claims.append({"text": text, "claim_type": "finding"})
        return claims

    # Format B: single block-quote or plain paragraph
    # Strip block-quote markers and use as one "finding" claim
    clean = re.sub(r"^>\s?", "", claim_text, flags=re.MULTILINE)
    clean = re.sub(r"\s+", " ", clean).strip()
    if clean:
        # Truncate to ~400 chars
        claims.append({"text": clean[:400], "claim_type": "finding"})

    return claims


def _extract_method_claims(method_text: str) -> list[dict]:
    """Extract method claims from ## Method section."""
    claims: list[dict] = []
    # Named method bullets: "**Term**: description"
    for m in re.finditer(r"\*\*(.+?)\*\*:\s*(.+?)(?=\n\*\*|\n\n|\Z)", method_text, re.DOTALL):
        text = f"{m.group(1).strip()}: {m.group(2).strip()}"
        text = re.sub(r"\s+", " ", text).strip()
        claims.append({"text": text, "claim_type": "method"})

    if not claims:
        # Plain paragraph
        clean = re.sub(r"\s+", " ", method_text).strip()
        if clean:
            claims.append({"text": clean, "claim_type": "method"})
    return claims


def _extract_limitation_claims(ev_text: str) -> list[dict]:
    """Extract limitations from ## Evidence & Limits."""
    claims: list[dict] = []
    for m in _BULLET_RE.finditer(ev_text):
        text = re.sub(r"\s+", " ", m.group(1)).strip()
        # Heuristic: if the bullet mentions "limitation", "bounded", "not", "only", "lack"
        if any(w in text.lower() for w in ("limit", "bound", "not ", "only ", "lack", "future")):
            claims.append({"text": text, "claim_type": "limitation"})
        else:
            claims.append({"text": text, "claim_type": "finding"})
    if not claims:
        clean = re.sub(r"\s+", " ", ev_text).strip()
        if clean:
            claims.append({"text": clean, "claim_type": "limitation"})
    return claims


# ── Concept extraction ────────────────────────────────────────────────────────

def _extract_concepts(fm: dict, claim_text: str) -> list[dict]:
    """Derive concepts from frontmatter primary_topic and bolded terms."""
    concepts: list[dict] = []
    seen: set[str] = set()

    def _add(name: str, ctype: str, defn: str | None = None) -> None:
        key = name.lower().strip()
        if key and key not in seen and len(key) > 2:
            seen.add(key)
            concepts.append({"name": name.strip(), "definition": defn, "concept_type": ctype})

    # Primary topic → term
    if fm.get("primary_topic"):
        _add(fm["primary_topic"], "term")

    # Bold terms in claim section
    for m in re.finditer(r"\*\*(.+?)\*\*", claim_text):
        raw = m.group(1).strip()
        raw = re.sub(r"\s*\(category\s*\w+\)", "", raw).strip()
        if raw and len(raw) < 60:
            _add(raw, "term")

    # Wikilinks in semantic-links section → terms
    # (from "## Semantic Links" or "## Relevance to This Catalogue")
    # We'll handle them in _convert_md if needed.

    return concepts[:6]


# ── Main conversion ───────────────────────────────────────────────────────────

def _convert_md(md_path: Path) -> dict:
    """Parse a .md file and return a nodes.json-compatible dict."""
    text = md_path.read_text(encoding="utf-8-sig")
    fm, body = _parse_frontmatter(text)
    sections = _split_sections(body)

    title = fm.get("title") or md_path.stem
    authors = fm.get("authors") or []
    year    = fm.get("year")
    venue   = fm.get("venue") or None
    doi: str | None = None
    id_kind = fm.get("identifier_kind")
    id_val  = fm.get("identifier")
    if id_kind == "doi" and id_val:
        doi = id_val
    elif id_kind == "arxiv" and id_val:
        doi = f"arxiv:{id_val}"

    abstract_summary = sections.get("bottom line", "")[:400]

    # Build virtual sections
    result_sections: list[dict] = []
    pos = 0

    # -- Bottom Line / Abstract summary
    if abstract_summary:
        result_sections.append({
            "heading": "Bottom Line",
            "section_type": "abstract",
            "position": pos,
            "word_count": len(abstract_summary.split()),
            "text": sections.get("bottom line", ""),
            "claims": [{"text": sections.get("bottom line", ""), "claim_type": "finding"}],
            "concepts": [],
        })
        pos += 1

    # -- Claim section
    claim_text = sections.get("claim", "")
    claim_items = _extract_claims(claim_text) if claim_text else []
    if claim_items:
        concepts = _extract_concepts(fm, claim_text)
        result_sections.append({
            "heading": "Claims",
            "section_type": "results",
            "position": pos,
            "word_count": len(claim_text.split()),
            "text": claim_text,
            "claims": claim_items,
            "concepts": concepts,
        })
        pos += 1

    # -- Method section
    method_text = sections.get("method", "") or sections.get("methodology", "")
    method_items = _extract_method_claims(method_text) if method_text else []
    if method_items:
        result_sections.append({
            "heading": "Method",
            "section_type": "methods",
            "position": pos,
            "word_count": len(method_text.split()),
            "text": method_text,
            "claims": method_items,
            "concepts": [],
        })
        pos += 1

    # -- Evidence & Limits
    ev_text = (sections.get("evidence & limits", "")
               or sections.get("evidence and limits", "")
               or sections.get("evidence & limits", ""))
    ev_items = _extract_limitation_claims(ev_text) if ev_text else []
    if ev_items:
        result_sections.append({
            "heading": "Evidence & Limits",
            "section_type": "limitations",
            "position": pos,
            "word_count": len(ev_text.split()),
            "text": ev_text,
            "claims": ev_items,
            "concepts": [],
        })
        pos += 1

    return {
        "file_path":      str(md_path).replace("\\", "/"),
        "metadata": {
            "title":            title,
            "authors":          authors_list(authors),
            "year":             year if isinstance(year, int) else None,
            "venue":            venue if venue else None,
            "doi":              doi,
            "abstract_summary": abstract_summary,
        },
        "sections":       result_sections,
        "references_raw": "",
        "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        "source": "md_import",
        'source_sha256':digest_file(md_path),'producer':'research-note-parser-v3',
        'extracted_at':datetime.now(timezone.utc).isoformat(),
        'status':'complete','coverage':{'status':'note_derived_excerpts','limitations':['Claims and metadata derive from a research note, not independently verified PDF assertions']},
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 2b — .md notes → nodes JSON")
    ap.add_argument("--notes-dir", default=NOTES_DIR_DEFAULT)
    ap.add_argument("--work-dir",  default=str(WORK_DIR))
    ap.add_argument("--dry-run",   action="store_true")
    args = ap.parse_args()

    notes_dir = Path(args.notes_dir)
    nodes_dir = Path(args.work_dir) / "nodes"
    if not args.dry_run:nodes_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(
        f for f in notes_dir.glob("*.md")
        if not f.stem.startswith("_") and f.stem not in ("Paper Index", "MEMORY", "README")
    )
    if not md_files:
        sys.exit(f"No .md files found in {notes_dir}")

    print(f"Notes dir: {notes_dir}")
    print(f"Found:     {len(md_files)} .md files")
    print(f"Output:    {nodes_dir}")
    print()

    done = skipped = failed = 0
    for md in md_files:
        # Stem is "Author, Year - Title"
        out = nodes_dir / (md.stem + ".nodes.json")
        if out.exists():
            old=json.loads(out.read_text(encoding='utf-8'))
            if old.get('file_path')!=str(md).replace('\\','/'):raise ValueError('Artifact stem collision with another source')
            if old.get('source_sha256')==digest_file(md) and old.get('producer')=='research-note-parser-v3':
                skipped += 1
                continue

        try:
            result = _convert_md(md)
            if not result["sections"]:
                print(f"  [skip] {md.name}  (no parseable content)")
                skipped += 1
                continue
            nsec = len(result["sections"])
            nclaims = sum(len(s["claims"]) for s in result["sections"])
            nconcepts = sum(len(s["concepts"]) for s in result["sections"])
            print(f"  {md.name[:60]:<62}  {nsec}sec  {nclaims}cl  {nconcepts}con", end="")

            if not args.dry_run:
                write_json(out,result)
                print("  [saved]")
            else:
                print("  [dry-run]")
            done += 1
        except Exception as exc:
            print(f"\n  FAILED {md.name}: {exc}")
            failed += 1

    print(f"\nDone: {done} converted, {skipped} skipped, {failed} failed")
    if failed:raise SystemExit(1)


if __name__ == "__main__":
    main()
