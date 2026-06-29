# ADR-004: Use ChromaDB for Runbook Retrieval (RAG)

## Status
Accepted

## Context
The Context Gather node needs to find the most relevant runbook for a given incident before the LLM diagnosis step. Runbooks are markdown files stored in `infra/runbooks/`. As the runbook library grows, keyword matching becomes brittle — an alert named `HighMemoryUsage` might be best served by a runbook titled "Handling OOM Events", which has no keyword overlap with the alert name.

Semantic retrieval (embedding-based similarity) is the right approach. The question was which vector store to use.

## Decision
Use **ChromaDB** (in-process, persistent mode) with `sentence-transformers/all-MiniLM-L6-v2` as the embedding model.

Runbooks are chunked, embedded, and indexed at startup if the collection doesn't exist or if runbook files have been modified since last indexing (detected via file hash comparison).

The retrieval query is constructed from: `alert_name + alert_labels + first 3 log lines`. Top-1 result is used; the matched runbook section is included in the context passed to the Diagnose LLM.

## Consequences

**Why ChromaDB over alternatives:**

| Option | Reason not chosen |
|--------|------------------|
| Pinecone / Weaviate | Requires external service; adds cloud dependency and cost |
| pgvector | Would require a PostgreSQL extension — adds ops complexity for a feature that's read-mostly |
| FAISS directly | No persistence layer; requires manual serialization; less ergonomic Python API |
| Simple keyword search | Brittle on vocabulary mismatch between alert names and runbook titles |

ChromaDB runs in-process with persistence to a local directory — same operational profile as DuckDB. No server to manage. The Python client API is straightforward and the library is actively maintained.

**Embedding model choice:**
`all-MiniLM-L6-v2` is 80MB, runs on CPU in ~10ms per query, and ranks well on semantic similarity benchmarks for short technical text. A larger model would improve retrieval quality marginally but add latency to an already time-sensitive context-gathering step.

**Gained:**
- Semantic runbook retrieval survives vocabulary mismatch between alert names and runbook content
- In-process, no external service to manage
- Runbook updates are automatically re-indexed at startup
- Retrieval latency ~10–15ms — negligible relative to the overall pipeline

**Trade-offs:**
- `sentence-transformers` is a heavy dependency (~500MB with model weights); first startup takes ~30s to download
- In-process ChromaDB is not suitable for multi-instance healer deployments (no shared vector store). Documented in `docs/deployment.md` — use ChromaDB server mode for multi-node deployments
- Top-1 retrieval may miss the best runbook if the runbook library is large and the alert description is ambiguous. Top-3 with re-ranking is a planned improvement

**Mitigation:**
`scripts/index_runbooks.py` can be run standalone to pre-index runbooks and verify retrieval quality before deployment:
```bash
python scripts/index_runbooks.py --query "high memory usage payment service"
# → Matched: high_memory.md (score: 0.91)
```
