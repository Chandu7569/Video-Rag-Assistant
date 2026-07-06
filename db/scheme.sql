-- Enable the pgvector extension (run once per database)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    external_id TEXT,              -- meeting_id, doc_id, crm_record_id, etc.
    source_type TEXT NOT NULL,     -- 'transcript' | 'summary' | 'doc' | 'crm'
    text TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(384),         -- must match EMBEDDING_DIM in config.py
    created_at TIMESTAMP DEFAULT NOW()
);

-- Speeds up similarity search (cosine distance)
CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Speeds up filtering by source_type (e.g. "summaries only")
CREATE INDEX IF NOT EXISTS documents_source_type_idx
    ON documents (source_type);