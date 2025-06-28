from signalwire.rest import Client as SignalWireClient
from flask import current_app
from typing import Optional, Dict, Tuple, List
import logging
import datetime;



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

def search_available_numbers(
    area_code: str = None,
    city: str = None,
    country: str = 'CA',
    limit: int = 5
) -> Tuple[List[Dict], str]:
    """
    Search for available phone numbers
    Returns: (list_of_numbers, error_message)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return [], "SignalWire service unavailable"
        
        search_params = {
            'limit': limit,
            'sms_enabled': True
        }
        
        if area_code:
            search_params['area_code'] = area_code
        
        # Search for numbers
        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').list(**search_params)
        
        # Format results
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
        
        logger.info(f"Found {len(formatted_numbers)} available numbers")
        return formatted_numbers, ""
        
    except Exception as e:
        error_msg = f"Failed to search available numbers: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

def purchase_phone_number(
    phone_number: str, 
    friendly_name: str = None,
    webhook_url: str = None
) -> Tuple[Optional[Dict], str]:
    """
    Purchase a phone number and configure webhook
    Returns: (purchased_number_data, error_message)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return None, "SignalWire service unavailable"
        
        logger.info(f"Purchasing phone number: {phone_number}")
        
        purchase_params = {
            'phone_number': phone_number
        }
        
        if friendly_name:
            purchase_params['friendly_name'] = friendly_name
        
        # Configure webhook during purchase
        if webhook_url:
            purchase_params['sms_url'] = webhook_url
            purchase_params['sms_method'] = 'POST'
            purchase_params['status_callback'] = webhook_url
            purchase_params['status_callback_method'] = 'POST'
        
        # Purchase the number
        purchased_number = client.incoming_phone_numbers.create(**purchase_params)
        
        result_data = {
            'phone_number': purchased_number.phone_number,
            'friendly_name': purchased_number.friendly_name,
            'sid': purchased_number.sid,
            'capabilities': {
                'sms': True,
                'mms': True, 
                'voice': True
            },
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
