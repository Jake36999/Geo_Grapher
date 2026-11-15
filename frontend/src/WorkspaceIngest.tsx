import { useEffect, useRef, useState } from "react";
import { json } from "./api";

type Partition = {
  key: string;
  role: string;
  subtrees: string[];
  file_counts: Record<string, number>;
  bytes: number;
};
type Plan = {
  plan_id: string;
  plan_version: string;
  root: string;
  archetype: string;
  partitions: Partition[];
  manual_steps: { kind: string; dir: string; command: string }[];
};
type Job = { state: "queued" | "running" | "done" | "failed"; reports: unknown[]; error: string | null };

/** Add folder…: browse an allowed root, preview workspace-init partitions, apply the chosen ones as a background job. */
export default function WorkspaceIngest({ onIngested }: { onIngested: () => void }) {
  const [open, setOpen] = useState(false);
  const [roots, setRoots] = useState<string[]>([]);
  const [path, setPath] = useState(""),
    [dirs, setDirs] = useState<string[]>([]);
  const [plan, setPlan] = useState<Plan>(),
    [approved, setApproved] = useState<Record<string, boolean>>({});
  const [job, setJob] = useState<Job>(),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const poll = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearInterval(poll.current), []);
  useEffect(() => {
    if (!open) return;
    json<{ roots: string[] }>("/api/fs/roots")
      .then((r) => {
        setRoots(r.roots);
        if (r.roots.length && !path) browse(r.roots[0]);
      })
      .catch((e) => setError((e as Error).message));
  }, [open]);
  async function browse(target: string) {
    setError("");
    setPlan(undefined);
    try {
      const listed = await json<{ path: string; dirs: string[] }>(`/api/fs/list?path=${encodeURIComponent(target)}`);
      setPath(listed.path);
      setDirs(listed.dirs);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const parent = () => {
    const root = roots.find((r) => path.startsWith(r));
    if (!root || path === root) return undefined;
    return path.replace(/[\\/][^\\/]+$/, "");
  };
  async function preview() {
    setBusy(true);
    setError("");
    setJob(undefined);
    try {
      const p = await json<Plan>("/api/workspace/ingest-preview", { root: path });
      setPlan(p);
      setApproved(Object.fromEntries(p.partitions.map((x) => [x.key, true])));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function apply() {
    if (!plan) return;
    setBusy(true);
    setError("");
    try {
      const started = await json<{ job_id: string }>("/api/workspace/ingest-execute", {
        plan_id: plan.plan_id,
        approved_keys: plan.partitions.filter((p) => approved[p.key]).map((p) => p.key),
      });
      window.clearInterval(poll.current);
      poll.current = window.setInterval(async () => {
        try {
          const status = await json<Job>(`/api/workspace/jobs/${encodeURIComponent(started.job_id)}`);
          setJob(status);
          if (status.state === "done" || status.state === "failed") {
            window.clearInterval(poll.current);
            setBusy(false);
            if (status.state === "done") onIngested();
          }
        } catch (e) {
          window.clearInterval(poll.current);
          setBusy(false);
          setError((e as Error).message);
        }
      }, 400);
    } catch (e) {
      setBusy(false);
      setError((e as Error).message);
    }
  }
  if (!open)
    return (
      <button className="workspace-add-folder" onClick={() => setOpen(true)}>
        Add folder…
      </button>
    );
  const up = parent();
  return (
    <section className="workspace-ingest" aria-label="Add folder">
      <header>
        <strong>Add folder</strong>{" "}
        <button onClick={() => setOpen(false)} aria-label="Close add folder">
          ×
        </button>
      </header>
      {!roots.length && <p>No folders are browsable. Start the server with --browse-root DIR.</p>}
      {roots.length > 0 && (
        <>
          <p>
            <code data-testid="ingest-path">{path}</code>
          </p>
          <ul aria-label="Folders">
            {up && (
              <li>
                <button onClick={() => browse(up)}>.. (up)</button>
              </li>
            )}
            {dirs.map((d) => (
              <li key={d}>
                <button onClick={() => browse(path.replace(/[\\/]$/, "") + "/" + d)}>{d}</button>
              </li>
            ))}
          </ul>
          <button disabled={busy || !path} onClick={preview}>
            Preview this folder
          </button>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {plan && (
        <table aria-label="Ingest preview">
          <caption>
            {plan.archetype} · {plan.partitions.length} partition(s)
          </caption>
          <thead>
            <tr>
              <th>Ingest</th>
              <th>Partition</th>
              <th>Role</th>
              <th>Files</th>
            </tr>
          </thead>
          <tbody>
            {plan.partitions.map((p) => (
              <tr key={p.key}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Ingest partition ${p.key}`}
                    checked={!!approved[p.key]}
                    disabled={busy}
                    onChange={(e) => setApproved((a) => ({ ...a, [p.key]: e.target.checked }))}
                  />
                </td>
                <td>{p.key}</td>
                <td>{p.role}</td>
                <td>{Object.values(p.file_counts).reduce((a, b) => a + b, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {plan && plan.manual_steps.length > 0 && (
        <p>{plan.manual_steps.length} paper corpus folder(s) need the paper pipeline; they are not ingested here.</p>
      )}
      {plan && (
        <button disabled={busy || !Object.values(approved).some(Boolean)} onClick={apply}>
          {busy ? "Ingesting…" : "Ingest selected partitions"}
        </button>
      )}
      {job && (
        <p aria-live="polite" data-testid="ingest-job-state">
          Job {job.state}
          {job.error ? `: ${job.error}` : ""}
        </p>
      )}
    </section>
  );
}
