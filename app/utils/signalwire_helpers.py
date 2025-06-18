# app/utils/signalwire_helpers.py - Enhanced SignalWire integration

import logging
from typing import Dict, List, Optional, Union
from signalwire.rest import Client
from flask import current_app
import os

logger = logging.getLogger(__name__)

def get_signalwire_client():
    """Get SignalWire client instance"""
    try:
        project_id = current_app.config.get('SIGNALWIRE_PROJECT_ID') or os.getenv('SIGNALWIRE_PROJECT_ID')
        auth_token = current_app.config.get('SIGNALWIRE_API_TOKEN') or os.getenv('SIGNALWIRE_API_TOKEN')
        space_url = current_app.config.get('SIGNALWIRE_SPACE_URL') or os.getenv('SIGNALWIRE_SPACE_URL')
        
        if not all([project_id, auth_token, space_url]):
            raise ValueError("Missing SignalWire configuration")
        
        client = Client(project_id, auth_token, signalwire_space_url=space_url)
        logger.info("SignalWire client initialized successfully")
        return client
        
    except Exception as e:
        logger.error(f"Failed to initialize SignalWire client: {str(e)}")
        raise


def get_available_phone_numbers(area_code: str = None, country: str = 'CA', limit: int = 20) -> List[Dict]:
    """Get available phone numbers from SignalWire"""
    try:
        client = get_signalwire_client()
        
        search_params = {
            'limit': limit,
            'sms_enabled': True
        }
        
        if area_code:
            search_params['area_code'] = area_code
            
        # Search for numbers based on country
        if country.upper() == 'CA':
            numbers = client.available_phone_numbers('CA').list(**search_params)
        else:
            numbers = client.available_phone_numbers('US').list(**search_params)
        
        # Format response
        formatted_numbers = []
        for num in numbers:
            formatted_numbers.append({
                'phone_number': num.phone_number,
                'locality': getattr(num, 'locality', None),
                'region': getattr(num, 'region', None),
                'capabilities': {
                    'sms': getattr(num, 'sms', True),
                    'mms': getattr(num, 'mms', True),
                    'voice': getattr(num, 'voice', True)
                },
                'price': '1.00'  # Default price
            })
        
        logger.info(f"Found {len(formatted_numbers)} available numbers for area code {area_code}")
        return formatted_numbers
        
    except Exception as e:
        logger.error(f"Error getting available numbers: {str(e)}")
        return []


def purchase_phone_number(phone_number: str, friendly_name: str = None) -> Optional[Dict]:
    """Purchase a phone number from SignalWire"""
    try:
        client = get_signalwire_client()
        
        purchase_params = {
            'phone_number': phone_number
        }
        
        if friendly_name:
            purchase_params['friendly_name'] = friendly_name
        
        # Purchase the number
        purchased_number = client.incoming_phone_numbers.create(**purchase_params)
        
        result = {
            'sid': purchased_number.sid,
            'phone_number': purchased_number.phone_number,
            'friendly_name': purchased_number.friendly_name,
            'status': 'active',
            'date_created': purchased_number.date_created,
            'capabilities': {
                'sms': True,
                'mms': True,
                'voice': True
            }
        }
        
        logger.info(f"Successfully purchased phone number: {phone_number}")
        return result
        
    except Exception as e:
        logger.error(f"Error purchasing phone number {phone_number}: {str(e)}")
        raise Exception(f"Failed to purchase phone number: {str(e)}")


def configure_number_webhook(phone_number: str, webhook_url: str) -> bool:
    """Configure webhook for a phone number"""
    try:
        client = get_signalwire_client()
        
        # Find the phone number
        numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if not numbers:
            raise Exception(f"Phone number {phone_number} not found in account")
        
        number = numbers[0]
        
        # Update webhook URL for SMS
        updated_number = number.update(
            sms_url=webhook_url,
            sms_method='POST',
            sms_fallback_url=f"{webhook_url}/fallback",
            sms_fallback_method='POST'
        )
        
        logger.info(f"Webhook configured for {phone_number}: {webhook_url}")
        return True
        
    except Exception as e:
        logger.error(f"Error configuring webhook for {phone_number}: {str(e)}")
        return False


def send_signalwire_sms(from_number: str, to_number: str, body: str) -> Optional[Dict]:
    """Send SMS via SignalWire"""
    try:
        client = get_signalwire_client()
        
        message = client.messages.create(
            from_=from_number,
            to=to_number,
            body=body
        )
        
        result = {
            'sid': message.sid,
            'status': message.status,
            'from': message.from_,
            'to': message.to,
            'body': message.body,
            'date_created': message.date_created
        }
        
        logger.info(f"SMS sent successfully: {message.sid}")
        return result
        
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")
        raise Exception(f"Failed to send SMS: {str(e)}")


def get_signalwire_phone_numbers() -> List[Dict]:
    """Get all phone numbers in the SignalWire account"""
    try:
        client = get_signalwire_client()
        numbers = client.incoming_phone_numbers.list()
        
        formatted_numbers = []
        for num in numbers:
            formatted_numbers.append({
                'phone_number': num.phone_number,
                'friendly_name': num.friendly_name,
                'sid': num.sid,
                'sms_url': getattr(num, 'sms_url', None),
                'voice_url': getattr(num, 'voice_url', None),
                'status': 'active',
                'capabilities': {
                    'sms': True,
                    'mms': True,
                    'voice': True
                },
                'date_created': num.date_created
            })
        
        return formatted_numbers
        
    except Exception as e:
        logger.error(f"Error getting SignalWire phone numbers: {str(e)}")
        return []


def validate_signalwire_webhook_request(request) -> bool:
    """Validate that request came from SignalWire"""
    try:
        from signalwire.request_validator import RequestValidator
        
        # Get signature from headers
        signature = request.headers.get('X-SignalWire-Signature', '')
        if not signature:
            logger.warning("No SignalWire signature found in request headers")
            return False
        
        # Get auth token
        auth_token = current_app.config.get('SIGNALWIRE_API_TOKEN')
        if not auth_token:
            logger.error("SignalWire auth token not configured")
            return False
        
        # Validate the request
        validator = RequestValidator(auth_token)
        is_valid = validator.validate(
            request.url,
            request.form,
            signature
        )
        
        if not is_valid:
            logger.warning("Invalid SignalWire signature")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"SignalWire request validation error: {str(e)}")
        return False


def get_signalwire_integration_status() -> Dict:
    """Get SignalWire integration status"""
    try:
        client = get_signalwire_client()
        
        # Test by getting account info
        account = client.api.v2010.accounts.get()
        
        return {
            'status': 'connected',
            'account_sid': account.sid,
            'friendly_name': account.friendly_name,
            'status_details': 'SignalWire integration is working properly'
        }
        
    except Exception as e:
        logger.error(f"SignalWire integration check failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e),
            'status_details': 'Failed to connect to SignalWire'
        }


def format_phone_number(phone_number: str) -> str:
    """Format phone number for display"""
    # Remove country code and formatting
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    # Format as (XXX) XXX-XXXX
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number


def get_number_details(phone_number: str) -> Optional[Dict]:
    """Get detailed information about a phone number"""
    try:
        client = get_signalwire_client()
        
        # Find the number in our account
        numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if numbers:
            num = numbers[0]
            return {
                'phone_number': num.phone_number,
                'sid': num.sid,
                'friendly_name': num.friendly_name,
                'sms_url': getattr(num, 'sms_url', None),
                'voice_url': getattr(num, 'voice_url', None),
                'capabilities': {
                    'sms': True,
                    'mms': True,
                    'voice': True
                },
                'date_created': num.date_created,
                'status': 'owned'
            }
        
        # If not in our account, check if it's available
        available_numbers = client.available_phone_numbers('CA').list(
            phone_number=phone_number,
            limit=1
        )
        
        if available_numbers:
            num = available_numbers[0]
            return {
                'phone_number': num.phone_number,
                'locality': getattr(num, 'locality', None),
                'region': getattr(num, 'region', None),
                'capabilities': {
                    'sms': getattr(num, 'sms', True),
                    'mms': getattr(num, 'mms', True),
                    'voice': getattr(num, 'voice', True)
                },
                'status': 'available'
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting number details for {phone_number}: {str(e)}")
        return None


# Legacy function aliases for backward compatibility
def send_sms(from_number: str, to_number: str, body: str) -> Optional[Dict]:
    """Legacy alias for send_signalwire_sms"""
    return send_signalwire_sms(from_number, to_number, body)


def validate_signalwire_request(request) -> bool:
    """Legacy alias for validate_signalwire_webhook_request"""
    return validate_signalwire_webhook_request(request)


def configure_webhook(phone_number: str, webhook_url: str) -> bool:
    """Legacy alias for configure_number_webhook"""
    return configure_number_webhook(phone_number, webhook_url)