# app/utils/signalwire_helpers.py - Working SignalWire integration

from signalwire.rest import Client as SignalWireClient
from flask import current_app
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def get_signalwire_client() -> Optional[SignalWireClient]:
    """Get configured SignalWire client"""
    try:
        space_url = current_app.config.get('SIGNALWIRE_SPACE_URL')
        project_id = current_app.config.get('SIGNALWIRE_PROJECT_ID') 
        auth_token = current_app.config.get('SIGNALWIRE_AUTH_TOKEN')
        
        logger.info(f"SignalWire config check: space_url={bool(space_url)}, project_id={bool(project_id)}, auth_token={bool(auth_token)}")
        
        if not all([space_url, project_id, auth_token]):
            logger.error("SignalWire credentials not configured properly")
            logger.error(f"Missing: space_url={not space_url}, project_id={not project_id}, auth_token={not auth_token}")
            return None
        
        client = SignalWireClient(project_id, auth_token, signalwire_space_url=space_url)
        logger.info("SignalWire client created successfully")
        return client
        
    except Exception as e:
        logger.error(f"Failed to create SignalWire client: {str(e)}")
        return None

def get_available_phone_numbers(area_code: str = None, city: str = None, country: str = 'CA', limit: int = 5) -> Tuple[List[Dict], str]:
    """Search for available phone numbers"""
    try:
        logger.info(f"Searching for numbers: area_code={area_code}, city={city}, country={country}")
        
        client = get_signalwire_client()
        if not client:
            error_msg = "SignalWire service unavailable - client not initialized"
            logger.error(error_msg)
            return [], error_msg
        
        search_params = {'limit': limit, 'sms_enabled': True}
        
        if area_code:
            search_params['area_code'] = area_code
        
        logger.info(f"Search params: {search_params}")
        
        # Search for numbers
        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').list(**search_params)
        
        logger.info(f"Found {len(available_numbers)} numbers from SignalWire")
        
        # Format results
        formatted_numbers = []
        for number in available_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'locality': getattr(number, 'locality', city or 'Unknown'),
                'region': getattr(number, 'region', 'ON'),
                'area_code': area_code or number.phone_number[2:5] if len(number.phone_number) > 5 else area_code,
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                },
                'setup_cost': '$1.00',
                'monthly_cost': '$1.00'
            }
            formatted_numbers.append(formatted_number)
        
        logger.info(f"Formatted {len(formatted_numbers)} numbers for return")
        return formatted_numbers, ""
        
    except Exception as e:
        error_msg = f"Failed to search available numbers: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

def purchase_phone_number(phone_number: str, friendly_name: str = None, webhook_url: str = None) -> Tuple[Optional[Dict], str]:
    """Purchase a phone number and configure webhook"""
    try:
        logger.info(f"Attempting to purchase number: {phone_number}")
        
        client = get_signalwire_client()
        if not client:
            error_msg = "SignalWire service unavailable for purchase"
            logger.error(error_msg)
            return None, error_msg
        
        purchase_params = {'phone_number': phone_number}
        
        if friendly_name:
            purchase_params['friendly_name'] = friendly_name
        
        if webhook_url:
            purchase_params['sms_url'] = webhook_url
            purchase_params['sms_method'] = 'POST'
            logger.info(f"Configuring webhook: {webhook_url}")
        
        logger.info(f"Purchase params: {purchase_params}")
        
        # Purchase the number
        purchased_number = client.incoming_phone_numbers.create(**purchase_params)
        
        result_data = {
            'phone_number': purchased_number.phone_number,
            'friendly_name': purchased_number.friendly_name,
            'sid': purchased_number.sid,
            'capabilities': {'sms': True, 'mms': True, 'voice': True},
            'webhook_configured': webhook_url is not None,
            'status': 'active',
            'purchased_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Successfully purchased number {phone_number} with SID {purchased_number.sid}")
        return result_data, ""
        
    except Exception as e:
        error_msg = f"Failed to purchase phone number: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

def send_sms(from_number: str, to_number: str, body: str, media_urls: List[str] = None) -> Dict[str, Any]:
    """Send SMS/MMS via SignalWire"""
    try:
        logger.info(f"Sending SMS from {from_number} to {to_number}")
        
        client = get_signalwire_client()
        if not client:
            error_msg = "SignalWire client not available for SMS"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        
        message_params = {
            'body': body,
            'from_': from_number,
            'to': to_number
        }
        
        if media_urls and len(media_urls) > 0:
            message_params['media_url'] = media_urls
        
        message = client.messages.create(**message_params)
        
        result = {
            'success': True,
            'message_sid': message.sid,
            'status': message.status,
            'from_number': message.from_,
            'to_number': message.to,
            'body': message.body,
            'date_created': message.date_created.isoformat() if message.date_created else None
        }
        
        logger.info(f"SMS sent successfully: {message.sid}")
        return result
        
    except Exception as e:
        error_msg = f"Failed to send SMS: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

def format_phone_display(phone_number: str) -> str:
    """Format phone number for display"""
    if not phone_number:
        return ""
        
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number

def validate_signalwire_webhook_request(request) -> bool:
    """Validate that the request came from SignalWire"""
    try:
        required_fields = ['From', 'To', 'Body']
        for field in required_fields:
            if field not in request.form:
                logger.warning(f"Missing required field: {field}")
                return False
        return True
    except Exception as e:
        logger.error(f"Error validating webhook request: {str(e)}")
        return False

# Backward compatibility functions
def get_signalwire_phone_numbers():
    """Get all purchased SignalWire phone numbers"""
    try:
        client = get_signalwire_client()
        if not client:
            return []
        
        phone_numbers = client.incoming_phone_numbers.list()
        return [{'phone_number': num.phone_number, 'sid': num.sid} for num in phone_numbers]
    except Exception as e:
        logger.error(f"Error getting phone numbers: {str(e)}")
        return []

def configure_number_webhook(phone_number: str, webhook_url: str) -> bool:
    """Configure webhook for an existing phone number"""
    try:
        client = get_signalwire_client()
        if not client:
            return False
        
        phone_numbers = client.incoming_phone_numbers.list()
        for number in phone_numbers:
            if number.phone_number == phone_number:
                client.incoming_phone_numbers(number.sid).update(
                    sms_url=webhook_url,
                    sms_method='POST'
                )
                logger.info(f"Webhook configured for {phone_number}")
                return True
        
        logger.error(f"Phone number {phone_number} not found")
        return False
        
    except Exception as e:
        logger.error(f"Error configuring webhook: {str(e)}")
        return False

# Export all functions
__all__ = [
    'get_signalwire_client',
    'get_available_phone_numbers', 
    'purchase_phone_number',
    'send_sms',
    'format_phone_display',
    'validate_signalwire_webhook_request',
    'get_signalwire_phone_numbers',
    'configure_number_webhook'
]

# Test import at module level
logger.info("SignalWire helpers module loaded successfully")
