import os
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import base64
import re
import logging

from .config import config

logger = logging.getLogger(__name__)


class MarkdownStorage:
    """Store emails and attachments as markdown files with base64 attachments"""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or config.MARKDOWN_STORAGE_PATH
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_path / "index.json"
        self._load_index()
    
    def _load_index(self):
        """Load or create index file"""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
        else:
            self.index = {"emails": {}, "last_updated": None}
    
    def _save_index(self):
        """Save index file"""
        self.index["last_updated"] = datetime.now().isoformat()
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def _sanitize_filename(self, text: str, max_length: int = 50) -> str:
        """Sanitize text for use in filename"""
        # Remove special characters
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        # Replace spaces with hyphens
        text = re.sub(r'\s+', '-', text)
        # Remove multiple hyphens
        text = re.sub(r'-+', '-', text)
        # Trim and convert to lowercase
        text = text.strip('-').lower()[:max_length]
        
        return text or "untitled"
    
    def _get_email_path(self, email_data: Dict[str, Any]) -> Path:
        """Generate path for email markdown file"""
        date = email_data.get('date') or datetime.now()
        
        # Create year/month directory structure
        year_month_path = self.base_path / str(date.year) / f"{date.month:02d}"
        year_month_path.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        timestamp = date.strftime("%Y%m%d_%H%M%S")
        subject_slug = self._sanitize_filename(email_data.get('subject', 'untitled'))
        filename = f"{timestamp}_{subject_slug}.md"
        
        return year_month_path / filename
    
    def save_email(self, email_data: Dict[str, Any], attachments_data: List[Dict[str, Any]] = None) -> str:
        """Save email as markdown with attachments"""
        # Get email path
        email_path = self._get_email_path(email_data)
        
        # Create attachments directory if needed
        attachment_dir = None
        if attachments_data:
            attachment_dir = email_path.parent / email_path.stem
            attachment_dir.mkdir(parents=True, exist_ok=True)
        
        # Build frontmatter
        frontmatter = {
            'id': email_data['message_id'],
            'thread_id': email_data.get('thread_id'),
            'subject': email_data.get('subject'),
            'from': email_data.get('sender'),
            'from_name': email_data.get('sender_name'),
            'to': email_data.get('recipients', []),
            'cc': email_data.get('cc_recipients', []),
            'bcc': email_data.get('bcc_recipients', []),
            'date': email_data['date'].isoformat() if email_data.get('date') else None,
            'labels': email_data.get('labels', []),
            'attachments': []
        }
        
        # Process attachments
        if attachments_data:
            for att in attachments_data:
                # Save attachment as base64
                att_filename = f"{att['filename']}.base64"
                att_path = attachment_dir / att_filename
                
                # Save base64 encoded file
                with open(att_path, 'w') as f:
                    f.write(att['data_base64'])
                
                # Add to frontmatter
                frontmatter['attachments'].append({
                    'filename': att['filename'],
                    'mime_type': att.get('mime_type'),
                    'size': att.get('size_bytes'),
                    'hash': att.get('content_hash'),
                    'safe': att.get('is_safe'),
                    'path': f"./{email_path.stem}/{att_filename}"
                })
        
        # Build markdown content
        markdown_content = self._build_markdown(email_data, frontmatter)
        
        # Save markdown file
        with open(email_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # Update index
        self.index['emails'][email_data['message_id']] = {
            'path': str(email_path.relative_to(self.base_path)),
            'subject': email_data.get('subject'),
            'sender': email_data.get('sender'),
            'date': email_data['date'].isoformat() if email_data.get('date') else None,
            'has_attachments': len(frontmatter['attachments']) > 0
        }
        self._save_index()
        
        logger.info(f"Saved email to: {email_path}")
        return str(email_path.relative_to(self.base_path))
    
    def _build_markdown(self, email_data: Dict[str, Any], frontmatter: Dict[str, Any]) -> str:
        """Build markdown content for email"""
        lines = []
        
        # Add frontmatter
        lines.append("---")
        lines.append(yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True).strip())
        lines.append("---")
        lines.append("")
        
        # Add title
        subject = email_data.get('subject', '(No Subject)')
        lines.append(f"# {subject}")
        lines.append("")
        
        # Add metadata section
        lines.append(f"**From:** {email_data.get('sender_name', '')} <{email_data.get('sender', '')}>  ")
        
        if email_data.get('recipients'):
            recipients = ', '.join(email_data['recipients'])
            lines.append(f"**To:** {recipients}  ")
        
        if email_data.get('cc_recipients'):
            cc = ', '.join(email_data['cc_recipients'])
            lines.append(f"**Cc:** {cc}  ")
        
        if email_data.get('date'):
            date_str = email_data['date'].strftime("%B %d, %Y at %I:%M %p")
            lines.append(f"**Date:** {date_str}  ")
        
        lines.append("")
        
        # Add content
        lines.append("## Content")
        lines.append("")
        
        content = email_data.get('body_markdown') or email_data.get('body_plain', '')
        if content:
            lines.append(content)
        else:
            lines.append("*(No content)*")
        
        lines.append("")
        
        # Add attachments section if present
        if frontmatter['attachments']:
            lines.append("## Attachments")
            lines.append("")
            
            for att in frontmatter['attachments']:
                size_mb = att['size'] / (1024 * 1024) if att.get('size') else 0
                safe_indicator = "✓" if att.get('safe') else "⚠️" if att.get('safe') is False else "?"
                lines.append(f"- [{att['filename']}]({att['path']}) ({size_mb:.1f} MB) {safe_indicator}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def load_email(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Load email from markdown file"""
        if message_id not in self.index['emails']:
            return None
        
        email_info = self.index['emails'][message_id]
        email_path = self.base_path / email_info['path']
        
        if not email_path.exists():
            logger.error(f"Email file not found: {email_path}")
            return None
        
        with open(email_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                markdown_content = parts[2].strip()
            else:
                frontmatter = {}
                markdown_content = content
        else:
            frontmatter = {}
            markdown_content = content
        
        return {
            'frontmatter': frontmatter,
            'content': markdown_content,
            'path': str(email_path)
        }
    
    def load_attachment(self, attachment_path: str) -> Optional[bytes]:
        """Load attachment from base64 file"""
        full_path = self.base_path / attachment_path
        
        if not full_path.exists():
            logger.error(f"Attachment not found: {full_path}")
            return None
        
        with open(full_path, 'r') as f:
            base64_data = f.read()
        
        return base64.b64decode(base64_data)
    
    def search_by_date(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Search emails by date range"""
        results = []
        
        for message_id, info in self.index['emails'].items():
            if info.get('date'):
                email_date = datetime.fromisoformat(info['date'])
                if start_date <= email_date <= end_date:
                    results.append({
                        'message_id': message_id,
                        **info
                    })
        
        return sorted(results, key=lambda x: x.get('date', ''), reverse=True)
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        total_emails = len(self.index['emails'])
        emails_with_attachments = sum(
            1 for info in self.index['emails'].values() 
            if info.get('has_attachments')
        )
        
        # Calculate storage size
        total_size = 0
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                file_path = Path(root) / file
                total_size += file_path.stat().st_size
        
        return {
            'total_emails': total_emails,
            'emails_with_attachments': emails_with_attachments,
            'total_size_mb': total_size / (1024 * 1024),
            'last_updated': self.index.get('last_updated')
        }