# Email Provider Plugin System

This directory contains the plugin-based email provider system that allows the ETL pipeline to work with multiple email services.

## Architecture

```
providers/
├── __init__.py      # Provider registry and auto-discovery
├── base.py          # BaseEmailProvider abstract class
├── gmail/           # Gmail provider implementation
│   ├── __init__.py
│   └── provider.py
├── imap/            # IMAP provider (to be implemented)
│   ├── __init__.py
│   └── provider.py
└── outlook/         # Outlook provider (to be implemented)
    ├── __init__.py
    └── provider.py
```

## Creating a New Provider

To add support for a new email service, follow these steps:

### 1. Create Provider Directory

```bash
mkdir src/providers/your_provider
touch src/providers/your_provider/__init__.py
touch src/providers/your_provider/provider.py
```

### 2. Implement the Provider Class

Create a class that inherits from `BaseEmailProvider`:

```python
# src/providers/your_provider/provider.py
from ..base import BaseEmailProvider
from typing import Dict, List, Any, Optional
from datetime import datetime

class YourProvider(BaseEmailProvider):
    """Your email provider implementation"""
    
    PROVIDER_NAME = "your_provider"
    
    def __init__(self):
        super().__init__()
        # Initialize provider-specific attributes
    
    def authenticate(self, **kwargs) -> bool:
        """Implement authentication logic"""
        # For OAuth2: implement OAuth flow
        # For IMAP: store credentials securely
        pass
    
    def test_connection(self) -> bool:
        """Test if connection is valid"""
        pass
    
    def list_messages(self, 
                     query: str = "",
                     max_results: Optional[int] = None,
                     page_token: Optional[str] = None,
                     start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None,
                     **kwargs) -> Dict[str, Any]:
        """List messages from the provider"""
        # Return format:
        # {
        #     'messages': [{'id': 'msg_id'}, ...],
        #     'next_page_token': 'token' or None,
        #     'total_results': 100
        # }
        pass
    
    def get_message(self, message_id: str, **kwargs) -> Dict[str, Any]:
        """Get full message details"""
        # Return standardized format - see base.py for details
        pass
    
    def get_attachment(self, message_id: str, attachment_id: str, **kwargs) -> bytes:
        """Download attachment data"""
        pass
```

### 3. Export the Provider

In `src/providers/your_provider/__init__.py`:

```python
from .provider import YourProvider

__all__ = ['YourProvider']
```

### 4. Provider Auto-Discovery

The provider will be automatically discovered when placed in the providers directory. The registry looks for classes that inherit from `BaseEmailProvider`.

## Provider Requirements

### Message Format

All providers must return messages in this standardized format:

```python
{
    'message_id': 'unique_id',
    'thread_id': 'thread_id',  # optional
    'subject': 'Email subject',
    'sender': 'sender@example.com',
    'sender_name': 'Sender Name',
    'recipients': ['recipient@example.com'],
    'cc_recipients': [],
    'bcc_recipients': [],
    'date': datetime_object,
    'body_plain': 'Plain text content',
    'body_html': '<html>...</html>',
    'body_markdown': 'Markdown content',
    'labels': ['label1', 'label2'],  # or folders
    'has_attachments': True,
    'attachments': [
        {
            'filename': 'file.pdf',
            'mime_type': 'application/pdf',
            'size_bytes': 1234,
            'attachment_id': 'att_id'
        }
    ],
    'headers': {'From': '...', 'To': '...'},
    'metadata': {
        'provider': 'your_provider',
        'provider_account': 'account@example.com',
        # ... provider-specific data
    }
}
```

### Authentication

Providers can implement various authentication methods:

1. **OAuth2** (like Gmail): Store tokens in database using `db_manager.save_provider_token()`
2. **Credentials** (like IMAP): Store encrypted in `provider_config` table
3. **API Keys**: Store in environment variables or config

### Configuration

Provider-specific configuration can be stored in:

1. Environment variables: `YOUR_PROVIDER_API_KEY`
2. Database: Use `db_manager.save_provider_config()`
3. Config file: Add to `src/config.py`

## Example: IMAP Provider

Here's a skeleton for an IMAP provider:

```python
import imaplib
import email
from email.utils import parsedate_to_datetime
from ..base import BaseEmailProvider

class IMAPProvider(BaseEmailProvider):
    PROVIDER_NAME = "imap"
    
    def __init__(self):
        super().__init__()
        self.connection = None
        self.host = None
        self.port = 993  # default IMAP SSL port
        self.username = None
        self.password = None
    
    def authenticate(self, host: str, username: str, password: str, 
                    port: int = 993, use_ssl: bool = True, **kwargs) -> bool:
        try:
            self.host = host
            self.port = port
            self.username = username
            self.password = password
            
            if use_ssl:
                self.connection = imaplib.IMAP4_SSL(host, port)
            else:
                self.connection = imaplib.IMAP4(host, port)
            
            self.connection.login(username, password)
            return True
        except Exception as e:
            self.logger.error(f"IMAP authentication failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        try:
            if not self.connection:
                return False
            status, data = self.connection.noop()
            return status == 'OK'
        except:
            return False
    
    # ... implement other required methods
```

## Testing Your Provider

1. **Unit Tests**: Create `tests/test_your_provider.py`
2. **Integration**: Test with the CLI:
   ```bash
   python main.py auth login --provider your_provider
   python main.py auth test --provider your_provider
   python main.py import full --provider your_provider --max-results 10
   ```

## Provider Registration

Providers are automatically registered when the module is imported. You can also manually register:

```python
from src.providers import register_provider
from src.providers.your_provider import YourProvider

register_provider('custom_name', YourProvider)
```

## Best Practices

1. **Error Handling**: Use try-except blocks and log errors
2. **Rate Limiting**: Implement rate limiting if the service has quotas
3. **Pagination**: Handle large result sets with pagination
4. **Caching**: Cache authentication tokens when appropriate
5. **Security**: Never log passwords or sensitive tokens
6. **Documentation**: Document provider-specific features and limitations