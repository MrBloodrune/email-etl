import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import base64
from tqdm import tqdm

from .database import db_manager
from .email_processor import EmailProcessor
from .markdown_storage import MarkdownStorage
from .security import security_validator
from .embeddings import embedding_generator
from .config import config

logger = logging.getLogger(__name__)


class ETLPipeline:
    """Main ETL pipeline for email data"""
    
    def __init__(self, provider_name: str = "gmail"):
        self.provider_name = provider_name
        self.email_processor = EmailProcessor(provider_name)
        self.markdown_storage = MarkdownStorage()
        self.stats = {
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'attachments_processed': 0,
            'attachments_rejected': 0
        }
    
    def run_import(self, 
                   query: str = "",
                   max_results: Optional[int] = None,
                   start_date: Optional[datetime] = None,
                   generate_embeddings: bool = True) -> Dict[str, Any]:
        """Run the full import pipeline"""
        logger.info(f"Starting Gmail import with query: '{query}'")
        
        # Build query with date filter if provided
        if start_date:
            date_str = start_date.strftime("%Y/%m/%d")
            query = f"{query} after:{date_str}".strip()
        
        # Get message list
        all_messages = []
        page_token = None
        
        while True:
            try:
                results = self.email_processor.list_messages(
                    query=query,
                    max_results=config.MAX_RESULTS_PER_PAGE if not max_results else min(max_results - len(all_messages), config.MAX_RESULTS_PER_PAGE),
                    page_token=page_token
                )
                
                messages = results.get('messages', [])
                all_messages.extend(messages)
                
                page_token = results.get('nextPageToken')
                
                if not page_token or (max_results and len(all_messages) >= max_results):
                    break
                
            except Exception as e:
                logger.error(f"Error listing messages: {e}")
                break
        
        logger.info(f"Found {len(all_messages)} messages to process")
        
        # Process messages in batches
        batch_size = config.BATCH_SIZE
        processed_emails = []
        
        for i in tqdm(range(0, len(all_messages), batch_size), desc="Processing emails"):
            batch = all_messages[i:i + batch_size]
            batch_results = self._process_batch(batch)
            processed_emails.extend(batch_results)
        
        # Generate embeddings if requested
        if generate_embeddings:
            self._generate_embeddings_batch(processed_emails)
        
        # Log results
        logger.info(f"Import complete. Stats: {self.stats}")
        
        return {
            'total_found': len(all_messages),
            'stats': self.stats,
            'processed_emails': len(processed_emails)
        }
    
    def _process_batch(self, messages: List[Dict[str, str]]) -> List[int]:
        """Process a batch of messages"""
        processed_ids = []
        
        for message in messages:
            try:
                email_id = self._process_single_email(message['id'])
                if email_id:
                    processed_ids.append(email_id)
                    self.stats['processed'] += 1
                else:
                    self.stats['skipped'] += 1
            
            except Exception as e:
                logger.error(f"Error processing message {message['id']}: {e}")
                self.stats['failed'] += 1
        
        return processed_ids
    
    def _process_single_email(self, message_id: str) -> Optional[int]:
        """Process a single email"""
        # Check if already processed
        existing = db_manager.get_email_by_message_id(message_id)
        if existing:
            logger.debug(f"Email {message_id} already processed")
            return existing['id']
        
        # Get full message
        email_data = self.email_processor.get_message(message_id)
        
        # Process attachments
        attachments_data = []
        if email_data.get('attachments'):
            attachments_data = self._process_attachments(
                message_id, 
                email_data['attachments']
            )
        
        # Insert into database
        email_id = db_manager.insert_email(email_data)
        
        # Save to markdown
        markdown_path = self.markdown_storage.save_email(email_data, attachments_data)
        
        # Update markdown path in database
        db_manager.update_markdown_path(email_id, markdown_path)
        
        # Save attachment metadata to database
        for att_data in attachments_data:
            att_data['email_id'] = email_id
            db_manager.insert_attachment(att_data)
        
        # Log audit
        db_manager.log_audit(email_id, 'imported', {
            'message_id': message_id,
            'attachments': len(attachments_data)
        }, provider=self.provider_name)
        
        return email_id
    
    def _process_attachments(self, 
                           message_id: str, 
                           attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and validate attachments"""
        processed_attachments = []
        
        for attachment in attachments:
            try:
                # Download attachment
                att_data = self.email_processor.get_attachment(
                    message_id,
                    attachment['attachment_id']
                )
                
                # Validate attachment
                validation_report = security_validator.validate_attachment(
                    attachment['filename'],
                    att_data,
                    attachment.get('mime_type')
                )
                
                if validation_report['is_safe']:
                    # Prepare attachment data
                    processed_attachments.append({
                        'filename': security_validator.sanitize_filename(attachment['filename']),
                        'mime_type': validation_report['detected_mime_type'] or attachment.get('mime_type'),
                        'size_bytes': len(att_data),
                        'content_hash': validation_report['content_hash'],
                        'is_safe': True,
                        'scan_results': validation_report['scan_results'],
                        'data_base64': security_validator.encode_attachment_safe(att_data)
                    })
                    self.stats['attachments_processed'] += 1
                else:
                    logger.warning(f"Attachment rejected: {attachment['filename']} - {validation_report['issues']}")
                    self.stats['attachments_rejected'] += 1
            
            except Exception as e:
                logger.error(f"Error processing attachment {attachment['filename']}: {e}")
                self.stats['attachments_rejected'] += 1
        
        return processed_attachments
    
    def _generate_embeddings_batch(self, email_ids: List[int]):
        """Generate embeddings for emails"""
        logger.info(f"Generating embeddings for {len(email_ids)} emails")
        
        # Get emails without embeddings
        emails_to_embed = db_manager.get_emails_without_embeddings(limit=1000)
        
        if not emails_to_embed:
            logger.info("All emails already have embeddings")
            return
        
        # Prepare texts for embedding
        texts = []
        email_id_map = []
        
        for email in emails_to_embed:
            text = embedding_generator.prepare_email_text(email)
            texts.append(text)
            email_id_map.append(email['id'])
        
        # Generate embeddings in batches
        batch_size = 100  # OpenAI can handle up to 2048 but let's be conservative
        
        for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
            batch_texts = texts[i:i + batch_size]
            batch_ids = email_id_map[i:i + batch_size]
            
            try:
                embeddings = embedding_generator.generate_batch_embeddings(batch_texts)
                
                # Update database
                for email_id, embedding in zip(batch_ids, embeddings):
                    db_manager.update_email_embedding(email_id, embedding)
            
            except Exception as e:
                logger.error(f"Error generating embeddings for batch: {e}")
    
    def run_incremental_sync(self) -> Dict[str, Any]:
        """Run incremental sync for new emails"""
        # Get the latest email date from database
        latest_date = db_manager.get_latest_email_date()
        
        if latest_date:
            # Add a small buffer to avoid missing emails
            start_date = latest_date.replace(tzinfo=timezone.utc)
            logger.info(f"Running incremental sync from {start_date}")
            return self.run_import(start_date=start_date)
        else:
            logger.info("No existing emails found, running full import")
            return self.run_import()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current ETL status"""
        email_count = db_manager.get_email_count()
        storage_stats = self.markdown_storage.get_storage_stats()
        
        return {
            'provider': self.provider_name,
            'database': {
                'total_emails': email_count,
                'emails_with_embeddings': db_manager.get_emails_with_embeddings_count()
            },
            'storage': storage_stats,
            'last_run_stats': self.stats,
            'provider_info': self.email_processor.get_provider_info()
        }
    
    def switch_provider(self, provider_name: str):
        """Switch to a different email provider"""
        self.provider_name = provider_name
        self.email_processor.switch_provider(provider_name)
        # Reset stats for new provider
        self.stats = {
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'attachments_processed': 0,
            'attachments_rejected': 0
        }
        logger.info(f"ETL pipeline switched to provider: {provider_name}")
    
    def authenticate_provider(self, **kwargs) -> bool:
        """Authenticate with the current provider"""
        return self.email_processor.authenticate(**kwargs)


# Global ETL pipeline instance
etl_pipeline = ETLPipeline()