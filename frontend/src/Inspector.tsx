import { useEffect, useRef, useState } from "react";
import type {
  NodeRecord,
  RelationshipSummary,
  ViewportFrameData,
  WitnessRecord,
  EvidenceHandle,
  GetArchitectureContextData,
  GetEntityContentData,
  ConformanceFinding,
  BudgetReport,
} from "../../contracts/geographer.wire";
import {
  base,
  budget,
  defaultFilter,
  json,
  query,
  shortName,
  type Node,
  type Snapshot,
} from "./api";
import type { Filter } from "../../contracts/geographer.wire";
import Investigation from "./Investigation";
import type { RelationshipSummary as ActorRelationship } from "../../contracts/v1.1/geographer.wire";

interface Props {
  snapshot: Snapshot;
  node?: Node;
  frame?: ViewportFrameData;
  edge?: RelationshipSummary;
  nodes: Record<string, Node>;
  filter: Filter;
  models: { digest: string; world_policy: string }[];
  onNodes: (nodes: Node[]) => void;
  onSelect: (id: string) => void;
  onEnter: (id: string) => void;
  onEdge: (id: string) => void;
  onStatus: (message: string) => void;
  pinned: boolean;
  onTogglePin: () => void;
  scopeReady: boolean;
  modelDigest: string;
  pins: string[];
  onPath: (relationshipIds: string[], entities: string[]) => void;
  violations?: string[];
}
type Tab =
  "overview" | "relationships" | "evidence" | "agent" | "investigation";
export default function Inspector({
  snapshot,
  node,
  frame,
  edge,
  nodes,
  filter,
  models,
  onNodes,
  onSelect,
  onEnter,
  onEdge,
  onStatus,
  pinned,
  onTogglePin,
  scopeReady,
  modelDigest,
  pins,
  onPath,
  violations = [],
}: Props) {
  const [impactDirection, setImpactDirection] = useState<
    "incoming" | "outgoing"
  >("incoming");
  const [agentVersion, setAgentVersion] = useState<"1.0" | "1.1">("1.1");
  const [tab, setTab] = useState<Tab>("overview"),
    [witnesses, setWitnesses] = useState<WitnessRecord[]>([]),
    [evidence, setEvidence] = useState<EvidenceHandle[]>([]),
    [witnessCursor, setWitnessCursor] = useState<string | null>(null);
  const [content, setContent] = useState<GetEntityContentData>(),
    [context, setContext] = useState<unknown>(),
    [contextData, setContextData] = useState<GetArchitectureContextData>();
  const [agentBudget, setAgentBudget] = useState(8192),
    [encoding, setEncoding] = useState<"o200k_base" | "cl100k_base">(
      "o200k_base",
    ),
    [qi, setQi] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  const [diagnostics, setDiagnostics] = useState<{
    boundary: {
      mode: string;
      ratio: number | null;
      cut_weight: number;
      volume: number;
      weight_unit: string;
    }[];
    cayley: {
      n: number;
      m: number;
      lower_bound: number | null;
      removed_self_loops: number;
      collapsed_parallel_edges: number;
    }[];
    scc: { component_size: number; dag_rank: number; has_self_loop: number }[];
    ast_body_hash: string | null;
    wl_3hop_hash: string | null;
  }>();
  const [impactCursor, setImpactCursor] = useState<string | null>(null);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
  const [members, setMembers] = useState<Node[]>([]),
    [remainingMembers, setRemainingMembers] = useState<string[]>([]);
  const [tokenReport, setTokenReport] = useState<BudgetReport>(),
    [similar, setSimilar] = useState<{
      nodes: Node[];
      candidate: boolean;
      next: string | null;
    }>();
  const [findings, setFindings] = useState<ConformanceFinding[]>(),
    [impact, setImpact] = useState<{
      nodes: NodeRecord[];
      count: number;
      complete: boolean;
      paths: Record<string, string[]>;
    }>();
  const id = node?.entity_id ?? node?.id,
    identity =
      snapshot.snapshot_id +
      "|" +
      node?.id +
      "|" +
      JSON.stringify(filter) +
      "|" +
      modelDigest +
      "|" +
      impactDirection +
      "|" +
      frame?.view_id;
  const activeIdentity = useRef(identity);
  activeIdentity.current = identity;
  useEffect(() => {
    setContent(undefined);
    setLoading(false);
    setMembers([]);
    setRemainingMembers([]);
    setWitnesses([]);
    setEvidence([]);
    setWitnessCursor(null);
    setDiagnostics(undefined);
    setImpact(undefined);
    setSimilar(undefined);
    setContext(undefined);
    setContextData(undefined);
    setTokenReport(undefined);
    setFindings(undefined);
    setError("");
  }, [
    node?.id,
    snapshot.snapshot_id,
    JSON.stringify(filter),
    modelDigest,
    impactDirection,
    frame?.view_id,
  ]);
  useEffect(() => {
    const abort = new AbortController();
    setDiagnostics(undefined);
    if (diagnosticsOpen && scopeReady) void advanced(abort.signal);
    return () => abort.abort();
  }, [
    diagnosticsOpen,
    scopeReady,
    node?.id,
    snapshot.snapshot_id,
    frame?.view_id,
    JSON.stringify(filter),
  ]);
  useEffect(() => {
    if (edge) {
      setTab("relationships");
      setWitnesses([]);
      setEvidence([]);
      setWitnessCursor(null);
    }
  }, [edge?.id]);
  useEffect(() => {
    if (tab !== "agent" || !node?.entity_id || !scopeReady) return;
    const abort = new AbortController();
    setContext(undefined);
    setContextData(undefined);
    setTokenReport(undefined);
    setLoading(true);
    setError("");
    const actorRequest = {
      ...base(snapshot.snapshot_id, agentBudget),
      schema_version: "1.1",
      identity_mode: "compact",
      budget: budget(agentBudget, encoding),
      focus_id: node.entity_id,
      grouping: { mode: "atomic" },
      context_radius: 1,
      filter,
      pins: pins.slice(0, 8),
      qi: { enabled: qi, max_diameter: 2 },
      cursor: null,
    };
    (agentVersion === "1.1"
      ? json<any>(
          "/api/v1.1/get_architecture_context",
          actorRequest,
          abort.signal,
        )
      : query(
          "get_architecture_context",
          {
            ...base(snapshot.snapshot_id, agentBudget),
            budget: budget(agentBudget, encoding),
            focus_id: node.entity_id,
            grouping: { mode: "atomic" },
            context_radius: 1,
            filter,
            pins: [],
            qi: { enabled: qi, max_diameter: 2 },
            cursor: null,
          },
          abort.signal,
        )
    )
      .then((result) => {
        setContext(result);
        setContextData(result.data);
        setTokenReport(result.budget);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [
    tab,
    node?.entity_id,
    snapshot.snapshot_id,
    agentBudget,
    encoding,
    qi,
    agentVersion,
    JSON.stringify(pins),
    scopeReady,
    frame?.view_id,
    modelDigest,
    JSON.stringify(filter),
  ]);
  async function inspect(relation: RelationshipSummary, more = false) {
    setLoading(true);
    setError("");
    try {
      const result = await query("inspect_relationship_witnesses", {
        ...base(snapshot.snapshot_id, 16384),
        view_id: relation.view_id,
        projection_id: relation.id,
        relationship_id: null,
        evidence_page_size: 3,
        evidence_cursor: null,
        page_size: 20,
        cursor: more ? witnessCursor : null,
      });
      if (activeIdentity.current !== identity) return;
      onNodes(result.data.nodes);
      setWitnesses((old) =>
        Array.from(
          new Map(
            [...(more ? old : []), ...result.data.witnesses].map((w) => [
              w.id,
              w,
            ]),
          ).values(),
        ),
      );
      setEvidence((old) =>
        Array.from(
          new Map(
            [...(more ? old : []), ...result.data.evidence_handles].map((e) => [
              e.id,
              e,
            ]),
          ).values(),
        ),
      );
      setWitnessCursor(result.data.completeness.next_cursor);
      const ids = [
        ...new Set(
          result.data.witnesses.flatMap((w) => [
            w.source_subject_id,
            w.target_subject_id,
          ]),
        ),
      ];
      const metadata = await json<{ nodes: Node[]; missing_ids: string[] }>(
        "/api/v1/entities",
        { snapshot_id: snapshot.snapshot_id, ids },
      );
      if (activeIdentity.current === identity) onNodes(metadata.nodes);
    } catch (e) {
      if (activeIdentity.current === identity) setError((e as Error).message);
    } finally {
      if (activeIdentity.current === identity) setLoading(false);
    }
  }
  async function source(entityId: string, more = false) {
    setTab("evidence");
    setLoading(true);
    setError("");
    try {
      const result = await query("get_entity_content", {
        ...base(snapshot.snapshot_id, 16384),
        entity_id: entityId,
        content_kind: "source",
        start_line: null,
        end_line: null,
        cursor: more ? (content?.completeness.next_cursor ?? null) : null,
      });
      if (activeIdentity.current !== identity) return;
      setContent((old) =>
        more && old
          ? { ...result.data, chunks: [...old.chunks, ...result.data.chunks] }
          : result.data,
      );
    } catch (e) {
      if (activeIdentity.current === identity) setError((e as Error).message);
    } finally {
      if (activeIdentity.current === identity) setLoading(false);
    }
  }
  async function moreEvidence(w: WitnessRecord) {
    if (!edge || !w.evidence_next_cursor) return;
    setLoading(true);
    try {
      const r = await query("inspect_relationship_witnesses", {
        ...base(snapshot.snapshot_id, 16384),
        view_id: edge.view_id,
        projection_id: null,
        relationship_id: w.id,
        evidence_page_size: 10,
        evidence_cursor: w.evidence_next_cursor,
        page_size: 1,
        cursor: null,
      });
      if (activeIdentity.current !== identity) return;
      setEvidence((old) =>
        Array.from(
          new Map(
            [...old, ...r.data.evidence_handles].map((e) => [e.id, e]),
          ).values(),
        ),
      );
      setWitnesses((old) =>
        old.map((x) =>
          x.id === w.id
            ? (r.data.witnesses.find((y) => y.id === w.id) ?? x)
            : x,
        ),
      );
    } catch (e) {
      if (activeIdentity.current === identity) setError((e as Error).message);
    } finally {
      if (activeIdentity.current === identity) setLoading(false);
    }
  }
  async function advanced(signal?: AbortSignal) {
    if (!id) return;
    try {
      const p = new URLSearchParams({
        snapshot_id: snapshot.snapshot_id,
        entity_id: id,
      });
      if (frame?.view_id) p.set("view_id", frame.view_id);
      const values = await json<typeof diagnostics>(
        "/api/v1/diagnostics?" + p,
        undefined,
        signal,
      );
      if (!signal?.aborted && activeIdentity.current === identity)
        setDiagnostics(values);
    } catch (e) {
      if (
        (e as Error).name !== "AbortError" &&
        activeIdentity.current === identity
      )
        setError((e as Error).message);
    }
  }
  async function dependants(more = false) {
    if (!node?.entity_id) return;
    setLoading(true);
    try {
      const r = await query("find_dependants", {
        ...base(snapshot.snapshot_id, 16384),
        entity_id: node.entity_id,
        direction: impactDirection,
        filter,
        max_depth: 8,
        max_results: 100,
        cursor: more ? impactCursor : null,
      });
      if (activeIdentity.current !== identity) return;
      onNodes(r.data.nodes);
      setImpact((old) => ({
        nodes: [
          ...(more ? (old?.nodes ?? []) : []),
          ...r.data.nodes.filter((n) =>
            r.data.results.some((x) => x.node_id === n.id),
          ),
        ],
        count: (more ? (old?.count ?? 0) : 0) + r.data.results.length,
        complete: r.data.traversal_complete && !r.data.completeness.truncated,
        paths: {
          ...(more ? old?.paths : {}),
          ...Object.fromEntries(
            r.data.results.map((x) => [x.node_id, x.witness_path_ids]),
          ),
        },
      }));
      setImpactCursor(r.data.completeness.next_cursor);
    } catch (e) {
      if (activeIdentity.current === identity) setError((e as Error).message);
    } finally {
      if (activeIdentity.current === identity) setLoading(false);
    }
  }
  async function conformance() {
    if (!id || !modelDigest) return;
    setLoading(true);
    try {
      const r = await query("check_architecture", {
        ...base(snapshot.snapshot_id, 16384),
        model_digest: modelDigest,
        scope_id: node?.entity_id ?? snapshot.root.id,
        filter: {
          ...filter,
          families: ["static"],
          resolution_statuses: ["exact"],
          runtime_window: null,
        },
        include_satisfied: true,
        page_size: 100,
        cursor: null,
      });
      if (activeIdentity.current !== identity) return;
      setFindings(r.data.findings);
      onNodes(r.data.nodes);
    } catch (e) {
      if (activeIdentity.current === identity) setError((e as Error).message);
    } finally {
      if (activeIdentity.current === identity) setLoading(false);
    }
  }
  async function similarities(candidate = false, more = false) {
    if (!node?.entity_id) return;
    setLoading(true);
    try {
      const r = await query("find_similar_code", {
        ...base(snapshot.snapshot_id, 16384),
        entity_id: node.entity_id,
        mode: candidate ? "wl_3hop_candidate" : "exact_normalized_ast",
        repo_ids: [node.repo_id],
        limit: 30,
        cursor: more ? (similar?.next ?? null) : null,
      });
      if (activeIdentity.current !== identity) return;
      onNodes(r.data.nodes);
      setSimilar((old) => ({
        candidate,
        nodes: [
          ...(more ? (old?.nodes ?? []) : []),
          ...r.data.nodes.filter((n) =>
            r.data.matches.some((m) => m.node_id === n.id),
          ),
        ],
        next: r.data.completeness.next_cursor,
      }));
    } catch (e) {
      if (activeIdentity.current === identity) setError((e as Error).message);
    } finally {
      if (activeIdentity.current === identity) setLoading(false);
    }
  }
  async function membership(more = false) {
    if (!node?.membership_handle) return;
    setLoading(true);
    try {
      const ids = more
        ? remainingMembers
        : (
            await json<{ members: string[] }>(
              "/api/v1/handles/" + encodeURIComponent(node.membership_handle),
            )
          ).members;
      const r = await json<{ nodes: Node[] }>("/api/v1/entities", {
        snapshot_id: snapshot.snapshot_id,
        ids: ids.slice(0, 50),
      });
      if (activeIdentity.current !== identity) return;
      onNodes(r.nodes);
      setMembers((old) => (more ? [...old, ...r.nodes] : r.nodes));
      setRemainingMembers(ids.slice(50));
    } catch (e) {
      if (activeIdentity.current === identity) setError((e as Error).message);
    } finally {
      if (activeIdentity.current === identity) setLoading(false);
    }
  }
  async function copyText(text: string, message: string) {
    try {
      await navigator.clipboard.writeText(text);
      onStatus(message);
    } catch {
      setError(
        "Clipboard unavailable. Select and copy the displayed text directly.",
      );
    }
  }
  const relations =
    frame?.relationships.filter(
      (r) => r.source === node?.id || r.target === node?.id,
    ) ?? [];
  const edgePreview = edge as
    (RelationshipSummary & Partial<ActorRelationship>) | undefined;
  const tabs: [Tab, string][] = [
    ["overview", "Overview"],
    ["relationships", "Links"],
    ["evidence", "Evidence"],
    ["agent", "Agent context"],
    ["investigation", "Investigate"],
  ];
  return (
    <>
      <div
        className="inspector-tabs"
        role="tablist"
        aria-label="Entity inspector"
      >
        {tabs.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            id={`tab-${key}`}
            aria-controls={`panel-${key}`}
            aria-selected={tab === key}
            tabIndex={tab === key ? 0 : -1}
            onKeyDown={(e) => {
              const i = tabs.findIndex((t) => t[0] === tab);
              const next =
                e.key === "ArrowRight"
                  ? (i + 1) % tabs.length
                  : e.key === "ArrowLeft"
                    ? (i + tabs.length - 1) % tabs.length
                    : e.key === "Home"
                      ? 0
                      : e.key === "End"
                        ? tabs.length - 1
                        : -1;
              if (next >= 0) {
                e.preventDefault();
                setTab(tabs[next][0]);
                document.getElementById("tab-" + tabs[next][0])?.focus();
              }
            }}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="inspector-content">
        {node && (
          <div className="entity-heading">
            <span className="kind-badge">{node.kind.replaceAll("_", " ")}</span>
            <h2>{shortName(node)}</h2>
            <p className="qualified-name" title={node.qualified_name}>
              {node.qualified_name}
            </p>
            {node.flags.is_test && (
              <span className="tiny-badge">Test code</span>
            )}
            {node.summary?.signature && <code>{node.summary.signature}</code>}
            {node.summary?.doc_gist && <p>{node.summary.doc_gist}</p>}
            {node.group_preview && (
              <div>
                <p>
                  {Object.entries(node.group_preview.kind_counts)
                    .map(([kind, count]) => `${count} ${kind}`)
                    .join(" · ")}{" "}
                  represented leaf owners
                </p>
                <ul>
                  {node.group_preview.top_exemplars.map((e) => (
                    <li key={e.id}>
                      <button onClick={() => onSelect(e.id)}>
                        {e.qualified_name}
                      </button>
                      <code>{e.signature}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {loading && (
          <p className="loading-message" role="status">
            Loading evidence…
          </p>
        )}
        {error && (
          <p className="error-text" role="status">
            {error}
          </p>
        )}
        <section
          id="panel-overview"
          role="tabpanel"
          aria-labelledby="tab-overview"
          hidden={tab !== "overview"}
        >
          {!node ? (
            <p>Select an entity to inspect its identity and evidence.</p>
          ) : (
            <>
              <div className="entity-actions">
                <button
                  disabled={!node.entity_id}
                  onClick={() => onEnter(node.id)}
                >
                  Enter / frame
                </button>
                <button
                  onClick={() => {
                    void copyText(node.id, "Entity ID copied");
                  }}
                >
                  Copy ID
                </button>
                <button
                  disabled={!node.entity_id}
                  aria-pressed={pinned}
                  onClick={onTogglePin}
                >
                  {pinned ? "Unpin entity" : "Pin entity"}
                </button>
              </div>
              {node.source ? (
                <div className="source-location">
                  <span className="field-label">Source</span>
                  <code>
                    {node.source.rel_path}:{node.source.start_line}–
                    {node.source.end_line}
                  </code>
                  <p>Revision {node.source.revision.slice(0, 12)}</p>
                  <button onClick={() => source(node.entity_id ?? node.id)}>
                    Inspect source
                  </button>
                </div>
              ) : (
                <p className="secondary">
                  {node.entity_id
                    ? "A structural enclosure in the containment tree."
                    : "A summary group. Membership is preserved; it is not a source-code entity."}
                </p>
              )}
              {node.member_count > 1 && (
                <div className="metric-strip">
                  <strong>{node.member_count.toLocaleString()}</strong>
                  <span>represented members</span>
                </div>
              )}
              <>
                {node.membership_handle && (
                  <button className="wide" onClick={() => void membership()}>
                    Inspect represented members
                  </button>
                )}
                {members.length > 0 && (
                  <div className="result-box">
                    <h3>Exact leaf membership</h3>
                    <ul>
                      {members.map((n) => (
                        <li key={n.id}>
                          <button
                            className="text-button"
                            onClick={() => onSelect(n.id)}
                          >
                            {shortName(n)}
                          </button>
                        </li>
                      ))}
                    </ul>
                    {remainingMembers.length > 0 && (
                      <button onClick={() => void membership(true)}>
                        Load more members
                      </button>
                    )}
                  </div>
                )}
              </>
              <label>
                Impact direction
                <select
                  aria-label="Impact direction"
                  value={impactDirection}
                  onChange={(e) =>
                    setImpactDirection(
                      e.target.value as "incoming" | "outgoing",
                    )
                  }
                >
                  <option value="incoming">
                    Incoming dependants (callers/importers)
                  </option>
                  <option value="outgoing">
                    Outgoing dependencies (callees/imports)
                  </option>
                </select>
              </label>
              <button
                className="wide"
                disabled={!node.entity_id || !filter.families.length}
                onClick={() => void dependants()}
              >
                {impactDirection === "incoming"
                  ? "Find dependants"
                  : "Find dependencies"}
              </button>
              {impact && (
                <div className="result-box">
                  <h3>
                    {impact.count}{" "}
                    {impactDirection === "incoming"
                      ? "dependants"
                      : "dependencies"}{" "}
                    in this result
                  </h3>
                  <p>
                    {impact.complete
                      ? "Traversal completed within the declared scope."
                      : "This is a bounded result; more may exist."}{" "}
                    Static dependencies do not guarantee runtime failure.
                  </p>
                  <ul>
                    {impact.nodes.map((n) => (
                      <li key={n.id}>
                        <button
                          className="text-button"
                          onClick={() => onSelect(n.id)}
                        >
                          {shortName(n)}
                        </button>
                        <button
                          onClick={() =>
                            onPath(impact.paths[n.id] ?? [], [node.id, n.id])
                          }
                        >
                          Highlight / pin path to {shortName(n)}
                        </button>
                      </li>
                    ))}
                  </ul>
                  {impactCursor && (
                    <button onClick={() => void dependants(true)}>
                      Load more dependants
                    </button>
                  )}
                </div>
              )}
              <details
                onToggle={(e) => {
                  setDiagnosticsOpen(e.currentTarget.open);
                }}
              >
                <summary>Advanced diagnostics</summary>
                {diagnostics ? (
                  <div className="advanced-values">
                    <h3>Boundary cut ratio</h3>
                    {diagnostics.boundary.map((b) => (
                      <div
                        className="diagnostic-row"
                        key={b.mode + b.weight_unit}
                      >
                        <span>
                          <span>{b.mode}</span> · {b.weight_unit}
                        </span>
                        <code>
                          {b.ratio === null
                            ? "Not applicable"
                            : b.ratio.toFixed(3)}
                        </code>
                      </div>
                    ))}
                    <p>
                      Cut weight / degree volume. This is a scoped boundary
                      ratio, not a measured latency bottleneck.
                    </p>
                    <h3>Degree asymmetry bound</h3>
                    <p>
                      Research interpretation · simple undirected static
                      projection
                    </p>
                    {diagnostics.cayley.slice(0, 8).map((c, i) => (
                      <div className="diagnostic-card" key={i}>
                        <strong>
                          {c.lower_bound === null
                            ? "Not applicable"
                            : `γ⁺ ≥ ${c.lower_bound.toFixed(3)}`}
                        </strong>
                        <span>
                          n={c.n}, m={c.m} · {c.removed_self_loops} loops
                          removed · {c.collapsed_parallel_edges} parallel edges
                          collapsed
                        </span>
                      </div>
                    ))}
                    <p>
                      A lower bound on abelian completion additions; not a
                      software quality score.
                    </p>
                    <h3>Cycles and dependency rank</h3>
                    {diagnostics.scc.length ? (
                      diagnostics.scc.map((s, i) => (
                        <p key={i}>
                          {s.component_size} group(s) in SCC · DAG rank{" "}
                          {s.dag_rank}
                          {s.has_self_loop
                            ? " · internal relationships retained"
                            : ""}
                        </p>
                      ))
                    ) : (
                      <p>
                        Cycle membership is attached to active groups in this
                        view.
                      </p>
                    )}
                    <h3>Code fingerprints</h3>
                    <p>
                      Normalised AST{" "}
                      <code>
                        {diagnostics.ast_body_hash?.slice(0, 16) ??
                          "Not available"}
                      </code>
                    </p>
                    <p>
                      3-hop WL{" "}
                      <code>
                        {diagnostics.wl_3hop_hash?.slice(0, 16) ??
                          "Not available"}
                      </code>
                    </p>
                    <p>WL identifies candidates, not semantic equivalence.</p>
                    <button
                      disabled={!node?.ast_body_hash}
                      onClick={() => void similarities()}
                    >
                      Find identical normal forms
                    </button>
                    <button
                      disabled={!node?.wl_3hop_hash}
                      onClick={() => void similarities(true)}
                    >
                      Find WL candidates
                    </button>
                    {similar && (
                      <div>
                        <p>
                          {similar.nodes.length}{" "}
                          {similar.candidate
                            ? "structural candidates"
                            : "verified normal-form matches"}
                          . Equality of normal forms does not prove behavioural
                          equivalence.
                        </p>
                        <ul>
                          {similar.nodes.map((n) => (
                            <li key={n.id}>
                              <button
                                className="text-button"
                                onClick={() => onSelect(n.id)}
                              >
                                {shortName(n)}
                              </button>
                            </li>
                          ))}
                        </ul>
                        {similar.next && (
                          <button
                            onClick={() =>
                              void similarities(similar.candidate, true)
                            }
                          >
                            Load more matches
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="secondary">
                    Open to calculate the scoped values.
                  </p>
                )}
              </details>
              <details>
                <summary>Architecture rules</summary>
                <p>
                  Conformance compares exact static facts, independently of the
                  runtime overlay.
                </p>
                {modelDigest ? (
                  <>
                    <p>
                      Model {modelDigest.slice(0, 12)} ·{" "}
                      {
                        models.find((m) => m.digest === modelDigest)
                          ?.world_policy
                      }{" "}
                      world
                    </p>
                    <button onClick={conformance}>Check this scope</button>
                    {findings?.map((f) => (
                      <div className="finding" key={f.id}>
                        <strong>{f.status.replaceAll("_", " ")}</strong>
                        <p>{f.rationale}</p>
                        <small>{f.witness_count} witnesses</small>
                      </div>
                    ))}
                  </>
                ) : (
                  <p>
                    No architecture rules configured. A versioned
                    geographer.rules.yaml file can be loaded when starting the
                    workspace.
                  </p>
                )}
              </details>
            </>
          )}
        </section>
        <section
          id="panel-relationships"
          role="tabpanel"
          aria-labelledby="tab-relationships"
          hidden={tab !== "relationships"}
        >
          {edge && (
            <div className="selected-relationship">
              <h3>Selected relationship</h3>
              <p>
                <strong>
                  {nodes[edge.source]
                    ? shortName(nodes[edge.source])
                    : "Source"}
                </strong>{" "}
                →{" "}
                <strong>
                  {nodes[edge.target]
                    ? shortName(nodes[edge.target])
                    : "Target"}
                </strong>
              </p>
              <p>
                {edge.subtype} · {edge.resolution_status} ·{" "}
                {edge.witness_count.toLocaleString()} witnesses
                {" · "}
                {edge.aggregated_weight.toLocaleString()} {edge.weight_unit}
              </p>
              {edge.is_internal && (
                <p>
                  Both endpoints are inside this group; internal calls are not
                  discarded.
                </p>
              )}
              {edgePreview?.witness_preview && (
                <div aria-label="Grounding preview">
                  <p>
                    {edgePreview.preview_complete
                      ? "Complete relationship preview"
                      : "Sample relationship preview; more witnesses exist"}
                  </p>
                  <ul>
                    {edgePreview.witness_preview.map((w) => (
                      <li key={w.relationship_id}>
                        {w.source_qualname}:{w.line ?? "?"} →{" "}
                        {w.target_qualname} [{w.reason_code}]
                      </li>
                    ))}
                  </ul>
                  <p>
                    {Object.entries(edgePreview.reason_counts ?? {})
                      .map(([reason, count]) => `${reason}: ${count}`)
                      .join(" · ")}
                  </p>
                </div>
              )}
              <button disabled={loading} onClick={() => inspect(edge)}>
                Inspect witnesses
              </button>
            </div>
          )}
          {!relations.length && !edge && (
            <p>
              No direct bundle for this item in the current result. Expanded
              enclosures are orientation shells; select a visible group or query
              dependants.
            </p>
          )}
          <ul className="relationship-list">
            {relations.map((r) => (
              <li key={r.id}>
                <button
                  className={edge?.id === r.id ? "is-selected" : ""}
                  onClick={() => {
                    onEdge(r.id);
                    void inspect(r);
                  }}
                >
                  <span>
                    {nodes[r.source] ? shortName(nodes[r.source]) : "Source"} →{" "}
                    {nodes[r.target] ? shortName(nodes[r.target]) : "Target"}
                  </span>
                  <small>
                    {r.subtype} · {r.witness_count} · {r.resolution_status}
                    {violations.includes(r.id)
                      ? " · rule violation (warning)"
                      : ""}
                  </small>
                </button>
              </li>
            ))}
          </ul>
          {witnesses.length > 0 && (
            <div className="witness-list">
              <h3>Concrete witnesses</h3>
              {witnesses.map((w) => (
                <div key={w.id} className="witness-card">
                  <p>
                    {nodes[w.source_subject_id]
                      ? shortName(nodes[w.source_subject_id])
                      : "Caller"}{" "}
                    →{" "}
                    {nodes[w.target_subject_id]
                      ? shortName(nodes[w.target_subject_id])
                      : "Callee"}
                  </p>
                  <small>
                    {w.subtype} · {w.resolution_status}
                    {" · "}
                    {w.weight.toLocaleString()} {w.weight_unit}
                  </small>
                  <button onClick={() => source(w.source_subject_id)}>
                    Read caller source
                  </button>
                  {w.evidence_next_cursor && (
                    <button onClick={() => void moreEvidence(w)}>
                      Load more evidence
                    </button>
                  )}
                </div>
              ))}
              {witnessCursor && edge && (
                <button disabled={loading} onClick={() => inspect(edge, true)}>
                  Load more witnesses / evidence
                </button>
              )}
            </div>
          )}
        </section>
        <section
          id="panel-evidence"
          role="tabpanel"
          aria-labelledby="tab-evidence"
          hidden={tab !== "evidence"}
        >
          {content ? (
            <>
              <h3>Snapshot source</h3>
              <p className="mono small">{content.chunks[0]?.source.rel_path}</p>
              <div
                className="source-code"
                tabIndex={0}
                aria-label="Source code from the selected snapshot"
              >
                {content.chunks.map((c) => (
                  <div
                    className="source-line"
                    key={c.source.start_line + c.sha256}
                  >
                    <span aria-hidden="true">{c.source.start_line}</span>
                    <code>{c.text}</code>
                  </div>
                ))}
              </div>
              {content.completeness.truncated && (
                <p className="warning-text">
                  Source is partial under this budget. More source is available.
                </p>
              )}
              {content.completeness.next_cursor && (
                <button onClick={() => void source(content.entity_id, true)}>
                  Load more source
                </button>
              )}
            </>
          ) : (
            <p>
              Inspect a relationship's witnesses or open an entity's snapshot
              source.
            </p>
          )}
          {evidence.map((e) => (
            <div className="evidence-card" key={e.id}>
              <strong>{e.category.replaceAll("_", " ")}</strong>
              <code>
                {e.source?.rel_path}:{e.source?.start_line}
              </code>
              <p>
                Revision {e.revision.slice(0, 12)} · {e.extractor_version}
              </p>
              <p>
                {e.confidence === null
                  ? "Confidence is not calibrated."
                  : `Confidence ${e.confidence}`}
              </p>
            </div>
          ))}
        </section>
        <section
          id="panel-agent"
          role="tabpanel"
          aria-labelledby="tab-agent"
          hidden={tab !== "agent"}
        >
          <div className="agent-controls">
            <label>
              Actor schema
              <select
                aria-label="Actor schema"
                value={agentVersion}
                onChange={(e) =>
                  setAgentVersion(e.target.value as "1.0" | "1.1")
                }
              >
                <option value="1.1">v1.1 compact, grounded</option>
                <option value="1.0">v1.0 compatibility</option>
              </select>
            </label>
            <label>
              Context budget
              <select
                value={agentBudget}
                onChange={(e) => setAgentBudget(Number(e.target.value))}
              >
                <option value={2048}>2,048 tokens</option>
                <option value={8192}>8,192 tokens</option>
                <option value={16384}>16,384 tokens</option>
              </select>
            </label>
            <label>
              Tokenizer
              <select
                value={encoding}
                onChange={(e) => setEncoding(e.target.value as typeof encoding)}
              >
                <option value="o200k_base">o200k_base</option>
                <option value="cl100k_base">cl100k_base</option>
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={qi}
                onChange={(e) => setQi(e.target.checked)}
              />
              Bounded helper summary
            </label>
          </div>
          {!node?.entity_id && (
            <p>
              Select an individual source entity to request its agent context.
            </p>
          )}
          {contextData && (
            <>
              <p>
                {contextData.nodes.length} node definitions ·{" "}
                {contextData.relationships.length} relationships
                {contextData.completeness.truncated
                  ? " · partial, omissions disclosed"
                  : ""}
              </p>
              {contextData.qi.mode !== "off" && (
                <p>
                  Undirected hop bound A={contextData.qi.A}, B=
                  {contextData.qi.B}. Directed reachability uses original
                  witnesses.
                </p>
              )}
            </>
          )}
          {tokenReport && (
            <>
              <p>
                {tokenReport.used_tokens.toLocaleString()} /{" "}
                {tokenReport.limit_tokens.toLocaleString()} tokens ·{" "}
                {tokenReport.guarantee.replaceAll("_", " ")}
              </p>
              <div
                className="token-meter"
                role="meter"
                aria-label="Agent context tokens"
                aria-valuemin={0}
                aria-valuemax={tokenReport.limit_tokens}
                aria-valuenow={tokenReport.used_tokens}
              >
                <span
                  style={{
                    width: `${(100 * tokenReport.used_tokens) / tokenReport.limit_tokens}%`,
                  }}
                />
              </div>
              <p className="secondary">
                Counts cover the returned JSON region. The complete envelope is
                also checked against the limit; this is not a whole-prompt
                estimate.
              </p>
            </>
          )}
          <button
            disabled={!context}
            onClick={() => {
              void copyText(
                JSON.stringify(context, null, 2),
                "Agent context copied",
              );
            }}
          >
            Copy context JSON
          </button>
          <pre
            className="agent-json"
            tabIndex={0}
            aria-label="Agent context JSON"
          >
            {context
              ? JSON.stringify(context, null, 2)
              : "Context appears here after selecting a source entity."}
          </pre>
        </section>
        <section
          id="panel-investigation"
          role="tabpanel"
          aria-labelledby="tab-investigation"
          hidden={tab !== "investigation"}
        >
          {tab === "investigation" && scopeReady && (
            <Investigation
              snapshotId={snapshot.snapshot_id}
              entityId={node?.entity_id ?? undefined}
              filter={filter}
              pins={pins}
              modelDigest={modelDigest}
              onSelect={onSelect}
              onNodes={onNodes}
              onPath={onPath}
            />
          )}
        </section>
      </div>
    </>
  );
}
