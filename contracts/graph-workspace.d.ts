/** Additive local workspace contract. Inner code-query contracts are unchanged.
 * Render collections are display data, never a serialized union analysis graph.
 */
import type { Vec3, ViewportFrameData, Filter } from './geographer.wire';
import type { Grouping } from './v1.1/geographer.wire';

export interface GraphFrameRequest {
  graph_id: string;
  snapshot_id?: string | null; // Omitted/null selects this graph's published head.
  focus_id?: string | null; // Canonical local ID, never a response alias/render ID.
  context_radius?: 0 | 1 | 2; // Default 1.
  filter?: Filter;
  grouping?: Grouping;
  model_digest?: string | null;
  revealed_ids?: string[];
  pins?: string[];
}
export interface CompositionRequest { graphs: GraphFrameRequest[] } // 1..19 distinct graphs; selection order defines hex slots.
export interface RenderAddress {
  graph_id: string;
  snapshot_id: string;
  local_id: string;
  kind: 'node' | 'relationship';
}
export interface ComposedGraphFrame {
  graph_id: string;
  label: string;
  snapshot_id: string;
  root_id: string;
  focus_id: string;
  transform: { scale: number; translation: Vec3 };
  frame: ViewportFrameData;
  budget: unknown; // Original inner viewport accounting, not a combined actor budget.
  root_radius: number;
  world_center: Vec3;
  repository_labels: Record<string, string>;
}
export interface FrameFailure {
  graph_id: string;
  label: string;
  error: { code: 'FRAME_UNAVAILABLE'; message: string };
}
export interface CompositionResponse {
  version: 'graph-composition-v1';
  composition: 'display_only';
  frames: (ComposedGraphFrame | FrameFailure)[];
  address_fields: ['graph_id', 'snapshot_id', 'local_id'];
  scope_policy: 'independent_partitions_no_cross_graph_dependencies';
}
export interface MergePlanRequest { graph_ids: string[]; label: string } // 2..8 disjoint graphs, name <=120 chars.
export interface MergeSource {
  graph_id: string;
  label: string;
  snapshot_id: string;
  repo_ids: string[];
  code_database: string;
  paper_database: string | null;
  paper_identity: { corpus_revision: string; source_digest: string } | null;
}
export interface MergePlan {
  version: 'graph-merge-v1';
  plan_id: string;
  destination_graph_id: string;
  label: string;
  sources: MergeSource[];
  owner_repo_ids: string[];
  policy: 'namespace_preserving_union_no_new_inferred_edges';
  source_disposition: 'preserved';
  derived_analyses: 'recomputed_stage_3';
  paper_policy: 'origin_scoped_documents_and_concepts_no_cross_origin_equivalence';
  warnings: string[];
}
export interface MergeExecuteRequest extends MergePlanRequest { plan_id: string }
export interface MergeReceipt {
  plan_id: string;
  graph_id: string;
  snapshot_id: string;
  counts: { entities: number; relationships: number; evidence: number; documentary_incidences: number };
  source_graph_ids: string[];
  sources_preserved: true;
  papers_merged: boolean;
  created_at: string;
}
// POST /api/graphs/frame, /api/graphs/merge/plan, /api/graphs/merge/execute.
// Invalid frame/plan input: HTTP400 {error:string}; stale/unreviewed execution: HTTP409 {error:string}.
// No mutation endpoint is exposed as a read-only MCP tool.
