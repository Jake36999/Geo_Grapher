# Geo Grapher — Technical Implementation Blueprint

Contract version 1.0 · 6 November 2026 · Engineering baseline before application implementation

## 0. Authority and deliverables

The approved [product specification](F:/uv-data/Geo_Grapher/FINAL_DESIGN_SPECIFICATION.md) remains authoritative for product direction, styling, safeguards and C1–C14. This companion supplies the missing implementation contracts for its §§7–11, 13, 17 and 18. Where the earlier document calls the deterministic computations optional or leaves baseline choices open, this blueprint supersedes that scheduling/choice only. No application implementation is included.

Normative contract artifacts:

- [Executable SQLite DDL](F:/uv-data/Geo_Grapher/contracts/geographer.schema.sql): all tables, constraints, foreign keys and indexes. Execute the entire file in a fresh database; do not transcribe a subset.
- [TypeScript wire declarations](F:/uv-data/Geo_Grapher/contracts/geographer.wire.d.ts): exact requests and responses for seven query tools and the viewport endpoint; declaration-only code.
- [Rules JSON Schema](F:/uv-data/Geo_Grapher/contracts/geographer.rules.schema.json): Draft 2020-12 schema applied after safe YAML parsing.
- [Example YAML rules](F:/uv-data/Geo_Grapher/contracts/geographer.rules.example.yaml): concrete valid example; not an active project configuration.

All algorithms below are normative unless explicitly labelled a rendering heuristic. IDs sort by UTF-8 byte order, hashes use SHA-256 lowercase hexadecimal, strings are valid Unicode without lone surrogates, floating-point computations use binary64, and JSON rejects NaN/Infinity. `H(part1,...,partN)` means SHA-256 of the canonical JSON array of parts, not delimiter-concatenated strings. Semantic determinism is required; cross-GPU pixel identity is not.

## 1. Locked baseline decisions — product §18

### 1.1 Language and resolver

Use CPython 3.11+ with standard `ast` and `symtable`; the reproducibility manifest records the exact Python minor version. Initial fixtures and AST normalisation contract target Python 3.11 grammar. A file using syntax unavailable to the selected runtime is a parse failure, not silently reinterpreted. AST grammar varies by Python release; symbol tables identify compiler scopes. [Python AST](https://docs.python.org/3.11/library/ast.html), [symtable](https://docs.python.org/3.11/library/symtable.html).

“Exact Python analysis” means exact facts for a deliberately resolved subset, not a complete Python call graph. Implement this resolver sequence:

1. Inventory configured `repo_id → source_roots` mappings. Module names follow relative paths, `__init__.py` and declared namespace-package roots. Relative imports ascend the containing package, never the filesystem arbitrarily. Cross-repository imports use the same declared workspace module map; they do not depend on host `sys.path` or import execution.
2. Build lexical scope tables from `symtable`, joined to AST scopes by type/name/line and traversal ordinal. Record definitions, bindings, `global` and `nonlocal`, import aliases and shadowing. Definition identity is `(repo_id, rel_path, scope-qualified name, kind, signature, duplicate-definition ordinal)` within a snapshot.
3. Emit exact declarations, ownership and syntactic import statements with source ranges. A resolved import target requires one module in the declared map. Multiple roots providing the same module are ambiguous; retain all candidates without selecting the first root. Record missing and external modules explicitly.
4. Resolve `Name()` to a lexical function/class binding only when its reaching binding is unique. Intraprocedural reaching definitions use a CFG fixed point: a map from identifier to finite set of binding IDs; joins union sets; assignments kill previous bindings; loop joins repeat until stable. Module global bindings that can be rebound and execution-order-dependent lookups remain candidates. Parameters and arbitrary assignment aliases are not inferred call targets in v1.
5. Resolve `module_alias.member()` through an unambiguous import plus static member table, including explicit re-exports; follow re-export chains to a fixed point and mark cycles without a unique terminal unresolved. Do not execute `__getattr__`, imports or decorators. For attribute dispatch on ordinary instances, inherited methods, descriptors or monkey-patched objects, retain candidate/unresolved facts unless a later separately tested resolver proves the target. `self.method()` is not automatically exact.
6. A call through a decorated definition identifies the syntactic binding only; record `static_candidate` for the runtime target unless decorator transparency is explicitly proven. `getattr`, reflection, `eval`, `exec`, star imports without statically enumerated exports and dynamic import strings remain unresolved/candidate. Never claim a possible branch is an observed execution.
7. External unresolved occurrences have scoped placeholders; never merge them solely on the spelling `Session` or `Path`. Emit a directed `calls` relation to the placeholder with its resolution status. Import relations and call relations are separate records.

Pair this with `tree-sitter` adapters for additional languages: declarations, containment, source ranges and syntactic import/call candidates. Adapter ID, grammar digest and resolver capability appear in snapshot metadata. Tree-sitter alone does not certify cross-language dispatch.

### 1.2 Rules file and semantics

The active file is **`geographer.rules.yaml`**, YAML 1.2 safe data only. TOML is not a second baseline format. Reject duplicate keys, aliases/anchors, merge keys, explicit YAML tags and unknown fields. Convert to JSON-compatible values, validate against the linked JSON Schema, then apply the semantic validation below. Maximum file size 1 MiB; string and collection limits are enforced before regex evaluation.

Required top-level fields are `version: "1.0"`, `world_policy: open | closed`, `components` and `rules`. Each component has a unique `id` and one or more `selectors`. Each selector requires exact `repo_id` and at least one of `path_glob` / `qualified_name_regex`. Both predicates in one selector are AND; selectors for one component are OR. Rules require unique `id`, `type: require | allow | forbid`, component `source`, component `target` and nonempty `rationale`.

Paths are case-sensitive, repository-relative POSIX paths even on Windows. `*` matches zero or more non-`/` characters, `?` one non-`/`, and a complete `**` segment matches zero or more complete path segments. Whole-path matching is required. Character classes, brace expansion, escaping, absolute paths and `..` segments are invalid in v1. Thus `src/**/a.py` includes `src/a.py`.

Qualified-name regexes use `re.fullmatch` semantics on the canonical qualified name. Limit the accepted grammar to literals, character classes, `.`, concatenation, alternation, noncapturing grouping and `?/*/+/{m,n}` quantifiers; reject backreferences, lookaround, inline flags and nested quantified subexpressions. Compile/evaluate in a bounded worker (100 ms per mapping batch); a timeout fails model validation. Do not silently skip a rule.

Every non-synthetic analysed subject maps to zero or one component. Two different matching component IDs are `RULE_CONFLICT`, not precedence by file order. Zero matches maps to a synthetic Unmapped component. Scope atoms inherit their owning subject's mapping. Reject unknown component references and `forbid` combined with `require` or `allow` on the same ordered pair. Multiple rules of the same type/pair are rejected. `require` plus `allow` is redundant and rejected. Self-pairs are allowed and explicit. Model digest hashes the canonical parsed configuration.

The baseline rule domain is directed resolved **static dependency existence**, all dependency subtypes selected by the query, excluding expected/similarity/history/runtime. Runtime observations can corroborate findings separately. For ordered mapped pair `(a,b)`, let `W(a,b)` be the distinct concrete relationship IDs after these filters:

| Type/policy | W nonempty | W empty |
|---|---|---|
| require | match | missing_required if analysis scope complete; otherwise inconclusive |
| allow | allowed_present | allowed_not_present, no defect |
| forbid | forbidden_present | forbidden_absent if scope complete; otherwise inconclusive |
| unlisted/open | unclassified | no finding |
| unlisted/closed | forbidden_present with rule_id null | no finding |

Report unmapped incident pairs independently. “Complete” here requires all participating files parsed and no unresolved/candidate relationships affecting that pair; it does not certify dynamic Python behaviour. Never materialise an expected edge as an implementation witness.

### 1.3 Tokenizer, transport and runtime contracts

Use `tiktoken.get_encoding("o200k_base")` by default; accept explicit `cl100k_base`. Use `encode_ordinary` on canonical JSON so repository strings resembling special tokens remain ordinary text. Package/cache the encoding data locally, record package version and weight-file SHA-256, and make no network fetch during a query. Encoding names are explicit, never guessed from a model alias. [tiktoken encoding definitions](https://github.com/openai/tiktoken/blob/main/tiktoken_ext/openai_public.py), [encoding API](https://github.com/openai/tiktoken/blob/main/tiktoken/core.py).

Only when local weights are unavailable and `allow_byte_fallback=true`, report `used_tokens = ceil(len(utf8(payload))/4)` as an **estimate**. It is not a token upper bound. Enforce the independent UTF-8 byte bound described in §8; missing weights with fallback disabled returns `TOKENIZER_UNAVAILABLE`.

Support MCP `stdio` and Streamable HTTP at `/mcp`, pinned initially to protocol **2025-11-25** and its negotiation rules. Stdio uses newline-delimited UTF-8 JSON-RPC, with logs exclusively on stderr. Streamable HTTP supports JSON or request-related SSE responses under that version. SSE is a framing option within Streamable HTTP, not an invented third transport; legacy standalone HTTP+SSE is not required. Bind HTTP to loopback by default and validate Origin/Host; nonlocal deployment needs explicit configuration. Use the official SDK for lifecycle/protocol handling. [Pinned MCP transport specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).

The current MCP draft changes transport behaviour relative to this pin; do not combine draft GET/session rules with the pinned implementation. A later protocol upgrade requires a compatibility test and explicit contract revision. [MCP draft transport changes](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/draft/basic/transports/streamable-http.mdx).

Application service: Python/Pydantic v2 with `extra='forbid'`, strict booleans/integers, finite floats and JSON Schema tool input/output publication. HTTP viewport: `POST /api/v1/viewport/frame`. Frontend contracts: TypeScript declarations linked above. SQLite minimum 3.37 + JSON1, `foreign_keys=ON` on every connection, WAL for the runtime store. Exact dependencies and grammar hashes are recorded in the build lockfile; CPython minimum does not imply the bundled SQLite meets requirements. [SQLite STRICT tables](https://sqlite.org/stricttables.html), [foreign-key configuration](https://sqlite.org/foreignkeys.html).

## 2. Relational storage and indexing — product §10

The product's conceptual table is retained. The linked **`contracts/geographer.schema.sql` is the exact executable DDL**, including every requested column and additional tables needed for multi-repository snapshots, mixed-detail membership and diagnostics. No SQL is merely illustrative.

### 2.1 Snapshot, identity and tree contract

`snapshot_sets.snapshot_id` identifies an immutable workspace build. `snapshots` has composite primary key `(snapshot_id, repo_id)`, one revision/digest/extractor record per participating repository, plus synthetic repo `@workspace`. This avoids pretending several repositories share one revision. Cross-repository edges share the build-set snapshot and can therefore use actual composite endpoint foreign keys.

One synthetic workspace entity is depth 0 with NULL parent. Repository roots are depth 1 beneath it. Other ownership parents can be in the same snapshot, including the common workspace parent; source facts never point into another snapshot. Entity IDs omit snapshot for continuity; the primary key includes snapshot. Definition changes/renames may require separately evidenced continuity and are not merged by body hash.

All relationships used by quotienting have **atomic leaf endpoints**. Python imports on a file, or execution directly in a container that has children, attach to a synthetic child `scope_atom` with ID `H("scope-atom-v1", owner_id)`. Preserve the original owner in `source_subject_id` / `target_subject_id`. The augmented tree `T+` includes one scope atom for every nonleaf subject eligible for direct relationships; all other leaves are their own atoms. Scope-atom source locations/flags inherit their owner. This removes the otherwise undefined “project a file-level import as a leaf call” case. Ownership containers still have their original IDs and source content.

`ancestors_binary_lifting_json[j]` is the entity ID of the `2^j` ancestor, with root saturating to itself. Array entries are strings, not nested ancestor objects. `ast_body_hash` and `wl_3hop_hash` are nullable for unsupported entities. `qi_cluster_id` is only a cache for the default helper-tree configuration in §6; request-specific cluster membership belongs to view tables and must not overwrite it.

### 2.2 Edge, evidence and hyperedge contract

`relationships` supports parallel typed edges via a per-occurrence primary ID; no uniqueness constraint on endpoint pairs. `occurrence_key` hashes snapshot-local extractor, source site, subtype, ordinal, target candidate and evidence collection identity. Adding corroborating evidence to the same occurrence does not duplicate the relationship. Symmetric relations canonicalise ordered endpoint IDs and swap subject IDs consistently. Self-relations are legal.

Each relationship has at least one `evidence` row at publication. One relationship can have many evidence records; witness counts count distinct relationships, never joined evidence rows. Confidence is nullable, within `[0,1]`, and not set to 1 merely because an extractor ran. Category/status compatibility, revision and runtime-window consistency are publication checks.

Documentary incidence `(snapshot_id, incidence_id)` is one hyperedge with one row per member entity. All member rows must have the same fragment and role. The fragment must have `sort='text'` and `kind='fragment'`. The k members are not converted into pairwise dependency edges; dependency degree queries never join this table.

### 2.3 Views, witnesses, SCCs and layout

`analysis_views` identifies grouping, filter and algorithm version; `view_representatives` holds both canonical and synthetic group IDs; `partition_members` maps every in-scope atom to exactly one representative. Representatives are never inserted into canonical `entities` merely for a camera state.

`quotient_projections` keys ordered representatives, family, subtype, direction, resolution and unit. Expected declarations have their own `family='expected'` projections and are excluded from implementation counts. `quotient_witness_map` has unique `(snapshot_id,view_id,relationship_id)`, so one raw relation appears once per partition, including internal self-edges. Rates from different runtime windows/environments cannot share a view; the filter fixes that collection scope.

`level_scc_condensations` contains one row per representative per view/filter, not one reused SCC assignment across levels. `level_key` is e.g. `depth:3`, `kind:file` or `mixed:<partition_digest>`. `scc_id=H(snapshot,view,filter,sorted_members)`; component size counts representatives. Condense with deterministic Tarjan traversal and rank by `rank(C)=0` for indegree-zero SCCs, otherwise `1+max(rank(P))` over predecessors. Self-loops remain separately recorded; a size-one SCC with recursion is not reported as a multi-entity cycle.

`layouts` stores canonical absolute coordinates/radii for a layout version and seed. Per-view residual positions and curve buffers are derived, not written into canonical entity facts. `analysis_results` stores versioned normalisation/WL manifests, cut ratios, Cayley projection logs and QI proofs/membership handles.

### 2.4 Required publication transaction and query plans

Insert a build under `status='building'`, with parent foreign keys deferred until commit. Before switching to complete, validate: exactly one workspace root; every entity reachable from it; parent depth + 1; leaf endpoint requirement; all binary-lifting entries; all relationship evidence; hyperedge consistency; total partition coverage; quotient witness/count/weight reconciliation; SCC rank consistency; finite layout and collision constraints. Run `PRAGMA foreign_key_check` and `integrity_check`. Failure keeps the build unpublished. Complete canonical snapshots are immutable through the service; rebuild creates a new snapshot. Derived views/results/layout caches can be appended under new content-addressed keys, never mutate existing semantic facts or published view membership. Cross-row invariants are not falsely claimed as SQL CHECK constraints.

JSON column shapes are also mandatory: parse_failures_json is an array of `{rel_path:string,language:string,code:string,message:string}` records; each ancestor array contains exactly J existing same-snapshot IDs as defined in §3.2; config_json records runtime/grammar/normalisation versions, source-root map, default filters and resource limits; view grouping/filter JSON is the exact wire Grouping/Filter value; details_json and analysis result JSON use the versioned algorithm records in §§5–6. Reject unknown parse-failure fields and invalid paths before publication. JSON validity/type CHECKs alone do not validate nested records.

Adjacency uses the covering prefixes `relationships_out` / `relationships_in`; children use `entities_children`; exact clone/hash candidate queries use `entities_ast` / `entities_wl`; source lookup uses `entities_path`; documentary retrieval uses its entity/fragment indexes. Mandatory keyset witness query:

```sql
SELECT r.*
FROM quotient_witness_map AS w
JOIN relationships AS r
  ON r.snapshot_id=w.snapshot_id AND r.relationship_id=w.relationship_id
WHERE w.snapshot_id=:snapshot AND w.view_id=:view AND w.projection_id=:projection
  AND w.relationship_id>:after_relationship_id
ORDER BY w.relationship_id COLLATE BINARY
LIMIT :page_size;
```

Use the analogous `(snapshot,relationship,evidence_id > after)` evidence page. Never paginate with OFFSET. First-page `after_relationship_id=''` is valid because IDs are nonempty. Record `EXPLAIN QUERY PLAN` on the 50k/150k reference workload; witness/adjacency pages must use these index prefixes, not a full graph scan.

## 3. Mixed-detail partition, LCA and DOI — product §8 / C4

### 3.1 Formal expansion state

Let `L(p)` be atomic leaves beneath node `p` of `T+`. Let `E` be **revealed branch IDs**, including the root and all ancestors of every revealed node. This is the stored expansion state; it is not “all containers whose children should be shown”. Clicking Expand(p) adds all immediate children to E. Revealing one child adds that child and its ancestors. Collapse(p) removes all proper descendants of p from E. Reject IDs outside the selected snapshot. A leaf can be in E; an internal p with no revealed children is a collapsed representative.

For an entered container p define `A_p=Children(p) ∩ E`, `U_p=Children(p) \ E`. Define recursively:

\[
F(p,E)=\begin{cases}
\{(p,L(p))\},& A_p=\varnothing;\\
\bigcup_{c\in A_p}F(c,E)\ \cup\ \{(R_p,\bigcup_{c\in U_p}L(c))\ : U_p\ne\varnothing\},& A_p\ne\varnothing.
\end{cases}
\]

`R_p=H("residual-v1",snapshot_id,p,sorted(U_p))`; display “Other children of <p>”. Its membership is the leaves under unentered child branches, not just the child container IDs. If p has no children, `F(p,E)={(p,{p})}`. Empty groups are forbidden. `Pi(E)` is the set of membership blocks from F(root,E). Children subtrees are disjoint, so induction proves the blocks are disjoint and cover every atomic leaf exactly once. Filters restrict the leaf universe before materialising view members; the same proof holds after removing empty blocks.

Algorithm: DFS from root; when `A_p` empty, bulk assign all leaves of its DFS interval to p; otherwise recurse into revealed children and assign each unentered child's leaf interval to `R_p`. Cache sorted atom leaf order and subtree intervals. `rep(u)` is the unique group whose block contains u, materialised in `partition_members`. Parent shells never receive membership when any child/residual group represents that region.

Example: p has A={a1,a2} and B={b1,b2}. Revealing only A yields representatives A and R_p(B). Revealing a1 beneath A yields a1, R_A({a2}), R_p({b1,b2}). A and p remain context shells only. A call a1→a2 is counted once from a1 to R_A; b1→b2 is one internal edge of R_p. There is no duplicate “p total” edge.

Roll up each eligible raw relation e once using `(rep(source(e)), rep(target(e)), family, subtype, direction, status, unit)`. For symmetric relations re-canonicalise representatives after mapping. If both representatives equal, keep the projection with `is_internal=1`. The inspector shows distinct internal witness IDs and source recursion separately; a shell can show a labelled descendant subtotal calculated from blocks, but it is not another active representative and its subtotal is never summed into graph totals.

### 3.2 Binary lifting (exact)

For N nodes let `J=max(1,ceil(log2(max(1,N)))+1)`. DFS in sorted child order; root depth 0 and `up[root][j]=root`. For each other v: `up[v][0]=parent(v)` and `up[v][j]=up[up[v][j-1]][j-1]`, j from 1 to J−1. Store the full J-entry array. Preprocessing time/space O(N log N).

```text
LCA(x,y):
  if depth[x] < depth[y]: swap(x,y)
  delta = depth[x]-depth[y]
  for j = 0 .. J-1:
    if delta & (1 << j): x = up[x][j]
  if x == y: return x
  for j = J-1 .. 0:
    if up[x][j] != up[y][j]: x=up[x][j]; y=up[y][j]
  return up[x][0]
```

Same-snapshot workspace root handles cross-repository LCAs. No LCA is defined across snapshots. Queries cost O(log N).

\[
d_T(x,y)=depth(x)+depth(y)-2depth(LCA(x,y)),\quad
DOI(x\mid y)=-(d_T(x,y)+depth(x))\ge-depth(y)-2r.
\]

Compute on `T+`, with scope atoms hidden behind their owner labels. Root-to-focus ancestors are pinned. DOI selects candidate revealed branches, normalised by ancestor closure; it does not by itself choose relationship scope. User pins/explicit caller/callee paths are added before building Pi(E). A radius-r branch lies at most r edges off the focus spine because `DOI=-depth(y)-2·off_spine_distance`; this is the precise reason for the threshold. Budget-driven collapsing removes branches atomically and recomputes affected membership/projections.

## 4. Deterministic 3D geometry — product §§7 and 9

### 4.1 Bottom-up radii and initial placement

Use scene units, `r_leaf=1`, padding=0.35, gap=0.20, target packing fraction eta=0.35, descendant cap C=10,000, epsilon=1e−4. These constants define `sphere-pack-v1`; changing one requires a new layout version. Leaf counts include scope atoms. For container p with already solved child radii r_i and leaf count L_p:

\[
s_p=1+0.35\ln(1+\min(L_p,C)),\qquad
r_p^{(0)}=\max\left(s_p,\ padding+\max_i r_i,\ padding+\left[\frac{\sum_i(r_i+gap/2)^3}{\eta}\right]^{1/3}\right).
\]

Leaf radius is exactly 1. The cap applies to the visual size preference s_p, not the feasibility requirement: arbitrarily many children cannot fit in a globally capped radius. Final radius is the solver's feasible radius, recursively used by ancestors.

Sort siblings by entity ID, i=0..K−1; compute phase `theta0=2π·u64(H(seed,p)[0:8])/2^64`, golden angle `g=π(3−sqrt(5))`, `z_i=1−2(i+0.5)/K`, `theta_i=theta0+i*g` and unit direction

\[
v_i=(\sqrt{1-z_i^2}\cos\theta_i,\sqrt{1-z_i^2}\sin\theta_i,z_i).
\]

Set local `c_i=0.8·max(0,r_p−padding−r_i)·v_i` relative to p. K=1 is centred exactly. A deterministic rotation from seed/p may be applied only if included in the version; v1 uses the unrotated formula. Child subtrees translate rigidly after their parent is placed. Unrelated filters never rerun the canonical packing.

### 4.2 Bounded collision projection and guaranteed fallback

For at most eight radius attempts and 256 sweeps each, process sibling pairs in lexicographic `(i,j)` order. For a pair compute `d=norm(c_j−c_i)` and overlap `o=r_i+r_j+gap−d`. If `o>0`, choose `n=(c_j−c_i)/d`, or the deterministic unit fallback axis with sign from H(i,j,seed) when d<1e−12. Update `c_i-=0.5*o*n`, `c_j+=0.5*o*n`. After the pair pass, project every centre into its allowed ball: if `norm(c_i)>r_p−padding−r_i`, multiply c_i by `(r_p−padding−r_i)/norm(c_i)`.

After each sweep measure maximum containment excess and maximum positive pair overlap, including gap. Stop only if both <=epsilon. Updates use binary64, fixed pair order, no nondeterministic GPU reductions. If no success after 256 sweeps, grow `r_p*=1.15`, rescale all centres by 1.15 and retry. Iterative projection is a bounded heuristic, not an assumed convergence theorem.

After eight unsuccessful attempts, use a provably feasible line packing: `W=2*sum(r_i)+(K−1)*gap`, place each centre on x at `−W/2 + 2*sum_{j<i}(r_j)+i*gap+r_i`, and choose `r_p=max(s_p,padding+W/2)`. Adjacent surfaces are gap apart, all children fit inside the sphere, and nonadjacent pairs are farther apart. Mark p as a fallback layout; it can be less legible but cannot silently overlap. Recheck all inequalities; if scale exceeds 1e12 or a nonfinite number appears, return LAYOUT_FAILED rather than publish invalid coordinates.

Residual spheres are view-local. Inside the canonical parent, run the same bounded solver on active immediate child/residual groups using residual radius from the same count/volume rule, keeping canonical coordinates as the first initialisation. If residual accommodation would move unrelated canonical shells, use the feasible fallback in an explicitly marked local expanded view and restore saved canonical coordinates on exit.

### 4.3 Control polygons and clamped splines

Route between representative centres via their canonical ownership ancestors. A residual uses p as its ownership attachment; a QI group uses the LCA of its members. Build the path from source to LCA to target, remove consecutive duplicate positions within 1e−12, and retain endpoint centres. If the **original** path length N0>3, remove the single internal LCA point; if N0=3 retain it. Endpoint LCA is never removed. After removal/reduction let N be the number of points, N>=2; N=1 is handled as a self-loop, not divided by zero.

For each i=0..N−1, Holten Method 1 is exactly

\[
P'_i=\beta_iP_i+(1−\beta_i)\left(P_0+\frac{i}{N−1}(P_{N−1}−P_0)\right).
\]

With no lens beta_i=beta in [0,1]. Let p=min(3,N−1), interior-knot count M=N−p−1. Use knot vector of length N+p+1:

\[
U=(\underbrace{0,\ldots,0}_{p+1},\frac1{N-p},\frac2{N-p},\ldots,\frac M{N-p},\underbrace{1,\ldots,1}_{p+1}).
\]

When M=0 there are no interior knots. Evaluate `C(t)=sum_i B_{i,p}(t)P'_i` using de Boor or Cox–de Boor, with zero-denominator basis terms taken as zero and `C(1)=P'_(N−1)` explicitly. Endpoint multiplicity gives exact endpoint interpolation. Default 48 segments; use 16 at overview and 96 on selected curves, with stable level-of-detail thresholds. Reference method: [Holten 2006](https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Holten06.pdf).

### 4.4 Canonical tracks, opposing directions and EdgeLens

Group curves by unordered representative pair {a,b}, with a<b. Build their **one shared** canonical polygon a→b, including a shared beta/lens field, before assigning lanes. Reverse parameterisation, not geometry, for b→a. This is essential: independent per-edge bases cannot guarantee separation.

Let tangent `T=(c_b−c_a)/norm(c_b−c_a)`. Choose world axis e in x,y,z with smallest absolute dot product with T (ties x,y,z), then `n=normalise(T×e)` and `b=T×n`. For coincident distinct centres, generate T from H(a,b,seed), use a virtual chord centred at that location for routing and mark degenerate endpoints; permit no distinct fully coincident spheres after packing. Self-loop edges use a deterministic local frame and `C_loop,j(t)=c+R_j*((1−cos(2πt))*n+sin(2πt)*b)`, where `R_j=owner_radius+delta*(j+1)`. These nested tangent circles share only their intentional attachment c; directed loops show an arrow. A residual internal projection is a counted inspector item by default, not one loop drawn per hidden witness.

For distinct endpoints, apply a **longitudinal safety projection** after straightening: for each control point let Greville abscissa `g_i=(U_(i+1)+...+U_(i+p))/p` and `Q_i=P'_i+dot(P0+g_i*(PN−1−P0)−P'_i,T)*T`. Evaluate the shared base spline using Q_i. Linear reproduction of the clamped B-spline gives `dot(C(t)−P0,T)=t*norm(PN−1−P0)`. Thus the chord coordinate is strictly monotone, while transverse hierarchical curvature is retained. This is a specified 3D routing extension after Holten Method 1; it is not attributed to the paper. It avoids same-pair crossings at different parameter values, which plain offsets alone cannot guarantee.

Order lanes by `(direction_is_b_to_a, family, subtype, resolution_status, relationship_id)`. Use all curves in the filter-defined pair inventory before render sampling so surviving lanes do not swap when one is hidden. For lane j=0..M−1 and spacing delta=max(0.08,2*world_line_radius+0.02):

\[
o_j=\delta(j−(M−1)/2)n,\qquad C_j(t)=C(t)+\sin(\pi t)o_j.
\]

For reverse direction sample `C_j(1−t)` and orient arrowheads accordingly. Between any two lanes at a common interior t, separation is `abs(j−k)*delta*sin(pi*t)>0`; shared endpoints are intentional. Use n/b only from the canonical pair, never camera direction. At endpoints fan into the sphere surface and draw direction glyphs outside the shell. Expand line thickness only within the available lane spacing. Large M is an aggregate bundle until selected.

Combined with the monotone chord coordinate, this proves distinct lanes of one endpoint pair cannot intersect at either equal or different interior parameters. Shared attachment endpoints are intentional; baseline rendering uses line primitives and separated surface ports for visible arrowheads. Optional tubes taper near attachments and require sampled segment-to-segment clearance checks before choosing a radius: minimise `norm(A+s*(B−A)−C−t*(D−C))` over the unit square for each different-lane segment pair, and keep both radii below one third of the minimum positive clearance. Where clearance is below epsilon, use lines rather than overlapping swept meshes. It does **not** prove no two unrelated endpoint-pair paths intersect or no projection shares pixels. For those cases use depth testing, selected-edge overlay with depth bias, picking IDs, and local unbundling. Do not promise universal absence of screen-space occlusion across arbitrary geometry.

For lens centre f and radius R>0, define q=clamp(norm(P_i−f)/R,0,1), falloff `w(q)=1−3q²+2q³`, and `beta_i=beta*(1−strength*w(q))`, strength in [0,1]. Endpoints remain unchanged by Method 1. Reapply the longitudinal safety projection after lens straightening. Cursor lens centre is the nearest picked node/curve's world-space hit, or intersection with the camera-facing plane through selection when no hit; never an unscaled 2D pixel position. A node lens centres at its world centre with default R=3*node_radius. The same falloff may add lane spacing `delta_local(t)=delta*(1+strength*w(norm(C(t)−f)/R))`, which remains positive and transverse to T, preserving per-pair separation and monotonicity. Wire control_points are the original post-LCA-removal P_i; the client computes P'_i then Q_i from request beta/lens before evaluating the provided knots.

## 5. AST normalisation and 3-hop WL — product §11

### 5.1 Exact normalised-AST representation `py-ast-v1`

Only supported Python function/method entities receive hashes. Parse with type comments enabled. Keep a lossless source reference separately. Normalisation is a structural comparison, not a semantics-preserving rewrite to execute.

1. Comments are absent from ordinary AST fields; documentary extraction retains their source text. Remove the first `Expr(Constant(str))` in module/class/function bodies as a docstring; preserve every other string literal, including runtime SQL/regex values.
2. Ignore lineno/end_lineno/column attributes, type comments and `Module.type_ignores`. Preserve annotations, literal values/types, operators, statement order, control flow, async/generator distinctions, decorators and argument kinds/defaults. Normalise the outer definition name to `__subject__`; keep nested definition/class names.
3. Use symtable bindings, not text replacement. Preserve parameter names (keyword API), global/nonlocal/free names, imported names, attributes, keyword argument names and all bindings appearing in a call's callee expression or its root (including callback parameters and module aliases). Preserve exception class, pattern class and annotation names. Preserve names in nested scopes referenced as free variables. This prevents `foo()`/`bar()` collapsing merely because both are calls.
4. Eligible local bindings are all remaining local Store/Del/capture targets, excluding parameters, nested definitions and imports. Enumerate by first binding AST preorder position, with deterministic field traversal from the Python 3.11 AST schema. Assign `v0,v1,...` per lexical scope. Replace all references to that binding consistently, including AugAssign, NamedExpr, exception-handler string names and match-pattern string captures. Nested scopes have separate binding maps; resolve closures before renaming. Never rename an Attribute.attr or a Call keyword.arg.
5. If scope uses `locals`, `globals`, `vars`, `eval`, `exec`, `__dict__` or a star import, disable identifier canonicalisation for that scope and all nested closures depending on it; still strip docstrings and locations. This is a conservative, syntactic policy, not an exhaustive reflection detector.
6. Encode each AST as tagged JSON arrays: node `[node_type, [[field_name, value],...]]` in fixed Python 3.11 field order; lists retain order; constants are `[python_type, canonical_value]`. Integers use base-10 strings, floats `float.hex()`, complex two float.hex strings, bytes lowercase hex, strings literal Unicode, Ellipsis a fixed tag. No ast.unparse formatting dependency. Include `py-ast-v1` and interpreter grammar version in the hashed envelope.

Hash canonical UTF-8 bytes. Hash equality is verified by comparing the entire normalised representation before labelling `verified_normalized_ast`. “Exact” means exact equality under this stated policy, not identical source or runtime behaviour. Inconsistent/unsupported scope matching produces NULL hash and a diagnostic, never guessed normalisation.

### 5.2 Directed typed WL refinement `directed-wl3-v1`

Use subject-level resolved static graph, excluding tests/vendor/generated by the default filter, and exclude containment, documentary, expected and runtime edges. Preserve parallel relationship multiplicity. Replace scope-atom endpoints with original subjects before building this graph. External resolved identities are included as typed terminal nodes when selected.

Set `h0(v)=H(["wl0-v1",language,kind,ast_body_hash_or_null])`. For rounds t=1,2,3, compute all nodes from the previous complete round (parallel workers cannot see partially updated colours):

\[
h_t(v)=H(["directed-wl3-v1",h_{t-1}(v),\operatorname{sortMultiset}\{["out",family,subtype,h_{t-1}(w)]\}_{v\to w},\operatorname{sortMultiset}\{["in",family,subtype,h_{t-1}(u)]\}_{u\to v}]).
\]

Multisets retain duplicate counts; self-loop contributes once to each directional list. Ignore source IDs/line numbers, not type/direction. Store h3 as `wl_3hop_hash`, with filter hash/graph normalisation manifest in analysis_results. Query filters that differ from the cached default require a new analysis view. Null-hash entities still have typed h0 seeds, but unsupported languages do not participate in `exact_normalized_ast` search.

`find_similar_code(exact_normalized_ast)` compares verified normalised bytes. `wl_3hop_candidate` returns h3 collisions as **candidates**, never “isomorphic” or equivalent. Complexity O(3(V+E)) hashing work plus per-node multiset sorting, O(sum degree·log degree) per round; no unsupported linear-time claim for arbitrary sorting.

## 6. Core bounded diagnostics and contraction — product §11

### 6.1 Boundary ratio: exact scope and denominator

Take selected leaf/subject set S and a filter-defined weighted dependency graph with nonnegative edge weights in **one unit/window**. Exclude containment/documentary/expected. Baseline static mode gives each distinct resolved occurrence weight 1; runtime uses compatible call counts or rates, never a mixture. For directed graph weights w:

\[
cut_{out}(S)=\sum_{u\in S,v\notin S}w_{uv},\quad vol_{out}(S)=\sum_{u\in S,v\in V}w_{uv},\quad \phi_{out}=cut_{out}/vol_{out};
\]
\[
cut_{in}(S)=\sum_{u\notin S,v\in S}w_{uv},\quad vol_{in}(S)=\sum_{u\in V,v\in S}w_{uv},\quad \phi_{in}=cut_{in}/vol_{in}.
\]

For undirected projection define `wU({u,v})=sum(w_uv+w_vu)` over distinct occurrences for u≠v; self-loops are excluded and logged. `cutU` counts crossing unordered edges once and `volU=sum_{u in S} degree_wU(u)`, so internal edges contribute twice. `phiU=cutU/volU`. A zero denominator returns ratio null/status zero_volume, never zero or infinity. Ratios lie in [0,1].

This is the chosen degree-volume convention, not the cardinality denominator of the early draft. A cardinality variant, if added, needs a different metric name/version. No minimisation over all subsets is performed; the UI says **Boundary cut ratio**, not graph-wide Cheeger constant or measured latency bottleneck. Precompute sums per container in one bottom-up aggregation plus crossing-edge traversal; arbitrary selection computes from indexed incidence once per distinct edge.

### 6.2 QI helper-tree contraction `helper_tree_balls_v1`

Use undirected, unweighted hop metric on the filtered **exact static subject graph**, with parallel edges collapsed for distances but retained as witnesses. Different connected components remain separate; distances between them are infinite and no finite inequality is asserted across components. This metric is not directed reachability, weighted latency or a group word metric.

Eligible helper subjects: Python private function/method (name begins `_` but not dunder), not explicitly exported, non-test/generated/vendor/external, no rule finding or unresolved incident dependency, singleton SCC without recursion, and not a focus/ancestor/pin or requested witness-path endpoint. In the eligible induced simple graph retain only connected components that are trees. Others stay singleton. Edges to noneligible vertices are allowed and are retained as crossing witnesses.

Request max diameter D is integer 0..8, default D=2; set rho=floor(D/2). Start with all eligible tree vertices unassigned. Each parallel round:

1. In each residual unassigned forest, use priority `(H("qi-seed-v1",snapshot_id,node_id),node_id)`.
2. A vertex is a seed iff its priority is minimum among unassigned vertices within 2*rho hops (rho=0 makes every vertex a seed). Compute BFS proposals from the immutable round-start forest; workers return sorted proposals.
3. For each seed take its unassigned radius-rho BFS ball. Distinct chosen seeds are more than 2*rho apart, so their balls are disjoint. Assign them in sorted seed order after the barrier, then remove assigned vertices and repeat. There is at least one seed in each residual component, guaranteeing termination in at most number-of-vertices rounds.
4. Each ball is connected in that forest and has intrinsic diameter b_C<=2*rho<=D. Measure its exact tree diameter by two BFS sweeps, lexicographic farthest-node tie breaks. Reject any violated bound; do not use ambient shortest paths as proof of internal diameter.
5. Protected and other ineligible vertices become singleton clusters. Cluster ID hashes snapshot, filter, D and sorted members. Store complete membership, internal witnesses and crossing witness counts; cluster metadata excludes similarity claims.

Per-round work is bounded-radius BFS; worst case is not O(V+E) over all rounds. Parallelism is allowed for proposals, not nondeterministic claiming. Stage 3 can cache the default D=2 unprotected decomposition; a focus query recomputes affected balls after protecting focus/pins, or uses singleton groups there.

Let q map vertices to clusters and H be the unweighted quotient, with b=max_C b_C (including singletons). Crossing quotient edges have actual underlying witnesses. For finite dG=d_G(x,y) and dH=d_H(qx,qy):

\[
d_H\le d_G,\qquad d_G\le (b+1)d_H+b.
\]

The second inequality lifts an H path with dH crossings and at most dH+1 intra-cluster traversals, each <=b. Therefore report valid quasi-isometry constants **A=b+1, B=b** in the conventional form

\[
\frac1A d_G(x,y)-B\le d_H(qx,qy)\le A d_G(x,y)+B.
\]

The sharper lower bound is `(dG−b)/(b+1)`; use the conservative conventional constants above. Example: repeated diameter-2 contractions can accumulate shortening, so `(A=1,B=2)` is not a valid global claim. D bounds each cluster, not global additive distortion. Surjectivity of q onto representatives is exact; no extra coarse-surjectivity error is needed. Weighted metrics require another proof and are unsupported in v1.

This QI contract applies only to this partition of this unweighted graph. Subsequent arbitrary containment aggregation or dropping context edges is **not** automatically QI. Set grouping.mode=atomic to request it; qi.enabled with any other grouping mode returns INVALID_REQUEST. Atomic mode maps each scope atom to its original subject ID and each ordinary leaf to itself, so it has one representative per atomic subject before contraction; ownership shells are separately contextual. Structural-only scope atoms not in the dependency graph remain singleton groups. `get_architecture_context` reports the QI certificate and membership handle for the full scope; its budgeted excerpt is explicitly partial. Directed impact/reachability always runs on original directed records and returns actual witness paths; q can invent directed traversals through a cluster and is not used to certify them.

### 6.3 Abelian Cayley degree asymmetry bound

For the selected subsystem's induced exact-static subject graph, remove self-loops and project every directed/parallel occurrence onto one unordered pair. Record raw occurrence count, removed loop count and collapsed parallel count (`nonloop_occurrences−unique_pairs`). Isolated nodes remain in V. Split disconnected projections into connected components and report **one result per component**; no unproved connected-graph result is applied to the whole disconnected graph.

For each connected simple component with n>=2,m>=1, compute degree sequence, Delta=max degree and `Delta_star=Delta if n*Delta is even else Delta+1`:

\[
\gamma^+(G)\ge\frac{n\Delta^*}{2m}-1.
\]

n=1 or m=0 returns not_applicable. Compute degrees in O(n+m), then the degree-sequence bound in O(n); calling the entire raw-edge projection O(n) would be incorrect. Retain n,m,Delta,Delta_star and projection-loss counts in the returned record. Count loop/parallel losses per component using original member IDs. The bound is a lower bound for normalised additions to an abelian Cayley host, **not** a debt score, an exact edit distance or recommended added software dependency. Source: local manuscript [Souop & Bitjoka](F:/uv-data/Geo_Grapher/Research/The%20Cayley%20Completion%20of%20a%20Graph.pdf), definitions and Theorem 5, PDF pages 3–5, as reviewed for the product specification.

Compute this in the core pipeline. Display it under collapsible **Advanced Diagnostics → Degree asymmetry bound (research interpretation)**; machine availability is core, engineering interpretation remains experimental. No runtime claim that it “takes microseconds” is assumed without measurement.

## 7. Wire contracts — product §13

The full interfaces are in **`contracts/geographer.wire.d.ts`**, including NodeRecord, RelationshipSummary, WitnessRecord, EvidenceHandle, ConformanceFinding, ErrorEnvelope, diagnostics and eight request/response pairs. All fields without `?` are required, including nullable fields. Arrays are arrays even when empty. No unknown fields are accepted. Pydantic and generated tool JSON Schemas must match these declarations; TypeScript alone is not runtime validation.

### 7.1 Value validation and common semantics

| Type/field | Exact validation |
|---|---|
| ID | Nonempty UTF-8 string, <=512 bytes; synthetic IDs use reserved `view:` prefix, canonical IDs use `entity:`. |
| Digest | Exactly 64 lowercase hexadecimal characters. |
| Request ID | Nonempty <=128 UTF-8 bytes; copied unchanged. |
| Snapshot/revision | Snapshot must be complete and available; revision manifest lists actual repo revisions/digests. |
| Number | JSON number, finite; counts/depths/line numbers integers <=2^53−1. Confidence [0,1]. |
| Budget | limit_tokens integer 256..32768; explicit tokenizer enum; missing fields rejected. |
| Page/limit | search/similar limit and witness/finding page_size 1..200; evidence_page_size 1..50. |
| Traversal | max_depth 0..64, max_results 1..1000; visited IDs deduplicated; lexical BFS tie breaks. |
| Context | radius exactly 0,1,2; QI max_diameter integer 0..8. |
| Source range | Both null or both integers >=1 with end>=start; requests cannot read outside indexed file range. |
| Filter | Empty repo_ids means all build-set repos; empty subtypes means all; families/statuses must be nonempty unique arrays; runtime family requires compatible runtime_window. Flags apply to both endpoints. |
| Runtime window | RFC3339 UTC `Z` timestamps, start<end, exact environment selector. v1 uses one pre-aggregated collection window; incompatible/partial-window rate requests are rejected. |
| Strings | Source/query max 4096 UTF-8 bytes per search request; content responses use chunk budgets. Names from sources are bounded by input-file resource limits and never silently altered for identity. |
| Viewport | width/height 1..16384; DPR (0,4]; node_budget 1..500; curve_budget 0..2000; beta/strength [0,1]; R>0; near>0, far>near, fov (1,179); finite nondegenerate camera/up vectors. |

Default filters selected by the UI are `families=[static]`, statuses=[exact], tests/generated/vendor=false, external=true, no runtime window; requests transmit the defaults explicitly. Sort all output records by deterministic operation-specific order with ID as final tie-breaker. Pydantic uses strict validation rather than coercing `"1"` to 1.

For a NodeRecord representing an entity, `entity_id=id` and member_count=1 for atomic nodes or the active block's leaf count for collapsed representatives. Residual/QI/conceptual nodes have entity_id=null, kind identifying the group, sort=synthetic, membership_handle nonnull and nullable depth where not meaningful. parent_id names the owning shell/group and need not be returned recursively; this is an explicit ancestry reference, not a relationship endpoint. EvidenceHandle IDs, source_subject IDs and content handles are likewise dereferenceable references, not hidden graph edges.

Every **RelationshipSummary** and **WitnessRecord** has source and target present in the same response's `data.nodes`. Summary IDs name projections; witness IDs name original relationships. Raw witness endpoints use atomic NodeRecords, not rolled-up endpoints. `source_subject_id` and `target_subject_id` identify original ownership subjects; they may be outside nodes unless explicitly requested. Evidence records link to relationships by handle; they do not multiply witness counts.

### 7.2 Operation behaviour

| Operation / interfaces | Normative behaviour |
|---|---|
| search_entities / SearchEntitiesRequest, Response | Baseline lexical mode only. Unicode casefold tokens split on non-word characters; require every query token to appear in qualified_name or rel_path. Score=100 exact qualified-name match +20 qualified-name prefix +5 per name-token hit +1 per path-token hit. Sort score descending then ID. No implicit hierarchy cascade or embeddings dependency. Hits reference nodes in this response. |
| get_architecture_context / GetArchitectureContextRequest, Response | Resolve focus, pins and ancestor spine; build requested grouping and DOI candidate context; helper-tree QI requires grouping.mode=atomic. Return focus/ancestor definitions, typed projections, boundary/Cayley records with scope and QI report. Mixed grouping takes revealed_ids; depth projects to the depth ancestor or the shallower leaf itself; kind grouping uses nearest qualifying ancestor, or singleton when no such ancestor exists. Conceptual grouping uses model mapping plus Unmapped. QI and grouping interaction follows §6.2, never an invented certificate for containment quotients. With qi.enabled=false return QIReport mode=off, A=1, B=0, diameter=0 and membership_handle=null. |
| inspect_relationship_witnesses / InspectRelationshipWitnessesRequest, Response | Exactly one of projection_id / relationship_id is nonnull. Projection and view must agree. Projection cursor pages distinct relationships; a raw ID yields one witness. Evidence cursor is valid only with a raw relationship_id and cursor=null; otherwise evidence pages begin at start independently for each witness. Each witness includes a nonempty evidence page or a nonnull continuation if budget cannot include one; at least one handle is preferred but endpoint closure is mandatory. total_witness_count is the full count before budgeting. |
| get_entity_content / GetEntityContentRequest, Response | Fetch snapshot content, not an unverified current working-tree file. Content kind must match source or attached documentary entity. Return complete lines in order with source range, chunk hash and untrusted-content tag. Line too long to fit produces no partial misleading line: return truncated result and a content handle/cursor; a later larger budget or bounded range is needed. |
| find_dependants / FindDependantsRequest, Response | Run on directed original subject facts, incoming means reverse traversal/callers; outgoing means dependencies/callees. A file/container input seeds all its atomic subjects at hop 0, displayed as members of that requested scope; a symbol seeds itself. BFS visited set and queue sorted by (hop,ID). For incoming traversal, witness_path_ids follow traversal order but retain original edge orientation in witnesses. One shortest lexicographic witness path per result; pack each path atomically with all vertices/edges. max_depth/result caps set traversal_complete=false when a frontier remains. QI summaries are never traversal edges. |
| check_architecture / CheckArchitectureRequest, Response | Evaluate §1.2 after mapping original subjects. Require filter families=[static] and statuses=[exact]; candidate/unresolved facts are still consulted for coverage limitations. scope_id restricts source membership; retain crossing target components and disclose coverage. Return findings and mapping counts for the entire scope, paginated findings. Component NodeRecords are synthetic and included for findings; a zero-witness missing expectation is a finding, not a fabricated relationship. include_satisfied=false excludes nonviolating match/allowed/forbidden-absent records. |
| find_similar_code / FindSimilarCodeRequest, Response | Return other supported function/method entities matching §5 hashes; exclude query entity, honour repo_ids. Exact mode verifies normalised bytes; WL mode labels every match candidate. Stable ID ordering; no threshold inferred from hashes. |
| viewport_frame / ViewportFrameRequest, Response | POST /api/v1/viewport/frame. Build Pi(E), include context shells separately, compute view-local residual geometry and canonical curve frames. `spheres.role` controls membership; context_shell does not count edges. Each sphere references a returned node and each curve a returned summary. Knots/degree/control_points are pre-lane geometry; client applies offsets/lens per §4. scene budget may omit geometry while graph results remain pageable. Never return a curve whose endpoints/spheres are missing. |

Scope-wide diagnostic arrays can themselves be budgeted; omitted_items counts their omission, and handles/cursors retain access. Node ancestry omitted due to budgeting is disclosed; the focus definition is mandatory for focus operations. The empty graph example in the old specification is replaced by these typed contracts, not treated as a valid context result for an existing focus.

### 7.3 Cursors, errors and transport mapping

Cursor payload is canonical JSON `{v:1,snapshot_id,query_digest,view_id,collection,after_id}` signed HMAC-SHA256 with a local 32-byte service secret, encoded base64url(payload) + `.` + base64url(signature). IDs are scoped by the query digest, not user-editable SQL. Decode length <=4096 bytes, verify signature constant-time, version, current snapshot and identical query (excluding request_id/cursor/budget). Budgets/page sizes can change between pages; filters cannot. Budget-skipped items remain pending in a server-side immutable ordered page plan; after_id is a plan ordinal ID, not “last object we happened to print”. Plan digest is included in query_digest. No OFFSET and no silent skip at budget gaps.

For direct witness paging, plan order is relationship_id and cursor collection names the projection/evidence list. For greedy context, keep a query plan of accepted and deferred bundle IDs; a cursor advances only through delivered items, with deferred items queued for the next page. Cursor replay is deterministic for the same snapshot/plan/tokenizer; retention lasts while the snapshot is available.

HTTP errors: INVALID_REQUEST/RULE_CONFLICT=400, NOT_FOUND=404, SNAPSHOT_MISMATCH/INVALID_CURSOR=409, SNAPSHOT_UNAVAILABLE=410, INCOMPLETE_BUILD=409, BUDGET_TOO_SMALL=422, TOKENIZER_UNAVAILABLE=503, LAYOUT_FAILED/INTERNAL_ERROR=500, CANCELLED=409. ErrorEnvelope includes retryability and optional minimum_tokens. Errors are not packed as successful graph data; protocol-level parse errors follow MCP JSON-RPC codes.

MCP tools expose the seven operation names with readOnlyHint=true, destructiveHint=false. Return the success envelope once in structuredContent with no duplicate JSON text block; errors use isError=true and ErrorEnvelope. SDK/protocol framing is separate from the payload budget. Viewport is HTTP-only; its service uses the same graph queries.

## 8. Graph-consistent greedy packing — product §13 / C9

### 8.1 Canonical serialisation and counted region

Define `J(x)` as UTF-8 JSON with recursive lexicographic object keys, arrays in declared deterministic order, ensure_ascii=false, compact separators, no NaN/Infinity and no insignificant whitespace. Server Python serialisation is authoritative; clients do not recalculate budgets from JavaScript float formatting.

The **budgeted_json** region is the SuccessEnvelope with its top-level `budget` field removed. This avoids a self-referential token-count field. `used_tokens` is exactly the tiktoken count of that region, or explicitly byte/4 estimate in fallback. The final complete SuccessEnvelope, including budget report, is also measured as a separate acceptance guard and must fit limit_tokens. Thus report overhead cannot cause an oversize success even though it is outside the reported region. MCP JSON-RPC wrappers, SSE framing, tool schemas and the caller's other prompt content are outside this local tool-result contract and require caller-side reservation.

`accounting_upper_bound` is the budgeted-region exact count in tiktoken mode; in fallback it is its full UTF-8 byte length. `guarantee=exact_payload` identifies exact local tokenizer enforcement, not total model prompt accounting. `guarantee=byte_bound` identifies conservative enforcement with estimated used_tokens. No “exact total provider tokens” claim is made.

### 8.2 Atomic candidate bundles

Create candidate units with explicit dependencies and priority tier:

0. Required envelope metadata, query digest, coverage report handle, omissions, focus node and minimum response fields for the operation. This is mandatory.
1. Focus ancestors/pins and explicitly requested witness/path/finding bundles. If request requires one indivisible item that cannot fit, return BUDGET_TOO_SMALL with its measured minimum rather than an unrelated success.
2. Rule violations, focus incident relationships, exact witness samples and important structural diagnostics.
3. Additional context nodes, ordinary relationships, candidates and full-line source chunks.

Each relationship unit contains its summary and endpoint NodeRecords. Each witness unit contains its raw endpoints and evidence references/pages. A traversal result contains its complete witness path and all endpoint definitions. A finding includes both component NodeRecords plus references/handles; referenced relationship objects, if included, obey the same closure. Geometry units depend on node definitions, endpoint spheres and summary. Deduplicate dependencies by typed ID before costing.

Assign utilities deterministically: explicit request=1000, violation=500, focus incident=200, witness=150, diagnostic=100, ancestor=80, other node/edge=20, source line=10. Within each tier sort by decreasing `utility/max(1,incremental_cost)` recomputed against the current accepted set, ties by stable unit ID. This is a greedy precedence-constrained knapsack heuristic, not a claim of optimal compression.

### 8.3 Exact admission algorithm

```text
1. Validate request; bind immutable snapshot/query plan; load the requested local encoder.
2. Build mandatory state M, all candidate units, complete totals and continuation plan.
3. finalise(S):
     a. Materialise all objects from S with deduplication and endpoint closure.
     b. Compute exact omitted_* counters against full scope/plan; generate cursor.
     c. Set budget report from J(envelope without budget).
     d. Serialise complete envelope; count full bytes/tokens as specified below.
     e. Return this frozen envelope and full cost; no later mutable timestamp fields.
4. If finalise(M) does not fit, return BUDGET_TOO_SMALL (errors are out of band).
5. For each tier, recompute candidate incremental costs and select best utility/cost.
   Tentatively add the entire candidate dependency closure; run finalise again.
   Commit only if full cost <= limit AND the reported region count <= limit;
   otherwise defer that unit and try other units.
   Units that share endpoints may get cheaper later; revisit deferred units once
   whenever their dependency set changes. Stop at a fixed point or no remaining units.
6. Validate closure for every summary/witness and geometry reference, re-finalise
   all counters/cursor, and count the final full envelope one last time.
   If it overflows, remove the lowest-priority optional unit plus all dependent
   units and repeat. Never strip an endpoint node under a retained relationship.
7. Return the frozen checked envelope. Cursor exposes undelivered items; omissions
   and truncated=true remain accurate even when small later candidates fitted.
```

In exact mode `cost=number of encode_ordinary tokens in J(full envelope)`. In fallback `cost=len(UTF8(J(full envelope)))`, not bytes/4. Admission enforces cost<=L. Because a byte-pair tokenisation of valid UTF-8 has at most one token per byte, this fallback also conservatively bounds either declared byte-level encoding if it is later loaded; the published byte/4 figure remains only an estimate. If a future encoding lacks this property, fallback must be disabled for it.

Token costs are not additive across serialised JSON boundaries, so per-object estimates are only sorting hints. Every admission and final response uses the whole finalised envelope. Removing fields can also change tokenisation non-monotonically; the finite deletion loop terminates at mandatory M or errors. Exact mode guarantees the full-envelope token count<=L and the reported region count<=L (check both explicitly). Fallback guarantees full bytes<=L and estimate<=L. There is no guarantee that an error envelope fits a deliberately impossible user budget; errors use the protocol error channel and include the minimum successful payload cost.

## 9. Core execution stages and release gates — product §17

| Stage | Deterministic output now required | Gate |
|---|---|---|
| 1 — Extract and normalise | Snapshot manifest, Python scopes/import map, exact/candidate/unresolved facts, source evidence, scope atoms, py-ast-v1 representations/hashes, documentary hyperedges. | C1/C2/C5; fixtures for shadowing, decorators, re-exports, dynamic dispatch and identical vs alpha-renamed bodies. |
| 2 — Project and analyse | Default partitions/witness maps, per-level SCCs/ranks, three synchronous WL rounds, boundary ratios and Cayley simple-projection logs/bounds. | C3/C4/C6/C13; independently recompute counts, directions, ranks and degree-bound fixtures. |
| 3 — Summarise and serve | Default helper-tree BFS contraction with measured diameters and certificates, focus-specific protected variants, shared typed services, token packer, rules engine and Advanced Inspector values. | C9/C10; all-pairs distance checks on small graphs, endpoint closure and adversarial-budget fixtures. |
| 4 — Spatial/UI and hardening | sphere-pack-v1, deterministic spline lanes/EdgeLens, neutral workspace, list/matrix, saved views, incremental invalidation and failure handling. | C7/C8/C11/C12/C14 plus original usability comparisons. |
| 5 — Further research | Alternative spectral summaries, exact Cayley completion/edit solvers, broader-language dispatch, live telemetry and stronger compression certificates. | Separate evidence and performance review; baseline diagnostic computations above are not deferred here. |

UI and schema work can proceed against declaration fixtures, but no production slice is complete without the indicated correctness gates. Advanced diagnostics are computed even when the inspector section is closed; opening it must not substitute canned numbers.

### Required engineering fixtures in addition to C1–C14

- SQLite: execute DDL; insert a two-repo workspace with cross-repo directed calls and parallel evidence; reject cross-snapshot endpoint/parent references, malformed JSON, invalid enums/booleans, bad hashes, inconsistent self-edge flags and duplicate witness assignment. Run foreign_key_check after deferred inserts.
- Partition: enumerate legal E for a small irregular tree, including scope atoms; prove every atom occurs once and every raw edge projects once. Test the explicit A/B residual example and partially filtered groups.
- LCA/DOI: compare all pairs to naive ancestor traversal, including cross-repository roots, root focus and deeply nested functions.
- Geometry: high fan-out/mixed radii, coincident initial positions, bounded solver exhaustion and guaranteed line fallback. Validate knot count N+p+1, endpoints, N0=3 preservation, beta endpoints, opposing lanes, and lens continuity.
- AST/WL: local-variable alpha-renaming, keyword parameter changes, changed call targets, nested/free bindings, reflection disablement, docstrings vs runtime strings, reversed edges and relation-type changes. WL collisions remain candidates.
- Boundary/Cayley: a path, star, isolated vertex, bidirectional parallel edges, loops and disconnected graph. For star K(1,q), the degree bound is (q−1)/2; do not confuse this with a latency claim.
- QI: helper paths and trees, adjacent proposed seeds, protected focus/pins, ineligible cycles and disconnected components. Check intrinsic diameter and `dH<=dG<=(b+1)dH+b` on every finite pair in small fixtures. Test that a quotient directed path without a lift is never used by find_dependants.
- Packing: exact budget edge, metadata overhead, non-ASCII strings, special-token-looking content, long lines, huge names, both tokenizers, missing offline weights, cursor resumption and optional bundle eviction. Assert all relationship/witness endpoints and all rendered curve dependencies are present in every successful response.

Reference performance dataset remains 50k entities/150k relations. Lock the C14 hardware target to Windows 11 x64, Intel Core i5-1235U, 16 GiB RAM and Iris Xe-class integrated graphics, 1440×900/DPR1, with Chromium build recorded in each run. This is a target profile, not an assertion that this machine was used for document checks. The available development/contract-check host was inventoried on 6 November 2026: Windows 11 Home 10.0.26200, AMD Ryzen 7 5800X, 31.9 GiB RAM, NVIDIA GTX 1080 and Radeon RX 5500 XT. Results on that host alone cannot establish integrated-GPU acceptance; the rendering run must record the selected adapter. No application performance results are claimed.

Functional fixtures are synthetic checked-in repositories. First real-repo acceptance is [ToolSet](D:/Aletheia_project/DEV_TOOLS/ToolSet) at verified commit `f8bc1ec4c54884293dace635275e95c685b03371`, using a clean snapshot with declared source roots `aletheia_toolchain` and `local_tool_assist_mcp`; uncommitted working-tree files must not silently replace that revision. Include tests for impact workflows and exclude virtual environments, caches and bundled/generated archives by path segment rules. Add a declared two-repo import fixture for resolution/merge checks. Performance scaling uses generated fixture graphs with fixed seed `geographer-benchmark-v1`, not the 53-node demo. Any changed repository revision is a new benchmark manifest, never an undocumented replacement.

## 10. Final decision ledger and limits

| Product section | Engineering choice now locked |
|---|---|
| §7 | Bottom-up capped/log preference with feasibility-driven radii; Fibonacci initialisation; deterministic projection and feasible line fallback; epsilon 1e−4. |
| §8 | Ancestor-closed revealed-branch E, formal residual partition, atom endpoint normalisation, one membership per leaf, binary lifting and depth-relative DOI. |
| §9 | Shared per-pair clamped spline, Method 1, N0>3 LCA policy, canonical n/b frame, deterministic lanes and smoothstep EdgeLens. |
| §10 | Linked executable STRICT SQLite schema and indexed keyset witness contract. |
| §11 | py-ast-v1, directed-wl3-v1, degree-volume boundary ratios, certified helper-tree hop contraction and scoped Cayley degree bound in the core pipeline. |
| §13 | Linked complete wire declarations, strict validation, snapshot-bound cursors and dependency-closed full-envelope budget admission. |
| §17 | Deterministic diagnostics in Stages 1–3; UI/hardening Stage 4; stronger unvalidated research remains Stage 5. |
| §18 | Python ast/symtable resolver, tree-sitter fallback, strict YAML/JSON Schema, explicit tiktoken encodings, pinned standard MCP transports and declared benchmark profile. |

The safeguards remain binding: static resolution is exact only where justified; normalised AST equality is not behavioural equivalence; WL is a candidate generator; contraction bounds apply to the declared undirected metric and partition; omitted subgraphs do not inherit that certificate; boundary ratios are not global Cheeger minima; Cayley regularity is not a software quality target; token estimates are not exact counts; geometry does not create facts. These limits are encoded in the engineering contracts rather than postponed to implementation judgement.

## 11. Contract validation performed for this blueprint

These are specification-artifact checks, not application implementation or release acceptance results:

- Executed the exact DDL under SQLite 3.40.1: 14 STRICT tables and 18 named indexes; integrity_check and foreign_key_check passed after a cross-repository fixture with parallel calls and one-to-many evidence. Nine invalid SQL mutations were rejected.
- Validated the rules JSON Schema itself and the supplied YAML example; invalid policy/version and unknown-field cases were rejected.
- Compiled the declaration-only wire file with `tsc --strict --noEmit --skipLibCheck false`; passed after the final schema update.
- Enumerated 25 legal revealed-branch states on an irregular fixture; all partitions covered each leaf once and counted every possible leaf-pair edge once. All-pairs LCA distances matched naive BFS.
- Checked helper-tree ball contraction on all 145 labelled trees of orders 2–5: 3,412 vertex-pair comparisons satisfied the stated distortion inequalities.
- Checked 64 deterministic line-packing fallback cases with varying radii, knot lengths for N=2..10, Greville linear reproduction and positive lane spacing at interior sample parameters.
- Verified local document links and that C1–C14 remain present, unchanged and in order in the product specification.

Offline tiktoken package import succeeded, but neither declared encoding's weight data was cached on this host. Network retrieval was disabled during that check. Exact-encoder budget fixtures therefore remain an implementation gate; the blueprint specifies both the exact admission algorithm and conservative offline path without claiming they have already been implemented. The bounded projection solver, renderer, resolver, MCP server and runtime schemas likewise require the application-stage tests listed above.
