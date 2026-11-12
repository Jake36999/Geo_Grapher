import type {
  NodeRecord as ActorNode,
} from "../../contracts/v1.1/geographer.wire";

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
  "fragment_rep",
  "entity_rep",
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
