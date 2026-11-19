// A colour for each graph, so which graph a shape belongs to can be told at a glance when several are
// shown together. It marks the graph's own enclosure; what is inside keeps the colour of its content
// (nodeStyle.ts). The set is reserved apart from the content hues and from the relationship colours
// (orange call/data, violet hierarchy, cyan rationale, gold bridge, red violation). Colours are assigned
// from the graph's id, so a graph keeps its colour from one visit to the next; a person can pick another.

export interface Accent {
  id: string;
  name: string;
  /** Hex for the dark and light themes. */
  dark: number;
  light: number;
}

export const ACCENTS: readonly Accent[] = [
  { id: "blue", name: "Blue", dark: 0x5b9bff, light: 0x2a5fc9 },
  { id: "green", name: "Green", dark: 0x5fc27e, light: 0x2a7d49 },
  { id: "magenta", name: "Magenta", dark: 0xd16be0, light: 0x9a2fa8 },
  { id: "rose", name: "Rose", dark: 0xe56b8a, light: 0xb02c55 },
  { id: "teal", name: "Teal", dark: 0x3fc1b5, light: 0x1c7f76 },
  { id: "indigo", name: "Indigo", dark: 0x8d86ff, light: 0x4540c9 },
  { id: "lime", name: "Lime", dark: 0xa8c93a, light: 0x6a8210 },
  { id: "sand", name: "Sand", dark: 0xd6b58a, light: 0x8a6a3c },
];

const hash = (text: string) => Array.from(text).reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);

/**
 * One accent per graph. A person's choice wins; the rest are spread over the set by id, in id order, so
 * the result does not depend on which graphs happen to be shown. Two graphs share a colour only when
 * there are more graphs than colours, or when a person picks the same one twice.
 */
export function assignAccents(graphIds: string[], chosen: Record<string, string> = {}): Record<string, Accent> {
  const out: Record<string, Accent> = {};
  const used = new Set<string>();
  for (const id of graphIds) {
    const pick = ACCENTS.find((a) => a.id === chosen[id]);
    if (pick) {
      out[id] = pick;
      used.add(pick.id);
    }
  }
  for (const id of [...graphIds].sort()) {
    if (out[id]) continue;
    const start = hash(id) % ACCENTS.length;
    let accent = ACCENTS[start];
    for (let i = 0; i < ACCENTS.length; i++) {
      const candidate = ACCENTS[(start + i) % ACCENTS.length];
      if (!used.has(candidate.id)) {
        accent = candidate;
        break;
      }
    }
    out[id] = accent;
    used.add(accent.id);
  }
  return out;
}

export const accentHex = (a: Accent, theme: "dark" | "light") => (theme === "dark" ? a.dark : a.light);
export const cssColour = (n: number) => `#${n.toString(16).padStart(6, "0")}`;

const KEY = "geographer.accents.v1";

/** A person's colour choices, kept for the browser. */
export function loadAccentChoices(): Record<string, string> {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) ?? "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed).filter(([, v]) => typeof v === "string" && ACCENTS.some((a) => a.id === v)),
    ) as Record<string, string>;
  } catch {
    return {};
  }
}

export function saveAccentChoices(choices: Record<string, string>) {
  try {
    localStorage.setItem(KEY, JSON.stringify(choices));
  } catch {
    /* a private window: the choice just is not kept */
  }
}
