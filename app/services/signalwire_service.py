# app/services/signalwire_service.py - Production SignalWire Service
"""
SignalWire Service - Production-ready implementation with proper error handling
"""
import os
import hmac
import hashlib
import time
import logging
from typing import Dict, Any, Optional, List
from signalwire.rest import Client as SignalWireClient
from signalwire.twiml import MessagingResponse, VoiceResponse
from twilio.request_validator import RequestValidator
from flask import current_app, request

logger = logging.getLogger(__name__)

class SignalWireConfig:
    """SignalWire configuration management"""
    
    def __init__(self):
        self.project_id = os.getenv('SIGNALWIRE_PROJECT_ID')
        self.auth_token = os.getenv('SIGNALWIRE_AUTH_TOKEN') 
        self.space_url = os.getenv('SIGNALWIRE_SPACE_URL')
        self.webhook_base_url = os.getenv('WEBHOOK_BASE_URL', 'https://backend.assitext.ca')
        
        if not all([self.project_id, self.auth_token, self.space_url]):
            raise ValueError("Missing required SignalWire configuration")

class SignalWireErrorHandler:
    """Production error handling for SignalWire operations"""
    
    @staticmethod
    def handle_api_error(func):
        """Decorator for handling SignalWire API errors"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"SignalWire API error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                
                # Return structured error response
                return {
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'function': func.__name__
                }
        return wrapper

class SignalWireService:
    """Production SignalWire service implementation"""
    
    def __init__(self):
        self.config = SignalWireConfig()
        self.client = None
        self.validator = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize SignalWire client and validator"""
        try:
            self.client = SignalWireClient(
                self.config.project_id,
                self.config.auth_token,
                signalwire_space_url=self.config.space_url
            )
            
            self.validator = RequestValidator(self.config.auth_token)
            
            # Test connection
            account = self.client.api.account.fetch()
            logger.info(f"✅ SignalWire connected: {account.friendly_name}")
            
        except Exception as e:
            logger.error(f"❌ SignalWire initialization failed: {e}")
            raise
    
    @SignalWireErrorHandler.handle_api_error
    def search_phone_numbers(self, country_code: str = 'US', area_code: str = None, 
                           city: str = None, limit: int = 10) -> Dict[str, Any]:
        """Search available phone numbers"""
        search_params = {'limit': limit}
        
        if area_code:
            search_params['area_code'] = area_code
        if city:
            search_params['in_locality'] = city
        
        numbers = self.client.available_phone_numbers(country_code).local.list(**search_params)
        
        return {
            'success': True,
            'numbers': [{
                'phone_number': num.phone_number,
                'friendly_name': num.friendly_name,
                'capabilities': {
                    'voice': num.capabilities.get('voice', False),
                    'sms': num.capabilities.get('sms', False),
                    'mms': num.capabilities.get('mms', False)
                },
                'rate_center': getattr(num, 'rate_center', None),
                'region': getattr(num, 'region', None)
            } for num in numbers],
            'count': len(numbers)
        }
    
    @SignalWireErrorHandler.handle_api_error
    def purchase_phone_number(self, phone_number: str, friendly_name: str = None,
                            webhook_urls: Dict[str, str] = None) -> Dict[str, Any]:
        """Purchase phone number with webhook configuration"""
        
        purchase_config = {
            'phone_number': phone_number,
            'friendly_name': friendly_name or f"AssisText {phone_number}"
        }
        
        # Configure webhooks
        if webhook_urls:
            webhook_config = self._build_webhook_config(webhook_urls)
            purchase_config.update(webhook_config)
        else:
            # Default webhook configuration
            purchase_config.update({
                'sms_url': f"{self.config.webhook_base_url}/api/webhooks/sms",
                'sms_method': 'POST',
                'voice_url': f"{self.config.webhook_base_url}/api/webhooks/voice",
                'voice_method': 'POST',
                'status_callback': f"{self.config.webhook_base_url}/api/webhooks/status",
                'status_callback_method': 'POST'
            })
        
        purchased_number = self.client.incoming_phone_numbers.create(**purchase_config)
        
        return {
            'success': True,
            'number_sid': purchased_number.sid,
            'phone_number': purchased_number.phone_number,
            'friendly_name': purchased_number.friendly_name,
            'capabilities': {
                'voice': purchased_number.capabilities.get('voice', False),
                'sms': purchased_number.capabilities.get('sms', False),
                'mms': purchased_number.capabilities.get('mms', False)
            },
            'webhook_urls': {
                'sms_url': purchased_number.sms_url,
                'voice_url': purchased_number.voice_url,
                'status_callback': purchased_number.status_callback
            }
        }
    
    @SignalWireErrorHandler.handle_api_error
    def send_sms(self, from_number: str, to_number: str, body: str, 
                media_url: List[str] = None) -> Dict[str, Any]:
        """Send SMS message"""
        
        message_config = {
            'from_': from_number,
            'to': to_number,
            'body': body,
            'status_callback': f"{self.config.webhook_base_url}/api/webhooks/status"
        }
        
        if media_url:
            message_config['media_url'] = media_url
        
        message = self.client.messages.create(**message_config)
        
        return {
            'success': True,
            'message_sid': message.sid,
            'status': message.status,
            'from_number': message.from_,
            'to_number': message.to,
            'body': message.body,
            'price': message.price,
            'direction': message.direction,
            'date_created': message.date_created.isoformat() if message.date_created else None
        }
    
    @SignalWireErrorHandler.handle_api_error
    def get_message_status(self, message_sid: str) -> Dict[str, Any]:
        """Get message delivery status"""
        message = self.client.messages(message_sid).fetch()
        
        return {
            'success': True,
            'message_sid': message.sid,
            'status': message.status,
            'error_code': message.error_code,
            'error_message': message.error_message,
            'price': message.price,
            'date_sent': message.date_sent.isoformat() if message.date_sent else None,
            'date_updated': message.date_updated.isoformat() if message.date_updated else None
        }
    
    def validate_webhook_signature(self, url: str, params: Dict[str, Any], 
                                  signature: str) -> bool:
        """Validate SignalWire webhook signature"""
        try:
            # Skip validation in development if configured
            if os.getenv('SKIP_WEBHOOK_VALIDATION', 'false').lower() == 'true':
                logger.warning("⚠️ Webhook signature validation skipped (development mode)")
                return True
            
            return self.validator.validate(url, params, signature)
        except Exception as e:
            logger.error(f"❌ Webhook signature validation error: {e}")
            return False
    
    def create_messaging_response(self, message: str, to_number: str = None,
                                from_number: str = None, media_url: str = None) -> str:
        """Create cXML messaging response"""
        response = MessagingResponse()
        
        message_kwargs = {}
        if to_number:
            message_kwargs['to'] = to_number
        if from_number:
            message_kwargs['from_'] = from_number
        if media_url:
            message_kwargs['media'] = media_url
        
        response.message(message, **message_kwargs)
        return str(response)
    
    def create_voice_response(self, message: str, voice: str = 'alice',
                            language: str = 'en-US') -> str:
        """Create cXML voice response"""
        response = VoiceResponse()
        response.say(message, voice=voice, language=language)
        return str(response)
    
    def _build_webhook_config(self, webhook_urls: Dict[str, str]) -> Dict[str, str]:
        """Build webhook configuration from provided URLs"""
        config = {}
        
        if 'sms_url' in webhook_urls:
            config['sms_url'] = webhook_urls['sms_url']
            config['sms_method'] = 'POST'
        
        if 'voice_url' in webhook_urls:
            config['voice_url'] = webhook_urls['voice_url']
            config['voice_method'] = 'POST'
        
        if 'status_callback' in webhook_urls:
            config['status_callback'] = webhook_urls['status_callback']
            config['status_callback_method'] = 'POST'
        
        return config
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get SignalWire account information"""
        try:
            account = self.client.api.account.fetch()
            return {
                'success': True,
                'account_sid': account.sid,
                'friendly_name': account.friendly_name,
                'status': account.status,
                'type': account.type
            }
        except Exception as e:
            logger.error(f"❌ Failed to get account info: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_phone_numbers(self) -> Dict[str, Any]:
        """List all purchased phone numbers"""
        try:
            numbers = self.client.incoming_phone_numbers.list()
            return {
                'success': True,
                'numbers': [{
                    'sid': num.sid,
                    'phone_number': num.phone_number,
                    'friendly_name': num.friendly_name,
                    'capabilities': {
                        'voice': num.capabilities.get('voice', False),
                        'sms': num.capabilities.get('sms', False),
                        'mms': num.capabilities.get('mms', False)
                    },
                    'webhook_urls': {
                        'sms_url': num.sms_url,
                        'voice_url': num.voice_url,
                        'status_callback': num.status_callback
                    }
                } for num in numbers],
                'count': len(numbers)
            }
        except Exception as e:
            logger.error(f"❌ Failed to list phone numbers: {e}")
            return {'success': False, 'error': str(e)}
    
    def release_phone_number(self, number_sid: str) -> Dict[str, Any]:
        """Release (delete) a phone number"""
        try:
            self.client.incoming_phone_numbers(number_sid).delete()
            return {
                'success': True,
                'message': f'Phone number {number_sid} released successfully'
            }
        except Exception as e:
            logger.error(f"❌ Failed to release phone number {number_sid}: {e}")
            return {'success': False, 'error': str(e)}

# Utility functions for external use
def test_signalwire_connection() -> bool:
    """Test SignalWire API connectivity"""
    try:
        service = SignalWireService()
        result = service.get_account_info()
        return result.get('success', False)
    except Exception as e:
        logger.error(f"❌ SignalWire connection test failed: {e}")
        return False

def get_signalwire_client() -> SignalWireService:
    """Get SignalWire service instance"""
    return SignalWireService()