# app/utils/__init__.py
"""
Utils package for Escort SMS AI Responder

This package provides utility functions for security, communication APIs, and other
common operations. By importing commonly used functions in this __init__.py file,
we make them easily accessible throughout the application.

Usage examples:
    from utils import hash_password, generate_token
    from utils import send_sms, validate_twilio_request
    from utils.openai_helpers import generate_ai_response
"""

# Import commonly used security functions for easy access
# These are the functions most likely to be used throughout the application
from .security import (
    # Token and authentication functions
    generate_token,
    verify_token,
    revoke_token,
    
    # Password handling
    hash_password,
    verify_password,
    
    # API key management
    generate_api_key,
    validate_api_key,
    revoke_api_key,
    get_api_key_info,
    
    # Security validation functions
    validate_password_strength,
    validate_email_address,
    validate_phone_number,
    
    # Input sanitization
    sanitize_input,
    mask_sensitive_data,
    
    # Security utilities
    generate_secure_key,
    generate_verification_code,
    secure_compare,
    
    # Rate limiting decorator
    rate_limit,
    
    # API key decorator
    require_api_key,
    
    # Security logging
    log_security_event
)

# Import Twilio utilities
# We import all functions from twilio_helpers since they're commonly used together
try:
    from .twilio_helpers import (
        get_twilio_client,
        send_sms,
        validate_twilio_request
    )
except ImportError:
    # Handle case where twilio_helpers.py doesn't exist yet
    pass

# Import OpenAI utilities
# These might be used less frequently, so we import selectively


# Package-level constants
# These define what's available when someone does "from utils import *"
__all__ = [
    # Security functions - most important to expose
    'generate_token',
    'verify_token',
    'revoke_token',
    'hash_password',
    'verify_password',
    'generate_api_key',
    'validate_api_key',
    'revoke_api_key',
    'get_api_key_info',
    'validate_password_strength',
    'validate_email_address',
    'validate_phone_number',
    'sanitize_input',
    'mask_sensitive_data',
    'generate_secure_key',
    'generate_verification_code',
    'secure_compare',
    'rate_limit',
    'require_api_key',
    'log_security_event',
    
    # Twilio functions - frequently used for SMS communication
    'get_twilio_client',
    'send_sms',
    'validate_twilio_request',
]


# Version information
__version__ = '1.0.0'
__author__ = 'Your Team'


# Package-level initialization (if needed)
# This code runs when the utils package is first imported
import logging

# Set up logging for the utils package
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a formatter for utils package logs
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)

# You can add a specific handler for utils logging if needed
# handler = logging.StreamHandler()
# handler.setFormatter(formatter)
# logger.addHandler(handler)

logger.debug("Utils package initialized successfully")


# Convenience functions that combine utilities from different modules
def create_user_session(user_id, remember_me=False):
    """
    Convenience function that creates both access and refresh tokens.
    
    This is a higher-level function that combines multiple security operations
    to make common tasks easier for developers using this package.
    
    Args:
        user_id (int): ID of the user to create session for
        remember_me (bool): Whether to create long-lasting session
        
    Returns:
        dict: Dictionary containing both tokens
    """
    access_hours = 1
    refresh_days = 1 if not remember_me else 30
    
    access_token = generate_token(
        user_id=user_id,
        token_type='access',
        expiry_hours=access_hours
    )
    
    refresh_token = generate_token(
        user_id=user_id,
        token_type='refresh',
        expiry_hours=refresh_days * 24
    )
    
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_in': access_hours * 3600,  # seconds
        'token_type': 'bearer'
    }


def validate_user_input(data, required_fields=None, sanitize=True):
    """
    Convenience function that validates and sanitizes user input.
    
    This combines multiple validation steps into a single, easy-to-use function
    that can be called from route handlers.
    
    Args:
        data (dict): Dictionary of user input
        required_fields (list): List of required field names
        sanitize (bool): Whether to sanitize text inputs
        
    Returns:
        tuple: (is_valid, cleaned_data, errors)
    """
    errors = []
    cleaned_data = {}
    
    required_fields = required_fields or []
    
    # Check for required fields
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"Missing required field: {field}")
    
    # Sanitize and validate each field
    for key, value in data.items():
        if isinstance(value, str) and sanitize:
            # Sanitize text inputs
            cleaned_value = sanitize_input(value)
            
            # Additional validation based on field name
            if 'email' in key.lower() and value:
                is_valid, validated_email = validate_email_address(value)
                if not is_valid:
                    errors.append(f"Invalid email format for {key}")
                else:
                    cleaned_value = validated_email
            
            elif 'phone' in key.lower() and value:
                is_valid, formatted_phone, error = validate_phone_number(value)
                if not is_valid:
                    errors.append(f"Invalid phone number for {key}: {error}")
                else:
                    cleaned_value = formatted_phone
            
            cleaned_data[key] = cleaned_value
        else:
            cleaned_data[key] = value
    
    return len(errors) == 0, cleaned_data, errors


# Error handling for missing dependencies
def _handle_import_error(module_name, error):
    """
    Log import errors gracefully without breaking the application.
    
    This is a good practice when you have optional dependencies or modules
    that might not exist in all deployment scenarios.
    """
    logger.warning(f"Could not import {module_name}: {error}")
    logger.info(f"{module_name} functionality will not be available")





# You can also define package-level configuration here
UTILS_CONFIG = {
    'default_token_expiry': 3600,  # 1 hour in seconds
    'default_api_key_prefix': 'sk_',
    'max_rate_limit_requests': 100,
    'rate_limit_window': 3600,  # 1 hour in seconds
}


# Helper function for debugging (development only)
def debug_package_imports():
    """
    Helper function to see what's available in the utils package.
    
    This is useful during development to understand what functions
    are available and how they're organized.
    """
    print("Available functions in utils package:")
    for item in __all__:
        try:
            func = globals()[item]
            print(f"  - {item}: {func.__doc__.split('.')[0] if func.__doc__ else 'No description'}")
        except KeyError:
            print(f"  - {item}: Not found (may be imported conditionally)")