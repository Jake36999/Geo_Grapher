import type { Dispatch, SetStateAction } from "react";
import type { Accent } from "./accents";
import { compareGraphs, type CompareItem, type CompareResult } from "./api";
import { MATCH_LABEL, MATCH_ORDER, compareHeadline, compareRows, cycleSentence } from "./buildOps";
import GraphSwatch from "./GraphSwatch";

export type CompareState = { a: string; b: string; result?: CompareResult; busy: boolean; error: string };
export const emptyCompare: CompareState = { a: "", b: "", busy: false, error: "" };

const where = (i: CompareItem) => (i.rel_path ? `${i.rel_path}${i.line ? `:${i.line}` : ""}` : "");

/**
 * Compare two of the checked graphs: what matches, and what is only on one side. Read-only: it writes
 * nothing and neither graph changes. The state lives with the workspace, because choosing something on the
 * canvas can switch the active graph and this panel would otherwise start over.
 */
export default function CompareSection({
  graphIds,
  fingerprinted,
  labels,
  accents,
  state,
  setState,
}: {
  graphIds: string[];
  /** Whether each graph's snapshot has code fingerprints (absent: unknown, assumed yes). */
  fingerprinted?: Record<string, boolean>;
  labels: Record<string, string>;
  accents: Record<string, Accent>;
  state: CompareState;
  setState: Dispatch<SetStateAction<CompareState>>;
}) {
  const name = (id: string) => labels[id] || id;
  const a = graphIds.includes(state.a) ? state.a : (graphIds[0] ?? "");
  const b = graphIds.includes(state.b) && state.b !== a ? state.b : (graphIds.find((g) => g !== a) ?? "");
  const result = state.result && state.result.graph_a === a && state.result.graph_b === b ? state.result : undefined;
  const ready = graphIds.length >= 2 && a && b && a !== b;
  // AR-F16: Compare needs code fingerprints; a graph without them is named before the click.
  const unprinted = ready ? [a, b].filter((g) => fingerprinted?.[g] === false) : [];
  async function run() {
    if (!ready) return;
    setState((s) => ({ ...s, a, b, busy: true, error: "", result: undefined }));
    try {
      const out = await compareGraphs(a, b);
      setState((s) => ({ ...s, a, b, busy: false, result: out }));
    } catch (e) {
      setState((s) => ({ ...s, a, b, busy: false, error: (e as Error).message }));
    }
  }
  return (
    <section aria-labelledby="build-compare">
      <h2 id="build-compare">Compare graphs</h2>
      <p className="build-hint">
        See what two of the checked graphs share and what only one has. Nothing is changed or made.
      </p>
      {graphIds.length < 2 ? (
        <p className="muted">Check two graphs in the Graphs tab to compare them.</p>
      ) : (
        <>
          <div className="compare-pickers">
            <label>
              First{" "}
              <select
                value={a}
                disabled={state.busy}
                onChange={(e) =>
                  // choosing the other side's graph swaps the two, so a graph is never compared with itself
                  setState((s) => ({ ...s, a: e.target.value, b: e.target.value === b ? a : b, error: "" }))
                }
              >
                {graphIds.map((g) => (
                  <option key={g} value={g}>
                    {name(g)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Second{" "}
              <select
                value={b}
                disabled={state.busy}
                onChange={(e) =>
                  setState((s) => ({ ...s, b: e.target.value, a: e.target.value === a ? b : a, error: "" }))
                }
              >
                {graphIds.map((g) => (
                  <option key={g} value={g}>
                    {name(g)}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" disabled={state.busy || !ready || unprinted.length > 0}
              aria-describedby={unprinted.length ? "compare-unavailable" : undefined} onClick={() => void run()}>
              {state.busy ? "Comparing…" : "Compare"}
            </button>
          </div>
          {unprinted.length > 0 && (
            <p id="compare-unavailable" className="muted">
              {unprinted.map(name).join(" and ")} {unprinted.length === 1 ? "has" : "have"} no code fingerprints
              (a paper or document graph, or one not fingerprinted yet), so {unprinted.length === 1 ? "it" : "they"} cannot
              be compared. Choose a code graph.
            </p>
          )}
          {state.error && <p role="alert">{state.error}</p>}
          {result && (
            <div className="compare-result" data-testid="compare-result" aria-live="polite">
              <p className="compare-headline">
                <GraphSwatch accent={accents[a]} />
                {name(a)} <span aria-hidden="true">·</span> <GraphSwatch accent={accents[b]} />
                {name(b)}
              </p>
              <p>{compareHeadline(result, name(a), name(b))}</p>
              <ul className="compare-counts" aria-label="Comparison counts">
                {compareRows(result, name(a), name(b)).map((row) => (
                  <li key={row.key}>
                    <strong>{row.count.toLocaleString("en")}</strong> {row.label}
                  </li>
                ))}
              </ul>
              {cycleSentence(result) && <p className="muted">{cycleSentence(result)}</p>}
              <p className="muted">
                Compared: {result.scope} ({result.compared.a.toLocaleString("en")} in {name(a)},{" "}
                {result.compared.b.toLocaleString("en")} in {name(b)}).
              </p>
              {MATCH_ORDER.filter((key) => result.pairs[key]?.length).map((key) => (
                <details key={key}>
                  <summary>
                    {MATCH_LABEL[key]} ({result.classes[key]})
                  </summary>
                  <ul className="compare-list">
                    {result.pairs[key].map((pair, i) => (
                      <li key={i}>
                        <code>{pair.a.name}</code> → <code>{pair.b.name}</code>
                      </li>
                    ))}
                  </ul>
                  {result.classes[key] > result.pairs[key].length && (
                    <p className="muted">Showing {result.pairs[key].length} of {result.classes[key]}.</p>
                  )}
                </details>
              ))}
              {(
                [
                  ["only_a", `Only in ${name(a)}`],
                  ["only_b", `Only in ${name(b)}`],
                ] as const
              )
                .filter(([key]) => result[key].count > 0)
                .map(([key, title]) => (
                  <details key={key}>
                    <summary>
                      {title} ({result[key].count.toLocaleString("en")})
                    </summary>
                    <ul className="compare-list">
                      {result[key].sample.map((item, i) => (
                        <li key={i}>
                          <code>{item.name}</code> <small>{where(item)}</small>
                        </li>
                      ))}
                    </ul>
                    {result[key].count > result[key].sample.length && (
                      <p className="muted">
                        Showing {result[key].sample.length} of {result[key].count.toLocaleString("en")}.
                      </p>
                    )}
                  </details>
                ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
