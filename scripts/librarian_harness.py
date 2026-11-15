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
import sqlite3
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


def call_record(name,arguments,result):
    """Keep compact diagnostic evidence, including registry and nested wire errors."""
    body=result
    if isinstance(result,dict) and isinstance(result.get('content'),str):
        try:body=json.loads(result['content'])
        except (ValueError,TypeError):pass
    error=(body.get('error') or (body.get('result') or {}).get('error')) if isinstance(body,dict) else None
    code=error.get('code','') if isinstance(error,dict) else str(error or '')
    message=error.get('message','') if isinstance(error,dict) else str(result.get('detail') or result.get('message') or error or '')
    failed=bool(error or result.get('is_error') or result.get('refused'))
    coverage=[];raw=body.get('coverage',[]) if isinstance(body,dict) else []
    clipped=bool(body.get('coverage_truncated')) if isinstance(body,dict) else False
    if not isinstance(raw,list):raw=[];clipped=True
    for row in raw:
        if not isinstance(row,dict):clipped=True;continue
        if not all(k in row for k in ('entity_id','start_line','end_line','truncated','sha256')):clipped=True;continue
        eid=row.get('entity_id');start=row.get('start_line');end=row.get('end_line');sha=row.get('sha256')
        if not (isinstance(eid,str) and len(eid)<=200 and isinstance(sha,str) and re.fullmatch('[0-9a-f]{64}',sha)
                and type(row.get('truncated')) is bool and all(x is None or type(x) is int and x>=1 for x in (start,end))
                and ((start is None and end is None) or start is not None and end is not None and start<=end)):
            clipped=True;continue
        if len(coverage)==16:clipped=True;break
        coverage.append({k:row[k] for k in ('entity_id','start_line','end_line','truncated','sha256')})
        source=row.get('source')
        if isinstance(source,dict):
            if all(isinstance(source.get(k),str) and len(source[k])<=512 for k in ('repo_id','revision','rel_path')):
                coverage[-1]['source']={k:source[k] for k in ('repo_id','revision','rel_path')}
            else:clipped=True
    data=(body.get('result') or {}).get('data',{}) if isinstance(body,dict) else {}
    supplemental=[]
    for card in data.get('calls_constants',[]):
        eid=card.get('entity_id') if isinstance(card,dict) else None
        if isinstance(eid,str) and eid.startswith('entity:') and len(eid)<=200 and eid not in supplemental:
            if len(supplemental)==16:clipped=True;break
            supplemental.append(eid)
    recoveries=[];raw_recoveries=body.get('recoveries',[]) if isinstance(body,dict) else []
    for row in raw_recoveries[:8] if isinstance(raw_recoveries,list) else []:
        if not isinstance(row,dict) or not isinstance(row.get('pattern'),str) or row.get('pattern') not in {'FP'+str(n) for n in range(1,9)}:continue
        if row.get('outcome') not in {'resolved','unresolved'} or not isinstance(row.get('action'),str) or not isinstance(row.get('trigger_value'),dict):continue
        if len(json.dumps(row,ensure_ascii=False,default=str))<=2500:recoveries.append(row)
    encoded_arguments=json.dumps(arguments,ensure_ascii=False,default=str)
    consumed=body.get('recovery_steps_consumed',0) if isinstance(body,dict) else 0
    return dict(tool=name,arguments=encoded_arguments[:4096],arguments_truncated=len(encoded_arguments)>4096,
                recoveries=recoveries,recovery_steps_consumed=consumed if type(consumed) is int and 0<=consumed<=3 else 0,
                withheld=code=='EXTERNAL_RESULT_TOO_LARGE',
                error_code=code[:100],error_message=message[:300],success=not failed,
                coverage=coverage,coverage_truncated=clipped,supplemental_entities=supplemental)

ENV_FILE = Path(r"D:\Resource-Library\.utility\.env")
WHEEL_PYTHON = ROOT / "output" / "wheel-env" / "Scripts" / "python.exe"
SERVER = "geo"
PACKAGE_VERSION = "0.1.1"
PAID_PREFLIGHT = None
PAID_CONFIG = None
CORE = ["list_graphs", *("paper_" + t for t in probes.CORE)]

BENCH = [
    ("What do recent papers say about retrieval augmented generation? Summarise the main claims.", ["115"]),
    ("Which papers combine knowledge graphs with large language models? What specific techniques do they propose?", ["doc:1", "108"]),
    ("What token efficiency advantages do graph-based retrieval methods claim over dense vector search?", ["85"]),
    ("What graph neural network techniques appear in the corpus, and which papers use them?", ["229", "152"]),
    ("What are the main evaluation benchmarks used in papers about knowledge graph construction?", ["234"]),
]

CODE_BENCH = [
    ('What tool set may research helpers use? Cite the defining code.', ['HELPER_TOOLS']),
    ('What does delegate use to cap concurrent tier 1 helpers? Cite the code.', ['lead_agents']),
    ('How does the Clerk run and check one task? Cite the code.', ['run_one']),
    ('How are external MCP structured results bounded? Cite the code.', ['MAX_EXTERNAL_RESULT']),
    ('How does the loop choose its fallback context window? Cite the code.', ['DEFAULT_CONTEXT_TOKENS']),
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


def requested_graphs(arguments,labels,pinned):
    refs=[arguments[key] for key in ('graph_id','paper_graph','code_graph') if isinstance(arguments.get(key),str)]
    if isinstance(arguments.get('graph_ids'),list):refs.extend(ref for ref in arguments['graph_ids'] if isinstance(ref,str))
    if not refs and len(pinned)==1:refs=list(pinned)
    return list(dict.fromkeys(labels.get(ref,ref) for ref in refs))


class Harness:
    """`scoping="open"`: one connection that can reach every graph in the catalog.
    `scoping="library"`: one connection per library, pinned with --graph-id to that
    library's graph(s) - how a Librarian library would be configured in practice."""

    def __init__(self, catalog: Path, workdir: Path, scoping: str = "open", launch: str = "source",
                 bundles: bool = False, context_tokens: int | None = None, preset: str = 'papers',
                 graph_label: str = 'librarian-v2', wheel: Path | None = None, self_check: bool | None = None,
                 semantic_model: str | None = None, semantic_cache: Path | None = None, semantic_python: Path | None = None):
        from resource_librarian.mcp_client import external_result_limit
        if context_tokens is not None and (type(context_tokens) is not int or context_tokens < 1024):
            raise ValueError('context_tokens must be at least 1024')
        self.context_tokens = context_tokens
        self.route_policy = {} if context_tokens is None else {'context_tokens':context_tokens}
        self.preset = preset
        self.graph_label = graph_label
        self.self_check = self_check
        if bool(semantic_model)!=bool(semantic_cache):raise ValueError('Semantic model and cache must be configured together')
        self.limit_chars = external_result_limit(context_tokens)
        server_cap = str(self.limit_chars - 500)
        init(workdir / "vault", name="Geo-Grapher harness")
        self.vault = Vault(workdir / "vault")
        self.manager = McpManager(workdir / "config")
        self.corpora = probes.corpus_titles(catalog)
        self.labels = {v["graph_id"]: k for k, v in self.corpora.items()}
        with sqlite3.connect(catalog.resolve().as_uri()+'?mode=ro',uri=True) as con:
            self.labels.update({gid:label for gid,label in con.execute('SELECT graph_id,label FROM graphs')})
        ids = {label:gid for gid,label in self.labels.items()}
        if scoping == "library":
            servers = ({"geo_ai": [ids[probes.AI]], "geo_tl": [ids[probes.TL]], "geo_both": [ids[probes.AI], ids[probes.TL]]}
                       if preset == 'papers' else {'geo_code':[ids[graph_label]]})
        else:
            servers = {SERVER: []}
        self.tools: dict[str, dict[str, str]] = {}
        for name, allowed in servers.items():
            if launch == "uvx":
                # Exactly the Librarian curated entry: a pinned package, configured by env.
                source = str(wheel.resolve()) if wheel is not None else f'geo-grapher=={PACKAGE_VERSION}'
                if semantic_model:source=(str(wheel.resolve())+'[semantic]') if wheel is not None else f'geo-grapher[semantic]=={PACKAGE_VERSION}'
                definition = {"command": "uvx", "args": ["--from", source, "geographer",
                                                         "serve-graphs", "--transport", "stdio"],
                              "env": {"GEOGRAPHER_CATALOG": str(catalog), "GEOGRAPHER_GRAPHS": ",".join(allowed),
                                      "GEOGRAPHER_TOOLS": preset,
                                      "GEOGRAPHER_MAX_RESULT_CHARS": server_cap, "UV_FIND_LINKS": str(ROOT / "dist"),
                                      **({"UV_CACHE_DIR": os.environ["UV_CACHE_DIR"]} if os.environ.get("UV_CACHE_DIR") else {})}}
                if wheel is not None:
                    definition['args']=['--refresh-package','geo-grapher',*definition['args']]
                if semantic_model:
                    definition['args']=['--python',str(semantic_python or Path(sys.executable)),*definition['args']]
                    definition['env'].update(GEOGRAPHER_SEMANTIC_MODEL=semantic_model,GEOGRAPHER_SEMANTIC_CACHE=str(semantic_cache.resolve()))
                if not allowed:
                    definition["env"].pop("GEOGRAPHER_GRAPHS")
            else:
                # Librarian withholds structured results over 8,000 chars; page under that instead.
                args = ["-m", "geographer", "serve-graphs", "--catalog", str(catalog), "--transport", "stdio",
                        "--max-result-chars", server_cap, "--tools", preset]
                for gid in allowed:
                    args += ["--graph-id", gid]
                definition = {"command": str(WHEEL_PYTHON), "args": args,
                              "env": {"PYTHONPATH": f"{ROOT / 'src'};{ROOT}"}, "cwd": str(ROOT)}
                if semantic_model:
                    definition['command']=str(semantic_python or WHEEL_PYTHON)
                    definition['env'].update(GEOGRAPHER_SEMANTIC_MODEL=semantic_model,GEOGRAPHER_SEMANTIC_CACHE=str(semantic_cache.resolve()))
            self.manager.set_server(name, definition)
            self.manager.accept(name)
        self.server_graphs = {name: list(allowed) for name, allowed in servers.items()}
        status = self.manager.sync()
        for name in servers:
            if not status[name]["connected"]:
                raise SystemExit(f"Librarian could not connect to {name}: {status[name]['error']}")
            self.tools[name] = {n.split("__", 2)[2]: n for n in self.manager.tool_names(name)}
            required = ('list_graphs', 'paper_search_documents', 'paper_get_document') if preset == 'papers' else ('list_graphs','search_entities','get_entity_content')
            missing = [t for t in required if t not in self.tools[name]]
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
        if self.preset != 'papers':return 'geo_code'
        return {probes.AI: "geo_ai", probes.TL: "geo_tl", None: "geo_both"}[graph_label]

    def close(self) -> None:
        self.manager.stop()

    def call(self, tool: str, arguments: dict, server: str | None = None) -> dict:
        return REGISTRY.call(self.tools[server or next(iter(self.tools))][tool], arguments,
                             Context(tier="contribute",extras={'external_result_limit':self.limit_chars}))

    def run(self, provider, prompt: str, max_steps: int = 12, server: str | None = None, research_question: str | None = None) -> dict:
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
            selected = CORE if self.preset == 'papers' else sorted(self.tools[server or next(iter(self.tools))])
            loop.only = frozenset(self.tools[server or next(iter(self.tools))][t] for t in selected
                                  if t in self.tools[server or next(iter(self.tools))])
        loop.context_limit = self.route_policy.get('context_tokens',0)
        if research_question is not None:loop.ctx.extras['research_question']=research_question
        if self.preset!='papers':
            from resource_librarian.agent_runtime import AgentProfile, DEFAULT_PROFILES, ProfileStore
            values=DEFAULT_PROFILES['code-research'].public()
            values['route_policy']=dict(values['route_policy'])
            if self.self_check is not None:values['route_policy']['answer_self_check']=self.self_check
            loop.configure_profile(AgentProfile(**values).validate())
            loop.ctx.extras['agent_profile']='code-research'
            loop.ctx.extras['profile_store']=ProfileStore(self.vault)
        hidden = self._only_server(server or next(iter(self.tools))) if self.bundles else []
        self.current_loop=loop
        try:
            offered = sorted(t.name for t in loop.tools() if t.name.startswith("mcp__"))
            start = time.monotonic()
            turn = loop.send(prompt)
        finally:
            for spec in hidden:
                REGISTRY.register(spec)
        retrieved: dict[str, set[int]] = {label: set() for label in sorted(set(self.labels.values()))}
        graphs_called, tool_text, withheld, errors, blocked, bundle_refused = [], [], 0, 0, 0, 0
        pending_graph = None
        pinned = self.server_graphs.get(server or next(iter(self.tools)), [])
        ids_by_label = {label:gid for gid,label in self.labels.items()}
        per_call=[];pending_name='';pending_arguments={}
        for event in events:
            if event["type"] == "tool_call":
                pending_name=event.get('tool') or event.get('name') or ''
                pending_arguments=event.get('arguments') or {}
                refs=requested_graphs(event.get('arguments') or {},ids_by_label,pinned)
                graphs_called.extend(refs)
                pending_graph=refs[0] if len(refs)==1 else None
            elif event["type"] == "tool_result":
                result = event.get("result") or {}
                per_call.append(call_record(event.get('tool') or pending_name,pending_arguments,result))
                content = str(result.get("content") or "")
                if per_call[-1]['withheld']:
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
        from collections import Counter
        reasons=Counter((c['error_code']+': '+c['error_message']) for c in per_call if not c['success'])
        return dict(answer=(turn.reply or "").strip(), steps=turn.steps, stopped=turn.stopped,
                    production_profile=loop.profile_id,temperature=loop.profile_temperature,
                    requested_self_check=self.self_check,
                    self_check_enabled=loop.profile_answer_self_check,
                    self_check_rejected=sum(e.get('type')=='answer_self_check' and e.get('reason')=='unsupported_citation' for e in events),
                    self_check_calls=sum(e.get('type')=='answer_self_check' and e.get('attempted',False) for e in events),
                    completed_at_step_limit=turn.completed_at_step_limit,
                    recoveries=turn.recoveries,first_attempt=turn.first_attempt,
                    recovery_episode_id=turn.recovery_episode_id,
                    recovery_steps=turn.recovery_steps,recovery_model_calls=turn.recovery_model_calls,
                    per_call=per_call,top_error_reasons=[dict(reason=k,count=v) for k,v in reasons.most_common(5)],
                    failure_category=turn.failure_category, error=turn.error[:300],
                    tool_calls=len(turn.calls), tool_errors=errors, withheld_oversize=withheld, blocked_by_allow_list=blocked,
                    bundle_refused=bundle_refused, outside_tools_offered=offered,
                    librarian_tools_used=sorted({c["tool"] for c in turn.calls if not c["tool"].startswith("mcp__")}),
                    graphs_called=graphs_called, retrieved={k: sorted(v) for k, v in retrieved.items()},
                    tool_text="\n".join(tool_text), elapsed_seconds=round(time.monotonic() - start, 1))


def provider_for(model: str):
    from eval_readiness import require
    require(PAID_PREFLIGHT,PAID_CONFIG)
    return providers.from_settings({"provider": "deepinfra", "model": model, "timeout": 180})


def smoke(h: Harness) -> None:
    if h.preset != 'papers':
        for server in h.tools:
            out=h.call('list_graphs',{},server)
            assert not out.get('is_error') and not out.get('error'), out
            print(f'{server}: preset={h.preset} tools={len(h.tools[server])} limit_chars={h.limit_chars}')
        return
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
              f"hits={len(body.get('result', {}).get('results', []))} withheld={call_record('paper_search_documents',{},out)['withheld']}")
    print("tools offered:", sorted(h.tools))


def bench(h: Harness, model: str, out: Path, resume: bool = False) -> None:
    provider = provider_for(model)
    results = json.loads(out.read_text(encoding='utf-8')) if resume and out.exists() else []
    code = h.preset != 'papers'
    target = h.graph_label if code else probes.AI
    target_id = next((gid for gid,label in h.labels.items() if label == target),None)
    if target_id is None:raise ValueError(f'Benchmark graph {target!r} is unavailable')
    workflow = 'Discover list_graphs, then use graph-local search and source content; cite returned handles exactly.' if code else WORKFLOW
    for question, markers in CODE_BENCH if code else BENCH:
        if any(r['question']==question for r in results):continue
        prompt = f"Graph: '{target}'. {workflow}\n\nQuestion: {question}"
        r = h.run(provider, prompt, server=h.server_for(None if code else probes.AI),research_question=question if code else None)
        r.update(question=question, model=model, markers=markers,
                 markers_found=[m for m in markers if m in r["answer"]],
                 wrong_graph_calls=sum(g != target_id for g in r["graphs_called"]),
                 benchmark='code' if code else 'papers',context_tokens=h.context_tokens,preset=h.preset)
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


def question_batch(args, out: Path, provider_override=None) -> None:
    """Collect a blind question batch; never read an answer key or print answers."""
    if out.exists() or args.resume:raise SystemExit('Preserve the first blind batch; no replacement or resume')
    questions=json.loads(args.question_file.read_text(encoding='utf-8'))
    if not 1<=len(questions)<=200 or len({q['id'] for q in questions})!=len(questions):raise SystemExit('Expected unique registered question IDs')
    provider=provider_override if provider_override is not None else provider_for(args.model)
    results=[];current=None;h=None
    workflow='Discover list_graphs, then use graph-local search and source content; cite returned handles exactly.'
    with tempfile.TemporaryDirectory(prefix='geo-quality-blind-') as tmp:
        try:
            for index,q in enumerate(questions,1):
                if q['graph']!=current:
                    if h is not None:h.close();h=None
                    h=Harness(args.catalog.resolve(),Path(tmp)/f'block-{index}',args.scoping,args.launch,
                              args.bundles=='on',args.context_tokens,args.preset,q['graph'],args.wheel,
                              None if args.self_check is None else args.self_check=='on',
                              **semantic_options(args))
                    current=q['graph']
                target_id=next(gid for gid,label in h.labels.items() if label==current)
                result=h.run(provider,f"Graph: '{current}'. {workflow}\n\nQuestion: {q['question']}",server=h.server_for(None),research_question=q['question'])
                result.pop('tool_text')
                result.update(question_id=q['id'],question=q['question'],graph=current,model=args.model,
                              wrong_graph_calls=sum(g!=target_id for g in result['graphs_called']),
                              benchmark='sealed-heldout',context_tokens=h.context_tokens,preset=h.preset)
                results.append(result)
                out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
                print(json.dumps(dict(collected=index,total=len(questions),question_id=q['id'])),flush=True)
        finally:
            if h is not None:h.close()


def run_probes(h: Harness, model: str, out: Path, only: str | None, resume: bool = False) -> None:
    provider = provider_for(model)
    chosen = [p for p in probes.PROBES if not only or p["kind"] in only.split(",")]
    results = json.loads(out.read_text(encoding='utf-8')) if resume and out.exists() else []
    for probe in chosen:
        if any((r['kind'],r['graph'],r['question'])==(probe['kind'],probe['graph'],probe['q']) for r in results):continue
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


def semantic_options(args):
    return {key:getattr(args,key) for key in ('semantic_model','semantic_cache','semantic_python') if getattr(args,key,None) is not None}


def main() -> None:
    global PAID_PREFLIGHT,PAID_CONFIG
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["smoke", "bench", "probes"])
    parser.add_argument("--catalog", type=Path, default=ROOT / "output" / "phase-b" / "catalog.sqlite")
    parser.add_argument("--model", default="Qwen/Qwen3-32B")
    parser.add_argument('--context-tokens',type=int,help='Declared route context window; unknown preserves the 128k fallback')
    parser.add_argument('--preset',choices=['lead','code','papers','cross'],default='papers')
    parser.add_argument('--graph-label',default='librarian-v2',help='Code benchmark graph; code facts have their own denominator')
    parser.add_argument('--wheel',type=Path,help='Exact local wheel for uvx verification, avoiding a stale same-version cached build')
    parser.add_argument('--resume',action='store_true',help='Keep completed first attempts and continue an interrupted benchmark/probe file')
    parser.add_argument('--question-file',type=Path,help='Sealed blind questions only; no answer key is accepted')
    parser.add_argument('--self-check',choices=['on','off'],help='Evaluation override; omitted uses production policy')
    parser.add_argument('--semantic-model',help='Explicit local-only optional encoder, identical to production server configuration')
    parser.add_argument('--semantic-cache',type=Path,help='Prebuilt immutable derived-analysis sidecar')
    parser.add_argument('--semantic-python',type=Path,help='Pin the interpreter used to build the semantic namespace')
    parser.add_argument('--dry-run',action='store_true',help='Execute the mandatory real-tool scripted preflight and stop without loading credentials')
    parser.add_argument("--out", type=Path)
    parser.add_argument("--only", help="comma-separated probe kinds")
    parser.add_argument("--scoping", choices=["open", "library"], default="open",
                        help="open: one connection to every graph; library: per-library connections pinned with --graph-id")
    parser.add_argument("--launch", choices=["source", "uvx"], default="source",
                        help="source: this checkout under wheel-env; uvx: the pinned package from dist/ (the curated entry)")
    parser.add_argument("--bundles", choices=["off", "on"], default="off",
                        help="on: the app's own compact tool bundles inside an explore session (outside tools via bundle policy)")
    args = parser.parse_args()
    out = args.out or ROOT / "output" / "librarian" / f"{args.mode}-{args.scoping}-{args.model.split('/')[-1]}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.mode!='smoke':
        from eval_dryrun import preflight
        PAID_PREFLIGHT,PAID_CONFIG=preflight(args,out)
        if args.dry_run:return
        load_key()
    if args.question_file:
        if args.mode!='bench' or args.preset!='lead' or args.scoping!='library':raise SystemExit('Blind cycle requires the registered library-scoped lead preset')
        question_batch(args,out)
        return
    with tempfile.TemporaryDirectory(prefix="geo-librarian-") as tmp:
        h = Harness(args.catalog.resolve(), Path(tmp), args.scoping, args.launch, args.bundles == "on",args.context_tokens,args.preset,args.graph_label,args.wheel,
                    None if args.self_check is None else args.self_check=='on',**semantic_options(args))
        try:
            if args.mode == "smoke":
                smoke(h)
            elif args.mode == "bench":
                bench(h, args.model, out,args.resume)
            else:
                run_probes(h, args.model, out, args.only,args.resume)
        finally:
            h.close()
    if args.mode != "smoke":
        print(f"Results: {out}")


if __name__ == "__main__":
    main()
