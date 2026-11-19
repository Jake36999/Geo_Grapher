import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  ROLE_ORDER,
  activeOverrides,
  asciiMap,
  buildMap,
  filesLabel,
  roleLabel,
  tags,
  type MapNode,
  type MapPartition,
  type MapPlan,
  type RoleOverrides,
} from "./ingestMap";

export type SheetPlan = MapPlan & {
  archetype: string;
  excluded?: { rel: string; reason: string }[];
  manual_steps: { kind: string; dir: string; command: string }[];
};

/**
 * How a folder was read, as a wide sheet over the canvas. The tree is the working view (tick what
 * to bring in); the text version beside it is for pasting. It goes only as deep as the folder is
 * split into separate graphs. Suggestions are never decided for the person: every part is theirs to
 * tick, the role the scan guessed is theirs to correct, and a source without a licence file is labelled,
 * not blocked.
 */
export default function IngestSheet({
  plan,
  approved,
  roles,
  busy,
  onApprove,
  onRole,
  onApply,
  onClose,
}: {
  plan: SheetPlan;
  approved: Record<string, boolean>;
  /** The roles a person chose instead of the suggested ones. */
  roles: RoleOverrides;
  busy: boolean;
  onApprove: (key: string, on: boolean) => void;
  onRole: (key: string, role: string) => void;
  onApply: () => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [copied, setCopied] = useState("");
  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
    return () => {
      if (element?.open) element.close();
    };
  }, []);
  const text = asciiMap(plan, roles);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied("Copied the text map.");
    } catch {
      // No clipboard permission: select the text so the person can copy it themselves.
      const pre = document.getElementById("ingest-map-text");
      if (pre) {
        const range = document.createRange();
        range.selectNodeContents(pre);
        const selection = window.getSelection();
        selection?.removeAllRanges();
        selection?.addRange(range);
      }
      setCopied("Select and copy the text above.");
    }
  }
  const root = buildMap(plan, roles);
  const chosen = plan.partitions.filter((p) => approved[p.key]).length;
  const changed = Object.keys(activeOverrides(plan, roles, approved)).length;
  // In the page body, not inside the right panel: at narrow widths that panel is a drawer that can
  // be hidden, and a sheet that is mid-review must not go with it.
  return createPortal(
    <dialog
      ref={dialog}
      className="ingest-sheet"
      aria-labelledby="ingest-sheet-title"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === dialog.current) onClose(); // a press on the backdrop
      }}
    >
      <header className="ingest-sheet-head">
        <div>
          <h2 id="ingest-sheet-title">How this folder was read</h2>
          <p>
            <code>{plan.root}</code> · {plan.archetype.replace(/_/g, " ")} · {plan.partitions.length} part
            {plan.partitions.length === 1 ? "" : "s"}
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close without ingesting">
          ×
        </button>
      </header>
      <p className="ingest-policy">
        Each part becomes its own graph, so you can keep them apart. Tick what to bring in. A source with no
        licence file is still brought in and copied; it is cited and kept out of anything published as our own
        work. If the scan guessed a role wrong, change it in the list: the part is read the same way, and only how
        it is labelled changes.
      </p>
      <ul className="folder-map" aria-label="Folder map">
        <MapRow node={root} approved={approved} roles={roles} busy={busy} onApprove={onApprove} onRole={onRole} top />
      </ul>
      {plan.manual_steps.length > 0 && (
        <p className="ingest-note">
          {plan.manual_steps.length} paper folder(s) need the paper pipeline; they are not ingested here.
        </p>
      )}
      {!!plan.excluded?.length && (
        <p className="ingest-note">
          {plan.excluded.length} folder(s) and file(s) are left out automatically (caches, builds, backups,
          binaries, empty folders).
        </p>
      )}
      <details className="ascii-map">
        <summary>Text version</summary>
        <pre id="ingest-map-text" aria-label="Folder map as text" tabIndex={0}>
          {text}
        </pre>
        <button type="button" onClick={() => void copy()}>
          Copy as ASCII
        </button>{" "}
        <span role="status">{copied}</span>
      </details>
      <footer className="ingest-sheet-actions">
        {changed > 0 && (
          <span className="ingest-changed" role="status">
            {changed} role{changed === 1 ? "" : "s"} changed by you
          </span>
        )}
        <button type="button" onClick={onClose}>
          Cancel
        </button>
        <button type="button" className="primary" disabled={busy || chosen === 0} onClick={onApply}>
          {busy ? "Ingesting…" : `Ingest ${chosen} selected part${chosen === 1 ? "" : "s"}`}
        </button>
      </footer>
    </dialog>,
    document.body,
  );
}

function MapRow({
  node,
  approved,
  roles,
  busy,
  onApprove,
  onRole,
  top = false,
}: {
  node: MapNode;
  approved: Record<string, boolean>;
  roles: RoleOverrides;
  busy: boolean;
  onApprove: (key: string, on: boolean) => void;
  onRole: (key: string, role: string) => void;
  top?: boolean;
}) {
  const part = node.partition;
  return (
    <li>
      <div className={`map-row${part ? "" : " map-row-plain"}`}>
        {part ? (
          <input
            type="checkbox"
            aria-label={top ? `Ingest the rest of ${node.name} (everything not in a folder below)` : `Ingest ${node.path}`}
            checked={!!approved[part.key]}
            disabled={busy}
            onChange={(e) => onApprove(part.key, e.target.checked)}
          />
        ) : (
          <span className="map-spacer" aria-hidden="true" />
        )}
        <span className="map-name">{node.name}/</span>
        {part && (
          <PartInfo
            part={part}
            top={top}
            label={top ? node.name : node.path}
            disabled={busy}
            onRole={(role) => onRole(part.key, role)}
          />
        )}
      </div>
      {part?.suggestion?.reasons?.length ? (
        <p className="map-reasons">{part.suggestion.reasons.join("; ")}</p>
      ) : null}
      {node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <MapRow
              key={child.path}
              node={child}
              approved={approved}
              roles={roles}
              busy={busy}
              onApprove={onApprove}
              onRole={onRole}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function PartInfo({
  part,
  top,
  label,
  disabled,
  onRole,
}: {
  part: MapPartition;
  top: boolean;
  label: string;
  disabled: boolean;
  onRole: (role: string) => void;
}) {
  // The first tag is the role: it is the one thing a person may correct, so it is the control.
  const [, ...rest] = tags(part);
  return (
    <>
      <span className="map-tags">
        <select
          className="map-role"
          aria-label={`Role of ${label}`}
          value={part.role}
          disabled={disabled}
          onChange={(e) => onRole(e.target.value)}
        >
          {ROLE_ORDER.map((role) => (
            <option key={role} value={role}>
              {roleLabel(role)}
            </option>
          ))}
        </select>
        {rest.map((t) => (
          <span
            key={t}
            className={`map-tag${t.startsWith("cited") ? " map-tag-cited" : ""}${t === "no licence file" ? " map-tag-nolicence" : ""}`}
          >
            {t}
          </span>
        ))}
      </span>
      <span className="map-count">
        {filesLabel(part)}
        {top ? " (the rest)" : ""}
      </span>
    </>
  );
}
