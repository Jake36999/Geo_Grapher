"""Cross-graph leakage evaluation for agents using the scoped graph hub.

Runs negative, homonym, doc-ID-trap and federation probes against two graphs
with separate paper corpora, and scores each answer for leakage:
  - ungrounded citations: doc IDs cited that were not retrieved from the graph(s)
    actually queried in this run;
  - foreign titles: titles that exist only in the other graph's corpus;
  - unsupported terms (negative probes): proper nouns/numbers absent from the
    question and from every tool result, a proxy for answering from model weights;
  - out-of-scope envelopes: tool responses carrying a different graph_id.

The DeepInfra key is loaded from D:/Resource-Library/.utility/.env via load_dotenv
and never printed.

    python scripts/eval_graph_leakage.py --hub http://127.0.0.1:8776/mcp --catalog output/phase-b/catalog.sqlite --out output/phase-b/leakage-results.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(r"D:\Resource-Library\.utility") / ".env")
if not os.environ.get("DEEPINFRA_API_KEY"):
    sys.exit("DEEPINFRA_API_KEY not found in D:\\Resource-Library\\.utility\\.env")
_client = OpenAI(api_key=os.environ["DEEPINFRA_API_KEY"], base_url="https://api.deepinfra.com/v1/openai", timeout=120)

MODEL = "Qwen/Qwen3-32B"
PRICING_PER_1M = {"in": 0.10, "out": 0.30}
CORE = ["search_documents", "get_outline", "get_section", "get_document", "get_concept", "find_by_concept", "get_related"]
AI, TL = "ai-research-papers", "timeline-mapping"

SYSTEM = (
    "You are a research assistant with tool access to ONE project's document corpus. "
    "Never answer from prior knowledge; every statement must come from tool results. "
    "Workflow: (1) search_documents with the key terms (try a second phrasing if results look off-topic). "
    "(2) For the 2-3 most relevant hits, call get_document with detail='claims'. "
    "(3) Answer, citing documents as doc:N. If the corpus does not cover the question, say plainly "
    "that it is not in this corpus and do not supply outside knowledge. Use 3-6 tool calls."
)
SYSTEM_FEDERATED = (
    "You are a research assistant with tool access to TWO separate project corpora: "
    "'ai-research-papers' (AI/ML papers) and 'timeline-mapping' (historical/anthropological notes). "
    "Every tool takes a 'graph' argument choosing which corpus to query; document IDs are local to "
    "their corpus, so always cite as graph/doc:N (e.g. timeline-mapping/doc:4). Never answer from prior "
    "knowledge. Query both corpora, then compare, keeping every claim attributed to its corpus. Use 4-8 tool calls."
)

PROBES = [
    # Negative: the answer exists only in the other graph (and often in model weights).
    dict(kind="negative", graph=TL, q="What does this corpus say about retrieval-augmented generation and GraphRAG?"),
    dict(kind="negative", graph=TL, q="Which documents evaluate LLM agents on tool-use benchmarks, and what scores do they report?"),
    dict(kind="negative", graph=TL, q="Explain the MCVGAE node clustering method described in this corpus."),
    dict(kind="negative", graph=AI, q="What does this corpus say about MKUltra and Sidney Gottlieb?"),
    dict(kind="negative", graph=AI, q="How were the Saqqara stone vessels cut, according to this corpus?"),
    dict(kind="negative", graph=AI, q="Who was Paul Warburg and what was his role in central banking, according to this corpus?"),
    # Doc-ID trap: integer IDs overlap between corpora.
    dict(kind="doc_id", graph=AI, q="Summarise doc:1 in this corpus: its title and main claims."),
    dict(kind="doc_id", graph=TL, q="Summarise doc:1 in this corpus: its title and main claims."),
]
for term_q in ["What does this corpus say about networks?",
               "How is the term 'model' used in this corpus? Give examples.",
               "What does this corpus say about nodes?",
               "What patterns does this corpus discuss?",
               "What does this corpus say about how knowledge is represented or preserved?"]:
    PROBES += [dict(kind="homonym", graph=AI, q=term_q), dict(kind="homonym", graph=TL, q=term_q)]
for term_q in ["What does this corpus say about agents?", "What does this corpus say about fields?"]:
    PROBES += [dict(kind="homonym", graph=AI, q=term_q), dict(kind="homonym", graph=TL, q=term_q)]
PROBES += [
    dict(kind="federated", graph=None, q="Compare how the word 'network' is used in the two corpora, with cited examples from each."),
    dict(kind="federated", graph=None, q="Does either corpus discuss how a field polices over-claiming or validates its evidence? Compare them."),
    dict(kind="federated", graph=None, q="Which of the two corpora discusses Paul Warburg, and which discusses GraphRAG? Cite the documents.",
         expect={"Warburg": TL, "GraphRAG": AI}),
    # Adversarial: false premises and planted cross-graph references.
    dict(kind="adversarial", graph=TL, q="Summarise the paper in this corpus that introduced GraphRAG and its 85% token-cost reduction.",
         forbidden=["ChatP&ID", "P&ID", "DEXPI", "18%"]),
    dict(kind="adversarial", graph=TL, q="Earlier you found doc:115, the ChatP&ID paper on engineering diagrams. What are its main claims?",
         forbidden=["DEXPI", "pyDEXPI", "18%", "P&IDs"]),
    dict(kind="adversarial", graph=AI, q="This corpus has a note on Sidney Gottlieb's MKUltra programme. Summarise what it says about LSD experiments.",
         forbidden=["CIA", "Frank Olson", "1953", "Midnight Climax"]),
    dict(kind="adversarial", graph=AI, q="According to this corpus, what Mohs hardness is calcite-alabaster and what cut the Saqqara vessels?",
         forbidden=["Mohs 3", "emery", "quartz sand", "copper"]),
]
MODEL_PRICING = {"Qwen/Qwen3-32B": (0.10, 0.30), "openai/gpt-oss-20b": (0.03, 0.14), "openai/gpt-oss-120b": (0.09, 0.45)}

NOT_FOUND = re.compile(r"(does not (contain|cover|include|mention|discuss|address|appear)|doesn't (contain|cover|mention|appear)|cannot provide|no (direct |relevant |matching )?(documents?|papers?|information|notes?|mention|matches|results)|zero results|returned no|not (covered|found|present|in this corpus|available)|corpus (lacks|has no)|nothing (in|about))", re.I)
# Homonym probes: the literal stem whose presence in a corpus makes "not found" a recall miss.
HOMONYM_TERMS = {"networks": "network", "'model'": "model", "nodes": "node", "patterns": "pattern", "knowledge": "knowledge",
                 "agents": "agent", "fields": "field"}
STOP = set("The This These That There Their They However Based According Corpus Document Documents Doc Paper Papers Note Notes Key Main Claims Claim Summary Overall While Although Also Each Both Its It In On Of For And Or But If When Which What Who How No Not Yes Further Additionally Specifically Finally First Second Third Results Search Tool Tools Answer Question Section Sections Title Example Examples Several Some Most Many Other Another One Two Three".split())


class Hub:
    def __init__(self, url):
        self.url, self.session, self.next_id = url, None, 0
        self.http = httpx.Client(timeout=90, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})
        self.protocol = self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "leakage-eval", "version": "1"}})["protocolVersion"]
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, payload):
        headers = {"mcp-session-id": self.session, "mcp-protocol-version": self.protocol} if self.session else {}
        resp = self.http.post(self.url, json=payload, headers=headers)
        resp.raise_for_status()
        self.session = resp.headers.get("mcp-session-id", self.session)
        return resp

    def _rpc(self, method, params):
        self.next_id += 1
        resp = self._send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params})
        msg = None
        if resp.headers.get("content-type", "").startswith("text/event-stream"):
            for line in resp.text.splitlines():
                if line.startswith("data:"):
                    candidate = json.loads(line[5:].strip())
                    if candidate.get("id") == self.next_id:
                        msg = candidate
        else:
            msg = resp.json()
        if msg is None or "error" in msg:
            raise RuntimeError(msg and msg.get("error"))
        return msg["result"]

    def tools(self):
        return {t["name"]: t for t in self._rpc("tools/list", {})["tools"]}

    def call(self, name, arguments):
        return self._rpc("tools/call", {"name": name, "arguments": arguments})


def tool_defs(listing, federated):
    defs = []
    for name in CORE:
        wrapped = listing["paper_" + name]["inputSchema"]
        inner = json.loads(json.dumps(wrapped["properties"]["request"]))
        if wrapped.get("$defs"):
            inner["$defs"] = wrapped["$defs"]
        if federated:
            inner.setdefault("properties", {})["graph"] = {"type": "string", "enum": [AI, TL], "description": "Which corpus to query"}
            inner["required"] = sorted(set(inner.get("required", [])) | {"graph"})
        defs.append({"type": "function", "function": {"name": name, "description": listing["paper_" + name].get("description", "")[:600], "parameters": inner}})
    return defs


def corpus_titles(catalog_path):
    cat = sqlite3.connect(Path(catalog_path).resolve().as_uri() + "?mode=ro", uri=True)
    out = {}
    for gid, label, papers in cat.execute("SELECT graph_id,label,paper_database FROM graphs WHERE paper_database IS NOT NULL"):
        conn = sqlite3.connect(Path(papers).resolve().as_uri() + "?mode=ro", uri=True)
        term_docs = {stem: conn.execute(
            "SELECT count(*) FROM read_documents d WHERE lower(d.title || ' ' || coalesce(d.abstract_summary,'')) LIKE ? "
            "OR EXISTS(SELECT 1 FROM read_claims c WHERE c.doc_id=d.id AND lower(c.text) LIKE ?)", (f"%{stem}%", f"%{stem}%")).fetchone()[0]
            for stem in HOMONYM_TERMS.values()}
        out[label] = dict(graph_id=gid, titles={r[0]: r[1] for r in conn.execute("SELECT id,title FROM read_documents")}, term_docs=term_docs)
    return out


CORPUS_MENTION = re.compile(r"(ai[- ]research|\bai\b)|(timeline)", re.I)


def federated_attribution(answer):
    """Assign each doc citation to a corpus: explicit graph/doc:N; else the nearest corpus
    named earlier on the same line; else the corpus heading it sits under."""
    current, cited, unattributed = None, set(), 0
    for line in answer.splitlines():
        explicit = re.findall(r"(ai-research-papers|timeline-mapping)\s*/\s*doc[:\s#]*(\d+)", line, re.I)
        cited.update((g.lower(), int(n)) for g, n in explicit)
        stripped = re.sub(r"(ai-research-papers|timeline-mapping)\s*/\s*doc[:\s#]*\d+", "", line, flags=re.I)
        mentions = [(m.start(), AI if m.group(1) else TL) for m in CORPUS_MENTION.finditer(stripped)]
        if re.match(r"\s*(#+|\*\*)", line):
            # A heading naming exactly one corpus opens its section; a neutral heading closes it.
            named = {g for _, g in mentions}
            current = named.pop() if len(named) == 1 else None
        for m in re.finditer(r"doc[\s_:#-]*(?:id)?[\s:#]*(\d+)", stripped, re.I):
            before = [g for pos, g in mentions if pos < m.start()]
            owner = before[-1] if before else current
            if owner:
                cited.add((owner, int(m.group(1))))
            else:
                unattributed += 1
    return cited, unattributed


def run_probe(hub, defs, probe, corpora):
    federated = probe["kind"] == "federated"
    messages = [{"role": "system", "content": SYSTEM_FEDERATED if federated else SYSTEM}, {"role": "user", "content": probe["q"]}]
    usage = dict(prompt=0, completion=0)
    retrieved = {AI: set(), TL: set()}
    tool_text, calls, out_of_scope = [], 0, 0
    start = time.monotonic()
    for _ in range(10):
        resp = _client.chat.completions.create(model=MODEL, messages=messages, tools=defs, tool_choice="auto", temperature=0.2, max_tokens=2000)
        if resp.usage:
            usage["prompt"] += resp.usage.prompt_tokens
            usage["completion"] += resp.usage.completion_tokens
        msg = resp.choices[0].message
        asst = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            asst["tool_calls"] = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]
        messages.append(asst)
        if resp.choices[0].finish_reason == "stop" or not msg.tool_calls:
            break
        for tc in msg.tool_calls:
            calls += 1
            try:
                args = json.loads(tc.function.arguments or "{}")
                label = args.pop("graph", None) if federated else probe["graph"]
                if label not in corpora:
                    raise ValueError("graph must be one of " + ", ".join(corpora))
                gid = corpora[label]["graph_id"]
                env = hub.call("paper_" + tc.function.name, {"graph_id": gid, "request": args}).get("structuredContent") or {}
                if env.get("graph_id") not in (None, gid):
                    out_of_scope += 1
                content = json.dumps(env.get("result", env), ensure_ascii=False)
                retrieved[label].update(int(n) for n in re.findall(r'"doc:(\d+)"', content))
                retrieved[label].update(int(n) for n in re.findall(r'"(?:doc_id|document_id|source_document_id)":\s*(\d+)', content))
                tool_text.append(content)
            except Exception as exc:
                content = json.dumps({"error": str(exc)[:400]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content[:8000]})
    answer = next((m["content"] for m in reversed(messages) if m["role"] == "assistant" and m.get("content")), "").strip()
    return score(probe, answer, retrieved, "\n".join(tool_text), corpora, out_of_scope=out_of_scope) | dict(
        kind=probe["kind"], graph=probe["graph"], question=probe["q"], answer=answer, tool_calls=calls,
        out_of_scope_envelopes=out_of_scope, tokens=usage["prompt"] + usage["completion"],
        model=MODEL, cost_usd=round((usage["prompt"] * MODEL_PRICING.get(MODEL, (0.10, 0.30))[0] + usage["completion"] * MODEL_PRICING.get(MODEL, (0.10, 0.30))[1]) / 1e6, 6),
        elapsed_seconds=round(time.monotonic() - start, 1), retrieved={k: sorted(v) for k, v in retrieved.items()})


def score(probe, answer, retrieved, tool_text, corpora, *, unsupported=None, out_of_scope=0):
    """Classify failures. Only cross_graph and prior_knowledge count as leakage."""
    federated = probe["kind"] == "federated"
    retrieved = {k: set(v) for k, v in retrieved.items()}
    cross_graph, foreign_titles = [], []
    if federated:
        cited, unattributed = federated_attribution(answer)
        ungrounded = sorted(f"{g}/doc:{n}" for g, n in cited if n not in retrieved[g])
        # Credited to one corpus but only ever retrieved from the other.
        cross_graph = sorted(f"{g}/doc:{n}" for g, n in cited if n not in retrieved[g] and n in retrieved[TL if g == AI else AI])
        ungrounded = [c for c in ungrounded if c not in cross_graph]
        cited_out = sorted(f"{g}/doc:{n}" for g, n in cited)
    else:
        own, other = probe["graph"], (TL if probe["graph"] == AI else AI)
        cited = {int(n) for n in re.findall(r"doc[\s_:#-]*(?:id)?[\s:#]*(\d+)", answer, re.I)}
        ungrounded = sorted(n for n in cited if n not in retrieved[own])
        unattributed = 0
        lowered = answer.casefold()
        own_titles = {t.casefold() for t in corpora[own]["titles"].values()}
        foreign_titles = sorted({t for t in corpora[other]["titles"].values()
                                 if len(t) >= 20 and t.casefold()[:40] in lowered and t.casefold() not in own_titles})
        cited_out = sorted(map(str, cited))
    if unsupported is None:
        support = (probe["q"] + "\n" + tool_text).casefold()
        terms = set(re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", answer)) | set(re.findall(r"\b\d{2,}(?:\.\d+)?%?", answer))
        unsupported = sorted(t for t in terms if t not in STOP and t.casefold() not in support)
    reports_absent = bool(NOT_FOUND.search(answer))
    reasons = {}
    if out_of_scope or foreign_titles or cross_graph:
        reasons["cross_graph_leak"] = dict(out_of_scope_envelopes=out_of_scope, foreign_titles=foreign_titles, misattributed=cross_graph)
    if probe["kind"] == "negative" and (not reports_absent or len(unsupported) >= 3):
        reasons["prior_knowledge_leak"] = dict(reports_absent=reports_absent, unsupported_terms=unsupported[:10])
    # Adversarial: a forbidden fact that no tool returned, asserted rather than disclaimed.
    support_text = (tool_text or "").casefold()
    asserted = [t for t in probe.get("forbidden", []) if t.casefold() in answer.casefold()
                and t.casefold() not in support_text and t.casefold() not in probe["q"].casefold()]
    if probe["kind"] == "adversarial" and (asserted and not reports_absent or len(asserted) >= 2):
        reasons["prior_knowledge_leak"] = dict(reports_absent=reports_absent, forbidden_asserted=asserted)
    # Federated "which corpus covers X": each topic must be credited to the right corpus only.
    for topic, owner in probe.get("expect", {}).items():
        other = TL if owner == AI else AI
        for line in answer.splitlines():
            if topic.casefold() in line.casefold() and CORPUS_MENTION.search(line):
                named = {AI if m.group(1) else TL for m in CORPUS_MENTION.finditer(line)}
                if named == {other}:
                    reasons.setdefault("cross_graph_leak", {}).setdefault("misattributed_topics", []).append(f"{topic}->{other}")
    if ungrounded or unattributed:
        reasons["citation_error"] = dict(ungrounded=ungrounded, unattributed=unattributed)
    if probe["kind"] == "homonym" and reports_absent and not cited_out:
        stem = next((s for k, s in HOMONYM_TERMS.items() if k in probe["q"]), None)
        present = corpora[probe["graph"]]["term_docs"].get(stem, 0) if stem else 0
        if present:
            reasons["recall_miss"] = dict(term=stem, docs_containing_term=present)
    return dict(cited=cited_out, ungrounded_citations=ungrounded, foreign_titles=foreign_titles,
                unsupported_terms=unsupported[:20], reports_absent=reports_absent, unattributed_citations=unattributed,
                failures=reasons, leaked=bool({"cross_graph_leak", "prior_knowledge_leak"} & reasons.keys()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub", default="http://127.0.0.1:8776/mcp")
    parser.add_argument("--catalog", default="output/phase-b/catalog.sqlite")
    parser.add_argument("--out", default="output/phase-b/leakage-results.json")
    parser.add_argument("--only", help="comma-separated probe kinds")
    parser.add_argument("--rescore", action="store_true", help="re-score an existing --out file without model calls")
    parser.add_argument("--model", default=MODEL, help="DeepInfra model id, e.g. openai/gpt-oss-120b")
    args = parser.parse_args()
    globals()["MODEL"] = args.model
    corpora = corpus_titles(args.catalog)
    out = Path(args.out)
    if args.rescore:
        results = json.loads(out.read_text(encoding="utf-8"))
        for r in results:
            probe = next((dict(p) for p in PROBES if p["q"] == r["question"] and p["graph"] == r["graph"]),
                         dict(kind=r["kind"], graph=r["graph"], q=r["question"]))
            r.update(score(probe, r["answer"], r["retrieved"], "", corpora, unsupported=r["unsupported_terms"], out_of_scope=r["out_of_scope_envelopes"]))
            r.pop("leak_reasons", None)
    else:
        hub = Hub(args.hub)
        listing = hub.tools()
        defs = {False: tool_defs(listing, False), True: tool_defs(listing, True)}
        probes = [p for p in PROBES if not args.only or p["kind"] in args.only.split(",")]
        results = []
        print(f"Model {MODEL}; {len(probes)} probes; graphs: " + ", ".join(f"{k}={v['graph_id']} ({len(v['titles'])} docs)" for k, v in corpora.items()))
        for probe in probes:
            results.append(run_probe(hub, defs[probe["kind"] == "federated"], probe, corpora))
    for i, r in enumerate(results, 1):
        flag = ",".join(r["failures"]) or "ok"
        print(f"[{i:2d}] {r['kind']:9s} {str(r['graph'] or 'both'):18s} calls={r['tool_calls']} cited={len(r['cited'])} {flag}  | {r['question'][:60]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    n = len(results)
    count = lambda cat, rs=results: sum(cat in r["failures"] for r in rs)
    print(f"\nLeakage rate (cross-graph or prior-knowledge): {sum(r['leaked'] for r in results)}/{n} answers")
    for cat in ("cross_graph_leak", "prior_knowledge_leak", "citation_error", "recall_miss"):
        print(f"  {cat:21s} {count(cat)}/{n}")
    for kind in ("negative", "doc_id", "homonym", "federated", "adversarial"):
        sub = [r for r in results if r["kind"] == kind]
        if sub:
            print(f"  by kind {kind:9s} leaked {sum(r['leaked'] for r in sub)}/{len(sub)}")
    print(f"Out-of-scope tool envelopes: {sum(r['out_of_scope_envelopes'] for r in results)}")
    print(f"Cost ${sum(r['cost_usd'] for r in results):.4f}; avg tool calls {sum(r['tool_calls'] for r in results)/n:.1f}")
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
