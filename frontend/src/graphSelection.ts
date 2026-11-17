// Which graphs the workspace shows (owner, 2026-11-17: RAM sat at 70-80%). Every loaded graph is
// held in server memory (about 12-14 KB per entity), so the server keeps at most `max_graphs`
// resident (graph_router.DEFAULT_MAX_LOADED) and reports the number in /api/workspace/context.
// The picker, the saved selection and the first visit all follow that number.

/** Used until the server answers; matches graph_router.DEFAULT_MAX_LOADED. */
export const DEFAULT_MAX_GRAPHS = 3;

export interface InitialSelection {
  /** Graph ids that can be shown, in catalogue order. */
  available: string[];
  /** The graph the workspace opens on (requested, primary, or the first available). */
  first: string | undefined;
  /** The ids saved from the last visit, or null when there is none. */
  saved: string[] | null;
  max: number;
  /** The person asked for `first` by address, or it is the library's primary graph. */
  forceFirst?: boolean;
}

/**
 * A first visit shows every graph of a small library (up to the cap), and only the first graph of a
 * larger one: opening all of a 6- or 16-graph library at once was what filled RAM. A returning
 * visit restores what was saved, within the cap.
 */
export function initialSelection(o: InitialSelection): string[] {
  const known = new Set(o.available);
  // A saved list longer than the cap can only date from before the cap existed, when the default
  // was "every graph". Clipping it would pick graphs nobody chose (often the largest), so it is
  // treated as no saved selection.
  const saved = o.saved && o.saved.length > o.max ? null : o.saved;
  // Someone who unchecked every graph and reloaded keeps that choice.
  if (saved && saved.length === 0) return [];
  let ids = (saved ?? []).filter((id, i, all) => known.has(id) && all.indexOf(id) === i);
  if (!ids.length) {
    if (!o.first) return [];
    return o.available.length <= o.max
      ? [o.first, ...o.available.filter((id) => id !== o.first)]
      : [o.first];
  }
  if (o.forceFirst && o.first && !ids.includes(o.first))
    ids = [o.first, ...ids];
  return ids.slice(0, o.max);
}

/** Adds a graph unless the cap is reached; `full` says the refusal was the cap. */
export function addGraph(
  ids: string[],
  id: string,
  max: number,
): { ids: string[]; full: boolean } {
  if (ids.includes(id)) return { ids, full: false };
  if (ids.length >= max) return { ids, full: true };
  return { ids: [...ids, id], full: false };
}
