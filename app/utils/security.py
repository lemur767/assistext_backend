from flask import request, jsonify
from functools import wraps
from datetime import datetime, timedelta
import redis
import hashlib

# Initialize Redis for rate limiting
redis_client = None

def init_redis(app):
    """Initialize Redis connection"""
    global redis_client
    redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
    try:
        redis_client = redis.from_url(redis_url)
        redis_client.ping()
        app.logger.info("Redis connection established")
    except Exception as e:
        app.logger.error(f"Redis connection failed: {str(e)}")
        redis_client = None

def rate_limit(requests_per_minute=60):
    """Rate limiting decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not redis_client:
                # Skip rate limiting if Redis unavailable
                return f(*args, **kwargs)
            
            # Get client identifier
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            endpoint = request.endpoint
            
            # Create rate limit key
            minute = datetime.utcnow().strftime('%Y-%m-%d-%H-%M')
            key = f"rate_limit:{client_ip}:{endpoint}:{minute}"
            
            try:
                # Increment counter
                current_requests = redis_client.incr(key)
                
                # Set expiration on first request
                if current_requests == 1:
                    redis_client.expire(key, 60)
                
                # Check if limit exceeded
                if current_requests > requests_per_minute:
                    return jsonify({
                        'success': False,
                        'error': 'Rate limit exceeded'
                    }), 429
                
            except Exception as e:
                # Log error but don't block request
                app.logger.error(f"Rate limiting error: {str(e)}")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def generate_api_key(user_id):
    """Generate API key for user"""
    import secrets
    import time
    
    timestamp = str(int(time.time()))
    random_part = secrets.token_urlsafe(32)
    
    # Create hash
    key_string = f"{user_id}:{timestamp}:{random_part}"
    api_key = hashlib.sha256(key_string.encode()).hexdigest()
    
    return f"ak_{api_key[:32]}"