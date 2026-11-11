import assert from "node:assert/strict";
import { test } from "node:test";
import {
  alphaAt,
  colourAt,
  contrastRatio,
  dashFor,
  familyStops,
  type RelationshipFamily,
} from "./edgeStyle.ts";

const families: RelationshipFamily[] = [
  "call_or_data",
  "hierarchy",
  "doc_rationale",
  "doc_describes",
  "doc_cites",
  "catalog_bridge",
  "violation",
];

test("every family stop has WCAG contrast >= 4.5 on both theme backgrounds", () => {
  for (const theme of ["dark", "light"] as const)
    for (const f of families) {
      const [a, b] = familyStops(f, theme);
      const bg = theme === "dark" ? "#17191C" : "#F3F2EF";
      assert(contrastRatio(a, bg) >= 4.5, `${f}/${theme} source ${a}`);
      assert(contrastRatio(b, bg) >= 4.5, `${f}/${theme} target ${b}`);
    }
});

test("dark stops are the master G9 palette", () => {
  assert.deepEqual(familyStops("call_or_data", "dark"), ["#FF8A1F", "#FFC46B"]);
  // Targets of hierarchy, doc_rationale and violation are lightened (G9 lists
  // 4.26:1 values) so the 4.5:1 requirement holds; sources are untouched.
  assert.equal(familyStops("hierarchy", "dark")[0], "#C77DFF");
  assert.equal(familyStops("violation", "dark")[0], "#FF2A55");
});

test("alpha law is 0.95 - 0.60 t and monotone decreasing", () => {
  assert(alphaAt(0) === 0.95);
  assert(Math.abs(alphaAt(1) - 0.35) < 1e-9);
  assert(alphaAt(0.3) > alphaAt(0.7));
});

test("dash law", () => {
  assert(dashFor("exact") === null);
  assert(dashFor("observed") === null);
  assert(dashFor("candidate")!.dash === 0.3);
  assert(dashFor("candidate")!.gap === 0.18);
  assert(dashFor("expected_only")!.dash === 0.06);
  assert(dashFor("expected_only")!.gap === 0.16);
});

test("colourAt interpolates in OkLab between the stops", () => {
  const [s, e] = familyStops("hierarchy", "dark");
  const hex = (c: number[]) =>
    "#" +
    c
      .map((v) =>
        Math.round(v * 255)
          .toString(16)
          .padStart(2, "0"),
      )
      .join("")
      .toUpperCase();
  assert.equal(hex(colourAt("hierarchy", "dark", 0)), s);
  assert.equal(hex(colourAt("hierarchy", "dark", 1)), e);
  const mid = colourAt("hierarchy", "dark", 0.5);
  assert(mid.every((v) => v >= 0 && v <= 1));
});

test("contrastRatio matches known WCAG values", () => {
  assert(Math.abs(contrastRatio("#000000", "#FFFFFF") - 21) < 1e-9);
  assert(Math.abs(contrastRatio("#FFFFFF", "#FFFFFF") - 1) < 1e-9);
});
