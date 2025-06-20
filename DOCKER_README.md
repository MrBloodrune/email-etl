# Docker Setup for Email ETL Pipeline

This guide explains how to run the Email ETL Pipeline using Docker, with persistent storage for PostgreSQL and email data.

## Quick Start

### 1. Prerequisites

- Docker Engine 20.10+
- Docker Compose v2.0+
- `.env` file with required credentials

### 2. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# Required: POSTGRES_USER, POSTGRES_PASSWORD, OPENAI_API_KEY
# For Gmail: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
```

### 3. Start the Services

```bash
# Start core services (PostgreSQL + API)
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

## Using the CLI

The CLI service provides an interactive shell for running ETL commands:

```bash
# Enter the CLI container
docker-compose run --rm cli

# Inside the container, run commands:
python main.py providers
python main.py auth login
python main.py import full --max-results 10
python main.py search semantic "meeting notes"
```

### Common CLI Operations

```bash
# One-liner commands from host
docker-compose run --rm cli python main.py status
docker-compose run --rm cli python main.py providers
docker-compose run --rm cli python main.py auth test

# Import emails
docker-compose run --rm cli python main.py import full --start-date 2024-01-01

# Search emails
docker-compose run --rm cli python main.py search ask "What are my deadlines?"
```

## Service Architecture

### Core Services

1. **postgres** - PostgreSQL with pgvector extension
   - Persistent volume: `postgres_data`
   - Port: 5432 (configurable)
   - Auto-runs initialization scripts

2. **cli** - Interactive command-line interface
   - Access to all ETL commands
   - Mounts credentials and tokens
   - Persistent email storage

3. **api** - REST API server
   - Port: 8000 (configurable)
   - Read-only access to emails
   - Health endpoint: `/health`

4. **migration** - Database migration runner
   - Runs once on startup
   - Ensures schema is up-to-date

### Optional Services

5. **etl** - Scheduled ETL worker (use `--profile scheduled`)
6. **alloy** - Observability stack (use `--profile observability`)
7. **clamav** - Virus scanning (use `--profile with-clamav`)

## Persistent Storage

All data is stored in Docker volumes for persistence:

- `postgres_data` - PostgreSQL database
- `emails_data` - Markdown email files
- `tokens_data` - OAuth tokens and credentials

### Backup and Restore

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U $POSTGRES_USER gmail_etl > backup.sql

# Backup email files
docker run --rm -v email-etl_emails_data:/data -v $(pwd):/backup alpine tar czf /backup/emails_backup.tar.gz -C /data .

# Restore PostgreSQL
docker-compose exec -T postgres psql -U $POSTGRES_USER gmail_etl < backup.sql

# Restore email files
docker run --rm -v email-etl_emails_data:/data -v $(pwd):/backup alpine tar xzf /backup/emails_backup.tar.gz -C /data
```

## Development Setup

For development with hot-reloading:

```bash
# Copy development override
cp docker-compose.override.yml.example docker-compose.override.yml

# Start with development settings
docker-compose up -d

# Code changes will be reflected immediately
```

Development features:
- Source code mounted for hot-reloading
- Additional development tools (ipython, pytest, etc.)
- pgAdmin available at http://localhost:5050

## Authentication with Gmail

Gmail authentication requires OAuth2 setup:

```bash
# First-time authentication
docker-compose run --rm cli python main.py auth login

# This will:
# 1. Open a browser for Google OAuth
# 2. Save tokens to token.json
# 3. Tokens persist across container restarts
```

## Environment Variables

Key environment variables (set in `.env`):

```env
# PostgreSQL
POSTGRES_USER=email_etl
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=gmail_etl
POSTGRES_PORT=5432

# API
API_PORT=8000

# Providers
ENABLED_PROVIDERS=gmail
DEFAULT_PROVIDER=gmail

# Gmail (if using)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# OpenAI
OPENAI_API_KEY=your_api_key
```

## Profiles

Use Docker Compose profiles for optional features:

```bash
# With observability (Grafana Alloy)
docker-compose --profile observability up -d

# With scheduled ETL worker
docker-compose --profile scheduled up -d

# With ClamAV virus scanning
docker-compose --profile with-clamav up -d

# Multiple profiles
docker-compose --profile observability --profile with-clamav up -d
```

## Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Test database connection
docker-compose exec postgres psql -U $POSTGRES_USER -d gmail_etl -c "SELECT 1;"

# Reinitialize database (WARNING: destroys data)
docker-compose down -v
docker-compose up -d
```

### Permission Issues

```bash
# Fix email directory permissions
docker-compose exec -u root cli chown -R etluser:etluser /app/emails

# Fix token permissions
docker-compose exec -u root cli chown etluser:etluser /app/token.json
```

### Container Won't Start

```bash
# Check detailed logs
docker-compose logs -f [service_name]

# Rebuild containers
docker-compose build --no-cache
docker-compose up -d
```

## Production Deployment

For production use:

1. Use strong passwords in `.env`
2. Enable HTTPS for API (use reverse proxy)
3. Set up regular backups
4. Monitor with observability stack
5. Use Docker secrets for sensitive data

```bash
# Production start
docker-compose -f docker-compose.yml up -d

# With observability
docker-compose -f docker-compose.yml --profile observability up -d
```

## Sharing the Container

To share this setup:

1. **Share the code repository** (without `.env` or credentials)
2. **Provide `.env.example`** as template
3. **User creates their own**:
   - `.env` file with credentials
   - `credentials.json` (if using Gmail)

The recipient runs:
```bash
docker-compose pull
docker-compose up -d
docker-compose run --rm cli python main.py auth login
```

## Advanced Usage

### Custom Email Provider

Add a new provider without rebuilding:

```bash
# Mount custom provider
docker-compose run -v ./my_provider:/app/src/providers/my_provider cli python main.py providers
```

### Direct Database Access

```bash
# PostgreSQL CLI
docker-compose exec postgres psql -U $POSTGRES_USER -d gmail_etl

# pgAdmin web interface
# Visit http://localhost:5050 (if using development override)
```

### Export Data

```bash
# Export emails as JSON
docker-compose run --rm cli python -c "
from src.database import db_manager
import json
emails = db_manager.get_recent_emails(100)
print(json.dumps(emails, default=str))
" > emails_export.json
```

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Clean up everything
docker-compose down -v --rmi all
```