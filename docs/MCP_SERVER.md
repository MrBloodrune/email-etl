# Gmail ETL MCP Server Documentation

## Overview

The Gmail ETL system implements a Model Context Protocol (MCP) server that exposes email operations as tools for LLM integration. This enables AI assistants to search, analyze, and manage emails through a standardized protocol.

## MCP Server Information

- **Name**: `gmail-etl-mcp`
- **Version**: `1.0.0`
- **Protocol**: MCP v1.0
- **Base URL**: `http://localhost:8000/mcp`

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   LLM Client    │────▶│   MCP Server     │────▶│  Gmail ETL API  │
│  (Claude, etc)  │◀────│  (FastMCP)       │◀────│  (FastAPI)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │                           │
                              │                           ▼
                              │                    ┌─────────────┐
                              │                    │ PostgreSQL  │
                              └───────────────────▶│ + pgvector  │
                                                   └─────────────┘
```

## MCP Tool Definitions

### 1. search_emails

Search emails using semantic similarity with vector embeddings.

**Parameters:**
- `query` (string, required): Natural language search query
- `limit` (integer, optional): Max results (1-100), default: 10
- `date_from` (string, optional): ISO 8601 datetime filter start
- `date_to` (string, optional): ISO 8601 datetime filter end
- `include_content` (boolean, optional): Include full content, default: false

**Example:**
```json
{
  "tool": "search_emails",
  "parameters": {
    "query": "project deadline meetings",
    "limit": 5,
    "date_from": "2024-01-01T00:00:00Z"
  }
}
```

### 2. ask_email_question

Ask natural language questions about emails using RAG (Retrieval Augmented Generation).

**Parameters:**
- `question` (string, required): Natural language question
- `context_limit` (integer, optional): Relevant emails for context (1-20), default: 5
- `date_from` (string, optional): ISO 8601 datetime filter start
- `date_to` (string, optional): ISO 8601 datetime filter end

**Example:**
```json
{
  "tool": "ask_email_question",
  "parameters": {
    "question": "What are my action items from last week's meetings?",
    "context_limit": 10
  }
}
```

### 3. categorize_emails

Categorize emails using AI to determine type, priority, and required actions.

**Parameters:**
- `email_ids` (array, optional): Specific email IDs to categorize
- `limit` (integer, optional): Recent emails to categorize (1-50), default: 10

**Categories:**
- Primary: Work, Personal, Finance, Shopping, Travel, Marketing, Spam, Other
- Priority: High, Medium, Low
- Action Required: Yes/No

### 4. extract_action_items

Extract action items, tasks, and commitments from emails.

**Parameters:**
- `days` (integer, optional): Look back N days (1-90), default: 7
- `limit` (integer, optional): Max emails to process (1-100), default: 50

**Returns:**
- Task descriptions
- Responsible parties
- Due dates (if mentioned)
- Inferred priorities

### 5. import_emails

Import emails from Gmail with filters and processing options.

**Parameters:**
- `query` (string, optional): Gmail search query, default: ""
- `max_results` (integer, optional): Maximum emails to import
- `start_date` (string, optional): ISO 8601 datetime
- `generate_embeddings` (boolean, optional): Generate vectors, default: true

**Gmail Query Examples:**
- `from:sender@example.com`
- `subject:invoice`
- `has:attachment`
- `is:unread`

### 6. sync_emails

Perform incremental sync for new emails since last import.

**Parameters:** None

**Behavior:**
- Automatically detects last import date
- Imports only new emails
- Maintains embedding generation

### 7. get_email_by_id

Retrieve specific email with full content and metadata.

**Parameters:**
- `email_id` (integer, required): Database ID
- `include_attachments` (boolean, optional): Include attachment info, default: true

### 8. get_system_status

Get current system status and statistics.

**Parameters:** None

**Returns:**
- Database statistics
- Storage information
- Last sync time
- Version information

### 9. summarize_thread

Generate summaries of email threads.

**Parameters:**
- `thread_id` (string, required): Gmail thread ID

**Returns:**
- Main discussion topic
- Key participants
- Important decisions
- Action items
- Current status

### 10. analyze_email_patterns

Analyze communication patterns and trends.

**Parameters:**
- `days` (integer, optional): Analysis period (1-365), default: 30
- `group_by` (string, optional): Grouping method, default: "sender"
  - Options: "sender", "domain", "label", "day", "week"

## Integration Guide

### 1. Direct MCP Integration

```python
import httpx

async def call_mcp_tool(tool_name: str, parameters: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/mcp/invoke",
            json={
                "tool": tool_name,
                "parameters": parameters
            }
        )
        return response.json()
```

### 2. Using with Claude or Other LLMs

The MCP server can be registered with LLM clients that support the Model Context Protocol:

```python
# Example configuration for an MCP-compatible client
mcp_config = {
    "servers": [
        {
            "name": "gmail-etl",
            "url": "http://localhost:8000/mcp",
            "capabilities": {
                "tools": True,
                "resources": False,
                "prompts": False
            }
        }
    ]
}
```

### 3. Tool Discovery

Get all available tools:
```bash
curl http://localhost:8000/mcp/tools
```

## OpenTelemetry Integration

All MCP tool invocations are automatically instrumented with:

- **Traces**: Tool name, parameters, execution time
- **Metrics**: Invocation counts, latencies, error rates
- **Attributes**: Tool-specific metadata

### Trace Attributes

Common attributes for all tools:
- `mcp.tool.name`: Tool being invoked
- `mcp.tool.parameters`: Input parameters (sanitized)
- `mcp.tool.duration`: Execution time in milliseconds
- `mcp.tool.status`: Success/failure status

## Error Handling

MCP errors follow the protocol specification:

```json
{
  "error": {
    "code": "INVALID_PARAMS",
    "message": "Required parameter 'query' is missing",
    "data": {
      "tool": "search_emails",
      "missing_params": ["query"]
    }
  }
}
```

Error codes:
- `INVALID_PARAMS`: Missing or invalid parameters
- `TOOL_NOT_FOUND`: Unknown tool name
- `EXECUTION_ERROR`: Tool execution failed
- `AUTHENTICATION_ERROR`: Gmail auth required
- `RATE_LIMIT_ERROR`: Rate limit exceeded

## Security Considerations

1. **Authentication**: Gmail OAuth2 configured at server level
2. **Parameter Validation**: All inputs validated before execution
3. **Attachment Security**: Multi-layer validation for file attachments
4. **Rate Limiting**: Planned for future releases
5. **Audit Logging**: All operations logged with trace IDs

## Performance Guidelines

1. **Batch Operations**: Use import tools for bulk processing
2. **Context Limits**: Balance accuracy vs. performance in RAG
3. **Embedding Cache**: Embeddings are cached after generation
4. **Async Processing**: Import operations run in background
5. **Query Optimization**: Use date filters to reduce search scope

## Monitoring

### Metrics Available

- `mcp.tool.invocations`: Counter of tool calls
- `mcp.tool.latency`: Histogram of execution times
- `mcp.tool.errors`: Counter of failures by error type

### Viewing Metrics

- Prometheus: `http://localhost:8000/prometheus`
- OpenTelemetry: Configure OTLP exporter endpoint

## Examples

### Email Search Workflow
```json
// 1. Search for relevant emails
{
  "tool": "search_emails",
  "parameters": {
    "query": "budget proposal",
    "limit": 10
  }
}

// 2. Get details of specific email
{
  "tool": "get_email_by_id",
  "parameters": {
    "email_id": 123
  }
}

// 3. Extract action items
{
  "tool": "extract_action_items",
  "parameters": {
    "days": 7
  }
}
```

### Analysis Workflow
```json
// 1. Categorize recent emails
{
  "tool": "categorize_emails",
  "parameters": {
    "limit": 50
  }
}

// 2. Analyze patterns
{
  "tool": "analyze_email_patterns",
  "parameters": {
    "days": 30,
    "group_by": "domain"
  }
}
```

## Troubleshooting

### Common Issues

1. **Tool not found**: Verify tool name matches exactly
2. **Parameter errors**: Check parameter types and requirements
3. **Empty results**: Verify Gmail authentication and data exists
4. **Timeout errors**: Reduce batch sizes or context limits

### Debug Mode

Enable debug logging:
```python
import logging
logging.getLogger("gmail-etl-mcp").setLevel(logging.DEBUG)
```

## Future Enhancements

- WebSocket support for real-time updates
- Streaming responses for large datasets
- Custom tool registration
- Multi-account support
- Advanced caching strategies