"""
Unified SMS Service for SignalWire Integration
Consolidates all SMS functionality from utils into proper service layer
"""
import os
import logging
import hmac
import hashlib
import base64
from typing import Dict, List, Tuple, Optional
from flask import current_app, request
from datetime import datetime

logger = logging.getLogger(__name__)

class SMSService:
    """Unified SMS service for all provider operations"""
    
    def __init__(self):
        self.provider = 'signalwire'  # Primary provider
        self._client = None
    
    @property
    def client(self):
        """Lazy load SignalWire client"""
        if self._client is None:
            self._client = self._get_signalwire_client()
        return self._client
    
    def _get_signalwire_client(self):
        """Initialize SignalWire client"""
        try:
            from signalwire.rest import Client as SignalWireClient
            
            project_id = os.getenv('SIGNALWIRE_PROJECT_ID')
            api_token = os.getenv('SIGNALWIRE_API_TOKEN') 
            space_url = os.getenv('SIGNALWIRE_SPACE_URL')
            
            if not all([project_id, api_token, space_url]):
                logger.error("Missing SignalWire configuration")
                return None
                
            return SignalWireClient(
                project_id, 
                api_token, 
                signalwire_space_url=space_url
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize SignalWire client: {e}")
            return None
    
    def send_message(self, from_number: str, to_number: str, body: str) -> Tuple[bool, str, Dict]:
        """
        Send SMS message via SignalWire
        
        Returns:
            Tuple of (success, message_sid_or_error, message_data)
        """
        try:
            if not self.client:
                return False, "SMS service unavailable", {}
            
            message = self.client.messages.create(
                from_=from_number,
                to=to_number,
                body=body
            )
            
            message_data = {
                'sid': message.sid,
                'status': message.status,
                'direction': message.direction,
                'from': message.from_,
                'to': message.to,
                'body': message.body,
                'date_created': message.date_created.isoformat() if message.date_created else None
            }
            
            logger.info(f"Message sent successfully: {message.sid}")
            return True, message.sid, message_data
            
        except Exception as e:
            error_msg = f"Failed to send message: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def validate_webhook(self, request_obj=None) -> bool:
        """
        Validate SignalWire webhook signature
        """
        try:
            if request_obj is None:
                request_obj = request
            
            signature = request_obj.headers.get('X-SignalWire-Signature', '')
            if not signature:
                logger.warning("Missing SignalWire webhook signature")
                return False
            
            auth_token = os.getenv('SIGNALWIRE_API_TOKEN')
            if not auth_token:
                logger.error("SIGNALWIRE_API_TOKEN not configured")
                return False
            
            # Build validation string
            url = request_obj.url
            if request_obj.query_string:
                url += '?' + request_obj.query_string.decode('utf-8')
            
            # Get POST data and sort
            post_data = request_obj.form.to_dict()
            sorted_data = []
            for key in sorted(post_data.keys()):
                sorted_data.append(f"{key}{post_data[key]}")
            
            validation_string = url + ''.join(sorted_data)
            
            # Calculate expected signature
            expected_signature = base64.b64encode(
                hmac.new(
                    auth_token.encode('utf-8'),
                    validation_string.encode('utf-8'),
                    hashlib.sha256
                ).digest()
            ).decode('utf-8')
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Webhook validation error: {e}")
            return False
    
    def get_phone_numbers(self) -> List[Dict]:
        """Get list of SignalWire phone numbers"""
        try:
            if not self.client:
                return []
            
            numbers = self.client.incoming_phone_numbers.list()
            formatted_numbers = []
            
            for number in numbers:
                formatted_number = {
                    'sid': number.sid,
                    'phone_number': number.phone_number,
                    'friendly_name': number.friendly_name,
                    'sms_url': number.sms_url,
                    'voice_url': number.voice_url,
                    'capabilities': {
                        'sms': getattr(number, 'sms_enabled', True),
                        'mms': getattr(number, 'mms_enabled', True),
                        'voice': getattr(number, 'voice_enabled', True)
                    }
                }
                formatted_numbers.append(formatted_number)
            
            return formatted_numbers
            
        except Exception as e:
            logger.error(f"Failed to get phone numbers: {e}")
            return []
    
    def search_available_numbers(self, area_code: str = None, contains: str = None) -> List[Dict]:
        """Search for available phone numbers"""
        try:
            if not self.client:
                return []
            
            search_params = {}
            if area_code:
                search_params['area_code'] = area_code
            if contains:
                search_params['contains'] = contains
            
            numbers = self.client.available_phone_numbers('US').local.list(**search_params)
            
            available_numbers = []
            for number in numbers:
                available_numbers.append({
                    'phone_number': number.phone_number,
                    'locality': number.locality,
                    'region': number.region,
                    'capabilities': {
                        'sms': number.capabilities.get('sms', False),
                        'mms': number.capabilities.get('mms', False),
                        'voice': number.capabilities.get('voice', False)
                    }
                })
            
            return available_numbers[:10]  # Limit results
            
        except Exception as e:
            logger.error(f"Failed to search available numbers: {e}")
            return []
    
    def purchase_phone_number(self, phone_number: str, webhook_urls: Dict = None) -> Tuple[bool, str]:
        """Purchase a phone number and configure webhooks"""
        try:
            if not self.client:
                return False, "SMS service unavailable"
            
            purchase_params = {'phone_number': phone_number}
            
            if webhook_urls:
                if 'sms_url' in webhook_urls:
                    purchase_params['sms_url'] = webhook_urls['sms_url']
                if 'voice_url' in webhook_urls:
                    purchase_params['voice_url'] = webhook_urls['voice_url']
                if 'status_callback' in webhook_urls:
                    purchase_params['status_callback'] = webhook_urls['status_callback']
            
            purchased_number = self.client.incoming_phone_numbers.create(**purchase_params)
            
            logger.info(f"Successfully purchased number: {purchased_number.phone_number}")
            return True, purchased_number.sid
            
        except Exception as e:
            error_msg = f"Failed to purchase phone number: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def configure_webhooks(self, phone_number_sid: str, webhook_config: Dict) -> Tuple[bool, str]:
        """Configure webhooks for an existing phone number"""
        try:
            if not self.client:
                return False, "SMS service unavailable"
            
            phone_number = self.client.incoming_phone_numbers(phone_number_sid).update(
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

# Create singleton instance
sms_service = SMSService()

# Export functions for backward compatibility
def send_sms(from_number: str, to_number: str, body: str) -> Tuple[bool, str, Dict]:
    """Backward compatible function"""
    return sms_service.send_message(from_number, to_number, body)

def validate_signalwire_webhook(request_obj=None) -> bool:
    """Backward compatible function"""
    return sms_service.validate_webhook(request_obj)

def get_signalwire_phone_numbers() -> List[Dict]:
    """Backward compatible function"""
    return sms_service.get_phone_numbers()

def get_available_phone_numbers(area_code: str = None) -> List[Dict]:
    """Backward compatible function"""
    return sms_service.search_available_numbers(area_code=area_code)

def purchase_phone_number(phone_number: str, webhook_urls: Dict = None) -> Tuple[bool, str]:
    """Backward compatible function"""
    return sms_service.purchase_phone_number(phone_number, webhook_urls)

def configure_number_webhook(phone_number_sid: str, webhook_config: Dict) -> Tuple[bool, str]:
    """Backward compatible function"""
    return sms_service.configure_webhooks(phone_number_sid, webhook_config)
