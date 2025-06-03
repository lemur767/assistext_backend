# app/utils/cors_middleware.py - Custom CORS middleware for additional control

from flask import request, make_response, current_app
from functools import wraps

def handle_cors():
    """
    Custom CORS handler for complex scenarios
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Handle preflight requests
            if request.method == 'OPTIONS':
                return handle_preflight_request()
            
            # Handle actual requests
            response = make_response(f(*args, **kwargs))
            return add_cors_headers(response)
        
        return decorated_function
    return decorator

def handle_preflight_request():
    """
    Handle CORS preflight requests
    """
    origin = request.headers.get('Origin')
    
    if not is_origin_allowed(origin):
        return make_response('', 403)
    
    response = make_response('', 200)
    response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
    response.headers['Access-Control-Allow-Headers'] = (
        'Content-Type, Authorization, X-Requested-With, Accept, Origin, X-CSRF-Token'
    )
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Max-Age'] = '86400'  # 24 hours
    
    return response

def add_cors_headers(response):
    """
    Add CORS headers to response
    """
    origin = request.headers.get('Origin')
    
    if is_origin_allowed(origin):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Range, X-Content-Range'
    
    return response

def is_origin_allowed(origin):
    """
    Check if origin is in allowed list
    """
    if not origin:
        return False
    
    allowed_origins = current_app.config.get('CORS_ORIGINS', [])
    
    # For development, allow localhost variations
    if current_app.config.get('DEBUG'):
        localhost_patterns = [
            'http://localhost',
            'http://127.0.0.1',
            'https://localhost',
            'https://127.0.0.1'
        ]
        
        for pattern in localhost_patterns:
            if origin.startswith(pattern):
                return True
    
    return origin in allowed_origins

# Decorator for API endpoints that need special CORS handling
def cors_enabled(f):
    """
    Decorator to enable CORS on specific endpoints
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'OPTIONS':
            return handle_preflight_request()
        
        response = make_response(f(*args, **kwargs))
        return add_cors_headers(response)
    
    return decorated_function