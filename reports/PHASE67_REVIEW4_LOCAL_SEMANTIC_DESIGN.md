# Local semantic design and independent review registration

Registered before dispatch, 2026-11-13. This is engineering preparation while L1 checks run, not a benchmark or permission to start L2 product changes early.

One bounded DeepInfra design review: `deepseek-ai/DeepSeek-V4.1-Flash`, temperature 0.2, no thinking, output at most 2048 tokens, task allowance $0.03 from the approved workflow cap. Approved delegation script and ledger only, spendable lifetime ceiling $14.24739611, mandatory script dry run before dispatch. No retries registered. Construction allowance $0.35 plus the registered remaining evaluation estimate $5.91253291 plus this review allowance $0.03 gives **$6.29253291**, below $6.50; reserve unchanged. The packet contains architecture requirements only, no source or question/key data. Its output is advice, not an implemented or verified result.

Proposed implementation:

- Optional `semantic` extra for numpy/model2vec; separate optional fastembed backend. Disabled unless configured explicitly. A strict allow-list rejects hosted/API encoder specifications before any source representation is built. Load a local model directory at runtime; provisioning downloads model weights explicitly without supplying source text.
- Represent each entity using split name, signature, own documentation, associated comments and parent path. A string constant includes bounded literal text extracted with AST/literal evaluation, never import/exec. Version and hash this representation.
- New ingestion may write derived embeddings before snapshot publication. Existing published graphs use an explicit backfill into an immutable derived-analysis sidecar, keyed by snapshot, model-file digest, representation version and text hash. Do not migrate or rewrite canonical facts. No silent model loading or cache population on the ordinary default read path.
- Prebuild caches explicitly; validate snapshot/entity membership, row text hashes, model digest, vector shape and finite values when reading. Normalize vectors, handle zero vectors, deterministic cosine ranking/ties. Lexical and semantic channels fuse by reciprocal-rank fusion; retain exact symbol priority and graph scope. Per-hit match labels identify lexical/semantic/both.
- Query vectors are computed locally, with network-free local model loading. Keep candidate work bounded. Wire packing still caps the whole envelope and explicitly reports omissions. Both actual cold/warm timings and sidecar bytes are measured.
- The offline evaluator scores first retrieval and simulated FP1/FP2 separately. The implementer sees only development data; v2 remains sealed. Test hosted-spec rejection, no source execution, immutable caches, model/snapshot invalidation, graph isolation, exact priority, token/character caps and default-off behavior before enabling the feature.

Open review question: identify concrete defects in this plan and a minimal safe integration strategy for immutable ingestion and the current front door. Do not propose model-hosted embeddings or benchmark-specific behavior.
## Independent review outcome

Completed once: DeepSeek receipt `20261113T185935-5e2c08c4`, cost **$0.00100520**, no truncation. Preflight reserve was $0.00146820. Raw advice and receipt are retained under `D:/Librarian_V2/tmp/deepinfra-delegation/runs/20261113T185935-5e2c08c4-review4-semantic-design.*`. The workflow's cumulative committed spending after this call is **$0.26443984**, leaving **$6.23556016** below its hard cap, with the nonspendable pool reserve unchanged.

Accepted refinements before implementation: one common write-once population function for ingestion/backfill; fingerprint tokenizer/model files, library versions and normalization/truncation settings; canonical versioned text fields; zero vectors omitted from cosine ranking (zero query gives no semantic candidates); fixed RRF k=60 and bounded candidate depth 200 with exact priority then canonical-ID tie breaks; pure specification validation separate from explicit model loading; default-off opens no semantic sidecar. Model weights may be provisioned separately without source text.

The reviewer correctly distinguishes the sealing policy from access control. This shared unrestricted workspace cannot provide independent implementer credentials. V2 separation is enforced by workflow, separate private artifacts and evaluator path/hash guards; it is not claimed to be an operating-system access boundary. No v2 questions or keys were supplied to this review.

Inference API reference consulted: [Model2Vec official inference documentation](https://minish.ai/packages/model2vec/inference/), which documents loading from a local directory. The implementation will use that local-path mode and will not add a hosted encoder adapter.

