import assert from "node:assert/strict";
import { test } from "node:test";
import { ACCENTS, accentHex, assignAccents, cssColour } from "./accents.ts";

const ids = ["g_1a", "g_2b", "g_3c", "g_4d", "g_5e", "g_6f"];

test("each graph gets its own colour while the set lasts", () => {
  const out = assignAccents(ids);
  assert.equal(new Set(ids.map((id) => out[id].id)).size, ids.length);
});

test("colours go by id order, not by the order graphs are listed or shown", () => {
  const all = assignAccents(ids);
  assert.deepEqual(assignAccents([...ids].reverse()), all);
  assert.deepEqual(assignAccents(ids.slice(0).sort()), all);
});

test("a person's choice wins, and the others step around it", () => {
  const base = assignAccents(ids);
  const taken = base["g_2b"].id;
  const chosen = assignAccents(ids, { g_1a: taken });
  assert.equal(chosen["g_1a"].id, taken);
  assert.notEqual(chosen["g_2b"].id, taken, "the graph that had it moves to a free colour");
  assert.equal(new Set(ids.map((id) => chosen[id].id)).size, ids.length);
  assert.equal(assignAccents(ids, { g_1a: "not-a-colour" })["g_1a"].id, base["g_1a"].id, "an unknown choice is ignored");
});

test("more graphs than colours share colours rather than failing", () => {
  const many = Array.from({ length: ACCENTS.length + 3 }, (_, i) => `g_${i.toString().padStart(3, "0")}`);
  const out = assignAccents(many);
  assert.equal(Object.keys(out).length, many.length);
  assert.ok(many.every((id) => ACCENTS.includes(out[id])));
});

test("the colour ids and hex values are valid and distinct", () => {
  assert.equal(new Set(ACCENTS.map((a) => a.id)).size, ACCENTS.length);
  assert.equal(new Set(ACCENTS.map((a) => a.dark)).size, ACCENTS.length);
  assert.equal(new Set(ACCENTS.map((a) => a.light)).size, ACCENTS.length);
  assert.equal(cssColour(0x5b9bff), "#5b9bff");
  assert.equal(cssColour(0x0a0b0c), "#0a0b0c");
  assert.equal(accentHex(ACCENTS[0], "dark"), ACCENTS[0].dark);
  assert.equal(accentHex(ACCENTS[0], "light"), ACCENTS[0].light);
});
