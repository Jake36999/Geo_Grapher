/** Normative JSON wire contract 1.0. Declarations only; no application implementation. */
export type Id = string;
export type Digest = string;
export type Cursor = string;
export type Family = 'static' | 'runtime' | 'similarity' | 'history' | 'expected';
export type Resolution = 'exact' | 'candidate' | 'unresolved' | 'observed' | 'declared';
export type EvidenceCategory = 'ast_exact' | 'static_candidate' | 'unresolved' |
  'dynamic_observed' | 'declared' | 'similarity' | 'history';
export type Direction = 'directed' | 'symmetric';
export type WeightUnit = 'edge_count' | 'call_count' | 'calls_per_second' | 'similarity_score' | 'cochange_count';
export type EntityKind = 'workspace' | 'repository' | 'directory' | 'package' | 'file' | 'class' |
  'function' | 'method' | 'attribute' | 'constant' | 'parameter' | 'document' | 'fragment' |
  'external_symbol' | 'scope_atom';
export type NodeKind = EntityKind | 'residual' | 'qi' | 'conceptual' | 'unmapped';
export interface SourceLocation {
  repo_id: Id;
  revision: string;
  rel_path: string;
  start_line: number;
  end_line: number;
}
export interface NodeRecord {
  id: Id;
  entity_id: Id | null;
  kind: NodeKind;
  sort: 'entity' | 'external' | 'text' | 'synthetic';
  repo_id: Id;
  language: string;
  qualified_name: string;
  parent_id: Id | null;
  depth: number | null;
  source: SourceLocation | null;
  flags: { is_test: boolean; is_generated: boolean; is_vendor: boolean; is_external: boolean };
  member_count: number;
  membership_handle: Id | null;
  ast_body_hash: Digest | null;
  wl_3hop_hash: Digest | null;
  doi: number | null;
}
export interface EvidenceHandle {
  id: Id;
  relationship_id: Id;
  category: EvidenceCategory;
  source: SourceLocation | null;
  trace_ref: string | null;
  revision: string;
  extractor_version: string;
  confidence: number | null;
  window: { start: string; end: string } | null;
  details_handle: Id;
}
export interface RelationshipSummary {
  id: Id;
  view_id: Id;
  source: Id;
  target: Id;
  family: Family;
  subtype: string;
  direction: Direction;
  resolution_status: Resolution;
  weight_unit: WeightUnit;
  aggregated_weight: number;
  witness_count: number;
  evidence_count: number;
  is_internal: boolean;
  witness_cursor: Cursor;
}
export interface WitnessRecord {
  id: Id;
  projection_id: Id | null;
  source: Id;
  target: Id;
  source_subject_id: Id;
  target_subject_id: Id;
  family: Family;
  subtype: string;
  direction: Direction;
  resolution_status: Resolution;
  confidence: number | null;
  weight: number;
  weight_unit: WeightUnit;
  evidence_ids: Id[];
  evidence_total: number;
  evidence_next_cursor: Cursor | null;
}
export interface ConformanceFinding {
  id: Id;
  model_digest: Digest;
  rule_id: Id | null;
  source_component_id: Id;
  target_component_id: Id;
  status: 'match' | 'allowed_present' | 'allowed_not_present' | 'forbidden_present' |
    'forbidden_absent' | 'missing_required' | 'unclassified' | 'unmapped' | 'inconclusive';
  rationale: string;
  witness_count: number;
  witness_projection_ids: Id[];
  witness_handle: Id | null;
  limitations: string[];
}
export interface Filter {
  repo_ids: Id[];
  families: Family[];
  subtypes: string[];
  resolution_statuses: Resolution[];
  include_tests: boolean;
  include_generated: boolean;
  include_vendor: boolean;
  include_external: boolean;
  runtime_window: { start: string; end: string; environment: string } | null;
}
export type Grouping =
  { mode: 'atomic' } |
  { mode: 'depth'; depth: number } |
  { mode: 'kind'; kind: 'file' | 'class' | 'repository' } |
  { mode: 'conceptual'; model_digest: Digest } |
  { mode: 'mixed'; revealed_ids: Id[] };
export interface BudgetRequest {
  limit_tokens: number;
  tokenizer: 'o200k_base' | 'cl100k_base';
  allow_byte_fallback: boolean;
}
export interface BudgetReport {
  limit_tokens: number;
  tokenizer: 'o200k_base' | 'cl100k_base';
  count_method: 'tiktoken' | 'utf8_bytes_div4';
  weights_digest: Digest | null;
  used_tokens: number;
  accounting_upper_bound: number;
  guarantee: 'exact_payload' | 'byte_bound';
  counted_region: 'budgeted_json';
}
export interface Coverage {
  status: 'complete_for_declared_static_subset' | 'partial';
  parse_failure_count: number;
  unresolved_count: number;
  limitations: string[];
  report_handle: Id;
}
export interface Completeness {
  truncated: boolean;
  omitted_nodes: number;
  omitted_relationships: number;
  omitted_items: number;
  next_cursor: Cursor | null;
}
export interface BoundaryDiagnostic {
  scope_id: Id;
  mode: 'incoming' | 'outgoing' | 'undirected';
  weight_unit: WeightUnit;
  cut_weight: number;
  volume: number;
  ratio: number | null;
  status: 'ok' | 'zero_volume';
  filter_hash: Digest;
}
export interface CayleyDiagnostic {
  scope_id: Id;
  component_id: Id;
  n: number;
  m: number;
  max_degree: number;
  parity_degree: number | null;
  lower_bound: number | null;
  removed_self_loops: number;
  collapsed_parallel_edges: number;
  status: 'ok' | 'not_applicable';
  interpretation: 'abelian_completion_degree_lower_bound';
}
export interface QIReport {
  mode: 'off' | 'helper_tree_balls_v1';
  metric: 'undirected_unweighted_hops';
  requested_diameter: number;
  measured_max_intrinsic_diameter: number;
  A: number;
  B: number;
  directed_reachability_preserved: false;
  group_count: number;
  internal_witness_count: number;
  crossing_witness_count: number;
  membership_handle: Id | null;
}
export interface GraphPayload {
  view_id: Id | null;
  nodes: NodeRecord[];
  relationships: RelationshipSummary[];
  witnesses: WitnessRecord[];
  evidence_handles: EvidenceHandle[];
  coverage: Coverage;
  completeness: Completeness;
}
export interface SuccessEnvelope<T extends GraphPayload> {
  schema_version: '1.0';
  request_id: Id;
  snapshot_id: Id;
  revisions: { repo_id: Id; revision: string; digest: Digest }[];
  query_digest: Digest;
  budget: BudgetReport;
  data: T;
}
export interface ErrorEnvelope {
  schema_version: '1.0';
  request_id: Id;
  error: {
    code: 'INVALID_REQUEST' | 'NOT_FOUND' | 'SNAPSHOT_UNAVAILABLE' | 'SNAPSHOT_MISMATCH' |
      'INVALID_CURSOR' | 'BUDGET_TOO_SMALL' | 'TOKENIZER_UNAVAILABLE' | 'RULE_CONFLICT' |
      'INCOMPLETE_BUILD' | 'LAYOUT_FAILED' | 'CANCELLED' | 'INTERNAL_ERROR';
    message: string;
    retryable: boolean;
    minimum_tokens: number | null;
    details_handle: Id | null;
  };
}
export type Response<T extends GraphPayload> = SuccessEnvelope<T> | ErrorEnvelope;
export interface BaseRequest {
  schema_version: '1.0';
  request_id: Id;
  snapshot_id: Id;
  budget: BudgetRequest;
}
export interface SearchEntitiesRequest extends BaseRequest {
  query: string;
  mode: 'lexical';
  repo_ids: Id[];
  kinds: EntityKind[];
  limit: number;
  cursor: Cursor | null;
}
export interface SearchEntitiesData extends GraphPayload {
  hits: { node_id: Id; score: number; matched_fields: ('qualified_name' | 'rel_path')[] }[];
}
export type SearchEntitiesResponse = Response<SearchEntitiesData>;
export interface GetArchitectureContextRequest extends BaseRequest {
  focus_id: Id;
  grouping: Grouping;
  context_radius: 0 | 1 | 2;
  filter: Filter;
  pins: Id[];
  qi: { enabled: boolean; max_diameter: number };
  cursor: Cursor | null;
}
export interface GetArchitectureContextData extends GraphPayload {
  focus_id: Id;
  ancestor_ids: Id[];
  representative_focus_id: Id;
  qi: QIReport;
  boundary: BoundaryDiagnostic[];
  cayley: CayleyDiagnostic[];
}
export type GetArchitectureContextResponse = Response<GetArchitectureContextData>;
export interface InspectRelationshipWitnessesRequest extends BaseRequest {
  view_id: Id;
  projection_id: Id | null;
  relationship_id: Id | null;
  evidence_page_size: number;
  evidence_cursor: Cursor | null;
  page_size: number;
  cursor: Cursor | null;
}
export interface InspectRelationshipWitnessesData extends GraphPayload {
  total_witness_count: number;
}
export type InspectRelationshipWitnessesResponse = Response<InspectRelationshipWitnessesData>;
export interface GetEntityContentRequest extends BaseRequest {
  entity_id: Id;
  content_kind: 'source' | 'documentation';
  start_line: number | null;
  end_line: number | null;
  cursor: Cursor | null;
}
export interface GetEntityContentData extends GraphPayload {
  entity_id: Id;
  chunks: {
    source: SourceLocation;
    text: string;
    sha256: Digest;
    trust: 'untrusted_repository_content';
  }[];
}
export type GetEntityContentResponse = Response<GetEntityContentData>;
export interface FindDependantsRequest extends BaseRequest {
  entity_id: Id;
  direction: 'incoming' | 'outgoing';
  filter: Filter;
  max_depth: number;
  max_results: number;
  cursor: Cursor | null;
}
export interface FindDependantsData extends GraphPayload {
  start_id: Id;
  traversal_complete: boolean;
  results: { node_id: Id; hop_count: number; witness_path_ids: Id[] }[];
}
export type FindDependantsResponse = Response<FindDependantsData>;
export interface CheckArchitectureRequest extends BaseRequest {
  model_digest: Digest;
  scope_id: Id;
  filter: Filter;
  include_satisfied: boolean;
  page_size: number;
  cursor: Cursor | null;
}
export interface CheckArchitectureData extends GraphPayload {
  model_digest: Digest;
  world_policy: 'open' | 'closed';
  findings: ConformanceFinding[];
  mapping_counts: { mapped: number; unmapped: number; conflicting: number };
}
export type CheckArchitectureResponse = Response<CheckArchitectureData>;
export interface FindSimilarCodeRequest extends BaseRequest {
  entity_id: Id;
  mode: 'exact_normalized_ast' | 'wl_3hop_candidate';
  repo_ids: Id[];
  limit: number;
  cursor: Cursor | null;
}
export interface FindSimilarCodeData extends GraphPayload {
  entity_id: Id;
  normalization_version: 'py-ast-v1';
  wl_version: 'directed-wl3-v1';
  matches: { node_id: Id; match: 'verified_normalized_ast' | 'wl_candidate'; hash: Digest }[];
}
export type FindSimilarCodeResponse = Response<FindSimilarCodeData>;

export type Vec3 = [number, number, number];
export interface ViewportFrameRequest extends BaseRequest {
  focus_id: Id;
  revealed_ids: Id[];
  pins: Id[];
  context_radius: 0 | 1 | 2;
  filter: Filter;
  layout_version: 'sphere-pack-v1';
  seed: string;
  beta: number;
  edge_lens: { enabled: boolean; center: Vec3; radius: number; strength: number };
  node_budget: number;
  curve_budget: number;
  viewport: { width_px: number; height_px: number; device_pixel_ratio: number };
  camera: { eye: Vec3; target: Vec3; up: Vec3; fov_y_degrees: number; near: number; far: number };
}
export interface ViewportFrameData extends GraphPayload {
  layout_version: 'sphere-pack-v1';
  partition_digest: Digest;
  spheres: { node_id: Id; center: Vec3; radius: number; role: 'representative' | 'context_shell' }[];
  curves: {
    relationship_id: Id;
    canonical_source: Id;
    canonical_target: Id;
    reversed: boolean;
    control_points: Vec3[];
    degree: 1 | 2 | 3;
    knots: number[];
    normal: Vec3;
    binormal: Vec3;
    lane_index: number;
    lane_count: number;
    lane_spacing: number;
    sample_count: number;
  }[];
  packing: { tolerance: 0.0001; fallback_parent_ids: Id[]; max_violation: number };
  scene_completeness: { omitted_spheres: number; omitted_curves: number };
}
export type ViewportFrameResponse = Response<ViewportFrameData>;
export interface OperationMap {
  search_entities: { request: SearchEntitiesRequest; response: SearchEntitiesResponse };
  get_architecture_context: { request: GetArchitectureContextRequest; response: GetArchitectureContextResponse };
  inspect_relationship_witnesses: { request: InspectRelationshipWitnessesRequest; response: InspectRelationshipWitnessesResponse };
  get_entity_content: { request: GetEntityContentRequest; response: GetEntityContentResponse };
  find_dependants: { request: FindDependantsRequest; response: FindDependantsResponse };
  check_architecture: { request: CheckArchitectureRequest; response: CheckArchitectureResponse };
  find_similar_code: { request: FindSimilarCodeRequest; response: FindSimilarCodeResponse };
  viewport_frame: { request: ViewportFrameRequest; response: ViewportFrameResponse };
}
