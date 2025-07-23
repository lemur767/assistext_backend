"""
SignalWire Client - Production Implementation
Based on SignalWire Official Documentation
"""
import os
import hmac
import hashlib
import time
import logging
from typing import Dict, Any, Optional, List
from signalwire.rest import Client
from twilio.base.exceptions import TwilioRestException
from functools import wraps
from flask import current_app

class SignalWireConfig:
    """SignalWire configuration management"""
    
    def __init__(self):
        self.project_id = os.getenv('SIGNALWIRE_PROJECT')
        self.auth_token = os.getenv('SIGNALWIRE_TOKEN')
        self.space_url = os.getenv('SIGNALWIRE_SPACE')
        self.webhook_base_url = os.getenv('WEBHOOK_BASE_URL')
        self.webhook_secret = os.getenv('WEBHOOK_SECRET')
        
        if not all([self.project_id, self.auth_token, self.space_url]):
            raise ValueError("Missing required SignalWire credentials")

class SignalWireErrorHandler:
    """Production error handling for SignalWire operations"""
    
    ERROR_CODES = {
        # Authentication errors
        20003: "Authentication failed - verify Project ID and Auth Token",
        20005: "Account suspended or inactive",
        20429: "Rate limit exceeded - implement backoff strategy",
        
        # Phone number errors
        21211: "Invalid 'To' phone number format",
        21212: "Invalid 'From' phone number - not owned or verified",
        21214: "Phone number not found in account",
        
        # Message errors
        21608: "Message body exceeds 1600 character limit",
        21610: "Cannot send SMS to landline numbers",
        21611: "Message blocked - recipient has opted out",
        21614: "Invalid 'From' number for SMS - not SMS-enabled",
        
        # Network errors
        30007: "Message delivery failure - carrier rejected",
        30008: "Message delivery unknown - no delivery receipt",
    }
    
    RETRYABLE_ERRORS = [20429, 30007, 30008, 500, 502, 503, 504]
    
    @classmethod
    def handle_error(cls, e: Exception, operation: str) -> Dict[str, Any]:
        """Handle SignalWire exceptions with detailed logging"""
        
        if isinstance(e, TwilioRestException):
            error_code = e.code
            error_message = cls.ERROR_CODES.get(error_code, f"Unknown error: {error_code}")
            is_retryable = error_code in cls.RETRYABLE_ERRORS
            
            if current_app:
                level = logging.WARNING if is_retryable else logging.ERROR
                current_app.logger.log(level, f"{operation} failed: [{error_code}] {error_message}")
            
            return {
                'success': False,
                'error_code': error_code,
                'error_message': error_message,
                'retryable': is_retryable,
                'operation': operation
            }
        else:
            if current_app:
                current_app.logger.error(f"Unexpected error in {operation}: {str(e)}")
            return {
                'success': False,
                'error_message': str(e),
                'retryable': False,
                'operation': operation
            }

def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for retry logic with exponential backoff"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_info = SignalWireErrorHandler.handle_error(e, func.__name__)
                    
                    if error_info['retryable'] and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        if current_app:
                            current_app.logger.info(f"Retrying {func.__name__} in {delay}s")
                        time.sleep(delay)
                        continue
                    else:
                        return error_info
            
            return SignalWireErrorHandler.handle_error(last_exception, func.__name__)
        return wrapper
    return decorator

class SignalWireClient:
    """Production SignalWire client implementation"""
    
    def __init__(self):
        self.config = SignalWireConfig()
        self.client = Client(
            self.config.project_id,
            self.config.auth_token,
            signalwire_space_url=self.config.space_url
        )
        
        if current_app:
            current_app.logger.info("SignalWire client initialized successfully")
    
    def validate_webhook_signature(self, request_url: str, post_vars: dict, signature: str) -> bool:
        """Validate webhook signature for security"""
        try:
            from signalwire.request_validator import RequestValidator
            validator = RequestValidator(self.config.auth_token)
            return validator.validate(request_url, post_vars, signature)
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Signature validation failed: {e}")
            return False
    
    def search_available_numbers(self, search_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Search for available phone numbers using SignalWire API"""
        try:
            country = search_criteria.get('country', 'US')
            
            # Use the SignalWire SDK to search for numbers
            if country.upper() == 'US':
                numbers = self.client.available_phone_numbers('US').local.list(
                    area_code=search_criteria.get('area_code'),
                    contains=search_criteria.get('contains'),
                    in_locality=search_criteria.get('city'),
                    in_region=search_criteria.get('region'),
                    sms_enabled=True,
                    voice_enabled=True,
                    limit=search_criteria.get('limit', 20)
                )
            elif country.upper() == 'CA':
                numbers = self.client.available_phone_numbers('CA').local.list(
                    area_code=search_criteria.get('area_code'),
                    contains=search_criteria.get('contains'),
                    in_locality=search_criteria.get('city'),
                    in_region=search_criteria.get('region'),
                    sms_enabled=True,
                    voice_enabled=True,
                    limit=search_criteria.get('limit', 20)
                )
            
            # Format the results
            formatted_numbers = []
            for number in numbers:
                formatted_numbers.append({
                    'phone_number': number.phone_number,
                    'formatted_number': number.friendly_name or number.phone_number,
                    'locality': number.locality,
                    'region': number.region,
                    'country': country.upper(),
                    'capabilities': {
                        'sms': getattr(number.capabilities, 'SMS', True),
                        'mms': getattr(number.capabilities, 'MMS', True),
                        'voice': getattr(number.capabilities, 'voice', True)
                    },
                    'monthly_cost': '$1.00'
                })
            
            return {
                'success': True,
                'numbers': formatted_numbers,
                'count': len(formatted_numbers),
                'search_criteria': search_criteria
            }
            
        except Exception as e:
            logging.error(f"Number search failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def purchase_phone_number(self, phone_number: str, webhook_config: Dict[str, str]) -> Dict[str, Any]:
        """Purchase a phone number with webhook configuration"""
        try:
            # Purchase the number with webhook URLs
            purchased_number = self.client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=webhook_config.get('friendly_name', 'AssisText Number'),
                sms_url=f"https://backend.assitext.ca/api/webhooks/sms",
                sms_method='POST',
                voice_url=f"https://backend.assitext.ca/api/webhooks/voice",
                voice_method='POST',
                status_callback=f"https://backend.assitext.ca/api/webhooks/status",
                status_callback_method='POST'
            )
            
            logging.info(f"Successfully purchased: {purchased_number.phone_number}")
            
            return {
                'success': True,
                'phone_number_sid': purchased_number.sid,
                'phone_number': purchased_number.phone_number,
                'friendly_name': purchased_number.friendly_name,
                'capabilities': purchased_number.capabilities,
                'sms_url': purchased_number.sms_url,
                'voice_url': purchased_number.voice_url,
                'status_callback': purchased_number.status_callback
            }
            
        except Exception as e:
            logging.error(f"Phone number purchase failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def send_sms_message(self, from_number: str, to_number: str, message_body: str) -> Dict[str, Any]:
        """Send an SMS message"""
        try:
            message = self.client.messages.create(
                from_=from_number,
                to=to_number,
                body=message_body,
                status_callback=f"https://backend.assitext.ca/api/webhooks/status"
            )
            
            logging.info(f"SMS sent successfully: {message.sid}")
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'from_number': message.from_,
                'to_number': message.to,
                'body': message.body,
                'direction': message.direction
            }
            
        except Exception as e:
            logging.error(f"SMS send failed: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_message_status(self, message_sid: str) -> Dict[str, Any]:
        """Get the status of a sent message"""
        try:
            message = self.client.messages(message_sid).fetch()
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'error_code': message.error_code,
                'error_message': message.error_message,
                'date_sent': message.date_sent,
                'date_updated': message.date_updated
            }
            
        except Exception as e:
            logging.error(f"Message status fetch failed: {str(e)}")
            return {'success': False, 'error': str(e)}

# Global client instance
_signalwire_client = None

def get_signalwire_client() -> SignalWireClient:
    """Get or create SignalWire client instance"""
    global _signalwire_client
    
    if _signalwire_client is None:
        _signalwire_client = SignalWireClient()
    
    return _signalwire_client
