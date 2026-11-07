/** Display-only affine edits. Source records, ownership and edges are untouched. */
import type { Vec3 } from "../../contracts/geographer.wire";
import type { SceneData } from "./Scene";
export interface Affine {
  scale: number;
  offset: Vec3;
}
const identity: Affine = { scale: 1, offset: [0, 0, 0] };
const point = (p: Vec3, t: Affine): Vec3 =>
  p.map((v, i) => v * t.scale + t.offset[i]) as Vec3;
function resolver(data: SceneData, edits: Map<string, Affine>) {
  const parents = new Map(data.nodes.map((n) => [n.id, n.parent_id]));
  return (id: string): Affine => {
    const seen = new Set<string>();
    let current: string | null | undefined = id;
    while (current && !seen.has(current)) {
      const value = edits.get(current);
      if (value) return value;
      seen.add(current);
      current = parents.get(current);
    }
    return identity;
  };
}

export function selectionRoots(data: SceneData, ids: string[]) {
  const parents = new Map(data.nodes.map((n) => [n.id, n.parent_id]));
  const selected = new Set(ids.filter((id) => parents.has(id)));
  return [...selected].filter((id) => {
    const visited = new Set<string>();
    let p = parents.get(id);
    while (p && !visited.has(p)) {
      if (selected.has(p)) return false;
      visited.add(p);
      p = parents.get(p);
    }
    return true;
  });
}
export function descendants(data: SceneData, ids: string[]) {
  const children = new Map<string, string[]>();
  for (const node of data.nodes)
    if (node.parent_id)
      children.set(node.parent_id, [
        ...(children.get(node.parent_id) ?? []),
        node.id,
      ]);
  const found = new Set<string>(),
    stack = [...ids];
  while (stack.length) {
    const id = stack.pop()!;
    if (found.has(id)) continue;
    found.add(id);
    stack.push(...(children.get(id) ?? []));
  }
  return found;
}
export function editSelection(
  data: SceneData,
  edits: Map<string, Affine>,
  ids: string[],
  pivot: Vec3,
  scale: number,
  delta: Vec3,
) {
  const selected = descendants(data, selectionRoots(data, ids));
  if (!selected.size) return;
  if (![...pivot, ...delta, scale].every(Number.isFinite) || scale <= 0)
    throw new Error("Invalid display transform");
  const transform = resolver(data, edits);
  const previous = new Map([...selected].map((id) => [id, transform(id)]));
  const transforms = [...previous.values()];
  // Clamp the whole group uniformly, preserving relative positions and sizes.
  const lower = Math.max(...transforms.map((t) => 0.1 / t.scale), 0.01);
  const upper = Math.min(...transforms.map((t) => 10 / t.scale), 100);
  scale = Math.max(lower, Math.min(upper, scale));
  for (const id of selected) {
    const old = previous.get(id)!;
    edits.set(id, {
      scale: old.scale * scale,
      offset: old.offset.map(
        (v, i) => v * scale + pivot[i] * (1 - scale) + delta[i],
      ) as Vec3,
    });
  }
}

export function editedScene(
  data: SceneData,
  edits: Map<string, Affine>,
): SceneData {
  if (!edits.size) return data;
  const transform = resolver(data, edits);
  const spheres = data.spheres.map((s) => ({
    ...s,
    center: point(s.center, transform(s.node_id)),
    radius: s.radius * transform(s.node_id).scale,
  }));
  const curves = data.curves.map((c) => {
    const a = transform(c.canonical_source),
      b = transform(c.canonical_target);
    const same =
      a.scale === b.scale && a.offset.every((v, i) => v === b.offset[i]);
    if (same)
      return {
        ...c,
        control_points: c.control_points.map((p) => point(p, a)),
        lane_spacing: c.lane_spacing * a.scale,
      };
    const rawA = c.control_points[0],
      rawB = c.control_points.at(-1)!;
    const newA = point(rawA, a),
      newB = point(rawB, b),
      scale = (a.scale + b.scale) / 2;
    const control_points = c.control_points.map((p, i) => {
      const t = i / (c.control_points.length - 1);
      return p.map(
        (v, j) =>
          newA[j] * (1 - t) +
          newB[j] * t +
          scale * (v - rawA[j] * (1 - t) - rawB[j] * t),
      ) as Vec3;
    });
    const direction = newB.map((v, i) => v - newA[i]);
    const length = Math.hypot(...direction);
    if (length < 1e-10)
      return { ...c, control_points, lane_spacing: c.lane_spacing * scale };
    const tangent = direction.map((v) => v / length),
      axis = [0, 1, 2].sort(
        (i, j) => Math.abs(tangent[i]) - Math.abs(tangent[j]),
      )[0];
    const v = [0, 0, 0];
    v[axis] = 1;
    const cross = (x: number[], y: number[]): Vec3 => [
      x[1] * y[2] - x[2] * y[1],
      x[2] * y[0] - x[0] * y[2],
      x[0] * y[1] - x[1] * y[0],
    ];
    const raw = cross(tangent, v),
      norm = Math.hypot(...raw);
    const normal = raw.map((v) => v / norm) as Vec3,
      binormal = cross(tangent, normal);
    return {
      ...c,
      control_points,
      normal,
      binormal,
      lane_spacing: c.lane_spacing * scale,
    };
  });
  return { ...data, spheres, curves };
}
