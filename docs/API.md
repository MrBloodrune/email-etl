# Gmail ETL API Documentation

## Overview

The Gmail ETL API provides RESTful endpoints and MCP (Model Context Protocol) tools for email import, search, and analysis with LLM capabilities. All operations are instrumented with OpenTelemetry for comprehensive observability.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, the API uses Gmail OAuth2 authentication configured at the server level. Future versions will support API key authentication.

## OpenTelemetry Integration

All API operations include:
- **Distributed Tracing**: Every request generates trace spans
- **Metrics**: Performance metrics exported to Prometheus
- **Context Propagation**: Trace IDs included in error responses

### Viewing Metrics

- Prometheus metrics: `http://localhost:8000/prometheus`
- Health check: `http://localhost:8000/health`

## Endpoints

### Email Import Operations

#### Import Emails
```http
POST /api/emails/import
```

Start a background email import task.

**Request Body:**
```json
{
  "query": "from:important@example.com",
  "max_results": 1000,
  "start_date": "2024-01-01T00:00:00Z",
  "generate_embeddings": true
}
```

**Response:**
```json
{
  "status": "running",
  "total_found": 0,
  "processed": 0,
  "failed": 0,
  "skipped": 0,
  "attachments_processed": 0,
  "attachments_rejected": 0
}
```

**OpenTelemetry Span Attributes:**
- `import_id`: Unique import task ID
- `query`: Gmail search query
- `generate_embeddings`: Whether embeddings are generated

#### Sync Emails
```http
POST /api/emails/sync
```

Perform incremental sync for new emails.

**Response:** Same as import endpoint

#### Check Import Status
```http
GET /api/emails/import/{import_id}
```

Get status of a running or completed import task.

### Search Operations

#### Semantic Search
```http
POST /api/search/emails
```

Search emails using vector similarity.

**Request Body:**
```json
{
  "query": "project deadline",
  "limit": 10,
  "date_from": "2024-01-01T00:00:00Z",
  "date_to": "2024-12-31T23:59:59Z",
  "include_content": false
}
```

**Response:**
```json
{
  "query": "project deadline",
  "total_found": 3,
  "results": [
    {
      "id": 123,
      "message_id": "abc123",
      "subject": "Project Alpha Deadline",
      "sender": "manager@company.com",
      "sender_name": "John Manager",
      "date": "2024-01-15T10:30:00Z",
      "has_attachments": false,
      "labels": ["INBOX", "IMPORTANT"],
      "similarity": 0.92
    }
  ]
}
```

**OpenTelemetry Metrics:**
- `gmail_etl_search_latency`: Search request duration histogram

#### Ask Questions
```http
POST /api/search/ask
```

Ask natural language questions about emails using RAG.

**Request Body:**
```json
{
  "question": "What are my upcoming deadlines?",
  "context_limit": 5,
  "date_from": "2024-01-01T00:00:00Z",
  "date_to": "2024-12-31T23:59:59Z"
}
```

**Response:**
```json
{
  "question": "What are my upcoming deadlines?",
  "answer": "Based on your recent emails, you have two upcoming deadlines:\n1. Project Alpha - Due January 30th\n2. Quarterly Report - Due February 5th",
  "context_email_count": 3,
  "sources": [
    {
      "id": 123,
      "message_id": "abc123",
      "subject": "Project Alpha Update",
      "sender": "manager@company.com",
      "date": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Analysis Operations

#### Categorize Emails
```http
POST /api/analyze/categorize
```

Categorize emails using AI.

**Request Body:**
```json
{
  "email_ids": [123, 124, 125],
  "limit": 20
}
```

**Response:**
```json
[
  {
    "email_id": 123,
    "subject": "Invoice #12345",
    "primary_category": "Finance",
    "subcategory": "Invoices",
    "priority": "High",
    "action_required": true,
    "summary": "Invoice for consulting services due within 30 days"
  }
]
```

#### Extract Action Items
```http
POST /api/analyze/actions
```

Extract action items from recent emails.

**Request Body:**
```json
{
  "days": 7,
  "limit": 50
}
```

**Response:**
```json
[
  {
    "email_id": 123,
    "email_subject": "Project Planning Meeting",
    "email_date": "2024-01-15T10:30:00Z",
    "description": "Prepare project timeline document",
    "responsible": "You",
    "due_date": "2024-01-20",
    "priority": "High"
  }
]
```

### System Operations

#### Get Status
```http
GET /api/status
```

Get system statistics.

**Response:**
```json
{
  "database": {
    "total_emails": 1500,
    "emails_with_embeddings": 1480
  },
  "storage": {
    "total_emails": 1500,
    "emails_with_attachments": 423,
    "total_size_mb": 2048.5
  },
  "last_sync": "2024-01-20T15:30:00Z",
  "version": "1.0.0"
}
```

## MCP (Model Context Protocol) Integration

The API exposes all functionality as MCP tools for LLM integration.

### MCP Endpoint
```http
GET /mcp/tools
```

Returns all available MCP tool definitions.

### Available MCP Tools

1. **search_emails** - Semantic email search
2. **ask_email_question** - Natural language Q&A
3. **categorize_emails** - AI categorization
4. **extract_action_items** - Action extraction
5. **import_emails** - Email import
6. **sync_emails** - Incremental sync
7. **get_email_by_id** - Retrieve specific email
8. **get_system_status** - System information
9. **summarize_thread** - Thread summarization
10. **analyze_email_patterns** - Pattern analysis

### Using MCP Tools

MCP tools can be invoked through the `/mcp` endpoint following the Model Context Protocol specification.

Example tool invocation:
```json
{
  "tool": "search_emails",
  "parameters": {
    "query": "meeting notes",
    "limit": 5
  }
}
```

## Error Handling

All errors follow a consistent format:

```json
{
  "error": "error_type",
  "message": "Human-readable error message",
  "details": {},
  "trace_id": "0123456789abcdef0123456789abcdef"
}
```

The `trace_id` can be used to correlate errors with OpenTelemetry traces.

## Rate Limiting

Currently no rate limiting is implemented. Future versions will include:
- Per-IP rate limiting
- API key based quotas
- Gmail API quota management

## Best Practices

1. **Batch Operations**: Use import endpoints for bulk operations
2. **Async Processing**: Import operations are asynchronous - poll for status
3. **Date Filtering**: Use date ranges to limit search scope
4. **Embedding Costs**: Monitor embedding generation costs using metrics
5. **Trace Context**: Include trace IDs when reporting issues

## Examples

### Python Client Example

```python
import httpx
import asyncio

async def search_emails():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/search/emails",
            json={
                "query": "important project",
                "limit": 10
            }
        )
        return response.json()

results = asyncio.run(search_emails())
```

### cURL Examples

Search emails:
```bash
curl -X POST http://localhost:8000/api/search/emails \
  -H "Content-Type: application/json" \
  -d '{"query": "meeting", "limit": 5}'
```

Ask a question:
```bash
curl -X POST http://localhost:8000/api/search/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What meetings do I have this week?"}'
```