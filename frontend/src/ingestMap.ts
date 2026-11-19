// The folder map of an ingest preview: how a directory was read, down to the depth at which it
// is split into separate graphs (the partitions) and no deeper. Pure functions, so the tree on
// screen and the pasteable text share one source.

export type Suggestion = {
  purpose?: string;
  reasons?: string[];
  accepted?: boolean;
  /** "reference": someone else's work, cited and never published as our own. A label, not a gate. */
  publication?: "own" | "reference";
  licence?: "found" | "none_found" | "not_applicable";
  licence_files?: number;
};
export type MapPartition = {
  key: string;
  role: string;
  subtrees: string[];
  file_counts: Record<string, number>;
  bytes: number;
  suggestion?: Suggestion;
};
/** What each role means for publication and licence labels. It comes from the scan (one source of truth). */
export type RolePolicy = Record<string, { publication: "own" | "reference"; licence_applicable: boolean }>;
export type MapPlan = { root: string; partitions: MapPartition[]; role_policy?: RolePolicy };
/** A person's corrections: part key to the role chosen instead of the suggested one. */
export type RoleOverrides = Record<string, string>;
export type MapNode = {
  name: string;
  path: string;
  partition?: MapPartition;
  children: MapNode[];
};

const ROLE_LABEL: Record<string, string> = {
  current: "own",
  legacy: "own · legacy",
  docs: "own · docs",
  transcripts: "logs and transcripts",
  data: "data",
  third_party: "third-party",
  external_reference: "external reference",
  research_docs: "research papers",
};

export const roleLabel = (role: string) => ROLE_LABEL[role] ?? role.replace(/_/g, " ");

/** The roles a part can be given, in the order they are offered. */
export const ROLE_ORDER = [
  "current",
  "legacy",
  "docs",
  "transcripts",
  "data",
  "third_party",
  "external_reference",
  "research_docs",
] as const;

/** The part as it will be treated: the chosen role when there is one, with the publication and licence
 * labels that role implies. The suggestion's own wording (reasons) is replaced by a plain statement that
 * a person chose it. A role the scan did not describe (no policy) is left as the scan reported it. */
export function withRole(p: MapPartition, role: string | undefined, policy?: RolePolicy): MapPartition {
  if (!role || role === p.role) return p;
  const rule = policy?.[role];
  const files = p.suggestion?.licence_files ?? 0;
  return {
    ...p,
    role,
    suggestion: {
      ...p.suggestion,
      publication: rule?.publication ?? p.suggestion?.publication,
      licence: rule ? (rule.licence_applicable ? (files ? "found" : "none_found") : "not_applicable") : p.suggestion?.licence,
      reasons: [`you chose “${roleLabel(role)}”; the scan suggested “${roleLabel(p.role)}”`],
    },
  };
}

/** Only the corrections that differ from the suggestion, for the parts that will be ingested. */
export function activeOverrides(plan: MapPlan, roles: RoleOverrides, approved: Record<string, boolean>): RoleOverrides {
  const out: RoleOverrides = {};
  for (const p of plan.partitions) if (approved[p.key] && roles[p.key] && roles[p.key] !== p.role) out[p.key] = roles[p.key];
  return out;
}

export const fileTotal = (p: MapPartition) => Object.values(p.file_counts).reduce((a, b) => a + b, 0);

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

/** Short tags for one part: what it is, and how it is treated when published. */
export function tags(p: MapPartition): string[] {
  const out = [roleLabel(p.role)];
  const s = p.suggestion;
  if (s?.publication === "reference") out.push("cited, not published as our own");
  if (s?.licence === "none_found") out.push("no licence file");
  else if (s?.licence === "found") out.push("licence file present");
  return out;
}

const baseName = (path: string) => path.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || path;

/** The root, then each partition at its own path. A folder that only leads to a partition is a plain node.
 * `roles` are a person's corrections; the map shows each part as it will be treated. */
export function buildMap(plan: MapPlan, roles: RoleOverrides = {}): MapNode {
  const shown = (p: MapPartition) => withRole(p, roles[p.key], plan.role_policy);
  const residual = plan.partitions.find((p) => p.key === "residual");
  const root: MapNode = {
    name: baseName(plan.root),
    path: "",
    partition: residual && shown(residual),
    children: [],
  };
  for (const original of plan.partitions) {
    if (original.key === "residual" || !original.subtrees.length) continue;
    const part = shown(original);
    let node = root;
    let path = "";
    for (const segment of part.subtrees[0].split("/")) {
      path = path ? `${path}/${segment}` : segment;
      let child = node.children.find((c) => c.name === segment);
      if (!child) {
        child = { name: segment, path, children: [] };
        node.children.push(child);
      }
      node = child;
    }
    node.partition = part;
  }
  const sort = (n: MapNode) => {
    n.children.sort((a, b) => a.name.localeCompare(b.name));
    n.children.forEach(sort);
  };
  sort(root);
  return root;
}

export const filesLabel = (p: MapPartition) => `${fileTotal(p)} file${fileTotal(p) === 1 ? "" : "s"} · ${formatBytes(p.bytes)}`;
const counts = (p?: MapPartition) => (p ? filesLabel(p) : "");

/** The same tree as monospace text, for pasting into a note or an issue. */
export function asciiMap(plan: MapPlan, roles: RoleOverrides = {}): string {
  const root = buildMap(plan, roles);
  const rows: { left: string; label: string; count: string }[] = [];
  const walk = (node: MapNode, prefix: string, last: boolean, top: boolean) => {
    const left = top ? `${node.name}/` : `${prefix}${last ? "└─ " : "├─ "}${node.name}/`;
    rows.push({ left, label: node.partition ? tags(node.partition).join(" · ") : "", count: counts(node.partition) });
    const next = top ? "" : prefix + (last ? "   " : "│  ");
    node.children.forEach((child, i) => walk(child, next, i === node.children.length - 1, false));
  };
  walk(root, "", true, true);
  const leftWidth = Math.min(Math.max(...rows.map((r) => r.left.length)) + 2, 56);
  const labelWidth = Math.max(...rows.map((r) => r.label.length));
  return rows
    .map((r) => `${r.left.padEnd(leftWidth)}${r.label.padEnd(labelWidth)}  ${r.count}`.trimEnd())
    .join("\n");
}
