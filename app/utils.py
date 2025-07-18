import re
import hashlib
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def sanitize_email(email: str) -> str:
    """Sanitize email addresses in logs by masking the local part."""
    if not email or '@' not in email:
        return email
    
    local_part, domain = email.split('@', 1)
    if len(local_part) <= 2:
        return f"*@{domain}"
    else:
        masked_local = local_part[0] + '*' * (len(local_part) - 2) + local_part[-1]
        return f"{masked_local}@{domain}"


def sanitize_url(url: str, mask_query_params: Optional[List[str]] = None) -> str:
    """Sanitize URLs by masking sensitive query parameters and credentials."""
    if not url:
        return url
    
    try:
        parsed = urlparse(url)
        
        # Mask username/password in netloc
        if '@' in parsed.netloc:
            auth, host = parsed.netloc.split('@', 1)
            if ':' in auth:
                username, password = auth.split(':', 1)
                masked_auth = f"{username}:***"
            else:
                masked_auth = f"{auth}:***"
            masked_netloc = f"{masked_auth}@{host}"
        else:
            masked_netloc = parsed.netloc
        
        # Mask sensitive query parameters
        if parsed.query:
            query_params = parse_qs(parsed.query)
            sensitive_params = mask_query_params or ['code', 'state', 'token', 'access_token', 'id_token', 'refresh_token']
            
            for param in sensitive_params:
                if param in query_params:
                    query_params[param] = ['***']
            
            masked_query = urlencode(query_params, doseq=True)
        else:
            masked_query = parsed.query
        
        # Reconstruct URL
        sanitized = urlunparse((
            parsed.scheme,
            masked_netloc,
            parsed.path,
            parsed.params,
            masked_query,
            parsed.fragment
        ))
        
        return sanitized
    except Exception:
        # If URL parsing fails, return a generic masked version
        return "***"


def sanitize_database_url(url: str) -> str:
    """Sanitize database URLs by masking credentials."""
    if not url:
        return url
    
    try:
        parsed = urlparse(url)
        
        # Mask username/password in netloc
        if '@' in parsed.netloc:
            auth, host = parsed.netloc.split('@', 1)
            if ':' in auth:
                username, password = auth.split(':', 1)
                masked_auth = f"{username}:***"
            else:
                masked_auth = f"{auth}:***"
            masked_netloc = f"{masked_auth}@{host}"
        else:
            masked_netloc = parsed.netloc
        
        # Reconstruct URL
        sanitized = urlunparse((
            parsed.scheme,
            masked_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        return sanitized
    except Exception:
        # If URL parsing fails, return a generic masked version
        return "***"


def sanitize_token(token: str) -> str:
    """Sanitize tokens by showing only first and last few characters."""
    if not token:
        return token
    
    if len(token) <= 8:
        return "***"
    else:
        return f"{token[:4]}...{token[-4:]}"


def sanitize_environment_variables(env_dict: Dict[str, str], sensitive_keys: Optional[List[str]] = None) -> Dict[str, str]:
    """Sanitize environment variables by masking sensitive values."""
    if not env_dict:
        return env_dict
    
    default_sensitive = [
        'DB_PASSWORD', 'DATABASE_URL', 'OAUTH2_CLIENT_SECRET', 
        'SECRET_KEY', 'API_KEY', 'TOKEN', 'PASSWORD'
    ]
    sensitive_keys = sensitive_keys or default_sensitive
    
    sanitized = {}
    for key, value in env_dict.items():
        if any(sensitive in key.upper() for sensitive in sensitive_keys):
            if 'URL' in key.upper() and value:
                sanitized[key] = sanitize_database_url(value)
            else:
                sanitized[key] = "***"
        else:
            sanitized[key] = value
    
    return sanitized


def sanitize_log_message(message: str) -> str:
    """Sanitize log messages by masking common sensitive patterns."""
    if not message:
        return message
    
    # Mask email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    message = re.sub(email_pattern, lambda m: sanitize_email(m.group()), message)
    
    # Mask tokens (JWT-like patterns)
    token_pattern = r'\b[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b'
    message = re.sub(token_pattern, lambda m: sanitize_token(m.group()), message)
    
    # Mask database URLs
    db_url_pattern = r'(?:mysql|postgresql|sqlite)(?:\+[a-z]+)?://[^\s]+'
    message = re.sub(db_url_pattern, lambda m: sanitize_database_url(m.group()), message)
    
    return message


class SanitizedLogger:
    """A logger wrapper that automatically sanitizes sensitive information."""
    
    def __init__(self, logger):
        self.logger = logger
    
    def debug(self, message: str, *args, **kwargs):
        sanitized_message = sanitize_log_message(message)
        self.logger.debug(sanitized_message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        sanitized_message = sanitize_log_message(message)
        self.logger.info(sanitized_message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        sanitized_message = sanitize_log_message(message)
        self.logger.warning(sanitized_message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        sanitized_message = sanitize_log_message(message)
        self.logger.error(sanitized_message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        sanitized_message = sanitize_log_message(message)
        self.logger.critical(sanitized_message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        sanitized_message = sanitize_log_message(message)
        self.logger.exception(sanitized_message, *args, **kwargs) 