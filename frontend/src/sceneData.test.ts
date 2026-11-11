import assert from "node:assert/strict";
import { test } from "node:test";
import { composeScene, renderId } from "./composition.ts";
import { editedScene } from "./layoutEditing.ts";

const link = {
  link_id: "L1",
  fragment_rep: "F",
  entity_rep: "E",
  role: "documents",
  incidence_count: 2,
  control_points: [
    [0, 0, 0],
    [1, 0, 0],
    [2, 0, 0],
  ],
  degree: 2,
  knots: [0, 0, 0, 1, 1, 1],
  relationship_family: "doc_describes",
  runtime_status: "exact",
};
const node = (id: string) => ({
  id,
  kind: "file",
  parent_id: null,
  entity_id: null,
  qualified_name: id,
});

test("composeScene remaps documentary ids and transforms control points", () => {
  const frame = {
    nodes: [node("F"), node("E")],
    relationships: [],
    spheres: [],
    curves: [],
    documentary_links: [link],
  };
  const result = composeScene({
    version: "graph-composition-v1",
    composition: "display_only",
    frames: [
      {
        graph_id: "g",
        label: "G",
        snapshot_id: "s",
        transform: { scale: 2, translation: [10, 0, 0] },
        frame,
      },
    ] as never,
  });
  const out = result.data.documentary_links!;
  assert.equal(out.length, 1);
  assert.equal(out[0].link_id, renderId("g", "s", "relationship", "L1"));
  assert.equal(out[0].fragment_rep, renderId("g", "s", "node", "F"));
  assert.equal(out[0].entity_rep, renderId("g", "s", "node", "E"));
  assert.deepEqual(out[0].control_points, [
    [10, 0, 0],
    [12, 0, 0],
    [14, 0, 0],
  ]);
  assert.equal(out[0].role, "documents");
  assert.equal(result.origins.get(out[0].link_id)!.local_id, "L1");
});

test("composeScene omits documentary_links when frames have none", () => {
  const result = composeScene({
    version: "v",
    composition: "display_only",
    frames: [
      {
        graph_id: "g",
        label: "G",
        snapshot_id: "s",
        transform: { scale: 1, translation: [0, 0, 0] },
        frame: { nodes: [], relationships: [], spheres: [], curves: [] },
      },
    ] as never,
  });
  assert.equal(result.data.documentary_links, undefined);
});

test("editedScene moves documentary control points with endpoint transforms", () => {
  const data = {
    nodes: [node("F"), node("E")],
    relationships: [],
    spheres: [],
    curves: [],
    documentary_links: [link],
  } as never;
  // No edits: same object, links untouched.
  assert.equal(editedScene(data, new Map()), data);
  const edited = editedScene(
    data,
    new Map([
      ["E", { scale: 1, offset: [0, 10, 0] as [number, number, number] }],
    ]),
  );
  const pts = edited.documentary_links![0].control_points;
  assert.deepEqual(pts[0], [0, 0, 0]); // at the fragment end: unmoved
  assert.deepEqual(pts[1], [1, 5, 0]); // midway: half the entity offset
  assert.deepEqual(pts[2], [2, 10, 0]); // at the entity end: fully moved
  assert.equal(edited.documentary_links![0].link_id, "L1");
});
