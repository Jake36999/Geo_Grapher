import assert from "node:assert/strict";
import { test } from "node:test";
import { compactLabel, repositoryLabel, setLibraryName } from "./names.ts";

test("graph labels drop the library name and keep the part that tells them apart", () => {
  setLibraryName("Nonlinear Field Lab");
  assert.equal(compactLabel("Nonlinear Field Lab-quantule_mapper-docs"), "quantule_mapper-docs");
  assert.equal(compactLabel("Nonlinear Field Lab-third-party"), "third-party");
  const long = compactLabel("Nonlinear Field Lab-quantule_mapper-colab_jobs-results-robustness-docs");
  assert.ok(long.length <= 34 && long.includes("…") && long.endsWith("robustness-docs"), long);
  setLibraryName("");
  assert.equal(compactLabel("Plain label"), "Plain label");
});

test("a repository never shows its internal id", () => {
  setLibraryName("Nonlinear Field Lab");
  const active = { label: "Nonlinear Field Lab-quantule_mapper", basePath: "/graphs/g_9e25f09ead6a48af654e7e31/" };
  // the active graph's reviewed-folder repository: an id of the form g_<24 hex>:<digest>
  assert.equal(repositoryLabel("g_9e25f09ead6a48af654e7e31:c69514817f8f", "g_9e25f09ead6a48af654e7e31:c69514817f8f", active), "quantule_mapper");
  // another graph's repository in the composed view: "graph label · own id"
  assert.equal(repositoryLabel("Nonlinear Field Lab-quantule_mapper-docs · g_aaaaaaaaaaaaaaaaaaaaaaaa:0011", "g_aaaaaaaaaaaaaaaaaaaaaaaa:0011", active), "quantule_mapper-docs");
  // unfinished description: nothing better known
  assert.equal(repositoryLabel("g_bbbbbbbbbbbbbbbbbbbbbbbb", "g_bbbbbbbbbbbbbbbbbbbbbbbb", { label: null, basePath: "/" }), "Repository");
  assert.equal(repositoryLabel("my-project", "r1", active), "my-project");
});

test("a node's own name drops the graph label the composed view adds", async () => {
  const { ownName } = await import("./names.ts");
  assert.equal(ownName("Nonlinear Field Lab-quantule_mapper · solver"), "solver");
  assert.equal(ownName("pkg.mod.func"), "pkg.mod.func");
});

test("members of one graph are told apart by their folder", async () => {
  const { memberFolder, repositoryLabel, setLibraryName } = await import("./names.ts");
  setLibraryName("Nonlinear Field Lab");
  assert.equal(memberFolder(String.raw`F:\quantule_mapper\external research`), "quantule_mapper/external research");
  assert.equal(memberFolder(String.raw`F:\quantule_mapper\tools\external_validation`), "external_validation");
  assert.equal(memberFolder("F:/a/colab_jobs/run1/docs"), "run1/docs");
  assert.equal(
    repositoryLabel("Nonlinear Field Lab-third-party · external_validation", "g_x:1", { label: null, basePath: "/" }),
    "third-party · external_validation",
  );
});
