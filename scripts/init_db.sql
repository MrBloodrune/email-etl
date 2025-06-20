-- Create database (run as superuser)
-- CREATE DATABASE gmail_etl;

-- Connect to gmail_etl database and run:

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop existing tables if they exist
DROP TABLE IF EXISTS attachments CASCADE;
DROP TABLE IF EXISTS emails CASCADE;

-- Create emails table with embeddings
CREATE TABLE emails (
    id BIGSERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    thread_id VARCHAR(255),
    subject TEXT,
    sender VARCHAR(255),
    sender_name VARCHAR(255),
    recipients TEXT[],
    cc_recipients TEXT[],
    bcc_recipients TEXT[],
    date TIMESTAMP WITH TIME ZONE,
    body_plain TEXT,
    body_html TEXT,
    body_markdown TEXT,
    labels TEXT[],
    has_attachments BOOLEAN DEFAULT FALSE,
    embedding vector(1536), -- OpenAI text-embedding-3-small dimension
    markdown_path TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create attachments table
CREATE TABLE attachments (
    id BIGSERIAL PRIMARY KEY,
    email_id BIGINT REFERENCES emails(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    mime_type VARCHAR(255),
    size_bytes BIGINT,
    content_hash VARCHAR(64), -- SHA-256 hash
    is_safe BOOLEAN DEFAULT NULL,
    scan_results JSONB DEFAULT '{}',
    file_path TEXT, -- Path in markdown structure
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_emails_embedding_cosine ON emails 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_emails_date ON emails(date DESC);
CREATE INDEX idx_emails_sender ON emails(sender);
CREATE INDEX idx_emails_thread ON emails(thread_id);
CREATE INDEX idx_emails_labels ON emails USING GIN(labels);
CREATE INDEX idx_emails_message_id ON emails(message_id);

CREATE INDEX idx_attachments_email_id ON attachments(email_id);
CREATE INDEX idx_attachments_mime_type ON attachments(mime_type);

-- Create full-text search index
CREATE INDEX idx_emails_fts ON emails 
USING GIN(to_tsvector('english', 
    COALESCE(subject, '') || ' ' || 
    COALESCE(body_plain, '') || ' ' || 
    COALESCE(sender_name, '')
));

-- Create update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_emails_updated_at BEFORE UPDATE
    ON emails FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create audit log table
CREATE TABLE email_audit_log (
    id BIGSERIAL PRIMARY KEY,
    email_id BIGINT,
    action VARCHAR(50),
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Function for hybrid search (vector + full-text)
CREATE OR REPLACE FUNCTION hybrid_email_search(
    query_embedding vector(1536),
    query_text TEXT,
    limit_count INTEGER DEFAULT 10,
    date_from TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    date_to TIMESTAMP WITH TIME ZONE DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    message_id VARCHAR(255),
    subject TEXT,
    sender VARCHAR(255),
    date TIMESTAMP WITH TIME ZONE,
    similarity FLOAT,
    rank FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.message_id,
        e.subject,
        e.sender,
        e.date,
        1 - (e.embedding <=> query_embedding) AS similarity,
        ts_rank(
            to_tsvector('english', 
                COALESCE(e.subject, '') || ' ' || 
                COALESCE(e.body_plain, '') || ' ' || 
                COALESCE(e.sender_name, '')
            ),
            plainto_tsquery('english', query_text)
        ) AS rank
    FROM emails e
    WHERE 
        (date_from IS NULL OR e.date >= date_from) AND
        (date_to IS NULL OR e.date <= date_to)
    ORDER BY 
        (0.7 * (1 - (e.embedding <=> query_embedding))) + 
        (0.3 * ts_rank(
            to_tsvector('english', 
                COALESCE(e.subject, '') || ' ' || 
                COALESCE(e.body_plain, '') || ' ' || 
                COALESCE(e.sender_name, '')
            ),
            plainto_tsquery('english', query_text)
        )) DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO gmail_etl_user;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO gmail_etl_user;