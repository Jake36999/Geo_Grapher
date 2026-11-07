import type { Vec3, ViewportFrameData } from "../../contracts/geographer.wire";
import type { SceneData } from "./Scene";

export interface OriginAddress {
  graph_id: string;
  snapshot_id: string;
  local_id: string;
  kind: "node" | "relationship";
}
export interface GraphFrame {
  graph_id: string;
  label: string;
  snapshot_id?: string;
  root_id?: string;
  focus_id?: string;
  repository_labels?: Record<string, string>;
  world_center?: Vec3;
  transform?: { scale: number; translation: Vec3 };
  frame?: ViewportFrameData;
  error?: { code: string; message: string };
}
export interface Composition {
  version: string;
  composition: "display_only";
  frames: GraphFrame[];
}

export function renderId(
  graph: string,
  snapshot: string,
  kind: string,
  id: string,
) {
  return JSON.stringify([graph, snapshot, kind, id]);
}

// This is render data, never an analysis graph or a valid query envelope.
// Originals and scope addresses stay outside the flattened GPU collections.
export function composeScene(input: Composition) {
  const data: SceneData = {
    nodes: [],
    relationships: [],
    spheres: [],
    curves: [],
  };
  const origins = new Map<string, OriginAddress>();
  for (const item of input.frames) {
    if (!item.frame || !item.transform || !item.snapshot_id) continue;
    const { scale, translation } = item.transform;
    const point = (p: Vec3): Vec3 =>
      p.map((v, i) => v * scale + translation[i]) as Vec3;
    const id = (local: string, kind: "node" | "relationship" = "node") => {
      const key = renderId(item.graph_id, item.snapshot_id!, kind, local);
      origins.set(key, {
        graph_id: item.graph_id,
        snapshot_id: item.snapshot_id!,
        local_id: local,
        kind,
      });
      return key;
    };
    const repositories = item.frame.nodes.filter(
      (n) => n.kind === "repository",
    );
    for (const node of item.frame.nodes)
      data.nodes.push({
        ...node,
        id: id(node.id),
        entity_id: node.entity_id ? id(node.entity_id) : null,
        parent_id: node.parent_id ? id(node.parent_id) : null,
        // The virtual workspace becomes a display enclosure for this graph.
        kind:
          node.id === item.root_id && repositories.length > 1
            ? "repository"
            : node.kind,
        qualified_name:
          node.id === item.root_id
            ? item.label
            : (item.repository_labels?.[node.id] ?? node.qualified_name),
      });
    for (const rel of item.frame.relationships)
      data.relationships.push({
        ...rel,
        id: id(rel.id, "relationship"),
        source: id(rel.source),
        target: id(rel.target),
      });
    for (const sphere of item.frame.spheres)
      data.spheres.push({
        ...sphere,
        node_id: id(sphere.node_id),
        center: point(sphere.center),
        radius: sphere.radius * scale,
      });
    for (const curve of item.frame.curves)
      data.curves.push({
        ...curve,
        relationship_id: id(curve.relationship_id, "relationship"),
        canonical_source: id(curve.canonical_source),
        canonical_target: id(curve.canonical_target),
        control_points: curve.control_points.map(point),
        lane_spacing: curve.lane_spacing * scale,
      });
  }
  return { data, origins };
}
