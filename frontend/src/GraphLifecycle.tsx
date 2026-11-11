import { useState } from "react";
import { copyGraph, deleteGraph } from "./api";
import type { WorkspaceGraph } from "./workspaceTypes";

export default function GraphActions({
  graph,
  onCopied,
  onDeleted,
}: {
  graph: WorkspaceGraph;
  onCopied: (id: string) => void;
  onDeleted: (id: string) => void;
}) {
  const [mode, setMode] = useState<"" | "copy" | "delete">(""),
    [text, setText] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  function open(next: "copy" | "delete") {
    setMode(next);
    setText(next === "copy" ? `${graph.label} copy` : "");
    setError("");
  }
  async function submit() {
    setBusy(true);
    setError("");
    try {
      if (mode === "copy") {
        const made = await copyGraph(graph.graph_id, text);
        setMode("");
        onCopied(made.graph_id);
      } else {
        await deleteGraph(graph.graph_id, text);
        setMode("");
        onDeleted(graph.graph_id);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const owned = graph.owned_store !== false;
  return (
    <>
      <button
        onClick={() => open("copy")}
        aria-label={`Copy graph ${graph.label}`}
      >
        Copy…
      </button>
      <button
        onClick={() => open("delete")}
        aria-label={`Delete graph ${graph.label}`}
      >
        Delete…
      </button>
      {mode && (
        <div
          role="group"
          aria-label={mode === "copy" ? "Copy graph" : "Delete graph"}
          className="graph-lifecycle-dialog"
        >
          {mode === "delete" && (
            <p>
              Deleting {graph.label} removes {graph.bridge_count ?? 0} bridge
              {graph.bridge_count === 1 ? "" : "s"}.{" "}
              {owned
                ? "Its store is owned by this catalogue and its files will be deleted."
                : "Its store is registered, not owned: the file is kept."}{" "}
              This cannot be undone.
            </p>
          )}
          <label>
            {mode === "copy" ? "Copy label" : "Type the graph label to confirm"}
            <input value={text} onChange={(e) => setText(e.target.value)} />
          </label>
          <button
            disabled={
              busy ||
              !text.trim() ||
              (mode === "delete" && text !== graph.label)
            }
            onClick={submit}
          >
            {mode === "copy" ? "Create copy" : "Delete graph"}
          </button>
          <button onClick={() => setMode("")}>Cancel</button>
          {error && <p role="alert">{error}</p>}
        </div>
      )}
    </>
  );
}
