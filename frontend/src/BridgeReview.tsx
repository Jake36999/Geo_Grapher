import { useEffect, useRef, useState } from "react";
import { json } from "./api";

type Proposal = {
  proposal_id: string;
  source_graph: string;
  source_ref: string;
  target_graph: string;
  target_ref: string;
  kind: string;
  score: number;
  features: { alias_overlap: number; shared_citation: number; neighbour_jaccard: number };
  status: "pending" | "accepted" | "rejected";
};

const KINDS = ["reference", "concept_equivalence", "document_identity"] as const;

/** Reviewed bridge candidates between two selected graphs (master G4). Proposing never creates a bridge. */
export default function BridgeReview({
  graphIds,
  labels,
  onDecided,
}: {
  graphIds: string[];
  labels: Record<string, string>;
  onDecided: () => void;
}) {
  const [kind, setKind] = useState<(typeof KINDS)[number]>("reference");
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [rationale, setRationale] = useState<Record<string, string>>({});
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const pair = graphIds.length === 2;
  useEffect(() => {
    generation.current++;
    setProposals([]);
    setError("");
  }, [graphIds.join(), kind]);
  async function propose() {
    if (!pair) return;
    const current = generation.current;
    setBusy(true);
    setError("");
    try {
      await json("/api/graphs/bridge-proposals", { graph_a: graphIds[0], graph_b: graphIds[1], kind });
      const listed = await json<{ proposals: Proposal[] }>(
        `/api/graphs/bridge-proposals?graph_ids=${graphIds.map(encodeURIComponent).join(",")}`,
      );
      if (current === generation.current) setProposals(listed.proposals);
    } catch (e) {
      if (current === generation.current) setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function decide(p: Proposal, decision: "accept" | "reject") {
    const why = (rationale[p.proposal_id] || "").trim();
    if (!why) return;
    setBusy(true);
    setError("");
    try {
      await json(`/api/graphs/bridge-proposals/${encodeURIComponent(p.proposal_id)}`, { decision, rationale: why });
      setProposals((all) => all.filter((x) => x.proposal_id !== p.proposal_id));
      onDecided();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const name = (gid: string) => labels[gid] || gid;
  return (
    <details className="bridge-review">
      <summary>Review bridge candidates</summary>
      <p>
        Candidates are scored from shared names, citations and neighbours; a match on names alone is
        down-weighted. Nothing becomes a bridge until you accept it with a rationale.
      </p>
      <label>
        Kind{" "}
        <select value={kind} disabled={busy} onChange={(e) => setKind(e.target.value as (typeof KINDS)[number])}>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </label>{" "}
      <button disabled={busy || !pair} onClick={propose}>
        {pair ? "Find candidates" : "Select exactly two graphs"}
      </button>
      {error && <p role="alert">{error}</p>}
      {proposals.length > 0 && (
        <ul aria-label="Bridge candidates">
          {proposals.map((p) => (
            <li key={p.proposal_id}>
              <strong>{p.score.toFixed(3)}</strong> · {name(p.source_graph)} <code>{p.source_ref}</code> →{" "}
              {name(p.target_graph)} <code>{p.target_ref}</code>
              <small>
                {" "}
                (names {p.features.alias_overlap}, citation {p.features.shared_citation}, neighbours{" "}
                {p.features.neighbour_jaccard})
              </small>
              <div>
                <input
                  aria-label={`Rationale for ${p.proposal_id}`}
                  placeholder="Rationale (required)"
                  maxLength={2000}
                  value={rationale[p.proposal_id] || ""}
                  disabled={busy}
                  onChange={(e) => setRationale((r) => ({ ...r, [p.proposal_id]: e.target.value }))}
                />{" "}
                <button disabled={busy || !(rationale[p.proposal_id] || "").trim()} onClick={() => decide(p, "accept")}>
                  Accept
                </button>{" "}
                <button disabled={busy || !(rationale[p.proposal_id] || "").trim()} onClick={() => decide(p, "reject")}>
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {!busy && pair && proposals.length === 0 && !error && <p className="muted">No pending candidates listed.</p>}
    </details>
  );
}
