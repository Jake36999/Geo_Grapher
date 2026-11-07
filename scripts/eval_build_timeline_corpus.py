"""Build a paper-style corpus from Timeline-mapping vault notes (evaluation fixture).

Deterministic, no model calls: H1 -> title, '##' headings -> sections, bolded
paragraphs -> claims (the note author's documentary assertions, not verified
facts), Obsidian [[links]] -> concepts. Uses a Timeline-local empty alias policy,
persisted so later default refreshes never apply the AI corpus aliases.

    python scripts/eval_build_timeline_corpus.py --vault D:/Timeline-mapping/vault --out output/phase-b/timeline-papers.sqlite
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import stage3_build_db as db  # noqa: E402
from pipeline.corpus import refresh  # noqa: E402

SKIP_DIRS = {"99-Templates", "08-Canvas"}
LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
POLICY = {"version": "timeline-local-v1", "groups": [], "ranking_exclusions": [], "related_not_identical": []}


def clean(text: str) -> str:
    text = LINK.sub(lambda m: m.group(2) or m.group(1).replace("-", " "), text)
    text = re.sub(r"\*\*|__|`", "", text)
    return re.sub(r"\s+", " ", text).strip()


def split_frontmatter(raw: str) -> tuple[dict, str]:
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            try:
                return yaml.safe_load(raw[3:end]) or {}, raw[end + 4:]
            except yaml.YAMLError:
                return {}, raw[end + 4:]
    return {}, raw


def convert(path: Path, vault: Path) -> dict | None:
    raw = path.read_text(encoding="utf-8", errors="replace")
    front, body = split_frontmatter(raw)
    title_match = re.search(r"^# (.+)$", body, re.M)
    title = clean(title_match.group(1)) if title_match else path.stem.replace("-", " ")
    if title_match:
        body = body[:title_match.start()] + body[title_match.end():]
    parts = re.split(r"^## (.+)$", body, flags=re.M)
    chunks = [("Overview", parts[0])] + [(parts[i], parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
    sections = []
    for heading, text in chunks:
        if not text.strip():
            continue
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        claims = []
        for p in paragraphs:
            if "**" in p and len(clean(p)) >= 40:
                kind = "finding" if re.match(r"\*\*(Finding|Result)", p) else "assertion"
                claims.append({"text": clean(p)[:1200], "claim_type": kind})
        concepts, seen = [], set()
        for m in LINK.finditer(text):
            name = m.group(1).strip().replace("-", " ")
            if name.casefold() not in seen:
                seen.add(name.casefold())
                concepts.append({"name": name, "definition": None, "concept_type": "term"})
        sections.append({"heading": clean(heading), "position": len(sections), "text": clean(text)[:20000],
                         "word_count": len(clean(text).split()), "claims": claims[:6], "concepts": concepts[:12]})
    if not sections:
        return None
    rel = path.relative_to(vault).as_posix()
    summary = front.get("confidence_assessment") or front.get("summary") or (sections[0]["text"][:400] if sections else None)
    return {
        "file_path": "timeline-vault/" + rel,
        "source_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "source": "timeline_vault_markdown",
        "producer": "eval_build_timeline_corpus-v1",
        "coverage": {"status": "deterministic_markdown_conversion",
                     "limitations": ["Claims are the note author's documentary assertions, not verified facts",
                                     "Concepts are Obsidian wiki links, not extracted definitions"]},
        "metadata": {"title": title, "authors": [], "year": front.get("year"), "venue": front.get("type"),
                     "abstract_summary": str(summary)[:600] if summary else None},
        "sections": sections,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    vault = args.vault.resolve()
    if args.out.exists():
        sys.exit(f"{args.out} already exists; remove it deliberately to rebuild")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    notes = [p for p in sorted(vault.rglob("*.md")) if not SKIP_DIRS.intersection(p.relative_to(vault).parts)]
    conn = sqlite3.connect(args.out)
    conn.executescript(db.DDL)
    loaded = skipped = 0
    with tempfile.TemporaryDirectory() as tmp:
        for note in notes:
            data = convert(note, vault)
            if data is None:
                skipped += 1
                continue
            artifact = Path(tmp) / (hashlib.sha256(data["file_path"].encode()).hexdigest()[:16] + ".nodes.json")
            artifact.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            db.load_nodes_file(artifact, conn, refresh_read_models=False)
            loaded += 1
        policy = Path(tmp) / "timeline-policy.json"
        policy.write_text(json.dumps(POLICY), encoding="utf-8")
        stats = refresh(conn, policy)
    conn.execute("INSERT OR REPLACE INTO corpus_metadata VALUES(?,?)", ("origin_alias_policy", json.dumps(POLICY)))
    conn.commit()
    conn.close()
    print(json.dumps({"notes": len(notes), "loaded": loaded, "skipped_empty": skipped,
                      **{k: v for k, v in (stats or {}).items() if isinstance(v, (int, str))}}, indent=2))


if __name__ == "__main__":
    main()
