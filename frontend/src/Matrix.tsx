import { useEffect, useMemo, useState } from "react";
import type {
  RelationshipSummary,
  ViewportFrameData,
} from "../../contracts/geographer.wire";
import { shortName, type Node } from "./api";
function displayName(node: Node) {
  const name = shortName(node),
    prefix = node.qualified_name.split(" · ")[0];
  if (node.id.startsWith('["g_') && node.kind === "repository")
    return node.qualified_name;
  return node.id.startsWith('["g_') &&
    node.qualified_name.includes(" · ") &&
    name !== prefix
    ? `${prefix} · ${name}`
    : name;
}
export type MatrixFrame = Pick<
  ViewportFrameData,
  "nodes" | "relationships" | "spheres" | "partition_digest"
>;

export default function Matrix({
  frame,
  onRelationship,
  onSelect,
  violations = [],
}: {
  frame: MatrixFrame;
  onRelationship: (ids: string[]) => void;
  onSelect: (id: string) => void;
  violations?: string[];
}) {
  const [rowPage, setRowPage] = useState(0),
    [colPage, setColPage] = useState(0);
  useEffect(() => {
    setRowPage(0);
    setColPage(0);
  }, [frame.partition_digest]);
  const representatives = new Set(
    frame.spheres
      .filter((s) => s.role === "representative")
      .map((s) => s.node_id),
  );
  const nodes = useMemo(
    () =>
      frame.nodes
        .filter((n) => representatives.has(n.id))
        .sort((a, b) => a.qualified_name.localeCompare(b.qualified_name)),
    [frame],
  );
  const rows = nodes.slice(rowPage * 10, rowPage * 10 + 10),
    cols = nodes.slice(colPage * 10, colPage * 10 + 10);
  const cells = new Map<string, RelationshipSummary[]>();
  for (const relation of frame.relationships) {
    const key = relation.source + "|" + relation.target;
    cells.set(key, [...(cells.get(key) ?? []), relation]);
  }
  return (
    <div className="matrix-view">
      <div className="matrix-paging">
        <div>
          <strong>Dependency matrix</strong>
          <p>
            Rows are sources; columns are targets. Select a populated cell to
            inspect its evidence.
          </p>
        </div>
        <div className="paging-buttons">
          <button
            disabled={!rowPage}
            onClick={() => setRowPage((p) => p - 1)}
            aria-label="Previous matrix rows"
          >
            ↑ Rows
          </button>
          <button
            disabled={(rowPage + 1) * 10 >= nodes.length}
            onClick={() => setRowPage((p) => p + 1)}
            aria-label="Next matrix rows"
          >
            ↓ Rows
          </button>
          <button
            disabled={!colPage}
            onClick={() => setColPage((p) => p - 1)}
            aria-label="Previous matrix columns"
          >
            ← Columns
          </button>
          <button
            disabled={(colPage + 1) * 10 >= nodes.length}
            onClick={() => setColPage((p) => p + 1)}
            aria-label="Next matrix columns"
          >
            Columns →
          </button>
        </div>
      </div>
      <div
        className="matrix-scroll"
        tabIndex={0}
        aria-label="Scrollable dependency matrix"
      >
        <table>
          <caption className="sr-only">
            Directed dependency counts between the currently displayed groups
          </caption>
          <thead>
            <tr>
              <th scope="col">Source / target</th>
              {cols.map((n) => (
                <th scope="col" key={n.id}>
                  <button
                    className="text-button"
                    title={n.qualified_name}
                    onClick={() => onSelect(n.id)}
                  >
                    {displayName(n)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((source) => (
              <tr key={source.id}>
                <th scope="row">
                  <button
                    className="text-button"
                    title={source.qualified_name}
                    onClick={() => onSelect(source.id)}
                  >
                    {displayName(source)}
                  </button>
                </th>
                {cols.map((target) => {
                  const relations =
                      cells.get(source.id + "|" + target.id) ?? [],
                    count = relations.reduce((a, r) => a + r.witness_count, 0);
                  return (
                    <td key={target.id}>
                      {count ? (
                        <button
                          className="matrix-cell populated"
                          onClick={() =>
                            onRelationship(relations.map((r) => r.id))
                          }
                          aria-label={`${displayName(source)} to ${displayName(target)}: ${count} witnesses`}
                          title={relations
                            .map(
                              (r) =>
                                `${r.subtype} · ${r.family} · ${r.resolution_status} · ${r.aggregated_weight} ${r.weight_unit}${violations.includes(r.id) ? " · rule violation (warning)" : ""}`,
                            )
                            .join("; ")}
                          data-warning={relations.some((r) =>
                            violations.includes(r.id),
                          )}
                        >
                          {count.toLocaleString()}
                        </button>
                      ) : (
                        <span
                          className="matrix-zero"
                          aria-label="No relationship in this result"
                        >
                          ·
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="view-note">
        Internal relationships are retained on the diagonal. Counts include only
        the current query result; omitted bundles remain available through
        evidence queries.
      </p>
    </div>
  );
}

export function EntityList({
  frame,
  selected,
  onSelect,
  onEnter,
}: {
  frame: MatrixFrame;
  selected: string;
  onSelect: (id: string) => void;
  onEnter: (id: string) => void;
}) {
  const ids = new Set(
    frame.spheres
      .filter((s) => s.role === "representative")
      .map((s) => s.node_id),
  );
  return (
    <div className="entity-list">
      <h2>Visible architecture groups</h2>
      <p>
        These groups and relationships are synchronised with the spatial view.
      </p>
      <ul>
        {frame.nodes
          .filter((n) => ids.has(n.id))
          .sort((a, b) => a.qualified_name.localeCompare(b.qualified_name))
          .map((n) => (
            <li key={n.id} className={selected === n.id ? "is-selected" : ""}>
              <button
                className="list-entity"
                onClick={() => onSelect(n.id)}
                aria-current={selected === n.id ? "true" : undefined}
              >
                <span className="kind-badge">
                  {n.kind.replaceAll("_", " ")}
                </span>
                <strong>{displayName(n)}</strong>
                <span>{n.member_count.toLocaleString()} members</span>
              </button>
              <button
                disabled={n.entity_id === null}
                aria-label={`Enter ${displayName(n)}`}
                onClick={() => onEnter(n.id)}
              >
                Enter →
              </button>
            </li>
          ))}
      </ul>
    </div>
  );
}
