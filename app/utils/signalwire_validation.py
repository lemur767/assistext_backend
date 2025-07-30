"""
Manual SignalWire Webhook Validation & Error Handling
====================================================

This module provides manual validation and error handling functions for SignalWire
webhooks and API calls without relying on the SDK's RequestValidator or exception classes.

Based on SignalWire's official documentation and proven implementations.
"""

import os
import hmac
import hashlib
import base64
import logging
import time
from typing import Dict, Any, Optional, Tuple
from urllib.parse import quote_plus
from flask import request, current_app
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)


# =============================================================================
# WEBHOOK SIGNATURE VALIDATION
# =============================================================================

class SignalWireWebhookValidator:
    """
    Manual SignalWire webhook signature validation
    
    Based on SignalWire's HMAC-SHA256 + Base64 signature validation process
    """
    
    def __init__(self, auth_token: str):
        self.auth_token = auth_token
    
    def validate_signature(self, url: str, post_data: Dict[str, str], signature: str) -> bool:
        """
        Validate SignalWire webhook signature using HMAC-SHA256 + Base64
        
        Args:
            url: Full webhook URL including query parameters
            post_data: POST form data as dictionary
            signature: X-SignalWire-Signature header value
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            if not signature:
                logger.warning("No signature provided for validation")
                return False
            
            if not self.auth_token:
                logger.error("No auth token configured for signature validation")
                return False
            
            # Build the validation string: URL + sorted form parameters
            validation_string = self._build_validation_string(url, post_data)
            
            # Calculate expected signature using HMAC-SHA256 + Base64
            expected_signature = self._calculate_signature(validation_string)
            
            # Compare signatures using secure comparison
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if is_valid:
                logger.debug("✅ SignalWire webhook signature validated successfully")
            else:
                logger.warning("❌ Invalid SignalWire webhook signature")
                logger.debug(f"Expected: {expected_signature}")
                logger.debug(f"Received: {signature}")
                logger.debug(f"Validation string: {validation_string}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Signature validation error: {e}")
            return False
    
    def _build_validation_string(self, url: str, post_data: Dict[str, str]) -> str:
        """
        Build the string used for signature validation
        
        Format: URL + sorted(key1value1key2value2...)
        """
        # Start with the full URL
        validation_string = url
        
        # Sort form data by key and concatenate key+value pairs
        sorted_params = []
        for key in sorted(post_data.keys()):
            # SignalWire expects key+value concatenation (no separators)
            sorted_params.append(f"{key}{post_data[key]}")
        
        # Append sorted parameters to URL
        validation_string += ''.join(sorted_params)
        
        return validation_string
    
    def _calculate_signature(self, validation_string: str) -> str:
        """
        Calculate HMAC-SHA256 signature and encode as Base64
        """
        signature = hmac.new(
            self.auth_token.encode('utf-8'),
            validation_string.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')


# =============================================================================
# FLASK REQUEST VALIDATION HELPERS
# =============================================================================

def validate_signalwire_webhook(auth_token: str = None, 
                               skip_in_development: bool = True) -> Tuple[bool, str]:
    """
    Validate SignalWire webhook request from Flask request context
    
    Args:
        auth_token: SignalWire auth token (uses env var if not provided)
        skip_in_development: Skip validation in development mode
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Skip validation in development if configured
        if (skip_in_development and 
            os.getenv('FLASK_ENV') == 'development' and 
            os.getenv('SKIP_WEBHOOK_VALIDATION', '').lower() == 'true'):
            logger.warning("⚠️ Skipping webhook validation in development mode")
            return True, ""
        
        # Get auth token
        if not auth_token:
            auth_token = (os.getenv('SIGNALWIRE_AUTH_TOKEN') or 
                         os.getenv('SIGNALWIRE_TOKEN'))
        
        if not auth_token:
            return False, "SIGNALWIRE_AUTH_TOKEN not configured"
        
        # Get signature from headers
        signature = request.headers.get('X-SignalWire-Signature', '')
        if not signature:
            return False, "Missing X-SignalWire-Signature header"
        
        # Get request data
        url = request.url
        post_data = request.form.to_dict()
        
        # Validate signature
        validator = SignalWireWebhookValidator(auth_token)
        is_valid = validator.validate_signature(url, post_data, signature)
        
        if is_valid:
            return True, ""
        else:
            return False, "Invalid webhook signature"
            
    except Exception as e:
        logger.error(f"Webhook validation error: {e}")
        return False, f"Validation error: {str(e)}"


def get_webhook_data() -> Dict[str, Any]:
    """
    Extract and validate webhook data from Flask request
    
    Returns:
        Dictionary containing webhook payload data
    """
    try:
        webhook_data = {
            'AccountSid': request.form.get('AccountSid', ''),
            'MessageSid': request.form.get('MessageSid', ''),
            'From': request.form.get('From', ''),
            'To': request.form.get('To', ''),
            'Body': request.form.get('Body', ''),
            'NumMedia': request.form.get('NumMedia', '0'),
            'MessageStatus': request.form.get('MessageStatus', ''),
            'SmsStatus': request.form.get('SmsStatus', ''),
            'CallSid': request.form.get('CallSid', ''),
            'CallStatus': request.form.get('CallStatus', ''),
            'Direction': request.form.get('Direction', ''),
            'ApiVersion': request.form.get('ApiVersion', ''),
        }
        
        # Add media URLs if present
        num_media = int(webhook_data['NumMedia'])
        media_urls = []
        for i in range(num_media):
            media_url = request.form.get(f'MediaUrl{i}')
            if media_url:
                media_urls.append(media_url)
        
        webhook_data['MediaUrls'] = media_urls
        
        return webhook_data
        
    except Exception as e:
        logger.error(f"Error extracting webhook data: {e}")
        return {}


# =============================================================================
# MANUAL ERROR HANDLING
# =============================================================================

class SignalWireError(Exception):
    """Base SignalWire error class"""
    def __init__(self, message: str, code: str = None, status_code: int = None, details: Dict = None):
        self.message = message
        self.code = code or 'UNKNOWN_ERROR'
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class SignalWireAuthError(SignalWireError):
    """Authentication/authorization errors"""
    pass


class SignalWireValidationError(SignalWireError):
    """Validation errors (invalid phone numbers, etc.)"""
    pass


class SignalWireRateLimitError(SignalWireError):
    """Rate limiting errors"""
    pass


class SignalWireServiceError(SignalWireError):
    """Service unavailable/timeout errors"""
    pass


def parse_signalwire_error(response: requests.Response) -> SignalWireError:
    """
    Parse SignalWire API error response and create appropriate exception
    
    Args:
        response: HTTP response from SignalWire API
        
    Returns:
        Appropriate SignalWireError subclass
    """
    try:
        # Try to parse JSON error response
        error_data = response.json()
        
        code = str(error_data.get('code', 'UNKNOWN'))
        message = error_data.get('message', 'Unknown error')
        more_info = error_data.get('more_info', '')
        status = error_data.get('status', response.status_code)
        
        # Map common error codes to specific exceptions
        if code in ['20003', '20005']:  # Authentication errors
            return SignalWireAuthError(
                message=f"Authentication failed: {message}",
                code=code,
                status_code=response.status_code,
                details={'more_info': more_info}
            )
        
        elif code in ['21614', '21211']:  # Invalid phone number format
            return SignalWireValidationError(
                message=f"Invalid phone number: {message}",
                code=code,
                status_code=response.status_code,
                details={'more_info': more_info}
            )
        
        elif code in ['21408', '21421']:  # Number not available
            return SignalWireValidationError(
                message=f"Phone number not available: {message}",
                code=code,
                status_code=response.status_code,
                details={'more_info': more_info}
            )
        
        elif code in ['20429']:  # Rate limiting
            return SignalWireRateLimitError(
                message=f"Rate limit exceeded: {message}",
                code=code,
                status_code=response.status_code,
                details={'more_info': more_info}
            )
        
        else:  # Generic error
            return SignalWireError(
                message=f"SignalWire API error: {message}",
                code=code,
                status_code=response.status_code,
                details={'more_info': more_info}
            )
        
    except ValueError:
        # Non-JSON response
        return SignalWireError(
            message=f"HTTP {response.status_code}: {response.text}",
            code=f"HTTP_{response.status_code}",
            status_code=response.status_code
        )


def handle_signalwire_request_errors(func):
    """
    Decorator for handling SignalWire API request errors
    
    Usage:
        @handle_signalwire_request_errors
        def make_api_call():
            response = requests.post(...)
            return response
    """
    def wrapper(*args, **kwargs):
        try:
            response = func(*args, **kwargs)
            
            # Check if response indicates an error
            if not response.ok:
                raise parse_signalwire_error(response)
            
            return response
            
        except RequestException as e:
            # Handle network/connection errors
            if isinstance(e, Timeout):
                raise SignalWireServiceError(
                    message="Request timeout while contacting SignalWire",
                    code="TIMEOUT_ERROR"
                )
            elif isinstance(e, ConnectionError):
                raise SignalWireServiceError(
                    message="Connection error while contacting SignalWire", 
                    code="CONNECTION_ERROR"
                )
            else:
                raise SignalWireServiceError(
                    message=f"Network error: {str(e)}",
                    code="NETWORK_ERROR"
                )
        
        except SignalWireError:
            # Re-raise SignalWire errors
            raise
        
        except Exception as e:
            # Handle unexpected errors
            raise SignalWireError(
                message=f"Unexpected error: {str(e)}",
                code="UNEXPECTED_ERROR"
            )
    
    return wrapper


# =============================================================================
# LAML/TWIML RESPONSE HELPERS
# =============================================================================

def create_laml_response(message: str = None, 
                        to_number: str = None,
                        from_number: str = None,
                        media_urls: list = None) -> str:
    """
    Create LaML (Language Markup Language) response for SignalWire webhooks
    
    Args:
        message: Response message text
        to_number: Recipient phone number (optional)
        from_number: Sender phone number (optional)
        media_urls: List of media URLs for MMS (optional)
        
    Returns:
        XML string for LaML response
    """
    response_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<Response>']
    
    if message or media_urls:
        message_attrs = []
        
        if to_number:
            message_attrs.append(f'to="{to_number}"')
        if from_number:
            message_attrs.append(f'from="{from_number}"')
        
        attrs_str = ' ' + ' '.join(message_attrs) if message_attrs else ''
        
        response_parts.append(f'<Message{attrs_str}>')
        
        if message:
            # Escape XML special characters
            escaped_message = (message.replace('&', '&amp;')
                              .replace('<', '&lt;')
                              .replace('>', '&gt;')
                              .replace('"', '&quot;')
                              .replace("'", '&#39;'))
            response_parts.append(escaped_message)
        
        if media_urls:
            for url in media_urls:
                response_parts.append(f'<Media>{url}</Media>')
        
        response_parts.append('</Message>')
    
    response_parts.append('</Response>')
    
    return '\n'.join(response_parts)


def create_empty_laml_response() -> str:
    """Create empty LaML response (no reply)"""
    return '<?xml version="1.0" encoding="UTF-8"?>\n<Response></Response>'


def create_voice_laml_response(message: str, voice: str = "alice", language: str = "en") -> str:
    """
    Create LaML response for voice calls
    
    Args:
        message: Text to speak
        voice: Voice to use (alice, man, woman)
        language: Language code (en, es, fr, etc.)
        
    Returns:
        XML string for voice LaML response
    """
    escaped_message = (message.replace('&', '&amp;')
                      .replace('<', '&lt;')
                      .replace('>', '&gt;'))
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}" language="{language}">{escaped_message}</Say>
</Response>'''


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def format_phone_number(phone: str) -> str:
    """
    Format phone number to E.164 format
    
    Args:
        phone: Phone number in various formats
        
    Returns:
        Phone number in E.164 format (+1XXXXXXXXXX)
    """
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Handle different formats
    if len(digits) == 10:
        # US/Canada number without country code
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        # US/Canada number with country code
        return f"+{digits}"
    elif digits.startswith('+'):
        # Already in E.164 format
        return phone
    else:
        # Return as-is if we can't determine format
        return phone


def is_valid_phone_number(phone: str) -> bool:
    """
    Basic phone number validation
    
    Args:
        phone: Phone number to validate
        
    Returns:
        True if number appears valid
    """
    if not phone:
        return False
    
    # Remove non-digit characters for validation
    digits = ''.join(filter(str.isdigit, phone))
    
    # Check length (US/Canada: 10 digits, with country code: 11)
    return len(digits) in [10, 11]


def log_webhook_event(event_type: str, data: Dict[str, Any], success: bool = True):
    """
    Log webhook events for debugging and monitoring
    
    Args:
        event_type: Type of webhook event (sms_received, call_started, etc.)
        data: Event data
        success: Whether event was processed successfully
    """
    log_level = logging.INFO if success else logging.ERROR
    status = "SUCCESS" if success else "FAILED"
    
    logger.log(log_level, f"SignalWire webhook {event_type} - {status}")
    logger.debug(f"Webhook data: {data}")


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def example_webhook_handler():
    """
    Example webhook handler using manual validation
    """
    from flask import request, Response
    
    # Validate webhook signature
    is_valid, error = validate_signalwire_webhook()
    if not is_valid:
        logger.warning(f"Invalid webhook: {error}")
        return Response('Unauthorized', status=401)
    
    # Extract webhook data
    webhook_data = get_webhook_data()
    
    # Log the event
    log_webhook_event('sms_received', webhook_data)
    
    try:
        # Process the message
        from_number = webhook_data['From']
        to_number = webhook_data['To']
        message_body = webhook_data['Body']
        
        # Your processing logic here
        response_message = f"Thanks for your message: {message_body}"
        
        # Create LaML response
        laml_response = create_laml_response(
            message=response_message,
            to=from_number,
            from_=to_number
        )
        
        return Response(laml_response, mimetype='application/xml')
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        log_webhook_event('sms_received', webhook_data, success=False)
        
        # Return empty response on error
        return Response(create_empty_laml_response(), mimetype='application/xml')


# Export main functions
__all__ = [
    'SignalWireWebhookValidator',
    'validate_signalwire_webhook',
    'get_webhook_data',
    'SignalWireError',
    'SignalWireAuthError', 
    'SignalWireValidationError',
    'SignalWireRateLimitError',
    'SignalWireServiceError',
    'parse_signalwire_error',
    'handle_signalwire_request_errors',
    'create_laml_response',
    'create_empty_laml_response',
    'create_voice_laml_response',
    'format_phone_number',
    'is_valid_phone_number',
    'log_webhook_event'
]