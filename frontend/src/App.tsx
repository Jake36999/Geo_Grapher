import { useCallback, useEffect, useRef, useState } from "react";
import type {
  Filter,
  ViewportFrameData,
  ViewportFrameRequest,
} from "../../contracts/geographer.wire";
import {
  base,
  graphBasePath,
  graphDisplayLabel,
  scopedStorageKey,
  defaultFilter,
  json,
  mergeFrame,
  query,
  shortName,
  shortRevision,
  validSaved,
  viewportPage,
  workspaceFrame,
  groupModes,
  type GroupMode,
  actorQuery,
  actorBase,
  runtimeFilter,
  visibilityPresets,
  visibilityFilter,
  currentVisibilityPreset,
  type VisibilityPreset,
  type Bootstrap,
  type Node,
  type Snapshot,
} from "./api";
import Scene, { type CameraState, type SceneHandle } from "./Scene";
import Hierarchy from "./Hierarchy";
import Matrix, { EntityList } from "./Matrix";
import Inspector from "./Inspector";
import type { WorkspaceControls } from "./workspaceTypes";
import { useGraphComposition } from "./useGraphComposition";
import { renderId } from "./composition";

type View = "spatial" | "list" | "matrix";
type Saved = {
  graph_ids?: string[];
  contextRadius?: 0 | 1 | 2;
  grouping?: GroupMode;
  modelDigest?: string;
  selectedVirtual?: boolean;
  pins?: string[];
  panelSizes?: [number, number];
  version: 1;
  name: string;
  snapshot_id: string;
  focus: string;
  revealed: string[];
  selected: string;
  camera?: CameraState;
  beta: number;
  lens: boolean;
  view: View;
  theme: "dark" | "light";
  filter: Filter;
};
type Frame = {
  data: ViewportFrameData;
  focus: string;
  navigation: string;
  scope: string;
};
export default function App({
  workspace,
}: { workspace?: WorkspaceControls } = {}) {
  const [boot, setBoot] = useState<Bootstrap>(),
    [bootAttempt, setBootAttempt] = useState(0),
    [snapshotId, setSnapshotId] = useState(""),
    [focus, setFocus] = useState(""),
    [selected, setSelected] = useState(""),
    [selectedEdge, setSelectedEdge] = useState("");
  const [nodes, setNodes] = useState<Record<string, Node>>({}),
    [revealed, setRevealed] = useState<string[]>([]),
    [frame, setFrame] = useState<Frame>(),
    [filter, setFilter] = useState<Filter>(
      workspace?.settings?.filter
        ? { ...workspace.settings.filter, repo_ids: [] }
        : defaultFilter,
    );
  const [view, setView] = useState<View>(
      () =>
        workspace?.settings?.view ??
        (new URLSearchParams(location.search).get("view") === "spatial"
          ? "spatial"
          : innerWidth < 720
            ? "list"
            : "spatial"),
    ),
    [theme, setTheme] = useState<"dark" | "light">(
      workspace?.settings?.theme ?? "dark",
    ),
    [beta, setBeta] = useState(workspace?.settings?.beta ?? 0.8),
    [lens, setLens] = useState(workspace?.settings?.lens ?? false);
  const [contextRadius, setContextRadius] = useState<0 | 1 | 2>(
    workspace?.settings?.contextRadius ?? 0,
  );
  const [collectionChoice, setCollectionChoice] = useState(""),
    [collectionReport, setCollectionReport] = useState<unknown>();
  const [grouping, setGrouping] = useState<GroupMode>(
      workspace?.settings?.grouping ?? "mixed",
    ),
    [modelDigest, setModelDigest] = useState("");
  const [rulesOpen, setRulesOpen] = useState(false),
    [rulesText, setRulesText] = useState(""),
    [rulesMessage, setRulesMessage] = useState("");
  const [pathIds, setPathIds] = useState<string[]>([]),
    [pathProjection, setPathProjection] = useState<{
      steps: {
        relationship_id: string;
        source: string;
        target: string;
        projections: {
          projection_id: string;
          source_rep_id: string;
          target_rep_id: string;
        }[];
      }[];
    }>();
  const [violations, setViolations] = useState<string[]>([]);
  const [pins, setPins] = useState<string[]>([]),
    [panelSizes, setPanelSizes] = useState<[number, number]>(
      workspace?.settings?.panelSizes ?? [235, 330],
    ),
    [coverageOpen, setCoverageOpen] = useState(false),
    [coverageFailures, setCoverageFailures] = useState<
      { repo_id: string; rel_path: string; language: string; message: string }[]
    >([]);
  const [loading, setLoading] = useState(false),
    [viewFailed, setViewFailed] = useState(false),
    [status, setStatus] = useState("Opening the local workspace…"),
    [error, setError] = useState(""),
    [drawer, setDrawer] = useState<"hierarchy" | "inspector" | null>(null);
  const [search, setSearch] = useState(""),
    [results, setResults] = useState<Node[]>([]),
    [searching, setSearching] = useState(false),
    [navExternal, setNavExternal] = useState(false),
    [navDocuments, setNavDocuments] = useState(false);
  const [searchMode, setSearchMode] = useState<
    "lexical" | "hybrid" | "documentation"
  >("lexical");
  const [searchProject, setSearchProject] = useState("");
  const [choices, setChoices] = useState<{
      ids: string[];
      edge: boolean;
    } | null>(null),
    [history, setHistory] = useState<
      {
        focus: string;
        revealed: string[];
        contextRadius: 0 | 1 | 2;
        camera?: CameraState;
      }[]
    >([]),
    [navigation, setNavigation] = useState(0);
  const [saved, setSaved] = useState<Saved[]>(() => {
    try {
      const data = JSON.parse(
        localStorage.getItem(scopedStorageKey("geographer.views.v1")) ?? "[]",
      );
      return Array.isArray(data) ? data.filter(validSaved).slice(-30) : [];
    } catch {
      return [];
    }
  });
  const [saveOpen, setSaveOpen] = useState(false),
    [saveName, setSaveName] = useState(""),
    [initialCamera, setInitialCamera] = useState<CameraState>();
  const scope = JSON.stringify([
    snapshotId,
    focus,
    revealed,
    filter,
    pins,
    contextRadius,
    grouping,
    modelDigest,
    navigation,
  ]);
  const frameCurrent = frame?.scope === scope;
  const scene = useRef<SceneHandle>(null),
    request = useRef<ViewportFrameRequest | undefined>(undefined),
    cursor = useRef<string | null>(null),
    active = useRef(new AbortController()),
    sequence = useRef(0),
    searchGeneration = useRef(0),
    dialog = useRef<HTMLDialogElement>(null),
    picker = useRef<HTMLDialogElement>(null);
  const retainedCamera = useRef<CameraState | undefined>(undefined);
  function captureCamera() {
    if (frameCurrent) {
      const camera = scene.current?.capture();
      if (camera) retainedCamera.current = camera;
    }
    return retainedCamera.current;
  }
  function changeView(next: View) {
    setInitialCamera(captureCamera());
    setView(next);
  }
  function changeDetail(next: 0 | 1 | 2) {
    retainedCamera.current = undefined;
    setInitialCamera(undefined);
    setContextRadius(next);
    setNavigation((n) => n + 1);
  }
  const snapshot = boot?.snapshots.find((s) => s.snapshot_id === snapshotId),
    snapshotRef = useRef(snapshot);
  snapshotRef.current = snapshot;
  const [inspectionFrame, setInspectionFrame] = useState<ViewportFrameData>();
  const inspectionScope = useRef("");
  const composition = useGraphComposition(
    workspace,
    frame?.data,
    snapshot?.snapshot_id,
    filter,
    grouping,
    contextRadius,
    modelDigest,
  );
  useEffect(() => {
    workspace?.settingsChanged({
      view,
      theme,
      beta,
      lens,
      contextRadius,
      grouping,
      filter,
      panelSizes,
    });
  }, [view, theme, beta, lens, contextRadius, grouping, filter, panelSizes]);
  useEffect(() => {
    if (workspace && snapshot && focus)
      workspace.remember(workspace.active, snapshot.snapshot_id, focus);
  }, [workspace?.active, snapshot?.snapshot_id, focus]);
  useEffect(() => {
    const pending = workspace?.pending;
    if (!pending || pending.graph_id !== workspace?.active || !boot) return;
    const target = boot.snapshots.find(
      (s) => s.snapshot_id === pending.snapshot_id,
    );
    if (!target) {
      setError("Selected graph snapshot is no longer available");
      workspace.consume();
      return;
    }
    if (snapshotId !== pending.snapshot_id) {
      chooseSnapshot(target);
      return;
    }
    addNodes(pending.frame.nodes as Node[]);
    setInspectionFrame(pending.frame);
    inspectionScope.current = scope;
    if (pending.camera) {
      setInitialCamera(pending.camera);
      retainedCamera.current = pending.camera;
    }
    if (pending.edge) {
      const edge = pending.frame.relationships.find(
        (r) => r.id === pending.local_id,
      );
      if (edge) {
        setSelected(edge.source);
        setSelectedEdge(edge.id);
      }
    } else {
      setSelected(pending.local_id);
      setSelectedEdge("");
    }
    if (pending.enter) {
      const node = pending.frame.nodes.find((n) => n.id === pending.local_id);
      const id = node?.entity_id ?? node?.parent_id;
      if (id) {
        setFocus(id);
        setRevealed((old) => [...new Set([...old, id])]);
        setContextRadius(1);
        setNavigation((n) => n + 1);
        setInspectionFrame(undefined);
      }
    } else setDrawer("inspector");
    workspace.consume();
  }, [workspace?.pending?.serial, boot, snapshotId]);
  useEffect(() => {
    if (inspectionScope.current !== scope) setInspectionFrame(undefined);
  }, [scope]);
  const activeSearchProject =
    searchProject ||
    (snapshot?.repositories.some((n) => n.repo_id === nodes[focus]?.repo_id)
      ? nodes[focus]?.repo_id
      : snapshot?.repositories[0]?.repo_id) ||
    "";
  const searchRepoIds =
    activeSearchProject === "@all"
      ? (snapshot?.repositories.map((n) => n.repo_id) ?? [])
      : activeSearchProject
        ? [activeSearchProject]
        : [];
  const activeCollection = snapshot?.runtime_collections?.find(
    (c) =>
      c.environment === filter.runtime_window?.environment &&
      c.window.start === filter.runtime_window?.start &&
      c.window.end === filter.runtime_window?.end,
  );
  const chosenCollection =
    activeCollection ??
    snapshot?.runtime_collections?.find(
      (c) => c.collection_id === collectionChoice,
    ) ??
    snapshot?.runtime_collections?.[0];
  const collectionScope = JSON.stringify([
      snapshotId,
      chosenCollection?.collection_id,
    ]),
    collectionScopeRef = useRef(collectionScope);
  collectionScopeRef.current = collectionScope;
  const addNodes = useCallback(
    (incoming: Node[]) =>
      setNodes((old) => {
        const next = { ...old };
        for (const n of incoming) next[n.id] = n;
        const keys = Object.keys(next);
        if (keys.length > 6000)
          for (const k of keys.slice(0, keys.length - 6000)) delete next[k];
        return next;
      }),
    [],
  );
  function chooseSnapshot(s: Snapshot) {
    active.current.abort();
    setSnapshotId(s.snapshot_id);
    setSearchProject("");
    setFilter((f) => runtimeFilter(f));
    setCollectionChoice(s.runtime_collections?.[0]?.collection_id ?? "");
    setCollectionReport(undefined);
    const remembered = workspace?.focus[workspace.active];
    const home =
      remembered?.snapshot === s.snapshot_id
        ? remembered.id
        : s.repositories.length > 1
          ? s.root.id
          : (s.repositories[0]?.id ?? s.root.id);
    setFocus(home);
    setSelected(home);
    setRevealed([s.root.id, ...s.repositories.map((n) => n.id)]);
    setNodes(
      Object.fromEntries([s.root, ...s.repositories].map((n) => [n.id, n])),
    );
    setSelectedEdge("");
    setPins([]);
    setContextRadius(workspace?.settings?.contextRadius ?? 0);
    setGrouping(workspace?.settings?.grouping ?? "mixed");
    setPathIds([]);
    setPathProjection(undefined);
    setFrame(undefined);
    setHistory([]);
    setInitialCamera(undefined);
    retainedCamera.current = undefined;
    setNavigation((n) => n + 1);
    setError("");
    searchGeneration.current++;
    setViewFailed(false);
    setSearch("");
    setResults([]);
    setSearching(false);
  }
  useEffect(() => {
    const abort = new AbortController();
    json<Bootstrap>("/api/v1/bootstrap", undefined, abort.signal)
      .then((b) => {
        setBoot(b);
        setModelDigest(b.models[0]?.digest ?? "");
        if (b.snapshots[0]) chooseSnapshot(b.snapshots[0]);
        else setStatus("No published snapshots. Ingest a repository to begin.");
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => abort.abort();
  }, [bootAttempt]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    if (choices) picker.current?.showModal();
  }, [choices]);
  useEffect(() => {
    if (saveOpen) dialog.current?.showModal();
    else dialog.current?.close();
  }, [saveOpen]);
  useEffect(() => {
    if (!drawer) return;
    const media = matchMedia(
      drawer === "hierarchy" ? "(max-width:1439px)" : "(max-width:1024px)",
    );
    if (!media.matches) return;
    const toggle = document.querySelector<HTMLButtonElement>(
      `[data-drawer-toggle="${drawer}"]`,
    );
    const opener =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : toggle;
    const panel = document.querySelector<HTMLElement>(`.${drawer}-panel`);
    panel?.querySelector<HTMLButtonElement>(".drawer-dismiss")?.focus();
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !document.querySelector("dialog[open]")) {
        event.preventDefault();
        setDrawer(null);
      }
    };
    const resize = () => {
      if (!media.matches) setDrawer(null);
    };
    document.addEventListener("keydown", dismiss);
    media.addEventListener("change", resize);
    return () => {
      document.removeEventListener("keydown", dismiss);
      media.removeEventListener("change", resize);
      const target =
        opener?.isConnected && opener.getClientRects().length ? opener : toggle;
      if (target?.getClientRects().length) target.focus();
      else document.getElementById("main-view")?.focus();
    };
  }, [drawer]);
  useEffect(() => {
    if (!snapshot || !focus) return;
    active.current.abort();
    const abort = new AbortController();
    active.current = abort;
    const generation = ++sequence.current;
    setLoading(true);
    setViewFailed(false);
    setError("");
    cursor.current = null;
    const q: ViewportFrameRequest = {
      ...base(snapshot.snapshot_id, 32768),
      focus_id: focus,
      revealed_ids: revealed,
      pins,
      context_radius: contextRadius,
      filter,
      layout_version: "sphere-pack-v1",
      seed: "geographer-workspace-v1",
      beta,
      edge_lens: { enabled: lens, center: [0, 0, 0], radius: 5, strength: 0.8 },
      node_budget: 500,
      curve_budget: 2000,
      viewport: {
        width_px: Math.max(1, innerWidth),
        height_px: Math.max(1, innerHeight),
        device_pixel_ratio: devicePixelRatio,
      },
      camera: {
        eye: [20, 14, 26],
        target: [0, 0, 0],
        up: [0, 1, 0],
        fov_y_degrees: 45,
        near: 0.01,
        far: 1000000,
      },
    };
    request.current = q;
    void (async () => {
      try {
        let r = await workspaceFrame(q, grouping, modelDigest, abort.signal);
        let combined = r.data;
        for (let page = 0; ; page++) {
          if (generation !== sequence.current) return;
          addNodes(r.data.nodes);
          setFrame({
            data: combined,
            focus,
            navigation: String(navigation),
            scope,
          });
          cursor.current = r.data.completeness.next_cursor;
          if (!cursor.current || page >= 15) break;
          r = await workspaceFrame(
            q,
            grouping,
            modelDigest,
            abort.signal,
            cursor.current,
          );
          combined = mergeFrame(combined, r.data);
        }
        setStatus(
          cursor.current
            ? "A budgeted scene is ready. Load more to continue."
            : contextRadius === 0
              ? "Overview ready. Enter a container or reveal nearby detail."
              : "Architecture view ready. Select to inspect; enter to navigate.",
        );
      } catch (e) {
        if (
          (e as Error).name !== "AbortError" &&
          generation === sequence.current
        ) {
          setError((e as Error).message);
          setViewFailed(true);
        }
      } finally {
        if (generation === sequence.current) setLoading(false);
      }
    })();
    return () => abort.abort();
  }, [
    snapshotId,
    focus,
    JSON.stringify(revealed),
    JSON.stringify(filter),
    JSON.stringify(pins),
    contextRadius,
    grouping,
    modelDigest,
    navigation,
  ]);
  useEffect(() => {
    if (!coverageOpen || !frame?.data.coverage.report_handle) return;
    const abort = new AbortController();
    json<{ failures: typeof coverageFailures }>(
      "/api/v1/handles/" +
        encodeURIComponent(frame.data.coverage.report_handle),
      undefined,
      abort.signal,
    )
      .then((r) => setCoverageFailures(r.failures))
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => abort.abort();
  }, [coverageOpen, frame?.data.coverage.report_handle]);
  async function more() {
    if (!cursor.current || !request.current) return;
    const generation = sequence.current;
    setLoading(true);
    try {
      const r = await workspaceFrame(
        request.current,
        grouping,
        modelDigest,
        active.current.signal,
        cursor.current,
      );
      if (generation !== sequence.current) return;
      addNodes(r.data.nodes);
      setFrame((old) =>
        old ? { ...old, data: mergeFrame(old.data, r.data) } : old,
      );
      cursor.current = r.data.completeness.next_cursor;
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      if (generation === sequence.current) setLoading(false);
    }
  }
  useEffect(() => {
    setPathProjection(undefined);
    if (!frameCurrent || !frame?.data.view_id || !pathIds.length) return;
    const abort = new AbortController();
    json<NonNullable<typeof pathProjection>>(
      "/api/workspace/path",
      {
        snapshot_id: snapshotId,
        view_id: frame.data.view_id,
        relationship_ids: pathIds,
      },
      abort.signal,
    )
      .then(setPathProjection)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => abort.abort();
  }, [frameCurrent, frame?.data.view_id, JSON.stringify(pathIds), snapshotId]);
  function highlightPath(ids: string[], entities: string[]) {
    setPathIds(ids);
    setPins((old) => [...new Set([...old, ...entities])].slice(0, 8));
  }
  useEffect(() => {
    setViolations([]);
    if (!frameCurrent || !frame?.data.view_id || !modelDigest) return;
    const abort = new AbortController();
    const ids = frame.data.relationships.map((r) => r.id),
      viewId = frame.data.view_id;
    (async () => {
      const warnings: string[] = [];
      for (let offset = 0; offset < ids.length; offset += 2000) {
        const r = await json<{ warning_projection_ids: string[] }>(
          "/api/workspace/semantics",
          {
            snapshot_id: snapshotId,
            view_id: viewId,
            model_digest: modelDigest,
            projection_ids: ids.slice(offset, offset + 2000),
          },
          abort.signal,
        );
        warnings.push(...r.warning_projection_ids);
      }
      if (!abort.signal.aborted) setViolations(warnings);
    })().catch((e) => {
      if (e.name !== "AbortError") setError(e.message);
    });
    return () => abort.abort();
  }, [
    frameCurrent,
    frame?.data.view_id,
    frame?.data.relationships.length,
    modelDigest,
    snapshotId,
  ]);
  useEffect(() => {
    const generation = ++searchGeneration.current;
    setResults([]);
    if (!snapshot || search.trim().length < 2) {
      setSearching(false);
      return;
    }
    setSearching(true);
    const abort = new AbortController();
    const timer = setTimeout(() => {
      setSearching(true);
      (searchMode === "lexical"
        ? query(
            "search_entities",
            {
              ...base(snapshot.snapshot_id),
              query: search.trim(),
              mode: "lexical",
              repo_ids: searchRepoIds,
              kinds: [
                "file",
                "directory",
                "class",
                "function",
                "method",
                "repository",
                "package",
                "document",
              ],
              limit: 20,
              cursor: null,
            },
            abort.signal,
          )
        : actorQuery(
            "search_entities",
            {
              ...actorBase(snapshot.snapshot_id),
              query: search.trim(),
              mode: searchMode,
              repo_ids: searchRepoIds,
              kinds: [],
              limit: 20,
              cursor: null,
            },
            abort.signal,
          )
      )
        .then((r) => {
          if (generation !== searchGeneration.current) return;
          const ordered = r.data.hits
            .map((h) => r.data.nodes.find((n) => n.id === h.node_id))
            .filter(Boolean) as Node[];
          setResults(ordered);
          addNodes(r.data.nodes as Node[]);
        })
        .catch((e) => {
          if (
            e.name !== "AbortError" &&
            generation === searchGeneration.current
          )
            setError(e.message);
        })
        .finally(() => {
          if (!abort.signal.aborted && generation === searchGeneration.current)
            setSearching(false);
        });
    }, 220);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [search, snapshotId, navExternal, searchMode, activeSearchProject]);
  async function select(id: string) {
    setInspectionFrame(undefined);
    setSelected(id);
    setSelectedEdge("");
    setDrawer("inspector");
    if (nodes[id] || !snapshot) return;
    const sid = snapshot.snapshot_id;
    try {
      const r = await json<{ nodes: Node[] }>("/api/v1/entities", {
        snapshot_id: snapshot.snapshot_id,
        ids: [id],
      });
      if (snapshotRef.current?.snapshot_id !== sid) return;
      addNodes(r.nodes);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function enter(id: string) {
    const origin = composition?.origins.get(id);
    if (origin && workspace) {
      const source = composition?.frames.find(
        (f) => f.graph_id === origin.graph_id,
      );
      if (source?.frame && source.snapshot_id)
        workspace.pick({
          graph_id: origin.graph_id,
          snapshot_id: source.snapshot_id,
          local_id: origin.local_id,
          edge: false,
          enter: true,
          frame: source.frame,
          camera: scene.current?.capture(),
        });
      return;
    }
    setInspectionFrame(undefined);
    const n = frame?.data.nodes.find((x) => x.id === id) ?? nodes[id];
    if (n?.entity_id === null) {
      void select(id);
      setStatus(
        "This summary preserves membership. Enter its enclosing source container to reveal more detail.",
      );
      return;
    }
    if (id === focus) {
      if (contextRadius === 0) {
        changeDetail(1);
      } else scene.current?.fit();
      return;
    }
    setContextRadius(1);
    setHistory((old) => [
      ...old.slice(-49),
      { focus, revealed, contextRadius, camera: captureCamera() },
    ]);
    retainedCamera.current = undefined;
    setInitialCamera(undefined);
    setFocus(id);
    setSelected(id);
    setSelectedEdge("");
    setRevealed((old) => [...new Set([...old.slice(-255), id])]);
    setNavigation((n) => n + 1);
    setSearch("");
    setDrawer(null);
  }
  function back() {
    const previous = history.at(-1);
    if (!previous) return;
    setHistory((old) => old.slice(0, -1));
    setFocus(previous.focus);
    setSelected(previous.focus);
    setRevealed(previous.revealed);
    setContextRadius(previous.contextRadius);
    setInitialCamera(previous.camera);
    retainedCamera.current = previous.camera;
    setNavigation((n) => n + 1);
  }
  function pick(ids: string[], _position?: unknown, edge = false) {
    if (
      composition &&
      workspace &&
      ids.some((id) => composition.origins.has(id))
    ) {
      if (ids.length !== 1) {
        setChoices({ ids, edge });
        return;
      }
      const origin = composition.origins.get(ids[0]);
      if (!origin) return;
      const source = composition.frames.find(
        (f) => f.graph_id === origin.graph_id,
      );
      if (source?.frame && source.snapshot_id)
        workspace.pick({
          graph_id: origin.graph_id,
          snapshot_id: source.snapshot_id,
          local_id: origin.local_id,
          edge,
          enter: false,
          frame: source.frame,
          camera: scene.current?.capture(),
        });
      return;
    }
    if (!frameCurrent) return;
    if (ids.length !== 1) {
      setChoices({ ids, edge });
      return;
    }
    if (edge) {
      const relation = (inspectionFrame ?? frame?.data)?.relationships.find(
        (r) => r.id === ids[0],
      );
      if (relation) {
        setSelected(relation.source);
        setSelectedEdge(relation.id);
        setDrawer("inspector");
      }
    } else void select(ids[0]);
  }
  function save() {
    if (!snapshot || !frameCurrent || !saveName.trim()) return;
    const entry: Saved = {
      graph_ids: workspace?.selected,
      version: 1,
      contextRadius,
      grouping,
      modelDigest,
      selectedVirtual: current?.entity_id === null,
      pins,
      panelSizes,
      name: saveName.trim().slice(0, 80),
      snapshot_id: snapshotId,
      focus,
      revealed,
      selected,
      camera: captureCamera(),
      beta,
      lens,
      view,
      theme,
      filter,
    };
    const next = [...saved.filter((x) => x.name !== entry.name), entry].slice(
      -30,
    );
    try {
      localStorage.setItem(
        scopedStorageKey("geographer.views.v1"),
        JSON.stringify(next),
      );
      setSaved(next);
      setSaveOpen(false);
      setStatus(`Saved view “${entry.name}”.`);
    } catch {
      setError(
        "The browser could not save this view. Local storage may be full or disabled.",
      );
    }
  }
  async function restore(name: string) {
    const entry = saved.find((x) => x.name === name),
      s = boot?.snapshots.find((x) => x.snapshot_id === entry?.snapshot_id);
    if (!entry) return;
    if (!s) {
      setError(
        "This saved view belongs to an unavailable snapshot. Ingest or reopen that snapshot before restoring it.",
      );
      return;
    }
    try {
      const generation = sequence.current;
      const ids = [
        ...new Set([
          entry.focus,
          ...(entry.selectedVirtual ? [] : [entry.selected]),
          ...entry.revealed,
          ...(entry.pins ?? []),
        ]),
      ];
      if (ids.length > 500)
        throw new Error("Saved view exceeds the supported identifier limit.");
      const check =
        snapshotId === entry.snapshot_id && ids.every((id) => nodes[id])
          ? { nodes: ids.map((id) => nodes[id]), missing_ids: [] }
          : await json<{ nodes: Node[]; missing_ids: string[] }>(
              "/api/v1/entities",
              { snapshot_id: s.snapshot_id, ids },
            );
      if (generation !== sequence.current) return;
      if (check.missing_ids.length)
        throw new Error(
          `Saved view contains ${check.missing_ids.length} missing entities; it has not been restored.`,
        );
      if (
        entry.grouping === "conceptual" &&
        !boot?.models.some((m) => m.digest === entry.modelDigest)
      )
        throw new Error(
          "Saved rules model is unavailable. Load it before restoring this view.",
        );
      if (
        entry.filter.runtime_window &&
        !s.runtime_collections?.some(
          (c) =>
            c.source_match &&
            c.environment === entry.filter.runtime_window?.environment &&
            c.window.start === entry.filter.runtime_window?.start &&
            c.window.end === entry.filter.runtime_window?.end,
        )
      )
        throw new Error(
          "Saved runtime collection is unavailable for this snapshot.",
        );
      chooseSnapshot(s);
      addNodes(check.nodes);
      setContextRadius(entry.contextRadius ?? 1);
      setGrouping(entry.grouping ?? "mixed");
      setModelDigest(entry.modelDigest ?? "");
      setFocus(entry.focus);
      setSelected(entry.selected);
      setRevealed(entry.revealed);
      setPins(entry.pins ?? []);
      setPanelSizes(entry.panelSizes ?? [235, 330]);
      setBeta(entry.beta);
      setLens(entry.lens);
      setView(entry.view);
      setTheme(entry.theme);
      setFilter(entry.filter);
      if (entry.graph_ids) workspace?.restoreGraphs(entry.graph_ids);
      setCollectionChoice(
        s.runtime_collections?.find(
          (c) =>
            c.environment === entry.filter.runtime_window?.environment &&
            c.window.start === entry.filter.runtime_window?.start &&
            c.window.end === entry.filter.runtime_window?.end,
        )?.collection_id ??
          s.runtime_collections?.[0]?.collection_id ??
          "",
      );
      setInitialCamera(entry.camera);
      retainedCamera.current = entry.camera;
      setStatus(`Restored view “${entry.name}” with its original snapshot.`);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const current =
      frame?.data.nodes.find((n) => n.id === selected) ?? nodes[selected],
    edge = (inspectionFrame ?? frame?.data)?.relationships.find(
      (r) => r.id === selectedEdge,
    ),
    focusNode = nodes[focus];
  const ancestors: Node[] = [];
  let ancestor: Node | undefined = focusNode;
  const visited = new Set<string>();
  while (ancestor && !visited.has(ancestor.id)) {
    visited.add(ancestor.id);
    ancestors.unshift(ancestor);
    ancestor = ancestor.parent_id ? nodes[ancestor.parent_id] : undefined;
  }
  function toggleFlag(
    key:
      | "include_tests"
      | "include_generated"
      | "include_vendor"
      | "include_external",
  ) {
    setFilter((old) => ({ ...old, [key]: !old[key] }));
  }
  return (
    <div
      className={`application${graphBasePath() !== "/" ? " graph-pane" : ""}${workspace ? " integrated-workspace" : ""}`}
      style={
        {
          "--left-panel": `${panelSizes[0]}px`,
          "--right-panel": `${panelSizes[1]}px`,
        } as React.CSSProperties
      }
    >
      <a className="skip-link" href="#main-view">
        Skip to architecture view
      </a>
      <header className="app-header">
        <a
          className="brand"
          href={workspace ? "/" : graphBasePath()}
          aria-label="Geo Grapher home"
        >
          <span className="brand-mark" aria-hidden="true">
            ◉
          </span>{" "}
          Geo Grapher
        </a>
        <span className="local-badge">LOCAL WORKSPACE</span>
        {workspace?.tools}
        <label className="sr-only" htmlFor="snapshot">
          Repository snapshot
        </label>
        <select
          id="snapshot"
          value={snapshotId}
          onChange={(e) => {
            const s = boot?.snapshots.find(
              (x) => x.snapshot_id === e.target.value,
            );
            if (s) chooseSnapshot(s);
          }}
        >
          {boot?.snapshots.map((s) => (
            <option key={s.snapshot_id} value={s.snapshot_id}>
              {graphDisplayLabel() ??
                s.revisions.map((r) => r.repo_id).join(" + ")}{" "}
              · {shortRevision(s.revisions[0]?.revision ?? "")} ·{" "}
              {s.snapshot_id.slice(-6)}
            </option>
          ))}
        </select>
        {snapshot && snapshot.repositories.length > 1 && (
          <label className="search-intent">
            Search project
            <select
              aria-label="Search project"
              value={activeSearchProject}
              onChange={(e) => setSearchProject(e.target.value)}
            >
              {snapshot.repositories.map((n) => (
                <option key={n.id} value={n.repo_id}>
                  {n.repo_id}
                </option>
              ))}
              <option value="@all">All projects (explicit)</option>
            </select>
          </label>
        )}
        <label className="search-intent">
          Search intent
          <select
            aria-label="Search intent"
            disabled={!snapshot}
            value={searchMode}
            onChange={(e) => setSearchMode(e.target.value as typeof searchMode)}
          >
            <option value="lexical">Symbols / paths</option>
            <option value="hybrid">Code + documents</option>
            <option value="documentation">Documents</option>
          </select>
        </label>
        <div className="search-wrap">
          <label className="sr-only" htmlFor="search">
            Search entities
          </label>
          <input
            id="search"
            type="search"
            disabled={!snapshot}
            value={search}
            onChange={(e) => {
              searchGeneration.current++;
              setResults([]);
              setSearching(e.target.value.trim().length >= 2);
              setSearch(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                e.preventDefault();
                e.stopPropagation();
                searchGeneration.current++;
                setSearch("");
                setResults([]);
                setSearching(false);
              }
            }}
            placeholder={
              snapshot
                ? "Search files, classes, functions…"
                : "Loading repository snapshots…"
            }
            autoComplete="off"
          />
          {search.trim().length >= 2 && (
            <div className="search-results">
              <p role="status" aria-live="polite">
                {searching
                  ? "Searching…"
                  : `${results.length} results · ${activeSearchProject === "@all" ? "all selected projects" : activeSearchProject}`}
              </p>
              {results.map((n) => (
                <div key={n.id}>
                  <button
                    onClick={() => {
                      void select(n.id);
                      setSearch("");
                    }}
                  >
                    <span className="kind-badge">{n.kind}</span>
                    {snapshot && snapshot.repositories.length > 1 && (
                      <span className="kind-badge">{n.repo_id}</span>
                    )}
                    <span>{n.qualified_name}</span>
                  </button>
                  <button
                    aria-label={`Enter ${shortName(n)}`}
                    onClick={() => enter(n.id)}
                  >
                    ↗
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
        <button
          className="theme-button"
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          aria-label={`Use ${theme === "dark" ? "light" : "dark"} theme`}
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
        <button
          onClick={() => {
            setSaveName("");
            setSaveOpen(true);
          }}
          disabled={!snapshot || !frameCurrent}
        >
          Save view
        </button>
        <label className="sr-only" htmlFor="saved-views">
          Restore saved view
        </label>
        <select
          id="saved-views"
          value=""
          onChange={(e) => void restore(e.target.value)}
        >
          <option value="">Saved views</option>
          {saved.map((v) => (
            <option key={v.name}>{v.name}</option>
          ))}
        </select>
      </header>
      <div
        className="navigation-bar"
        role="region"
        aria-label="Workspace navigation"
      >
        <button
          onClick={back}
          disabled={!history.length}
          aria-label="Navigate back"
        >
          ←
        </button>
        <button
          onClick={() => focusNode?.parent_id && enter(focusNode.parent_id)}
          disabled={!focusNode?.parent_id}
          aria-label="Enter parent container"
        >
          ↑
        </button>
        <button
          onClick={() =>
            snapshot &&
            enter(
              snapshot.repositories.length > 1
                ? snapshot.root.id
                : (snapshot.repositories[0]?.id ?? snapshot.root.id),
            )
          }
          disabled={!snapshot}
        >
          Home
        </button>
        <nav className="breadcrumbs" aria-label="Containment path">
          {ancestors.map((n, i) => (
            <span key={n.id}>
              {i > 0 && <span aria-hidden="true"> / </span>}
              <button
                onClick={() => enter(n.id)}
                aria-current={n.id === focus ? "location" : undefined}
              >
                {shortName(n)}
              </button>
            </span>
          ))}
        </nav>
        <span className="static-badge" role="note" aria-label="Analysis mode">
          {filter.families.includes("runtime")
            ? filter.families.includes("static")
              ? "STATIC + OBSERVED"
              : "OBSERVATIONS"
            : filter.families.includes("static")
              ? "STATIC ANALYSIS"
              : "CONTAINMENT ONLY"}
        </span>
      </div>
      <div className="mobile-navigation">
        <button
          data-drawer-toggle="hierarchy"
          aria-expanded={drawer === "hierarchy"}
          onClick={() =>
            setDrawer((d) => (d === "hierarchy" ? null : "hierarchy"))
          }
        >
          Hierarchy
        </button>
        <button
          data-drawer-toggle="inspector"
          aria-expanded={drawer === "inspector"}
          onClick={() =>
            setDrawer((d) => (d === "inspector" ? null : "inspector"))
          }
        >
          Inspector
        </button>
      </div>
      <div className="workspace">
        <aside
          className={`hierarchy-panel side-panel ${drawer === "hierarchy" ? "drawer-open" : ""}`}
          aria-label="Repository hierarchy"
        >
          <button className="drawer-dismiss" onClick={() => setDrawer(null)}>
            Close hierarchy
          </button>
          <div className="panel-heading">
            <h2>Hierarchy</h2>
            <span className="secondary">Containment</span>
          </div>
          <div className="hierarchy-options">
            <label>
              <input
                type="checkbox"
                checked={navExternal}
                onChange={(e) => setNavExternal(e.target.checked)}
              />
              External references
            </label>
            <label>
              <input
                type="checkbox"
                checked={navDocuments}
                onChange={(e) => setNavDocuments(e.target.checked)}
              />
              Documentation
            </label>
          </div>
          {snapshot && (
            <Hierarchy
              snapshot={snapshot}
              selected={selected}
              onSelect={(n) => {
                addNodes([n]);
                void select(n.id);
              }}
              onEnter={enter}
              onNodes={addNodes}
              external={navExternal}
              documents={navDocuments}
            />
          )}
          <p className="navigation-hint">
            Select to inspect. Shift+Enter or double click to enter. Arrow keys
            move through the list.
          </p>
        </aside>
        <main id="main-view" className="main-view" tabIndex={-1}>
          <div className="workspace-heading">
            <div>
              <span className="eyebrow">ARCHITECTURE AT A GLANCE</span>
              <h1>
                {focusNode ? shortName(focusNode) : "Repository workspace"}
              </h1>
              {workspace && (
                <small className="workspace-scope-caption">
                  {workspace.selected.length} graph(s) displayed · Active:{" "}
                  {
                    workspace.graphs.find(
                      (g) => g.graph_id === workspace.active,
                    )?.label
                  }
                </small>
              )}
            </div>
            <div
              className="view-switch"
              role="group"
              aria-label="Architecture representation"
            >
              {(["spatial", "list", "matrix"] as View[]).map((v) => (
                <button
                  key={v}
                  aria-pressed={view === v}
                  onClick={() => changeView(v)}
                >
                  {v === "spatial"
                    ? "3D space"
                    : v === "list"
                      ? "List"
                      : "Matrix"}
                </button>
              ))}
            </div>
          </div>
          <div className="filter-bar">
            <label>
              Relationships{" "}
              <select
                aria-label="Relationship visibility preset"
                value={currentVisibilityPreset(filter)}
                onChange={(e) =>
                  setFilter((f) =>
                    visibilityFilter(f, e.target.value as VisibilityPreset),
                  )
                }
              >
                <option value="custom" disabled>
                  Custom scope
                </option>
                {(Object.keys(visibilityPresets) as VisibilityPreset[]).map(
                  (key) => (
                    <option key={key} value={key}>
                      {visibilityPresets[key].label}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label>
              Abstraction
              <select
                aria-label="Abstraction grouping"
                value={grouping}
                onChange={(e) => {
                  captureCamera();
                  setGrouping(e.target.value as GroupMode);
                  setNavigation((n) => n + 1);
                }}
              >
                {(Object.keys(groupModes) as GroupMode[]).map((mode) => (
                  <option
                    key={mode}
                    value={mode}
                    disabled={mode === "conceptual" && !modelDigest}
                  >
                    {groupModes[mode]}
                  </option>
                ))}
              </select>
            </label>
            <div role="group" aria-label="Context breadth">
              {(["Path", "Nearby", "Wider"] as const).map((label, i) => (
                <button
                  key={label}
                  aria-pressed={contextRadius === i}
                  onClick={() => changeDetail(i as 0 | 1 | 2)}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              onClick={() => setRulesOpen(!rulesOpen)}
              aria-expanded={rulesOpen}
            >
              Configure rules
            </button>
            {rulesOpen && (
              <section
                className="rules-editor"
                aria-label="Rules configuration"
              >
                <label>
                  Selected rules model
                  <select
                    aria-label="Selected rules model"
                    value={modelDigest}
                    onChange={(e) => {
                      setModelDigest(e.target.value);
                      if (!e.target.value && grouping === "conceptual")
                        setGrouping("mixed");
                    }}
                  >
                    <option value="">None</option>
                    {boot?.models.map((m) => (
                      <option key={m.digest} value={m.digest}>
                        {m.digest.slice(0, 12)} · {m.world_policy}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Rules YAML
                  <textarea
                    aria-label="Rules YAML"
                    rows={10}
                    value={rulesText}
                    onChange={(e) => setRulesText(e.target.value)}
                  />
                </label>
                <label>
                  Upload rules file
                  <input
                    aria-label="Upload rules file"
                    type="file"
                    accept=".yaml,.yml"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        if (file.size > 262144) {
                          setRulesMessage("Rules file exceeds 256 KiB");
                          return;
                        }
                        setRulesText(await file.text());
                      }
                    }}
                  />
                </label>
                <button
                  disabled={!rulesText.trim()}
                  onClick={async () => {
                    const sid = snapshotId;
                    try {
                      const result = await json<{
                        models: Bootstrap["models"];
                        model_digest: string;
                      }>("/api/workspace/rules", {
                        snapshot_id: sid,
                        text: rulesText,
                        activate: true,
                      });
                      if (snapshotRef.current?.snapshot_id !== sid) return;
                      setBoot((b) => (b ? { ...b, models: result.models } : b));
                      setModelDigest(result.model_digest);
                      setRulesMessage(
                        "Rules validated and activated. Previous versions remain available.",
                      );
                    } catch (e) {
                      setRulesMessage((e as Error).message);
                    }
                  }}
                >
                  Validate and activate rules
                </button>
                <p role="status">{rulesMessage}</p>
              </section>
            )}
            <details>
              <summary>Scope & filters</summary>
              <div className="filter-popover">
                <strong>Dependency scope</strong>
                <fieldset>
                  <legend>Relationship families</legend>
                  <label>
                    <input
                      type="checkbox"
                      checked={filter.families.includes("static")}
                      onChange={(e) =>
                        setFilter((f) => ({
                          ...f,
                          families: [
                            ...f.families.filter(
                              (family) => family !== "static",
                            ),
                            ...(e.target.checked ? ["static" as const] : []),
                          ],
                        }))
                      }
                    />
                    Static
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      aria-label="Runtime overlay"
                      disabled={!chosenCollection?.source_match}
                      checked={filter.families.includes("runtime")}
                      onChange={(e) =>
                        setFilter((f) =>
                          runtimeFilter(
                            f,
                            e.target.checked ? chosenCollection : undefined,
                          ),
                        )
                      }
                    />
                    Runtime observations
                  </label>
                </fieldset>
                <fieldset>
                  <legend>Relationship subtypes</legend>
                  {["calls", "imports", "imports_from", "inherits"].map(
                    (type) => (
                      <label key={type}>
                        <input
                          type="checkbox"
                          checked={
                            !filter.subtypes.length ||
                            filter.subtypes.includes(type)
                          }
                          onChange={(e) =>
                            setFilter((f) => {
                              const all = [
                                "calls",
                                "imports",
                                "imports_from",
                                "inherits",
                              ];
                              const selected = f.subtypes.length
                                ? f.subtypes
                                : all;
                              const next = e.target.checked
                                ? [...selected.filter((x) => x !== type), type]
                                : selected.filter((x) => x !== type);
                              return {
                                ...f,
                                subtypes: next.length ? next : ["__none__"],
                              };
                            })
                          }
                        />
                        {type}
                      </label>
                    ),
                  )}
                </fieldset>
                <button
                  onClick={() => changeDetail(contextRadius === 0 ? 1 : 0)}
                >
                  {contextRadius === 0
                    ? "Reveal nearby detail"
                    : "Collapse nearby detail"}
                </button>
                <button
                  onClick={() =>
                    setRevealed([
                      snapshot?.root.id ?? focus,
                      snapshot?.repositories[0]?.id ?? focus,
                      focus,
                    ])
                  }
                >
                  Collapse to focused scope
                </button>
                <button onClick={() => setFilter({ ...defaultFilter })}>
                  Reset filters
                </button>
                {(
                  [
                    "include_tests",
                    "include_generated",
                    "include_vendor",
                    "include_external",
                  ] as const
                ).map((k) => (
                  <label key={k}>
                    <input
                      type="checkbox"
                      checked={filter[k]}
                      onChange={() => toggleFlag(k)}
                    />
                    {k.replace("include_", "").replaceAll("_", " ")}
                  </label>
                ))}
                <label>
                  <input
                    type="checkbox"
                    checked={filter.resolution_statuses.includes("candidate")}
                    onChange={(e) =>
                      setFilter((f) => ({
                        ...f,
                        resolution_statuses: [
                          ...(e.target.checked
                            ? (["exact", "candidate", "unresolved"] as const)
                            : (["exact"] as const)),
                          ...(f.families.includes("runtime")
                            ? ["observed" as const]
                            : []),
                        ],
                      }))
                    }
                  />
                  Include uncertain relationships
                </label>
                <p>
                  Only exact static relationships are shown by default.
                  Uncertain targets remain labelled.
                </p>
                {!snapshot?.runtime_collections?.length ? (
                  <button
                    disabled
                    title="No measured runtime collection is attached to this snapshot"
                  >
                    Runtime overlay unavailable
                  </button>
                ) : (
                  <section aria-label="Runtime collection">
                    <label>
                      Collection window
                      <select
                        aria-label="Runtime collection window"
                        value={chosenCollection?.collection_id ?? ""}
                        onChange={(e) => {
                          const c = snapshot.runtime_collections?.find(
                            (c) => c.collection_id === e.target.value,
                          );
                          setCollectionChoice(e.target.value);
                          setCollectionReport(undefined);
                          if (filter.families.includes("runtime"))
                            setFilter((f) => runtimeFilter(f, c));
                        }}
                      >
                        {snapshot.runtime_collections?.map((c) => (
                          <option key={c.collection_id} value={c.collection_id}>
                            {c.environment} · {c.window.start} → {c.window.end}
                          </option>
                        ))}
                      </select>
                    </label>
                    {chosenCollection && (
                      <>
                        <p>
                          {chosenCollection.mapped_call_count} observed calls ·{" "}
                          {chosenCollection.quarantined_records} unmapped
                          records ·{" "}
                          {chosenCollection.coverage.complete
                            ? "complete within declared capture scope"
                            : "incomplete capture"}
                        </p>
                        <p>
                          Positive observations only. Not seeing a call does not
                          prove absence.
                        </p>
                        <button
                          onClick={async () => {
                            const key = collectionScope;
                            try {
                              const report = await json<unknown>(
                                "/api/v1/handles/" +
                                  encodeURIComponent(
                                    chosenCollection.report_handle,
                                  ),
                              );
                              if (collectionScopeRef.current === key)
                                setCollectionReport(report);
                            } catch (e) {
                              setError((e as Error).message);
                            }
                          }}
                        >
                          Inspect collection coverage
                        </button>
                        {collectionReport !== undefined && (
                          <pre className="collection-report" tabIndex={0}>
                            {JSON.stringify(collectionReport, null, 2)}
                          </pre>
                        )}
                      </>
                    )}
                  </section>
                )}
              </div>
            </details>
            <span>
              {filter.include_tests ? "All code" : "Production"} ·{" "}
              {filter.families.includes("static")
                ? filter.resolution_statuses.some(
                    (s) => s === "candidate" || s === "unresolved",
                  )
                  ? "uncertainty included"
                  : "exact dependencies"
                : ""}
              {filter.families.includes("runtime") ? " · observed calls" : ""}
            </span>
            <button
              className="pin-action"
              disabled={!current?.entity_id}
              aria-pressed={pins.includes(selected)}
              onClick={() =>
                setPins((old) =>
                  old.includes(selected)
                    ? old.filter((x) => x !== selected)
                    : [...old, selected],
                )
              }
            >
              {pins.includes(selected) ? "Unpin" : "Pin selection"}
            </button>
            <span className="filter-count">
              {composition?.data.spheres.length ??
                frame?.data.spheres.length ??
                0}{" "}
              groups ·{" "}
              {composition?.data.curves.length ??
                frame?.data.curves.length ??
                0}{" "}
              curves
            </span>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              {error}
              <button
                onClick={() =>
                  boot
                    ? setNavigation((n) => n + 1)
                    : setBootAttempt((n) => n + 1)
                }
              >
                Retry view
              </button>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                ×
              </button>
            </div>
          )}
          <div
            className={`view-content view-${view}`}
            role={workspace ? "region" : undefined}
            aria-label={workspace ? "Shared detailed scene" : undefined}
            aria-busy={
              loading ||
              Boolean(composition?.loading) ||
              Boolean(snapshot && !frameCurrent && !viewFailed)
            }
            inert={
              snapshot && (!frameCurrent || composition?.loading)
                ? true
                : undefined
            }
          >
            {boot && !snapshot ? (
              <div className="empty-state">
                <h2>No repository snapshots</h2>
                <p>
                  Create a snapshot with the Geo Grapher CLI, then refresh.
                  Python analysis and JavaScript/TypeScript syntax extraction
                  are supported.
                </p>
                <button onClick={() => setBootAttempt((n) => n + 1)}>
                  Refresh snapshots
                </button>
              </div>
            ) : view === "spatial" ? (
              <>
                <Scene
                  ref={scene}
                  frame={composition?.data ?? frame?.data}
                  declaredLinks={composition?.declaredLinks}
                  focusId={
                    composition
                      ? ""
                      : grouping === "mixed"
                        ? (frame?.focus ?? focus)
                        : ""
                  }
                  navigationKey={
                    composition
                      ? `${frame?.navigation}:${workspace?.selected.join()}:${composition.frames
                          .filter((f) => f.frame)
                          .map((f) => f.graph_id)
                          .join()}`
                      : (frame?.navigation ?? "")
                  }
                  selectedId={
                    composition && workspace && snapshot
                      ? renderId(
                          workspace.active,
                          snapshot.snapshot_id,
                          "node",
                          selected,
                        )
                      : selected
                  }
                  selectedEdge={
                    composition && workspace && snapshot
                      ? renderId(
                          workspace.active,
                          snapshot.snapshot_id,
                          "relationship",
                          selectedEdge,
                        )
                      : selectedEdge
                  }
                  highlightedEdges={
                    pathProjection?.steps
                      .flatMap((s) =>
                        s.projections
                          .filter((p) => p.source_rep_id !== p.target_rep_id)
                          .map((p) => p.projection_id),
                      )
                      .map((id) =>
                        composition && workspace && snapshot
                          ? renderId(
                              workspace.active,
                              snapshot.snapshot_id,
                              "relationship",
                              id,
                            )
                          : id,
                      ) ?? []
                  }
                  violations={violations.map((id) =>
                    composition && workspace && snapshot
                      ? renderId(
                          workspace.active,
                          snapshot.snapshot_id,
                          "relationship",
                          id,
                        )
                      : id,
                  )}
                  beta={beta}
                  lensEnabled={lens}
                  theme={theme}
                  initialCamera={initialCamera}
                  onPick={pick}
                  onEnter={enter}
                  onFailure={(reason) => {
                    setStatus(reason);
                    changeView("list");
                  }}
                />
                <div className="legend">
                  <span>○ enclosure / summary</span>
                  <span>→ direction: darker source to lighter target</span>
                  <span>·· candidate / unresolved · –– expected only</span>
                  <span>
                    Solid: calls · long dash: imports · paired dash: inherits
                  </span>
                  <span>
                    Grey: static · sage: observed · amber: rule violation
                  </span>
                  <span>
                    Size: capped content / membership and packing space.
                    Position is not similarity.
                  </span>
                </div>
                <div
                  className="camera-tools"
                  role="group"
                  aria-label="Camera controls"
                >
                  {contextRadius === 0 && !composition && (
                    <button onClick={() => changeDetail(1)}>
                      Reveal nearby detail
                    </button>
                  )}
                  <button
                    onClick={() => scene.current?.fit()}
                    aria-label={
                      composition
                        ? "Fit displayed graphs"
                        : grouping === "mixed"
                          ? "Fit focused container"
                          : "Fit displayed groups"
                    }
                  >
                    Fit
                  </button>
                  <button
                    onClick={() => scene.current?.zoom(0.8)}
                    aria-label="Zoom in"
                  >
                    +
                  </button>
                  <button
                    onClick={() => scene.current?.zoom(1.25)}
                    aria-label="Zoom out"
                  >
                    −
                  </button>
                </div>
              </>
            ) : frame ? (
              view === "matrix" ? (
                <Matrix
                  frame={
                    composition
                      ? {
                          ...composition.data,
                          partition_digest: composition.partition_digest,
                        }
                      : frame.data
                  }
                  violations={violations}
                  onSelect={(id) => pick([id])}
                  onRelationship={(ids) => pick(ids, undefined, true)}
                />
              ) : (
                <EntityList
                  frame={
                    composition
                      ? {
                          ...composition.data,
                          partition_digest: composition.partition_digest,
                        }
                      : frame.data
                  }
                  selected={
                    composition && workspace && snapshot
                      ? renderId(
                          workspace.active,
                          snapshot.snapshot_id,
                          "node",
                          selected,
                        )
                      : selected
                  }
                  onSelect={(id) => pick([id])}
                  onEnter={enter}
                />
              )
            ) : (
              <div className="empty-state">
                <h2>
                  {loading
                    ? "Building your architecture view…"
                    : "No architecture view"}
                </h2>
                <p>
                  {loading
                    ? "Resolving containment, rollups and evidence."
                    : "Select a published snapshot to explore its source structure."}
                </p>
              </div>
            )}
            {(loading || (snapshot && !frameCurrent)) && (
              <div className="scene-loading" role="status">
                {viewFailed && !loading
                  ? "Previous architecture · refresh failed"
                  : frame && !frameCurrent
                    ? `Previous view · loading ${focusNode ? shortName(focusNode) : "new scope"}…`
                    : "Loading architecture…"}
              </div>
            )}
          </div>
          {(view === "spatial" || cursor.current) && (
            <div className="scene-controls">
              {view === "spatial" && (
                <>
                  <label htmlFor="bundling">
                    Bundling <output>{beta.toFixed(2)}</output>
                  </label>
                  <input
                    id="bundling"
                    type="range"
                    min="0"
                    max="1"
                    step=".01"
                    value={beta}
                    onChange={(e) => setBeta(Number(e.target.value))}
                  />
                  <label>
                    <input
                      type="checkbox"
                      checked={lens}
                      onChange={(e) => setLens(e.target.checked)}
                    />
                    Local EdgeLens
                  </label>
                </>
              )}
              {cursor.current && (
                <button disabled={loading} onClick={() => void more()}>
                  Load more detail
                </button>
              )}
            </div>
          )}
          {pathProjection && (
            <section aria-label="Highlighted witness path">
              <p>
                {pathProjection.steps.length} original directed steps ·{" "}
                {
                  pathProjection.steps.filter((s) =>
                    s.projections.some(
                      (p) => p.source_rep_id === p.target_rep_id,
                    ),
                  ).length
                }{" "}
                internal collapsed steps ·{" "}
                {
                  pathProjection.steps.filter((s) => !s.projections.length)
                    .length
                }{" "}
                steps outside this filter/view
              </p>
              <ol>
                {pathProjection.steps.map((s) => (
                  <li key={s.relationship_id}>
                    {nodes[s.source]?.qualified_name ?? s.source} →{" "}
                    {nodes[s.target]?.qualified_name ?? s.target}
                  </li>
                ))}
              </ol>
              <button
                onClick={() => {
                  setPathIds([]);
                  setPathProjection(undefined);
                }}
              >
                Clear path highlight
              </button>
            </section>
          )}
          <div className="scope-note">
            {composition?.loading && (
              <span role="status">Loading selected graphs…</span>
            )}
            {composition?.error && (
              <span role="alert">{composition.error}</span>
            )}
            {!composition?.loading &&
              composition?.frames
                .filter((f) => f.error)
                .map((f) => (
                  <span key={f.graph_id} role="alert">
                    {f.label}: {f.error?.message}
                  </span>
                ))}
            {viewFailed && !frameCurrent && !error && (
              <button onClick={() => setNavigation((n) => n + 1)}>
                Retry requested view
              </button>
            )}
            <button
              className="text-button"
              aria-expanded={coverageOpen}
              onClick={() => setCoverageOpen((o) => !o)}
            >
              Coverage
            </button>
            {coverageOpen && (
              <div className="coverage-popover">
                <h2>Extraction coverage</h2>
                <p>
                  Static facts are conservative; unresolved targets are retained
                  rather than guessed.
                </p>
                <p>
                  {snapshot?.statuses.exact ?? 0} exact ·{" "}
                  {snapshot?.statuses.candidate ?? 0} candidate ·{" "}
                  {snapshot?.statuses.unresolved ?? 0} unresolved relationships
                </p>
                {frame?.data.coverage.limitations.map((x, i) => (
                  <p key={i}>{x}</p>
                ))}
                <p>
                  {frame?.data.coverage.parse_failure_count ?? 0} parse failures
                  in this snapshot.
                </p>
                <ul>
                  {coverageFailures.map((f, i) => (
                    <li key={i}>
                      {f.repo_id} / {f.rel_path} · {f.language}: {f.message}
                    </li>
                  ))}
                </ul>
                <p>
                  {pins.length} pinned entities. Expanded ancestors remain as
                  orientation shells, including when excluded by the dependency
                  filter.
                </p>
                <label>
                  Hierarchy width
                  <input
                    aria-label="Hierarchy panel width"
                    type="range"
                    min="190"
                    max="340"
                    value={panelSizes[0]}
                    onChange={(e) =>
                      setPanelSizes([Number(e.target.value), panelSizes[1]])
                    }
                  />
                </label>
                <label>
                  Inspector width
                  <input
                    aria-label="Inspector panel width"
                    type="range"
                    min="290"
                    max="440"
                    value={panelSizes[1]}
                    onChange={(e) =>
                      setPanelSizes([panelSizes[0], Number(e.target.value)])
                    }
                  />
                </label>
                <button onClick={() => setCoverageOpen(false)}>
                  Close coverage
                </button>
              </div>
            )}
            {frame && (
              <>
                <span>
                  {frame.data.scene_completeness.omitted_spheres.toLocaleString()}{" "}
                  groups and{" "}
                  {frame.data.scene_completeness.omitted_curves.toLocaleString()}{" "}
                  curves omitted by scope or budget.
                </span>{" "}
                <span>
                  Internal relationships remain in the inspector and matrix.
                </span>
              </>
            )}
            {snapshot && (
              <span>
                {snapshot.counts.entities.toLocaleString()} source entities ·
                revision {snapshot.revisions[0]?.revision.slice(0, 12)}
              </span>
            )}
          </div>
        </main>
        <aside
          className={`inspector-panel side-panel ${drawer === "inspector" ? "drawer-open" : ""}`}
          aria-label="Entity details"
        >
          <button className="drawer-dismiss" onClick={() => setDrawer(null)}>
            Close inspector
          </button>
          {snapshot && (
            <Inspector
              snapshot={snapshot}
              node={current}
              frame={inspectionFrame ?? frame?.data}
              edge={edge}
              nodes={{
                ...nodes,
                ...Object.fromEntries(
                  (frame?.data.nodes ?? []).map((n) => [n.id, n]),
                ),
              }}
              filter={filter}
              models={boot?.models ?? []}
              violations={violations}
              modelDigest={modelDigest}
              pins={pins}
              onPath={highlightPath}
              onNodes={addNodes}
              onSelect={(id) => void select(id)}
              onEnter={enter}
              onEdge={(id) => pick([id], undefined, true)}
              onStatus={setStatus}
              scopeReady={Boolean(inspectionFrame) || frameCurrent}
              pinned={pins.includes(selected)}
              onTogglePin={() =>
                setPins((old) =>
                  old.includes(selected)
                    ? old.filter((id) => id !== selected)
                    : [...old, selected],
                )
              }
            />
          )}
        </aside>
      </div>
      <footer className="status-bar">
        <span
          className={`status-dot ${loading ? "busy" : ""}`}
          aria-hidden="true"
        />
        <span role="status" aria-live="polite">
          {snapshot && !frameCurrent
            ? viewFailed
              ? "Previous architecture preserved. Retry the requested scope or return to another container."
              : "Loading the requested architecture scope…"
            : status}
        </span>
        <span className="status-end">
          Source-backed · local ·{" "}
          {filter.families.includes("runtime")
            ? `observations: ${chosenCollection?.environment ?? "unknown collection"}`
            : "static view"}
        </span>
      </footer>
      {choices && (
        <dialog
          ref={picker}
          onCancel={() => setChoices(null)}
          className="pick-menu"
          aria-label={choices.edge ? "Choose relationship" : "Choose entity"}
        >
          <h2>
            {choices.edge
              ? "Overlapping relationships"
              : "Overlapping entities"}
          </h2>
          <p>Select the intended item.</p>
          {choices.ids.map((id) => (
            <button
              key={id}
              onClick={() => {
                pick([id], undefined, choices.edge);
                setChoices(null);
              }}
            >
              {choices.edge
                ? `${(composition?.data ?? inspectionFrame ?? frame?.data)?.relationships.find((r) => r.id === id)?.family} · ${(composition?.data ?? inspectionFrame ?? frame?.data)?.relationships.find((r) => r.id === id)?.subtype} · ${id.slice(-8)}`
                : (composition?.data.nodes.find((n) => n.id === id)
                    ?.qualified_name ??
                  (nodes[id] ? shortName(nodes[id]) : id))}
            </button>
          ))}
          <button autoFocus onClick={() => setChoices(null)}>
            Cancel
          </button>
        </dialog>
      )}
      <dialog
        ref={dialog}
        aria-labelledby="save-view-heading"
        onCancel={() => setSaveOpen(false)}
        onClose={() => setSaveOpen(false)}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <h2 id="save-view-heading">Save this workspace</h2>
          <p>
            The view stores its snapshot, scope, camera and visual settings in
            this browser.
          </p>
          <label htmlFor="view-name">View name</label>
          <input
            id="view-name"
            autoFocus
            value={saveName}
            maxLength={80}
            onChange={(e) => setSaveName(e.target.value)}
            required
          />
          <div className="dialog-actions">
            <button type="button" onClick={() => setSaveOpen(false)}>
              Cancel
            </button>
            <button type="submit">Save</button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
