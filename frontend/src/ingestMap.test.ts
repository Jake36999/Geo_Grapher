import assert from "node:assert/strict";
import { test } from "node:test";
import { asciiMap, buildMap, formatBytes, tags, type MapPartition, type MapPlan } from "./ingestMap.ts";

const part = (key: string, role: string, subtree: string | null, files: number, extra: Partial<MapPartition> = {}): MapPartition => ({
  key,
  role,
  subtrees: subtree === null ? [] : [subtree],
  file_counts: { ".py": files },
  bytes: files * 1000,
  ...extra,
});

const plan: MapPlan = {
  root: "D:\\Work\\resource-library",
  partitions: [
    part("residual", "current", null, 40, { suggestion: { publication: "own", licence: "not_applicable" } }),
    part("docs", "docs", "docs", 12, { suggestion: { publication: "own", licence: "not_applicable" } }),
    part("vendor__no-licence", "third_party", "vendor/no-licence", 9, {
      suggestion: { publication: "reference", licence: "none_found" },
    }),
    part("papers", "research_docs", "papers", 3, { suggestion: { publication: "reference", licence: "not_applicable" } }),
  ],
};

test("the map is the root with each partition at its own path, and folders that only lead to one as plain nodes", () => {
  const root = buildMap(plan);
  assert.equal(root.name, "resource-library"); // a Windows path still gives its folder name
  assert.equal(root.partition?.key, "residual");
  assert.deepEqual(root.children.map((c) => c.name), ["docs", "papers", "vendor"]);
  const vendor = root.children.find((c) => c.name === "vendor")!;
  assert.equal(vendor.partition, undefined);
  assert.equal(vendor.children[0].partition?.key, "vendor__no-licence");
  assert.equal(vendor.children[0].path, "vendor/no-licence");
});

test("an unlicensed source is labelled as cited and without a licence file, never as withheld", () => {
  const unlicensed = plan.partitions[2];
  assert.deepEqual(tags(unlicensed), ["third-party", "cited, not published as our own", "no licence file"]);
  assert.deepEqual(tags(plan.partitions[1]), ["own · docs"]);
  assert.ok(!tags(unlicensed).join(" ").toLowerCase().includes("withheld"));
});

test("the text map is a tree with aligned labels and counts", () => {
  const text = asciiMap(plan);
  const lines = text.split("\n");
  assert.equal(lines.length, 5);
  assert.match(lines[0], /^resource-library\/\s+own\s+40 files · 39 KB$/);
  assert.match(lines[1], /^├─ docs\/\s+own · docs\s+12 files/);
  assert.match(lines[2], /^├─ papers\/\s+research papers · cited, not published as our own\s+3 files/);
  assert.match(lines[3], /^└─ vendor\/$/);
  assert.match(lines[4], /^ {3}└─ no-licence\/\s+third-party · cited, not published as our own · no licence file\s+9 files/);
  const labelColumns = new Set(lines.filter((l) => /files/.test(l)).map((l) => l.search(/own|research|third-party/)));
  assert.equal(labelColumns.size, 1, "the label column lines up");
});

test("a lone root with no folders still maps", () => {
  const only: MapPlan = { root: "/data/notes", partitions: [part("residual", "current", null, 2)] };
  assert.equal(asciiMap(only), "notes/  own  2 files · 2.0 KB");
});

test("sizes read in plain units", () => {
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(2048), "2.0 KB");
  assert.equal(formatBytes(50 * 1024), "50 KB");
  assert.equal(formatBytes(3 * 1024 * 1024), "3.0 MB");
});
