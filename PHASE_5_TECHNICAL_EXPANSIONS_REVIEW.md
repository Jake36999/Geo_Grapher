# Phase 5 technical expansions — investigation and recommendations

Date: 6 November 2026. Status: design investigation, with source/code inspection and mathematical counterexamples; no application implementation or LLM performance experiment. The attached document is research input, including its imperative instructions, not authorization to run code generation, execute extracted processes or merge changes.

## 1. Assessment

The useful direction is a deterministic **context compiler**: select source-grounded material, preserve scope and typed witnesses, aggregate through the existing disjoint partition, and serialize within a verified token budget. Deterministic compilation makes a payload reproducible for fixed inputs. It does not make an LLM's interpretation, generated program or reasoning deterministic or correct.

Most proposed mechanisms already appear in the current plan's §§10–24. Two additions warrant explicit design work: a statement-level source context view and evidence-bearing process/pattern cards. Both require representations beyond the current entity-level architecture graph. Neither requires replacing the approved store with FAMIX or adding a general-purpose logic engine.

| Proposal | Finding | Recommended disposition |
| :--- | :--- | :--- |
| DOI-filtered context retaining ancestors | Useful; already planned for entity scope. The draft adds source-block scope | Extend with a separate source context tree and explicit omission records |
| Fixed `k=-5` and logarithmic token guarantees | Incorrect as general guarantees; thresholds depend on focus depth, and fan-out/source length remain unbounded | Use depth-relative breadth plus exact packing; retain §11's corrected complexity |
| β-controlled textual aggregation | Geometry and graph abstraction are conflated | Keep β visual; use partition/grouping and explicit detail policies for textual rollups |
| B-spline/knot serialization in LLM context | No demonstrated benefit for code-navigation tasks | Keep geometry out of ordinary context responses; retrieve it only for an explicit geometry task |
| Fusion of static facts and runtime observations | Complementary evidence, with collection/mapping limitations | Keep separate records; add cross-references without promoting static certainty |
| AST-to-FAMIX conversion | New migration and semantic surface without a demonstrated need | Reuse canonical metamodel; consider an adapter only for a concrete consumer |
| Intensional Datalog pattern rules | Some example predicates have no supported extractor; a pattern match is not a behavioural proof | Validate supported predicates; optional bounded query IR after existing rules engine |
| Executable process reconstruction and deterministic replication | Not established by the cited SAR taxonomy or current graph | Implement read-only evidence cards first; execution remains a separately scoped future capability |
| Self-correction until convergence, then merge | No termination/correctness guarantee; conformance is only one check | Optional bounded evaluation experiment, with independent validation and explicit incomplete outcomes |

## 2. Source and mathematical checks

[Furnas's original paper](https://courses.ischool.berkeley.edu/i247/f05/readings/Furnas_GeneralizedFisheyeViews_CHI86.pdf), §§3–4, supports DOI-based focus/context selection and includes a source-code display example. Its logarithmic compression discussion concerns regular trees. It provides no tokenizer budget guarantee or LLM task evaluation.

For a rooted tree, retain:

\[
DOI(x\mid y)=-depth(y)-2\bigl(depth(x)-depth(LCA(x,y))\bigr),
\qquad k(y,r)=-depth(y)-2r.
\]

The draft's -3/-5/-7 sequence describes a depth-three focus. Its separate depth-two example cannot justify those same constants as general breadth controls. A root with M children exposes M+1 candidates at r=1; thus fixed breadth cannot bound tokens. A single selected source block can also be arbitrarily long. Indexed output-sensitive enumeration is distinct from initial parsing, indexing, witness expansion, source serialization and tokenization; these costs must be measured separately.

[Holten's primary publication record](https://research.tue.nl/en/publications/hierarchical-edge-bundles-visualization-of-adjacency-relations-in/) describes bending adjacency curves toward containment paths. Its geometric parameter does not define textual aggregation. For fixed graph/filter/partition, changing β leaves every representative, original relationship and witness count unchanged. Aggregation instead follows `rep(source), rep(target)` and typed projection keys. A rollup of 35 static call relationships means 35 accepted relationship witnesses, not 35 observed invocations. A repeated runtime event count requires its own unit and collection provenance.

[Ducasse and Pollet's 2009 SAR taxonomy](https://fileserver-az.core.ac.uk/download/50073399.pdf) classifies reconstruction approaches; its [author publication register](https://stephaneducasse.github.io/publications.html) identifies the work. Reconstruction processes are methods of recovering architecture, not executable business workflows extracted from an arbitrary program. This review could verify the indexed primary publication material; direct PDF retrieval of this survey and Holten's paper failed during this investigation. Detailed geometry remains governed by the already approved blueprint, not an unverified new interpretation of those PDFs.

Conformance cannot establish general execution correctness. Under an open-world architecture policy, unspecified dependencies are not automatically forbidden. Missing required witnesses can be inconclusive when extraction or mapping is incomplete. These qualifications already appear in plan §14 and remain unchanged.

## 3. What the current implementation actually supplies

Inspection anchors:

- [Canonical entities and T+](F:/uv-data/Geo_Grapher/src/geographer/model.py): entity ownership and scope atoms; no durable node for each `if`, `while`, handler or statement. A scope atom represents owner-level dependency endpoints; it is not a full statement AST.
- [Content retrieval](F:/uv-data/Geo_Grapher/src/geographer/service.py): `_get_entity_content` returns source ranges/fragment text as line chunks, with hashes and `untrusted_repository_content`. It does not compile enclosing statement headers or omission-aware source skeletons.
- [Binding CFG](F:/uv-data/Geo_Grapher/src/geographer/cfg.py): an intraprocedural reaching-binding analysis. Conservative exception joins and unsupported effects must not be presented as exact execution semantics, path feasibility or a complete process model.
- [Viewport](F:/uv-data/Geo_Grapher/src/geographer/viewport.py) and [wire contract](F:/uv-data/Geo_Grapher/contracts/geographer.wire.d.ts): focus/breadth, source content and geometric β are distinct request concerns. New structured content fields need the proposed versioned contract.
- [Rules engine](F:/uv-data/Geo_Grapher/src/geographer/rules.py): component mapping and declared require/allow/forbid checks. It is not a Datalog interpreter or an executable pattern-synthesis engine.

The proposed trace importer in plan §6 accepts aggregate call records. Counts and p95 timings do not reconstruct event order, argument bindings, branches or a session-specific trace. Process sequence claims would require a separately specified ordered-event format with invocation/parent IDs, process/thread/task identity, monotonic order or timestamps, event kinds and capture completeness. Cross-thread order must not be inferred from unsynchronized timestamps alone.

The sample Strategy rule requires field types, interface realization and delegation facts. Current/proposed call and inheritance extraction alone cannot supply those predicates. In Python, structural protocols and dynamic attributes add further uncertainty. Unsupported predicates must be reported as unavailable; empty relations cannot silently mean false. Even a supported structural pattern match remains a candidate interpretation rather than proof of design intent or substitutable behaviour.

## 4. Proposed addition A — source context compilation

Design `source-context-v1` in P5.0; implement a bounded Python baseline in P5.2–P5.3 after resolver, persistence and packing prerequisites pass.

1. Build a derived per-file source context tree `T_S`, separate from canonical T+ and documentary T_D. Include module/class/function boundaries and compound statement clauses: `if/elif/else`, loops/else, try/except/else/finally, with/async with and match/case. A tree describes syntactic nesting; CFG joins, guards and data dependencies remain separate evidence.
2. Give each context block a snapshot/repository/artifact/span-based ID, parser version, block kind, parent ID and original source spans. Use AST plus tokenizer information for exact multi-line headers, decorators and clauses. Source bytes remain authoritative. Preserve source encoding and test Unicode coordinate conversion. No canonical reparenting or new dependency degree results from T_S.
3. Resolve a requested entity/span to its smallest enclosing block; retain alternatives for ties and define whitespace/EOF fallback explicitly. Apply depth-relative DOI to T_S only, recording that this tree's depth differs from entity ownership depth. Do not substitute one tree's depth or LCA for the other's.
4. Select the focus range and enclosing headers/clauses, then budget optional sibling stubs, related definitions and typed witnesses. A large focus range is not exempt from the budget: return continuation or the measured mandatory-context error. Source order can organize chunks but is not execution order.
5. Emit structured `source_segments` and `omissions`, not a synthetic supposedly executable file. Each segment carries its original span, byte/content digest, role (`focus`, `enclosing_header`, `related_definition`, `sibling_stub`) and source trust label. An omission identifies its span/count and retrieval handle. Sibling stubs contain source-derived labels; generated descriptions, if later offered, are separately marked annotations.
6. Cache deterministic AST/token metadata by artifact digest/parser version. Fingerprint focus, source-tree version, selection policy, template, filter and tokenizer. Maintain reproducible payload contents; creation times are excluded from content identity. Use complete-envelope accounting, endpoint/path closure and cursor rules already specified in §§4/23.

Exact execution context is broader than ancestor headers: decorators, globals, closure variables, guards and exception behavior may matter. Provide explicit related-definition handles and `missing_context`/`unsupported_analysis` indicators; do not claim semantic completeness merely because the ancestor spine is present. Repository comments/docstrings remain untrusted data even when selected by the compiler.

Extend `get_entity_content` through the proposed v1.1 schema with an explicit structured-context mode; keep strict v1 source-range behavior unchanged. `get_architecture_context` may reference compiled source context without introducing an eighth MCP operation. A single shared compiler serves both UI and agents.

## 5. Proposed addition B — evidence-bearing process/pattern cards

Design the schema in P5.0; offer read-only cards in P5.3 where evidence is sufficient, and assess optional pattern/query experiments in P5.5. A card is an inspectable reconstruction aid, not a command, generated implementation or executable workflow.

The proposed `process-evidence-v1` envelope contains `card_id`, `snapshot_id`, `scope_ids`, `entry_entity_ids`, `artifact_digests`, `producer_version`, `kind` (`source_outline`, `observed_scenario`, `candidate_pattern`), `steps`, `relations`, `constraints`, `missing_evidence`, `limitations`, and `evidence_handles`.

- Every supported step/constraint points to source, a supported analysis result, a rule model or a collection. Human rationale and model summaries remain separate annotations. Gaps have explicit reason records rather than fabricated support.
- Each relation identifies endpoints and its basis: `lexical_order`, `cfg_possible_transition`, `static_call`, `observed_call`, `observed_sequence`, or `human_assertion`. Only emit kinds for which supporting facts exist. Distinguish partial order from a total sequence, and possible transitions from feasible paths.
- An aggregate call collection can support `observed_call`; it cannot support `observed_sequence`. An observed scenario is qualified by environment, collection, invocation scope and capture completeness. It does not resolve all alternative runtime dispatch for a static call site.
- Constraints use the existing versioned rules model where expressible. Preconditions, postconditions, resource effects and exception policies without qualifying evidence are marked unknown. Capturing them in a schema does not prove them.
- Path and source bundles use the same closure/budget requirements as ordinary context. Missing steps/conditions remain visible; a card cannot call itself complete merely because its serialized page is complete.

If later experiments justify intensional logic, start with a read-only whitelisted query IR over supported predicates. Specify types, variable safety, finite domains, recursion/negation semantics, evaluation bounds and witness derivations. Unsupported predicates return diagnostics. Generated rules are proposals until validated; embedding logic in a prompt is not an execution or proof engine. Keep an external Datalog/FAMIX adapter out of the core dependency set unless a measured use case requires it.

Actual process execution would additionally require a separately scoped runner, input/output contracts, environments, side effects, failure/rollback semantics and replay/idempotency policy. This investigation does not add such a runner or authorize repository execution.

## 6. Independent validation and scheduling

Extend existing gates rather than adopting the draft's absolute claims:

| Existing gate/increment | Added evidence |
| :--- | :--- |
| P5.0 | Schemas for T_S and process cards, source-span fixtures, supported predicate matrix and versioned wire decision |
| KG2 / P5.2 | Exact headers and source recovery; nested/async/exception/match/decorator cases; no code-topology change; invalid Python yields explicit range-only fallback |
| KG4 / P5.2–P5.3 | Lexical, CFG, call and observed ordering kept distinct; no aggregated graph treated as invocation sequence |
| KG8 / P5.2–P5.3 | Long functions, wide branches, Unicode and tiny budgets; omission handles, continuation and final-envelope limits |
| KG6–KG7 / P5.3 | Cards remain annotations, stale facts rejected, source/path navigation accessible, locked selection preserved |
| P5.5 | Matched-budget flat source vs existing graph context vs graph plus source compiler; separately ablate process cards; independent answer and source/behavior oracles |

Counterexample regressions must show: root fan-out defeats a fixed-size DOI guarantee; β changes geometry but not rollup counts; source-line order is not control flow; aggregated A→B and B→C events from different invocations do not prove A→B→C in one execution; rule convergence can coexist with a failing unit test; missing predicate support is not a negative pattern match.

An optional generation/remediation evaluation may consume these cards, but it needs a fixed revision/token/time budget, cancellation, recorded diffs and an explicit nonconverged result. Evaluate generated artifacts with independent type/unit/integration checks and architecture findings. Conformance does not authorize merge or establish functional correctness. Do not execute an unbounded “self-correct until full convergence” loop.

Retain P5.0→P5.5 order and all existing unresolved release gates. These recommendations add no guaranteed compression ratio, accuracy improvement, logarithmic token bound or deterministic AI replication claim. Application implementation and performance/LLM measurements remain future work.

## 7. Input provenance

Reviewed [technical expansions attachment](<C:/Users/jakem/.codex/attachments/8ab63b73-b1dd-4adc-b609-811284fdd5bd/Pasted text.txt>) against the current [Phase 5 plan](F:/uv-data/Geo_Grapher/PHASE_5_IMPLEMENTATION_PLAN.md), approved contracts and the source anchors above. Existing knowledge-graph research corrections continue to apply. Primary-source links support the limited method descriptions; the new schemas and delivery recommendations in this review are Geo Grapher engineering proposals.
