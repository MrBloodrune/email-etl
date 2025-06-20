# Email ETL Pipeline

A plugin-based ETL (Extract, Transform, Load) pipeline for multiple email providers that combines PostgreSQL with pgvector for semantic search and markdown files for archival storage. This system enables LLM-based email analysis, categorization, and question-answering.

## 🐳 Docker Quick Start

```bash
# Clone and setup
git clone <repository>
cd gmail-etl
cp .env.example .env
# Edit .env with your credentials

# Start services
docker-compose up -d

# Use the CLI
docker-compose run --rm cli python main.py auth login
docker-compose run --rm cli python main.py import full --max-results 10
```

See [DOCKER_README.md](DOCKER_README.md) for complete Docker documentation.

## Features

- 🔌 **Plugin-based architecture** supporting multiple email providers
- 🔐 **Multiple authentication methods** (OAuth2, IMAP, API keys)
- 📧 **Full email extraction** including attachments
- 🛡️ **Security validation** for attachments with optional ClamAV scanning
- 🗄️ **Hybrid storage**: PostgreSQL + pgvector for search, markdown for archival
- 🤖 **LLM integration** for semantic search, categorization, and Q&A
- 🔍 **Vector embeddings** using OpenAI's text-embedding-3-small
- 📝 **Markdown export** with YAML frontmatter
- 🚀 **Incremental sync** for new emails
- 📊 **CLI interface** for all operations
- 🌐 **FastAPI REST API** with MCP tool integration
- 📈 **Optional observability** with Grafana Alloy (metrics, logs, traces)
- 🐳 **Docker support** with persistent storage

## Architecture

```
Gmail API → Email Processor → Security Validator
                ↓
        ┌───────┴───────┐
        │               │
PostgreSQL + pgvector   Markdown Files
        │               │
        └───────┬───────┘
                ↓
         LLM Integration
                ↓
         Search & Analysis
```

## Prerequisites

- Python 3.8+
- PostgreSQL 17 with pgvector extension
- Gmail API credentials
- OpenAI API key
- Docker & Docker Compose (for containerized deployment)
- (Optional) ClamAV for virus scanning
- (Optional) Grafana Alloy for observability

## Installation

1. Clone the repository:
```bash
cd gmail-etl
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up PostgreSQL with pgvector:
```bash
# Install pgvector extension
cd /tmp
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
make install

# Create database
createdb gmail_etl

# Run schema setup
psql -d gmail_etl -f scripts/init_db.sql
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

Edit `.env` file with your credentials:

```env
# Gmail API
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=gmail_etl
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password

# OpenAI
OPENAI_API_KEY=your_api_key

# Storage
MARKDOWN_STORAGE_PATH=./emails
```

## Usage

### Initial Setup

1. Authenticate with Gmail:
```bash
python main.py auth login
```

2. Initialize database:
```bash
python main.py db init
```

### Import Emails

Full import:
```bash
python main.py import full --start-date 2024-01-01
```

Import with filters:
```bash
python main.py import full --query "from:important@example.com" --max-results 1000
```

Incremental sync:
```bash
python main.py import sync
```

### Search and Analysis

Semantic search:
```bash
python main.py search semantic "project deadline"
```

Ask questions:
```bash
python main.py search ask "What are my upcoming deadlines?"
```

Categorize emails:
```bash
python main.py analyze categorize --limit 20
```

Extract action items:
```bash
python main.py analyze actions --days 7
```

### Status and Monitoring

Check status:
```bash
python main.py status
```

Estimate embedding costs:
```bash
python main.py estimate-cost --text-count 10000
```

## Storage Structure

### PostgreSQL Schema
- `emails` table with vector embeddings
- `attachments` table with security metadata
- HNSW index for fast similarity search
- Hybrid search function combining vector + full-text

### Markdown Files
```
emails/
├── 2024/
│   ├── 01/
│   │   ├── 20240115_123456_subject-slug.md
│   │   └── 20240115_123456_subject-slug/
│   │       └── attachment.pdf.base64
│   └── 02/
└── index.json
```

## Security Features

- OAuth2 authentication (no password storage)
- Attachment validation:
  - MIME type checking
  - File size limits
  - Extension allowlist
  - Optional ClamAV scanning
- Base64 encoding for safe attachment storage
- SQL injection prevention
- Audit logging

## API Reference

### ETL Pipeline
```python
from src.etl_pipeline import etl_pipeline

# Run import
results = etl_pipeline.run_import(
    query="after:2024/01/01",
    max_results=1000,
    generate_embeddings=True
)
```

### LLM Integration
```python
from src.llm_integration import llm_integration

# Semantic search
results = llm_integration.semantic_search("important project")

# Answer questions
answer = llm_integration.answer_question("What are my action items?")
```

## Troubleshooting

### Common Issues

1. **pgvector not found**: Ensure pgvector is installed and enabled:
   ```sql
   CREATE EXTENSION vector;
   ```

2. **Gmail API quota**: Implement exponential backoff for rate limits

3. **Large attachments**: Adjust `MAX_ATTACHMENT_SIZE_MB` in config

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details

## Docker Deployment

### Quick Start

```bash
# Start core services only (no observability)
docker-compose up -d

# Start with Grafana Alloy observability
docker-compose --profile observability up -d

# Check status
docker-compose ps
```

### API Access

The FastAPI server is available at http://localhost:8000
- API docs: http://localhost:8000/docs
- MCP tools: http://localhost:8000/mcp/tools
- Health check: http://localhost:8000/health

### Observability

When running with the `observability` profile:
- Alloy UI: http://localhost:12345
- OTLP receiver: localhost:4317 (gRPC), localhost:4318 (HTTP)

See [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) for detailed observability setup.