"""Gmail provider implementation"""
import os
import json
import base64
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from email.utils import parseaddr

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup
import html2text

from ..base import BaseEmailProvider
from ...config import config


class GmailProvider(BaseEmailProvider):
    """Gmail email provider using Gmail API"""
    
    PROVIDER_NAME = "gmail"
    
    def __init__(self):
        super().__init__()
        self.credentials: Optional[Credentials] = None
        self.service = None
        self.token_file = config.TOKEN_FILE
        self.scopes = config.GMAIL_SCOPES
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = False
        self.html_converter.body_width = 0  # Don't wrap lines
    
    def authenticate(self, **kwargs) -> bool:
        """Authenticate with Gmail using OAuth2"""
        try:
            creds = None
            
            # Load existing token
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            
            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Create credentials.json if it doesn't exist
                    if not os.path.exists(config.CREDENTIALS_FILE):
                        self._create_credentials_file()
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        config.CREDENTIALS_FILE, self.scopes
                    )
                    creds = flow.run_local_server(
                        port=8080,
                        prompt='consent',
                        access_type='offline'
                    )
                
                # Save the credentials for the next run
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            
            self.credentials = creds
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test Gmail API connection"""
        try:
            service = self._get_service()
            # Try to get user profile
            profile = service.users().getProfile(userId='me').execute()
            self.logger.info(f"Successfully connected to Gmail for: {profile.get('emailAddress')}")
            return True
        except HttpError as error:
            self.logger.error(f"Connection test failed: {error}")
            return False
    
    def list_messages(self, 
                     query: str = "",
                     max_results: Optional[int] = None,
                     page_token: Optional[str] = None,
                     start_date: Optional[datetime] = None,
                     end_date: Optional[datetime] = None,
                     **kwargs) -> Dict[str, Any]:
        """List Gmail messages"""
        try:
            service = self._get_service()
            
            # Build query with date filters
            full_query = query
            if start_date:
                date_str = start_date.strftime("%Y/%m/%d")
                full_query = f"{full_query} after:{date_str}".strip()
            if end_date:
                date_str = end_date.strftime("%Y/%m/%d")
                full_query = f"{full_query} before:{date_str}".strip()
            
            params = {
                'userId': 'me',
                'includeSpamTrash': kwargs.get('include_spam_trash', False)
            }
            
            if full_query:
                params['q'] = full_query
            if max_results:
                params['maxResults'] = min(max_results, config.MAX_RESULTS_PER_PAGE)
            if page_token:
                params['pageToken'] = page_token
            
            result = service.users().messages().list(**params).execute()
            
            return {
                'messages': result.get('messages', []),
                'next_page_token': result.get('nextPageToken'),
                'total_results': result.get('resultSizeEstimate')
            }
            
        except HttpError as error:
            self.logger.error(f"Error listing messages: {error}")
            raise
    
    def get_message(self, message_id: str, **kwargs) -> Dict[str, Any]:
        """Get full Gmail message details"""
        try:
            service = self._get_service()
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            return self._parse_message(message)
            
        except HttpError as error:
            self.logger.error(f"Error getting message {message_id}: {error}")
            raise
    
    def get_attachment(self, message_id: str, attachment_id: str, **kwargs) -> bytes:
        """Download Gmail attachment"""
        try:
            service = self._get_service()
            attachment = service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            data = attachment.get('data', '')
            return base64.urlsafe_b64decode(data)
            
        except HttpError as error:
            self.logger.error(f"Error downloading attachment: {error}")
            raise
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get Gmail account information"""
        try:
            service = self._get_service()
            profile = service.users().getProfile(userId='me').execute()
            
            return {
                'email_address': profile.get('emailAddress'),
                'threads_total': profile.get('threadsTotal'),
                'messages_total': profile.get('messagesTotal'),
                'history_id': profile.get('historyId')
            }
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return None
    
    def supports_labels(self) -> bool:
        """Gmail supports labels"""
        return True
    
    def supports_threading(self) -> bool:
        """Gmail supports threading"""
        return True
    
    def get_quota_info(self) -> Optional[Dict[str, Any]]:
        """Get Gmail API quota information"""
        # Gmail API quotas are managed externally
        # This could be enhanced to track usage
        return {
            'daily_limit': 1000000000,  # 1 billion quota units per day
            'per_user_limit': 250,  # quota units per user per second
            'note': 'Gmail API quotas are managed in Google Cloud Console'
        }
    
    def _get_service(self):
        """Get Gmail API service instance"""
        if not self.service:
            if not self.credentials:
                self.authenticate()
            
            self.service = build('gmail', 'v1', credentials=self.credentials)
        
        return self.service
    
    def _create_credentials_file(self):
        """Create credentials.json from environment variables"""
        credentials_data = {
            "installed": {
                "client_id": config.GOOGLE_CLIENT_ID,
                "client_secret": config.GOOGLE_CLIENT_SECRET,
                "redirect_uris": [config.GOOGLE_REDIRECT_URI],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "project_id": "gmail-etl-project"
            }
        }
        
        with open(config.CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials_data, f, indent=2)
    
    def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Gmail message into standardized format"""
        headers = self._parse_headers(message['payload'].get('headers', []))
        
        # Extract email addresses
        sender_email, sender_name = parseaddr(headers.get('From', ''))
        
        # Parse body and attachments
        body_plain, body_html, attachments = self._parse_payload(message['payload'])
        
        # Convert HTML to Markdown if no plain text
        body_markdown = None
        if body_html and not body_plain:
            body_markdown = self._html_to_markdown(body_html)
        elif body_plain:
            body_markdown = body_plain
        
        # Parse date
        date = None
        if 'Date' in headers:
            try:
                date = datetime.strptime(
                    headers['Date'], 
                    '%a, %d %b %Y %H:%M:%S %z'
                )
            except ValueError:
                # Try alternative formats
                try:
                    from dateutil import parser
                    date = parser.parse(headers['Date'])
                except:
                    self.logger.warning(f"Could not parse date: {headers['Date']}")
        
        # Build standardized email data
        return {
            'message_id': message['id'],
            'thread_id': message.get('threadId'),
            'subject': headers.get('Subject', '(No Subject)'),
            'sender': sender_email,
            'sender_name': sender_name,
            'recipients': self._parse_recipients(headers.get('To', '')),
            'cc_recipients': self._parse_recipients(headers.get('Cc', '')),
            'bcc_recipients': self._parse_recipients(headers.get('Bcc', '')),
            'date': date,
            'body_plain': body_plain,
            'body_html': body_html,
            'body_markdown': body_markdown,
            'labels': message.get('labelIds', []),
            'has_attachments': len(attachments) > 0,
            'attachments': attachments,
            'headers': headers,
            'metadata': {
                'snippet': message.get('snippet'),
                'size_estimate': message.get('sizeEstimate'),
                'history_id': message.get('historyId'),
                'provider': self.PROVIDER_NAME
            }
        }
    
    def _parse_headers(self, headers: List[Dict[str, str]]) -> Dict[str, str]:
        """Parse email headers into dictionary"""
        return {h['name']: h['value'] for h in headers}
    
    def _parse_recipients(self, recipients_str: str) -> List[str]:
        """Parse recipient string into list of email addresses"""
        if not recipients_str:
            return []
        
        recipients = []
        for recipient in recipients_str.split(','):
            email, _ = parseaddr(recipient.strip())
            if email:
                recipients.append(email)
        
        return recipients
    
    def _parse_payload(self, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[Dict]]:
        """Parse message payload to extract body and attachments"""
        body_plain = None
        body_html = None
        attachments = []
        
        def process_part(part):
            nonlocal body_plain, body_html
            
            mime_type = part.get('mimeType', '')
            
            # Handle multipart
            if mime_type.startswith('multipart/'):
                for subpart in part.get('parts', []):
                    process_part(subpart)
            
            # Handle text parts
            elif mime_type == 'text/plain' and not body_plain:
                data = part.get('body', {}).get('data', '')
                if data:
                    body_plain = self._decode_base64(data)
            
            elif mime_type == 'text/html' and not body_html:
                data = part.get('body', {}).get('data', '')
                if data:
                    body_html = self._decode_base64(data)
            
            # Handle attachments
            elif part.get('filename'):
                attachment_data = {
                    'filename': part['filename'],
                    'mime_type': mime_type,
                    'size_bytes': part.get('body', {}).get('size', 0),
                    'attachment_id': part.get('body', {}).get('attachmentId'),
                    'part_id': part.get('partId')
                }
                attachments.append(attachment_data)
        
        process_part(payload)
        return body_plain, body_html, attachments
    
    def _decode_base64(self, data: str) -> str:
        """Decode base64 encoded data"""
        try:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        except Exception as e:
            self.logger.error(f"Error decoding base64: {e}")
            return ""
    
    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to Markdown"""
        try:
            # Clean HTML first
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove tracking pixels and external images
            for img in soup.find_all('img'):
                if img.get('width') == '1' or img.get('height') == '1':
                    img.decompose()
            
            # Convert to markdown
            markdown = self.html_converter.handle(str(soup))
            
            return markdown.strip()
        except Exception as e:
            self.logger.error(f"Error converting HTML to Markdown: {e}")
            return html