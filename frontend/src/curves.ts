import type { Vec3, ViewportFrameData } from "../../contracts/geographer.wire";
export type Curve = ViewportFrameData["curves"][number];
export interface Lens {
  enabled: boolean;
  center: Vec3;
  radius: number;
  strength: number;
}
const add = (a: Vec3, b: Vec3): Vec3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const mul = (a: Vec3, s: number): Vec3 => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const length = (a: Vec3) => Math.sqrt(dot(a, a));
const falloff = (p: Vec3, lens: Lens) => {
  const q = Math.min(1, length(sub(p, lens.center)) / lens.radius);
  return 1 - 3 * q * q + 2 * q * q * q;
};

export function evaluate(
  points: Vec3[],
  degree: number,
  knots: number[],
  t: number,
): Vec3 {
  if (t <= 0) return [...points[0]];
  if (t >= 1) return [...points.at(-1)!];
  let span = points.length - 1;
  for (let i = degree; i < points.length; i++)
    if (knots[i] <= t && t < knots[i + 1]) {
      span = i;
      break;
    }
  const d = Array.from(
    { length: degree + 1 },
    (_, j) => [...points[span - degree + j]] as Vec3,
  );
  for (let r = 1; r <= degree; r++)
    for (let j = degree; j >= r; j--) {
      const k = span - degree + j,
        denom = knots[k + degree - r + 1] - knots[k],
        alpha = denom ? (t - knots[k]) / denom : 0;
      d[j] = add(mul(d[j - 1], 1 - alpha), mul(d[j], alpha));
    }
  return d[degree];
}

export function samples(
  curve: Curve,
  beta: number,
  lens: Lens,
  radius = 1,
): Vec3[] {
  const raw = curve.control_points,
    N = raw.length,
    p = curve.degree,
    U = curve.knots;
  if (curve.canonical_source === curve.canonical_target) {
    const R = radius + curve.lane_spacing * (curve.lane_index + 1);
    return Array.from({ length: curve.sample_count + 1 }, (_, i) => {
      const t = i / curve.sample_count;
      return add(
        raw[0],
        add(
          mul(curve.normal, R * (1 - Math.cos(2 * Math.PI * t))),
          mul(curve.binormal, R * Math.sin(2 * Math.PI * t)),
        ),
      );
    });
  }
  const delta = sub(raw[N - 1], raw[0]),
    L = length(delta),
    T = mul(delta, 1 / Math.max(1e-12, L));
  const controls = raw.map((point, i) => {
    const local =
      beta * (1 - (lens.enabled ? lens.strength * falloff(point, lens) : 0));
    const chord = add(raw[0], mul(delta, i / (N - 1)));
    let value = add(mul(point, local), mul(chord, 1 - local));
    const g = U.slice(i + 1, i + p + 1).reduce((a, b) => a + b, 0) / p;
    value = add(value, mul(T, dot(sub(add(raw[0], mul(delta, g)), value), T)));
    return value;
  });
  const result = Array.from({ length: curve.sample_count + 1 }, (_, i) => {
    const t = i / curve.sample_count,
      point = evaluate(controls, p, U, t);
    const spacing =
      curve.lane_spacing *
      (1 + (lens.enabled ? lens.strength * falloff(point, lens) : 0));
    return add(
      point,
      mul(
        curve.normal,
        Math.sin(Math.PI * t) *
          spacing *
          (curve.lane_index - (curve.lane_count - 1) / 2),
      ),
    );
  });
  return curve.reversed ? result.reverse() : result;
}
