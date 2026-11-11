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
// until `hex` reaches MIN_CONTRAST on `background`. Used only to derive the
// frozen constants below; the unit test proves the constants hold.
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

// Frozen stops: [source, target] per family. Dark values are master G9. Three
// G9 targets (hierarchy, doc_rationale, violation) measure 4.26:1 on #17191C,
// below the 4.5:1 the same section requires, so they are lightened in OkLab L
// in 0.02 steps until they pass. Light stops darken the dark stop in OkLab L
// in 0.02 steps until they pass on #F3F2EF.
const STOPS: Record<Theme, Record<RelationshipFamily, [string, string]>> = {
  dark: {
    call_or_data: ["#FF8A1F", "#FFC46B"],
    hierarchy: ["#C77DFF", "#9D66E8"],
    doc_rationale: ["#00E5FF", "#2589CA"],
    doc_describes: ["#7FD7FF", "#4F9BD9"],
    doc_cites: ["#00F5D4", "#00BB9E"],
    catalog_bridge: ["#FFE66D", "#F4A261"],
    violation: ["#FF2A55", "#DE545A"],
  },
  light: {
    call_or_data: ["#BA4A00", "#966100"],
    hierarchy: ["#954AC8", "#854DCD"],
    doc_rationale: ["#007891", "#0071AF"],
    doc_describes: ["#037397", "#1F70AB"],
    doc_cites: ["#007A60", "#007C63"],
    catalog_bridge: ["#806800", "#A45808"],
    violation: ["#DA0038", "#C23943"],
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

export const alphaAt = (t: number): number => 0.95 - 0.6 * t;

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
