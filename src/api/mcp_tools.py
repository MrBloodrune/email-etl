"""
MCP (Model Context Protocol) tool definitions for Gmail ETL

This module defines all tools exposed via MCP following the standard format.
Each tool includes proper parameter definitions and descriptions.
"""

from typing import List, Dict, Any
from .models import MCPToolDefinition, MCPToolParameter


# Define all MCP tools
MCP_TOOLS: List[MCPToolDefinition] = [
    MCPToolDefinition(
        name="search_emails",
        description="Search emails using semantic similarity. Uses vector embeddings to find emails with similar meaning to your query.",
        parameters=[
            MCPToolParameter(
                name="query",
                type="string",
                description="Natural language search query for semantic matching",
                required=True
            ),
            MCPToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of results to return (1-100)",
                required=False,
                default=10
            ),
            MCPToolParameter(
                name="date_from",
                type="string",
                description="ISO 8601 datetime to filter emails after this date",
                required=False
            ),
            MCPToolParameter(
                name="date_to",
                type="string",
                description="ISO 8601 datetime to filter emails before this date",
                required=False
            ),
            MCPToolParameter(
                name="include_content",
                type="boolean",
                description="Whether to include full email content in results",
                required=False,
                default=False
            )
        ]
    ),
    
    MCPToolDefinition(
        name="ask_email_question",
        description="Ask a natural language question about your emails. Uses RAG to find relevant emails and generate an answer.",
        parameters=[
            MCPToolParameter(
                name="question",
                type="string",
                description="Natural language question about your emails",
                required=True
            ),
            MCPToolParameter(
                name="context_limit",
                type="integer",
                description="Number of relevant emails to use as context (1-20)",
                required=False,
                default=5
            ),
            MCPToolParameter(
                name="date_from",
                type="string",
                description="ISO 8601 datetime to only consider emails after this date",
                required=False
            ),
            MCPToolParameter(
                name="date_to",
                type="string",
                description="ISO 8601 datetime to only consider emails before this date",
                required=False
            )
        ]
    ),
    
    MCPToolDefinition(
        name="categorize_emails",
        description="Categorize emails using AI to determine type, priority, and required actions.",
        parameters=[
            MCPToolParameter(
                name="email_ids",
                type="array",
                description="List of specific email database IDs to categorize",
                required=False
            ),
            MCPToolParameter(
                name="limit",
                type="integer",
                description="Number of recent emails to categorize if no IDs provided (1-50)",
                required=False,
                default=10
            )
        ]
    ),
    
    MCPToolDefinition(
        name="extract_action_items",
        description="Extract action items, tasks, and commitments from recent emails.",
        parameters=[
            MCPToolParameter(
                name="days",
                type="integer",
                description="Extract actions from emails in the last N days (1-90)",
                required=False,
                default=7
            ),
            MCPToolParameter(
                name="limit",
                type="integer",
                description="Maximum number of emails to process (1-100)",
                required=False,
                default=50
            )
        ]
    ),
    
    MCPToolDefinition(
        name="import_emails",
        description="Import emails from Gmail with optional filters. Includes attachment processing and embedding generation.",
        parameters=[
            MCPToolParameter(
                name="query",
                type="string",
                description="Gmail search query (e.g., 'from:example@email.com', 'subject:invoice')",
                required=False,
                default=""
            ),
            MCPToolParameter(
                name="max_results",
                type="integer",
                description="Maximum number of emails to import",
                required=False
            ),
            MCPToolParameter(
                name="start_date",
                type="string",
                description="ISO 8601 datetime to import emails after this date",
                required=False
            ),
            MCPToolParameter(
                name="generate_embeddings",
                type="boolean",
                description="Whether to generate vector embeddings for imported emails",
                required=False,
                default=True
            )
        ]
    ),
    
    MCPToolDefinition(
        name="sync_emails",
        description="Perform incremental sync to import only new emails since last import.",
        parameters=[]
    ),
    
    MCPToolDefinition(
        name="get_email_by_id",
        description="Retrieve a specific email by its database ID, including full content and metadata.",
        parameters=[
            MCPToolParameter(
                name="email_id",
                type="integer",
                description="Database ID of the email to retrieve",
                required=True
            ),
            MCPToolParameter(
                name="include_attachments",
                type="boolean",
                description="Whether to include attachment metadata",
                required=False,
                default=True
            )
        ]
    ),
    
    MCPToolDefinition(
        name="get_system_status",
        description="Get current system status including database statistics and storage information.",
        parameters=[]
    ),
    
    MCPToolDefinition(
        name="summarize_thread",
        description="Generate a summary of an email thread including participants, decisions, and action items.",
        parameters=[
            MCPToolParameter(
                name="thread_id",
                type="string",
                description="Gmail thread ID to summarize",
                required=True
            )
        ]
    ),
    
    MCPToolDefinition(
        name="analyze_email_patterns",
        description="Analyze email patterns to generate insights about communication habits and trends.",
        parameters=[
            MCPToolParameter(
                name="days",
                type="integer",
                description="Analyze emails from the last N days (1-365)",
                required=False,
                default=30
            ),
            MCPToolParameter(
                name="group_by",
                type="string",
                description="How to group analysis: 'sender', 'domain', 'label', 'day', 'week'",
                required=False,
                default="sender",
                enum=["sender", "domain", "label", "day", "week"]
            )
        ]
    )
]


def get_mcp_tool_definitions() -> List[Dict[str, Any]]:
    """Get all MCP tool definitions as dictionaries"""
    return [tool.model_dump() for tool in MCP_TOOLS]


def get_mcp_tool_by_name(name: str) -> MCPToolDefinition:
    """Get a specific MCP tool definition by name"""
    for tool in MCP_TOOLS:
        if tool.name == name:
            return tool
    raise ValueError(f"MCP tool '{name}' not found")


def validate_mcp_parameters(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate parameters for an MCP tool
    
    Returns cleaned parameters with defaults applied
    """
    tool = get_mcp_tool_by_name(tool_name)
    cleaned_params = {}
    
    for param_def in tool.parameters:
        param_name = param_def.name
        param_value = parameters.get(param_name)
        
        # Check required parameters
        if param_def.required and param_value is None:
            raise ValueError(f"Required parameter '{param_name}' missing for tool '{tool_name}'")
        
        # Apply defaults
        if param_value is None and param_def.default is not None:
            param_value = param_def.default
        
        # Type validation would go here
        # For now, we'll just pass through
        
        if param_value is not None:
            cleaned_params[param_name] = param_value
    
    return cleaned_params


# MCP Server metadata
MCP_SERVER_INFO = {
    "name": "gmail-etl-mcp",
    "version": "1.0.0",
    "description": "Gmail ETL system with semantic search and LLM capabilities via MCP",
    "author": "Gmail ETL Team",
    "capabilities": {
        "email_import": True,
        "semantic_search": True,
        "question_answering": True,
        "categorization": True,
        "action_extraction": True,
        "thread_summarization": True,
        "pattern_analysis": True
    },
    "supported_email_sources": ["gmail"],
    "embedding_model": "text-embedding-3-small",
    "vector_dimensions": 1536
}