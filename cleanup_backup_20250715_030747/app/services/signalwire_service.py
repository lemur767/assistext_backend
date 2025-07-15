# app/services/signalwire_service.py
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from signalwire.rest import Client as SignalWireClient
from flask import current_app
import redis
import json
import uuid

logger = logging.getLogger(__name__)

class SignalWireService:
    """SignalWire integration service for phone number management and subproject creation"""
    
    def __init__(self):
        self.project_id = os.getenv('SIGNALWIRE_PROJECT')
        self.auth_token = os.getenv('SIGNALWIRE_TOKEN')
        self.space_url = os.getenv('SIGNALWIRE_SPACE')
        self.webhook_base_url = os.getenv('BACKEND_URL', 'https://backend.assitext.ca')
        
        if not all([self.project_id, self.auth_token, self.space_url]):
            raise ValueError("Missing required SignalWire credentials")
        
        # Initialize with proper space URL format
        space_url_formatted = f"https://{self.space_url}" if not self.space_url.startswith('http') else self.space_url
        
        self.client = SignalWireClient(
            self.project_id,
            self.auth_token,
            signalwire_space_url=space_url_formatted
        )
        
        # Redis for caching number searches
        try:
            self.redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
            # Test Redis connection
            self.redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self.redis_client = None
    
    def search_available_numbers(self, country: str = 'CA', area_code: str = None, 
                                locality: str = None, limit: int = 5) -> Dict:
        """
        Search for available phone numbers in Ontario, Canada
        
        Args:
            country: Country code (CA for Canada)
            area_code: Specific area code to search
            locality: City/locality to search in
            limit: Maximum number of results to return
            
        Returns:
            Dict containing available numbers and selection token
        """
        try:
            # For Ontario, focus on major area codes if none specified
            ontario_area_codes = ['416', '647', '437', '905', '289', '365', '519', '226', '807', '705', '249']
            
            if not area_code and locality:
                # Map common Ontario cities to area codes
                city_area_codes = {
                    'toronto': ['416', '647', '437'],
                    'mississauga': ['905', '289', '365'],
                    'ottawa': ['613', '343'],
                    'hamilton': ['905', '289'],
                    'london': ['519', '226'],
                    'kitchener': ['519', '226'],
                    'windsor': ['519', '226']
                }
                area_codes_to_search = city_area_codes.get(locality.lower(), ontario_area_codes[:3])
            elif area_code:
                area_codes_to_search = [area_code]
            else:
                area_codes_to_search = ontario_area_codes[:3]  # Default to Toronto area codes
            
            all_numbers = []
            
            # Search across multiple area codes to ensure we find numbers
            for ac in area_codes_to_search:
                if len(all_numbers) >= limit:
                    break
                    
                try:
                    # Use the current SignalWire REST API format
                    search_params = {
                        'area_code': ac,
                        'limit': limit - len(all_numbers),
                        'sms_enabled': True,
                        'voice_enabled': True
                    }
                    
                    numbers = self.client.available_phone_numbers("CA").local.list(**search_params)
                    
                    for number in numbers:
                        if len(all_numbers) >= limit:
                            break
                        
                        # Access capabilities properly based on current API
                        capabilities = getattr(number, 'capabilities', {})
                        
                        all_numbers.append({
                            'phone_number': number.phone_number,
                            'friendly_name': getattr(number, 'friendly_name', number.phone_number),
                            'locality': getattr(number, 'locality', ''),
                            'region': getattr(number, 'region', 'ON'),
                            'capabilities': {
                                'voice': getattr(capabilities, 'voice', True),
                                'sms': getattr(capabilities, 'sms', True) or getattr(capabilities, 'SMS', True),
                                'mms': getattr(capabilities, 'mms', True) or getattr(capabilities, 'MMS', True)
                            }
                        })
                
                except Exception as e:
                    logger.warning(f"Failed to search area code {ac}: {e}")
                    continue
            
            if not all_numbers:
                # Fallback: try without area code restriction for Ontario
                try:
                    search_params = {
                        'limit': limit,
                        'in_region': 'ON',  # Ontario
                        'sms_enabled': True,
                        'voice_enabled': True
                    }
                    numbers = self.client.available_phone_numbers("CA").local.list(**search_params)
                    
                    for number in numbers:
                        capabilities = getattr(number, 'capabilities', {})
                        all_numbers.append({
                            'phone_number': number.phone_number,
                            'friendly_name': getattr(number, 'friendly_name', number.phone_number),
                            'locality': getattr(number, 'locality', ''),
                            'region': getattr(number, 'region', 'ON'),
                            'capabilities': {
                                'voice': getattr(capabilities, 'voice', True),
                                'sms': getattr(capabilities, 'sms', True) or getattr(capabilities, 'SMS', True),
                                'mms': getattr(capabilities, 'mms', True) or getattr(capabilities, 'MMS', True)
                            }
                        })
                except Exception as e:
                    logger.error(f"Fallback number search failed: {e}")
                    # Add your initialized number as an option if no numbers found
                    all_numbers = [{
                        'phone_number': '+12899171708',
                        'friendly_name': 'Your Business Number',
                        'locality': 'Hamilton',
                        'region': 'ON',
                        'capabilities': {
                            'voice': True,
                            'sms': True,
                            'mms': True
                        }
                    }]
            
            # Create selection token with 15-minute expiry
            selection_token = self._create_selection_token(all_numbers)
            
            return {
                'success': True,
                'available_numbers': all_numbers,
                'selection_token': selection_token,
                'expires_in': 900  # 15 minutes
            }
            
        except Exception as e:
            logger.error(f"Phone number search failed: {e}")
            return {
                'success': False,
                'error': f'Failed to search phone numbers: {str(e)}',
                'available_numbers': []
            }
    
    def create_subproject_and_purchase_number(self, user_id: int, username: str, 
                                            selected_number: str, selection_token: str) -> Dict:
        """
        Create SignalWire subproject and purchase selected phone number
        
        Args:
            user_id: Database user ID
            username: User's username
            selected_number: Phone number to purchase
            selection_token: Token from number search
            
        Returns:
            Dict containing subproject details and phone number info
        """
        try:
            # Validate selection token
            cached_numbers = self._validate_selection_token(selection_token)
            if not cached_numbers:
                return {
                    'success': False,
                    'error': 'Selection token expired or invalid. Please search for numbers again.'
                }
            
            # Verify selected number is in cached results
            if not any(num['phone_number'] == selected_number for num in cached_numbers):
                return {
                    'success': False,
                    'error': 'Selected number is no longer available.'
                }
            
            # Create subproject using current API format
            friendly_name = f"{username}_{user_id}"
            subproject = self.client.api.accounts.create(friendly_name=friendly_name)
            
            # Configure webhook URLs
            webhook_config = {
                'sms_url': f"{self.webhook_base_url}/api/webhooks/sms",
                'sms_method': 'POST',
                'voice_url': f"{self.webhook_base_url}/api/webhooks/voice",
                'voice_method': 'POST',
                'status_callback': f"{self.webhook_base_url}/api/webhooks/status",
                'status_callback_method': 'POST'
            }
            
            # Purchase phone number and assign to subproject
            try:
                phone_number = self.client.incoming_phone_numbers.create(
                    phone_number=selected_number,
                    account_sid=subproject.sid,
                    friendly_name=f"AssisText - {username}",
                    **webhook_config
                )
            except Exception as e:
                # If purchasing fails, try to cleanup subproject
                try:
                    self.client.api.accounts(subproject.sid).delete()
                except:
                    pass
                raise Exception(f"Failed to purchase number: {str(e)}")
            
            # Calculate trial expiry (14 days from now)
            trial_expires = datetime.utcnow() + timedelta(days=14)
            
            return {
                'success': True,
                'subproject': {
                    'sid': subproject.sid,
                    'auth_token': subproject.auth_token,
                    'friendly_name': subproject.friendly_name,
                    'status': subproject.status
                },
                'phone_number': {
                    'sid': phone_number.sid,
                    'number': phone_number.phone_number,
                    'capabilities': {
                        'voice': True,
                        'sms': True,
                        'mms': True
                    }
                },
                'trial_expires_at': trial_expires.isoformat(),
                'webhook_configured': True,
                'webhook_urls': webhook_config
            }
            
        except Exception as e:
            logger.error(f"Subproject creation failed: {e}")
            return {
                'success': False,
                'error': f'Failed to setup phone service: {str(e)}'
            }
    
    def test_webhook_configuration(self, subproject_sid: str, phone_number: str) -> Dict:
        """Test webhook configuration by sending a test message"""
        try:
            # Send a test message to verify webhook setup
            test_message = self.client.messages.create(
                from_=phone_number,
                to=phone_number,  # Send to self for testing
                body="Test message - SignalWire integration active!",
                account_sid=subproject_sid
            )
            
            return {
                'success': True,
                'message_sid': test_message.sid,
                'status': test_message.status
            }
            
        except Exception as e:
            logger.warning(f"Webhook test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_subproject_usage(self, subproject_sid: str) -> Dict:
        """Get usage statistics for a subproject"""
        try:
            # Get messages sent/received
            messages = self.client.messages.list(account_sid=subproject_sid, limit=1000)
            calls = self.client.calls.list(account_sid=subproject_sid, limit=1000)
            
            return {
                'success': True,
                'usage': {
                    'messages_sent': len([m for m in messages if m.direction == 'outbound-api']),
                    'messages_received': len([m for m in messages if m.direction == 'inbound']),
                    'calls_made': len([c for c in calls if c.direction == 'outbound-api']),
                    'calls_received': len([c for c in calls if c.direction == 'inbound']),
                    'total_messages': len(messages),
                    'total_calls': len(calls)
                }
            }
            
        except Exception as e:
            logger.error(f"Usage fetch failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_selection_token(self, numbers: List[Dict]) -> str:
        """Create a secure token for number selection with Redis caching"""
        token = str(uuid.uuid4())
        
        try:
            if self.redis_client:
                # Cache numbers for 15 minutes
                self.redis_client.setex(
                    f"number_selection:{token}",
                    900,  # 15 minutes
                    json.dumps(numbers)
                )
            else:
                # Fallback: log warning but still return token
                logger.warning("Redis not available for token caching")
        except Exception as e:
            logger.error(f"Failed to cache selection token: {e}")
        
        return token
    
    def _validate_selection_token(self, token: str) -> Optional[List[Dict]]:
        """Validate selection token and return cached numbers"""
        try:
            if self.redis_client:
                cached_data = self.redis_client.get(f"number_selection:{token}")
                if cached_data:
                    return json.loads(cached_data)
            else:
                logger.warning("Redis not available for token validation")
            return None
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return None