import { useEffect, useMemo, useState } from "react";
import type {
  Filter,
  ViewportFrameData,
} from "../../contracts/geographer.wire";
import { json, type GroupMode } from "./api";
import {
  composeScene,
  renderId,
  type Composition,
  type GraphFrame,
} from "./composition";
import type { WorkspaceControls } from "./workspaceTypes";

export function useGraphComposition(
  workspace: WorkspaceControls | undefined,
  activeData: ViewportFrameData | undefined,
  snapshot: string | undefined,
  filter: Filter,
  mode: GroupMode,
  radius: 0 | 1 | 2,
  model: string,
) {
  const [remote, setRemote] = useState<Composition>({
      version: "graph-composition-v1",
      composition: "display_only",
      frames: [],
    }),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  const enabled = Boolean(
    workspace &&
    (workspace.selected.length !== 1 ||
      workspace.selected[0] !== workspace.active),
  );
  const [bridges, setBridges] = useState<
    { bridge_id: string; source_graph: string; target_graph: string }[]
  >([]);
  useEffect(() => {
    const abort = new AbortController();
    if (!workspace?.selected.length) {
      setBridges([]);
      return;
    }
    json<{ bridges: typeof bridges }>(
      "/api/graphs/bridges",
      { graph_ids: workspace.selected },
      abort.signal,
    )
      .then((r) => {
        if (!abort.signal.aborted) setBridges(r.bridges);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => abort.abort();
  }, [workspace?.selected.join()]);
  const requests =
    workspace?.selected
      .filter((id) => id !== workspace.active)
      .map((id) => {
        const graph = workspace.graphs.find((g) => g.graph_id === id)!;
        const remembered = workspace.focus[id];
        const grouping =
          mode === "mixed"
            ? { mode: "mixed", revealed_ids: [] }
            : mode === "atomic"
              ? { mode: "atomic" }
              : mode === "conceptual"
                ? { mode: "conceptual", model_digest: model }
                : { mode: "kind", kind: mode };
        return {
          graph_id: id,
          snapshot_id: remembered?.snapshot ?? graph.snapshot_id,
          focus_id: remembered?.id,
          context_radius: radius,
          filter: { ...filter, repo_ids: [] },
          grouping,
          model_digest: model || null,
        };
      }) ?? [];
  const requestKey = JSON.stringify(requests);
  useEffect(() => {
    const abort = new AbortController();
    if (!enabled || !requests.length) {
      setRemote({
        version: "graph-composition-v1",
        composition: "display_only",
        frames: [],
      });
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    json<Composition>("/api/graphs/frame", { graphs: requests }, abort.signal)
      .then((data) => {
        if (!abort.signal.aborted) setRemote(data);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [enabled, requestKey]);
  return useMemo(() => {
    if (!enabled || !workspace) return undefined;
    const frames: GraphFrame[] = [];
    // Same axial rings as the backend. Display order comes from the checkbox list.
    const slots: [number, number][] = [[0, 0]];
    for (let ring = 1; slots.length < workspace.selected.length; ring++) {
      let q = ring,
        r = 0;
      for (const [dq, dr] of [
        [0, -1],
        [-1, 0],
        [-1, 1],
        [0, 1],
        [1, 0],
        [1, -1],
      ])
        for (let i = 0; i < ring; i++) {
          slots.push([q, r]);
          q += dq;
          r += dr;
        }
    }
    for (const [index, id] of workspace.selected.entries()) {
      const graph = workspace.graphs.find((g) => g.graph_id === id)!;
      let frame: GraphFrame | undefined;
      if (id === workspace.active && activeData && snapshot) {
        const root = activeData.nodes.find((n) => n.kind === "workspace");
        if (root)
          frame = {
            graph_id: id,
            label: graph.label,
            snapshot_id: snapshot,
            root_id: root.id,
            frame: activeData,
            repository_labels: Object.fromEntries(
              activeData.nodes
                .filter((n) => n.kind === "repository")
                .map((n) => [
                  n.id,
                  (
                    workspace.graphs.find((g) => g.graph_id === n.repo_id) ??
                    workspace.graphs.find(
                      (g) =>
                        g.repo_ids?.length === 1 && g.repo_ids[0] === n.repo_id,
                    )
                  )?.label ?? n.qualified_name,
                ]),
            ),
          };
      } else frame = remote.frames.find((f) => f.graph_id === id);
      if (!frame) {
        frames.push({
          graph_id: id,
          label: graph.label,
          error: {
            code: "FRAME_UNAVAILABLE",
            message: loading ? "Loading graph…" : "Graph detail unavailable",
          },
        });
        continue;
      }
      if (frame.frame && frame.root_id) {
        const root = frame.frame.spheres.find(
          (s) => s.node_id === frame!.root_id,
        );
        if (!root) continue;
        const [q, r] = slots[index],
          world: [number, number, number] = [
            7 * (q + r / 2),
            0,
            ((7 * Math.sqrt(3)) / 2) * r,
          ],
          scale = 2.5 / root.radius;
        frame = {
          ...frame,
          transform: {
            scale,
            translation: world.map((v, i) => v - scale * root.center[i]) as [
              number,
              number,
              number,
            ],
          },
          world_center: world,
        };
      }
      frames.push(frame);
    }
    const result = composeScene({
      version: "graph-composition-v1",
      composition: "display_only",
      frames,
    });
    for (const node of result.data.nodes) {
      const origin = result.origins.get(node.id)!;
      const label = workspace.graphs.find(
        (g) => g.graph_id === origin.graph_id,
      )?.label;
      if (node.kind !== "repository" || node.qualified_name !== label)
        node.qualified_name = `${label} · ${node.qualified_name}`;
    }
    const declaredLinks = (workspace.showBridges ? bridges : [])
      .slice(0, 100)
      .flatMap((b) => {
        const source = frames.find((f) => f.graph_id === b.source_graph),
          target = frames.find((f) => f.graph_id === b.target_graph);
        const anchor = (f: GraphFrame) => {
          const roots = f.frame?.nodes.filter((n) => n.kind === "repository");
          const id = roots?.length === 1 ? roots[0].id : f.root_id;
          return id && f.snapshot_id
            ? renderId(f.graph_id, f.snapshot_id, "node", id)
            : undefined;
        };
        return source?.world_center && target?.world_center
          ? [
              {
                id: b.bridge_id,
                source: source.world_center,
                target: target.world_center,
                sourceNodeId: anchor(source),
                targetNodeId: anchor(target),
              },
            ]
          : [];
      });
    return {
      ...result,
      frames,
      loading,
      error,
      declaredLinks,
      partition_digest: JSON.stringify(
        frames.map((f) => [
          f.graph_id,
          f.snapshot_id,
          f.frame?.partition_digest,
        ]),
      ),
    };
  }, [
    enabled,
    workspace?.selected.join(),
    workspace?.active,
    workspace?.showBridges,
    activeData,
    snapshot,
    remote,
    loading,
    error,
    bridges,
  ]);
}
