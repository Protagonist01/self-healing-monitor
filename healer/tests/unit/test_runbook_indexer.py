from healer.src.rag.runbook_indexer import LocalHashEmbeddingFunction


def test_local_hash_embeddings_are_deterministic():
    embedding_fn = LocalHashEmbeddingFunction(dimensions=32)

    first = embedding_fn(["high memory oom"])
    second = embedding_fn(["high memory oom"])

    assert [list(vector) for vector in first] == [list(vector) for vector in second]
    assert len(first[0]) == 32


def test_local_hash_embeddings_distinguish_documents():
    embedding_fn = LocalHashEmbeddingFunction(dimensions=32)

    high_memory, high_errors = embedding_fn(["memory oom restart", "http 500 exception"])

    assert list(high_memory) != list(high_errors)
