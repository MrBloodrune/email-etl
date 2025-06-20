-- Migration script to add provider support to existing database
-- Run this after the initial schema is created

-- Add provider columns to emails table
ALTER TABLE emails 
ADD COLUMN IF NOT EXISTS provider VARCHAR(50) DEFAULT 'gmail',
ADD COLUMN IF NOT EXISTS provider_account VARCHAR(255);

-- Create index on provider columns
CREATE INDEX IF NOT EXISTS idx_emails_provider ON emails(provider);
CREATE INDEX IF NOT EXISTS idx_emails_provider_account ON emails(provider, provider_account);

-- Create provider_config table for storing provider-specific settings
CREATE TABLE IF NOT EXISTS provider_config (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    account VARCHAR(255),
    config_key VARCHAR(100) NOT NULL,
    config_value TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(provider, account, config_key)
);

-- Create provider_tokens table for OAuth tokens and credentials
CREATE TABLE IF NOT EXISTS provider_tokens (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    account VARCHAR(255) NOT NULL,
    token_type VARCHAR(50) NOT NULL, -- 'access_token', 'refresh_token', etc.
    token_value TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(provider, account, token_type)
);

-- Update trigger for provider tables
CREATE TRIGGER update_provider_config_updated_at BEFORE UPDATE
    ON provider_config FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_provider_tokens_updated_at BEFORE UPDATE
    ON provider_tokens FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add provider info to audit log
ALTER TABLE email_audit_log
ADD COLUMN IF NOT EXISTS provider VARCHAR(50);

-- Create view for emails by provider
CREATE OR REPLACE VIEW emails_by_provider AS
SELECT 
    provider,
    provider_account,
    COUNT(*) as email_count,
    COUNT(DISTINCT sender) as unique_senders,
    MIN(date) as earliest_email,
    MAX(date) as latest_email,
    SUM(CASE WHEN has_attachments THEN 1 ELSE 0 END) as emails_with_attachments
FROM emails
GROUP BY provider, provider_account;

-- Update hybrid search function to include provider filter
CREATE OR REPLACE FUNCTION hybrid_email_search(
    query_embedding vector(1536),
    query_text TEXT,
    limit_count INTEGER DEFAULT 10,
    date_from TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    date_to TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    provider_filter VARCHAR(50) DEFAULT NULL,
    account_filter VARCHAR(255) DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    message_id VARCHAR(255),
    subject TEXT,
    sender VARCHAR(255),
    date TIMESTAMP WITH TIME ZONE,
    provider VARCHAR(50),
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
        e.provider,
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
        (date_to IS NULL OR e.date <= date_to) AND
        (provider_filter IS NULL OR e.provider = provider_filter) AND
        (account_filter IS NULL OR e.provider_account = account_filter)
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
-- GRANT ALL ON provider_config TO gmail_etl_user;
-- GRANT ALL ON provider_tokens TO gmail_etl_user;