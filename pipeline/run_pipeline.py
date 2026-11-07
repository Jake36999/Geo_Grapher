"""Doc-Grapher extraction pipeline orchestrator.

Runs stage1 → stage2 → stage3 in sequence.
Each stage is resumable: already-processed files are skipped.

Usage:
  python run_pipeline.py                          # all 114 papers, 70B model
  python run_pipeline.py --model 405b             # higher-quality extraction
  python run_pipeline.py --file "Paper.pdf"       # single paper only
  python run_pipeline.py --stage1-only            # just extract text (no API calls)
  python run_pipeline.py --dry-run                # estimate cost without running
  python run_pipeline.py --show-stats             # show DB stats only

Output:
  work/text/*.text.json   — stage 1: raw structured text
  work/nodes/*.nodes.json — stage 2: LLM-extracted claims/concepts
  work/doc_graph.db       — stage 3: SQLite knowledge graph

Cost estimate at 70B: ~$0.13 for 114 papers
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def run(cmd: list[str]) -> int:
    command=[str(HERE / cmd[0]),*cmd[1:]]
    result = subprocess.run([sys.executable] + command)
    return result.returncode


def main() -> None:
    ap = argparse.ArgumentParser(description="Doc-Grapher pipeline orchestrator")
    ap.add_argument("--library",    default="E:/Librarian research")
    ap.add_argument("--work-dir",   default=str(HERE/'work'))
    ap.add_argument("--db",         default=None)
    ap.add_argument("--model",      default="70b", choices=["70b", "405b", "500b"])
    ap.add_argument("--file",       default=None, help="Process a single PDF filename")
    ap.add_argument("--stage1-only",action="store_true")
    ap.add_argument("--dry-run",    action="store_true")
    ap.add_argument("--yes",        action="store_true")
    ap.add_argument("--show-stats", action="store_true")
    args = ap.parse_args()
    if args.db is None:args.db=str(Path(args.work_dir)/'doc_graph.db')

    if args.show_stats:
        raise SystemExit(run(["stage3_build_db.py", "--work-dir", args.work_dir,
             "--db", args.db, "--show-stats"]))

    # ── Stage 1 ──
    s1_cmd = [
        "stage1_extract_text.py",
        "--library", args.library,
        "--work-dir", f"{args.work_dir}/text",
    ]
    if args.file:
        s1_cmd += ["--file", args.file]

    if args.dry_run:
        print('Dry run: no extraction, writes, or API calls. Planned PDF stage:', ' '.join(s1_cmd))
        raise SystemExit(run(['stage2_extract_nodes.py','--work-dir',args.work_dir,'--model',args.model,'--dry-run']+(['--file',args.file] if args.file else [])))

    print("=" * 60)
    print("Stage 1 — PDF text extraction")
    print("=" * 60)
    rc = run(s1_cmd)
    if rc != 0:
        sys.exit(f"Stage 1 failed (exit {rc})")

    if args.stage1_only:
        return

    # ── Stage 2 ──
    s2_cmd = [
        "stage2_extract_nodes.py",
        "--work-dir", args.work_dir,
        "--model", args.model,
    ]
    if args.file:
        s2_cmd += ["--file", args.file]
    if args.dry_run:
        s2_cmd.append("--dry-run")
    elif args.yes:
        s2_cmd.append("--yes")

    print("\n" + "=" * 60)
    print("Stage 2 — LLM node extraction")
    print("=" * 60)
    rc = run(s2_cmd)
    if rc != 0 and not args.dry_run:
        sys.exit(f"Stage 2 failed (exit {rc})")

    if args.dry_run:
        return

    # ── Stage 3 ──
    s3_cmd = [
        "stage3_build_db.py",
        "--work-dir", args.work_dir,
        "--db", args.db,
    ]
    if args.file:
        s3_cmd += ["--file", args.file]

    print("\n" + "=" * 60)
    print("Stage 3 — SQLite knowledge graph build")
    print("=" * 60)
    rc = run(s3_cmd)
    if rc != 0:
        sys.exit(f"Stage 3 failed (exit {rc})")

    print(f"\nPipeline complete. DB: {args.db}")


if __name__ == "__main__":
    main()
