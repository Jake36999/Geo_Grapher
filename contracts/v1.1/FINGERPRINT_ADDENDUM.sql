-- Geo Grapher v1.1 fingerprint addendum; additive, user_version unchanged.
CREATE TABLE IF NOT EXISTS entity_fingerprints (
  snapshot_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  algorithm_version TEXT NOT NULL CHECK(algorithm_version='entity-fingerprint-v1'),
  span_sha256 TEXT, ast_body_hash TEXT, signature_hash TEXT,
  ts_guard_hash TEXT, exact_out_edges_hash TEXT, wl_3hop_hash TEXT,
  PRIMARY KEY(snapshot_id, entity_id),
  FOREIGN KEY(snapshot_id, entity_id) REFERENCES entities(snapshot_id, entity_id)
) STRICT;
CREATE INDEX IF NOT EXISTS fp_ast ON entity_fingerprints(snapshot_id, ast_body_hash) WHERE ast_body_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS fp_sig ON entity_fingerprints(snapshot_id, signature_hash, ts_guard_hash) WHERE signature_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS fp_wl ON entity_fingerprints(snapshot_id, wl_3hop_hash) WHERE wl_3hop_hash IS NOT NULL;
