"""
Base email provider interface

Defines the abstract base class that all email providers must implement.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class BaseEmailProvider(ABC):
    """Abstract base class for email providers"""
    
    PROVIDER_NAME = "base"  # Override in subclasses
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.PROVIDER_NAME}")
    
    @abstractmethod
    def authenticate(self, **kwargs) -> bool:
        """
        Authenticate with the email provider
        
        Args:
            **kwargs: Provider-specific authentication parameters
            
        Returns:
            bool: True if authentication successful
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the connection to the email provider
        
        Returns:
            bool: True if connection is valid
        """
        pass
    
    @abstractmethod
    def list_messages(self, 
                     query: str = "",
                     max_results: Optional[int] = None,
                     page_token: Optional[str] = None,
                     start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None,
                     **kwargs) -> Dict[str, Any]:
        """
        List messages from the email provider
        
        Args:
            query: Provider-specific search query
            max_results: Maximum number of results to return
            page_token: Token for pagination
            start_date: Filter messages after this date
            end_date: Filter messages before this date
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Dict containing:
                - messages: List of message metadata
                - next_page_token: Token for next page (if any)
                - total_results: Total number of results (if available)
        """
        pass
    
    @abstractmethod
    def get_message(self, message_id: str, **kwargs) -> Dict[str, Any]:
        """
        Get full message details
        
        Args:
            message_id: Provider-specific message identifier
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Dict containing standardized email data:
                - message_id: Unique message ID
                - thread_id: Thread/conversation ID (if applicable)
                - subject: Email subject
                - sender: Sender email address
                - sender_name: Sender display name
                - recipients: List of recipient addresses
                - cc_recipients: List of CC addresses
                - bcc_recipients: List of BCC addresses
                - date: Message date as datetime
                - body_plain: Plain text body
                - body_html: HTML body
                - body_markdown: Markdown version of body
                - labels: List of labels/folders
                - has_attachments: Boolean
                - attachments: List of attachment metadata
                - headers: Dict of email headers
                - metadata: Provider-specific metadata
        """
        pass
    
    @abstractmethod
    def get_attachment(self, message_id: str, attachment_id: str, **kwargs) -> bytes:
        """
        Download attachment data
        
        Args:
            message_id: Message identifier
            attachment_id: Attachment identifier
            **kwargs: Additional provider-specific parameters
            
        Returns:
            bytes: Raw attachment data
        """
        pass
    
    def process_batch(self, message_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Process a batch of messages (can be overridden for optimization)
        
        Args:
            message_ids: List of message IDs to process
            
        Returns:
            List of message data dictionaries
        """
        results = []
        for message_id in message_ids:
            try:
                email_data = self.get_message(message_id)
                results.append(email_data)
            except Exception as e:
                self.logger.error(f"Error processing message {message_id}: {e}")
                continue
        return results
    
    def get_provider_name(self) -> str:
        """Get the provider name"""
        return self.PROVIDER_NAME
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the authenticated account
        
        Returns:
            Dict with account information or None if not authenticated
        """
        return None
    
    def supports_labels(self) -> bool:
        """Check if provider supports labels/folders"""
        return False
    
    def supports_threading(self) -> bool:
        """Check if provider supports email threading"""
        return False
    
    def supports_search(self) -> bool:
        """Check if provider supports server-side search"""
        return True
    
    def get_quota_info(self) -> Optional[Dict[str, Any]]:
        """
        Get quota/rate limit information
        
        Returns:
            Dict with quota information or None if not applicable
        """
        return None
    
    def normalize_message_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize provider-specific message data to standard format
        
        This method should be implemented by providers to convert their
        specific data format to the standard format expected by the system.
        
        Args:
            raw_data: Provider-specific message data
            
        Returns:
            Standardized message data dictionary
        """
        # Default implementation - override in subclasses
        return raw_data
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(provider={self.PROVIDER_NAME})>"