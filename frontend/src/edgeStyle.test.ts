import assert from "node:assert/strict";
import { test } from "node:test";
import {
  alphaAt,
  colourAt,
  contrastRatio,
  dashFor,
  familyStops,
  hexToRgb,
  rgbToHex,
  srgbToOkLab,
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

test("dark stops are neon, and each thread is one colour: direction is the fade, not a hue change", () => {
  const lab = (hex: string) => srgbToOkLab(hexToRgb(hex));
  const chroma = (hex: string) => Math.hypot(lab(hex)[1], lab(hex)[2]);
  const hue = (hex: string) => (Math.atan2(lab(hex)[2], lab(hex)[1]) * 180) / Math.PI;
  const gap = (x: number, y: number) => Math.abs(((x - y + 540) % 360) - 180);
  for (const theme of ["dark", "light"] as const)
    for (const f of families) {
      const [a, b] = familyStops(f, theme);
      assert(gap(hue(a), hue(b)) <= 10, `${f}/${theme} is one colour, not a blend: ${a} ${b}`);
    }
  for (const f of families) {
    const [a, b] = familyStops(f, "dark");
    assert(chroma(a) >= 0.14 && chroma(b) >= 0.14, `${f} is neon (saturated): ${a} ${b}`);
  }
  // the whole thread is that one colour: the midpoint is the same hue as the ends
  for (const f of families) {
    const mid = rgbToHex(colourAt(f, "dark", 0.5));
    assert(gap(hue(mid), hue(familyStops(f, "dark")[0])) <= 10, `${f} midpoint stays the same colour`);
  }
});

test("light stops keep the hue of their dark stop and still hold 4.5:1", () => {
  const hue = (hex: string) => {
    const [, a, b] = srgbToOkLab(hexToRgb(hex));
    return (Math.atan2(b, a) * 180) / Math.PI;
  };
  const gap = (x: number, y: number) => Math.abs(((x - y + 540) % 360) - 180);
  for (const f of families) {
    const [dark] = familyStops(f, "dark"),
      [light] = familyStops(f, "light");
    assert(gap(hue(dark), hue(light)) <= 50, `${f}: light ${light} keeps the hue of ${dark}`);
  }
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

import {
  documentaryCurve,
  resolveCurveStyle,
  resolveLinkStyle,
  resolveStatus,
  ALPHA_SLOPE,
  ALPHA_START,
} from "./edgeStyle.ts";

test("status derives from the relationship when runtime_status is absent", () => {
  assert.equal(resolveStatus({}, { family: "runtime" }), "observed");
  assert.equal(resolveStatus({}, { family: "expected" }), "expected_only");
  assert.equal(
    resolveStatus({}, { resolution_status: "candidate" }),
    "candidate",
  );
  assert.equal(
    resolveStatus({}, { resolution_status: "unresolved" }),
    "candidate",
  );
  assert.equal(
    resolveStatus({}, { family: "static", resolution_status: "exact" }),
    "exact",
  );
  assert.equal(resolveStatus({}, undefined), "exact");
});

test("explicit runtime_status wins over the relationship", () => {
  assert.equal(
    resolveStatus({ runtime_status: "exact" }, { family: "runtime" }),
    "exact",
  );
  assert.equal(resolveStatus({ runtime_status: "observed" }, {}), "observed");
});

test("violation override wins over every family", () => {
  for (const f of families)
    assert.equal(
      resolveCurveStyle({ relationship_family: f }, true).family,
      "violation",
    );
  assert.equal(
    resolveCurveStyle({ relationship_family: "hierarchy" }, false).family,
    "hierarchy",
  );
});

test("fallbacks when family or status are absent", () => {
  assert.deepEqual(resolveCurveStyle({}, false), {
    family: "call_or_data",
    status: "exact",
  });
  assert.deepEqual(resolveLinkStyle({}), {
    family: "doc_describes",
    status: "exact",
  });
  assert.deepEqual(
    resolveLinkStyle({
      relationship_family: "doc_cites",
      runtime_status: "candidate",
    }),
    { family: "doc_cites", status: "candidate" },
  );
});

test("documentary adapter yields a samplable curve", () => {
  const c = documentaryCurve({
    link_id: "L",
    fragment_rep: "F",
    entity_rep: "E",
    control_points: [
      [0, 0, 0],
      [1, 1, 0],
      [2, 0, 0],
    ],
    degree: 2,
    knots: [0, 0, 0, 1, 1, 1],
  });
  assert.equal(c.relationship_id, "L");
  assert.equal(c.canonical_source, "F");
  assert.equal(c.canonical_target, "E");
  assert.equal(c.reversed, false);
  assert.equal(c.lane_count, 1);
  assert.equal(c.lane_spacing, 0);
  assert.equal(c.sample_count, 32);
  assert.deepEqual(c.control_points, [
    [0, 0, 0],
    [1, 1, 0],
    [2, 0, 0],
  ]);
});

test("alpha constants feed alphaAt", () => {
  assert.equal(alphaAt(0.5), ALPHA_START - ALPHA_SLOPE * 0.5);
});
