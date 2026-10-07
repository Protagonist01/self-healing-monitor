# ADR-004: Embedded ChromaDB for runbook retrieval

## Status

Accepted for the single-host demo. Chroma HTTP server mode is disabled pending
upstream security fixes; see [dependency review](../dependency-security.md).

## Context and decision

Runbooks live in `infra/runbooks/`. Obvious memory, error, and service-down incidents
first use a deterministic keyword match. If no keyword match is found, the indexer
chunks Markdown at H1/H2 boundaries and searches an embedded persistent Chroma collection.
It indexes changed files on retrieval, using content hashes; removed files are removed
from the collection. `scripts/index_runbooks.py` can pre-index and query the library.

Without an OpenAI key, a project-owned hash embedding produces 384-dimensional vectors
from technical vocabulary. With a key, `text-embedding-3-small` is the default embedding
model. Sentence Transformers and remote model execution are not configured.

The query combines alert name, service, and log summary. The top result contributes a
bounded excerpt to diagnosis. No retrieval accuracy or latency benchmark is claimed.
Hash embeddings cannot guarantee semantic matches between different vocabulary.

## Tradeoffs

Embedded persistence avoids running another network service, but the Python package
and its transitive dependencies make the image larger. The supported healer is a
single process; multi-instance vector-store coordination is outside this deployment.
The three supplied runbooks make a small demonstration set, not a comprehensive
operations knowledge base. Top-1 retrieval can select an irrelevant section.

Switching embedding providers changes vector dimensions. Use a separate index directory
and reindex when switching between local hash and OpenAI embeddings. Do not point the
new embedding configuration at an old collection with different dimensions.

## Verification

```sh
python scripts/index_runbooks.py --query "high memory usage"
```

Review the returned document and distance against the intended runbook. Distance is
not a calibrated relevance percentage. Unit tests cover deterministic local vectors;
provider retrieval quality requires separate reviewed examples.
