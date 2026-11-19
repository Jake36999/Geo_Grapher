import { useEffect, useRef } from "react";

/** A panel the page keeps in its own state (not a `<details>`), so the hook can close it. */
export type OpenPanel = { open: boolean; close: () => void };

function popovers(): HTMLDetailsElement[] {
  return [...document.querySelectorAll<HTMLDetailsElement>("details.popover[open]")];
}

/**
 * One way to dismiss every floating panel: Escape closes the top-most one (and gives the focus
 * back to its trigger), and a press outside closes an open `<details class="popover">`.
 *
 * A `<details>` has no dismiss behaviour of its own, so Scope & filters and Graphs stayed open
 * until their trigger was found again, and sat over what a person was trying to reach.
 * `panels` are panels held in state (Coverage, Configure rules): Escape closes them too, but a
 * press outside does not, because their trigger is outside them and would reopen what it closed.
 */
export function useDismissPopovers(panels: OpenPanel[] = []): void {
  const latest = useRef(panels);
  latest.current = panels;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented || e.isComposing) return;
      const open = popovers();
      if (open.length) {
        // The one holding the focus, else the last opened in the page.
        const holding = open.filter((d) => d.contains(document.activeElement));
        const target = (holding.length ? holding : open).at(-1)!;
        const hadFocus = target.contains(document.activeElement);
        target.open = false;
        if (hadFocus) target.querySelector<HTMLElement>(":scope > summary")?.focus();
        e.preventDefault();
        return;
      }
      const panel = latest.current.filter((p) => p.open).at(-1);
      if (panel) {
        panel.close();
        e.preventDefault();
      }
    };
    const onPress = (e: PointerEvent) => {
      for (const d of popovers()) if (!d.contains(e.target as Node)) d.open = false;
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPress, true);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPress, true);
    };
  }, []);
}
