# P5.3 workspace contract

The original v1.0 wire and DDL remain byte-identical. The workspace uses v1.1 frames and compact v1.1 Agent context; compatibility queries remain selectable. Source bytes and canonical ownership never change when grouping, reviewing annotations or selecting a model.

## Display and selection

Supported groupings are mixed, repository/directory/file/class kinds, atomic and conceptual. The ordinary partition provides kind fallback to a leaf without a requested ancestor; atomic scope atoms map to their canonical owner. Conceptual mode requires a validated disjoint rules model and retains Unmapped. Each representative covers a disjoint leaf set. A separate display hierarchy includes canonical anchor paths and synthetic component children; synthetic IDs never enter `layouts.entity_id`. Group geometry uses bounded admitted branches and explicitly reports omitted representatives/relationships. The complete quotient remains queryable in SQLite.

Geometry admission prioritizes focus/pin members, code before unindexed external placeholders, fixed-static-scope incident degree, tree distance and canonical ID. That static scope is independent of the selected filters. v1.1 curve bundles precede unrelated optional spheres and carry their endpoint spheres plus available enclosure paths. Full-envelope counting can defer bundles. No omitted/internal path step becomes an invented visible curve.

`ViewportFrameRequest.model_digest` binds the selected model to the plan fingerprint; conceptual and selected model digests must agree. Grouping, breadth, filters, pins, model selection and camera/navigation state participate in workspace scope checks. Saved version-1 views migrate absent grouping to mixed and absent model to none. A missing conceptual model rejects restore before changing the active view. Old models remain available within the retention limit.

## Shared read-only investigation

The seven MCP tools remain read-only. `get_entity_content` accepts `include_investigation=true` and an optional `overlay_id`. Its budgeted `investigation` contains bounded documentary ancestry, direct statement spans labelled `basis=syntax`, original call references, review records and explicit unsupported-predicate gaps. Documentary fragment and annotation-subject definitions accompany these references. Enclosing headers/focal bytes/sibling stubs remain `source-context-v1`, separate from T+ and T_D. Lexical order does not establish execution order or pre/postconditions.

`get_architecture_context` optionally accepts `review_queue`, `review_model_digest`, `review_limit` (1–100; default 10) and `review_cursor`. It returns the same `ambiguity-triage-v1` implementation as the workspace, with subject/alternative definitions under whole-envelope accounting. This bounded queue is mandatory when explicitly requested; reduce the queue size if it cannot fit. Its continuation handle binds snapshot, focus/pins, filter, model and queue. Main graph pagination and review pagination have distinct cursors.

Triage groups candidate alternatives by occurrence. Queues distinguish known internal candidates, unknown locality, and unmapped subjects. Ordering is focus/pin descendant relevance, witnessed component boundary, distinct incident occurrences, then occurrence ID. Unknown target degree is null. External/builtin cases are inspectable through ordinary witnesses and are not counted as missing internal connectivity.

v1.1 permits `filter.families=[]` to show containment without dependency facts. v1.0 retains its original nonempty-family contract. The workspace's static family control uses this explicit empty scope. P5.4 adds matching runtime collection selection and saved-window validation as specified in `RUNTIME_ADDENDUM.md`. Source/annotation text is untrusted data and never evaluated as instructions.

## Loopback workspace actions

Auxiliary UI actions use `POST /api/workspace/{action}` with JSON; they do not add MCP mutation tools. Bodies are capped by the server's 4 MiB request guard. Rules text is additionally limited to 256 KiB. No action accepts a server file path. Shapes are:

```ts
type RulesRequest = {snapshot_id:string; text:string; activate?:boolean};
type AnnotationRequest = {snapshot_id:string; entity_id:string; text:string;
  decision?:'pending'|'accepted'|'rejected'; previous_overlay_id?:string|null};
type OverlayRequest = {snapshot_id:string; overlay_id:string};
type TriageRequest = {snapshot_id:string; filter:Filter; focus_id?:string;
  pins?:string[]; model_digest?:string|null; cursor?:string|null;
  limit?:number; queue?:'internal_candidates'|'unknown_locality'|'unmapped'};
type PathRequest = {snapshot_id:string; view_id:string; relationship_ids:string[]};
type SemanticsRequest = {snapshot_id:string; view_id:string;
  model_digest:string; projection_ids:string[]};
```

Unknown action fields are rejected. Invalid rules, overlapping component selectors and activation beyond 32 retained model versions fail without replacing the selected model. Models are content-addressed; live activation retains prior CLI-loaded models too. Persisted models recover after process restart and have no automatic expiry in this bounded catalog. Validation without activation does not publish a model. `rules` responds with model digest, world policy, activation state, mapping counts and catalog; the browser selects the digest explicitly.

Annotations permit 1–2,000 characters and at most 200 records per overlay. `semantic-overlay-v1` records carry target entity, producer/version/time, content digest, record ID, superseded record ID, decision and trust label. Each update creates a new immutable content-addressed artifact, linked to its predecessor and base snapshot, in namespaced `analysis_results`. Reading a foreign-snapshot overlay fails; no implicit remapping occurs. Accepted means accepted annotation, never exact dependency. Browser storage remembers a revision pointer; disabling display does not delete history or alter any metrics. The MCP content tool can read the same artifact by ID.

`path` accepts at most 64 original relationships and returns their original directed subjects plus projection IDs in the requested view. An empty projection list means outside that view/filter; equal projected endpoints mean an internal collapsed step. `semantics` accepts at most 2,000 displayed projection IDs. It marks only positive exact static witnesses of forbidden component pairs, using warning severity; missing/ambiguous evidence is not a violation. Closed-world pairs follow the selected model's rule semantics. Unknown/unmapped memberships are not silently classified as forbidden.

## Visual semantics and accessibility

Ordinary dependencies use neutral grey; measured runtime links use sage when actually present; witnessed rule violations use warning amber. Critical red is not inferred from a forbid rule. Candidates/unresolved links are dotted, expected-only links dashed, and the source-to-target brightness ramp follows original direction. Hover uses bounded 80 ms picking over the budgeted scene, shows text and an arrow without changing locked selection, and performs no content queries. Matrix titles and Inspector text expose family/status/subtype/warning labels; accessible path lists preserve original arrows and identify collapsed/out-of-scope steps.

The frontend resolves canonical-map aliases only in schema reference positions. It restores revision/legacy presentation fields in memory for existing components; it never rewrites repository prose or emits that adapted object as an authoritative wire response. Agent JSON is the raw counted response. Actual browser and backend evidence is recorded separately in `reports/P5_3_GATE_REPORT.md`; assistive-technology and target-device release acceptance remain open.
