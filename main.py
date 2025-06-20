#!/usr/bin/env python3
"""
Gmail ETL Pipeline CLI

A secure ETL pipeline for extracting emails from Gmail, storing them with 
PostgreSQL + pgvector, and enabling LLM-based search and analysis.
"""

import click
import logging
from datetime import datetime
import json
import sys
from pathlib import Path

from src.config import config
from src.database import db_manager
from src.etl_pipeline import etl_pipeline
from src.llm_integration import llm_integration
from src.embeddings import embedding_generator
from src.providers import list_providers

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """Gmail ETL Pipeline - Extract, Transform, and Load Gmail data for LLM analysis"""
    pass


@cli.command()
def providers():
    """List available email providers and statistics"""
    available = list_providers()
    enabled = config.ENABLED_PROVIDERS
    
    click.echo("\n📧 Available Email Providers:\n")
    for provider in available:
        status = "✓ Enabled" if provider in enabled else "  Disabled"
        default = " (default)" if provider == config.DEFAULT_PROVIDER else ""
        click.echo(f"  {provider:<15} {status}{default}")
    
    # Show provider statistics from database
    try:
        provider_stats = db_manager.get_providers()
        if provider_stats:
            click.echo("\n📊 Provider Statistics:\n")
            for stat in provider_stats:
                click.echo(f"  {stat['provider']:<15} {stat['email_count']:>8,} emails")
                if stat['provider_account']:
                    click.echo(f"    Account: {stat['provider_account']}")
                click.echo(f"    Date range: {stat['earliest_email']} to {stat['latest_email']}")
    except Exception:
        pass
    
    click.echo(f"\nTo enable providers, set ENABLED_PROVIDERS in .env")
    click.echo(f"Current: ENABLED_PROVIDERS={','.join(enabled)}\n")


@cli.group()
def auth():
    """Authentication management commands"""
    pass


@auth.command()
@click.option('--provider', '-p', default=None, help='Email provider to authenticate')
def login(provider):
    """Authenticate with email provider"""
    provider_name = provider or config.DEFAULT_PROVIDER
    
    try:
        # Switch to the specified provider
        etl_pipeline.switch_provider(provider_name)
        
        if etl_pipeline.authenticate_provider():
            click.echo(f"✓ Successfully authenticated with {provider_name}")
        else:
            click.echo(f"✗ Authentication failed for {provider_name}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"✗ Error during authentication: {e}", err=True)
        sys.exit(1)


@auth.command()
@click.option('--provider', '-p', default=None, help='Email provider')
def logout(provider):
    """Revoke email provider authentication"""
    provider_name = provider or config.DEFAULT_PROVIDER
    click.echo(f"Logout functionality needs to be implemented for {provider_name}")
    # TODO: Implement provider-specific logout


@auth.command()
@click.option('--provider', '-p', default=None, help='Email provider to test')
def test(provider):
    """Test email provider connection"""
    provider_name = provider or config.DEFAULT_PROVIDER
    
    try:
        etl_pipeline.switch_provider(provider_name)
        if etl_pipeline.email_processor.test_connection():
            click.echo(f"✓ {provider_name} connection successful")
        else:
            click.echo(f"✗ {provider_name} connection failed", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"✗ Error testing {provider_name}: {e}", err=True)
        sys.exit(1)


@cli.group()
def db():
    """Database management commands"""
    pass


@db.command()
def init():
    """Initialize database with pgvector"""
    click.echo("Initializing database...")
    
    # Test connection
    if db_manager.test_connection():
        click.echo("✓ Database connection successful")
        click.echo("✓ pgvector extension found")
        click.echo("\nRun the SQL script to create tables:")
        click.echo("  psql -d gmail_etl -f scripts/init_db.sql")
    else:
        click.echo("✗ Database connection failed", err=True)
        sys.exit(1)


@db.command()
def test():
    """Test database connection"""
    if db_manager.test_connection():
        click.echo("✓ Database connection successful")
    else:
        click.echo("✗ Database connection failed", err=True)
        sys.exit(1)


@cli.group()
def import_():
    """Email import commands"""
    pass


@import_.command('full')
@click.option('--provider', '-p', default=None, help='Email provider to use')
@click.option('--query', '-q', default='', help='Provider-specific search query')
@click.option('--max-results', '-m', type=int, help='Maximum emails to import')
@click.option('--start-date', '-s', help='Start date (YYYY-MM-DD)')
@click.option('--no-embeddings', is_flag=True, help='Skip embedding generation')
def import_full(provider, query, max_results, start_date, no_embeddings):
    """Run full email import"""
    provider_name = provider or config.DEFAULT_PROVIDER
    
    # Switch to the specified provider
    etl_pipeline.switch_provider(provider_name)
    
    click.echo(f"Starting full email import from {provider_name}...")
    
    # Parse start date
    start_dt = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            click.echo(f"✗ Invalid date format: {start_date}", err=True)
            sys.exit(1)
    
    # Run import
    try:
        results = etl_pipeline.run_import(
            query=query,
            max_results=max_results,
            start_date=start_dt,
            generate_embeddings=not no_embeddings
        )
        
        click.echo("\n✓ Import completed successfully!")
        click.echo(f"  Total emails found: {results['total_found']}")
        click.echo(f"  Emails processed: {results['stats']['processed']}")
        click.echo(f"  Emails skipped: {results['stats']['skipped']}")
        click.echo(f"  Emails failed: {results['stats']['failed']}")
        click.echo(f"  Attachments processed: {results['stats']['attachments_processed']}")
        click.echo(f"  Attachments rejected: {results['stats']['attachments_rejected']}")
        
    except Exception as e:
        click.echo(f"✗ Import failed: {e}", err=True)
        logger.exception("Import failed")
        sys.exit(1)


@import_.command('sync')
@click.option('--provider', '-p', default=None, help='Email provider to use')
def import_sync(provider):
    """Run incremental sync for new emails"""
    provider_name = provider or config.DEFAULT_PROVIDER
    
    # Switch to the specified provider
    etl_pipeline.switch_provider(provider_name)
    
    click.echo(f"Starting incremental sync from {provider_name}...")
    
    try:
        results = etl_pipeline.run_incremental_sync()
        
        click.echo("\n✓ Sync completed successfully!")
        click.echo(f"  New emails processed: {results['stats']['processed']}")
        
    except Exception as e:
        click.echo(f"✗ Sync failed: {e}", err=True)
        logger.exception("Sync failed")
        sys.exit(1)


@cli.group()
def search():
    """Search and query commands"""
    pass


@search.command('semantic')
@click.argument('query')
@click.option('--limit', '-l', default=10, help='Number of results')
@click.option('--show-content', '-c', is_flag=True, help='Show email content')
def search_semantic(query, limit, show_content):
    """Semantic search for emails"""
    try:
        results = llm_integration.semantic_search(query, limit=limit)
        
        if not results:
            click.echo("No matching emails found")
            return
        
        click.echo(f"\nFound {len(results)} matching emails:\n")
        
        for i, result in enumerate(results, 1):
            click.echo(f"{i}. Subject: {result.get('subject', 'No Subject')}")
            click.echo(f"   From: {result.get('sender', 'Unknown')}")
            click.echo(f"   Date: {result.get('date', 'Unknown')}")
            click.echo(f"   Similarity: {result.get('similarity', 0):.2%}")
            
            if show_content and result.get('content'):
                content_preview = result['content'][:200].replace('\n', ' ')
                click.echo(f"   Preview: {content_preview}...")
            
            click.echo()
        
    except Exception as e:
        click.echo(f"✗ Search failed: {e}", err=True)
        logger.exception("Search failed")
        sys.exit(1)


@search.command('ask')
@click.argument('question')
@click.option('--context', '-c', default=5, help='Number of emails to use as context')
def search_ask(question, context):
    """Ask questions about your emails"""
    try:
        click.echo(f"Searching for relevant emails...")
        
        result = llm_integration.answer_question(question, context_limit=context)
        
        click.echo(f"\n📧 Found {result['context_email_count']} relevant emails\n")
        click.echo("Answer:")
        click.echo("-" * 50)
        click.echo(result['answer'])
        click.echo("-" * 50)
        
        if result.get('sources'):
            click.echo("\nSources:")
            for source in result['sources']:
                click.echo(f"  • {source['subject']} (from {source['sender']})")
        
    except Exception as e:
        click.echo(f"✗ Failed to answer question: {e}", err=True)
        logger.exception("Question answering failed")
        sys.exit(1)


@cli.group()
def analyze():
    """Analysis and insights commands"""
    pass


@analyze.command('categorize')
@click.option('--limit', '-l', default=10, help='Number of recent emails to categorize')
def analyze_categorize(limit):
    """Categorize recent emails"""
    try:
        # Get recent emails
        recent_emails = db_manager.get_recent_emails(limit=limit)
        
        if not recent_emails:
            click.echo("No emails found to categorize")
            return
        
        email_ids = [e['id'] for e in recent_emails]
        
        click.echo(f"Categorizing {len(email_ids)} emails...")
        
        results = llm_integration.categorize_emails(email_ids)
        
        click.echo("\nCategorization Results:")
        click.echo("-" * 80)
        
        for email in recent_emails:
            email_id = email['id']
            if email_id in results:
                cat = results[email_id]
                
                click.echo(f"\n📧 {email['subject']}")
                
                if 'error' not in cat:
                    click.echo(f"   Category: {cat.get('primary_category', 'Unknown')}")
                    click.echo(f"   Subcategory: {cat.get('subcategory', 'N/A')}")
                    click.echo(f"   Priority: {cat.get('priority', 'Unknown')}")
                    click.echo(f"   Action Required: {cat.get('action_required', 'Unknown')}")
                    click.echo(f"   Summary: {cat.get('summary', 'N/A')}")
                else:
                    click.echo(f"   ✗ Error: {cat['error']}")
        
    except Exception as e:
        click.echo(f"✗ Categorization failed: {e}", err=True)
        logger.exception("Categorization failed")
        sys.exit(1)


@analyze.command('actions')
@click.option('--days', '-d', default=7, help='Extract actions from last N days')
def analyze_actions(days):
    """Extract action items from recent emails"""
    try:
        # Get recent emails
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=days)
        
        recent_emails = db_manager.get_emails_after_date(start_date, limit=50)
        
        if not recent_emails:
            click.echo(f"No emails found in the last {days} days")
            return
        
        email_ids = [e['id'] for e in recent_emails]
        
        click.echo(f"Extracting action items from {len(email_ids)} emails...")
        
        actions = llm_integration.extract_action_items(email_ids)
        
        if not actions:
            click.echo("\nNo action items found")
            return
        
        click.echo(f"\n📋 Found {len(actions)} action items:\n")
        
        for i, action in enumerate(actions, 1):
            click.echo(f"{i}. {action.get('description', 'No description')}")
            
            if action.get('responsible'):
                click.echo(f"   Assigned to: {action['responsible']}")
            
            if action.get('due_date'):
                click.echo(f"   Due: {action['due_date']}")
            
            click.echo(f"   Priority: {action.get('priority', 'Normal')}")
            click.echo(f"   From: {action.get('email_subject', 'Unknown')}")
            click.echo()
        
    except Exception as e:
        click.echo(f"✗ Action extraction failed: {e}", err=True)
        logger.exception("Action extraction failed")
        sys.exit(1)


@cli.command()
def status():
    """Show ETL pipeline status"""
    try:
        status = etl_pipeline.get_status()
        
        click.echo("\n📊 Email ETL Pipeline Status\n")
        
        click.echo(f"Current Provider: {status['provider']}")
        
        # Show provider info if available
        if status.get('provider_info'):
            info = status['provider_info']
            if info.get('account_info'):
                click.echo(f"  Account: {info['account_info'].get('email_address', 'N/A')}")
            click.echo(f"  Supports Labels: {info.get('supports_labels', False)}")
            click.echo(f"  Supports Threading: {info.get('supports_threading', False)}")
        
        click.echo("\nDatabase:")
        click.echo(f"  Total emails: {status['database']['total_emails']:,}")
        click.echo(f"  With embeddings: {status['database']['emails_with_embeddings']:,}")
        
        click.echo("\nStorage:")
        click.echo(f"  Total emails: {status['storage']['total_emails']:,}")
        click.echo(f"  With attachments: {status['storage']['emails_with_attachments']:,}")
        click.echo(f"  Storage size: {status['storage']['total_size_mb']:.2f} MB")
        
        if status['storage']['last_updated']:
            click.echo(f"  Last updated: {status['storage']['last_updated']}")
        
        if status['last_run_stats']['processed'] > 0:
            click.echo("\nLast Run:")
            for key, value in status['last_run_stats'].items():
                click.echo(f"  {key}: {value}")
        
    except Exception as e:
        click.echo(f"✗ Failed to get status: {e}", err=True)
        logger.exception("Status check failed")
        sys.exit(1)


@cli.command()
@click.option('--text-count', '-t', type=int, default=1000, help='Number of texts to estimate for')
@click.option('--avg-tokens', '-a', type=int, default=500, help='Average tokens per text')
def estimate_cost(text_count, avg_tokens):
    """Estimate embedding generation costs"""
    estimate = embedding_generator.estimate_cost(text_count, avg_tokens)
    
    click.echo("\n💰 Embedding Cost Estimate\n")
    click.echo(f"Text count: {estimate['text_count']:,}")
    click.echo(f"Estimated tokens: {estimate['estimated_tokens']:,}")
    click.echo(f"Estimated cost: ${estimate['estimated_cost_usd']:.4f}")
    click.echo(f"\nModel: {config.EMBEDDING_MODEL}")


if __name__ == '__main__':
    cli()