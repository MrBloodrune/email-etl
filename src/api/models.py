"""
Pydantic models for API requests and responses

Following MCP standards for tool parameter definitions
"""

from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# Base Models
class MCPToolParameter(BaseModel):
    """MCP-compliant tool parameter definition"""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, integer, boolean, array, object)")
    description: str = Field(..., description="Human-readable description of the parameter")
    required: bool = Field(True, description="Whether this parameter is required")
    default: Optional[Any] = Field(None, description="Default value if not required")
    enum: Optional[List[str]] = Field(None, description="Allowed values for enum types")


class MCPToolDefinition(BaseModel):
    """MCP-compliant tool definition"""
    name: str = Field(..., description="Tool name (function name)")
    description: str = Field(..., description="Human-readable description of what the tool does")
    parameters: List[MCPToolParameter] = Field(..., description="Tool parameters")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "search_emails",
                "description": "Search emails using semantic similarity",
                "parameters": [
                    {
                        "name": "query",
                        "type": "string",
                        "description": "Search query for semantic matching",
                        "required": True
                    },
                    {
                        "name": "limit",
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "required": False,
                        "default": 10
                    }
                ]
            }
        }
    )


# Request Models
class EmailImportRequest(BaseModel):
    """Request model for email import"""
    query: str = Field("", description="Gmail search query (e.g., 'from:example@email.com')")
    max_results: Optional[int] = Field(None, description="Maximum number of emails to import")
    start_date: Optional[datetime] = Field(None, description="Import emails after this date")
    generate_embeddings: bool = Field(True, description="Whether to generate embeddings for imported emails")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "from:important@example.com",
                "max_results": 1000,
                "start_date": "2024-01-01T00:00:00Z",
                "generate_embeddings": True
            }
        }
    )


class EmailSearchRequest(BaseModel):
    """Request model for semantic email search"""
    query: str = Field(..., description="Search query for semantic matching")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    date_from: Optional[datetime] = Field(None, description="Filter emails after this date")
    date_to: Optional[datetime] = Field(None, description="Filter emails before this date")
    include_content: bool = Field(False, description="Include full email content in response")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "project deadline",
                "limit": 10,
                "include_content": True
            }
        }
    )


class EmailQuestionRequest(BaseModel):
    """Request model for asking questions about emails"""
    question: str = Field(..., description="Natural language question about your emails")
    context_limit: int = Field(5, ge=1, le=20, description="Number of relevant emails to use as context")
    date_from: Optional[datetime] = Field(None, description="Only consider emails after this date")
    date_to: Optional[datetime] = Field(None, description="Only consider emails before this date")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What are my upcoming deadlines?",
                "context_limit": 10
            }
        }
    )


class EmailCategorizeRequest(BaseModel):
    """Request model for email categorization"""
    email_ids: Optional[List[int]] = Field(None, description="Specific email IDs to categorize")
    limit: int = Field(10, ge=1, le=50, description="Number of recent emails to categorize if no IDs provided")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "limit": 20
            }
        }
    )


class ActionItemExtractionRequest(BaseModel):
    """Request model for action item extraction"""
    days: int = Field(7, ge=1, le=90, description="Extract actions from emails in the last N days")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of emails to process")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "days": 7,
                "limit": 50
            }
        }
    )


# Response Models
class EmailSummary(BaseModel):
    """Summary information about an email"""
    id: int = Field(..., description="Database ID of the email")
    message_id: str = Field(..., description="Gmail message ID")
    subject: str = Field(..., description="Email subject")
    sender: str = Field(..., description="Sender email address")
    sender_name: Optional[str] = Field(None, description="Sender display name")
    date: datetime = Field(..., description="Email date")
    has_attachments: bool = Field(..., description="Whether email has attachments")
    labels: List[str] = Field(..., description="Gmail labels")
    similarity: Optional[float] = Field(None, description="Similarity score for search results")
    markdown_path: Optional[str] = Field(None, description="Path to markdown file")


class EmailSearchResponse(BaseModel):
    """Response model for email search"""
    query: str = Field(..., description="Original search query")
    results: List[EmailSummary] = Field(..., description="Search results")
    total_found: int = Field(..., description="Total number of matching emails")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
                        "has_attachments": False,
                        "labels": ["INBOX", "IMPORTANT"],
                        "similarity": 0.92
                    }
                ]
            }
        }
    )


class EmailAnswerResponse(BaseModel):
    """Response model for email questions"""
    question: str = Field(..., description="Original question")
    answer: str = Field(..., description="AI-generated answer based on email context")
    sources: List[EmailSummary] = Field(..., description="Emails used as context")
    context_email_count: int = Field(..., description="Number of emails used for context")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "What are my upcoming deadlines?",
                "answer": "Based on your recent emails, you have two upcoming deadlines:\n1. Project Alpha - Due January 30th\n2. Quarterly Report - Due February 5th",
                "context_email_count": 3,
                "sources": []
            }
        }
    )


class EmailCategory(BaseModel):
    """Email categorization result"""
    email_id: int = Field(..., description="Database ID of the email")
    subject: str = Field(..., description="Email subject")
    primary_category: str = Field(..., description="Primary category (Work, Personal, Finance, etc.)")
    subcategory: Optional[str] = Field(None, description="More specific subcategory")
    priority: Literal["High", "Medium", "Low"] = Field(..., description="Priority level")
    action_required: bool = Field(..., description="Whether action is required")
    summary: str = Field(..., description="Brief summary of the email")


class ActionItem(BaseModel):
    """Extracted action item"""
    email_id: int = Field(..., description="Source email ID")
    email_subject: str = Field(..., description="Source email subject")
    email_date: datetime = Field(..., description="Source email date")
    description: str = Field(..., description="Description of the action item")
    responsible: Optional[str] = Field(None, description="Person responsible for the action")
    due_date: Optional[str] = Field(None, description="Due date if mentioned")
    priority: Literal["High", "Medium", "Low"] = Field("Medium", description="Inferred priority")


class ImportStatus(BaseModel):
    """Email import status"""
    status: Literal["running", "completed", "failed"] = Field(..., description="Import status")
    total_found: int = Field(..., description="Total emails found matching criteria")
    processed: int = Field(..., description="Successfully processed emails")
    failed: int = Field(..., description="Failed email imports")
    skipped: int = Field(..., description="Skipped emails (already imported)")
    attachments_processed: int = Field(..., description="Successfully processed attachments")
    attachments_rejected: int = Field(..., description="Rejected attachments (security/size)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "completed",
                "total_found": 150,
                "processed": 145,
                "failed": 2,
                "skipped": 3,
                "attachments_processed": 48,
                "attachments_rejected": 2
            }
        }
    )


class SystemStatus(BaseModel):
    """System status information"""
    database: Dict[str, int] = Field(..., description="Database statistics")
    storage: Dict[str, Any] = Field(..., description="Storage statistics")
    last_sync: Optional[datetime] = Field(None, description="Last successful sync time")
    version: str = Field(..., description="API version")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
        }
    )


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    trace_id: Optional[str] = Field(None, description="OpenTelemetry trace ID for debugging")