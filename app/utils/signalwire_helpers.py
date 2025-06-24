# app/utils/signalwire_helpers.py - Enhanced SignalWire integration helpers

from signalwire.rest import Client
from flask import current_app
import logging
import requests
from typing import Dict, List, Optional, Tuple
import os
from datetime import datetime

logger = logging.getLogger(__name__)

def get_signalwire_client() -> Optional[Client]:
    """
    Get configured SignalWire client with error handling
    Returns None if configuration is invalid
    """
    try:
        # Get credentials from environment or app config
        project_id = os.getenv('SIGNALWIRE_PROJECT_ID') or current_app.config.get('SIGNALWIRE_PROJECT_ID')
        api_token = os.getenv('SIGNALWIRE_API_TOKEN') or current_app.config.get('SIGNALWIRE_API_TOKEN') 
        space_url = os.getenv('SIGNALWIRE_SPACE_URL') or current_app.config.get('SIGNALWIRE_SPACE_URL')
        
        if not all([project_id, api_token, space_url]):
            logger.error("Missing SignalWire credentials. Required: PROJECT_ID, API_TOKEN, SPACE_URL")
            return None
        
        # Create and test client
        client = Client(
            project_id, 
            api_token, 
            signalwire_space_url=space_url
        )
        
        # Test connection by fetching account info
        try:
            account = client.api.accounts(project_id).fetch()
            logger.info(f"SignalWire client connected successfully. Account: {account.friendly_name}")
            return client
        except Exception as test_error:
            logger.error(f"SignalWire client test failed: {str(test_error)}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to create SignalWire client: {str(e)}")
        return None


def search_available_numbers(
    country: str = 'CA',
    area_code: str = None, 
    city: str = None,
    limit: int = 20,
    sms_enabled: bool = True,
    voice_enabled: bool = True
) -> Tuple[List[Dict], str]:
    """
    Search for available phone numbers with comprehensive error handling
    Returns: (list_of_numbers, error_message)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return [], "SignalWire service unavailable"
        
        search_params = {
            'limit': limit,
            'sms_enabled': sms_enabled,
            'voice_enabled': voice_enabled
        }
        
        if area_code:
            search_params['area_code'] = area_code
        
        # For Canadian numbers, search by region if city provided
        if country == 'CA' and city:
            province = get_province_for_city(city)
            if province:
                search_params['in_region'] = province
        
        logger.info(f"Searching {country} numbers with params: {search_params}")
        
        # Execute search
        available_numbers = client.available_phone_numbers(country).list(**search_params)
        
        if not available_numbers:
            return [], f"No available numbers found for the specified criteria"
        
        # Format results
        formatted_numbers = []
        for number in available_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'locality': getattr(number, 'locality', city or 'Unknown'),
                'region': getattr(number, 'region', get_province_for_city(city) if city else 'Unknown'),
                'country': country,
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                },
                'setup_cost': get_setup_cost(country),
                'monthly_cost': get_monthly_cost(country),
                'is_toll_free': is_toll_free_number(number.phone_number)
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
    Purchase a phone number and optionally configure webhook
    Returns: (purchased_number_data, error_message)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return None, "SignalWire service unavailable"
        
        # Purchase the number
        logger.info(f"Purchasing phone number: {phone_number}")
        
        purchase_params = {
            'phone_number': phone_number
        }
        
        if friendly_name:
            purchase_params['friendly_name'] = friendly_name
        
        # Configure webhook during purchase if provided
        if webhook_url:
            purchase_params['sms_url'] = webhook_url
            purchase_params['sms_method'] = 'POST'
            purchase_params['voice_url'] = webhook_url
            purchase_params['voice_method'] = 'POST'
        
        purchased_number = client.incoming_phone_numbers.create(**purchase_params)
        
        result_data = {
            'phone_number': purchased_number.phone_number,
            'friendly_name': purchased_number.friendly_name,
            'sid': purchased_number.sid,
            'capabilities': {
                'sms': purchased_number.capabilities.get('sms', True),
                'mms': purchased_number.capabilities.get('mms', True), 
                'voice': purchased_number.capabilities.get('voice', True)
            },
            'webhook_configured': webhook_url is not None,
            'status': 'active',
            'purchased_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Successfully purchased number {phone_number} with SID {purchased_number.sid}")
        return result_data, ""
        
    except Exception as e:
        error_msg = f"Failed to purchase phone number {phone_number}: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


def configure_number_webhook(phone_number_sid: str, webhook_url: str) -> Tuple[bool, str]:
    """
    Configure webhook for an existing phone number
    Returns: (success, error_message)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return False, "SignalWire service unavailable"
        
        # Update the phone number with webhook configuration
        updated_number = client.incoming_phone_numbers(phone_number_sid).update(
            sms_url=webhook_url,
            sms_method='POST',
            voice_url=webhook_url, 
            voice_method='POST'
        )
        
        logger.info(f"Webhook configured for number {updated_number.phone_number}: {webhook_url}")
        return True, ""
        
    except Exception as e:
        error_msg = f"Failed to configure webhook: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def validate_phone_number_availability(phone_number: str) -> Tuple[bool, str, Dict]:
    """
    Check if a specific phone number is still available for purchase
    Returns: (is_available, error_message, number_details)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return False, "SignalWire service unavailable", {}
        
        country = 'CA' if phone_number.startswith('+1') else 'US'
        
        # Search for this specific number
        available_numbers = client.available_phone_numbers(country).list(
            phone_number=phone_number,
            limit=1
        )
        
        if available_numbers:
            number = available_numbers[0]
            number_details = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'locality': getattr(number, 'locality', 'Unknown'),
                'region': getattr(number, 'region', 'Unknown'),
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                }
            }
            return True, "", number_details
        else:
            return False, "Number no longer available", {}
            
    except Exception as e:
        error_msg = f"Failed to validate number availability: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, {}


def get_purchased_numbers() -> Tuple[List[Dict], str]:
    """
    Get all purchased phone numbers for the account
    Returns: (list_of_numbers, error_message)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return [], "SignalWire service unavailable"
        
        phone_numbers = client.incoming_phone_numbers.list()
        
        formatted_numbers = []
        for number in phone_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'friendly_name': number.friendly_name,
                'sid': number.sid,
                'capabilities': number.capabilities,
                'sms_url': getattr(number, 'sms_url', None),
                'voice_url': getattr(number, 'voice_url', None),
                'status': getattr(number, 'status', 'active'),
                'date_created': number.date_created.isoformat() if number.date_created else None
            }
            formatted_numbers.append(formatted_number)
        
        return formatted_numbers, ""
        
    except Exception as e:
        error_msg = f"Failed to get purchased numbers: {str(e)}"
        logger.error(error_msg)
        return [], error_msg


# ========== UTILITY FUNCTIONS ==========

def format_phone_display(phone_number: str) -> str:
    """Format phone number for display as (XXX) XXX-XXXX"""
    clean_number = phone_number
    if clean_number.startswith('+1'):
        clean_number = clean_number[2:]
    elif clean_number.startswith('1'):
        clean_number = clean_number[1:]
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number


def get_province_for_city(city: str) -> str:
    """Get Canadian province code for a city"""
    city_to_province = {
        'toronto': 'ON', 'ottawa': 'ON', 'mississauga': 'ON', 'london': 'ON', 'hamilton': 'ON',
        'montreal': 'QC', 'quebec_city': 'QC', 'gatineau': 'QC',
        'vancouver': 'BC', 'burnaby': 'BC', 'richmond': 'BC', 'surrey': 'BC',
        'calgary': 'AB', 'edmonton': 'AB', 'red_deer': 'AB',
        'winnipeg': 'MB', 'brandon': 'MB',
        'halifax': 'NS', 'sydney': 'NS',
        'saskatoon': 'SK', 'regina': 'SK',
        'fredericton': 'NB', 'moncton': 'NB',
        'charlottetown': 'PE',
        'st_johns': 'NL'
    }
    return city_to_province.get(city.lower(), 'ON')


def get_setup_cost(country: str) -> str:
    """Get setup cost based on country"""
    costs = {
        'US': '$1.00',
        'CA': '$1.00',  # Canadian numbers
        'GB': '$2.00'
    }
    return costs.get(country, '$1.00')


def get_monthly_cost(country: str) -> str:
    """Get monthly cost based on country"""
    costs = {
        'US': '$1.00',
        'CA': '$1.00',  # Canadian monthly cost
        'GB': '$3.00'
    }
    return costs.get(country, '$1.00')


def is_toll_free_number(phone_number: str) -> bool:
    """Check if number is toll-free"""
    toll_free_prefixes = ['+1800', '+1888', '+1877', '+1866', '+1855', '+1844', '+1833']
    return any(phone_number.startswith(prefix) for prefix in toll_free_prefixes)


def test_signalwire_connection() -> Tuple[bool, str, Dict]:
    """
    Test SignalWire connection and return account information
    Returns: (is_connected, error_message, account_info)
    """
    try:
        client = get_signalwire_client()
        if not client:
            return False, "Failed to create SignalWire client", {}
        
        # Test by fetching account information
        project_id = os.getenv('SIGNALWIRE_PROJECT_ID') or current_app.config.get('SIGNALWIRE_PROJECT_ID')
        account = client.api.accounts(project_id).fetch()
        
        account_info = {
            'friendly_name': account.friendly_name,
            'status': account.status,
            'type': account.type,
            'date_created': account.date_created.isoformat() if account.date_created else None
        }
        
        return True, "", account_info
        
    except Exception as e:
        error_msg = f"SignalWire connection test failed: {str(e)}"
        logger.error(error_msg)
        return False, error_msg, {}