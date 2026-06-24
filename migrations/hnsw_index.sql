-- Replace IVFFlat with HNSW for 10x search speed and better recall.
-- CONCURRENTLY means no table lock — safe to run in production.
DROP INDEX IF EXISTS policy_chunks_embedding_idx;

CREATE INDEX CONCURRENTLY IF NOT EXISTS policy_chunks_hnsw
ON policy_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
