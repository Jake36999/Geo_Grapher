-- Geo Grapher schema contract 1.0; SQLite >= 3.37 with JSON1. No application code.
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;
BEGIN;

CREATE TABLE snapshot_sets (
  snapshot_id TEXT PRIMARY KEY CHECK(length(snapshot_id)>0),
  manifest_digest TEXT NOT NULL CHECK(length(manifest_digest)=64 AND manifest_digest NOT GLOB '*[^0-9a-f]*'),
  status TEXT NOT NULL CHECK(status IN ('building','complete','failed')),
  created_at TEXT NOT NULL CHECK(length(created_at)>0),
  config_json TEXT NOT NULL CHECK(json_valid(config_json) AND json_type(config_json)='object')
) STRICT;

-- One build-set can contain multiple repo revisions; @workspace is the synthetic root owner.
CREATE TABLE snapshots (
  snapshot_id TEXT NOT NULL,
  repo_id TEXT NOT NULL CHECK(length(repo_id)>0),
  revision TEXT NOT NULL CHECK(length(revision)>0),
  digest TEXT NOT NULL CHECK(length(digest)=64 AND digest NOT GLOB '*[^0-9a-f]*'),
  extractor_version TEXT NOT NULL CHECK(length(extractor_version)>0),
  parse_failures_json TEXT NOT NULL DEFAULT '[]'
    CHECK(json_valid(parse_failures_json) AND json_type(parse_failures_json)='array'),
  PRIMARY KEY(snapshot_id,repo_id),
  FOREIGN KEY(snapshot_id) REFERENCES snapshot_sets(snapshot_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE entities (
  entity_id TEXT NOT NULL CHECK(length(entity_id)>0),
  snapshot_id TEXT NOT NULL,
  repo_id TEXT NOT NULL,
  sort TEXT NOT NULL CHECK(sort IN ('entity','external','text','synthetic')),
  kind TEXT NOT NULL CHECK(kind IN ('workspace','repository','directory','package','file','class',
    'function','method','attribute','constant','parameter','document','fragment','external_symbol','scope_atom')),
  language TEXT NOT NULL CHECK(length(language)>0),
  qualified_name TEXT NOT NULL CHECK(length(qualified_name)>0),
  rel_path TEXT,
  start_line INTEGER,
  end_line INTEGER,
  parent_id TEXT,
  depth INTEGER NOT NULL CHECK(depth>=0),
  ancestors_binary_lifting_json TEXT NOT NULL CHECK(json_valid(ancestors_binary_lifting_json)
    AND json_type(ancestors_binary_lifting_json)='array' AND json_array_length(ancestors_binary_lifting_json)>0),
  is_test INTEGER NOT NULL DEFAULT 0 CHECK(is_test IN (0,1)),
  is_generated INTEGER NOT NULL DEFAULT 0 CHECK(is_generated IN (0,1)),
  is_vendor INTEGER NOT NULL DEFAULT 0 CHECK(is_vendor IN (0,1)),
  is_external INTEGER NOT NULL DEFAULT 0 CHECK(is_external IN (0,1)),
  ast_body_hash TEXT CHECK(ast_body_hash IS NULL OR (length(ast_body_hash)=64 AND ast_body_hash NOT GLOB '*[^0-9a-f]*')),
  wl_3hop_hash TEXT CHECK(wl_3hop_hash IS NULL OR (length(wl_3hop_hash)=64 AND wl_3hop_hash NOT GLOB '*[^0-9a-f]*')),
  qi_cluster_id TEXT,
  PRIMARY KEY(snapshot_id,entity_id),
  FOREIGN KEY(snapshot_id,repo_id) REFERENCES snapshots(snapshot_id,repo_id),
  FOREIGN KEY(snapshot_id,parent_id) REFERENCES entities(snapshot_id,entity_id) DEFERRABLE INITIALLY DEFERRED,
  CHECK(parent_id IS NULL OR parent_id<>entity_id),
  CHECK((parent_id IS NULL AND depth=0 AND kind='workspace') OR (parent_id IS NOT NULL AND depth>0)),
  CHECK((start_line IS NULL AND end_line IS NULL) OR
        (start_line IS NOT NULL AND end_line IS NOT NULL AND start_line>=1 AND end_line>=start_line)),
  CHECK(rel_path IS NULL OR (length(rel_path)>0 AND substr(rel_path,1,1)<>'/'
    AND instr(rel_path,char(92))=0 AND instr(rel_path,':')=0
    AND instr('/'||rel_path||'/','/../')=0 AND instr('/'||rel_path||'/','/./')=0)),
  CHECK((sort='external' AND is_external=1) OR (sort<>'external' AND is_external=0))
) STRICT;
CREATE UNIQUE INDEX entities_one_root ON entities(snapshot_id) WHERE parent_id IS NULL;
CREATE INDEX entities_children ON entities(snapshot_id,parent_id,entity_id);
CREATE INDEX entities_lookup ON entities(snapshot_id,repo_id,qualified_name,kind);
CREATE INDEX entities_path ON entities(snapshot_id,repo_id,rel_path,start_line);
CREATE INDEX entities_ast ON entities(snapshot_id,ast_body_hash,entity_id) WHERE ast_body_hash IS NOT NULL;
CREATE INDEX entities_wl ON entities(snapshot_id,wl_3hop_hash,entity_id) WHERE wl_3hop_hash IS NOT NULL;
CREATE INDEX entities_qi ON entities(snapshot_id,qi_cluster_id,entity_id) WHERE qi_cluster_id IS NOT NULL;

CREATE TABLE relationships (
  relationship_id TEXT NOT NULL CHECK(length(relationship_id)>0),
  snapshot_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  source_subject_id TEXT NOT NULL,
  target_subject_id TEXT NOT NULL,
  family TEXT NOT NULL CHECK(family IN ('static','runtime','similarity','history','expected')),
  subtype TEXT NOT NULL CHECK(length(subtype)>0),
  direction TEXT NOT NULL CHECK(direction IN ('directed','symmetric')),
  resolution_status TEXT NOT NULL CHECK(resolution_status IN ('exact','candidate','unresolved','observed','declared')),
  confidence REAL CHECK(confidence IS NULL OR (confidence>=0 AND confidence<=1)),
  weight REAL NOT NULL DEFAULT 1 CHECK(weight>=0 AND weight<=1e15),
  weight_unit TEXT NOT NULL CHECK(weight_unit IN ('edge_count','call_count','calls_per_second','similarity_score','cochange_count')),
  occurrence_key TEXT NOT NULL CHECK(length(occurrence_key)>0),
  PRIMARY KEY(snapshot_id,relationship_id),
  UNIQUE(snapshot_id,occurrence_key),
  FOREIGN KEY(snapshot_id) REFERENCES snapshot_sets(snapshot_id),
  FOREIGN KEY(snapshot_id,source_id) REFERENCES entities(snapshot_id,entity_id),
  FOREIGN KEY(snapshot_id,target_id) REFERENCES entities(snapshot_id,entity_id),
  FOREIGN KEY(snapshot_id,source_subject_id) REFERENCES entities(snapshot_id,entity_id),
  FOREIGN KEY(snapshot_id,target_subject_id) REFERENCES entities(snapshot_id,entity_id),
  CHECK(direction<>'symmetric' OR source_id<=target_id),
  CHECK(family NOT IN ('static','runtime','expected') OR direction='directed'),
  CHECK((family='runtime' AND resolution_status='observed') OR
    (family='expected' AND resolution_status='declared') OR
    (family NOT IN ('runtime','expected') AND resolution_status IN ('exact','candidate','unresolved')))
) STRICT;
CREATE INDEX relationships_out ON relationships(snapshot_id,source_id,family,subtype,relationship_id);
CREATE INDEX relationships_in ON relationships(snapshot_id,target_id,family,subtype,relationship_id);
CREATE INDEX relationships_filter ON relationships(snapshot_id,family,resolution_status,relationship_id);

CREATE TABLE evidence (
  evidence_id TEXT NOT NULL CHECK(length(evidence_id)>0),
  snapshot_id TEXT NOT NULL,
  relationship_id TEXT NOT NULL,
  category TEXT NOT NULL CHECK(category IN ('ast_exact','static_candidate','unresolved','dynamic_observed','declared','similarity','history')),
  extractor_version TEXT NOT NULL CHECK(length(extractor_version)>0),
  repo_id TEXT NOT NULL,
  rel_path TEXT,
  start_line INTEGER,
  end_line INTEGER,
  revision TEXT NOT NULL CHECK(length(revision)>0),
  confidence REAL CHECK(confidence IS NULL OR (confidence>=0 AND confidence<=1)),
  trace_ref TEXT,
  window_start TEXT,
  window_end TEXT,
  details_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(details_json) AND json_type(details_json)='object'),
  PRIMARY KEY(snapshot_id,evidence_id),
  FOREIGN KEY(snapshot_id,relationship_id) REFERENCES relationships(snapshot_id,relationship_id),
  FOREIGN KEY(snapshot_id,repo_id) REFERENCES snapshots(snapshot_id,repo_id),
  CHECK((start_line IS NULL AND end_line IS NULL) OR
    (start_line IS NOT NULL AND end_line IS NOT NULL AND start_line>=1 AND end_line>=start_line)),
  CHECK((window_start IS NULL AND window_end IS NULL) OR
    (window_start IS NOT NULL AND window_end IS NOT NULL AND window_start<window_end)),
  CHECK(category<>'dynamic_observed' OR (trace_ref IS NOT NULL AND window_start IS NOT NULL))
) STRICT;
CREATE INDEX evidence_by_relationship ON evidence(snapshot_id,relationship_id,evidence_id);

-- A hyperedge is (snapshot_id,incidence_id); each row is one member, never a dependency edge.
CREATE TABLE documentary_incidences (
  snapshot_id TEXT NOT NULL,
  incidence_id TEXT NOT NULL CHECK(length(incidence_id)>0),
  fragment_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('discusses','documents','rationale_for','cites')),
  PRIMARY KEY(snapshot_id,incidence_id,entity_id),
  FOREIGN KEY(snapshot_id,fragment_id) REFERENCES entities(snapshot_id,entity_id),
  FOREIGN KEY(snapshot_id,entity_id) REFERENCES entities(snapshot_id,entity_id)
) STRICT;
CREATE INDEX documentary_by_entity ON documentary_incidences(snapshot_id,entity_id,incidence_id);
CREATE INDEX documentary_by_fragment ON documentary_incidences(snapshot_id,fragment_id,incidence_id);

CREATE TABLE analysis_views (
  snapshot_id TEXT NOT NULL,
  view_id TEXT NOT NULL,
  grouping_json TEXT NOT NULL CHECK(json_valid(grouping_json) AND json_type(grouping_json)='object'),
  filter_json TEXT NOT NULL CHECK(json_valid(filter_json) AND json_type(filter_json)='object'),
  filter_hash TEXT NOT NULL CHECK(length(filter_hash)=64 AND filter_hash NOT GLOB '*[^0-9a-f]*'),
  algorithm_version TEXT NOT NULL,
  PRIMARY KEY(snapshot_id,view_id),
  UNIQUE(snapshot_id,view_id,filter_hash),
  FOREIGN KEY(snapshot_id) REFERENCES snapshot_sets(snapshot_id)
) STRICT;
CREATE TABLE view_representatives (
  snapshot_id TEXT NOT NULL,
  view_id TEXT NOT NULL,
  representative_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('entity','residual','qi','conceptual','unmapped')),
  entity_id TEXT,
  parent_shell_id TEXT,
  member_count INTEGER NOT NULL CHECK(member_count>0),
  PRIMARY KEY(snapshot_id,view_id,representative_id),
  FOREIGN KEY(snapshot_id,view_id) REFERENCES analysis_views(snapshot_id,view_id),
  FOREIGN KEY(snapshot_id,entity_id) REFERENCES entities(snapshot_id,entity_id),
  FOREIGN KEY(snapshot_id,parent_shell_id) REFERENCES entities(snapshot_id,entity_id),
  CHECK((kind='entity' AND entity_id IS NOT NULL) OR (kind<>'entity' AND entity_id IS NULL))
) STRICT;
CREATE TABLE partition_members (
  snapshot_id TEXT NOT NULL,
  view_id TEXT NOT NULL,
  atom_id TEXT NOT NULL,
  representative_id TEXT NOT NULL,
  PRIMARY KEY(snapshot_id,view_id,atom_id),
  FOREIGN KEY(snapshot_id,atom_id) REFERENCES entities(snapshot_id,entity_id),
  FOREIGN KEY(snapshot_id,view_id,representative_id)
    REFERENCES view_representatives(snapshot_id,view_id,representative_id)
) STRICT;
CREATE INDEX partition_by_rep ON partition_members(snapshot_id,view_id,representative_id,atom_id);

CREATE TABLE quotient_projections (
  snapshot_id TEXT NOT NULL,
  view_id TEXT NOT NULL,
  projection_id TEXT NOT NULL,
  source_rep_id TEXT NOT NULL,
  target_rep_id TEXT NOT NULL,
  family TEXT NOT NULL CHECK(family IN ('static','runtime','similarity','history','expected')),
  subtype TEXT NOT NULL,
  direction TEXT NOT NULL CHECK(direction IN ('directed','symmetric')),
  resolution_status TEXT NOT NULL CHECK(resolution_status IN ('exact','candidate','unresolved','observed','declared')),
  weight_unit TEXT NOT NULL CHECK(weight_unit IN ('edge_count','call_count','calls_per_second','similarity_score','cochange_count')),
  witness_count INTEGER NOT NULL CHECK(witness_count>0),
  evidence_count INTEGER NOT NULL CHECK(evidence_count>0),
  aggregated_weight REAL NOT NULL CHECK(aggregated_weight>=0 AND aggregated_weight<=1e15),
  is_internal INTEGER NOT NULL CHECK(is_internal IN (0,1)),
  PRIMARY KEY(snapshot_id,view_id,projection_id),
  UNIQUE(snapshot_id,view_id,source_rep_id,target_rep_id,family,subtype,direction,resolution_status,weight_unit),
  FOREIGN KEY(snapshot_id,view_id,source_rep_id)
    REFERENCES view_representatives(snapshot_id,view_id,representative_id),
  FOREIGN KEY(snapshot_id,view_id,target_rep_id)
    REFERENCES view_representatives(snapshot_id,view_id,representative_id),
  CHECK(is_internal=(source_rep_id=target_rep_id)),
  CHECK(direction<>'symmetric' OR source_rep_id<=target_rep_id)
) STRICT;
CREATE INDEX quotient_out ON quotient_projections(snapshot_id,view_id,source_rep_id,projection_id);
CREATE INDEX quotient_in ON quotient_projections(snapshot_id,view_id,target_rep_id,projection_id);
CREATE TABLE quotient_witness_map (
  snapshot_id TEXT NOT NULL,
  view_id TEXT NOT NULL,
  projection_id TEXT NOT NULL,
  relationship_id TEXT NOT NULL,
  PRIMARY KEY(snapshot_id,view_id,projection_id,relationship_id),
  UNIQUE(snapshot_id,view_id,relationship_id),
  FOREIGN KEY(snapshot_id,view_id,projection_id)
    REFERENCES quotient_projections(snapshot_id,view_id,projection_id),
  FOREIGN KEY(snapshot_id,relationship_id) REFERENCES relationships(snapshot_id,relationship_id)
) STRICT;
CREATE INDEX witness_reverse ON quotient_witness_map(snapshot_id,relationship_id,view_id);

CREATE TABLE level_scc_condensations (
  snapshot_id TEXT NOT NULL,
  view_id TEXT NOT NULL,
  filter_hash TEXT NOT NULL,
  level_key TEXT NOT NULL CHECK(length(level_key)>0),
  representative_id TEXT NOT NULL,
  scc_id TEXT NOT NULL CHECK(length(scc_id)>0),
  component_size INTEGER NOT NULL CHECK(component_size>0),
  dag_rank INTEGER NOT NULL CHECK(dag_rank>=0),
  has_self_loop INTEGER NOT NULL CHECK(has_self_loop IN (0,1)),
  PRIMARY KEY(snapshot_id,view_id,filter_hash,representative_id),
  FOREIGN KEY(snapshot_id,view_id,filter_hash) REFERENCES analysis_views(snapshot_id,view_id,filter_hash),
  FOREIGN KEY(snapshot_id,view_id,representative_id)
    REFERENCES view_representatives(snapshot_id,view_id,representative_id)
) STRICT;
CREATE INDEX scc_members ON level_scc_condensations(snapshot_id,view_id,filter_hash,scc_id,representative_id);

CREATE TABLE layouts (
  snapshot_id TEXT NOT NULL,
  layout_version TEXT NOT NULL CHECK(length(layout_version)>0),
  seed TEXT NOT NULL CHECK(length(seed)>0),
  entity_id TEXT NOT NULL,
  center_x REAL NOT NULL CHECK(abs(center_x)<=1e12),
  center_y REAL NOT NULL CHECK(abs(center_y)<=1e12),
  center_z REAL NOT NULL CHECK(abs(center_z)<=1e12),
  radius REAL NOT NULL CHECK(radius>0 AND radius<=1e12),
  PRIMARY KEY(snapshot_id,layout_version,seed,entity_id),
  FOREIGN KEY(snapshot_id,entity_id) REFERENCES entities(snapshot_id,entity_id)
) STRICT;

CREATE TABLE analysis_results (
  snapshot_id TEXT NOT NULL,
  analysis_id TEXT NOT NULL,
  algorithm_version TEXT NOT NULL,
  scope_json TEXT NOT NULL CHECK(json_valid(scope_json) AND json_type(scope_json)='object'),
  result_json TEXT NOT NULL CHECK(json_valid(result_json) AND json_type(result_json)='object'),
  PRIMARY KEY(snapshot_id,analysis_id),
  FOREIGN KEY(snapshot_id) REFERENCES snapshot_sets(snapshot_id)
) STRICT;
COMMIT;
