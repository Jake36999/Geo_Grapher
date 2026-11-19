import assert from "node:assert/strict";
import { test } from "node:test";
import { activeOverrides, asciiMap, buildMap, formatBytes, tags, withRole, type MapPartition, type MapPlan } from "./ingestMap.ts";

const part = (key: string, role: string, subtree: string | null, files: number, extra: Partial<MapPartition> = {}): MapPartition => ({
  key,
  role,
  subtrees: subtree === null ? [] : [subtree],
  file_counts: { ".py": files },
  bytes: files * 1000,
  ...extra,
});

const policy = {
  current: { publication: "own", licence_applicable: false },
  docs: { publication: "own", licence_applicable: false },
  third_party: { publication: "reference", licence_applicable: true },
  research_docs: { publication: "reference", licence_applicable: false },
} as const;

const plan: MapPlan = {
  role_policy: policy,
  root:"D:\\Work\\resource-library",
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

test("a corrected role changes the labels, not the files: own work is no longer cited", () => {
  const unlicensed = plan.partitions[2];
  const own = withRole(unlicensed, "current", plan.role_policy);
  assert.equal(own.role, "current");
  assert.deepEqual(tags(own), ["own"]);
  assert.equal(own.suggestion?.licence, "not_applicable");
  assert.deepEqual(own.suggestion?.reasons, ["you chose “own”; the scan suggested “third-party”"]);
  assert.deepEqual(own.subtrees, unlicensed.subtrees); // where it is and what it holds are untouched
  assert.equal(own.bytes, unlicensed.bytes);
  assert.equal(withRole(unlicensed, undefined, plan.role_policy), unlicensed);
  assert.equal(withRole(unlicensed, "third_party", plan.role_policy), unlicensed); // choosing the suggestion changes nothing
});

test("choosing a licence-bearing role looks for a licence file again", () => {
  const docs = plan.partitions[1];
  assert.deepEqual(tags(withRole(docs, "third_party", plan.role_policy)), ["third-party", "cited, not published as our own", "no licence file"]);
  const licensed = part("lib", "current", "lib", 4, { suggestion: { publication: "own", licence: "not_applicable", licence_files: 2 } });
  assert.deepEqual(tags(withRole(licensed, "third_party", plan.role_policy)), ["third-party", "cited, not published as our own", "licence file present"]);
});

test("a role the scan did not describe keeps the scan's labels", () => {
  const odd = withRole(plan.partitions[2], "data", plan.role_policy);
  assert.equal(odd.role, "data");
  assert.equal(odd.suggestion?.publication, "reference");
});

test("the map and the pasted text show the corrected role", () => {
  const roles = { "vendor__no-licence": "current" };
  const root = buildMap(plan, roles);
  assert.equal(root.children.find((c) => c.name === "vendor")!.children[0].partition?.role, "current");
  assert.match(asciiMap(plan, roles).split("\n")[4], /^ {3}└─ no-licence\/\s+own\s+9 files/);
  assert.match(asciiMap(plan).split("\n")[4], /third-party/); // without a correction it is as scanned
});

test("only corrections that differ, for parts that will be ingested, are sent", () => {
  const roles = { docs: "docs", "vendor__no-licence": "current", papers: "legacy" };
  const approved = { residual: true, docs: true, "vendor__no-licence": true, papers: false };
  assert.deepEqual(activeOverrides(plan, roles, approved), { "vendor__no-licence": "current" });
  assert.deepEqual(activeOverrides(plan, {}, approved), {});
});
