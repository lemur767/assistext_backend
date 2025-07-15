"""
Security utilities for the SMS AI Responder application.
Provides authentication, encryption, validation, and protection mechanisms.
"""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import string
import time
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
import jwt
from flask import current_app, request, g, jsonify
from werkzeug.local import LocalProxy

# Initialize Redis client for token blacklist and rate limiting
# This will be initialized in init_app
redis_client = None

def init_app(app):
    """Initialize security module with Flask app context"""
    global redis_client
    
    # Initialize Redis if configured
    if app.config.get('REDIS_URL'):
        import redis
        redis_client = redis.from_url(app.config.get('REDIS_URL'))
    
    # Register API key middleware if needed
    if app.config.get('USE_API_KEY_AUTH', False):
        @app.before_request
        def check_api_key():
            # Skip for routes that don't need API key
            if request.endpoint and request.endpoint.startswith('api.public'):
                return
            
            # Skip for authentication routes
            if request.endpoint and request.endpoint.startswith('auth.'):
                return
                
            # Check for API key in headers or query params
            api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
            if not api_key:
                return
                
            # Validate API key
            key_info = validate_api_key(api_key)
            if key_info:
                g.api_key = api_key
                g.api_key_info = key_info


# Token Management Functions

def generate_token(user_id, expiration=3600, additional_claims=None):
    """
    Generate a JWT token for a user.
    
    Args:
        user_id: User identifier
        expiration: Token lifetime in seconds
        additional_claims: Dictionary of additional JWT claims
        
    Returns:
        str: JWT token
    """
    payload = {
        'sub': user_id,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(seconds=expiration),
        'jti': secrets.token_hex(16)  # Unique token ID for revocation
    }
    
    # Add any additional claims
    if additional_claims:
        payload.update(additional_claims)
    
    # Create token
    token = jwt.encode(
        payload,
        current_app.config.get('JWT_SECRET_KEY'),
        algorithm='HS256'
    )
    
    return token


def verify_token(token):
    """
    Verify a JWT token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        dict: Token payload if valid, None otherwise
    """
    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            current_app.config.get('JWT_SECRET_KEY'),
            algorithms=['HS256']
        )
        
        # Check if token has been revoked
        if redis_client and redis_client.get(f"revoked_token:{payload['jti']}"):
            return None
        
        return payload
    except jwt.ExpiredSignatureError:
        # Token has expired
        return None
    except jwt.InvalidTokenError:
        # Token is invalid
        return None


def revoke_token(token):
    """
    Revoke a JWT token by adding it to a blacklist.
    
    Args:
        token: JWT token to revoke
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Decode token without verification to get jti
        payload = jwt.decode(
            token,
            options={"verify_signature": False}
        )
        
        token_jti = payload.get('jti')
        if not token_jti:
            return False
        
        # Calculate time until token expiration
        expiration = datetime.fromtimestamp(payload.get('exp')) - datetime.utcnow()
        ttl = max(1, int(expiration.total_seconds()))
        
        # Add to blacklist with expiration
        if redis_client:
            redis_client.setex(f"revoked_token:{token_jti}", ttl, 1)
            return True
        else:
            # Fallback if Redis isn't available
            # This is less optimal as the revocation won't persist across app restarts
            if not hasattr(g, 'revoked_tokens'):
                g.revoked_tokens = set()
            g.revoked_tokens.add(token_jti)
            return True
    except Exception:
        return False


# Password Management Functions

def hash_password(password):
    """
    Hash a password securely using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password, password_hash):
    """
    Verify a password against its hash.
    
    Args:
        password: Plain text password
        password_hash: Stored password hash
        
    Returns:
        bool: True if password matches, False otherwise
    """
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def validate_password_strength(password):
    """
    Check if a password meets strength requirements.
    
    Args:
        password: Password to check
        
    Returns:
        tuple: (bool, str) - (is_valid, reason_if_invalid)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    # Check for at least one lowercase letter
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for at least one digit
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    # Check for at least one special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, ""


# API Key Management Functions

def generate_api_key():
    """
    Generate a new API key.
    
    Returns:
        str: Newly generated API key
    """
    # Generate a random string for the API key
    # Format: prefix_random_string
    prefix = "sk"
    random_part = secrets.token_hex(16)
    api_key = f"{prefix}_{random_part}"
    
    return api_key


def validate_api_key(api_key):
    """
    Validate an API key.
    
    Args:
        api_key: API key to validate
        
    Returns:
        dict: API key information if valid, None otherwise
    """
    from app.models.api_key import APIKey
    
    if not api_key:
        return None
    
    # Check against database
    key_record = APIKey.query.filter_by(key_hash=_hash_api_key(api_key)).first()
    
    if not key_record:
        return None
    
    # Check if key is active
    if not key_record.is_active:
        return None
    
    # Check if key has expired
    if key_record.expires_at and key_record.expires_at < datetime.utcnow():
        return None
    
    # Return key info
    return {
        "id": key_record.id,
        "user_id": key_record.user_id,
        "name": key_record.name,
        "permissions": key_record.permissions,
        "created_at": key_record.created_at
    }


def revoke_api_key(api_key):
    """
    Revoke an API key.
    
    Args:
        api_key: API key to revoke
        
    Returns:
        bool: True if successful, False otherwise
    """
    from app.models.api_key import APIKey
    from app.extensions import db
    
    # Find key record
    key_record = APIKey.query.filter_by(key_hash=_hash_api_key(api_key)).first()
    
    if not key_record:
        return False
    
    # Deactivate key
    key_record.is_active = False
    key_record.revoked_at = datetime.utcnow()
    
    try:
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False


def get_api_key_info(api_key):
    """
    Get information about an API key.
    
    Args:
        api_key: API key to get information for
        
    Returns:
        dict: API key information if found, None otherwise
    """
    # Use validate_api_key to get info
    return validate_api_key(api_key)


def _hash_api_key(api_key):
    """
    Hash an API key for secure storage.
    
    Args:
        api_key: API key to hash
        
    Returns:
        str: Hashed API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def require_api_key(f):
    """
    Decorator for routes that require an API key.
    
    Args:
        f: Function to decorate
        
    Returns:
        decorated function
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get API key from header or query parameter
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not api_key:
            return jsonify({"error": "API key required"}), 401
        
        # Validate API key
        key_info = validate_api_key(api_key)
        if not key_info:
            return jsonify({"error": "Invalid API key"}), 401
        
        # Store key info for the view function
        g.api_key = api_key
        g.api_key_info = key_info
        
        return f(*args, **kwargs)
    
    return decorated


# Validation Functions

def validate_email_address(email):
    """
    Validate an email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Simple regex for email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    return bool(re.match(pattern, email))


def validate_phone_number(phone_number):
    """
    Validate a phone number format (E.164).
    
    Args:
        phone_number: Phone number to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Regex for E.164 format (e.g., +12125551234)
    pattern = r'^\+[1-9]\d{1,14}$'
    
    return bool(re.match(pattern, phone_number))


def sanitize_input(text):
    """
    Sanitize user input to prevent injection attacks.
    
    Args:
        text: Input to sanitize
        
    Returns:
        str: Sanitized input
    """
    if not text:
        return ""
    
    # Remove potentially dangerous patterns
    sanitized = re.sub(r'[<>\'";]', '', text)
    
    return sanitized


def mask_sensitive_data(data, field_type=None):
    """
    Mask sensitive data like credit card numbers, SSNs, etc.
    
    Args:
        data: Data to mask
        field_type: Type of field (card, ssn, phone, etc.)
        
    Returns:
        str: Masked data
    """
    if not data:
        return ""
    
    if field_type == "card":
        # Mask credit card number (show only last 4 digits)
        return re.sub(r'\d(?=\d{4})', '*', data)
    
    elif field_type == "ssn":
        # Mask SSN (show only last 4 digits)
        return re.sub(r'\d(?=\d{4})', '*', data)
    
    elif field_type == "phone":
        # Mask phone number (show only last 4 digits)
        return re.sub(r'\d(?=\d{4})', '*', data)
    
    else:
        # Default masking for unknown types (mask middle portion)
        if len(data) <= 4:
            return data
        
        visible_start = min(4, len(data) // 4)
        visible_end = min(4, len(data) // 4)
        masked_length = len(data) - visible_start - visible_end
        
        return data[:visible_start] + '*' * masked_length + data[-visible_end:]


# Utility Functions

def generate_secure_key(length=32):
    """
    Generate a cryptographically secure random key.
    
    Args:
        length: Length of key in bytes
        
    Returns:
        str: Base64-encoded key
    """
    random_bytes = os.urandom(length)
    return base64.urlsafe_b64encode(random_bytes).decode('utf-8')


def generate_verification_code(length=6):
    """
    Generate a numeric verification code.
    
    Args:
        length: Code length
        
    Returns:
        str: Verification code
    """
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def secure_compare(a, b):
    """
    Compare two strings in a timing-safe manner.
    
    Args:
        a: First string
        b: Second string
        
    Returns:
        bool: True if equal, False otherwise
    """
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def rate_limit(key, limit, period):
    """
    Implement rate limiting.
    
    Args:
        key: Rate limit key (e.g., user_id or IP)
        limit: Maximum number of requests
        period: Time period in seconds
        
    Returns:
        tuple: (bool, dict) - (is_allowed, rate_limit_info)
    """
    if not redis_client:
        # No rate limiting if Redis is not available
        return True, {"limit": limit, "remaining": limit, "reset": int(time.time()) + period}
    
    current = int(time.time())
    reset_time = current - (current % period) + period
    window_key = f"ratelimit:{key}:{reset_time}"
    
    # Get current count
    count = redis_client.get(window_key)
    count = int(count) if count else 0
    
    # Check if limit exceeded
    if count >= limit:
        return False, {
            "limit": limit,
            "remaining": 0, 
            "reset": reset_time,
            "retry_after": reset_time - current
        }
    
    # Increment count and set expiration
    pipeline = redis_client.pipeline()
    pipeline.incr(window_key)
    pipeline.expire(window_key, period)
    pipeline.execute()
    
    return True, {
        "limit": limit,
        "remaining": limit - (count + 1),
        "reset": reset_time
    }


def log_security_event(event_type, details, user_id=None, ip_address=None):
    """
    Log a security-related event.
    
    Args:
        event_type: Type of security event
        details: Event details
        user_id: User ID if applicable
        ip_address: IP address if applicable
        
    Returns:
        bool: True if logged successfully, False otherwise
    """
    from app.models.security_log import SecurityLog
    from app.extensions import db
    
    # Get IP address if not provided
    if not ip_address:
        ip_address = request.remote_addr
    
    # Create log entry
    log_entry = SecurityLog(
        event_type=event_type,
        details=json.dumps(details) if isinstance(details, dict) else str(details),
        user_id=user_id,
        ip_address=ip_address,
        timestamp=datetime.utcnow()
    )
    
    try:
        db.session.add(log_entry)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False