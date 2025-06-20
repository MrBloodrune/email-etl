"""
FastAPI server with MCP integration and OpenTelemetry instrumentation

This server exposes Gmail ETL functionality as both REST API and MCP tools.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
import uvicorn

from ..config import config
from ..auth import auth_manager
from ..database import db_manager
from ..etl_pipeline import etl_pipeline
from ..llm_integration import llm_integration
from ..email_processor import EmailProcessor
from ..embeddings import embedding_generator

from .models import (
    EmailImportRequest, EmailSearchRequest, EmailQuestionRequest,
    EmailCategorizeRequest, ActionItemExtractionRequest,
    EmailSearchResponse, EmailAnswerResponse, EmailCategory,
    ActionItem, ImportStatus, SystemStatus, ErrorResponse,
    EmailSummary
)
from .mcp_tools import (
    get_mcp_tool_definitions, MCP_SERVER_INFO,
    validate_mcp_parameters
)
from .telemetry import (
    setup_telemetry, get_tracer, get_metrics,
    trace_operation, record_metric, create_span_context
)

logger = logging.getLogger(__name__)


# Global state for background tasks
import_tasks: Dict[str, ImportStatus] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting Gmail ETL API server...")
    
    # Test database connection
    if not db_manager.test_connection():
        logger.error("Failed to connect to database")
        raise RuntimeError("Database connection failed")
    
    # Test Gmail authentication
    try:
        if not auth_manager.get_authenticator().test_connection():
            logger.warning("Gmail authentication not set up")
    except Exception as e:
        logger.warning(f"Gmail auth check failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Gmail ETL API server...")


# Create FastAPI app
app = FastAPI(
    title="Gmail ETL API",
    description="API for Gmail ETL with semantic search and LLM capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler with OpenTelemetry integration
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with tracing"""
    tracer = get_tracer()
    span = trace.get_current_span()
    
    if span:
        span.set_status(Status(StatusCode.ERROR, str(exc)))
        span.record_exception(exc)
    
    logger.exception("Unhandled exception")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "trace_id": format(span.get_span_context().trace_id, '032x') if span else None
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "gmail-etl-api",
        "version": "1.0.0"
    }


# Metrics endpoint (Prometheus format)
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    # This would be handled by the Prometheus ASGI app
    return {"message": "Use /prometheus for metrics"}


# Email operations
@app.post("/api/emails/import", response_model=ImportStatus)
@trace_operation("import_emails")
async def import_emails(
    request: EmailImportRequest,
    background_tasks: BackgroundTasks
) -> ImportStatus:
    """
    Import emails from Gmail
    
    This endpoint starts a background import task and returns immediately.
    """
    import_id = f"import_{datetime.now().timestamp()}"
    
    # Create initial status
    status = ImportStatus(
        status="running",
        total_found=0,
        processed=0,
        failed=0,
        skipped=0,
        attachments_processed=0,
        attachments_rejected=0
    )
    import_tasks[import_id] = status
    
    # Start background import
    background_tasks.add_task(
        run_import_task,
        import_id,
        request.query,
        request.max_results,
        request.start_date,
        request.generate_embeddings
    )
    
    return status


async def run_import_task(
    import_id: str,
    query: str,
    max_results: Optional[int],
    start_date: Optional[datetime],
    generate_embeddings: bool
):
    """Background task for email import"""
    tracer = get_tracer()
    
    with tracer.start_as_current_span(
        "background_import",
        attributes={
            "import_id": import_id,
            "query": query,
            "generate_embeddings": generate_embeddings
        }
    ) as span:
        try:
            # Run import in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                etl_pipeline.run_import,
                query,
                max_results,
                start_date,
                generate_embeddings
            )
            
            # Update status
            import_tasks[import_id] = ImportStatus(
                status="completed",
                total_found=result['total_found'],
                **result['stats']
            )
            
            # Record metrics
            record_metric("email_import_counter", result['stats']['processed'], {
                "status": "success"
            })
            
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            import_tasks[import_id].status = "failed"
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


@app.post("/api/emails/sync", response_model=ImportStatus)
@trace_operation("sync_emails")
async def sync_emails(background_tasks: BackgroundTasks) -> ImportStatus:
    """Perform incremental sync for new emails"""
    import_id = f"sync_{datetime.now().timestamp()}"
    
    status = ImportStatus(
        status="running",
        total_found=0,
        processed=0,
        failed=0,
        skipped=0,
        attachments_processed=0,
        attachments_rejected=0
    )
    import_tasks[import_id] = status
    
    background_tasks.add_task(run_sync_task, import_id)
    
    return status


async def run_sync_task(import_id: str):
    """Background task for email sync"""
    tracer = get_tracer()
    
    with tracer.start_as_current_span("background_sync") as span:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                etl_pipeline.run_incremental_sync
            )
            
            import_tasks[import_id] = ImportStatus(
                status="completed",
                total_found=result['total_found'],
                **result['stats']
            )
            
            span.set_status(Status(StatusCode.OK))
            
        except Exception as e:
            import_tasks[import_id].status = "failed"
            span.set_status(Status(StatusCode.ERROR, str(e)))
            raise


@app.get("/api/emails/import/{import_id}", response_model=ImportStatus)
async def get_import_status(import_id: str) -> ImportStatus:
    """Get status of an import task"""
    if import_id not in import_tasks:
        raise HTTPException(404, "Import task not found")
    
    return import_tasks[import_id]


# Search endpoints
@app.post("/api/search/emails", response_model=EmailSearchResponse)
@trace_operation("search_emails")
async def search_emails(request: EmailSearchRequest) -> EmailSearchResponse:
    """Search emails using semantic similarity"""
    tracer = get_tracer()
    
    with create_span_context("search_processing") as span:
        span.set_attribute("query_length", len(request.query))
        
        # Run search
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            llm_integration.semantic_search,
            request.query,
            request.limit,
            request.date_from,
            request.date_to
        )
        
        # Record metrics
        record_metric("search_latency_histogram", span.end_time - span.start_time, {
            "result_count": str(len(results))
        })
        
        # Convert to response model
        email_summaries = []
        for result in results:
            email_summaries.append(EmailSummary(
                id=result['id'],
                message_id=result['message_id'],
                subject=result.get('subject', ''),
                sender=result.get('sender', ''),
                sender_name=result.get('sender_name'),
                date=result.get('date'),
                has_attachments=result.get('has_attachments', False),
                labels=result.get('labels', []),
                similarity=result.get('similarity'),
                markdown_path=result.get('markdown_path')
            ))
        
        return EmailSearchResponse(
            query=request.query,
            results=email_summaries,
            total_found=len(results)
        )


@app.post("/api/search/ask", response_model=EmailAnswerResponse)
@trace_operation("ask_question")
async def ask_email_question(request: EmailQuestionRequest) -> EmailAnswerResponse:
    """Ask a question about emails using RAG"""
    tracer = get_tracer()
    
    with create_span_context("question_answering") as span:
        span.set_attribute("question", request.question)
        span.set_attribute("context_limit", request.context_limit)
        
        # Get answer
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            llm_integration.answer_question,
            request.question,
            request.context_limit
        )
        
        # Convert sources
        sources = []
        for source in result.get('sources', []):
            sources.append(EmailSummary(
                id=source.get('id', 0),
                message_id=source['message_id'],
                subject=source.get('subject', ''),
                sender=source.get('sender', ''),
                sender_name=source.get('sender_name'),
                date=source.get('date'),
                has_attachments=False,
                labels=[],
                similarity=source.get('similarity')
            ))
        
        return EmailAnswerResponse(
            question=request.question,
            answer=result['answer'],
            sources=sources,
            context_email_count=result['context_email_count']
        )


# Analysis endpoints
@app.post("/api/analyze/categorize", response_model=List[EmailCategory])
@trace_operation("categorize_emails")
async def categorize_emails(request: EmailCategorizeRequest) -> List[EmailCategory]:
    """Categorize emails using AI"""
    # Implementation
    loop = asyncio.get_event_loop()
    
    # Get email IDs
    if request.email_ids:
        email_ids = request.email_ids
    else:
        recent_emails = await loop.run_in_executor(
            None,
            db_manager.get_recent_emails,
            request.limit
        )
        email_ids = [e['id'] for e in recent_emails]
    
    # Categorize
    categorizations = await loop.run_in_executor(
        None,
        llm_integration.categorize_emails,
        email_ids
    )
    
    # Convert to response
    results = []
    for email_id, cat in categorizations.items():
        if 'error' not in cat:
            results.append(EmailCategory(
                email_id=email_id,
                subject=cat.get('subject', ''),
                primary_category=cat.get('primary_category', 'Other'),
                subcategory=cat.get('subcategory'),
                priority=cat.get('priority', 'Medium'),
                action_required=cat.get('action_required', False),
                summary=cat.get('summary', '')
            ))
    
    return results


@app.post("/api/analyze/actions", response_model=List[ActionItem])
@trace_operation("extract_actions")
async def extract_action_items(request: ActionItemExtractionRequest) -> List[ActionItem]:
    """Extract action items from emails"""
    loop = asyncio.get_event_loop()
    
    # Get recent emails
    from datetime import timedelta
    start_date = datetime.now() - timedelta(days=request.days)
    
    emails = await loop.run_in_executor(
        None,
        db_manager.get_emails_after_date,
        start_date,
        request.limit
    )
    
    email_ids = [e['id'] for e in emails]
    
    # Extract actions
    actions = await loop.run_in_executor(
        None,
        llm_integration.extract_action_items,
        email_ids
    )
    
    # Convert to response
    return [ActionItem(**action) for action in actions]


# System endpoints
@app.get("/api/status", response_model=SystemStatus)
async def get_system_status() -> SystemStatus:
    """Get system status"""
    loop = asyncio.get_event_loop()
    status = await loop.run_in_executor(None, etl_pipeline.get_status)
    
    return SystemStatus(
        database=status['database'],
        storage=status['storage'],
        last_sync=None,  # TODO: Track last sync
        version="1.0.0"
    )


# MCP Integration
mcp = FastMCP("gmail-etl-mcp")

# Register all MCP tools
@mcp.tool()
async def search_emails(
    query: str,
    limit: int = 10,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_content: bool = False
) -> Dict[str, Any]:
    """Search emails using semantic similarity"""
    request = EmailSearchRequest(
        query=query,
        limit=limit,
        date_from=datetime.fromisoformat(date_from) if date_from else None,
        date_to=datetime.fromisoformat(date_to) if date_to else None,
        include_content=include_content
    )
    
    response = await search_emails(request)
    return response.model_dump()


@mcp.tool()
async def ask_email_question(
    question: str,
    context_limit: int = 5,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Dict[str, Any]:
    """Ask a natural language question about emails"""
    request = EmailQuestionRequest(
        question=question,
        context_limit=context_limit,
        date_from=datetime.fromisoformat(date_from) if date_from else None,
        date_to=datetime.fromisoformat(date_to) if date_to else None
    )
    
    response = await ask_email_question(request)
    return response.model_dump()


# MCP metadata endpoint
@app.get("/mcp/tools")
async def get_mcp_tools():
    """Get MCP tool definitions"""
    return {
        "server": MCP_SERVER_INFO,
        "tools": get_mcp_tool_definitions()
    }


# Mount MCP server
app.mount("/mcp", mcp)


# Mount Prometheus metrics
from .telemetry import telemetry
if telemetry and telemetry.get("prometheus_app"):
    app.mount("/prometheus", telemetry["prometheus_app"])


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )