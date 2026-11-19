import { useEffect, useState } from "react";
import { deriveGraph, previewDerive, type DeriveMode, type DerivePreview } from "./api";
import { previewMakesNothing, previewSentence } from "./buildOps";
import { useBuild } from "./buildContext";

/**
 * Keep only, or remove: make a new graph from what is selected on the canvas. The counts come first, from
 * the source graph, so the result is known before anything is made. The source graph is never changed.
 */
export default function DeriveSection() {
  const { derive, clearDerive, derived } = useBuild();
  const [mode, setMode] = useState<DeriveMode>("keep"),
    [label, setLabel] = useState("");
  const [preview, setPreview] = useState<DerivePreview>(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [made, setMade] = useState("");
  const paths = derive?.paths ?? [];
  const graph = derive?.graph;
  const key = graph && paths.length ? `${graph}|${mode}|${paths.join("\n")}` : "";
  useEffect(() => {
    setPreview(undefined);
    setError("");
    setMade("");
    if (!graph || !paths.length) return;
    const abort = new AbortController();
    previewDerive(graph, mode, paths, abort.signal)
      .then((p) => {
        if (!abort.signal.aborted) setPreview(p);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError((e as Error).message);
      });
    return () => abort.abort();
  }, [key]);
  async function create() {
    if (!graph || !paths.length || !label.trim()) return;
    setBusy(true);
    setError("");
    try {
      await deriveGraph(graph, mode, paths, label.trim());
      derived();
      setMade(`Made “${label.trim()}”. It is in the Graphs tab; the graph you started from is unchanged.`);
      setLabel("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const nothing = preview ? previewMakesNothing(preview) : false;
  return (
    <section aria-labelledby="build-derive">
      <h2 id="build-derive">Keep only or remove</h2>
      <p className="build-hint">
        Select files or folders on the canvas, then press the scissors. Choose here whether to keep only them or to
        leave them out.
      </p>
      {!derive && <p className="muted">Nothing is selected for this yet.</p>}
      {derive && !paths.length && <p role="status">{derive.message || "The selection holds no files of this graph."}</p>}
      {derive && paths.length > 0 && (
        <form
          className="derive-form"
          aria-label="Keep only or remove the selection"
          onSubmit={(e) => {
            e.preventDefault();
            void create();
          }}
        >
          <fieldset disabled={busy}>
            <legend>
              What to do with the {paths.length} selected path{paths.length === 1 ? "" : "s"}
            </legend>
            <label>
              <input type="radio" name="derive-mode" checked={mode === "keep"} onChange={() => setMode("keep")} /> Keep only
              these
            </label>
            <label>
              <input type="radio" name="derive-mode" checked={mode === "exclude"} onChange={() => setMode("exclude")} /> Remove
              these
            </label>
          </fieldset>
          <details>
            <summary>The {paths.length} selected path{paths.length === 1 ? "" : "s"}</summary>
            <ul className="derive-paths">
              {paths.map((p) => (
                <li key={p}>
                  <code>{p}</code>
                </li>
              ))}
            </ul>
          </details>
          <p className="derive-preview" data-testid="derive-preview" aria-live="polite">
            {preview ? previewSentence(preview) : error ? "" : "Counting…"}
          </p>
          {!!preview?.unmatched_paths.length && (
            <p className="muted">
              {preview.unmatched_paths.length} selected path{preview.unmatched_paths.length === 1 ? " holds" : "s hold"} no
              file in this graph.
            </p>
          )}
          {preview && <p className="muted">{preview.note}</p>}
          <label>
            New graph name{" "}
            <input value={label} maxLength={120} disabled={busy} onChange={(e) => setLabel(e.target.value)} />
          </label>
          <div className="derive-actions">
            <button type="submit" disabled={busy || !preview || nothing || !label.trim()}>
              {mode === "keep" ? "Create graph of only these" : "Create graph without these"}
            </button>
            <button type="button" onClick={clearDerive} disabled={busy}>
              Clear selection
            </button>
          </div>
          {error && <p role="alert">{error}</p>}
          {made && <p role="status">{made}</p>}
        </form>
      )}
    </section>
  );
}
