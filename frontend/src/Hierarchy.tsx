import { useEffect, useRef, useState } from "react";
import { json, shortName, type Node, type Snapshot } from "./api";

interface Props {
  snapshot: Snapshot;
  selected: string;
  onSelect: (node: Node) => void;
  onEnter: (id: string) => void;
  onNodes: (nodes: Node[]) => void;
  external: boolean;
  documents: boolean;
}
export default function Hierarchy({
  snapshot,
  selected,
  onSelect,
  onEnter,
  onNodes,
  external,
  documents,
}: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(
    new Set(snapshot.repositories.map((n) => n.id)),
  );
  const [children, setChildren] = useState<Record<string, Node[]>>({});
  const [after, setAfter] = useState<Record<string, string | null>>({});
  const [loading, setLoading] = useState<Set<string>>(new Set());
  const [failures, setFailures] = useState<
    Record<string, { message: string; more: boolean }>
  >({});
  const abort = useRef(new AbortController());
  const requested = useRef(new Set<string>()),
    childrenRef = useRef(children);
  childrenRef.current = children;
  useEffect(() => {
    abort.current.abort();
    abort.current = new AbortController();
    requested.current.clear();
    setChildren({});
    setAfter({});
    setFailures({});
    setLoading(new Set());
    setExpanded(new Set(snapshot.repositories.map((n) => n.id)));
    return () => abort.current.abort();
  }, [snapshot.snapshot_id, external, documents]);
  async function load(id: string, more = false) {
    const key = id + ":" + (more ? (after[id] ?? "") : "start");
    if (requested.current.has(key)) return;
    requested.current.add(key);
    const signal = abort.current.signal;
    setFailures((old) => {
      const next = { ...old };
      delete next[id];
      return next;
    });
    setLoading((old) => new Set(old).add(id));
    try {
      const params = new URLSearchParams({
        snapshot_id: snapshot.snapshot_id,
        parent_id: id,
        limit: "100",
        external: String(external),
        documents: String(documents),
      });
      if (more && after[id]) params.set("after", after[id]!);
      const response = await json<{ nodes: Node[]; next_after: string | null }>(
        "/api/v1/hierarchy?" + params,
        undefined,
        signal,
      );
      if (signal.aborted) return;
      onNodes(response.nodes);
      setChildren((old) => ({
        ...old,
        [id]: more ? [...(old[id] ?? []), ...response.nodes] : response.nodes,
      }));
      setAfter((old) => ({ ...old, [id]: response.next_after }));
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        if (signal.aborted) return;
        setFailures((old) => ({
          ...old,
          [id]: { message: (e as Error).message, more },
        }));
        requested.current.delete(key);
      }
    } finally {
      if (!signal.aborted)
        setLoading((old) => {
          const next = new Set(old);
          next.delete(id);
          return next;
        });
    }
  }
  useEffect(() => {
    for (const id of expanded) if (!children[id]) void load(id);
  }, [expanded, children, snapshot.snapshot_id, external, documents]);
  function toggle(id: string) {
    setExpanded((old) => {
      const next = new Set(old);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function keyboard(event: React.KeyboardEvent<HTMLButtonElement>, node: Node) {
    const buttons = Array.from(
      event.currentTarget
        .closest("nav")!
        .querySelectorAll<HTMLButtonElement>(".node-select"),
    );
    const index = buttons.indexOf(event.currentTarget);
    if (event.key === "ArrowDown") {
      event.preventDefault();
      buttons[Math.min(index + 1, buttons.length - 1)]?.focus();
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      buttons[Math.max(0, index - 1)]?.focus();
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      if (!expanded.has(node.id)) toggle(node.id);
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      if (expanded.has(node.id)) toggle(node.id);
    }
    if (event.key === "Enter" && event.shiftKey) {
      event.preventDefault();
      onEnter(node.id);
    }
  }
  function rows(nodes: Node[], depth = 0): React.ReactNode {
    return (
      <ul className={depth ? "tree-children" : "tree-root"}>
        {nodes.map((node) => {
          const open = expanded.has(node.id),
            canExpand =
              node.child_count === undefined
                ? [
                    "repository",
                    "directory",
                    "package",
                    "file",
                    "class",
                    "function",
                    "method",
                  ].includes(node.kind)
                : node.child_count > 0;
          return (
            <li key={node.id}>
              <div
                className={`tree-row ${selected === node.id ? "is-selected" : ""}`}
              >
                {canExpand ? (
                  <button
                    className="tree-toggle icon-button"
                    aria-label={`${open ? "Collapse" : "Expand"} ${shortName(node)}`}
                    aria-expanded={open}
                    onClick={() => toggle(node.id)}
                  >
                    {open ? "−" : "+"}
                  </button>
                ) : (
                  <span className="tree-spacer" />
                )}
                <button
                  className="node-select"
                  title={node.qualified_name}
                  aria-current={selected === node.id ? "true" : undefined}
                  onClick={() => onSelect(node)}
                  onDoubleClick={() => onEnter(node.id)}
                  onKeyDown={(e) => keyboard(e, node)}
                >
                  <span
                    className={`kind-mark kind-${node.kind}`}
                    aria-hidden="true"
                  >
                    {node.kind === "directory" || node.kind === "repository"
                      ? "▱"
                      : node.kind === "class"
                        ? "◇"
                        : node.kind === "function" || node.kind === "method"
                          ? "ƒ"
                          : "·"}
                  </span>
                  <span className="tree-name">{shortName(node)}</span>
                  {node.flags.is_test && (
                    <span className="tiny-badge">test</span>
                  )}
                </button>
              </div>
              {open && canExpand && (
                <>
                  {loading.has(node.id) && (
                    <p className="tree-message">Loading…</p>
                  )}
                  {failures[node.id] && (
                    <div className="tree-message">
                      <p role="status" id={"tree-error-" + node.id}>
                        {failures[node.id].message}
                      </p>
                      <button
                        aria-describedby={"tree-error-" + node.id}
                        onClick={() =>
                          void load(node.id, failures[node.id].more)
                        }
                      >
                        Retry hierarchy
                      </button>
                    </div>
                  )}
                  {children[node.id] && rows(children[node.id], depth + 1)}
                  {after[node.id] && (
                    <button
                      className="tree-more text-button"
                      onClick={() => load(node.id, true)}
                    >
                      Load more children
                    </button>
                  )}
                  {children[node.id]?.length === 0 && !loading.has(node.id) && (
                    <p className="tree-message">
                      No children in this hierarchy filter
                    </p>
                  )}
                </>
              )}
            </li>
          );
        })}
      </ul>
    );
  }
  return (
    <nav className="hierarchy-tree" aria-label="Repository hierarchy">
      {rows(snapshot.repositories)}
    </nav>
  );
}
