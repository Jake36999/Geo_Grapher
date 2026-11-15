"""Generate the C0 review from explicitly reviewed classifications, never execute a tool."""
import importlib.util
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description='Reproduce the pre-fix C0 census; not a policy implementation or post-fix certification')
parser.add_argument('--native-root', type=Path, required=True)
parser.add_argument('--geo-root', type=Path, required=True)
parser.add_argument('--geo-python', required=True)
args = parser.parse_args()
NATIVE = args.native_root.resolve(); GEO = args.geo_root.resolve()
sys.path[:0] = [str(NATIVE / 'src'), str(GEO / 'src'), str(GEO)]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


# Control receipts/counts/configuration, not source/work text or materialised content.
# Everything else is conservatively treated as a potential content surface.
METADATA = set('''accept_artifact accept_workflow add_candidate advance answer archive_note
audit_targets batch_cancel branch_session capabilities capability_install capability_propose
check_notes checkpoint claim_run_preflight clerk_submit close_brief close_session cohort_reviewed
community_rebuild concept_candidates decide desk_pin desk_touch desk_unpin doctor embed_index
engagement_close engagement_propose engagement_start extend_budget filters gitignore_ensure index
index_status intake_run lens_drop list_files log_use model_catalog_status model_expectation_propose
note_move park_session process_approved promote_offering queue_remove queue_retry queue_source
ranking_benchmark ranking_candidate_generate ranking_restore ranking_select ranking_status
record_application record_assumptions record_synthesis reduce_round refile_source reflection_accept
reject_artifact request_budget request_evidence review_due_open rewind_session rules scout_discover
search_feedback set_effort set_requirement stage_artifact staging_flag task_done task_route
understanding_record update_plan validate_workflow vault_commit vault_push vault_status verify_access
views_refresh withdraw_reference'''.split())
RAW = {'read_file','read_source_file','read_project','read_evidence','read_result','extract_materialize'}
CATALOG = {'search','search_work','get_note','web_search','read_url','scout_rank','scout_expand','research_round','topics_list'}
CONVERSION = {'ocr_pdf','pdf_to_markdown'}
WORK = {'staging_list','staging_show','staging_preview','staging_review','staging_decide','deep_read','deep_read_note',
        'ingest','sweep','draft_offering','reflection_draft','v1_import_plan','v1_import_stage','v1_import_status'}

import resource_librarian.tools  # noqa: E402,F401
from resource_librarian.registry import REGISTRY
native = load('native_access_audit', NATIVE / 'scripts/audit_tool_access.py')
assert METADATA <= set(REGISTRY._tools), 'classification must not silently retain renamed tools'
rows = []
for spec in sorted(REGISTRY._tools.values(), key=lambda item:item.name):
    content = spec.name not in METADATA
    fixes = [] if not content else ['S1']
    if spec.name in RAW or spec.name == 'clerk_next': fixes += ['S4']
    if spec.name in CATALOG: fixes += ['S4','S5']
    if spec.name in CONVERSION: fixes += ['S2','S3','S4']
    if spec.name in WORK: fixes += ['R']
    if spec.name in {'project_map','project_scan','read_project','index','get_note','search'} and content: fixes += ['S6']
    if spec.name in {'model_catalog_adopt','model_catalog_status','model_expectation_propose','v1_import_plan','v1_import_stage'} and content: fixes += ['S6b']
    row = native.declaration(spec, content=content, status='diverges' if content else 'n/a', fixes=sorted(set(fixes)))
    row['reason'] = ('No explicit owner_created/generated/third_party contract on potentially mixed output; review the named follow-up steps.'
                     if content else 'Control/receipt/configuration or counts; not counted as a content-access pass.')
    if spec.name in RAW: row['reason'] += ' Raw content is available at registry consult tier without the new catalogue/graph/target grant.'
    if spec.name in CONVERSION: row['reason'] += ' The produced conversion is user-visible and is not yet the required hidden, page-anchored library work.'
    rows.append(row)
review = dict(version='access-audit-v1', authorship_vocabulary=list(native.AUTHORSHIP),
    scope='All shipped native registry tools; runtime MCP adapters and Wave L non-registry paths are supplemental, not silently certified.', tools=rows)
(NATIVE / 'docs/tool-access-declarations.json').write_text(json.dumps(review, indent=2) + '\n', encoding='utf-8')

geo = load('geo_access_audit', GEO / 'scripts/audit_tool_access.py')
rows = []
env = {**os.environ, 'PYTHONPATH': str(GEO / 'src') + ';' + str(GEO)}
discovered = subprocess.run([args.geo_python,
    str(GEO / 'scripts/audit_tool_access.py'), '--discover'], capture_output=True, check=True, env=env)
for name in json.loads(discovered.stdout):
    surface, operation = name.split(':', 1)
    metadata = operation in {'get_corpus_status','paper_get_corpus_status'}
    content = not metadata
    fixes = [] if metadata else ['S1', 'S4']
    if 'paper_' in operation or surface == 'paper': fixes = [] if metadata else ['S1','S3','S4','S5']
    if operation == 'list_graphs': fixes = ['S1','B2']
    if operation == 'annotate_document': fixes = ['S1','S2']
    source = 'src/geographer/server.py' if surface == 'canonical' else 'pipeline/mcp_doc_graph.py' if surface == 'paper' else 'src/geographer/graph_server.py'
    rows.append(dict(tool=name, minimum_tier='connection-scoped (no native registry tier)',
        actors=['person', 'lead', 'research helper', 'Clerk/Scribe connection principal: own-only; native models have no external registry tools'] if surface == 'scoped' else ['person', 'connected MCP client (not tier-labelled)'],
        returns_content=content, authorship_may_return=list(native.AUTHORSHIP) if content else [],
        status='diverges' if content else 'n/a', fixes=fixes, evidence=dict(path=source, symbol=operation),
        reason='Wave L scoped role/provenance boundaries exist; authorship/domain and the new source-access route are not yet enforced.' if content
               else 'Corpus counters or bridge metadata; not a content-access pass.'))
(GEO / 'docs/tool-access-declarations.json').write_text(json.dumps(dict(version='access-audit-v1',
    authorship_vocabulary=list(native.AUTHORSHIP), tools=rows), indent=2) + '\n', encoding='utf-8')

def table(review_rows):
    lines = ['| Tool | Minimum tier | Possible actors, subject to gates | Possible authorship | Status | Fix | Source evidence |',
             '|---|---|---|---|---|---|---|']
    for row in review_rows:
        evidence = row['evidence']; source = evidence['path'] + (':' + str(evidence['line']) if 'line' in evidence else '')
        lines.append('| ' + ' | '.join([row['tool'], row['minimum_tier'], '; '.join(row['actors']),
            ', '.join(row['authorship_may_return']) or 'n/a', row['status'], ', '.join(row['fixes']) or '—', source]) + ' |')
    return '\n'.join(lines)

native_content = sum(row['returns_content'] for row in review['tools']); geo_content = sum(row['returns_content'] for row in rows)
text = f'''# C0 content-tool conformance sweep

Review baseline: native Wave L `54f17b5`, Geo Wave L `495d689`/`4e773a2`. This is a pre-fix census against the newly approved Part A0 contract. It does not apply S1–S6b or R.

The census includes all 180 native registrations, even metadata/control tools, plus every Geo MCP surface (canonical, graph-scoped, standalone paper and opt-in annotations). A materialised content path, arbitrary nested tool result, draft, plan or source text counts conservatively as potential content. Pure control receipts/counts are n/a. Unknown authorship is not silently interpreted as owner_created.

**Full-contract conformance: 0/{native_content} native potential-content tools and 0/{geo_content} Geo potential-content operations.** This is not a claim that the existing permission boundaries fail: the new authorship contract is absent, so no mixed-content tool earns full conformance merely from its tier or Wave L provenance label. Metadata/control rows do not improve this score. Surface duplicates are counted separately because wrappers can change exposure; canonical 1.0/1.1 share one implementation and one row per operation.

Actors are possible entry points, not unconditional authority. The native registry's consult/contribute/curate tiers are distinct from model role tiers 1/2/3. MCP agents are capped at contribute; a lead is further bundle/profile-gated; helpers have the explicit HELPER_TOOLS allow-list; a task worker sees only its queue payload. Scribe models receive no registry tools. Live runtime MCP installations are not enumerated: no connected Core was used. Their generic adapter is reviewed separately below, not asserted compliant.

## Native registry — {len(review['tools'])} tools

{table(review['tools'])}

## Geo MCP — {len(rows)} operations

{table(rows)}

## Supplemental Wave L paths and dynamic adapters

| Surface | Actors | Content/authorship today | Status | Follow-up |
|---|---|---|---|---|
| GET /api/folders; POST /api/folders/survey | Person via Core | Inventory, paths and staged suggestions; purpose only, no authorship or DIK inventory record | diverges | S1, R |
| POST /api/folders/draft | Person-approved qualified Clerk, metadata only | Generated staged description; provenance check not yet wired | diverges | S1, R; production drafting remains off pending owner approval |
| POST /api/folders/accept | Person only | Frozen-purpose decision and static graph application; no canonical authorship propagation | diverges | S1, R |
| init-workspace --survey-in | Native ingestion/operator | Shared metadata fingerprint and suggested strata; no evidence/DIK record | diverges | S1, R |
| apply-folder-review | Person-reviewed native caller | Static source graph with immutable snapshot, purpose/stratum, provenance | diverges | S1, R |
| review-mcp-config | Operator | Generated configuration only; never connects or accepts a server | n/a | Existing Wave L own-only Clerk principal is retained |
| Native dynamic MCP adapter (mcp_client._make_fn) | Lead; bounded Core packet-fetch expansion | Arbitrary external content; untrusted=True wrapper but plain read/open_world=False registration | diverges | S1 must test closure outside audited sessions; S4 targets/grants |
| Native writer/registry read-only guard | All native writers | Control; typed FOLDER_READ_ONLY, accepted internal child override, attached sources read-only | n/a | Retain Wave L checks while R changes ingestion |
| dispatch_plan tier-3 preflight | Lead orchestrator | PLAN_SCOPE before packets/models for direct third-party graph anchoring | n/a | Keep L4(a); S4 adds a bounded-target route, not free graph access |
| Bridge creation/proposals | Person/operator | Reference-only, owner decision across own/external boundary | n/a | Retain L4(d) and W3-5 firewall |
| Credential guards | All source readers | Refused names only; credential bodies never inspected | n/a | Retain L5; D6 graphify output hygiene is separate |

The CI guard requires an individual explicit declaration for every shipped registry/MCP operation, including new metadata tools. There is no wildcard approval. Native function/schema fingerprints invalidate stale reviews after implementation changes. These tests only ensure review coverage; **passing them is not a policy-conformance pass**. Runtime dynamic tools need a per-install declaration when S1 wires that surface; the generic adapter does not certify unknown servers.
'''
(NATIVE / 'docs/access-conformance-sweep.md').write_text(text, encoding='utf-8')
print(json.dumps(dict(native_tools=len(review['tools']), native_content=native_content, geo_operations=len(rows),
                     geo_content=geo_content, full_contract_conforms=0), indent=2))
