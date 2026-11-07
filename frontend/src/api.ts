import type {
  NodeRecord,
  OperationMap,
  ViewportFrameData,
  ViewportFrameRequest,
  SuccessEnvelope,
  Filter,
} from "../../contracts/geographer.wire";
import visibilityPresets from "../../contracts/visibility-presets.json";
import type {
  OperationMap as ActorOperations,
  NodeRecord as ActorNode,
} from "../../contracts/v1.1/geographer.wire";
export type GroupMode =
  | "mixed"
  | "repository"
  | "directory"
  | "file"
  | "class"
  | "atomic"
  | "conceptual";
export const groupModes: Record<GroupMode, string> = {
  mixed: "Interactive Mixed",
  repository: "Repository",
  directory: "Directories",
  file: "Files",
  class: "Classes",
  atomic: "Atomic",
  conceptual: "Conceptual Components",
};

export type VisibilityPreset = keyof typeof visibilityPresets;
export { visibilityPresets };
export function visibilityFilter(
  current: Filter,
  preset: VisibilityPreset,
): Filter {
  const value = visibilityPresets[preset];
  return {
    ...current,
    resolution_statuses: [
      ...value.resolution_statuses,
      ...(current.families.includes("runtime") ? ["observed"] : []),
    ] as Filter["resolution_statuses"],
    include_external: value.include_external,
  };
}
export function currentVisibilityPreset(
  filter: Filter,
): VisibilityPreset | "custom" {
  return (
    (Object.keys(visibilityPresets) as VisibilityPreset[]).find((key) => {
      const value = visibilityPresets[key];
      return (
        filter.include_external === value.include_external &&
        filter.resolution_statuses
          .filter((s) => s !== "observed")
          .sort()
          .join() === [...value.resolution_statuses].sort().join()
      );
    }) ?? "custom"
  );
}

export type Node = NodeRecord & {
  child_count?: number;
  summary?: ActorNode["summary"];
  group_preview?: ActorNode["group_preview"];
};
export interface RuntimeCollection {
  collection_id: string;
  environment: string;
  window: { start: string; end: string };
  source_match: boolean;
  coverage: {
    complete: boolean;
    truncated: boolean;
    limitations: string[];
    process_scope: string;
    thread_scope: string;
    async_scope: string;
  };
  mapped_call_count: number;
  input_call_count: number;
  mapped_records: number;
  quarantined_records: number;
  report_handle: string;
}
export function runtimeFilter(
  current: Filter,
  collection?: RuntimeCollection,
): Filter {
  const statuses = current.resolution_statuses.filter((s) => s !== "observed");
  return {
    ...current,
    families: [
      ...current.families.filter((f) => f !== "runtime"),
      ...(collection ? ["runtime" as const] : []),
    ],
    resolution_statuses: [
      ...(statuses.length ? statuses : ["exact" as const]),
      ...(collection ? ["observed" as const] : []),
    ],
    runtime_window: collection
      ? { ...collection.window, environment: collection.environment }
      : null,
  };
}
export interface Snapshot {
  snapshot_id: string;
  created_at: string;
  stage: number;
  revisions: { repo_id: string; revision: string; digest: string }[];
  root: Node;
  repositories: Node[];
  counts: { entities: number; relationships: number };
  statuses: Record<string, number>;
  telemetry_available: boolean;
  runtime_collections?: RuntimeCollection[];
}
export interface Bootstrap {
  snapshots: Snapshot[];
  models: { digest: string; world_policy: "open" | "closed" }[];
}
export const defaultFilter = {
  repo_ids: [],
  families: ["static" as const],
  subtypes: [],
  resolution_statuses: ["exact" as const],
  include_tests: false,
  include_generated: false,
  include_vendor: false,
  include_external: true,
  runtime_window: null,
};

export function budget(
  limit = 8192,
  tokenizer: "o200k_base" | "cl100k_base" = "o200k_base",
) {
  return { limit_tokens: limit, tokenizer, allow_byte_fallback: false };
}
export function base(snapshot_id: string, limit = 8192) {
  return {
    schema_version: "1.0" as const,
    request_id: crypto.randomUUID(),
    snapshot_id,
    budget: budget(limit),
  };
}

let workspaceGraph: {id:string;label:string;primary?:string} | null = null;
export function setWorkspaceGraph(id:string,label:string,primary?:string) { workspaceGraph={id,label,primary}; }
export function graphBasePath(): string {
  if (workspaceGraph) return `/graphs/${workspaceGraph.id}/`;
  return window.location.pathname.match(/^\/graphs\/g_[0-9a-f]{24}\//)?.[0] ?? "/";
}

export function scopedStorageKey(key: string): string {
  if (workspaceGraph?.id === workspaceGraph?.primary && workspaceGraph) return key;
  const path = graphBasePath();
  return path === "/" ? key : `${key}:${path}`;
}

export function graphDisplayLabel(): string | null {
  if (workspaceGraph) return workspaceGraph.label;
  return graphBasePath() === "/" ? null : new URLSearchParams(location.search).get("label")?.slice(0,120) ?? null;
}

export async function json<T>(
  url: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const prefix = graphBasePath();
  const target = prefix !== "/" && url.startsWith("/api/") && !url.startsWith('/api/graphs') ? prefix.slice(0,-1) + url : url;
  const response = await fetch(target, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  const text = await response.text();
  let result: any;
  try {
    result = JSON.parse(text);
  } catch {
    const method = body === undefined ? "GET" : "POST";
    const detail = text.trim().slice(0, 160) || response.statusText;
    const hint = response.status === 405 && url.startsWith("/api/")
      ? " The running backend may not match this workspace build; restart the Geo Grapher server with the current project environment."
      : "";
    throw new Error(`${method} ${url} returned ${response.status} ${response.statusText}: ${detail}.${hint}`);
  }
  if (result.error)
    throw new Error(
      typeof result.error === "string" ? result.error : result.error.message,
    );
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return result as T;
}

export async function query<K extends keyof OperationMap>(
  operation: K,
  request: OperationMap[K]["request"],
  signal?: AbortSignal,
): Promise<Exclude<OperationMap[K]["response"], { error: unknown }>> {
  const url =
    operation === "viewport_frame"
      ? "/api/v1/viewport/frame"
      : `/api/v1/${operation}`;
  return json(url, request, signal) as Promise<
    Exclude<OperationMap[K]["response"], { error: unknown }>
  >;
}

export async function viewportPage(
  request: ViewportFrameRequest,
  cursor: string,
  signal?: AbortSignal,
) {
  return json<SuccessEnvelope<ViewportFrameData>>(
    "/api/v1/viewport/page",
    { request, cursor },
    signal,
  );
}

const referenceFields = new Set([
  "id",
  "node_id",
  "entity_id",
  "source",
  "target",
  "parent_id",
  "source_subject_id",
  "target_subject_id",
  "projection_id",
  "relationship_id",
  "focus_id",
  "representative_focus_id",
  "start_id",
  "scope_id",
  "component_id",
  "source_component_id",
  "target_component_id",
  "canonical_source",
  "canonical_target",
  "doc_handle",
  "resolved_source",
  "resolved_target",
  "ancestor_ids",
  "evidence_ids",
  "witness_path_ids",
  "witness_projection_ids",
  "fragment_ids",
  "fallback_parent_ids",
  "call_relationship_ids",
  "alternatives",
  "relationship_ids",
]);
// Decode only schema reference positions. Repository source/prose is never rewritten.
export function canonicalActor<
  T extends {
    revisions: { repo_id: string; revision: string }[];
    data: {
      ids: Record<string, string>;
      view_id: string | null;
      nodes: ActorNode[];
    };
  },
>(result: T): T {
  const ids = result.data.ids;
  const decode = (value: any, key = ""): any =>
    Array.isArray(value)
      ? value.map((v) => decode(v, key))
      : value && typeof value === "object"
        ? Object.fromEntries(
            Object.entries(value).map(([k, v]) => [k, decode(v, k)]),
          )
        : typeof value === "string" && referenceFields.has(key)
          ? (ids[value] ?? value)
          : value;
  const copy = decode(result) as T;
  const revisions = Object.fromEntries(
    copy.revisions.map((r) => [r.repo_id, r.revision]),
  );
  const restore = (v: any): void => {
    if (!v || typeof v !== "object") return;
    if (
      "repo_id" in v &&
      "rel_path" in v &&
      "start_line" in v &&
      !("revision" in v)
    )
      v.revision = v.revision_override ?? revisions[v.repo_id];
    for (const child of Object.values(v)) restore(child);
  };
  restore(copy.data);
  for (const node of copy.data.nodes)
    Object.assign(node, {
      entity_id: node.is_synthetic ? null : node.id,
      depth: null,
      ast_body_hash: null,
      wl_3hop_hash: null,
      doi: null,
    });
  for (const relation of (copy.data as any).relationships ?? [])
    Object.assign(relation, {
      view_id: copy.data.view_id,
      witness_cursor: null,
    });
  return copy;
}
export function actorBase(snapshot_id: string, limit = 16384) {
  return {
    ...base(snapshot_id, limit),
    schema_version: "1.1" as const,
    identity_mode: "canonical_map" as const,
  };
}
export async function actorQuery<K extends keyof ActorOperations>(
  operation: K,
  request: ActorOperations[K]["request"],
  signal?: AbortSignal,
) {
  const url =
    operation === "viewport_frame"
      ? "/api/v1.1/viewport/frame"
      : `/api/v1.1/${operation}`;
  const result = await json<
    Exclude<ActorOperations[K]["response"], { error: unknown }>
  >(url, request, signal);
  return canonicalActor(result);
}
export async function workspaceFrame(
  request: ViewportFrameRequest,
  mode: GroupMode,
  model: string,
  signal?: AbortSignal,
  cursor?: string,
) {
  const grouping =
    mode === "mixed"
      ? { mode: "mixed" as const, revealed_ids: request.revealed_ids }
      : mode === "conceptual"
        ? { mode: "conceptual" as const, model_digest: model }
        : mode === "atomic"
          ? { mode: "atomic" as const }
          : { mode: "kind" as const, kind: mode };
  const payload = {
    ...request,
    ...actorBase(request.snapshot_id, request.budget.limit_tokens),
    budget: request.budget,
    model_digest: model || null,
    grouping,
  };
  const response = cursor
    ? canonicalActor(
        await json<any>(
          "/api/v1.1/viewport/page",
          { request: payload, cursor },
          signal,
        ),
      )
    : await actorQuery("viewport_frame", payload, signal);
  return response as unknown as SuccessEnvelope<ViewportFrameData>;
}

export function mergeFrame(
  old: ViewportFrameData | undefined,
  page: ViewportFrameData,
): ViewportFrameData {
  if (!old || old.partition_digest !== page.partition_digest) return page;
  const merge = <T>(a: T[], b: T[], key: (x: T) => string) =>
    Array.from(new Map([...a, ...b].map((v) => [key(v), v])).values());
  return {
    ...page,
    nodes: merge(old.nodes, page.nodes, (n) => n.id),
    relationships: merge(old.relationships, page.relationships, (r) => r.id),
    witnesses: merge(old.witnesses, page.witnesses, (r) => r.id),
    evidence_handles: merge(
      old.evidence_handles,
      page.evidence_handles,
      (e) => e.id,
    ),
    spheres: merge(old.spheres, page.spheres, (s) => s.node_id),
    curves: merge(old.curves, page.curves, (c) => c.relationship_id),
    scene_completeness: {
      omitted_spheres: Math.max(
        0,
        page.scene_completeness.omitted_spheres +
          page.spheres.length -
          merge(old.spheres, page.spheres, (s) => s.node_id).length,
      ),
      omitted_curves: Math.max(
        0,
        page.scene_completeness.omitted_curves +
          page.curves.length -
          merge(old.curves, page.curves, (c) => c.relationship_id).length,
      ),
    },
  };
}

export function shortName(node: Node): string {
  if (node.kind === "repository" && graphDisplayLabel() && graphBasePath().includes(node.repo_id)) return graphDisplayLabel()!;
  if (node.kind === "residual")
    return `Other contents · ${node.member_count.toLocaleString()}`;
  if (node.kind === "scope_atom") return "Body";
  if (node.kind === "fragment")
    return `Documentation · line ${node.source?.start_line ?? ""}`;
  if (node.kind === "file")
    return node.source?.rel_path.split("/").at(-1) ?? node.qualified_name;
  if (["function", "method", "class"].includes(node.kind))
    return node.qualified_name.split(".").at(-1) ?? node.qualified_name;
  return (
    node.qualified_name.split("/").at(-1)?.split(".").at(-1) ??
    node.qualified_name
  );
}

export function shortRevision(revision: string): string {
  if (revision.startsWith("working-tree:"))
    return (
      "working tree " +
      revision.slice("working-tree:".length, "working-tree:".length + 8)
    );
  if (/^[a-f0-9]{40,64}$/i.test(revision)) return revision.slice(0, 8);
  return revision.length <= 24
    ? revision
    : revision.slice(0, 12) + "…" + revision.slice(-8);
}

// Persisted browser state is untrusted input too. Old or malformed views are ignored.
export function validSaved(value: unknown): boolean {
  const x = value as Record<string, any>;
  const ids = (a: unknown) =>
    Array.isArray(a) &&
    a.length <= 500 &&
    a.every((v) => typeof v === "string" && v.length > 0 && v.length <= 512);
  const vec = (a: unknown) =>
    Array.isArray(a) &&
    a.length === 3 &&
    a.every(
      (v) => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= 1e12,
    );
  return Boolean(
    x &&
    x.version === 1 &&
    (x.graph_ids === undefined || (Array.isArray(x.graph_ids) && x.graph_ids.length<=19 && x.graph_ids.every((id:unknown)=>typeof id==='string'&&/^g_[0-9a-f]{24}$/.test(id)))) &&
    typeof x.name === "string" &&
    x.name.length > 0 &&
    x.name.length <= 80 &&
    typeof x.snapshot_id === "string" &&
    typeof x.focus === "string" &&
    typeof x.selected === "string" &&
    ids(x.revealed) &&
    (x.pins === undefined || ids(x.pins)) &&
    (x.contextRadius === undefined ||
      x.contextRadius === 0 ||
      x.contextRadius === 1 ||
      x.contextRadius === 2) &&
    (x.grouping === undefined || Object.hasOwn(groupModes, x.grouping)) &&
    (x.modelDigest === undefined || typeof x.modelDigest === "string") &&
    (x.selectedVirtual === undefined ||
      typeof x.selectedVirtual === "boolean") &&
    ["spatial", "list", "matrix"].includes(x.view) &&
    ["dark", "light"].includes(x.theme) &&
    typeof x.lens === "boolean" &&
    typeof x.beta === "number" &&
    x.beta >= 0 &&
    x.beta <= 1 &&
    (x.camera === undefined ||
      (x.camera &&
        vec(x.camera.eye) &&
        vec(x.camera.target) &&
        x.camera.eye.some(
          (v: number, i: number) => Math.abs(v - x.camera.target[i]) > 1e-6,
        ))) &&
    (x.panelSizes === undefined ||
      (Array.isArray(x.panelSizes) &&
        x.panelSizes.length === 2 &&
        x.panelSizes.every(
          (v: unknown) => typeof v === "number" && Number.isFinite(v),
        ) &&
        x.panelSizes[0] >= 190 &&
        x.panelSizes[0] <= 340 &&
        x.panelSizes[1] >= 290 &&
        x.panelSizes[1] <= 440)) &&
    x.filter &&
    Object.keys(x.filter).every((k) =>
      Object.keys(defaultFilter).includes(k),
    ) &&
    ids(x.filter.repo_ids) &&
    Array.isArray(x.filter.families) &&
    x.filter.families.length <= 2 &&
    new Set(x.filter.families).size === x.filter.families.length &&
    x.filter.families.every(
      (v: unknown) => v === "static" || v === "runtime",
    ) &&
    ids(x.filter.subtypes) &&
    Array.isArray(x.filter.resolution_statuses) &&
    x.filter.resolution_statuses.length > 0 &&
    new Set(x.filter.resolution_statuses).size ===
      x.filter.resolution_statuses.length &&
    x.filter.resolution_statuses.every(
      (v: unknown) =>
        typeof v === "string" &&
        ["exact", "candidate", "unresolved", "observed"].includes(v),
    ) &&
    [
      "include_tests",
      "include_generated",
      "include_vendor",
      "include_external",
    ].every((k) => typeof x.filter[k] === "boolean") &&
    (x.filter.families.includes("runtime")
      ? x.filter.runtime_window &&
        Object.keys(x.filter.runtime_window).sort().join() ===
          ["end", "environment", "start"].join() &&
        typeof x.filter.runtime_window.environment === "string" &&
        x.filter.runtime_window.environment.length > 0 &&
        x.filter.runtime_window.environment.length <= 128 &&
        typeof x.filter.runtime_window.start === "string" &&
        typeof x.filter.runtime_window.end === "string" &&
        x.filter.runtime_window.start.endsWith("Z") &&
        x.filter.runtime_window.end.endsWith("Z") &&
        Number.isFinite(Date.parse(x.filter.runtime_window.start)) &&
        Date.parse(x.filter.runtime_window.start) <
          Date.parse(x.filter.runtime_window.end) &&
        x.filter.resolution_statuses.includes("observed")
      : x.filter.runtime_window === null &&
        !x.filter.resolution_statuses.includes("observed")),
  );
}
