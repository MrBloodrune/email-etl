import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from .providers import get_provider
from .providers.base import BaseEmailProvider
from .config import config

logger = logging.getLogger(__name__)


class EmailProcessor:
    """Process and extract email data using provider plugins"""
    
    def __init__(self, provider_name: str = "gmail"):
        self.provider_name = provider_name
        self.provider: Optional[BaseEmailProvider] = None
        self._initialize_provider()
    
    def _initialize_provider(self):
        """Initialize the email provider"""
        self.provider = get_provider(self.provider_name)
        if not self.provider:
            raise ValueError(f"Unknown provider: {self.provider_name}")
        
        logger.info(f"Initialized email processor with provider: {self.provider_name}")
    
    def authenticate(self, **kwargs) -> bool:
        """Authenticate with the email provider"""
        return self.provider.authenticate(**kwargs)
    
    def test_connection(self) -> bool:
        """Test connection to email provider"""
        return self.provider.test_connection()
    
    def list_messages(self, 
                     query: str = "",
                     max_results: int = None,
                     page_token: str = None,
                     include_spam_trash: bool = False,
                     start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """List messages from the email provider"""
        return self.provider.list_messages(
            query=query,
            max_results=max_results,
            page_token=page_token,
            start_date=start_date,
            end_date=end_date,
            include_spam_trash=include_spam_trash
        )
    
    def get_message(self, message_id: str) -> Dict[str, Any]:
        """Get full message details"""
        return self.provider.get_message(message_id)
    
    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download attachment data"""
        return self.provider.get_attachment(message_id, attachment_id)
    
    def process_batch(self, message_ids: List[str]) -> List[Dict[str, Any]]:
        """Process a batch of messages"""
        return self.provider.process_batch(message_ids)
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider"""
        return {
            'name': self.provider_name,
            'supports_labels': self.provider.supports_labels(),
            'supports_threading': self.provider.supports_threading(),
            'supports_search': self.provider.supports_search(),
            'account_info': self.provider.get_account_info(),
            'quota_info': self.provider.get_quota_info()
        }
    
    def switch_provider(self, provider_name: str):
        """Switch to a different email provider"""
        self.provider_name = provider_name
        self._initialize_provider()
        logger.info(f"Switched to provider: {provider_name}")