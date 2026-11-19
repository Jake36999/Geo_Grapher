// Node colour by content (owner, 2026-11-17: "the colour of nodes, in file, function and
// atomic view should be colour coded depending on content"). Containers stay neutral so the
// content they hold is what stands out. Hues are muted and kept apart from the relationship
// colours (orange call/data, violet hierarchy, cyan rationale, gold bridge, red violation).

export type NodeCategory =
  | "code"
  | "docs"
  | "data"
  | "config"
  | "notebook"
  | "media"
  | "test"
  | "outside"
  | "class"
  | "function"
  | "constant"
  | "external"
  | "atom"
  | "container";

export interface StyledNode {
  kind: string;
  language?: string;
  qualified_name?: string;
  source?: { rel_path?: string } | null;
  flags?: {
    is_test?: boolean;
    is_generated?: boolean;
    is_vendor?: boolean;
    is_external?: boolean;
  };
}

const EXTENSIONS: Record<string, NodeCategory> = {};
const add = (category: NodeCategory, list: string) =>
  list.split(" ").forEach((e) => (EXTENSIONS[e] = category));
add(
  "code",
  "py pyi rs go c h cc cpp hpp cxx cs java kt js mjs cjs ts tsx jsx vue svelte rb php swift scala lua r jl sh bash ps1 psm1 bat cmd sql proto zig dart m mm",
);
add("docs", "md markdown rst txt pdf html htm tex adoc org rtf docx");
add("data", "json jsonl ndjson csv tsv npz npy parquet sqlite db xml arrow h5 hdf5 pkl pickle log");
add("config", "toml yaml yml ini cfg conf lock env properties j2 jinja editorconfig gitignore dockerfile");
add("notebook", "ipynb");
add("media", "png jpg jpeg gif svg webp bmp ico blend blend1 mp4 mov wav mp3 zip tar gz 7z bin drawio");

/** The extension of a file node, lower case, or "" when there is none. */
export function extensionOf(node: StyledNode): string {
  const path = node.source?.rel_path || node.qualified_name || "";
  const base = path.split(/[\\/]/).at(-1) ?? "";
  if (/^dockerfile$/i.test(base)) return "dockerfile";
  const dot = base.lastIndexOf(".");
  return dot > 0 ? base.slice(dot + 1).toLowerCase() : "";
}

export function nodeCategory(node: StyledNode): NodeCategory {
  const flags = node.flags ?? {};
  if (flags.is_generated || flags.is_vendor) return "outside";
  switch (node.kind) {
    case "class":
      return flags.is_test ? "test" : "class";
    case "function":
    case "method":
      return flags.is_test ? "test" : "function";
    case "constant":
    case "attribute":
    case "parameter":
      return "constant";
    case "external_symbol":
      return "external";
    case "scope_atom":
      return "atom";
    case "document":
    case "fragment":
      return "docs";
    case "file": {
      if (flags.is_test) return "test";
      if (flags.is_external) return "outside";
      return EXTENSIONS[extensionOf(node)] ?? (node.language ? "code" : "container");
    }
    default:
      return "container";
  }
}

// [dark theme, light theme]
const COLOURS: Record<NodeCategory, [number, number]> = {
  code: [0x8aa4c8, 0x3f5f86],
  docs: [0x9cbf9a, 0x4f7a4c],
  data: [0xc8b48a, 0x86703e],
  config: [0xb59ac4, 0x6c4f80],
  notebook: [0x8cc0bc, 0x3f7a76],
  media: [0x9a9a9a, 0x6e6e6e],
  test: [0xc79aa6, 0x84505e],
  outside: [0x6f7378, 0xa0a4a8],
  class: [0xcfb27a, 0x8a6b2e],
  function: [0x86b6d6, 0x2f6d93],
  constant: [0xc2a68e, 0x7c5f46],
  external: [0x7b8087, 0x9a9ea3],
  atom: [0x8e99a6, 0x5c6772],
  container: [0xa7b4bc, 0x627783],
};
const CONTAINER_TONES: [number[], number[]] = [
  [0xa7b4bc, 0xaaa69a, 0x9faea3, 0xaca6af],
  [0x627783, 0x817c6f, 0x708477, 0x847a88],
];

export const LEGEND: [NodeCategory, string][] = [
  ["code", "code"],
  ["docs", "docs"],
  ["data", "data"],
  ["config", "config"],
  ["notebook", "notebook"],
  ["test", "tests"],
  ["class", "class"],
  ["function", "function"],
  ["constant", "constant"],
  ["outside", "generated / vendor"],
];

export function categoryColour(category: NodeCategory, theme: "dark" | "light"): number {
  return COLOURS[category][theme === "dark" ? 0 : 1];
}

/** How strongly a relationship that leaves its own repository or folder is drawn
 * (owner, 2026-11-17: "slightly faded, and only when the connecting graph is also being
 * displayed"). */
export const CROSSING_FADE = 0.4;

/** How strongly a declared link between two graphs is drawn. A declared link is something a person asserted, so
 * it is softer than a thread inside a graph but, unlike a crossing relationship, must stay readable along its
 * whole length: the fade away from the source end is what shows which way it points. */
export const DECLARED_FADE = 0.75;

/** The fade for one relationship, or null when it is not drawn. A relationship whose
 * end is not displayed is not drawn; one between two repositories (graphs or reviewed
 * folders) is drawn faded; one inside a repository is drawn as before. */
export function edgeFade(
  source: { repo_id?: string } | undefined,
  target: { repo_id?: string } | undefined,
  sourceShown: boolean,
  targetShown: boolean,
): number | null {
  if (!sourceShown || !targetShown) return null;
  const a = source?.repo_id ?? "",
    b = target?.repo_id ?? "";
  return a && b && a !== b ? CROSSING_FADE : 1;
}

/** The colour of one node. Containers keep a quiet tone that varies by parent, so
 * neighbouring folders remain distinguishable without competing with content. */
export function nodeColour(
  node: StyledNode | undefined,
  theme: "dark" | "light",
  parentKey = "",
): number {
  const category = node ? nodeCategory(node) : "container";
  if (category !== "container") return categoryColour(category, theme);
  const tones = CONTAINER_TONES[theme === "dark" ? 0 : 1];
  const hash = Array.from(parentKey).reduce((a, c) => a + c.charCodeAt(0), 0);
  return tones[hash % tones.length];
}
