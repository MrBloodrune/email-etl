import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.extensions import register_adapter
from pgvector.psycopg2 import register_vector
import numpy as np

from .config import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage PostgreSQL database connections and operations"""
    
    def __init__(self):
        self.connection_params = {
            'host': config.POSTGRES_HOST,
            'port': config.POSTGRES_PORT,
            'database': config.POSTGRES_DB,
            'user': config.POSTGRES_USER,
            'password': config.POSTGRES_PASSWORD
        }
        self._register_types()
    
    def _register_types(self):
        """Register custom types for psycopg2"""
        # Register numpy array adapter for pgvector
        def addapt_numpy_ndarray(numpy_ndarray):
            return psycopg2.extensions.AsIs(numpy_ndarray.tolist())
        register_adapter(np.ndarray, addapt_numpy_ndarray)
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            register_vector(conn)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                    result = cur.fetchone()
                    if result:
                        logger.info(f"Connected to PostgreSQL with pgvector version: {result[0]}")
                        return True
                    else:
                        logger.error("pgvector extension not found")
                        return False
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def insert_email(self, email_data: Dict[str, Any]) -> int:
        """Insert email into database and return email_id"""
        # Extract provider info from metadata
        provider = email_data.get('metadata', {}).get('provider', 'gmail')
        provider_account = email_data.get('metadata', {}).get('provider_account')
        
        query = """
            INSERT INTO emails (
                message_id, thread_id, subject, sender, sender_name,
                recipients, cc_recipients, bcc_recipients, date,
                body_plain, body_html, body_markdown, labels,
                has_attachments, embedding, markdown_path, metadata,
                provider, provider_account
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (message_id) DO UPDATE SET
                updated_at = NOW(),
                embedding = EXCLUDED.embedding,
                markdown_path = EXCLUDED.markdown_path,
                provider = EXCLUDED.provider,
                provider_account = EXCLUDED.provider_account
            RETURNING id;
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (
                    email_data['message_id'],
                    email_data.get('thread_id'),
                    email_data.get('subject'),
                    email_data.get('sender'),
                    email_data.get('sender_name'),
                    email_data.get('recipients', []),
                    email_data.get('cc_recipients', []),
                    email_data.get('bcc_recipients', []),
                    email_data.get('date'),
                    email_data.get('body_plain'),
                    email_data.get('body_html'),
                    email_data.get('body_markdown'),
                    email_data.get('labels', []),
                    email_data.get('has_attachments', False),
                    email_data.get('embedding'),
                    email_data.get('markdown_path'),
                    Json(email_data.get('metadata', {})),
                    provider,
                    provider_account
                ))
                email_id = cur.fetchone()[0]
                conn.commit()
                return email_id
    
    def insert_attachment(self, attachment_data: Dict[str, Any]) -> int:
        """Insert attachment metadata into database"""
        query = """
            INSERT INTO attachments (
                email_id, filename, mime_type, size_bytes,
                content_hash, is_safe, scan_results, file_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (
                    attachment_data['email_id'],
                    attachment_data['filename'],
                    attachment_data.get('mime_type'),
                    attachment_data.get('size_bytes'),
                    attachment_data.get('content_hash'),
                    attachment_data.get('is_safe'),
                    Json(attachment_data.get('scan_results', {})),
                    attachment_data.get('file_path')
                ))
                attachment_id = cur.fetchone()[0]
                conn.commit()
                return attachment_id
    
    def update_email_embedding(self, email_id: int, embedding: np.ndarray):
        """Update email embedding"""
        query = "UPDATE emails SET embedding = %s WHERE id = %s"
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (embedding.tolist(), email_id))
                conn.commit()
    
    def update_markdown_path(self, email_id: int, markdown_path: str):
        """Update email markdown path"""
        query = "UPDATE emails SET markdown_path = %s WHERE id = %s"
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (markdown_path, email_id))
                conn.commit()
    
    def search_similar_emails(self, embedding: np.ndarray, limit: int = 10) -> List[Dict]:
        """Search for similar emails using vector similarity"""
        query = """
            SELECT 
                id, message_id, subject, sender, date,
                1 - (embedding <=> %s::vector) as similarity,
                markdown_path
            FROM emails
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (embedding.tolist(), embedding.tolist(), limit))
                return cur.fetchall()
    
    def hybrid_search(self, 
                     query_embedding: np.ndarray,
                     query_text: str,
                     limit: int = 10,
                     date_from: Optional[datetime] = None,
                     date_to: Optional[datetime] = None,
                     provider_filter: Optional[str] = None,
                     account_filter: Optional[str] = None) -> List[Dict]:
        """Perform hybrid search combining vector and full-text search"""
        query = """
            SELECT * FROM hybrid_email_search(%s::vector, %s, %s, %s, %s, %s, %s)
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (
                    query_embedding.tolist(),
                    query_text,
                    limit,
                    date_from,
                    date_to,
                    provider_filter,
                    account_filter
                ))
                return cur.fetchall()
    
    def get_email_by_message_id(self, message_id: str) -> Optional[Dict]:
        """Get email by Gmail message ID"""
        query = """
            SELECT * FROM emails WHERE message_id = %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (message_id,))
                return cur.fetchone()
    
    def get_email_by_id(self, email_id: int) -> Optional[Dict]:
        """Get email by database ID"""
        query = """
            SELECT * FROM emails WHERE id = %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (email_id,))
                return cur.fetchone()
    
    def get_emails_by_thread(self, thread_id: str) -> List[Dict]:
        """Get all emails in a thread"""
        query = """
            SELECT * FROM emails 
            WHERE thread_id = %s 
            ORDER BY date ASC
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (thread_id,))
                return cur.fetchall()
    
    def get_emails_without_embeddings(self, limit: int = 100) -> List[Dict]:
        """Get emails that don't have embeddings yet"""
        query = """
            SELECT id, message_id, subject, sender, sender_name, recipients,
                   date, body_plain, body_markdown, labels
            FROM emails
            WHERE embedding IS NULL
            AND (body_plain IS NOT NULL OR body_markdown IS NOT NULL)
            ORDER BY date DESC
            LIMIT %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit,))
                return cur.fetchall()
    
    def get_email_count(self) -> int:
        """Get total email count"""
        query = "SELECT COUNT(*) FROM emails"
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchone()[0]
    
    def get_emails_with_embeddings_count(self) -> int:
        """Get count of emails with embeddings"""
        query = "SELECT COUNT(*) FROM emails WHERE embedding IS NOT NULL"
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchone()[0]
    
    def get_latest_email_date(self) -> Optional[datetime]:
        """Get the date of the most recent email"""
        query = "SELECT MAX(date) FROM emails"
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                result = cur.fetchone()
                return result[0] if result else None
    
    def get_recent_emails(self, limit: int = 10) -> List[Dict]:
        """Get recent emails"""
        query = """
            SELECT id, message_id, subject, sender, date
            FROM emails
            ORDER BY date DESC
            LIMIT %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (limit,))
                return cur.fetchall()
    
    def get_emails_after_date(self, date: datetime, limit: int = 100) -> List[Dict]:
        """Get emails after a specific date"""
        query = """
            SELECT id, message_id, subject, sender, date
            FROM emails
            WHERE date > %s
            ORDER BY date DESC
            LIMIT %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (date, limit))
                return cur.fetchall()
    
    def log_audit(self, email_id: int, action: str, details: Dict[str, Any], provider: Optional[str] = None):
        """Log an audit entry"""
        query = """
            INSERT INTO email_audit_log (email_id, action, details, provider)
            VALUES (%s, %s, %s, %s)
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (email_id, action, Json(details), provider))
                conn.commit()
    
    def get_providers(self) -> List[Dict[str, Any]]:
        """Get list of providers with email counts"""
        query = """
            SELECT * FROM emails_by_provider
            ORDER BY email_count DESC
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()
    
    def save_provider_config(self, provider: str, account: Optional[str], config_key: str, config_value: str):
        """Save provider configuration"""
        query = """
            INSERT INTO provider_config (provider, account, config_key, config_value)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (provider, account, config_key) DO UPDATE
            SET config_value = EXCLUDED.config_value,
                updated_at = NOW()
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (provider, account, config_key, config_value))
                conn.commit()
    
    def get_provider_config(self, provider: str, account: Optional[str] = None) -> Dict[str, str]:
        """Get provider configuration"""
        query = """
            SELECT config_key, config_value
            FROM provider_config
            WHERE provider = %s AND (account = %s OR account IS NULL)
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (provider, account))
                results = cur.fetchall()
                return {row['config_key']: row['config_value'] for row in results}
    
    def save_provider_token(self, provider: str, account: str, token_type: str, 
                           token_value: str, expires_at: Optional[datetime] = None):
        """Save provider token"""
        query = """
            INSERT INTO provider_tokens (provider, account, token_type, token_value, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (provider, account, token_type) DO UPDATE
            SET token_value = EXCLUDED.token_value,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (provider, account, token_type, token_value, expires_at))
                conn.commit()
    
    def get_provider_token(self, provider: str, account: str, token_type: str) -> Optional[Dict[str, Any]]:
        """Get provider token"""
        query = """
            SELECT token_value, expires_at
            FROM provider_tokens
            WHERE provider = %s AND account = %s AND token_type = %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (provider, account, token_type))
                return cur.fetchone()


# Global database manager
db_manager = DatabaseManager()