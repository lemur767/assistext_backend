import os
import hmac
import hashlib
import base64
import logging
from typing import Dict, Any, Optional
from flask import request, current_app
from signalwire.rest import Client as SignalWireClient

def get_signalwire_client() -> Optional[SignalWireClient]:
    """
    Get configured SignalWire client instance
    
    Returns:
        SignalWire client or None if not configured
    """
    try:
        project_id = os.getenv('SIGNALWIRE_PROJECT_ID')
        api_token = os.getenv('SIGNALWIRE_API_TOKEN')
        space_url = os.getenv('SIGNALWIRE_SPACE_URL')
        
        if not all([project_id, api_token, space_url]):
            if current_app:
                current_app.logger.error("Missing SignalWire credentials")
            return None
        
        client = SignalWireClient(
            project_id,
            api_token,
            signalwire_space_url=space_url
        )
        
        return client
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Failed to create SignalWire client: {str(e)}")
        return None

def validate_signalwire_signature(request_url: str = None, post_data: Dict = None, signature: str = None) -> bool:
    """
    Validate SignalWire webhook signature using HMAC SHA-256
    
    Args:
        request_url: Full request URL (optional, will use Flask request if not provided)
        post_data: POST data dictionary (optional, will use Flask request if not provided)
        signature: Signature header (optional, will use Flask request if not provided)
    
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Use Flask request if parameters not provided
        if request_url is None:
            request_url = request.url
        
        if post_data is None:
            post_data = request.form.to_dict()
        
        if signature is None:
            signature = request.headers.get('X-SignalWire-Signature', '')
        
        if not signature:
            if current_app:
                current_app.logger.warning("Missing SignalWire webhook signature")
            return False
        
        # Get auth token
        auth_token = os.getenv('SIGNALWIRE_API_TOKEN')
        if not auth_token:
            if current_app:
                current_app.logger.error("SIGNALWIRE_API_TOKEN not configured")
            return False
        
        # Build validation string
        # Sort POST data and concatenate
        sorted_data = []
        for key in sorted(post_data.keys()):
            sorted_data.append(f"{key}{post_data[key]}")
        
        validation_string = request_url + ''.join(sorted_data)
        
        # Calculate expected signature
        expected_signature = base64.b64encode(
            hmac.new(
                auth_token.encode('utf-8'),
                validation_string.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Compare signatures using timing-safe comparison
        is_valid = hmac.compare_digest(signature, expected_signature)
        
        if not is_valid and current_app:
            current_app.logger.warning(
                f"Invalid SignalWire signature. Expected: {expected_signature}, Got: {signature}"
            )
        
        return is_valid
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Webhook signature validation error: {str(e)}")
        return False

def create_cxml_response(message: str = None, to_number: str = None, from_number: str = None, 
                        additional_elements: str = "") -> str:
    """
    Create cXML response for SignalWire webhooks
    
    Args:
        message: Message text to send
        to_number: Recipient phone number
        from_number: Sender phone number
        additional_elements: Additional XML elements to include
    
    Returns:
        Formatted cXML response string
    """
    if message and to_number and from_number:
        # Escape XML special characters
        escaped_message = escape_xml(message)
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message to="{to_number}" from="{from_number}">{escaped_message}</Message>
    {additional_elements}
</Response>'''
    elif message and to_number:
        # Simple message without from number
        escaped_message = escape_xml(message)
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message to="{to_number}">{escaped_message}</Message>
    {additional_elements}
</Response>'''
    else:
        # Empty response
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    {additional_elements}
</Response>'''

def create_voice_cxml_response(message: str = None, voice: str = "alice", 
                             action_after: str = "hangup") -> str:
    """
    Create cXML response for voice webhooks
    
    Args:
        message: Message to speak
        voice: Voice to use (alice, bob, etc.)
        action_after: Action after speaking (hangup, pause, etc.)
    
    Returns:
        Voice cXML response
    """
    if message:
        escaped_message = escape_xml(message)
        response = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice}">{escaped_message}</Say>'''
        
        if action_after == "hangup":
            response += '\n    <Hangup/>'
        elif action_after == "pause":
            response += '\n    <Pause length="2"/>'
        
        response += '\n</Response>'
        return response
    else:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Hangup/>
</Response>'''

def escape_xml(text: str) -> str:
    """
    Escape XML special characters
    
    Args:
        text: Text to escape
    
    Returns:
        XML-safe text
    """
    if not text:
        return ""
    
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))

def format_phone_number(phone_number: str) -> str:
    """
    Format phone number to E.164 standard
    
    Args:
        phone_number: Phone number in various formats
    
    Returns:
        E.164 formatted phone number
    """
    if not phone_number:
        return ""
    
    # Remove all non-digit characters
    digits_only = ''.join(filter(str.isdigit, phone_number))
    
    # Handle different input formats
    if digits_only.startswith('1') and len(digits_only) == 11:
        # US/Canada number with country code
        return f"+{digits_only}"
    elif len(digits_only) == 10:
        # US/Canada number without country code
        return f"+1{digits_only}"
    elif digits_only.startswith('1') and len(digits_only) > 11:
        # Likely international with extra digits
        return f"+{digits_only}"
    else:
        # Assume it's already in correct format or international
        return f"+{digits_only}"

def parse_signalwire_webhook_data(request_form: Dict) -> Dict[str, Any]:
    """
    Parse and normalize SignalWire webhook data
    
    Args:
        request_form: Flask request.form data
    
    Returns:
        Normalized webhook data dictionary
    """
    return {
        'message_sid': request_form.get('MessageSid', ''),
        'account_sid': request_form.get('AccountSid', ''),
        'from_number': request_form.get('From', ''),
        'to_number': request_form.get('To', ''),
        'message_body': request_form.get('Body', '').strip(),
        'message_status': request_form.get('SmsStatus', 'received'),
        'num_media': int(request_form.get('NumMedia', '0')),
        'error_code': request_form.get('ErrorCode', ''),
        'error_message': request_form.get('ErrorMessage', ''),
        
        # Call-specific fields
        'call_sid': request_form.get('CallSid', ''),
        'call_status': request_form.get('CallStatus', ''),
        'direction': request_form.get('Direction', ''),
        
        # Additional metadata
        'timestamp': request_form.get('Timestamp', ''),
        'api_version': request_form.get('ApiVersion', ''),
    }

def get_media_urls_from_webhook(request_form: Dict) -> list:
    """
    Extract media URLs from SignalWire webhook data
    
    Args:
        request_form: Flask request.form data
    
    Returns:
        List of media URL dictionaries
    """
    media_urls = []
    num_media = int(request_form.get('NumMedia', '0'))
    
    for i in range(num_media):
        media_url = request_form.get(f'MediaUrl{i}')
        media_type = request_form.get(f'MediaContentType{i}')
        
        if media_url:
            media_urls.append({
                'url': media_url,
                'content_type': media_type,
                'index': i
            })
    
    return media_urls

def log_webhook_request(webhook_type: str, webhook_data: Dict[str, Any], 
                       success: bool = True, error: str = None):
    """
    Log webhook request details for debugging and monitoring
    
    Args:
        webhook_type: Type of webhook (sms, voice, status)
        webhook_data: Parsed webhook data
        success: Whether webhook processing was successful
        error: Error message if processing failed
    """
    if not current_app:
        return
    
    log_data = {
        'webhook_type': webhook_type,
        'message_sid': webhook_data.get('message_sid', ''),
        'from': webhook_data.get('from_number', ''),
        'to': webhook_data.get('to_number', ''),
        'success': success
    }
    
    if error:
        log_data['error'] = error
    
    if success:
        current_app.logger.info(f"Webhook {webhook_type} processed: {log_data}")
    else:
        current_app.logger.error(f"Webhook {webhook_type} failed: {log_data}")

def validate_phone_number_format(phone_number: str) -> tuple[bool, str]:
    """
    Validate phone number format
    
    Args:
        phone_number: Phone number to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone_number:
        return False, "Phone number is required"
    
    # Remove all non-digit characters for validation
    digits_only = ''.join(filter(str.isdigit, phone_number))
    
    if len(digits_only) < 10:
        return False, "Phone number must have at least 10 digits"
    
    if len(digits_only) > 15:
        return False, "Phone number is too long"
    
    # Check for valid North American numbers
    if len(digits_only) == 10 or (len(digits_only) == 11 and digits_only.startswith('1')):
        return True, ""
    
    # Check for international numbers
    if len(digits_only) >= 10:
        return True, ""
    
    return False, "Invalid phone number format"

class SignalWireError(Exception):
    """Custom exception for SignalWire-related errors"""
    def __init__(self, message: str, error_code: str = None, status_code: int = None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)

def handle_signalwire_exception(e: Exception) -> Dict[str, Any]:
    """
    Handle SignalWire API exceptions and return standardized error response
    
    Args:
        e: Exception from SignalWire API
    
    Returns:
        Standardized error dictionary
    """
    error_response = {
        'success': False,
        'error': 'SignalWire API error',
        'details': str(e)
    }
    
    # Handle specific SignalWire error types
    if hasattr(e, 'code'):
        error_response['error_code'] = e.code
    
    if hasattr(e, 'status'):
        error_response['status_code'] = e.status
    
    if hasattr(e, 'msg'):
        error_response['error'] = e.msg
    
    return error_response