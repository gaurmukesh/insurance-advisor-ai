-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Policy chunks table for RAG
CREATE TABLE IF NOT EXISTS policy_chunks (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata TEXT,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS policy_chunks_embedding_idx
    ON policy_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
