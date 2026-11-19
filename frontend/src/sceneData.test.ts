import assert from "node:assert/strict";
import { test } from "node:test";
import { composeScene, renderId } from "./composition.ts";
import { editedScene } from "./layoutEditing.ts";
import { canonicalActor } from "./actorDecode.ts";

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

test("canonicalActor decodes documentary link endpoints", () => {
  
  const decoded = canonicalActor({
    revisions: [],
    data: {
      ids: { n2: "frag-id", n5: "ent-id" },
      view_id: null,
      nodes: [],
      documentary_links: [{ link_id: "L", fragment_rep: "n2", entity_rep: "n5" }],
    } as any,
  });
  const l = (decoded.data as any).documentary_links[0];
  assert.equal(l.fragment_rep, "frag-id");
  assert.equal(l.entity_rep, "ent-id");
});

test("composeScene marks only a graph's own enclosures with its accent", () => {
  const n = (id: string, kind: string, parent: string | null) => ({ ...node(id), kind, parent_id: parent });
  const frame = (nodes: ReturnType<typeof n>[]) => ({ nodes, relationships: [], spheres: [], curves: [] });
  const result = composeScene(
    {
      version: "v",
      composition: "display_only",
      frames: [
        {
          graph_id: "a",
          label: "A",
          snapshot_id: "s1",
          root_id: "root",
          transform: { scale: 1, translation: [0, 0, 0] },
          frame: frame([n("root", "workspace", null), n("repo", "repository", "root"), n("dir", "directory", "repo"), n("deep", "repository", "dir")]),
        },
        {
          graph_id: "b",
          label: "B",
          snapshot_id: "s2",
          root_id: "root",
          transform: { scale: 1, translation: [0, 0, 0] },
          frame: frame([n("root", "workspace", null), n("repo", "repository", "root")]),
        },
      ] as never,
    },
    { a: { dark: 0x111111, light: 0x222222 } },
  );
  const accents = result.data.accents!;
  const key = (g: string, s: string, id: string) => renderId(g, s, "node", id);
  assert.deepEqual(accents[key("a", "s1", "root")], [0x111111, 0x222222]);
  assert.deepEqual(accents[key("a", "s1", "repo")], [0x111111, 0x222222]);
  assert.equal(accents[key("a", "s1", "dir")], undefined, "what is inside keeps the colour of its content");
  assert.equal(accents[key("a", "s1", "deep")], undefined, "a nested repository is not the graph's own enclosure");
  assert.equal(Object.keys(accents).some((k) => k.includes('"b"')), false, "a graph with no accent is left as it was");
  assert.equal(composeScene({ version: "v", composition: "display_only", frames: [] }).data.accents, undefined);
});
