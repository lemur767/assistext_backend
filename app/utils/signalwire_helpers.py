"""
Complete SignalWire Helpers Implementation
app/utils/signalwire_helpers.py - All functions needed for SignalWire integration
"""
import os
import hmac
import hashlib
import base64
import logging
from typing import Dict, Any, Optional, List, Tuple
from flask import request, current_app
from signalwire.rest import Client as SignalWireClient
from signalwire.rest.api.v2010.account.available_phone_number import AvailablePhoneNumberInstance
from signalwire.rest.api.v2010.account.incoming_phone_number import IncomingPhoneNumberInstance

# Configure logging
logger = logging.getLogger(__name__)

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

def validate_signalwire_request(request_url: str = None, post_data: Dict = None, signature: str = None) -> bool:
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
        
        # Get auth token for validation
        auth_token = os.getenv('SIGNALWIRE_API_TOKEN')
        if not auth_token:
            if current_app:
                current_app.logger.error("Missing SignalWire auth token for validation")
            return False
        
        # Create the signature
        expected_signature = create_signature(auth_token, request_url, post_data)
        
        # Compare signatures
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Signature validation error: {str(e)}")
        return False

def create_signature(auth_token: str, url: str, post_data: Dict) -> str:
    """
    Create HMAC SHA-256 signature for SignalWire webhook validation
    
    Args:
        auth_token: SignalWire auth token
        url: Request URL
        post_data: POST data dictionary
        
    Returns:
        Base64 encoded signature
    """
    # Sort parameters and create query string
    sorted_params = sorted(post_data.items())
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
    
    # Create signature string
    signature_string = f"{url}{query_string}"
    
    # Create HMAC SHA-256 signature
    signature = hmac.new(
        auth_token.encode('utf-8'),
        signature_string.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    # Return base64 encoded signature
    return base64.b64encode(signature).decode('utf-8')

def get_available_phone_numbers(
    area_code: str = None, 
    city: str = None, 
    country: str = 'US', 
    limit: int = 20
) -> Tuple[List[Dict], str]:
    """
    Search for available phone numbers with proper regional parameters
    
    Args:
        area_code: Area code to search in
        city: City to search in
        country: Country code (US or CA)
        limit: Maximum number of results
        
    Returns:
        Tuple of (list of available numbers, error message)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return [], "SignalWire service unavailable"
        
        # Build search parameters
        search_params = {'limit': limit}
        
        if area_code:
            search_params['area_code'] = area_code
        
        if city:
            search_params['in_locality'] = city
        
        # Search for available numbers
        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').local.list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').local.list(**search_params)
        
        # Format results
        formatted_numbers = []
        for number in available_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'friendly_name': getattr(number, 'friendly_name', ''),
                'locality': getattr(number, 'locality', city or 'Unknown'),
                'region': getattr(number, 'region', 'Unknown'),
                'iso_country': getattr(number, 'iso_country', country),
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                },
                'beta': getattr(number, 'beta', False),
                'price': getattr(number, 'price', 'Unknown'),
                'price_unit': getattr(number, 'price_unit', 'USD')
            }
            formatted_numbers.append(formatted_number)
        
        return formatted_numbers, ""
        
    except Exception as e:
        error_msg = f"Failed to search available numbers: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

def purchase_phone_number(phone_number: str, webhook_config: Dict = None) -> Tuple[bool, str, Dict]:
    """
    Purchase a phone number and configure webhooks
    
    Args:
        phone_number: Phone number to purchase
        webhook_config: Dictionary with webhook URLs
        
    Returns:
        Tuple of (success, message, purchased_number_data)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return False, "SignalWire service unavailable", {}
        
        # Default webhook config
        if webhook_config is None:
            base_url = os.getenv('BASE_URL', 'https://assitext.ca')
            webhook_config = {
                'sms_url': f"{base_url}/api/webhooks/sms",
                'voice_url': f"{base_url}/api/webhooks/voice",
                'status_callback': f"{base_url}/api/webhooks/status"
            }
        
        # Purchase the number
        purchased_number = client.incoming_phone_numbers.create(
            phone_number=phone_number,
            sms_url=webhook_config.get('sms_url'),
            voice_url=webhook_config.get('voice_url'),
            status_callback=webhook_config.get('status_callback'),
            sms_method='POST',
            voice_method='POST'
        )
        
        # Format response
        number_data = {
            'sid': purchased_number.sid,
            'phone_number': purchased_number.phone_number,
            'friendly_name': purchased_number.friendly_name,
            'date_created': purchased_number.date_created.isoformat() if purchased_number.date_created else None,
            'sms_url': purchased_number.sms_url,
            'voice_url': purchased_number.voice_url,
            'status_callback': purchased_number.status_callback,
            'capabilities': {
                'sms': getattr(purchased_number, 'sms_enabled', True),
                'mms': getattr(purchased_number, 'mms_enabled', True),
                'voice': getattr(purchased_number, 'voice_enabled', True)
            }
        }
        
        logger.info(f"Successfully purchased phone number: {phone_number}")
        return True, "Phone number purchased successfully", number_data
        
    except Exception as e:
        error_msg = f"Failed to purchase phone number: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, {}

def get_signalwire_phone_numbers() -> List[Dict]:
    """
    Get all phone numbers owned by the account
    
    Returns:
        List of owned phone numbers
    """
    try:
        client = get_signalwire_client()
        if not client:
            return []
        
        # Get all incoming phone numbers
        phone_numbers = client.incoming_phone_numbers.list()
        
        # Format results
        formatted_numbers = []
        for number in phone_numbers:
            formatted_number = {
                'sid': number.sid,
                'phone_number': number.phone_number,
                'friendly_name': number.friendly_name,
                'date_created': number.date_created.isoformat() if number.date_created else None,
                'sms_url': number.sms_url,
                'voice_url': number.voice_url,
                'status_callback': number.status_callback,
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                }
            }
            formatted_numbers.append(formatted_number)
        
        return formatted_numbers
        
    except Exception as e:
        logger.error(f"Failed to get phone numbers: {str(e)}")
        return []

def configure_number_webhook(phone_number_sid: str, webhook_config: Dict) -> Tuple[bool, str]:
    """
    Configure webhooks for an existing phone number
    
    Args:
        phone_number_sid: SID of the phone number
        webhook_config: Dictionary with webhook URLs
        
    Returns:
        Tuple of (success, message)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return False, "SignalWire service unavailable"
        
        # Update the phone number configuration
        phone_number = client.incoming_phone_numbers(phone_number_sid).update(
            sms_url=webhook_config.get('sms_url'),
            voice_url=webhook_config.get('voice_url'),
            status_callback=webhook_config.get('status_callback'),
            sms_method='POST',
            voice_method='POST'
        )
        
        logger.info(f"Successfully configured webhooks for {phone_number.phone_number}")
        return True, "Webhooks configured successfully"
        
    except Exception as e:
        error_msg = f"Failed to configure webhooks: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def send_sms(from_number: str, to_number: str, body: str) -> Tuple[bool, str, Dict]:
    """
    Send SMS message
    
    Args:
        from_number: Source phone number
        to_number: Destination phone number
        body: Message body
        
    Returns:
        Tuple of (success, message, message_data)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return False, "SignalWire service unavailable", {}
        
        # Send the message
        message = client.messages.create(
            from_=from_number,
            to=to_number,
            body=body
        )
        
        # Format response
        message_data = {
            'sid': message.sid,
            'from_number': message.from_,
            'to_number': message.to,
            'body': message.body,
            'status': message.status,
            'direction': message.direction,
            'date_sent': message.date_sent.isoformat() if message.date_sent else None,
            'price': message.price,
            'price_unit': message.price_unit
        }
        
        logger.info(f"Successfully sent SMS: {message.sid}")
        return True, "Message sent successfully", message_data
        
    except Exception as e:
        error_msg = f"Failed to send SMS: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, {}

def get_phone_number_info(phone_number: str) -> Dict:
    """
    Get information about a phone number
    
    Args:
        phone_number: Phone number to lookup
        
    Returns:
        Dictionary with phone number information
    """
    try:
        client = get_signalwire_client()
        if not client:
            return {}
        
        # Look up the phone number
        number_info = client.lookups.v1.phone_numbers(phone_number).fetch()
        
        return {
            'phone_number': number_info.phone_number,
            'national_format': number_info.national_format,
            'country_code': number_info.country_code,
            'carrier': getattr(number_info, 'carrier', {}),
            'url': number_info.url
        }
        
    except Exception as e:
        logger.error(f"Failed to get phone number info: {str(e)}")
        return {}

def format_phone_number(phone_number: str) -> str:
    """
    Format phone number for display
    
    Args:
        phone_number: Raw phone number
        
    Returns:
        Formatted phone number
    """
    if not phone_number:
        return ""
    
    # Remove non-digit characters
    digits = ''.join(filter(str.isdigit, phone_number))
    
    # Format based on length
    if len(digits) == 11 and digits.startswith('1'):
        # US/Canada format: +1 (123) 456-7890
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:11]}"
    elif len(digits) == 10:
        # US/Canada format without country code: (123) 456-7890
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    else:
        # International or unknown format
        return phone_number

def format_phone_display(phone_number: str) -> str:
    """
    Alias for format_phone_number for backwards compatibility
    """
    return format_phone_number(phone_number)

def configure_webhook(phone_number_sid: str, webhook_urls: Dict) -> bool:
    """
    Configure webhooks for a phone number (alias for configure_number_webhook)
    
    Args:
        phone_number_sid: SID of the phone number
        webhook_urls: Dictionary with webhook URLs
        
    Returns:
        True if successful, False otherwise
    """
    success, message = configure_number_webhook(phone_number_sid, webhook_urls)
    return success

def validate_signalwire_webhook_request(request_url: str = None, post_data: Dict = None, signature: str = None) -> bool:
    """
    Alias for validate_signalwire_request for backwards compatibility
    """
    return validate_signalwire_request(request_url, post_data, signature)

# Health check function
def get_signalwire_health() -> Dict:
    """
    Check SignalWire service health
    
    Returns:
        Dictionary with health status
    """
    try:
        client = get_signalwire_client()
        if not client:
            return {
                'status': 'unhealthy',
                'message': 'SignalWire client not available',
                'configured': False
            }
        
        # Try to list phone numbers to verify connection
        phone_numbers = client.incoming_phone_numbers.list(limit=1)
        
        return {
            'status': 'healthy',
            'message': 'SignalWire service is operational',
            'configured': True,
            'phone_numbers_count': len(list(phone_numbers))
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'message': f'SignalWire service error: {str(e)}',
            'configured': True,
            'error': str(e)
        }

# Export all functions
__all__ = [
    'get_signalwire_client',
    'validate_signalwire_request',
    'get_available_phone_numbers',
    'purchase_phone_number',
    'get_signalwire_phone_numbers',
    'configure_number_webhook',
    'send_sms',
    'get_phone_number_info',
    'format_phone_number',
    'format_phone_display',
    'configure_webhook',
    'validate_signalwire_webhook_request',
    'get_signalwire_health'
]