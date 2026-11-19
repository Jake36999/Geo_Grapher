import { useEffect, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import type { Accent } from "./accents";
import { declareLink, listLinks, removeLink, type DeclaredLink } from "./api";
import { kindLabel, linkStateLabel, shortRef } from "./buildOps";
import { useBuild } from "./buildContext";
import GraphSwatch from "./GraphSwatch";

export type LinkEnd = { graph: string; ref: string; label: string };
export type LinkDraft = { source: LinkEnd; target: LinkEnd; kind: string; rationale: string };
export const emptyLink: LinkDraft = {
  source: { graph: "", ref: "", label: "" },
  target: { graph: "", ref: "", label: "" },
  kind: "reference",
  rationale: "",
};

const KINDS = ["reference", "concept_equivalence", "document_identity"] as const;

/**
 * Declared links between the checked graphs. A link is how a person says two graphs relate; it is kept
 * apart from what was extracted and never edits either graph, and it can be taken back. Each end is the
 * whole graph, the item selected on the canvas, or a reference typed in. The draft lives with the workspace
 * because choosing the second item on the canvas can switch the active graph.
 */
export default function LinkSection({
  graphIds,
  labels,
  accents,
  draft,
  setDraft,
  version,
  onChanged,
  children,
}: {
  graphIds: string[];
  labels: Record<string, string>;
  accents: Record<string, Accent>;
  draft: LinkDraft;
  setDraft: Dispatch<SetStateAction<LinkDraft>>;
  /** Bumped whenever a link is declared or taken back, so what is shown is read again. */
  version: number;
  onChanged: () => void;
  /** Reviewed suggestions for links, shown after the person's own. */
  children?: ReactNode;
}) {
  const { selection } = useBuild();
  const [links, setLinks] = useState<DeclaredLink[]>([]),
    [error, setError] = useState(""),
    [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [confirming, setConfirming] = useState("");
  const name = (id: string) => labels[id] || id;
  const sourceGraph = graphIds.includes(draft.source.graph) ? draft.source.graph : (graphIds[0] ?? "");
  const targetGraph =
    graphIds.includes(draft.target.graph) && draft.target.graph !== sourceGraph
      ? draft.target.graph
      : (graphIds.find((g) => g !== sourceGraph) ?? "");
  const source = draft.source.graph === sourceGraph ? draft.source : { graph: sourceGraph, ref: "", label: "" };
  const target = draft.target.graph === targetGraph ? draft.target : { graph: targetGraph, ref: "", label: "" };
  const key = graphIds.join();
  useEffect(() => {
    if (!graphIds.length) {
      setLinks([]);
      return;
    }
    const abort = new AbortController();
    listLinks(graphIds, abort.signal)
      .then((l) => {
        if (!abort.signal.aborted) setLinks(l);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError((e as Error).message);
      });
    return () => abort.abort();
  }, [key, version]);
  const setEnd = (side: "source" | "target", end: LinkEnd) => {
    setNote("");
    setError("");
    setDraft((d) => ({ ...d, [side]: end }));
  };
  const ready = !!source.ref.trim() && !!target.ref.trim() && !!draft.rationale.trim() && sourceGraph !== targetGraph;
  async function declare() {
    if (!ready) return;
    setBusy(true);
    setError("");
    setNote("");
    try {
      await declareLink({
        source_graph: sourceGraph,
        source_ref: source.ref.trim(),
        target_graph: targetGraph,
        target_ref: target.ref.trim(),
        kind: draft.kind,
        rationale: draft.rationale.trim(),
      });
      setDraft((d) => ({ ...d, source: { ...d.source, ref: "", label: "" }, target: { ...d.target, ref: "", label: "" }, rationale: "" }));
      setNote("Link declared. It is listed below, and you can take it back.");
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function take(link: DeclaredLink) {
    setBusy(true);
    setError("");
    setNote("");
    try {
      await removeLink(link.bridge_id);
      setConfirming("");
      setNote("Link taken back. Both graphs are as they were.");
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const end = (side: "source" | "target", title: string, value: LinkEnd, graph: string, other: string) => (
    <fieldset className="link-end" disabled={busy}>
      <legend>{title}</legend>
      <label>
        Graph{" "}
        <select
          aria-label={`${title} graph`}
          value={graph}
          onChange={(e) => {
            const next = e.target.value;
            setEnd(side, { graph: next, ref: "", label: "" });
            // choosing the other end's graph swaps the two, so they never name the same graph
            if (next === other) setEnd(side === "source" ? "target" : "source", { graph: graph, ref: "", label: "" });
          }}
        >
          {graphIds.map((g) => (
            <option key={g} value={g}>
              {name(g)}
            </option>
          ))}
        </select>
      </label>
      <div className="link-end-choices">
        <button
          type="button"
          aria-pressed={value.ref === "root"}
          onClick={() => setEnd(side, { graph, ref: "root", label: "the whole graph" })}
        >
          Whole graph
        </button>
        <button
          type="button"
          disabled={!selection || selection.graph_id !== graph}
          title={
            !selection
              ? "Select an item on the canvas first"
              : selection.graph_id !== graph
                ? `The selected item is in ${name(selection.graph_id)}`
                : undefined
          }
          onClick={() => selection && setEnd(side, { graph, ref: selection.ref, label: selection.label })}
        >
          Use the selected item
        </button>
      </div>
      <label>
        Reference{" "}
        <input
          aria-label={`${title} reference`}
          value={value.ref}
          maxLength={300}
          placeholder="entity:…, doc:12, concept:7 or root"
          onChange={(e) => setEnd(side, { graph, ref: e.target.value, label: "" })}
        />
      </label>
      {value.label && value.ref && <p className="muted">{value.label}</p>}
    </fieldset>
  );
  return (
    <section aria-labelledby="build-link">
      <h2 id="build-link">Link graphs</h2>
      <p className="build-hint">
        Declare how two checked graphs relate. A link is kept apart from what was extracted, changes neither graph,
        and can be taken back.
      </p>
      {graphIds.length < 2 ? (
        <p className="muted">Check two graphs in the Graphs tab to link them.</p>
      ) : (
        <form
          className="link-form"
          aria-label="Declare a link"
          onSubmit={(e) => {
            e.preventDefault();
            void declare();
          }}
        >
          {end("source", "From", source, sourceGraph, targetGraph)}
          {end("target", "To", target, targetGraph, sourceGraph)}
          <label>
            How they relate{" "}
            <select value={draft.kind} disabled={busy} onChange={(e) => setDraft((d) => ({ ...d, kind: e.target.value }))}>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {kindLabel(k)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Why{" "}
            <input
              aria-label="Why this link"
              value={draft.rationale}
              maxLength={2000}
              disabled={busy}
              placeholder="Required"
              onChange={(e) => setDraft((d) => ({ ...d, rationale: e.target.value }))}
            />
          </label>
          <button type="submit" disabled={busy || !ready}>
            Declare link
          </button>
        </form>
      )}
      {error && <p role="alert">{error}</p>}
      {note && <p role="status">{note}</p>}
      {links.length > 0 && (
        <ul className="link-list" aria-label="Declared links">
          {links.map((l) => (
            <li key={l.bridge_id}>
              <span className="link-ends">
                <GraphSwatch accent={accents[l.source_graph]} />
                {name(l.source_graph)} <code title={l.source_ref}>{shortRef(l.source_ref)}</code> <span aria-hidden="true">→</span>{" "}
                <GraphSwatch accent={accents[l.target_graph]} />
                {name(l.target_graph)} <code title={l.target_ref}>{shortRef(l.target_ref)}</code>
              </span>
              <small>
                {kindLabel(l.kind)} · {linkStateLabel(l.state)}
              </small>
              <p className="link-why">{l.rationale}</p>
              {confirming === l.bridge_id ? (
                <span role="group" aria-label="Confirm taking the link back">
                  Take this link back?{" "}
                  <button type="button" disabled={busy} onClick={() => void take(l)}>
                    Take it back
                  </button>{" "}
                  <button type="button" disabled={busy} onClick={() => setConfirming("")}>
                    Keep it
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  disabled={busy}
                  aria-label={`Take back the link from ${name(l.source_graph)} to ${name(l.target_graph)}`}
                  onClick={() => setConfirming(l.bridge_id)}
                >
                  Take back
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {graphIds.length >= 2 && links.length === 0 && <p className="muted">No links are declared between the checked graphs.</p>}
      {children}
    </section>
  );
}
