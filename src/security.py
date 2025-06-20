import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import base64

try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    logging.warning("python-magic not available, using mimetypes fallback")

try:
    import pyclamd
    HAS_CLAMAV = True
except ImportError:
    HAS_CLAMAV = False
    logging.warning("pyclamd not available, virus scanning disabled")

from .config import config

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Validate and scan attachments for security threats"""
    
    def __init__(self):
        self.allowed_mime_types = set(config.ALLOWED_MIME_TYPES)
        self.max_size_bytes = config.MAX_ATTACHMENT_SIZE_BYTES
        
        # Initialize magic for MIME type detection
        if HAS_MAGIC:
            self.magic = magic.Magic(mime=True)
        else:
            self.magic = None
        
        # Initialize ClamAV if enabled
        self.clamav = None
        if config.ENABLE_CLAMAV and HAS_CLAMAV:
            try:
                self.clamav = pyclamd.ClamdNetworkSocket(
                    host=config.CLAMAV_HOST,
                    port=config.CLAMAV_PORT
                )
                if self.clamav.ping():
                    logger.info("ClamAV connection successful")
                else:
                    logger.error("ClamAV ping failed")
                    self.clamav = None
            except Exception as e:
                logger.error(f"Failed to connect to ClamAV: {e}")
                self.clamav = None
    
    def validate_attachment(self, 
                          filename: str,
                          data: bytes,
                          declared_mime_type: Optional[str] = None) -> Dict[str, Any]:
        """Validate attachment and return security report"""
        report = {
            'filename': filename,
            'size_bytes': len(data),
            'declared_mime_type': declared_mime_type,
            'detected_mime_type': None,
            'content_hash': self._calculate_hash(data),
            'is_safe': True,
            'issues': [],
            'scan_results': {}
        }
        
        # Check file size
        if len(data) > self.max_size_bytes:
            report['is_safe'] = False
            report['issues'].append(f"File too large: {len(data)} bytes (max: {self.max_size_bytes})")
        
        # Detect actual MIME type
        detected_mime = self._detect_mime_type(data, filename)
        report['detected_mime_type'] = detected_mime
        
        # Check for MIME type mismatch
        if declared_mime_type and detected_mime:
            if declared_mime_type != detected_mime:
                report['issues'].append(
                    f"MIME type mismatch: declared={declared_mime_type}, detected={detected_mime}"
                )
        
        # Check if MIME type is allowed
        mime_to_check = detected_mime or declared_mime_type
        if mime_to_check and mime_to_check not in self.allowed_mime_types:
            report['is_safe'] = False
            report['issues'].append(f"MIME type not allowed: {mime_to_check}")
        
        # Check file extension
        extension = Path(filename).suffix.lower()
        if self._is_dangerous_extension(extension):
            report['is_safe'] = False
            report['issues'].append(f"Dangerous file extension: {extension}")
        
        # Virus scan if available
        if self.clamav and report['is_safe']:  # Only scan if passed other checks
            scan_result = self._scan_with_clamav(data)
            report['scan_results']['clamav'] = scan_result
            
            if scan_result['infected']:
                report['is_safe'] = False
                report['issues'].append(f"Virus detected: {scan_result['virus_name']}")
        
        return report
    
    def _calculate_hash(self, data: bytes) -> str:
        """Calculate SHA-256 hash of data"""
        return hashlib.sha256(data).hexdigest()
    
    def _detect_mime_type(self, data: bytes, filename: str) -> Optional[str]:
        """Detect MIME type from file content"""
        # Try magic first
        if self.magic:
            try:
                return self.magic.from_buffer(data)
            except Exception as e:
                logger.error(f"Magic MIME detection failed: {e}")
        
        # Fallback to mimetypes
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type
    
    def _is_dangerous_extension(self, extension: str) -> bool:
        """Check if file extension is potentially dangerous"""
        dangerous_extensions = {
            '.exe', '.com', '.bat', '.cmd', '.scr', '.vbs', '.vbe',
            '.js', '.jse', '.wsf', '.wsh', '.msi', '.jar', '.app',
            '.dmg', '.pkg', '.deb', '.rpm', '.sh', '.bash', '.ps1',
            '.psm1', '.reg', '.dll', '.so', '.dylib'
        }
        
        return extension in dangerous_extensions
    
    def _scan_with_clamav(self, data: bytes) -> Dict[str, Any]:
        """Scan data with ClamAV"""
        if not self.clamav:
            return {'scanned': False, 'infected': False, 'error': 'ClamAV not available'}
        
        try:
            # ClamAV expects the data as a stream
            result = self.clamav.instream(data)
            
            if result and 'stream' in result:
                status = result['stream']
                if status[0] == 'OK':
                    return {
                        'scanned': True,
                        'infected': False,
                        'status': 'clean'
                    }
                elif status[0] == 'FOUND':
                    return {
                        'scanned': True,
                        'infected': True,
                        'virus_name': status[1],
                        'status': 'infected'
                    }
            
            return {
                'scanned': True,
                'infected': False,
                'status': 'unknown',
                'result': str(result)
            }
        
        except Exception as e:
            logger.error(f"ClamAV scan failed: {e}")
            return {
                'scanned': False,
                'infected': False,
                'error': str(e)
            }
    
    def validate_email_content(self, content: str) -> Dict[str, Any]:
        """Validate email content for security issues"""
        report = {
            'has_suspicious_content': False,
            'issues': []
        }
        
        # Check for suspicious patterns
        suspicious_patterns = [
            # Executable file references
            r'\.exe\s*$',
            r'\.bat\s*$',
            r'\.cmd\s*$',
            r'\.scr\s*$',
            # Script tags
            r'<script[^>]*>',
            r'javascript:',
            r'vbscript:',
            # Common phishing patterns
            r'verify.{0,20}account',
            r'suspended.{0,20}account',
            r'click.{0,20}here.{0,20}immediately',
        ]
        
        import re
        content_lower = content.lower()
        
        for pattern in suspicious_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                report['has_suspicious_content'] = True
                report['issues'].append(f"Suspicious pattern found: {pattern}")
        
        return report
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove path components
        filename = Path(filename).name
        
        # Replace dangerous characters
        safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_')
        sanitized = ''.join(c if c in safe_chars else '_' for c in filename)
        
        # Ensure it has a safe extension
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        
        if not ext or self._is_dangerous_extension(ext.lower()):
            ext = '.txt'
        
        return f"{name}{ext}"
    
    def encode_attachment_safe(self, data: bytes) -> str:
        """Safely encode attachment data as base64"""
        return base64.b64encode(data).decode('ascii')
    
    def decode_attachment_safe(self, encoded: str) -> bytes:
        """Safely decode base64 attachment data"""
        try:
            return base64.b64decode(encoded)
        except Exception as e:
            logger.error(f"Failed to decode attachment: {e}")
            raise ValueError("Invalid base64 data")


# Global security validator instance
security_validator = SecurityValidator()