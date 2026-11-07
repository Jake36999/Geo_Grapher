import { useCallback, useEffect, useState } from "react";
import App from "./App";
import GraphMergeReview from "./GraphMergeReview";
import { setWorkspaceGraph } from "./api";
import type {
  GraphPick,
  WorkspaceGraph,
  WorkspaceSettings,
} from "./workspaceTypes";

export default function Workspace() {
  const [graphs, setGraphs] = useState<WorkspaceGraph[]>([]),
    [active, setActive] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [error, setError] = useState("");
  const [pending, setPending] = useState<GraphPick>(),
    [settings, setSettings] = useState<WorkspaceSettings>();
  const [showBridges, setShowBridges] = useState(true);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [focus, setFocus] = useState<
    Record<string, { snapshot: string; id: string }>
  >({});
  const primary =
    document
      .querySelector('meta[name="geographer-primary-graph"]')
      ?.getAttribute("content") ?? undefined;
  useEffect(() => {
    const abort = new AbortController();
    fetch("/api/graphs", { signal: abort.signal })
      .then((r) => {
        if (!r.ok) throw Error("Cannot load graph catalogue");
        return r.json();
      })
      .then((data) => {
        const available: WorkspaceGraph[] = data.graphs.filter(
          (g: WorkspaceGraph) => g.availability !== "unavailable",
        );
        setGraphs(data.graphs);
        const requested = new URLSearchParams(location.search).get("graph");
        const first =
          available.find((g) => g.graph_id === (requested ?? primary)) ??
          available[0];
        let ids = available.map((g) => g.graph_id).slice(0, 19),
          restored = false;
        try {
          const saved = JSON.parse(
            localStorage.getItem("geographer.graphs.v1") ?? "null",
          );
          if (Array.isArray(saved)) {
            ids = saved
              .filter((id) => available.some((g) => g.graph_id === id))
              .slice(0, 19);
            restored = true;
          }
        } catch {}
        if (first) {
          setActive(first.graph_id);
          if (
            !restored ||
            ((requested || first.graph_id === primary) &&
              ids.length &&
              !ids.includes(first.graph_id))
          )
            ids = [
              first.graph_id,
              ...ids.filter((id) => id !== first.graph_id),
            ].slice(0, 19);
        }
        setSelected(ids);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => abort.abort();
  }, []);
  useEffect(() => {
    if (graphs.length)
      localStorage.setItem("geographer.graphs.v1", JSON.stringify(selected));
  }, [graphs.length, selected.join()]);
  const remember = useCallback(
    (graph: string, snapshot: string, id: string) =>
      setFocus((old) =>
        old[graph]?.id === id && old[graph]?.snapshot === snapshot
          ? old
          : { ...old, [graph]: { snapshot, id } },
      ),
    [],
  );
  const pick = useCallback((item: Omit<GraphPick, "serial">) => {
    setPending({ ...item, serial: crypto.randomUUID() });
    setActive(item.graph_id);
    setPickerOpen(false);
  }, []);
  const consume = useCallback(() => setPending(undefined), []);
  const settingsChanged = useCallback(
    (value: WorkspaceSettings) => setSettings(value),
    [],
  );
  const restoreGraphs = useCallback(
    (ids: string[]) =>
      setSelected(
        ids
          .filter((id) =>
            graphs.some(
              (g) => g.graph_id === id && g.availability !== "unavailable",
            ),
          )
          .slice(0, 19),
      ),
    [graphs],
  );
  function choose(id: string) {
    setPending(undefined);
    setActive(id);
    setSelected((old) => (old.includes(id) ? old : [...old, id].slice(0, 19)));
  }
  function toggle(id: string) {
    setSelected((old) => {
      const next = old.includes(id)
        ? old.filter((g) => g !== id)
        : [...old, id].slice(0, 19);
      if (id === active && !next.includes(id) && next.length)
        setActive(next[0]);
      return next;
    });
  }
  const graph = graphs.find((g) => g.graph_id === active);
  if (!graph)
    return (
      <main>
        <h1>Geo Grapher</h1>
        <p role={error ? "alert" : "status"}>
          {error || "Opening project graphs…"}
        </p>
      </main>
    );
  setWorkspaceGraph(active, graph.label, primary);
  const tools = (
    <>
      <label className="search-intent">
        Active graph{" "}
        <select
          aria-label="Active graph"
          value={active}
          onChange={(e) => choose(e.target.value)}
        >
          {graphs.map((g) => (
            <option
              key={g.graph_id}
              value={g.graph_id}
              disabled={g.availability === "unavailable"}
            >
              {g.label}
            </option>
          ))}
        </select>
      </label>
      <details
        className="workspace-graph-picker"
        open={pickerOpen}
        onToggle={(e) => setPickerOpen(e.currentTarget.open)}
      >
        <summary>Graphs ({selected.length})</summary>
        <div role="group" aria-label="Graphs to display">
          <p>
            Checked graphs share this view. Search, hierarchy and inspector
            follow the active graph; selecting a bubble activates its graph.
          </p>
          {graphs.map((g) => (
            <div className="workspace-graph-choice" key={g.graph_id}>
              <label>
                <input
                  type="checkbox"
                  checked={selected.includes(g.graph_id)}
                  disabled={
                    g.availability === "unavailable" ||
                    (!selected.includes(g.graph_id) && selected.length >= 19)
                  }
                  onChange={() => toggle(g.graph_id)}
                />
                {g.label}
              </label>
              <button
                disabled={
                  !selected.includes(g.graph_id) || selected[0] === g.graph_id
                }
                onClick={() =>
                  setSelected((old) => [
                    g.graph_id,
                    ...old.filter((id) => id !== g.graph_id),
                  ])
                }
                aria-label={`Centre graph ${g.label}`}
              >
                Centre
              </button>
            </div>
          ))}
          <label>
            <input
              type="checkbox"
              checked={showBridges}
              onChange={(e) => setShowBridges(e.target.checked)}
            />
            Show declared bridges
          </label>
          <GraphMergeReview
            graphIds={selected}
            onMerged={(id) => {
              fetch("/api/graphs")
                .then((r) => r.json())
                .then((data) => {
                  setGraphs(data.graphs);
                  setSelected([id]);
                  setActive(id);
                })
                .catch((e) => setError(e.message));
            }}
          />
          {error && <p role="alert">{error}</p>}
        </div>
      </details>
    </>
  );
  return (
    <App
      key={active}
      workspace={{
        active,
        graphs,
        selected,
        tools,
        settings,
        pending,
        consume,
        pick,
        settingsChanged,
        focus,
        remember,
        showBridges,
        restoreGraphs,
      }}
    />
  );
}
