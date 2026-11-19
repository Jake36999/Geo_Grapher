// Plain-language wording for the Build tab's operators. Pure functions, so the words a person reads
// are tested apart from the panels that show them.
import type { CompareResult, DerivePreview } from "./api";

const plural = (n: number, one: string, many = one + "s") => `${n.toLocaleString("en")} ${n === 1 ? one : many}`;

/** One sentence on what a keep-only or remove would do, from the counts the server gave. */
export function previewSentence(p: DerivePreview): string {
  const { files: f, entities: e, relationships: r } = p;
  if (f.total === 0) return "The source graph has no files to count.";
  if (p.mode === "keep") {
    if (f.kept === 0) return "None of the selected paths holds a file, so nothing would be kept.";
    if (f.removed === 0) return "The selection covers every file, so keeping only it would change nothing.";
    return (
      `Keeps ${f.kept.toLocaleString("en")} of ${plural(f.total, "file")} and ` +
      `${e.kept.toLocaleString("en")} of ${plural(e.total, "item")}. ` +
      `Relationships across the cut would be dropped: ${r.dropped.toLocaleString("en")}.`
    );
  }
  if (f.removed === 0) return "None of the selected paths holds a file, so nothing would be removed.";
  if (f.kept === 0) return "That would remove every file, so nothing would be left.";
  return (
    `Removes ${f.removed.toLocaleString("en")} of ${plural(f.total, "file")} and ` +
    `${e.removed.toLocaleString("en")} of ${plural(e.total, "item")}. ` +
    `Relationships dropped with them: ${r.dropped.toLocaleString("en")}.`
  );
}

/** True when the preview says the new graph would be empty or unchanged, so there is nothing to make. */
export function previewMakesNothing(p: DerivePreview): boolean {
  return p.files.kept === 0 || p.files.removed === 0;
}

/** How a function or class in one graph matches one in the other, in words a person would use. */
export const MATCH_LABEL: Record<string, string> = {
  EXACT_AST_SURVIVOR: "Identical",
  CONTRACT_PRESERVING_REFACTOR: "Same contract, rewritten",
  TOPOLOGICAL_ROLE_ANALOG: "Same place in the graph",
  SIGNATURE_OR_GUARD_DRIFT: "Same name, changed",
};
export const MATCH_ORDER = Object.keys(MATCH_LABEL);

const CYCLE_LABEL: Record<string, string> = {
  CYCLE_DISSOLVED: "dissolved",
  CYCLE_INTRODUCED: "new",
  COUPLING_REDUCED: "less tangled",
  COUPLING_INCREASED: "more tangled",
  INVARIANT: "unchanged",
};

export type CompareRow = { key: string; label: string; count: number };

/** The counts as rows, in the order a person reads them: what matches, then what is only on one side. */
export function compareRows(c: CompareResult, a: string, b: string): CompareRow[] {
  const rows: CompareRow[] = MATCH_ORDER.map((key) => ({ key, label: MATCH_LABEL[key], count: c.classes[key] ?? 0 }));
  rows.push({ key: "only_a", label: `Only in ${a}`, count: c.only_a.count });
  rows.push({ key: "only_b", label: `Only in ${b}`, count: c.only_b.count });
  return rows;
}

export function compareHeadline(c: CompareResult, a: string, b: string): string {
  const total = Math.max(c.compared.a, c.compared.b);
  if (total === 0) return "Neither graph has functions, methods or classes to compare.";
  return (
    `${plural(c.matched, "item")} in ${a} ${c.matched === 1 ? "has" : "have"} a counterpart in ${b}; ` +
    `${c.only_a.count.toLocaleString("en")} appear only in ${a} and ${c.only_b.count.toLocaleString("en")} only in ${b}.`
  );
}

/** Dependency-loop changes, or "" when neither graph has loops to compare. */
export function cycleSentence(c: CompareResult): string {
  const parts = Object.entries(c.cycles).map(([state, n]) => `${n} ${CYCLE_LABEL[state] ?? state.toLowerCase()}`);
  return parts.length ? `Dependency loops: ${parts.join(", ")}.` : "";
}

/** A short form of a bridge endpoint for a list: long entity ids keep their start and end. */
export function shortRef(ref: string): string {
  if (ref.length <= 36) return ref;
  return `${ref.slice(0, 20)}…${ref.slice(-10)}`;
}

/** "reference" -> "reference", "concept_equivalence" -> "concept equivalence". */
export const kindLabel = (kind: string) => kind.replace(/_/g, " ");

const LINK_STATE_LABEL: Record<string, string> = {
  accepted: "in force",
  provisional_reanchored: "moved with a re-read",
  suspect_stale: "may be out of date",
  demoted_contestable: "contested",
};
/** A link's lineage state in words: whether what it points at has changed since it was declared. */
export const linkStateLabel = (state: string) => LINK_STATE_LABEL[state] ?? state.replace(/_/g, " ");
