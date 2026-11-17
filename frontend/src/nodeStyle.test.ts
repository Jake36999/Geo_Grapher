import assert from "node:assert/strict";
import { test } from "node:test";
import {
  CROSSING_FADE,
  categoryColour,
  edgeFade,
  nodeCategory,
  nodeColour,
} from "./nodeStyle.ts";

const file = (rel_path: string, flags = {}) => ({ kind: "file", source: { rel_path }, flags });

test("files are coloured by what they contain", () => {
  assert.equal(nodeCategory(file("src/app.py")), "code");
  assert.equal(nodeCategory(file("docs/README.md")), "docs");
  assert.equal(nodeCategory(file("runs/result.jsonl")), "data");
  assert.equal(nodeCategory(file("pyproject.toml")), "config");
  assert.equal(nodeCategory(file("notebooks/a.ipynb")), "notebook");
  assert.equal(nodeCategory(file("img/plot.png")), "media");
  assert.equal(nodeCategory(file("tests/test_a.py", { is_test: true })), "test");
  assert.equal(nodeCategory(file("build/gen.py", { is_generated: true })), "outside");
  assert.equal(nodeCategory(file("Dockerfile")), "config");
});

test("symbols and atoms are coloured by kind; containers stay neutral", () => {
  assert.equal(nodeCategory({ kind: "class" }), "class");
  assert.equal(nodeCategory({ kind: "method" }), "function");
  assert.equal(nodeCategory({ kind: "function", flags: { is_test: true } }), "test");
  assert.equal(nodeCategory({ kind: "constant" }), "constant");
  assert.equal(nodeCategory({ kind: "external_symbol" }), "external");
  assert.equal(nodeCategory({ kind: "scope_atom" }), "atom");
  assert.equal(nodeCategory({ kind: "directory" }), "container");
  assert.equal(nodeCategory({ kind: "repository" }), "container");
});

test("distinct content gets distinct colours in both themes", () => {
  for (const theme of ["dark", "light"] as const) {
    const seen = new Set(
      ["code", "docs", "data", "config", "test", "class", "function"].map((c) =>
        categoryColour(c as never, theme),
      ),
    );
    assert.equal(seen.size, 7, theme);
  }
  assert.equal(nodeColour(file("a.py"), "dark"), categoryColour("code", "dark"));
  // A container's tone depends only on its parent key, so it is stable between frames.
  assert.equal(nodeColour({ kind: "directory" }, "dark", "p1"), nodeColour({ kind: "directory" }, "dark", "p1"));
});

test("a relationship leaving its repository is faded, and hidden unless both ends show", () => {
  const a = { repo_id: "g_1:aa" },
    b = { repo_id: "g_1:bb" };
  assert.equal(edgeFade(a, a, true, true), 1);
  assert.equal(edgeFade(a, b, true, true), CROSSING_FADE);
  assert.ok(CROSSING_FADE > 0 && CROSSING_FADE < 1);
  assert.equal(edgeFade(a, b, true, false), null);
  assert.equal(edgeFade(a, a, false, true), null);
  assert.equal(edgeFade({}, b, true, true), 1); // unknown repository: not judged as crossing
});
