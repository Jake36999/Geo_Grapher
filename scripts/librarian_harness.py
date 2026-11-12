"""Geo-Grapher exercised through the Librarian V2 runtime (Librarian as the harness).

Geo-Grapher stays a tool: `serve-graphs --transport stdio` under the pinned
wheel-env, attached exactly as a person would attach it in Librarian's
Settings -> MCP servers. Everything else is Librarian's own machinery:

  * provider  - providers.from_settings({"provider": "deepinfra", ...}): transient
                retries (429/5xx/timeouts), typed failure categories;
  * loop      - loop.Loop: context fitting, budgets, untrusted wrapping of
                external results, max-step stop;
  * MCP       - mcp_client.McpManager: digest-accepted stdio server, tools
                registered as mcp__geo__<tool>, oversize structured results
                withheld intact (EXTERNAL_RESULT_TOO_LARGE) rather than clipped.

The model is told a graph's *label* only and must discover its graph_id with
list_graphs, so wrong-graph calls are measured as well as answer leakage.

Run with the Librarian's interpreter (no packages are installed anywhere):

    D:/Librarian_V2/.venv/Scripts/python.exe scripts/librarian_harness.py smoke
    D:/Librarian_V2/.venv/Scripts/python.exe scripts/librarian_harness.py bench  --model Qwen/Qwen3-32B
    D:/Librarian_V2/.venv/Scripts/python.exe scripts/librarian_harness.py probes --model Qwen/Qwen3-32B

The DeepInfra key is read from D:/Resource-Library/.utility/.env into this
process's environment only; it is never printed or written.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import eval_graph_leakage as probes  # noqa: E402  (probe set + scorer; no client deps at import)

from resource_librarian import providers  # noqa: E402
from resource_librarian.init import init  # noqa: E402
from resource_librarian.loop import Loop  # noqa: E402
from resource_librarian.mcp_client import McpManager  # noqa: E402
from resource_librarian.registry import REGISTRY, Context  # noqa: E402
from resource_librarian.vault import Vault  # noqa: E402

ENV_FILE = Path(r"D:\Resource-Library\.utility\.env")
WHEEL_PYTHON = ROOT / "output" / "wheel-env" / "Scripts" / "python.exe"
SERVER = "geo"
PACKAGE_VERSION = "0.1.1"
CORE = ["list_graphs", *("paper_" + t for t in probes.CORE)]

BENCH = [
    ("What do recent papers say about retrieval augmented generation? Summarise the main claims.", ["115"]),
    ("Which papers combine knowledge graphs with large language models? What specific techniques do they propose?", ["doc:1", "108"]),
    ("What token efficiency advantages do graph-based retrieval methods claim over dense vector search?", ["85"]),
    ("What graph neural network techniques appear in the corpus, and which papers use them?", ["229", "152"]),
    ("What are the main evaluation benchmarks used in papers about knowledge graph construction?", ["234"]),
]

WORKFLOW = ("Use only the geo-grapher tools. First call list_graphs to find the graph_id for the named "
            "graph; every other call needs that graph_id and a request object. Workflow: "
            "paper_search_documents with the key terms (rephrase once if results look off-topic); "
            "search cards are summaries, so open the 2-3 most relevant hits with paper_get_document "
            "(request.detail='claims') before answering or concluding something is absent. Cite each document "
            "by its cite_as handle exactly as returned (graph-label/doc:N). Never answer from prior knowledge; if the graph does not cover the question, say "
            "plainly that it is not in this corpus.")
FEDERATED = ("Two graphs are relevant: 'ai-research-papers' and 'timeline-mapping'. Use list_graphs for "
             "their graph_ids and query both. Document IDs are local to each graph, so cite by each "
             "result's cite_as handle (e.g. timeline-mapping/doc:4) and keep every claim attributed to its graph.")


def load_key() -> None:
    if os.environ.get("DEEPINFRA_API_KEY"):
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "DEEPINFRA_API_KEY":
            os.environ["DEEPINFRA_API_KEY"] = value.strip().strip('"').strip("'")
            return
    sys.exit(f"DEEPINFRA_API_KEY not found in {ENV_FILE}")


class Harness:
    """`scoping="open"`: one connection that can reach every graph in the catalog.
    `scoping="library"`: one connection per library, pinned with --graph-id to that
    library's graph(s) - how a Librarian library would be configured in practice."""

    def __init__(self, catalog: Path, workdir: Path, scoping: str = "open", launch: str = "source",
                 bundles: bool = False):
        init(workdir / "vault", name="Geo-Grapher harness")
        self.vault = Vault(workdir / "vault")
        self.manager = McpManager(workdir / "config")
        self.corpora = probes.corpus_titles(catalog)
        self.labels = {v["graph_id"]: k for k, v in self.corpora.items()}
        ids = {label: info["graph_id"] for label, info in self.corpora.items()}
        if scoping == "library":
            servers = {"geo_ai": [ids[probes.AI]], "geo_tl": [ids[probes.TL]], "geo_both": [ids[probes.AI], ids[probes.TL]]}
        else:
            servers = {SERVER: []}
        self.tools: dict[str, dict[str, str]] = {}
        for name, allowed in servers.items():
            if launch == "uvx":
                # Exactly the Librarian curated entry: a pinned package, configured by env.
                definition = {"command": "uvx", "args": ["--from", f"geo-grapher=={PACKAGE_VERSION}", "geographer",
                                                         "serve-graphs", "--transport", "stdio"],
                              "env": {"GEOGRAPHER_CATALOG": str(catalog), "GEOGRAPHER_GRAPHS": ",".join(allowed),
                                      "GEOGRAPHER_TOOLS": "papers",
                                      "GEOGRAPHER_MAX_RESULT_CHARS": "7500", "UV_FIND_LINKS": str(ROOT / "dist"),
                                      **({"UV_CACHE_DIR": os.environ["UV_CACHE_DIR"]} if os.environ.get("UV_CACHE_DIR") else {})}}
                if not allowed:
                    definition["env"].pop("GEOGRAPHER_GRAPHS")
            else:
                # Librarian withholds structured results over 8,000 chars; page under that instead.
                args = ["-m", "geographer", "serve-graphs", "--catalog", str(catalog), "--transport", "stdio",
                        "--max-result-chars", "7500"]
                for gid in allowed:
                    args += ["--graph-id", gid]
                definition = {"command": str(WHEEL_PYTHON), "args": args,
                              "env": {"PYTHONPATH": f"{ROOT / 'src'};{ROOT}"}, "cwd": str(ROOT)}
            self.manager.set_server(name, definition)
            self.manager.accept(name)
        self.server_graphs = {name: list(allowed) for name, allowed in servers.items()}
        status = self.manager.sync()
        for name in servers:
            if not status[name]["connected"]:
                raise SystemExit(f"Librarian could not connect to {name}: {status[name]['error']}")
            self.tools[name] = {n.split("__", 2)[2]: n for n in self.manager.tool_names(name)}
            missing = [t for t in ("list_graphs", "paper_search_documents", "paper_get_document") if t not in self.tools[name]]
            if missing:
                raise SystemExit(f"{name} did not offer {missing}")
        self.scoping = scoping
        self.bundles = bundles

    def _only_server(self, server: str):
        """A library enables only its own server: hide the others' tools for one run."""
        hidden = [REGISTRY.get(n) for other, tools in self.tools.items() if other != server for n in tools.values()]
        for spec in hidden:
            REGISTRY.unregister(spec.name)
        return hidden

    def server_for(self, graph_label: str | None) -> str:
        if self.scoping != "library":
            return SERVER
        return {probes.AI: "geo_ai", probes.TL: "geo_tl", None: "geo_both"}[graph_label]

    def close(self) -> None:
        self.manager.stop()

    def call(self, tool: str, arguments: dict, server: str | None = None) -> dict:
        return REGISTRY.call(self.tools[server or next(iter(self.tools))][tool], arguments, Context(tier="contribute"))

    def run(self, provider, prompt: str, max_steps: int = 12, server: str | None = None) -> dict:
        events: list[dict] = []
        if self.bundles:
            # The app's own path: compact task bundles, inside an explore research
            # session; outside tools are offered only by the bundle policy.
            loop = Loop(self.vault, provider, tier="contribute", scribe=None, max_steps=max_steps,
                        on_event=events.append)
            opened = REGISTRY.call("open_session", {"purpose": "explore", "question": prompt[-300:]},
                                   Context(tier="contribute", vault=self.vault))
            loop.ctx.session = opened["opened"]
        else:
            loop = Loop(self.vault, provider, tier="contribute", scribe=None, max_steps=max_steps,
                        extras={"use_tool_bundles": False}, on_event=events.append)
            loop.only = frozenset(self.tools[server or next(iter(self.tools))][t] for t in CORE
                                  if t in self.tools[server or next(iter(self.tools))])
        hidden = self._only_server(server or next(iter(self.tools))) if self.bundles else []
        try:
            offered = sorted(t.name for t in loop.tools() if t.name.startswith("mcp__"))
            start = time.monotonic()
            turn = loop.send(prompt)
        finally:
            for spec in hidden:
                REGISTRY.register(spec)
        retrieved: dict[str, set[int]] = {label: set() for label in self.corpora}
        graphs_called, tool_text, withheld, errors, blocked, bundle_refused = [], [], 0, 0, 0, 0
        pending_graph = None
        pinned = self.server_graphs.get(server or next(iter(self.tools)), [])
        ids_by_label = {label: info["graph_id"] for label, info in self.corpora.items()}
        for event in events:
            if event["type"] == "tool_call":
                ref = (event.get("arguments") or {}).get("graph_id")
                # Mirror the hub: a label is an alias, and a single-graph connection needs no graph_id.
                pending_graph = ids_by_label.get(ref, ref) if ref else (pinned[0] if len(pinned) == 1 else None)
                if pending_graph:
                    graphs_called.append(pending_graph)
            elif event["type"] == "tool_result":
                result = event.get("result") or {}
                content = str(result.get("content") or "")
                if "EXTERNAL_RESULT_TOO_LARGE" in content:
                    withheld += 1
                if result.get("is_error") or result.get("error") or result.get("refused"):
                    errors += 1
                if "not available on this connection" in content:
                    blocked += 1
                if result.get("refused") == "TOOL_BUNDLE_REFUSED":
                    bundle_refused += 1
                label = self.labels.get(pending_graph)
                if label:
                    ids = {int(n) for n in re.findall(r'"doc:(\d+)"', content)}
                    ids |= {int(n) for n in re.findall(r'"(?:doc_id|document_id|source_document_id)":\s*(\d+)', content)}
                    retrieved[label] |= ids
                    tool_text.append(content)
        return dict(answer=(turn.reply or "").strip(), steps=turn.steps, stopped=turn.stopped,
                    failure_category=turn.failure_category, error=turn.error[:300],
                    tool_calls=len(turn.calls), tool_errors=errors, withheld_oversize=withheld, blocked_by_allow_list=blocked,
                    bundle_refused=bundle_refused, outside_tools_offered=offered,
                    librarian_tools_used=sorted({c["tool"] for c in turn.calls if not c["tool"].startswith("mcp__")}),
                    graphs_called=graphs_called, retrieved={k: sorted(v) for k, v in retrieved.items()},
                    tool_text="\n".join(tool_text), elapsed_seconds=round(time.monotonic() - start, 1))


def provider_for(model: str):
    return providers.from_settings({"provider": "deepinfra", "model": model, "timeout": 180})


def smoke(h: Harness) -> None:
    for server in h.tools:
        graphs = json.loads(h.call("list_graphs", {}, server)["content"])
        print(f"{server} lists:", [(g["label"], g["graph_id"]) for g in graphs["graphs"]])
    for label, info in h.corpora.items():
        server = h.server_for(label)
        out = h.call("paper_search_documents", {"graph_id": info["graph_id"], "request": {"query": "networks", "limit": 10}}, server)
        other = next(v["graph_id"] for k, v in h.corpora.items() if k != label)
        if h.scoping == "library":
            refused = h.call("paper_search_documents", {"graph_id": other, "request": {"query": "networks"}}, server)
            print(f"{server} -> other graph: {json.loads(refused['content']).get('error', {}).get('message')}")
        body = json.loads(out["content"])
        print(f"{label}: untrusted={out['untrusted']} error={out['is_error']} chars={len(out['content'])} "
              f"hits={len(body.get('result', {}).get('results', []))} withheld={'EXTERNAL_RESULT_TOO_LARGE' in out['content']}")
    print("tools offered:", sorted(h.tools))


def bench(h: Harness, model: str, out: Path) -> None:
    provider = provider_for(model)
    results = []
    for question, markers in BENCH:
        prompt = f"Graph: 'ai-research-papers'. {WORKFLOW}\n\nQuestion: {question}"
        r = h.run(provider, prompt, server=h.server_for(probes.AI))
        r.update(question=question, model=model, markers=markers,
                 markers_found=[m for m in markers if m in r["answer"]],
                 wrong_graph_calls=sum(g != h.corpora[probes.AI]["graph_id"] for g in r["graphs_called"]))
        r.pop("tool_text")
        results.append(r)
        print(f"[bench] calls={r['tool_calls']:2d} steps={r['steps']:2d} stopped={r['stopped'] or '-':10s} "
              f"facts={len(r['markers_found'])}/{len(markers)} wrong_graph={r['wrong_graph_calls']} "
              f"withheld={r['withheld_oversize']} offered={len(r['outside_tools_offered'])} "
              f"bundle_refused={r['bundle_refused']} lib_tools={r['librarian_tools_used']} {r['elapsed_seconds']}s | {question[:50]}", flush=True)
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    n = len(results)
    print(f"\nanswered {sum(bool(r['answer']) for r in results)}/{n}; facts "
          f"{sum(len(r['markers_found']) for r in results)}/{sum(len(r['markers']) for r in results)}; "
          f"avg tool calls {sum(r['tool_calls'] for r in results)/n:.1f}; wrong-graph calls "
          f"{sum(r['wrong_graph_calls'] for r in results)}; withheld {sum(r['withheld_oversize'] for r in results)}")


def run_probes(h: Harness, model: str, out: Path, only: str | None) -> None:
    provider = provider_for(model)
    chosen = [p for p in probes.PROBES if not only or p["kind"] in only.split(",")]
    results = []
    for probe in chosen:
        federated = probe["kind"] == "federated"
        prompt = (f"{FEDERATED} {WORKFLOW}" if federated else f"Graph: '{probe['graph']}'. {WORKFLOW}") + \
                 f"\n\nQuestion: {probe['q']}"
        r = h.run(provider, prompt, server=h.server_for(probe["graph"]))
        target = None if federated else h.corpora[probe["graph"]]["graph_id"]
        real = set(h.labels)
        # Only a call that actually reached another real graph is a scope violation;
        # a mistyped graph_id is rejected by the hub and reported separately.
        wrong = 0 if federated else sum(g != target and g in real for g in r["graphs_called"])
        invalid = sum(g not in real for g in r["graphs_called"])
        reached_other = max(0, wrong - r["blocked_by_allow_list"])
        scored = probes.score(probe, r["answer"], r["retrieved"], r["tool_text"], h.corpora, out_of_scope=reached_other)
        r.update(scored, kind=probe["kind"], graph=probe["graph"], question=probe["q"], model=model,
                 scoping=h.scoping, wrong_graph_calls=wrong, invalid_graph_ids=invalid)
        results.append(r)
        flag = ",".join(r["failures"]) or "ok"
        print(f"[{len(results):2d}] {r['kind']:11s} {str(r['graph'] or 'both'):18s} calls={r['tool_calls']:2d} "
              f"stopped={r['stopped'] or '-':9s} wrong_graph={wrong} blocked={r['blocked_by_allow_list']} {flag} | {r['question'][:50]}", flush=True)
        out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    n = len(results)
    count = lambda cat: sum(cat in r["failures"] for r in results)
    print(f"\nLeakage (cross-graph or prior-knowledge): {sum(r['leaked'] for r in results)}/{n}")
    for cat in ("cross_graph_leak", "prior_knowledge_leak", "citation_error", "recall_miss", "no_answer"):
        print(f"  {cat:21s} {count(cat)}/{n}")
    print(f"  wrong-graph calls      {sum(r['wrong_graph_calls'] for r in results)} "
          f"(blocked by allow-list {sum(r['blocked_by_allow_list'] for r in results)}; "
          f"mistyped ids {sum(r['invalid_graph_ids'] for r in results)})")
    print(f"  oversize withheld      {sum(r['withheld_oversize'] for r in results)}")
    print(f"  bundle-refused calls   {sum(r['bundle_refused'] for r in results)}; "
          f"outside tools offered per turn {sorted({len(r['outside_tools_offered']) for r in results})}; "
          f"turns using Librarian tools {sum(bool(r['librarian_tools_used']) for r in results)}")
    print(f"  turns stopped early    {sum(bool(r['stopped']) for r in results)} "
          f"({', '.join(sorted({r['stopped'] for r in results if r['stopped']})) or 'none'})")
    print(f"  avg tool calls         {sum(r['tool_calls'] for r in results)/n:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["smoke", "bench", "probes"])
    parser.add_argument("--catalog", type=Path, default=ROOT / "output" / "phase-b" / "catalog.sqlite")
    parser.add_argument("--model", default="Qwen/Qwen3-32B")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--only", help="comma-separated probe kinds")
    parser.add_argument("--scoping", choices=["open", "library"], default="open",
                        help="open: one connection to every graph; library: per-library connections pinned with --graph-id")
    parser.add_argument("--launch", choices=["source", "uvx"], default="source",
                        help="source: this checkout under wheel-env; uvx: the pinned package from dist/ (the curated entry)")
    parser.add_argument("--bundles", choices=["off", "on"], default="off",
                        help="on: the app's own compact tool bundles inside an explore session (outside tools via bundle policy)")
    args = parser.parse_args()
    if args.mode != "smoke":
        load_key()
    out = args.out or ROOT / "output" / "librarian" / f"{args.mode}-{args.scoping}-{args.model.split('/')[-1]}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="geo-librarian-") as tmp:
        h = Harness(args.catalog.resolve(), Path(tmp), args.scoping, args.launch, args.bundles == "on")
        try:
            if args.mode == "smoke":
                smoke(h)
            elif args.mode == "bench":
                bench(h, args.model, out)
            else:
                run_probes(h, args.model, out, args.only)
        finally:
            h.close()
    if args.mode != "smoke":
        print(f"Results: {out}")


if __name__ == "__main__":
    main()
