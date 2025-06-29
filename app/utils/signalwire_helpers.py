# =============================================================================
# COMPLETE SIGNALWIRE HELPERS - ALL MISSING FUNCTIONS INCLUDED
# =============================================================================

from signalwire.rest import Client as SignalWireClient
from flask import current_app
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import logging
import hashlib
import hmac
import base64

logger = logging.getLogger(__name__)

def get_signalwire_client() -> Optional[SignalWireClient]:
    """Get configured SignalWire client"""
    try:
        space_url = current_app.config.get('SIGNALWIRE_SPACE_URL')
        project_id = current_app.config.get('SIGNALWIRE_PROJECT_ID') 
        auth_token = current_app.config.get('SIGNALWIRE_AUTH_TOKEN')
        
        if not all([space_url, project_id, auth_token]):
            logger.error("SignalWire credentials not configured")
            return None
        
        return SignalWireClient(project_id, auth_token, signalwire_space_url=space_url)
        
    except Exception as e:
        logger.error(f"Failed to create SignalWire client: {str(e)}")
        return None

def send_sms(from_number: str, to_number: str, body: str, media_urls: List[str] = None) -> Dict[str, Any]:
    """Send SMS/MMS via SignalWire"""
    try:
        client = get_signalwire_client()
        if not client:
            return {'success': False, 'error': 'SignalWire client not available'}
        
        message_params = {
            'body': body,
            'from_': from_number,
            'to': to_number
        }
        
        if media_urls and len(media_urls) > 0:
            message_params['media_url'] = media_urls
        
        message = client.messages.create(**message_params)
        
        return {
            'success': True,
            'message_sid': message.sid,
            'status': message.status,
            'from_number': message.from_,
            'to_number': message.to,
            'body': message.body,
            'date_created': message.date_created.isoformat() if message.date_created else None
        }
        
    except Exception as e:
        logger.error(f"Failed to send SMS: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_signalwire_phone_numbers() -> List[Dict]:
    """Get all purchased SignalWire phone numbers"""
    try:
        client = get_signalwire_client()
        if not client:
            return []
        
        phone_numbers = client.incoming_phone_numbers.list()
        
        formatted_numbers = []
        for number in phone_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'sid': number.sid,
                'friendly_name': number.friendly_name,
                'capabilities': {
                    'sms': getattr(number.capabilities, 'sms', True) if hasattr(number, 'capabilities') else True,
                    'mms': getattr(number.capabilities, 'mms', True) if hasattr(number, 'capabilities') else True,
                    'voice': getattr(number.capabilities, 'voice', True) if hasattr(number, 'capabilities') else True
                },
                'sms_url': getattr(number, 'sms_url', None),
                'voice_url': getattr(number, 'voice_url', None),
                'date_created': getattr(number, 'date_created', None)
            }
            formatted_numbers.append(formatted_number)
        
        return formatted_numbers
        
    except Exception as e:
        logger.error(f"Error retrieving SignalWire phone numbers: {str(e)}")
        return []

def get_available_phone_numbers(area_code: str = None, city: str = None, country: str = 'CA', limit: int = 5) -> Tuple[List[Dict], str]:
    """Search for available phone numbers"""
    try:
        client = get_signalwire_client()
        if not client:
            return [], "SignalWire service unavailable"
        
        search_params = {'limit': limit, 'sms_enabled': True}
        
        if area_code:
            search_params['area_code'] = area_code
        
        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').list(**search_params)
        
        formatted_numbers = []
        for number in available_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'locality': getattr(number, 'locality', city or 'Unknown'),
                'region': getattr(number, 'region', 'ON'),
                'area_code': area_code or number.phone_number[2:5],
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                },
                'setup_cost': '$1.00',
                'monthly_cost': '$1.00'
            }
            formatted_numbers.append(formatted_number)
        
        return formatted_numbers, ""
        
    except Exception as e:
        return [], f"Failed to search available numbers: {str(e)}"

def purchase_phone_number(phone_number: str, friendly_name: str = None, webhook_url: str = None) -> Tuple[Optional[Dict], str]:
    """Purchase a phone number and configure webhook"""
    try:
        client = get_signalwire_client()
        if not client:
            return None, "SignalWire service unavailable"
        
        purchase_params = {'phone_number': phone_number}
        
        if friendly_name:
            purchase_params['friendly_name'] = friendly_name
        
        if webhook_url:
            purchase_params['sms_url'] = webhook_url
            purchase_params['sms_method'] = 'POST'
        
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
        
        return result_data, ""
        
    except Exception as e:
        return None, f"Failed to purchase phone number: {str(e)}"

def configure_number_webhook(phone_number: str, webhook_url: str) -> bool:
    """Configure webhook for an existing phone number"""
    try:
        client = get_signalwire_client()
        if not client:
            return False
        
        phone_numbers = client.incoming_phone_numbers.list()
        target_number = None
        
        for number in phone_numbers:
            if number.phone_number == phone_number:
                target_number = number
                break
        
        if not target_number:
            return False
        
        client.incoming_phone_numbers(target_number.sid).update(
            sms_url=webhook_url,
            sms_method='POST'
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error configuring webhook: {str(e)}")
        return False

def validate_signalwire_webhook_request(request) -> bool:
    """Validate that the request came from SignalWire"""
    try:
        # Basic validation - in production, implement proper signature validation
        required_fields = ['From', 'To', 'Body']
        for field in required_fields:
            if field not in request.form:
                return False
        return True
    except:
        return False

def format_phone_display(phone_number: str) -> str:
    """Format phone number for display"""
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number

def format_phone_number(phone_number: str) -> str:
    """Format phone number to E.164 format"""
    cleaned = ''.join(filter(str.isdigit, phone_number))
    
    if len(cleaned) == 10:
        cleaned = '1' + cleaned
    
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    
    return cleaned

# Backward compatibility aliases
def validate_signalwire_request(request):
    return validate_signalwire_webhook_request(request)

def get_phone_number_info(phone_number: str):
    numbers = get_signalwire_phone_numbers()
    for number in numbers:
        if number['phone_number'] == phone_number:
            return number
    return None

def configure_webhook(phone_number_sid: str, webhook_url: str):
    try:
        client = get_signalwire_client()
        if not client:
            return False
        
        client.incoming_phone_numbers(phone_number_sid).update(
            sms_url=webhook_url,
            sms_method='POST'
        )
        return True
    except:
        return False
