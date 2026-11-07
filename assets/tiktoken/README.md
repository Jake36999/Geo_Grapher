# Offline encoding assets

The two `.tiktoken` files are the public byte-pair rank files used by the official tiktoken encoding definitions. They were fetched explicitly by `geographer cache-tokenizers`, not during a tool query.

| Encoding | Origin | SHA-256 |
|---|---|---|
| o200k_base | https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken | `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d` |
| cl100k_base | https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken | `223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7` |

`TokenCounter` verifies these hashes and constructs the official encoding from local ranks and the installed tiktoken definition. It does not change module-global loaders, fetch network data or infer encodings from a model alias. `TIKTOKEN_CACHE_DIR` can point to a directory with the same named files. Tests compare both encodings against official `get_encoding` calls using a checksum-verified offline cache and disabled network functions.

With absent weights, callers must explicitly permit byte fallback. Reported byte/4 counts are estimates; the independent whole-envelope byte bound enforces the conservative budget.
