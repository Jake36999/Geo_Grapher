import type { QIReport } from "../../contracts/v1.1/geographer.wire";

const REQUIREMENTS = "Requires atomic grouping and exact static relationships.";

export type QiMode = "off" | "helper_tree_balls_v1" | "directed-helper-condensation-v1";
type Group = { id: string; qualified_name: string; display_label?: string | null; member_count: number; membership_handle: string | null };

export default function QiControl({ mode, enabled, report, groups, onChange, onExpand }: {
  mode: QiMode; enabled: boolean; report?: QIReport; groups: Group[];
  onChange: (mode: QiMode) => void; onExpand: (id: string) => void;
}) {
  return <section className="qi-control" aria-label="QI grouping">
    <label>QI <select aria-label="QI algorithm" value={mode} disabled={!enabled}
      title={!enabled ? REQUIREMENTS : undefined}
      aria-describedby={!enabled ? "qi-requirements" : undefined}
      onChange={e => onChange(e.target.value as QiMode)}>
      <option value="off">Off</option><option value="helper_tree_balls_v1">Helper balls</option>
      <option value="directed-helper-condensation-v1">Directed</option>
    </select></label>
    {!enabled && <span id="qi-requirements" className="sr-only">{REQUIREMENTS}</span>}
    {enabled && mode !== "off" && report && <>
      <span role="status" data-testid="qi-certificate">{report.group_count} blocks · {report.directed_reachability_preserved
        ? "reachability preserved (existential)" : `undirected hop bound A=${report.A}, B=${report.B}`}</span>
      <details className="qi-blocks"><summary>Visible QI blocks ({groups.length})</summary>
        <ul>{groups.map((g, i) => <li key={g.id}><button data-qi-group={g.id}
          aria-label={`Expand QI block ${i + 1}`} disabled={!g.membership_handle} onClick={() => onExpand(g.id)}>
          {g.display_label || g.qualified_name} ({g.member_count})</button></li>)}</ul>
      </details>
    </>}
  </section>;
}
