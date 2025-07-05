"""
SignalWire Service with Automatic Webhook Configuration
app/services/signalwire_service.py - Complete phone number management with webhook setup
"""
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from flask import current_app
from signalwire.rest import Client as SignalWireClient
from signalwire.rest.api.v2010.account.incoming_phone_number import IncomingPhoneNumberInstance
import time
import functools

class SignalWireService:
    """
    Complete SignalWire service for phone number management and webhook configuration
    """
    
    def __init__(self):
        # SignalWire credentials
        self.project_id = os.getenv('SIGNALWIRE_PROJECT_ID')
        self.api_token = os.getenv('SIGNALWIRE_API_TOKEN')
        self.space_url = os.getenv('SIGNALWIRE_SPACE_URL')
        self.base_url = os.getenv('BASE_URL', 'https://assitext.ca')
        
        # Webhook URLs
        self.webhook_urls = {
            'sms_url': f"{self.base_url}/api/webhooks/sms",
            'voice_url': f"{self.base_url}/api/webhooks/voice", 
            'status_callback': f"{self.base_url}/api/webhooks/status",
            'fallback_url': f"{self.base_url}/api/webhooks/fallback"
        }
        
        # Initialize client
        self.client = None
        self._initialize_client()
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
    
    def _initialize_client(self):
        """Initialize SignalWire client with error handling"""
        try:
            if not all([self.project_id, self.api_token, self.space_url]):
                self.logger.error("Missing SignalWire credentials")
                return
                
            self.client = SignalWireClient(
                self.project_id,
                self.api_token,
                signalwire_space_url=self.space_url
            )
            
            self.logger.info("SignalWire client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize SignalWire client: {str(e)}")
            self.client = None
    
    def is_configured(self) -> bool:
        """Check if SignalWire service is properly configured"""
        return self.client is not None
    
    def _with_retry(self, max_retries: int = 2, base_delay: float = 1.0):
        """Decorator for retrying failed SignalWire API calls"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            self.logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {str(e)}")
                            time.sleep(delay)
                        else:
                            self.logger.error(f"All {max_retries + 1} attempts failed: {str(e)}")
                
                raise last_exception
            return wrapper
        return decorator
    
    @_with_retry(max_retries=2, base_delay=2.0)
    def search_available_numbers(self, search_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search for available phone numbers
        
        Args:
            search_criteria: Dictionary with search parameters
                - country: 'US' or 'CA' 
                - area_code: Target area code
                - city: City name
                - region: State/Province
                - contains: Number pattern to search for
                - limit: Maximum results (default 10)
                - sms_enabled: Require SMS capability
                - voice_enabled: Require voice capability
        
        Returns:
            Dictionary with success status and available numbers
        """
        try:
            if not self.is_configured():
                return {'success': False, 'error': 'SignalWire not configured'}
            
            # Extract search parameters
            country = search_criteria.get('country', 'US').upper()
            area_code = search_criteria.get('area_code')
            city = search_criteria.get('city')
            region = search_criteria.get('region')
            contains = search_criteria.get('contains')
            limit = min(search_criteria.get('limit', 10), 50)  # Max 50 for performance
            
            # Build search filters
            search_filters = {}
            if area_code:
                search_filters['area_code'] = area_code
            if city:
                search_filters['in_locality'] = city
            if region:
                search_filters['in_region'] = region
            if contains:
                search_filters['contains'] = contains
            
            self.logger.info(f"Searching for numbers in {country} with filters: {search_filters}")
            
            # Search for available numbers
            if country == 'US':
                available_numbers = self.client.available_phone_numbers('US').local.list(
                    limit=limit,
                    **search_filters
                )
            elif country == 'CA':
                available_numbers = self.client.available_phone_numbers('CA').local.list(
                    limit=limit,
                    **search_filters
                )
            else:
                return {'success': False, 'error': f'Unsupported country: {country}'}
            
            # Format results
            formatted_numbers = []
            for number in available_numbers:
                formatted_number = {
                    'phone_number': number.phone_number,
                    'friendly_name': number.friendly_name,
                    'locality': getattr(number, 'locality', 'Unknown'),
                    'region': getattr(number, 'region', region or 'Unknown'),
                    'country': country,
                    'area_code': number.phone_number[2:5] if len(number.phone_number) > 5 else '',
                    'capabilities': {
                        'voice': getattr(number.capabilities, 'voice', True),
                        'sms': getattr(number.capabilities, 'SMS', True),
                        'mms': getattr(number.capabilities, 'MMS', True),
                        'fax': getattr(number.capabilities, 'fax', False)
                    },
                    'monthly_cost': '$1.00' if country == 'US' else '$1.50',  # Canadian numbers cost more
                    'setup_cost': '$1.00'
                }
                formatted_numbers.append(formatted_number)
            
            self.logger.info(f"Found {len(formatted_numbers)} available numbers")
            
            return {
                'success': True,
                'numbers': formatted_numbers,
                'count': len(formatted_numbers),
                'search_criteria': search_criteria
            }
            
        except Exception as e:
            self.logger.error(f"Number search failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @_with_retry(max_retries=2, base_delay=3.0)
    def purchase_phone_number(self, phone_number: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Purchase phone number and automatically configure webhooks
        
        Args:
            phone_number: Phone number to purchase in E.164 format
            profile_data: Profile information for webhook configuration
                - profile_id: User profile ID
                - friendly_name: Display name for the number
                - user_id: User ID for tracking
        
        Returns:
            Dictionary with purchase result and webhook configuration status
        """
        try:
            if not self.is_configured():
                return {'success': False, 'error': 'SignalWire not configured'}
            
            if not phone_number.startswith('+'):
                phone_number = f"+{phone_number}"
            
            friendly_name = profile_data.get('friendly_name', f"AssisText Number {phone_number[-4:]}")
            
            self.logger.info(f"Purchasing phone number: {phone_number}")
            
            # Purchase phone number with webhook configuration
            purchased_number = self.client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=friendly_name,
                
                # SMS webhook configuration
                sms_url=self.webhook_urls['sms_url'],
                sms_method='POST',
                sms_fallback_url=self.webhook_urls['fallback_url'],
                sms_fallback_method='POST',
                
                # Voice webhook configuration
                voice_url=self.webhook_urls['voice_url'],
                voice_method='POST',
                voice_fallback_url=self.webhook_urls['fallback_url'],
                voice_fallback_method='POST',
                
                # Status callback configuration
                status_callback=self.webhook_urls['status_callback'],
                status_callback_method='POST'
            )
            
            self.logger.info(f"Successfully purchased and configured: {purchased_number.phone_number}")
            
            # Verify webhook configuration
            webhook_status = self._verify_webhook_configuration(purchased_number.sid)
            
            return {
                'success': True,
                'purchase_details': {
                    'phone_number_sid': purchased_number.sid,
                    'phone_number': purchased_number.phone_number,
                    'friendly_name': purchased_number.friendly_name,
                    'account_sid': purchased_number.account_sid,
                    'date_created': purchased_number.date_created.isoformat() if purchased_number.date_created else None,
                    'capabilities': {
                        'voice': getattr(purchased_number.capabilities, 'voice', True),
                        'sms': getattr(purchased_number.capabilities, 'sms', True),
                        'mms': getattr(purchased_number.capabilities, 'mms', True)
                    }
                },
                'webhook_configuration': {
                    'sms_url': purchased_number.sms_url,
                    'voice_url': purchased_number.voice_url,
                    'status_callback': purchased_number.status_callback,
                    'configuration_verified': webhook_status['verified'],
                    'webhook_urls_configured': self.webhook_urls
                },
                'profile_data': profile_data
            }
            
        except Exception as e:
            self.logger.error(f"Phone number purchase failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _verify_webhook_configuration(self, phone_number_sid: str) -> Dict[str, Any]:
        """Verify that webhooks are properly configured for a phone number"""
        try:
            # Fetch the phone number details to verify configuration
            phone_number = self.client.incoming_phone_numbers(phone_number_sid).fetch()
            
            verification_results = {
                'sms_webhook_configured': phone_number.sms_url == self.webhook_urls['sms_url'],
                'voice_webhook_configured': phone_number.voice_url == self.webhook_urls['voice_url'],
                'status_callback_configured': phone_number.status_callback == self.webhook_urls['status_callback'],
                'sms_url': phone_number.sms_url,
                'voice_url': phone_number.voice_url,
                'status_callback': phone_number.status_callback
            }
            
            verification_results['verified'] = all([
                verification_results['sms_webhook_configured'],
                verification_results['voice_webhook_configured'],
                verification_results['status_callback_configured']
            ])
            
            return verification_results
            
        except Exception as e:
            self.logger.error(f"Webhook verification failed: {str(e)}")
            return {'verified': False, 'error': str(e)}
    
    @_with_retry(max_retries=2, base_delay=2.0)
    def update_phone_number_webhooks(self, phone_number_sid: str, webhook_config: Dict[str, str]) -> Dict[str, Any]:
        """
        Update webhook configuration for an existing phone number
        
        Args:
            phone_number_sid: SID of the phone number to update
            webhook_config: New webhook configuration
        
        Returns:
            Dictionary with update status
        """
        try:
            if not self.is_configured():
                return {'success': False, 'error': 'SignalWire not configured'}
            
            # Merge with default webhook URLs
            update_data = {}
            
            if 'sms_url' in webhook_config:
                update_data['sms_url'] = webhook_config['sms_url']
                update_data['sms_method'] = webhook_config.get('sms_method', 'POST')
            
            if 'voice_url' in webhook_config:
                update_data['voice_url'] = webhook_config['voice_url']
                update_data['voice_method'] = webhook_config.get('voice_method', 'POST')
            
            if 'status_callback' in webhook_config:
                update_data['status_callback'] = webhook_config['status_callback']
                update_data['status_callback_method'] = webhook_config.get('status_callback_method', 'POST')
            
            if 'friendly_name' in webhook_config:
                update_data['friendly_name'] = webhook_config['friendly_name']
            
            self.logger.info(f"Updating webhooks for {phone_number_sid}")
            
            # Update the phone number
            updated_number = self.client.incoming_phone_numbers(phone_number_sid).update(**update_data)
            
            return {
                'success': True,
                'phone_number': updated_number.phone_number,
                'updated_configuration': {
                    'sms_url': updated_number.sms_url,
                    'voice_url': updated_number.voice_url,
                    'status_callback': updated_number.status_callback,
                    'friendly_name': updated_number.friendly_name
                }
            }
            
        except Exception as e:
            self.logger.error(f"Webhook update failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def list_owned_phone_numbers(self) -> Dict[str, Any]:
        """List all phone numbers owned by this account"""
        try:
            if not self.is_configured():
                return {'success': False, 'error': 'SignalWire not configured'}
            
            phone_numbers = self.client.incoming_phone_numbers.list()
            
            formatted_numbers = []
            for number in phone_numbers:
                formatted_number = {
                    'sid': number.sid,
                    'phone_number': number.phone_number,
                    'friendly_name': number.friendly_name,
                    'capabilities': {
                        'voice': getattr(number.capabilities, 'voice', True),
                        'sms': getattr(number.capabilities, 'sms', True),
                        'mms': getattr(number.capabilities, 'mms', True)
                    },
                    'webhook_configuration': {
                        'sms_url': number.sms_url,
                        'voice_url': number.voice_url,
                        'status_callback': number.status_callback
                    },
                    'date_created': number.date_created.isoformat() if number.date_created else None
                }
                formatted_numbers.append(formatted_number)
            
            return {
                'success': True,
                'phone_numbers': formatted_numbers,
                'count': len(formatted_numbers)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to list phone numbers: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def release_phone_number(self, phone_number_sid: str) -> Dict[str, Any]:
        """Release (delete) a phone number"""
        try:
            if not self.is_configured():
                return {'success': False, 'error': 'SignalWire not configured'}
            
            # Get phone number details before deletion
            phone_number = self.client.incoming_phone_numbers(phone_number_sid).fetch()
            number_value = phone_number.phone_number
            
            # Delete the phone number
            phone_number.delete()
            
            self.logger.info(f"Released phone number: {number_value}")
            
            return {
                'success': True,
                'message': f'Phone number {number_value} has been released',
                'released_number': number_value
            }
            
        except Exception as e:
            self.logger.error(f"Failed to release phone number: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_sms(self, to_number: str, from_number: str, message_body: str, 
                 media_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Send SMS message through SignalWire
        
        Args:
            to_number: Recipient phone number in E.164 format
            from_number: Sender phone number (must be owned)
            message_body: Message content
            media_urls: Optional list of media URLs for MMS
        
        Returns:
            Dictionary with send status and message SID
        """
        try:
            if not self.is_configured():
                return {'success': False, 'error': 'SignalWire not configured'}
            
            # Ensure numbers are in E.164 format
            if not to_number.startswith('+'):
                to_number = f"+{to_number}"
            if not from_number.startswith('+'):
                from_number = f"+{from_number}"
            
            # Prepare message data
            message_data = {
                'to': to_number,
                'from': from_number,
                'body': message_body
            }
            
            # Add media URLs if provided
            if media_urls:
                message_data['media_url'] = media_urls
            
            # Send the message
            message = self.client.messages.create(**message_data)
            
            self.logger.info(f"SMS sent: {message.sid}")
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'direction': message.direction,
                'to': message.to,
                'from': message.from_,
                'date_sent': message.date_sent.isoformat() if message.date_sent else None
            }
            
        except Exception as e:
            self.logger.error(f"Failed to send SMS: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        try:
            status = {
                'configured': self.is_configured(),
                'credentials': {
                    'project_id': bool(self.project_id),
                    'api_token': bool(self.api_token),
                    'space_url': self.space_url
                },
                'webhook_urls': self.webhook_urls,
                'base_url': self.base_url
            }
            
            if self.is_configured():
                # Test API connectivity
                try:
                    account = self.client.api.accounts(self.project_id).fetch()
                    status['api_connectivity'] = True
                    status['account_status'] = account.status
                    status['account_friendly_name'] = account.friendly_name
                except Exception as e:
                    status['api_connectivity'] = False
                    status['api_error'] = str(e)
            else:
                status['api_connectivity'] = False
            
            return status
            
        except Exception as e:
            return {
                'configured': False,
                'error': str(e)
            }