import os
import logging
import hmac
import hashlib
from typing import Dict, Any, List, Optional
from functools import wraps
from datetime import datetime

from flask import current_app, request
from signalwire.rest import Client as SignalWireRestClient
from signalwire.rest.exceptions import TwilioException
from signalwire.request_validator import RequestValidator

from app.extensions import db
from app.models import User


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
    def handle_error(e: Exception, operation: str) -> Dict[str, Any]:
        """Handle SignalWire API errors with proper logging"""
        error_msg = str(e)
        
        if current_app:
            current_app.logger.error(f"SignalWire {operation} failed: {error_msg}")
        
        # Map common SignalWire errors
        if "20003" in error_msg:  # Authentication error
            return {'success': False, 'error': 'Authentication failed', 'code': 'AUTH_ERROR'}
        elif "21614" in error_msg:  # Invalid phone number
            return {'success': False, 'error': 'Invalid phone number format', 'code': 'INVALID_NUMBER'}
        elif "21408" in error_msg:  # Number not available
            return {'success': False, 'error': 'Phone number not available', 'code': 'NUMBER_UNAVAILABLE'}
        elif "21211" in error_msg:  # Invalid from number
            return {'success': False, 'error': 'Invalid from phone number', 'code': 'INVALID_FROM'}
        elif "30008" in error_msg:  # Unknown webhook
            return {'success': False, 'error': 'Webhook configuration failed', 'code': 'WEBHOOK_ERROR'}
        else:
            return {'success': False, 'error': f'SignalWire operation failed: {error_msg}', 'code': 'UNKNOWN_ERROR'}


def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator to retry SignalWire operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise e
                    
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    
            return func(*args, **kwargs)
        return wrapper
    return decorator


class SignalWireService:
    """
    Complete SignalWire integration service
    Handles subprojects, phone numbers, SMS, and webhooks
    """
    
    def __init__(self):
        self.config = SignalWireConfig()
        self.client = SignalWireRestClient(
            self.config.project_id,
            self.config.auth_token,
            signalwire_space_url=self.config.space_url
        )
        self.validator = RequestValidator(self.config.auth_token)
        self.logger = logging.getLogger(__name__)
    
    # =============================================================================
    # SUBPROJECT MANAGEMENT
    # =============================================================================
    
    @with_retry(max_retries=3, base_delay=1.0)
    def create_subproject(self, user_id: int, name: str) -> Dict[str, Any]:
        """
        Create SignalWire subproject for user isolation
        """
        try:
            subproject = self.client.api.accounts.create(
                friendly_name=name
            )
            
            self.logger.info(f"Created subproject {subproject.sid} for user {user_id}")
            
            return {
                'success': True,
                'subproject_id': subproject.sid,
                'name': subproject.friendly_name,
                'status': subproject.status,
                'auth_token': subproject.auth_token
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'create_subproject')
    
    def get_subproject(self, subproject_id: str) -> Dict[str, Any]:
        """
        Get subproject details
        """
        try:
            subproject = self.client.api.accounts(subproject_id).fetch()
            
            return {
                'success': True,
                'subproject': {
                    'id': subproject.sid,
                    'name': subproject.friendly_name,
                    'status': subproject.status,
                    'date_created': subproject.date_created.isoformat() if subproject.date_created else None
                }
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'get_subproject')
    
    def delete_subproject(self, subproject_id: str) -> Dict[str, Any]:
        """
        Delete subproject (for account closure)
        """
        try:
            subproject = self.client.api.accounts(subproject_id).update(
                status='closed'
            )
            
            self.logger.info(f"Closed subproject {subproject_id}")
            
            return {
                'success': True,
                'message': f'Subproject {subproject_id} closed'
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'delete_subproject')
    
    # =============================================================================
    # PHONE NUMBER SEARCH AND PURCHASE
    # =============================================================================
    
    def search_available_numbers(self, area_code: str = None, region: str = None, 
                                country: str = 'US', limit: int = 10) -> Dict[str, Any]:
        """
        Search for available phone numbers
        """
        try:
            search_params = {
                'limit': limit,
                'exclude_all_address_required': True,
                'exclude_local_address_required': True
            }
            
            if area_code:
                search_params['area_code'] = area_code
            if region:
                search_params['in_region'] = region
            
            # Search for local numbers
            numbers = self.client.available_phone_numbers(country).local.list(**search_params)
            
            available_numbers = []
            for number in numbers:
                number_info = {
                    'phone_number': number.phone_number,
                    'friendly_name': number.friendly_name,
                    'locality': number.locality,
                    'region': number.region,
                    'postal_code': number.postal_code,
                    'iso_country': number.iso_country,
                    'capabilities': {
                        'voice': number.capabilities.get('voice', False),
                        'sms': number.capabilities.get('sms', False),
                        'mms': number.capabilities.get('mms', False)
                    }
                }
                available_numbers.append(number_info)
            
            return {
                'success': True,
                'numbers': available_numbers,
                'count': len(available_numbers),
                'search_params': search_params
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'search_numbers')
    
    @with_retry(max_retries=3, base_delay=1.0)
    def purchase_phone_number(self, user_id: int, phone_number: str = None, 
                            area_code: str = None) -> Dict[str, Any]:
        """
        Purchase phone number and configure webhooks
        """
        try:
            # If no specific number, search for one
            if not phone_number:
                search_result = self.search_available_numbers(
                    area_code=area_code or '416',
                    limit=1
                )
                
                if not search_result['success'] or not search_result['numbers']:
                    return {'success': False, 'error': 'No available numbers found'}
                
                phone_number = search_result['numbers'][0]['phone_number']
            
            # Configure webhook URLs
            webhook_base = self.config.webhook_base_url
            
            # Purchase the number
            purchased_number = self.client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=f'AssisText-User-{user_id}',
                sms_url=f"{webhook_base}/api/webhooks/sms",
                sms_method='POST',
                voice_url=f"{webhook_base}/api/webhooks/voice",
                voice_method='POST',
                status_callback=f"{webhook_base}/api/webhooks/status",
                status_callback_method='POST'
            )
            
            self.logger.info(f"Purchased phone number {purchased_number.phone_number} for user {user_id}")
            
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
            return SignalWireErrorHandler.handle_error(e, 'purchase_phone_number')
    
    def update_phone_number_webhooks(self, phone_number_sid: str, 
                                   webhook_base_url: str = None) -> Dict[str, Any]:
        """
        Update webhook configuration for a phone number
        """
        try:
            if not webhook_base_url:
                webhook_base_url = self.config.webhook_base_url
            
            number = self.client.incoming_phone_numbers(phone_number_sid).update(
                sms_url=f"{webhook_base_url}/api/webhooks/sms",
                sms_method='POST',
                voice_url=f"{webhook_base_url}/api/webhooks/voice",
                voice_method='POST',
                status_callback=f"{webhook_base_url}/api/webhooks/status",
                status_callback_method='POST'
            )
            
            self.logger.info(f"Updated webhooks for phone number {number.phone_number}")
            
            return {
                'success': True,
                'phone_number': number.phone_number,
                'sms_url': number.sms_url,
                'voice_url': number.voice_url,
                'status_callback': number.status_callback
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'update_webhooks')
    
    def release_phone_number(self, phone_number_sid: str) -> Dict[str, Any]:
        """
        Release a phone number
        """
        try:
            number = self.client.incoming_phone_numbers(phone_number_sid).delete()
            
            self.logger.info(f"Released phone number SID: {phone_number_sid}")
            
            return {
                'success': True,
                'message': f'Phone number {phone_number_sid} released'
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'release_phone_number')
    
    def get_user_phone_numbers(self, user_id: int) -> Dict[str, Any]:
        """
        Get all phone numbers for a user
        """
        try:
            # Get user's SignalWire phone number
            user = User.query.get(user_id)
            if not user or not user.signalwire_phone_number:
                return {
                    'success': True,
                    'numbers': [],
                    'count': 0
                }
            
            # Get number details from SignalWire
            numbers = self.client.incoming_phone_numbers.list(
                phone_number=user.signalwire_phone_number
            )
            
            user_numbers = []
            for number in numbers:
                number_info = {
                    'sid': number.sid,
                    'phone_number': number.phone_number,
                    'friendly_name': number.friendly_name,
                    'capabilities': number.capabilities,
                    'sms_url': number.sms_url,
                    'voice_url': number.voice_url,
                    'status_callback': number.status_callback,
                    'date_created': number.date_created.isoformat() if number.date_created else None
                }
                user_numbers.append(number_info)
            
            return {
                'success': True,
                'numbers': user_numbers,
                'count': len(user_numbers)
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'get_user_numbers')
    
    # =============================================================================
    # SMS MESSAGING
    # =============================================================================
    
    @with_retry(max_retries=3, base_delay=1.0)
    def send_sms(self, from_number: str, to_number: str, body: str, 
                media_urls: List[str] = None) -> Dict[str, Any]:
        """
        Send SMS message via SignalWire
        """
        try:
            # Prepare message parameters
            message_params = {
                'from_': from_number,
                'to': to_number,
                'body': body,
                'status_callback': f"{self.config.webhook_base_url}/api/webhooks/status"
            }
            
            # Add media URLs if provided (for MMS)
            if media_urls:
                message_params['media_url'] = media_urls
            
            # Send message
            message = self.client.messages.create(**message_params)
            
            self.logger.info(f"Sent SMS {message.sid}: {from_number} -> {to_number}")
            
            return {
                'success': True,
                'message_sid': message.sid,
                'from_number': from_number,
                'to_number': to_number,
                'status': message.status,
                'direction': message.direction,
                'date_created': message.date_created.isoformat() if message.date_created else None
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'send_sms')
    
    def get_message_status(self, message_sid: str) -> Dict[str, Any]:
        """
        Get message status from SignalWire
        """
        try:
            message = self.client.messages(message_sid).fetch()
            
            return {
                'success': True,
                'message': {
                    'sid': message.sid,
                    'status': message.status,
                    'direction': message.direction,
                    'from_': message.from_,
                    'to': message.to,
                    'body': message.body,
                    'error_code': message.error_code,
                    'error_message': message.error_message,
                    'date_created': message.date_created.isoformat() if message.date_created else None,
                    'date_sent': message.date_sent.isoformat() if message.date_sent else None,
                    'date_updated': message.date_updated.isoformat() if message.date_updated else None
                }
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'get_message_status')
    
    # =============================================================================
    # WEBHOOK VALIDATION
    # =============================================================================
    
    def validate_webhook_signature(self, url: str, post_vars: Dict[str, Any], 
                                 signature: str) -> bool:
        """
        Validate SignalWire webhook signature for security
        """
        try:
            return self.validator.validate(url, post_vars, signature)
        except Exception as e:
            self.logger.error(f"Webhook validation error: {str(e)}")
            return False
    
    def validate_webhook_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and extract webhook data
        """
        try:
            # Required SignalWire webhook fields
            required_fields = ['MessageSid', 'From', 'To']
            
            # Check for required fields
            missing_fields = [field for field in required_fields 
                            if field not in request_data]
            
            if missing_fields:
                return {
                    'valid': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }
            
            # Validate phone number formats
            from_number = request_data.get('From', '')
            to_number = request_data.get('To', '')
            
            if not (from_number.startswith('+') and to_number.startswith('+')):
                return {
                    'valid': False,
                    'error': 'Invalid phone number format'
                }
            
            return {
                'valid': True,
                'data': {
                    'message_sid': request_data.get('MessageSid'),
                    'from_number': from_number,
                    'to_number': to_number,
                    'body': request_data.get('Body', '').strip(),
                    'status': request_data.get('SmsStatus', 'received'),
                    'account_sid': request_data.get('AccountSid'),
                    'media_count': int(request_data.get('NumMedia', 0)),
                    'media_urls': self._extract_media_urls(request_data)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Webhook validation error: {str(e)}")
            return {
                'valid': False,
                'error': 'Webhook validation failed'
            }
    
    def _extract_media_urls(self, request_data: Dict[str, Any]) -> List[str]:
        """Extract media URLs from webhook data"""
        media_urls = []
        media_count = int(request_data.get('NumMedia', 0))
        
        for i in range(media_count):
            media_url = request_data.get(f'MediaUrl{i}')
            if media_url:
                media_urls.append(media_url)
        
        return media_urls
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def get_account_balance(self) -> Dict[str, Any]:
        """
        Get SignalWire account balance
        """
        try:
            balance = self.client.balance.fetch()
            
            return {
                'success': True,
                'balance': {
                    'account_sid': balance.account_sid,
                    'balance': balance.balance,
                    'currency': balance.currency
                }
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'get_balance')
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test SignalWire connection and configuration
        """
        try:
            # Test by fetching account details
            account = self.client.api.accounts(self.config.project_id).fetch()
            
            return {
                'success': True,
                'connection': 'verified',
                'account': {
                    'sid': account.sid,
                    'friendly_name': account.friendly_name,
                    'status': account.status,
                    'type': account.type
                },
                'config': {
                    'space_url': self.config.space_url,
                    'webhook_base_url': self.config.webhook_base_url
                }
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'test_connection')
    
    def get_usage_records(self, start_date: datetime = None, 
                         end_date: datetime = None) -> Dict[str, Any]:
        """
        Get SignalWire usage records for billing
        """
        try:
            params = {}
            if start_date:
                params['start_date'] = start_date.date()
            if end_date:
                params['end_date'] = end_date.date()
            
            usage_records = self.client.usage.records.list(**params)
            
            records = []
            for record in usage_records:
                record_data = {
                    'category': record.category,
                    'description': record.description,
                    'account_sid': record.account_sid,
                    'count': record.count,
                    'count_unit': record.count_unit,
                    'usage': record.usage,
                    'usage_unit': record.usage_unit,
                    'price': record.price,
                    'price_unit': record.price_unit,
                    'start_date': record.start_date.isoformat() if record.start_date else None,
                    'end_date': record.end_date.isoformat() if record.end_date else None
                }
                records.append(record_data)
            
            return {
                'success': True,
                'usage_records': records,
                'count': len(records)
            }
            
        except Exception as e:
            return SignalWireErrorHandler.handle_error(e, 'get_usage_records')
    
    # =============================================================================
    # BULK OPERATIONS
    # =============================================================================
    
    def bulk_send_sms(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Send multiple SMS messages in bulk
        """
        results = []
        successful = 0
        failed = 0
        
        for message_data in messages:
            try:
                result = self.send_sms(
                    from_number=message_data['from_number'],
                    to_number=message_data['to_number'],
                    body=message_data['body'],
                    media_urls=message_data.get('media_urls')
                )
                
                if result['success']:
                    successful += 1
                else:
                    failed += 1
                
                results.append(result)
                
            except Exception as e:
                failed += 1
                results.append({
                    'success': False,
                    'error': str(e),
                    'to_number': message_data.get('to_number')
                })
        
        return {
            'success': True,
            'results': results,
            'summary': {
                'total': len(messages),
                'successful': successful,
                'failed': failed
            }
        }