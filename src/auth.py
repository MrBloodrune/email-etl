"""
Backward compatibility layer for authentication

This module provides compatibility with the old authentication system
while using the new provider-based architecture.
"""
import logging
from typing import Optional

from .providers import get_provider
from .providers.gmail.provider import GmailProvider

logger = logging.getLogger(__name__)


class GmailAuthenticator:
    """Compatibility wrapper for GmailProvider"""
    
    def __init__(self, token_file: Optional[str] = None):
        self.provider = get_provider('gmail') or GmailProvider()
        if hasattr(self.provider, 'token_file') and token_file:
            self.provider.token_file = token_file
    
    def authenticate(self):
        """Authenticate with Gmail"""
        return self.provider.authenticate()
    
    def test_connection(self) -> bool:
        """Test Gmail connection"""
        return self.provider.test_connection()
    
    def get_service(self):
        """Get Gmail service instance"""
        if hasattr(self.provider, '_get_service'):
            return self.provider._get_service()
        # Fallback for compatibility
        return None
    
    def revoke_token(self):
        """Revoke token (placeholder for compatibility)"""
        logger.info("Token revocation should be implemented in the provider")


class AuthManager:
    """Singleton auth manager for backward compatibility"""
    _instance = None
    _authenticator = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_authenticator(self) -> GmailAuthenticator:
        if not self._authenticator:
            self._authenticator = GmailAuthenticator()
        return self._authenticator
    
    def get_service(self):
        """Get Gmail service instance"""
        return self.get_authenticator().get_service()


# Global auth manager for backward compatibility
auth_manager = AuthManager()