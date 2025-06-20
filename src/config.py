import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration management for Gmail ETL pipeline"""
    
    # Gmail API Settings
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8080")
    GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
    TOKEN_FILE = "token.json"
    CREDENTIALS_FILE = "credentials.json"
    
    # PostgreSQL Settings
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB = os.getenv("POSTGRES_DB", "gmail_etl")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # OpenAI Settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSION = 1536  # for text-embedding-3-small
    
    # Security Settings
    MAX_ATTACHMENT_SIZE_MB = int(os.getenv("MAX_ATTACHMENT_SIZE_MB", "10"))
    MAX_ATTACHMENT_SIZE_BYTES = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    
    ALLOWED_MIME_TYPES = os.getenv(
        "ALLOWED_MIME_TYPES",
        "application/pdf,image/jpeg,image/png,image/gif,text/plain,"
        "application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ).split(",")
    
    # Storage Settings
    MARKDOWN_STORAGE_PATH = Path(os.getenv("MARKDOWN_STORAGE_PATH", "./emails"))
    ATTACHMENT_STORAGE_PATH = Path(os.getenv("ATTACHMENT_STORAGE_PATH", "./emails"))
    
    # ClamAV Settings
    ENABLE_CLAMAV = os.getenv("ENABLE_CLAMAV", "false").lower() == "true"
    CLAMAV_HOST = os.getenv("CLAMAV_HOST", "localhost")
    CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
    
    # Processing Settings
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))
    MAX_RESULTS_PER_PAGE = int(os.getenv("MAX_RESULTS_PER_PAGE", "100"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "gmail_etl.log")
    
    # Provider Settings
    ENABLED_PROVIDERS = os.getenv("ENABLED_PROVIDERS", "gmail").split(",")
    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "gmail")
    
    def __init__(self):
        """Initialize configuration and validate required settings"""
        self.validate()
        self.setup_directories()
    
    def validate(self):
        """Validate required configuration settings"""
        required = {
            "GOOGLE_CLIENT_ID": self.GOOGLE_CLIENT_ID,
            "GOOGLE_CLIENT_SECRET": self.GOOGLE_CLIENT_SECRET,
            "POSTGRES_USER": self.POSTGRES_USER,
            "POSTGRES_PASSWORD": self.POSTGRES_PASSWORD,
            "OPENAI_API_KEY": self.OPENAI_API_KEY,
        }
        
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
    
    def setup_directories(self):
        """Create necessary directories if they don't exist"""
        self.MARKDOWN_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        self.ATTACHMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

# Global config instance
config = Config()