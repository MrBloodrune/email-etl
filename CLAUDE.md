# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Plugin-Based Email Provider System

The ETL pipeline now supports multiple email providers through a plugin architecture:

### Available Providers
- **Gmail** (implemented) - Uses Gmail API with OAuth2
- **IMAP** (ready for implementation) - For standard email servers
- **Outlook** (ready for implementation) - For Microsoft accounts

### Provider Commands
```bash
# List available providers
python main.py providers

# Authenticate with a specific provider
python main.py auth login --provider gmail

# Import emails from a specific provider
python main.py import full --provider gmail

# Test provider connection
python main.py auth test --provider gmail
```

## Commands

### Database Setup
```bash
# Create database and enable pgvector
createdb gmail_etl
psql -d gmail_etl -f scripts/init_db.sql

# Apply provider migration
psql -d gmail_etl -f scripts/migrate_providers.sql
```

### Development Commands
```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-api.txt  # For API features

# Set up environment
cp .env.example .env
# Edit .env with required credentials

# Authenticate with Gmail
python main.py auth login

# Run full import
python main.py import full --start-date 2024-01-01

# Incremental sync
python main.py import sync

# Semantic search
python main.py search semantic "query"

# Ask questions
python main.py search ask "What are my deadlines?"
```

### Docker Commands
```bash
# Start without observability
docker-compose up -d

# Start with Grafana Alloy observability
docker-compose --profile observability up -d

# Disable observability via override
cp docker-compose.override.example.yml docker-compose.override.yml
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f alloy
```

## High-Level Architecture

This is a multi-provider Email ETL pipeline with hybrid storage (PostgreSQL + Markdown) and LLM capabilities. The system uses a plugin architecture to support multiple email providers (Gmail, IMAP, Outlook, etc.).

### Core Flow
1. **Provider Authentication** → Provider-specific auth (OAuth2 for Gmail, IMAP credentials, etc.)
2. **Email Extraction** → Process emails and attachments via provider interface
3. **Security Validation** → MIME type checking, size limits, optional ClamAV
4. **Dual Storage**:
   - PostgreSQL with pgvector: Vector embeddings (1536d) for semantic search
   - Markdown files: Human-readable archive with base64 attachments
5. **LLM Integration** → Search, categorization, Q&A using OpenAI

### Key Modules
- `src/providers/` - Plugin-based email provider system
  - `base.py` - Abstract base class for all providers
  - `gmail/` - Gmail provider implementation
- `src/auth.py` - Backward compatibility layer
- `src/etl_pipeline.py` - Orchestrates the ETL process, supports multiple providers
- `src/database.py` - PostgreSQL operations with pgvector, provider tracking
- `src/email_processor.py` - Provider-agnostic email processing interface
- `src/markdown_storage.py` - File storage in year/month structure
- `src/security.py` - Multi-layer attachment validation
- `src/embeddings.py` - OpenAI text-embedding-3-small generation
- `src/llm_integration.py` - RAG implementation for search and analysis

### Database Schema
- `emails` table with vector(1536) column for embeddings + provider fields
- `provider_config` table for provider-specific settings
- `provider_tokens` table for OAuth tokens and credentials
- HNSW index for similarity search
- `hybrid_email_search()` function combines vector + full-text search with provider filtering
- Audit logging for all operations with provider tracking

### Configuration Requirements
Required in `.env`:
- `ENABLED_PROVIDERS` - Comma-separated list of providers (default: gmail)
- `DEFAULT_PROVIDER` - Default provider to use (default: gmail)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` - Gmail API (if using Gmail)
- `POSTGRES_USER`, `POSTGRES_PASSWORD` - Database
- `OPENAI_API_KEY` - For embeddings and LLM

### Processing Patterns
- Batch size: 50 emails (configurable)
- Incremental sync tracks last processed date
- Context managers for database connections
- Progress bars for long operations
- Comprehensive error tracking and statistics

### Observability
- **Grafana Alloy** as unified telemetry collector
- Optional deployment with `--profile observability`
- Supports external backends (Prometheus, Loki, Tempo, Grafana Cloud)
- Can run with `ENABLE_OBSERVABILITY=false` for zero overhead
- Collects metrics (app + system + PostgreSQL), logs, and traces
- Configuration in `alloy/config.alloy`