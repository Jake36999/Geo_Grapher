// The names people see for graphs and repositories (owner, 2026-11-17: node names looked
// wrong - six graphs all read "Nonlinear Field Lab-quantule_map…", and a reviewed folder's
// repository showed its internal id "g_…:c695…").

let libraryName = "";
/** The owning library's name (from /api/workspace/context), so graph labels can drop it. */
export function setLibraryName(name: string | null | undefined): void {
  libraryName = name ?? "";
}

export const RAW_ID = /^g_[0-9a-f]{24}(:[0-9a-f]+)?$/;

/** A graph or repository label without the library name every label in it starts with
 * ("Nonlinear Field Lab-quantule_mapper-docs" -> "quantule_mapper-docs"), shortened in the
 * middle so the part that tells graphs apart stays visible. */
export function compactLabel(label: string, max = 34): string {
  let text = label.trim();
  for (const sep of ["-", " · ", " "])
    if (libraryName && text.startsWith(libraryName + sep) && text.length > libraryName.length + sep.length) {
      text = text.slice(libraryName.length + sep.length);
      break;
    }
  if (text.length <= max) return text;
  const head = Math.ceil((max - 1) * 0.4);
  return `${text.slice(0, head)}…${text.slice(text.length - (max - 1 - head))}`;
}

/** The name of a repository node. Composition writes "graph label · own name"; a reviewed
 * folder's own name is an internal id, never shown. With nothing better (enrichment not
 * finished), the active graph's label, then the word "Repository". */
export function repositoryLabel(
  qualifiedName: string,
  repoId: string,
  active: { label: string | null; basePath: string },
): string {
  const own = qualifiedName ?? "";
  const graphPart = own.includes(" · ") ? own.split(" · ")[0] : "";
  const member = own.includes(" · ") ? own.slice(own.indexOf(" · ") + 3) : "";
  if (graphPart && !RAW_ID.test(graphPart))
    return member && !RAW_ID.test(member) ? `${compactLabel(graphPart, 22)} · ${member}` : compactLabel(graphPart);
  if (own && !RAW_ID.test(own)) return compactLabel(own);
  const graph = (repoId ?? "").split(":")[0];
  if (active.label && graph && active.basePath.includes(graph)) return compactLabel(active.label);
  return "Repository";
}

/** A node's own name, without the "graph label · " the composed view puts in front. */
export function ownName(qualifiedName: string): string {
  const at = qualifiedName.indexOf(" · ");
  return at >= 0 ? qualifiedName.slice(at + 3) : qualifiedName;
}

/** A member folder's short name: its last part, or the last two when the last is generic
 * ("docs", "data", "papers" ...), so sibling members stay distinguishable. */
export function memberFolder(root: string): string {
  const parts = root.split(/[\\/]+/).filter(Boolean);
  const last = parts.at(-1) ?? root;
  const generic = /^(docs?|data|papers?|files|logs?|src|research|external[_ ]?research|reports?)$/i;
  return generic.test(last) && parts.length > 1 ? `${parts.at(-2)}/${last}` : last;
}
