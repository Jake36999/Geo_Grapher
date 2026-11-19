import { useEffect, useRef, useState } from "react";
import { json } from "./api";
import IngestSheet, { type SheetPlan } from "./IngestSheet";
import { activeOverrides, type RoleOverrides } from "./ingestMap";

type Plan = SheetPlan & { plan_id: string; plan_version: string };
type Job = { state: "queued" | "running" | "done" | "failed"; reports: unknown[]; error: string | null };

/**
 * Add folder…: browse an allowed root, read it (workspace-init partitions), review the folder map in a
 * wide sheet, then apply the chosen parts as a background job. The panel keeps the browser and the
 * job's status; the review itself is in the sheet.
 */
export default function WorkspaceIngest({ onIngested, managedBy = "" }: { onIngested: () => void; managedBy?: string }) {
  const [open, setOpen] = useState(false);
  const [roots, setRoots] = useState<string[]>([]);
  const [path, setPath] = useState(""),
    [dirs, setDirs] = useState<string[]>([]);
  const [plan, setPlan] = useState<Plan>(),
    [approved, setApproved] = useState<Record<string, boolean>>({}),
    [roles, setRoles] = useState<RoleOverrides>({}),
    [sheet, setSheet] = useState(false);
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
    setSheet(false);
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
      // Every part starts ticked, unlicensed ones included: they are ingested and copied like any
      // other; the sheet only labels them as cited, not published as our own.
      setApproved(Object.fromEntries(p.partitions.map((x) => [x.key, true])));
      setRoles({});
      setSheet(true);
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
    setSheet(false);
    try {
      const started = await json<{ job_id: string }>("/api/workspace/ingest-execute", {
        plan_id: plan.plan_id,
        approved_keys: plan.partitions.filter((p) => approved[p.key]).map((p) => p.key),
        role_overrides: activeOverrides(plan, roles, approved),
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
      {!roots.length &&
        (managedBy ? (
          <p>
            No folders can be browsed yet. In the Librarian, open Settings → Project folders, turn on project access and
            attach a folder to “{managedBy}”, then reopen Geo-Grapher from the Librarian.
          </p>
        ) : (
          <p>No folders are browsable. Start the server with --browse-root DIR.</p>
        ))}
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
            Read this folder
          </button>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {plan && !sheet && !job && (
        <p>
          Read {plan.partitions.length} part{plan.partitions.length === 1 ? "" : "s"}.{" "}
          <button onClick={() => setSheet(true)}>Review the folder map</button>
        </p>
      )}
      {job && (
        <p aria-live="polite" data-testid="ingest-job-state">
          Job {job.state}
          {job.error ? `: ${job.error}` : ""}
          {job.state === "done" && job.reports.length > 0
            ? `: added ${job.reports.length} graph${job.reports.length === 1 ? "" : "s"}. They are in the Graphs tab; check one to show it.`
            : ""}
        </p>
      )}
      {!job && busy && plan && !sheet && (
        <p aria-live="polite" data-testid="ingest-job-state">
          Starting…
        </p>
      )}
      {plan && sheet && (
        <IngestSheet
          plan={plan}
          approved={approved}
          roles={roles}
          busy={busy}
          onApprove={(key, on) => setApproved((a) => ({ ...a, [key]: on }))}
          onRole={(key, role) => setRoles((r) => ({ ...r, [key]: role }))}
          onApply={apply}
          onClose={() => setSheet(false)}
        />
      )}
    </section>
  );
}
