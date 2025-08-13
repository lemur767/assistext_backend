import re
from functools import wraps
from flask import request, jsonify
from marshmallow import ValidationError

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone_number(phone):
    """Validate phone number format"""
    # Remove all non-digit characters
    digits_only = re.sub(r'[^\d]', '', phone)
    
    # Check if it's a valid North American number
    if len(digits_only) == 10:
        return True
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        return True
    elif phone.startswith('+1') and len(digits_only) == 11:
        return True
    
    return False

def normalize_phone_number(phone):
    """Normalize phone number to E.164 format"""
    if not phone:
        return None
    
    # Remove all non-digit characters
    digits_only = re.sub(r'[^\d]', '', phone)
    
    # Add country code if missing
    if len(digits_only) == 10:
        return f'+1{digits_only}'
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        return f'+{digits_only}'
    elif phone.startswith('+'):
        return phone
    
    return phone

def sanitize_string(text, max_length=None):
    """Sanitize text input"""
    if not text:
        return None
    
    # Strip whitespace
    text = text.strip()
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Truncate if necessary
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text

def validate_request_json(schema):
    """Decorator to validate JSON request data"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                if not request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Content-Type must be application/json'
                    }), 400
                
                json_data = request.get_json()
                if json_data is None:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid JSON'
                    }), 400
                
                # Validate with schema
                validated_data = schema.load(json_data)
                
                # Replace request data with validated data
                request.validated_data = validated_data
                
                return f(*args, **kwargs)
                
            except ValidationError as e:
                return jsonify({
                    'success': False,
                    'error': 'Validation failed',
                    'errors': e.messages
                }), 400
                
        return decorated_function
    return decorator
