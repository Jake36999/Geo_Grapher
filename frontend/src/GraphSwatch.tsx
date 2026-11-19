import type { CSSProperties } from "react";
import { cssColour, type Accent } from "./accents";

/** A small dot in a graph's accent colour. Decorative: the graph's name always sits beside it. */
export default function GraphSwatch({ accent }: { accent?: Accent }) {
  if (!accent) return null;
  return (
    <span
      className="graph-swatch"
      aria-hidden="true"
      style={{ "--sw-dark": cssColour(accent.dark), "--sw-light": cssColour(accent.light) } as CSSProperties}
    />
  );
}
