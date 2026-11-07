import { useEffect, useRef, useState } from "react";
import type { Filter } from "../../contracts/geographer.wire";
import type {
  GetEntityContentData,
  GetArchitectureContextData,
  SemanticOverlay,
} from "../../contracts/v1.1/geographer.wire";
import { actorBase, actorQuery, json, type Node } from "./api";

interface Props {
  snapshotId: string;
  entityId?: string;
  filter: Filter;
  pins: string[];
  modelDigest: string;
  onSelect: (id: string) => void;
  onNodes: (nodes: Node[]) => void;
  onPath: (ids: string[], entities: string[]) => void;
}
type Queue = {
  items: {
    occurrence_id: string;
    entity_id: string;
    line: number | null;
    reason_codes: string[];
    relationship_ids: string[];
    alternatives: string[];
    focus_relevant: boolean;
    boundary: boolean;
    incident_occurrences: number;
  }[];
  total: number;
  next_cursor: string | null;
  ordering: string;
};
export default function Investigation(p: Props) {
  const [content, setContent] = useState<GetEntityContentData>(),
    [context, setContext] = useState<GetArchitectureContextData>(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [queue, setQueue] = useState("unknown_locality"),
    [triage, setTriage] = useState<Queue>(),
    [annotation, setAnnotation] = useState(""),
    [decision, setDecision] = useState<"pending" | "accepted" | "rejected">(
      "pending",
    ),
    [overlay, setOverlay] = useState<SemanticOverlay>(),
    [showOverlay, setShowOverlay] = useState(true);
  const identity = JSON.stringify([
      p.snapshotId,
      p.entityId,
      p.filter,
      p.pins,
      p.modelDigest,
    ]),
    current = useRef(identity);
  current.current = identity;
  useEffect(() => {
    setContent(undefined);
    setContext(undefined);
    setTriage(undefined);
    setError("");
    setBusy(false);
    setAnnotation("");
    setOverlay(undefined);
  }, [identity]);
  useEffect(() => {
    const abort = new AbortController();
    let saved: string | null = null;
    try {
      saved = localStorage.getItem("geographer.overlay." + p.snapshotId);
    } catch {}
    if (saved?.startsWith("overlay:"))
      json<SemanticOverlay>(
        "/api/workspace/overlay",
        { snapshot_id: p.snapshotId, overlay_id: saved },
        abort.signal,
      )
        .then(setOverlay)
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
    return () => abort.abort();
  }, [identity]);
  async function action(work: () => Promise<void>) {
    const key = identity;
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      if (current.current === key) setError((e as Error).message);
    } finally {
      if (current.current === key) setBusy(false);
    }
  }
  function rememberOverlay(value: SemanticOverlay) {
    setOverlay(value);
    try {
      localStorage.setItem(
        "geographer.overlay." + p.snapshotId,
        value.overlay_id,
      );
    } catch {
      setError("Review saved on the server; browser storage is unavailable.");
    }
  }
  async function source(
    entityId = p.entityId,
    range?: { start_line: number; end_line: number },
  ) {
    if (!entityId) return;
    const key = identity;
    const r = await actorQuery("get_entity_content", {
      ...actorBase(p.snapshotId, 32768),
      entity_id: entityId,
      content_kind: "source",
      context_mode: "source-context-v1",
      context_radius: 1,
      start_line: range?.start_line ?? null,
      end_line: range?.end_line ?? null,
      cursor: null,
      include_investigation: true,
      overlay_id: showOverlay ? (overlay?.overlay_id ?? null) : null,
    });
    if (current.current !== key) return;
    setContent(r.data);
    p.onNodes(r.data.nodes as unknown as Node[]);
  }
  async function document(entityId: string) {
    const key = identity;
    const r = await actorQuery("get_entity_content", {
      ...actorBase(p.snapshotId),
      entity_id: entityId,
      content_kind: "documentation",
      context_mode: "range",
      context_radius: 0,
      start_line: null,
      end_line: null,
      cursor: null,
      include_investigation: true,
    });
    if (current.current === key) {
      setContent(r.data);
      p.onNodes(r.data.nodes as unknown as Node[]);
    }
  }
  async function paths() {
    if (!p.entityId) return;
    const key = identity;
    const r = await actorQuery("get_architecture_context", {
      ...actorBase(p.snapshotId, 32768),
      focus_id: p.entityId,
      grouping: { mode: "atomic" },
      context_radius: 1,
      filter: p.filter,
      pins: p.pins.filter((id) => id !== p.entityId).slice(0, 8),
      qi: { enabled: false, max_diameter: 2 },
      path_request: {
        template: "CALL_CHAIN_WITH_HELPERS",
        max_hops: 4,
        max_expansions: 20000,
        undirected: false,
        boundary_model_digest: null,
      },
      cursor: null,
    });
    if (current.current === key) {
      setContext(r.data);
      p.onNodes(r.data.nodes as unknown as Node[]);
    }
  }
  async function review(more = false) {
    const key = identity;
    const result = await json<Queue>("/api/workspace/triage", {
      snapshot_id: p.snapshotId,
      focus_id: p.entityId,
      pins: p.pins,
      model_digest: p.modelDigest || null,
      filter: p.filter,
      queue,
      limit: 10,
      cursor: more ? triage?.next_cursor : null,
    });
    if (current.current === key)
      setTriage((old) => ({
        ...result,
        items: more ? [...(old?.items ?? []), ...result.items] : result.items,
      }));
  }
  const fold = content?.source_context,
    details = content?.investigation;
  return (
    <div className="investigation">
      <p>
        Original evidence and source context. Documentation and review
        annotations are untrusted assertions.
      </p>
      {busy && <p role="status">Loading investigation…</p>}
      {error && <p role="alert">{error}</p>}
      <fieldset disabled={busy}>
        <legend className="sr-only">Investigation actions</legend>
        <button
          disabled={busy || !p.entityId}
          onClick={() => void action(() => source())}
        >
          Open folded source and documents
        </button>
        {fold && (
          <section aria-label="Folded source">
            <h3>Enclosing headers</h3>
            {fold.enclosing_headers.map((s) => (
              <pre key={s.sha256}>{s.text}</pre>
            ))}
            <h3>Verbatim focal source</h3>
            {fold.focal_segments.map((s) => (
              <pre key={s.sha256} tabIndex={0}>
                {s.text}
              </pre>
            ))}
            <h3>Sibling context</h3>
            {fold.sibling_stubs.map((s) => (
              <div key={s.content_handle}>
                <button
                  onClick={() =>
                    void action(async () => {
                      const range = await json<{
                        entity_id: string;
                        start_line: number;
                        end_line: number;
                      }>(
                        "/api/v1/handles/" +
                          encodeURIComponent(s.content_handle),
                      );
                      await source(range.entity_id, range);
                    })
                  }
                >
                  {s.signature ?? "Statement"} · lines {s.source.start_line}–
                  {s.source.end_line}
                </button>
                <p>{s.doc_gist}</p>
                <small>
                  Calls: {s.outgoing_call_names.join(", ") || "none listed"}
                  {!s.calls_complete ? " · incomplete/unsupported" : ""}
                </small>
              </div>
            ))}
            <details>
              <summary>Omitted source ranges</summary>
              {fold.omissions.map((s) => (
                <button
                  key={s.content_handle}
                  onClick={() =>
                    void action(async () => {
                      const range = await json<{
                        entity_id: string;
                        start_line: number;
                        end_line: number;
                      }>(
                        "/api/v1/handles/" +
                          encodeURIComponent(s.content_handle),
                      );
                      await source(range.entity_id, range);
                    })
                  }
                >
                  Lines {s.source.start_line}–{s.source.end_line} omitted — open
                </button>
              ))}
            </details>
          </section>
        )}
        {content && !fold && (
          <pre tabIndex={0} aria-label="Document content">
            {content.chunks.map((c) => c.text).join("")}
          </pre>
        )}
        {details && (
          <>
            <h3>Documentary hierarchy T_D</h3>
            {details.documentary_sections.length ? (
              details.documentary_sections.map((s) => (
                <div key={s.section_id}>
                  <strong>{s.heading}</strong>
                  <small> · {s.coordinate_space}</small>
                  {s.fragment_ids.map((fid) => (
                    <button
                      key={fid}
                      onClick={() => void action(() => document(fid))}
                    >
                      Open documentary section {s.heading}
                    </button>
                  ))}
                </div>
              ))
            ) : (
              <p>No linked documentary section was extracted.</p>
            )}
            <details>
              <summary>Source/process evidence card</summary>
              <ol>
                {details.statement_steps.map((s, i) => (
                  <li key={i}>
                    {s.kind} · lines {s.start_line}–{s.end_line} · {s.basis}
                  </li>
                ))}
              </ol>
              <p>
                {details.call_relationship_ids.length} original call references;
                inspection is available through relationship evidence.
              </p>
              {details.limitations.map((gap) => (
                <p key={gap}>{gap}</p>
              ))}
            </details>
          </>
        )}
        <h3>Witness bridges to pins</h3>
        {p.filter.families.includes("runtime") && (
          <p>
            Observed/static adjacency does not prove that a whole path ran in
            one invocation. Call counts are not latency measurements.
          </p>
        )}
        <button
          disabled={
            busy || !p.entityId || !p.pins.some((id) => id !== p.entityId)
          }
          onClick={() => void action(paths)}
        >
          Find bounded call paths
        </button>
        {context?.paths.map((path) => (
          <div key={path.target}>
            <strong>{path.outcome.replaceAll("_", " ")}</strong>
            <p>
              {path.steps.length} original steps · {path.visited_states}{" "}
              searched states ·{" "}
              {path.anchors_complete ? "anchors covered" : "partial anchors"}
            </p>
            {path.steps.map((step) => {
              const w = context.witnesses.find(
                (w) => w.id === step.relationship_id,
              );
              return (
                <p key={step.relationship_id}>
                  {w
                    ? `${context.nodes.find((n) => n.id === w.source_subject_id)?.qualified_name ?? w.source_subject_id} → ${context.nodes.find((n) => n.id === w.target_subject_id)?.qualified_name ?? w.target_subject_id} · ${w.resolution_status}`
                    : step.relationship_id}
                  {step.traversal_reversed ? " (traversed backwards)" : ""}
                </p>
              );
            })}
            {path.outcome === "found" && (
              <button
                onClick={() =>
                  p.onPath(
                    path.steps.map((s) => s.relationship_id),
                    [path.source, path.target],
                  )
                }
              >
                Highlight this witness path
              </button>
            )}
          </div>
        ))}
        <h3>Ambiguity triage</h3>
        <label>
          Review queue
          <select
            aria-label="Review queue"
            value={queue}
            onChange={(e) => {
              setQueue(e.target.value);
              setTriage(undefined);
            }}
          >
            <option value="unknown_locality">Unknown target locality</option>
            <option value="internal_candidates">
              Known internal candidate targets
            </option>
            <option value="unmapped" disabled={!p.modelDigest}>
              Unmapped conceptual subjects
            </option>
          </select>
        </label>
        <button disabled={busy} onClick={() => void action(() => review())}>
          Load review queue
        </button>
        {triage && (
          <>
            <p>
              {triage.total} occurrences · order: {triage.ordering}
            </p>
            <ol>
              {triage.items.map((row) => (
                <li key={row.occurrence_id}>
                  <button onClick={() => p.onSelect(row.entity_id)}>
                    Open caller · line {row.line ?? "unknown"}
                  </button>
                  <p>{row.reason_codes.join(", ")}</p>
                  <small>
                    Focus/pin: {String(row.focus_relevant)} · boundary:{" "}
                    {String(row.boundary)} · incident occurrences:{" "}
                    {row.incident_occurrences}
                  </small>
                  <p>
                    {row.alternatives.length} alternatives; unknown target
                    degree is not estimated.
                  </p>
                </li>
              ))}
            </ol>
            {triage.next_cursor && (
              <button onClick={() => void action(() => review(true))}>
                More review occurrences
              </button>
            )}
          </>
        )}
        <h3>Review annotations</h3>
        <label>
          <input
            type="checkbox"
            checked={showOverlay}
            onChange={(e) => setShowOverlay(e.target.checked)}
          />
          Show review overlay
        </label>
        <label>
          Annotation
          <textarea
            aria-label="Review annotation"
            maxLength={2000}
            value={annotation}
            onChange={(e) => setAnnotation(e.target.value)}
          />
        </label>
        <label>
          Review decision
          <select
            aria-label="Review decision"
            value={decision}
            onChange={(e) => setDecision(e.target.value as typeof decision)}
          >
            <option value="pending">Pending</option>
            <option value="accepted">Accepted annotation</option>
            <option value="rejected">Rejected annotation</option>
          </select>
        </label>
        <button
          disabled={busy || !p.entityId || !annotation.trim()}
          onClick={() =>
            void action(async () => {
              const key = identity;
              const result = await json<SemanticOverlay>(
                "/api/workspace/annotation",
                {
                  snapshot_id: p.snapshotId,
                  entity_id: p.entityId,
                  text: annotation,
                  decision,
                  previous_overlay_id: overlay?.overlay_id ?? null,
                },
              );
              if (current.current === key) {
                rememberOverlay(result);
                setAnnotation("");
              }
            })
          }
        >
          Save review decision
        </button>
        {showOverlay && overlay && (
          <div>
            <p>
              Overlay {overlay.overlay_id.slice(0, 20)} · canonical facts
              unchanged
            </p>
            {overlay.records.map((r, i) => (
              <p key={i}>
                {r.decision}: {r.text}
              </p>
            ))}
          </div>
        )}
      </fieldset>
    </div>
  );
}
