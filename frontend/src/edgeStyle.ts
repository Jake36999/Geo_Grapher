// Edge chromatics (master G9, "edge-chromatics-v1"). Pure functions only: no
// three.js, no DOM, so the same code runs under `node --test`.
export type RelationshipFamily =
  | "call_or_data"
  | "hierarchy"
  | "doc_rationale"
  | "doc_describes"
  | "doc_cites"
  | "catalog_bridge"
  | "violation";
export type RuntimeStatus =
  "exact" | "candidate" | "expected_only" | "observed";
export type Theme = "dark" | "light";
export type Rgb = [r: number, g: number, b: number];

export const BACKGROUND: Record<Theme, string> = {
  dark: "#17191C",
  light: "#F3F2EF",
};
export const MIN_CONTRAST = 4.5;

const toLinear = (c: number) =>
  c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
const fromLinear = (c: number) =>
  c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055;

export function hexToRgb(hex: string): Rgb {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}
export function rgbToHex(rgb: Rgb): string {
  return (
    "#" +
    rgb
      .map((v) =>
        Math.round(Math.min(1, Math.max(0, v)) * 255)
          .toString(16)
          .padStart(2, "0"),
      )
      .join("")
      .toUpperCase()
  );
}

export function srgbToOkLab([r, g, b]: Rgb): [number, number, number] {
  const lr = toLinear(r),
    lg = toLinear(g),
    lb = toLinear(b);
  const l = Math.cbrt(
      0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb,
    ),
    m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb),
    s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}
export function okLabToSrgb([L, a, b]: [number, number, number]): Rgb {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3,
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3,
    s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  const lin: Rgb = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
  return lin.map((v) => Math.min(1, Math.max(0, fromLinear(v)))) as Rgb;
}

// WCAG 2.x relative luminance and contrast ratio.
function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map(toLinear);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
export function contrastRatio(hexA: string, hexB: string): number {
  const a = luminance(hexA),
    b = luminance(hexB);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

// Shifts OkLab L in steps of `step` (negative darkens, positive lightens)
// until `hex` reaches MIN_CONTRAST on `background`. A tool for choosing stops;
// the unit test proves the frozen constants below hold.
export function shiftUntilContrast(
  hex: string,
  background: string,
  step: number,
): string {
  const [L, a, b] = srgbToOkLab(hexToRgb(hex));
  let out = hex;
  for (let i = 1; i <= 60 && contrastRatio(out, background) < MIN_CONTRAST; i++)
    out = rgbToHex(okLabToSrgb([L + step * i, a, b]));
  return out;
}

// Frozen stops: [source, target] per family. Each family is ONE colour. Direction is carried by the fade
// away from the source end (alphaAt), not by a hue change, so a thread reads as a single colour thinning out
// from the node it leaves, never as a blend of the two nodes' colours. Owner direction 2026-11-19: the
// threads are thin and sat matte against the nodes, so the dark colours are neon (saturated and bright);
// the light colours are the same hues deepened until they hold 4.5:1 on #F3F2EF (neon cannot be bright on
// a light page). The target equals the source; the pair is kept so a family could be given a deliberate
// second tone later. Every stop keeps the 4.5:1 contrast the master G9 section requires; the unit test
// proves it, along with the chroma and the single hue.
const STOPS: Record<Theme, Record<RelationshipFamily, [string, string]>> = {
  dark: {
    call_or_data: ["#FF6A00", "#FF6A00"],
    hierarchy: ["#E040FF", "#E040FF"],
    doc_rationale: ["#00F0FF", "#00F0FF"],
    doc_describes: ["#3FA9FF", "#3FA9FF"],
    doc_cites: ["#00FFC8", "#00FFC8"],
    catalog_bridge: ["#FFE600", "#FFE600"],
    violation: ["#FF1744", "#FF1744"],
  },
  light: {
    call_or_data: ["#B84300", "#B84300"],
    hierarchy: ["#A52FD6", "#A52FD6"],
    doc_rationale: ["#007489", "#007489"],
    doc_describes: ["#0068B0", "#0068B0"],
    doc_cites: ["#007A64", "#007A64"],
    catalog_bridge: ["#7C6400", "#7C6400"],
    violation: ["#D8002F", "#D8002F"],
  },
};

export function familyStops(
  family: RelationshipFamily,
  theme: Theme,
): [string, string] {
  return STOPS[theme][family];
}

// Direction law: colour(t) = mix_OkLab(source, target, t), t = 0 at the source.
export function colourAt(
  family: RelationshipFamily,
  theme: Theme,
  t: number,
): Rgb {
  const [s, e] = familyStops(family, theme);
  const a = srgbToOkLab(hexToRgb(s)),
    b = srgbToOkLab(hexToRgb(e)),
    u = Math.min(1, Math.max(0, t));
  return okLabToSrgb([
    a[0] + (b[0] - a[0]) * u,
    a[1] + (b[1] - a[1]) * u,
    a[2] + (b[2] - a[2]) * u,
  ]);
}

export const ALPHA_START = 0.95;
export const ALPHA_SLOPE = 0.6;
export const alphaAt = (t: number): number => ALPHA_START - ALPHA_SLOPE * t;

// Status law, world units. Exact and observed are solid (observed pulses in
// the shader).
export function dashFor(
  status: RuntimeStatus,
): { dash: number; gap: number } | null {
  if (status === "candidate") return { dash: 0.3, gap: 0.18 };
  if (status === "expected_only") return { dash: 0.06, gap: 0.16 };
  return null;
}
export const STATUS_CODE: Record<RuntimeStatus, number> = {
  exact: 0,
  candidate: 1,
  expected_only: 2,
  observed: 3,
};
export const PULSE_PERIOD_SECONDS = 1.2;
export const PULSE_GAIN = 1.6;

// ---- Resolution of what reaches the shader (pure; used by Scene.tsx) ----
export interface RelationFacts {
  family?: string;
  resolution_status?: string;
}
export interface StyledCurveFields {
  relationship_family?: RelationshipFamily;
  runtime_status?: RuntimeStatus;
}

// Runtime status. An explicit `runtime_status` wins; otherwise derive it from
// the relationship (G9 status table) for frames that predate v1.1.
export function resolveStatus(
  curve: StyledCurveFields,
  relation?: RelationFacts,
): RuntimeStatus {
  if (curve.runtime_status) return curve.runtime_status;
  if (relation?.family === "runtime") return "observed";
  if (relation?.family === "expected") return "expected_only";
  if (
    relation?.resolution_status === "candidate" ||
    relation?.resolution_status === "unresolved"
  )
    return "candidate";
  return "exact";
}

// Family of a relationship curve. The backend never emits `violation`; the
// active violations win over any family. Absent family means call_or_data.
export function resolveCurveFamily(
  curve: StyledCurveFields,
  violated: boolean,
): RelationshipFamily {
  return violated ? "violation" : (curve.relationship_family ?? "call_or_data");
}
export function resolveCurveStyle(
  curve: StyledCurveFields,
  violated: boolean,
  relation?: RelationFacts,
) {
  return {
    family: resolveCurveFamily(curve, violated),
    status: resolveStatus(curve, relation),
  };
}
export function resolveLinkStyle(link: StyledCurveFields): {
  family: RelationshipFamily;
  status: RuntimeStatus;
} {
  return {
    family: link.relationship_family ?? "doc_describes",
    status: link.runtime_status ?? "exact",
  };
}

export interface LinkGeometry {
  link_id: string;
  fragment_rep: string;
  entity_rep: string;
  control_points: [number, number, number][];
  degree: 1 | 2 | 3;
  knots: number[];
}
// Adapts a documentary link to the curve shape `samples()` consumes.
export function documentaryCurve(link: LinkGeometry) {
  return {
    relationship_id: link.link_id,
    canonical_source: link.fragment_rep,
    canonical_target: link.entity_rep,
    reversed: false,
    control_points: link.control_points,
    degree: link.degree,
    knots: link.knots,
    normal: [0, 1, 0] as [number, number, number],
    binormal: [0, 0, 1] as [number, number, number],
    lane_index: 0,
    lane_count: 1,
    lane_spacing: 0,
    sample_count: 32,
  };
}
