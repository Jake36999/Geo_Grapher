import assert from "node:assert/strict";
import { test } from "node:test";
import { DEFAULT_MAX_GRAPHS, addGraph, initialSelection } from "./graphSelection.ts";

const six = ["a", "b", "c", "d", "e", "f"];

test("a first visit to a large library opens one graph, not all of them", () => {
  assert.deepEqual(initialSelection({ available: six, first: "a", saved: null, max: 3 }), ["a"]);
});

test("a first visit to a small library still shows all its graphs, the requested one first", () => {
  assert.deepEqual(initialSelection({ available: ["a", "b"], first: "a", saved: null, max: 3 }), ["a", "b"]);
  assert.deepEqual(initialSelection({ available: ["a", "b", "c"], first: "c", saved: null, max: 3 }), ["c", "a", "b"]);
  assert.deepEqual(initialSelection({ available: ["a", "b", "c", "d"], first: "c", saved: null, max: 3 }), ["c"]);
});

test("a saved selection is restored, trimmed to the cap, and drops graphs that are gone", () => {
  const ids = initialSelection({ available: six, first: "a", saved: ["x", "b", "c", "d", "e"], max: 3 });
  assert.deepEqual(ids, ["b", "c", "d"]);
});

test("a requested graph is shown first even when the saved set left it out", () => {
  const ids = initialSelection({ available: six, first: "e", saved: ["a", "b", "c"], max: 3, forceFirst: true });
  assert.deepEqual(ids, ["e", "a", "b"]);
});

test("a saved selection whose graphs are all gone falls back to the first-visit default", () => {
  assert.deepEqual(initialSelection({ available: six, first: "a", saved: ["x", "y"], max: 3 }), ["a"]);
});

test("a deliberately empty saved selection stays empty after a reload", () => {
  assert.deepEqual(initialSelection({ available: six, first: "a", saved: [], max: 3 }), []);
});

test("adding a graph past the cap is refused, so the picker can say why", () => {
  assert.deepEqual(addGraph(["a", "b"], "c", 3), { ids: ["a", "b", "c"], full: false });
  assert.deepEqual(addGraph(["a", "b", "c"], "d", 3), { ids: ["a", "b", "c"], full: true });
  assert.deepEqual(addGraph(["a", "b", "c"], "b", 3), { ids: ["a", "b", "c"], full: false });
});

test("the default cap matches the server's", () => {
  assert.equal(DEFAULT_MAX_GRAPHS, 3);
});
