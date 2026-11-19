import assert from "node:assert/strict";
import { test } from "node:test";
import { compareHeadline, compareRows, cycleSentence, previewMakesNothing, previewSentence, shortRef } from "./buildOps.ts";
import type { CompareResult, DerivePreview } from "./api.ts";

const preview = (over: Partial<DerivePreview> = {}): DerivePreview => ({
  mode: "keep",
  source_graph: "g_1",
  files: { total: 4, kept: 2, removed: 2 },
  entities: { total: 30, kept: 12, removed: 18 },
  relationships: { total: 20, kept: 9, dropped: 11 },
  paths: 2,
  unmatched_paths: [],
  note: "",
  ...over,
});

test("keep only says what stays and what crosses the cut", () => {
  assert.equal(
    previewSentence(preview()),
    "Keeps 2 of 4 files and 12 of 30 items. Relationships across the cut would be dropped: 11.",
  );
  assert.match(previewSentence(preview({ relationships: { total: 5, kept: 4, dropped: 1 } })), /dropped: 1\./);
});

test("remove says what goes", () => {
  const p = preview({ mode: "exclude", files: { total: 4, kept: 3, removed: 1 }, entities: { total: 30, kept: 25, removed: 5 } });
  assert.equal(previewSentence(p), "Removes 1 of 4 files and 5 of 30 items. Relationships dropped with them: 11.");
});

test("a preview that would make nothing says so and is flagged", () => {
  const none = preview({ files: { total: 4, kept: 0, removed: 4 } });
  assert.match(previewSentence(none), /nothing would be kept/);
  assert.equal(previewMakesNothing(none), true);
  const all = preview({ files: { total: 4, kept: 4, removed: 0 } });
  assert.equal(previewMakesNothing(all), true);
  assert.match(previewSentence(all), /covers every file, so keeping only it would change nothing/);
  assert.equal(previewMakesNothing(preview()), false);
  assert.match(previewSentence(preview({ mode: "exclude", files: { total: 4, kept: 4, removed: 0 } })), /nothing would be removed/);
  assert.match(previewSentence(preview({ mode: "exclude", files: { total: 4, kept: 0, removed: 4 } })), /nothing would be left/);
  assert.match(previewSentence(preview({ files: { total: 0, kept: 0, removed: 0 } })), /no files to count/);
});

const compare = (over: Partial<CompareResult> = {}): CompareResult => ({
  graph_a: "g_a",
  graph_b: "g_b",
  scope: "functions, methods and classes",
  compared: { a: 10, b: 12 },
  matched: 8,
  classes: { EXACT_AST_SURVIVOR: 5, SIGNATURE_OR_GUARD_DRIFT: 3, STRATUM_EXCLUSIVE: 6 },
  only_a: { count: 2, sample: [] },
  only_b: { count: 4, sample: [] },
  pairs: {},
  cycles: { CYCLE_DISSOLVED: 1 },
  ...over,
});

test("the comparison lists matches first, then what is only on one side, by graph name", () => {
  const rows = compareRows(compare(), "Old", "New");
  assert.deepEqual(
    rows.map((r) => [r.label, r.count]),
    [
      ["Identical", 5],
      ["Same contract, rewritten", 0],
      ["Same place in the graph", 0],
      ["Same name, changed", 3],
      ["Only in Old", 2],
      ["Only in New", 4],
    ],
  );
});

test("the headline reads in the graph names and handles empty graphs", () => {
  assert.equal(
    compareHeadline(compare(), "Old", "New"),
    "8 items in Old have a counterpart in New; 2 appear only in Old and 4 only in New.",
  );
  assert.match(compareHeadline(compare({ matched: 1 }), "Old", "New"), /^1 item in Old has a counterpart/);
  assert.match(compareHeadline(compare({ compared: { a: 0, b: 0 } }), "Old", "New"), /Neither graph has/);
});

test("dependency-loop changes read plainly, and nothing is said when there are none", () => {
  assert.equal(cycleSentence(compare()), "Dependency loops: 1 dissolved.");
  assert.equal(cycleSentence(compare({ cycles: { CYCLE_INTRODUCED: 2, COUPLING_REDUCED: 1 } })), "Dependency loops: 2 new, 1 less tangled.");
  assert.equal(cycleSentence(compare({ cycles: {} })), "");
});

test("long endpoints keep their start and end", () => {
  assert.equal(shortRef("root"), "root");
  assert.equal(shortRef("doc:12#claim:3"), "doc:12#claim:3");
  const long = "entity:" + "a1b2c3d4".repeat(8);
  const short = shortRef(long);
  assert.ok(short.length < long.length && short.startsWith("entity:a1b2c3d4") && short.endsWith(long.slice(-10)) && short.includes("…"));
});

test("a link's state reads as whether it still holds", async () => {
  const { linkStateLabel, kindLabel } = await import("./buildOps.ts");
  assert.equal(linkStateLabel("accepted"), "in force");
  assert.equal(linkStateLabel("suspect_stale"), "may be out of date");
  assert.equal(linkStateLabel("something_new"), "something new");
  assert.equal(kindLabel("concept_equivalence"), "concept equivalence");
});
