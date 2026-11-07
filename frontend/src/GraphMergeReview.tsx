import { useEffect, useRef, useState } from "react";
import { json } from "./api";
import type { MergePlan as Plan } from "../../contracts/graph-workspace";
export default function GraphMergeReview({
  graphIds,
  onMerged,
}: {
  graphIds: string[];
  onMerged: (id: string) => void;
}) {
  const [label, setLabel] = useState(""),
    [plan, setPlan] = useState<Plan>();
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    generation.current++;
    setPlan(undefined);
    setAcknowledged(false);
    setError("");
  }, [graphIds.join(), label]);
  async function review() {
    setAcknowledged(false);
    const current = generation.current;
    setBusy(true);
    setError("");
    setPlan(undefined);
    try {
      const result = await json<Plan>("/api/graphs/merge/plan", {
        graph_ids: graphIds,
        label,
      });
      if (current === generation.current) setPlan(result);
    } catch (e) {
      if (current === generation.current) setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function execute() {
    if (!plan || !acknowledged) return;
    setBusy(true);
    setError("");
    try {
      const receipt = await json<{ graph_id: string }>(
        "/api/graphs/merge/execute",
        {
          graph_ids: plan.sources.map((s) => s.graph_id),
          label: plan.label,
          plan_id: plan.plan_id,
        },
      );
      setPlan(undefined);
      setAcknowledged(false);
      onMerged(receipt.graph_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="graph-merge-review">
      <summary>Create a physically merged graph</summary>
      <p>
        For projects you intend to analyse together. A merged graph is a new
        destination containing the selected snapshots; all source graphs remain
        available. Shared display alone needs no merge.
      </p>
      <label>
        New graph name{" "}
        <input
          value={label}
          maxLength={120}
          disabled={busy}
          onChange={(e) => setLabel(e.target.value)}
        />
      </label>{" "}
      <button
        disabled={
          busy || graphIds.length < 2 || graphIds.length > 8 || !label.trim()
        }
        onClick={review}
      >
        Review merge plan
      </button>
      {error && <p role="alert">{error}</p>}
      {plan && (
        <section aria-label="Merge plan review">
          <h3>{plan.label}</h3>
          <ul>
            {plan.sources.map((s) => (
              <li key={s.graph_id}>
                {s.label} · snapshot {s.snapshot_id.slice(-12)} ·{" "}
                {s.repo_ids.length} repository namespace(s)
                {s.paper_database ? " · paper corpus" : ""}
              </li>
            ))}
          </ul>
          {plan.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
          <label>
            <input
              type="checkbox"
              checked={acknowledged}
              disabled={busy}
              onChange={(e) => setAcknowledged(e.target.checked)}
            />{" "}
            I reviewed these sources and want a new merged graph.
          </label>{" "}
          <button disabled={busy || !acknowledged} onClick={execute}>
            {busy ? "Building merged graph…" : "Create reviewed merged graph"}
          </button>
        </section>
      )}
    </details>
  );
}
