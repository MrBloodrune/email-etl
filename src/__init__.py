# Gmail ETL Pipeline Package

from .config import config
from .auth import auth_manager, GmailAuthenticator
from .database import DatabaseManager

__version__ = "0.1.0"
__all__ = ["config", "auth_manager", "GmailAuthenticator", "DatabaseManager"]