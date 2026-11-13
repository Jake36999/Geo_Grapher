# Optional local semantic search

Semantic search is **off by default**. The `semantic` extra uses Model2Vec static embeddings. `semantic-fastembed` provides an optional local ONNX backend. Neither backend has a hosted embedding adapter. Source is represented and encoded on the local machine; ingestion does not import or execute source files.

Build this feature branch's candidate wheel, then install its extra in the environment that will serve Geo Grapher:

```powershell
uv pip install 'C:/path/to/geo_grapher-<version>-py3-none-any.whl[semantic]'
```

For an isolated installed-wheel launch, request its extra explicitly: `uvx --from 'C:/path/to/geo_grapher.whl[semantic]' geographer ...`. Use the same Python version and architecture as the cache builder. The encoder fingerprint covers model/tokenizer assets, library versions, Python/architecture, normalization/truncation settings and the encoder implementation. A changed fingerprint requires an explicit new cache population; it never silently substitutes a model.

## Explicit provisioning and migration

The repository helper `scripts/provision_semantic_model.py --destination <absolute-directory> --receipt <new-json-path>` downloads only public model assets and records their exact revision and hashes. It accepts no code/source input. Ordinary server reads never download weights or populate caches.

Backfill published snapshots using an interpreter with the extra installed:

```powershell
python scripts/build_semantic_cache.py --catalog <catalog.sqlite> --graph librarian-v2 --graph ToolSet --model model2vec:D:/models/potion-base-8M --cache D:/derived/semantic.sqlite --out <new-build-report.json>
```

The helper opens canonical stores read-only, verifies their hashes are unchanged and writes only the explicitly named derived sidecar. Old snapshots need no canonical schema migration. Sidecar namespaces are write-once: snapshot, encoder fingerprint, representation version and per-entity text hashes identify the analysis. Existing matching vectors are validated and reused. New namespaces append; conflicting data is refused. Model or membership mismatches fail closed.

For new programmatic ingestion, `ingest(..., semantic={"cache": sidecar_path, "encoder": load_encoder(local_spec)})` populates through the same write-once path before publication. Omitting `semantic` preserves the default pipeline. Representations cover code declarations, including own documentation, adjacent comments and bounded static string literals; truncation is recorded. Zero vectors are omitted from cosine ranking. Query work and candidate pools are bounded, and exact symbols retain priority before deterministic ID tie breaking.

## Serving

```powershell
geographer serve-graphs --catalog <catalog.sqlite> --semantic-model model2vec:D:/models/potion-base-8M --semantic-cache D:/derived/semantic.sqlite
```

Equivalent opt-in environment variables are `GEOGRAPHER_SEMANTIC_MODEL` and `GEOGRAPHER_SEMANTIC_CACHE`. Both must be supplied. With neither set, the server opens no semantic sidecar and loads no encoder. For FastEmbed, install `semantic-fastembed` and use `fastembed:BAAI/bge-small-en-v1.5@D:/models/local-onnx`; its local directory must already contain the supported model assets. Loading uses `specific_model_path`, `local_files_only=True` and CPU providers. Model2Vec is the backend measured for this release; FastEmbed is an optional adapter, not a claim of measured superiority.

Search still accepts plain `search_entities(graph_id, query)`. Pass the question verbatim and optionally up to two identifier guesses in `also`. Enabled channels return per-hit `match: lexical|semantic|both`. Whole-envelope token and character caps still apply. If a response returns `next_offset`, repeat the same query with `offset=next_offset` to reach omitted candidates. Pagination changes neither rank nor graph scope.

Episode recovery uses standard MCP metadata, outside model-facing arguments; see [the recovery contract](RECOVERY_DESIGN.md). Offline recall reports are raw candidate ranks. Capped delivery and end-to-end answer success are measured separately. Turning the feature on does not qualify a Librarian helper route or approve a merge/release.

Reference APIs: [Model2Vec local inference](https://minish.ai/packages/model2vec/inference/) and [FastEmbed local model parameters](https://github.com/qdrant/fastembed/blob/main/fastembed/text/text_embedding.py).
