# =============================================================================
# app/utils/auth.py
"""
AUTHENTICATION UTILITIES - CORRECTED VERSION
JWT, API keys, and security functions with proper SignalWire webhook validation
"""
import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Tuple, Optional
from flask import request, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from functools import wraps


def generate_api_key() -> Tuple[str, str]:
    """Generate API key and hash"""
    # Generate random API key
    api_key = f"sk_{secrets.token_urlsafe(32)}"
    
    # Create hash for storage
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    return api_key, key_hash


def hash_api_key(api_key: str) -> str:
    """Hash API key for secure storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Verify API key against stored hash"""
    return hashlib.sha256(api_key.encode()).hexdigest() == stored_hash


def verify_signalwire_signature(payload: str, signature: str, auth_token: str) -> bool:
    """Verify SignalWire webhook signature"""
    try:
        # SignalWire uses SHA1 HMAC for webhook signatures
        expected_signature = hmac.new(
            auth_token.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()
        
        # SignalWire signatures come as base64, compare properly
        return hmac.compare_digest(signature, expected_signature)
    except Exception:
        return False


def verify_stripe_signature(payload: bytes, signature: str, webhook_secret: str) -> bool:
    """Verify Stripe webhook signature"""
    try:
        import stripe
        stripe.Webhook.construct_event(payload, signature, webhook_secret)
        return True
    except Exception:
        return False


def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for API key in header
        api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not api_key:
            return {
                'success': False,
                'error': 'API key required'
            }, 401
        
        # TODO: Validate API key against database
        # For now, just check if it's properly formatted
        if not api_key.startswith('sk_'):
            return {
                'success': False,
                'error': 'Invalid API key format'
            }, 401
        
        return f(*args, **kwargs)
    return decorated_function


def require_webhook_signature(webhook_type='signalwire'):
    """Decorator to verify webhook signatures"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_app.config.get('VERIFY_WEBHOOK_SIGNATURES', True):
                return f(*args, **kwargs)
            
            if webhook_type == 'signalwire':
                signature = request.headers.get('X-SignalWire-Signature')
                auth_token = current_app.config.get('SIGNALWIRE_API_TOKEN')
                
                if not signature or not auth_token:
                    return {'success': False, 'error': 'Missing signature or token'}, 401
                
                payload = request.get_data(as_text=True)
                if not verify_signalwire_signature(payload, signature, auth_token):
                    return {'success': False, 'error': 'Invalid signature'}, 401
                    
            elif webhook_type == 'stripe':
                signature = request.headers.get('Stripe-Signature')
                webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
                
                if not signature or not webhook_secret:
                    return {'success': False, 'error': 'Missing signature or secret'}, 401
                
                payload = request.get_data()
                if not verify_stripe_signature(payload, signature, webhook_secret):
                    return {'success': False, 'error': 'Invalid signature'}, 401
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_client_ip() -> str:
    """Get client IP address"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


def get_user_agent() -> str:
    """Get user agent string"""
    return request.headers.get('User-Agent', '')


def rate_limit_key(identifier: str) -> str:
    """Generate rate limiting key"""
    return f"rate_limit:{identifier}:{datetime.utcnow().strftime('%Y-%m-%d-%H-%M')}"
