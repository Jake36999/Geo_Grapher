"""Stage 1 — PDF → structured text JSON using PyMuPDF.

Outputs one JSON file per PDF into the work directory:
  <work_dir>/<stem>.text.json

Each output has the shape:
  {
    "file_path": "E:/Librarian research/Paper.pdf",
    "page_count": 12,
    "first_page_text": "...",        # raw first-page text for metadata extraction
    "sections": [
      {
        "heading": "Introduction",
        "section_type": null,        # filled by stage 2
        "position": 0,
        "text": "...",               # complete extracted section body
        "page_start": 1,
        "word_count": 423
      }
    ],
    "references_raw": "..."          # raw text of reference section, truncated
  }

Usage:
  python stage1_extract_text.py --library "E:/Librarian research" --work-dir work/text
  python stage1_extract_text.py --library "E:/Librarian research" --work-dir work/text --file "Paper.pdf"
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import json
import re
import sys
from pathlib import Path
try:from .artifacts import WORK_DIR,write_json
except ImportError:from artifacts import WORK_DIR,write_json

try:import fitz  # PyMuPDF, optional until extraction is requested
except ImportError:fitz=None

MAX_REF_CHARS     = 3000
HEADING_SIZE_GAP   = 2.5   # font size must exceed body by at least this many pts
MIN_HEADING_CHARS  = 3     # ignore heading spans shorter than this
MAX_HEADING_CHARS  = 120   # ignore heading spans longer than this (likely body text)


# Section-type classifiers keyed on first word(s) of normalised heading
_SECTION_TYPES = {
    "abstract":        "abstract",
    "introduction":    "intro",
    "background":      "background",
    "related":         "related_work",
    "literature":      "related_work",
    "prior":           "related_work",
    "method":          "methods",
    "approach":        "methods",
    "model":           "methods",
    "experiment":      "results",
    "evaluation":      "results",
    "result":          "results",
    "finding":         "results",
    "discussion":      "discussion",
    "analysis":        "discussion",
    "conclusion":      "conclusion",
    "summary":         "conclusion",
    "future":          "future_work",
    "limitation":      "limitations",
    "reference":       "references",
    "bibliography":    "references",
    "appendix":        "appendix",
    "acknowledge":     "acknowledgements",
}


def _guess_section_type(heading: str) -> str:
    h = heading.lower().strip()
    for prefix, stype in _SECTION_TYPES.items():
        if h.startswith(prefix):
            return stype
    return "other"


def _body_font_size(blocks: list[dict]) -> float:
    """Return the most common font size in the document (approximates body text)."""
    sizes: dict[float, int] = {}
    for b in blocks:
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                s = round(span.get("size", 0), 1)
                sizes[s] = sizes.get(s, 0) + len(span.get("text", ""))
    if not sizes:
        return 10.0
    return max(sizes, key=sizes.__getitem__)


def extract_pdf(pdf_path: Path) -> dict:
    if fitz is None:raise RuntimeError('PDF extraction requires PyMuPDF in the selected Python environment')
    with fitz.open(str(pdf_path)) as doc:return _extract_document(pdf_path,doc)


def _extract_document(pdf_path,doc):
    page_count = len(doc)

    # Gather all text blocks with metadata
    all_blocks: list[dict] = []
    for page_number,page in enumerate(doc,1):
        for block in page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]:
            block['source_page']=page_number
            all_blocks.append(block)

    body_size = _body_font_size(all_blocks)
    heading_threshold = body_size + HEADING_SIZE_GAP

    # First-page raw text for metadata
    first_page_text = doc[0].get_text("text")[:3000] if page_count > 0 else ""

    # Build sections by detecting headings
    sections: list[dict] = []
    current_heading = "preamble"
    current_type    = "preamble"
    current_text: list[str] = []
    current_page    = 1
    current_end     = 1
    section_pos     = 0

    def _flush(heading, stype, text_parts, page_start, pos):
        body = " ".join(text_parts).strip()
        body = re.sub(r"\s{2,}", " ", body)
        words = len(body.split())
        if not body:return
        sections.append({
            "heading":      heading,
            "section_type": stype,
            "position":     pos,
            "text":         body,
            "page_start":   page_start,
            "page_end":     current_end,
            "word_count":   len(body.split()),
            "text_truncated": False,
        })

    for b in all_blocks:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                size   = span.get("size", 0)
                flags  = span.get("flags", 0)
                text   = span.get("text", "").strip()
                is_bold = bool(flags & 2**4)
                pg     = b['source_page']

                if not text:
                    continue

                # ALL-CAPS short line (common in journal two-column layouts)
                # Allow single-word known section names or multi-word ALL-CAPS headings
                _KNOWN_CAPS_SECTIONS = {
                    "ABSTRACT", "INTRODUCTION", "BACKGROUND", "PRELIMINARIES",
                    "METHODS", "METHODOLOGY", "APPROACH", "EXPERIMENTS",
                    "EVALUATION", "RESULTS", "DISCUSSION", "CONCLUSIONS",
                    "CONCLUSION", "CONTRIBUTIONS", "REFERENCES", "BIBLIOGRAPHY",
                    "ACKNOWLEDGEMENTS", "ACKNOWLEDGMENTS", "APPENDIX", "SUMMARY",
                }
                _caps_start_skip = ("FIGURE", "TABLE", "FIG.", "TAB.")
                alpha = "".join(c for c in text if c.isalpha())
                alpha_upper = alpha.upper()
                words = text.split()
                _caps_ok = (
                    len(alpha) >= 4
                    and alpha == alpha_upper
                    and MIN_HEADING_CHARS <= len(text) <= 60
                    and not text[0] in "([{"            # not a word-split
                    and not any(text.upper().startswith(x) for x in _caps_start_skip)
                    and (len(words) >= 2 or alpha_upper in _KNOWN_CAPS_SECTIONS)
                    and not re.search(r"\d{4}", text)   # exclude year/page-range citations
                )
                is_all_caps = _caps_ok

                # Detect heading: larger font OR bold + short standalone line
                # Require heading to look like a title (starts with capital, no colons mid-text)
                looks_like_title = (
                    text[0].isupper()
                    and MIN_HEADING_CHARS <= len(text) <= MAX_HEADING_CHARS
                    and text.count(",") <= 1   # not an author list
                )
                is_heading = (is_all_caps and len(text) < 80) or (looks_like_title and (
                    size >= heading_threshold
                    or (is_bold and len(text) < 80 and size >= body_size - 0.5)
                ))

                if is_heading and len(text) < MAX_HEADING_CHARS:
                    _flush(current_heading, current_type, current_text, current_page, section_pos)
                    current_heading = text
                    current_type    = _guess_section_type(text)
                    current_text    = []
                    current_page    = pg
                    current_end     = pg
                    section_pos    += 1
                else:
                    if not current_text:current_page=pg
                    current_text.append(text)
                    current_end=pg

    _flush(current_heading, current_type, current_text, current_page, section_pos)

    # Pull out references section raw text (for citation edge building)
    refs_raw = ""
    for s in sections:
        if s["section_type"] == "references":
            refs_raw = s["text"][:MAX_REF_CHARS]
            break

    return {
        "file_path":      str(pdf_path).replace("\\", "/"),
        "page_count":     page_count,
        "first_page_text": first_page_text,
        "sections":       [s for s in sections if s["section_type"] != "references"],
        "references_raw": refs_raw,
        "source_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "extractor_version": "paper-text-v2",
        "extracted_at":datetime.now(timezone.utc).isoformat(),
        "limitations": ["PDF reading order and heading detection are heuristic; text is not a verified semantic transcription"],
    }


def process_library(library: Path, work_dir: Path, single_file: str | None = None) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    if not library.is_dir():raise ValueError('PDF library directory not found')

    if single_file:
        pdfs = [library / single_file]
    else:
        pdfs = sorted(library.glob("*.pdf"))

    total = len(pdfs)
    skipped = done = failed = 0

    for i, pdf in enumerate(pdfs, 1):
        out = work_dir / (pdf.stem + ".text.json")
        if out.exists():
            try:old=json.loads(out.read_text(encoding='utf-8'))
            except (ValueError,UnicodeError):old={}
            if old.get('file_path') not in (None,str(pdf).replace('\\','/')):raise ValueError('Artifact stem collision')
            if old.get('source_sha256')==hashlib.sha256(pdf.read_bytes()).hexdigest() and old.get('extractor_version')=='paper-text-v2':
                skipped += 1
                continue

        print(f"[{i}/{total}] {pdf.name} ...", end=" ", flush=True)
        try:
            result = extract_pdf(pdf)
            write_json(out,result)
            nsec = len(result["sections"])
            print(f"ok  {nsec} sections  {result['page_count']}pp")
            done += 1
        except Exception as exc:
            print(f"FAILED: {exc}")
            failed += 1

    print(f"\nDone: {done} extracted, {skipped} skipped (already exist), {failed} failed")
    return dict(done=done,skipped=skipped,failed=failed)


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 1 — PDF → structured text JSON")
    ap.add_argument("--library",  default="E:/Librarian research", help="Folder of PDFs")
    ap.add_argument("--work-dir", default=str(WORK_DIR/'text'), help="Output directory")
    ap.add_argument("--file",     default=None,                    help="Process a single PDF filename only")
    args = ap.parse_args()

    library  = Path(args.library)
    work_dir = Path(args.work_dir)
    if not library.exists():
        sys.exit(f"Library not found: {library}")

    result=process_library(library, work_dir, args.file)
    if result['failed']:raise SystemExit(1)


if __name__ == "__main__":
    main()
