

from signalwire.rest import Client as SignalWireClient
from flask import current_app
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def get_signalwire_client() -> Optional[SignalWireClient]:
    """Get configured SignalWire client - FIXED VERSION"""
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
    """Search for available phone numbers with proper regional parameters - FIXED VERSION"""
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
        

        if country.upper() == 'CA' and city:
            # Map cities to provinces  
            city_to_province = {
                'toronto': 'ON', 'ottawa': 'ON', 'mississauga': 'ON', 'london': 'ON', 'hamilton': 'ON',
                'burlington': 'ON', 'niagara': 'ON',
                'montreal': 'QC', 'quebec_city': 'QC',
                'vancouver': 'BC',
                'calgary': 'AB', 'edmonton': 'AB',
                'winnipeg': 'MB',
                'halifax': 'NS',
                'saskatoon': 'SK', 'regina': 'SK',
                'st_johns': 'NL'
            }
            
            province = city_to_province.get(city.lower(), 'ON')
            search_params['in_region'] = province
            search_params['in_locality'] = city.title()
        
        logger.info(f"Search params: {search_params}")
        
    
        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').local.list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').local.list(**search_params)
        
        logger.info(f"Found {len(available_numbers)} numbers from SignalWire")
        
        # Format results
        formatted_numbers = []
        for number in available_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'locality': getattr(number, 'locality', city or 'Unknown'),
                'region': getattr(number, 'region', search_params.get('in_region', 'ON')),
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
        logger.error(f"Failed to search available numbers: {str(e)}")
        return [], f"Failed to search available numbers: {str(e)}"

def format_phone_display(phone_number: str) -> str:
   
    if not phone_number:
        return ""
        
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number

def purchase_phone_number(phone_number: str, friendly_name: str = None, webhook_url: str = None) -> Tuple[Optional[Dict], str]:
    """Purchase a phone number from SignalWire - FIXED VERSION"""
    try:
        client = get_signalwire_client()
        if not client:
            return None, "SignalWire service unavailable"
        
        purchase_data = {
            'phone_number': phone_number,
            'friendly_name': friendly_name or f"Purchased Number {phone_number}"
        }
        
        if webhook_url:
            purchase_data['sms_url'] = webhook_url
            purchase_data['sms_method'] = 'POST'
        
        purchased_number = client.incoming_phone_numbers.create(**purchase_data)
        
        return {
            'phone_number': purchased_number.phone_number,
            'sid': purchased_number.sid,
            'friendly_name': purchased_number.friendly_name,
            'status': 'purchased'
        }, ""
        
    except Exception as e:
        logger.error(f"Failed to purchase phone number {phone_number}: {str(e)}")
        return None, f"Failed to purchase phone number: {str(e)}"

def configure_number_webhook(phone_number_sid: str, webhook_url: str) -> Tuple[bool, str]:
    """Configure webhook for a purchased phone number - FIXED VERSION"""
    try:
        client = get_signalwire_client()
        if not client:
            return False, "SignalWire service unavailable"
        
        # Update the phone number with webhook configuration
        phone_number = client.incoming_phone_numbers(phone_number_sid).update(
            sms_url=webhook_url,
            sms_method='POST'
        )
        
        logger.info(f"Webhook configured for {phone_number.phone_number}: {webhook_url}")
        return True, ""
        
    except Exception as e:
        logger.error(f"Failed to configure webhook for {phone_number_sid}: {str(e)}")
        return False, f"Failed to configure webhook: {str(e)}"

def get_signalwire_phone_numbers() -> List[Dict]:
    """Get all phone numbers owned by the account - FIXED VERSION"""
    try:
        client = get_signalwire_client()
        if not client:
            logger.error("SignalWire client not available")
            return []
        
        phone_numbers = client.incoming_phone_numbers.list()
        
        formatted_numbers = []
        for number in phone_numbers:
            formatted_numbers.append({
                'phone_number': number.phone_number,
                'friendly_name': number.friendly_name,
                'sid': number.sid,
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                },
                'date_created': number.date_created.isoformat() if number.date_created else None,
                'sms_url': getattr(number, 'sms_url', None),
                'voice_url': getattr(number, 'voice_url', None)
            })
        
        return formatted_numbers
        
    except Exception as e:
        logger.error(f"Error retrieving SignalWire phone numbers: {str(e)}")
        return []

def validate_signalwire_webhook_request(request_url: str, post_vars: dict, signature: str) -> bool:
    """Validate webhook signature for security - FIXED VERSION"""
    try:
        from signalwire.request_validator import RequestValidator
        
        auth_token = current_app.config.get('SIGNALWIRE_AUTH_TOKEN')
        if not auth_token:
            logger.error("SignalWire auth token not configured")
            return False
        
        validator = RequestValidator(auth_token)
        return validator.validate(request_url, post_vars, signature)
        
    except Exception as e:
        logger.error(f"Webhook signature validation failed: {str(e)}")
        return False

def send_sms(from_number: str, to_number: str, message: str) -> Tuple[Optional[Dict], str]:
    """Send SMS message using SignalWire - FIXED VERSION"""
    try:
        client = get_signalwire_client()
        if not client:
            return None, "SignalWire service unavailable"
        
        message_obj = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        
        return {
            'message_sid': message_obj.sid,
            'from': message_obj.from_,
            'to': message_obj.to,
            'body': message_obj.body,
            'status': message_obj.status,
            'date_created': message_obj.date_created.isoformat() if message_obj.date_created else None
        }, ""
        
    except Exception as e:
        logger.error(f"Failed to send SMS from {from_number} to {to_number}: {str(e)}")
        return None, f"Failed to send SMS: {str(e)}"

# Log successful loading
logger.info("✅ Fixed SignalWire helpers loaded successfully")