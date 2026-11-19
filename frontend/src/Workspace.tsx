import { useCallback, useEffect, useMemo, useState } from "react";
import App from "./App";
import GraphMergeReview from "./GraphMergeReview";
import BridgeReview from "./BridgeReview";
import WorkspaceIngest from "./WorkspaceIngest";
import GraphActions from "./GraphLifecycle";
import DeriveSection from "./DeriveSection";
import CompareSection, { emptyCompare, type CompareState } from "./CompareSection";
import LinkSection, { emptyLink, type LinkDraft } from "./LinkSection";
import GraphSwatch from "./GraphSwatch";
import { ACCENTS, assignAccents, loadAccentChoices, saveAccentChoices } from "./accents";
import { getActiveGraphs, setActiveGraphs, setWorkspaceGraph } from "./api";
import { DEFAULT_MAX_GRAPHS, addGraph, initialSelection } from "./graphSelection";
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
  const [activeSet, setActiveSet] = useState<string[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  // What the Build tab is in the middle of. It lives here, not in the canvas view, because choosing something
  // on the canvas can make another graph the active one, and the canvas view then starts over.
  const [compare, setCompare] = useState<CompareState>(emptyCompare),
    [linkDraft, setLinkDraft] = useState<LinkDraft>(emptyLink),
    [linksVersion, setLinksVersion] = useState(0);
  const [accentChoices, setAccentChoices] = useState(loadAccentChoices);
  const accents = useMemo(
    () => assignAccents(graphs.map((g) => g.graph_id), accentChoices),
    [graphs.map((g) => g.graph_id).join(), accentChoices],
  );
  // Graphs the server keeps loaded at once (each is held in memory); /api/workspace/context says.
  const [maxGraphs, setMaxGraphs] = useState(DEFAULT_MAX_GRAPHS);
  const [focus, setFocus] = useState<
    Record<string, { snapshot: string; id: string }>
  >({});
  const primary =
    document
      .querySelector('meta[name="geographer-primary-graph"]')
      ?.getAttribute("content") ?? undefined;
  useEffect(() => {
    const abort = new AbortController();
    Promise.all([
      fetch("/api/graphs", { signal: abort.signal }).then((r) => {
        if (!r.ok) throw Error("Cannot load graph catalogue");
        return r.json();
      }),
      fetch("/api/workspace/context", { signal: abort.signal })
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null),
    ])
      .then(([data, context]) => {
        const max =
          Number.isInteger(context?.max_graphs) && context.max_graphs >= 1
            ? (context.max_graphs as number)
            : DEFAULT_MAX_GRAPHS;
        setMaxGraphs(max);
        const available: WorkspaceGraph[] = data.graphs.filter(
          (g: WorkspaceGraph) => g.availability !== "unavailable",
        );
        setGraphs(data.graphs);
        const requested = new URLSearchParams(location.search).get("graph");
        const first =
          available.find((g) => g.graph_id === (requested ?? primary)) ??
          available[0];
        let saved: string[] | null = null;
        try {
          const parsed = JSON.parse(
            localStorage.getItem("geographer.graphs.v1") ?? "null",
          );
          if (Array.isArray(parsed)) saved = parsed;
        } catch {}
        if (first) setActive(first.graph_id);
        setSelected(
          initialSelection({
            available: available.map((g) => g.graph_id),
            first: first?.graph_id,
            saved,
            max,
            forceFirst: Boolean(
              first && (requested || first.graph_id === primary),
            ),
          }),
        );
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
  useEffect(() => {
    getActiveGraphs()
      .then((r) => setActiveSet(r.graph_ids))
      .catch(() => {});
  }, []);
  async function reloadGraphs() {
    const data = await (await fetch("/api/graphs")).json();
    setGraphs(data.graphs);
    return data.graphs as WorkspaceGraph[];
  }
  async function toggleActive(id: string) {
    const next = activeSet.includes(id)
      ? activeSet.filter((g) => g !== id)
      : [...activeSet, id];
    if (next.length < 1 || next.length > maxGraphs) return;
    try {
      const saved = await setActiveGraphs(next);
      setActiveSet(saved.graph_ids);
      setSelected(saved.graph_ids);
      if (!saved.graph_ids.includes(active)) setActive(saved.graph_ids[0]);
    } catch (e) {
      setError((e as Error).message);
    }
  }
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
          .slice(0, maxGraphs),
      ),
    [graphs, maxGraphs],
  );
  function choose(id: string) {
    setPending(undefined);
    setActive(id);
    setSelected((old) => {
      const added = addGraph(old, id, maxGraphs);
      if (!added.full) return added.ids;
      // Full: the graph being replaced as active gives up its place.
      return old.includes(active)
        ? old.map((g) => (g === active ? id : g))
        : [...old.slice(0, -1), id];
    });
  }
  function toggle(id: string) {
    setSelected((old) => {
      const next = old.includes(id)
        ? old.filter((g) => g !== id)
        : addGraph(old, id, maxGraphs).ids;
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
      <label className="stacked-field">
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
          <p role="status">
            At most {maxGraphs} graphs stay loaded at once, because each one is
            held in memory.
            {selected.length >= maxGraphs
              ? " Uncheck one to show another."
              : ""}
          </p>
          {graphs.map((g) => (
            <div className="workspace-graph-choice" key={g.graph_id}>
              <label>
                <GraphSwatch accent={accents[g.graph_id]} />
                <input
                  type="checkbox"
                  checked={selected.includes(g.graph_id)}
                  disabled={
                    g.availability === "unavailable" ||
                    (!selected.includes(g.graph_id) &&
                      selected.length >= maxGraphs)
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
              <button
                aria-pressed={activeSet.includes(g.graph_id)}
                disabled={
                  g.availability === "unavailable" ||
                  (!activeSet.includes(g.graph_id) &&
                    activeSet.length >= maxGraphs) ||
                  (activeSet.includes(g.graph_id) && activeSet.length <= 1)
                }
                onClick={() => toggleActive(g.graph_id)}
                aria-label={`Active set ${g.label}`}
                title={`Shared scene members (at most ${maxGraphs})`}
              >
                Active
              </button>
              <select
                className="accent-select"
                aria-label={`Colour of ${g.label}`}
                title="The colour that marks this graph when several are shown"
                value={accents[g.graph_id]?.id ?? ""}
                onChange={(e) =>
                  setAccentChoices((old) => {
                    const next = { ...old, [g.graph_id]: e.target.value };
                    saveAccentChoices(next);
                    return next;
                  })
                }
              >
                {ACCENTS.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
              <GraphActions
                graph={g}
                onCopied={() => reloadGraphs().catch((e) => setError(e.message))}
                onDeleted={async (id) => {
                  try {
                    const rest = (await reloadGraphs()).filter(
                      (x) => x.availability !== "unavailable",
                    );
                    setSelected((old) => old.filter((x) => x !== id));
                    if (active === id && rest.length) setActive(rest[0].graph_id);
                    setActiveSet((await getActiveGraphs()).graph_ids);
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              />
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
          {error && <p role="alert">{error}</p>}
        </div>
      </details>
    </>
  );
  const labels = Object.fromEntries(graphs.map((g) => [g.graph_id, g.label]));
  // The Build tab of the right-hand panel: what makes something new. Each result is a new graph or a
  // declared link; the source graphs are never changed.
  const build = (
    <>
      <section aria-labelledby="build-add">
        <h2 id="build-add">Add a folder</h2>
        <p className="build-hint">
          Read a folder, see how it splits into parts, and choose which become graphs.
        </p>
        <WorkspaceIngest
          onIngested={() => {
            fetch("/api/graphs")
              .then((r) => r.json())
              .then((data) => setGraphs(data.graphs))
              .catch((e) => setError(e.message));
          }}
        />
      </section>
      <DeriveSection />
      <section aria-labelledby="build-combine">
        <h2 id="build-combine">Combine graphs</h2>
        <p className="build-hint">
          Works on the graphs checked in the Graphs tab ({selected.length} checked). The sources stay as they are.
        </p>
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
      </section>
      <CompareSection
        graphIds={selected}
        labels={labels}
        accents={accents}
        state={compare}
        setState={setCompare}
      />
      <LinkSection
        graphIds={selected}
        labels={labels}
        accents={accents}
        draft={linkDraft}
        setDraft={setLinkDraft}
        version={linksVersion}
        onChanged={() => setLinksVersion((v) => v + 1)}
      >
        <BridgeReview graphIds={selected} labels={labels} onDecided={() => setLinksVersion((v) => v + 1)} />
      </LinkSection>
      {error && <p role="alert">{error}</p>}
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
        build,
        settings,
        pending,
        consume,
        pick,
        settingsChanged,
        focus,
        remember,
        showBridges,
        accents,
        linksVersion,
        restoreGraphs,
        reloadGraphs,
      }}
    />
  );
}
