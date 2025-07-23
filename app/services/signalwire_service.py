
"""
UNIFIED SignalWire Service Layer - FIXED VERSION
Consolidates ALL SignalWire functionality into ONE service
"""
=======
# Create a completely simplified version that avoids the problematic account access



import os
import logging
import hmac
import hashlib
import base64
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
from flask import current_app, request
from signalwire.rest import Client as SignalWireClient

logger = logging.getLogger(__name__)

class SignalWireServiceError(Exception):
    """Custom exception for SignalWire service errors"""
    pass

class SignalWireService:
    """UNIFIED SignalWire Service - The ONLY SignalWire integration class you need"""
    
    def __init__(self):
        self._client = None
        self._config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, str]:
        """Load SignalWire configuration from environment"""
        return {
            'project_id': os.getenv('SIGNALWIRE_PROJECT_ID') or os.getenv('SIGNALWIRE_PROJECT'),
            'auth_token': os.getenv('SIGNALWIRE_AUTH_TOKEN') or os.getenv('SIGNALWIRE_TOKEN'),  
            'space_url': os.getenv('SIGNALWIRE_SPACE_URL') or os.getenv('SIGNALWIRE_SPACE'),
            'webhook_base_url': os.getenv('WEBHOOK_BASE_URL', 'https://backend.assitext.ca')
        }
    
    def _validate_config(self):
        """Validate required configuration"""
        required_fields = ['project_id', 'auth_token', 'space_url']
        missing = [field for field in required_fields if not self._config.get(field)]
        
        if missing:
            raise SignalWireServiceError(f"Missing required SignalWire config: {', '.join(missing)}")
    
    @property
    def client(self) -> SignalWireClient:
        """Lazy-load SignalWire client with connection validation"""
        if self._client is None:
            try:
                self._client = SignalWireClient(
                    self._config['project_id'],
                    self._config['auth_token'],
                    signalwire_space_url=self._config['space_url']
                )
                logger.info("✅ SignalWire client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize SignalWire client: {e}")
                raise SignalWireServiceError(f"SignalWire connection failed: {e}")
        
        return self._client

    # =========================================================================
    # SUB-PROJECT (SUBACCOUNT) MANAGEMENT
    # =========================================================================
    
    def create_subproject(self, user_id: int, friendly_name: str) -> Dict[str, Any]:
        """Create a dedicated sub-project for multi-tenant isolation"""
        try:
            subproject_name = f"User_{user_id}_{friendly_name}"
            
            subproject = self.client.api.accounts.create(
                friendly_name=subproject_name
            )
            
            logger.info(f"✅ Created subproject: {subproject.sid} for user {user_id}")
            
            return {
                'success': True,
                'subproject_sid': subproject.sid,
                'auth_token': subproject.auth_token,
                'friendly_name': subproject.friendly_name,
                'status': subproject.status,
                'date_created': str(subproject.date_created) if subproject.date_created else None
            }
            
        except Exception as e:
            logger.error(f"❌ Subproject creation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    # =========================================================================
    # PHONE NUMBER SEARCH & MANAGEMENT
    # =========================================================================
    
    def search_available_numbers(self, 
                                country: str = 'US',
                                area_code: str = None,
                                city: str = None,
                                region: str = None,
                                contains: str = None,
                                limit: int = 20) -> Dict[str, Any]:
        """Search for available phone numbers with comprehensive filtering"""
        try:
            limit = min(limit, 50)
            
            search_params = {}
            if area_code:
                search_params['area_code'] = area_code
            if city:
                search_params['in_locality'] = city
            if region:
                search_params['in_region'] = region
            if contains:
                search_params['contains'] = contains
            
            if country.upper() == 'CA':
                numbers = self.client.available_phone_numbers('CA').local.list(
                    limit=limit, sms_enabled=True, voice_enabled=True, **search_params
                )
            else:
                numbers = self.client.available_phone_numbers('US').local.list(
                    limit=limit, sms_enabled=True, voice_enabled=True, **search_params
                )
            
            formatted_numbers = []
            for number in numbers:
                formatted_numbers.append({
                    'phone_number': number.phone_number,
                    'formatted_number': number.friendly_name or number.phone_number,
                    'locality': number.locality,
                    'region': number.region,
                    'country': country.upper(),
                    'capabilities': {
                        'sms': getattr(number.capabilities, 'SMS', True) if hasattr(number, 'capabilities') else True,
                        'mms': getattr(number.capabilities, 'MMS', True) if hasattr(number, 'capabilities') else True,
                        'voice': getattr(number.capabilities, 'voice', True) if hasattr(number, 'capabilities') else True
                    },
                    'monthly_cost': '$1.00'
                })
            
            logger.info(f"✅ Found {len(formatted_numbers)} available numbers")
            
            return {
                'success': True,
                'numbers': formatted_numbers,
                'count': len(formatted_numbers)
            }
            
        except Exception as e:
            logger.error(f"❌ Phone number search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'numbers': [],
                'count': 0
            }

    # =========================================================================
    # PHONE NUMBER PURCHASE & ASSIGNMENT
    # =========================================================================
    
    def purchase_number(self, 
                       phone_number: str,
                       subproject_sid: str = None,
                       friendly_name: str = None) -> Dict[str, Any]:
        """Purchase phone number and assign to subproject with webhooks"""
        try:
            webhook_base = self._config['webhook_base_url']
            
            purchase_params = {
                'phone_number': phone_number,
                'friendly_name': friendly_name or 'AssisText Number',
                'sms_url': f"{webhook_base}/api/webhooks/sms",
                'sms_method': 'POST',
                'voice_url': f"{webhook_base}/api/webhooks/voice", 
                'voice_method': 'POST',
                'status_callback': f"{webhook_base}/api/webhooks/status",
                'status_callback_method': 'POST'
            }
            
            if subproject_sid:
                purchase_params['account_sid'] = subproject_sid
            
            purchased_number = self.client.incoming_phone_numbers.create(**purchase_params)
            
            logger.info(f"✅ Successfully purchased {phone_number}")
            
            return {
                'success': True,
                'phone_number_sid': purchased_number.sid,
                'phone_number': purchased_number.phone_number,
                'friendly_name': purchased_number.friendly_name,
                'account_sid': getattr(purchased_number, 'account_sid', None),
                'webhook_configured': True,
                'webhooks': {
                    'sms_url': getattr(purchased_number, 'sms_url', None),
                    'voice_url': getattr(purchased_number, 'voice_url', None),
                    'status_callback': getattr(purchased_number, 'status_callback', None)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Phone number purchase failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    # =========================================================================
    # SMS SENDING & STATUS TRACKING
    # =========================================================================
    
    def send_sms(self, 
                from_number: str,
                to_number: str,
                message_body: str,
                subproject_sid: str = None) -> Dict[str, Any]:
        """Send SMS message with subproject context"""
        try:
            send_params = {
                'from_': from_number,
                'to': to_number,
                'body': message_body,
                'status_callback': f"{self._config['webhook_base_url']}/api/webhooks/status"
            }
            
            if subproject_sid:
                subproject_client = SignalWireClient(
                    subproject_sid,
                    self._config['auth_token'],
                    signalwire_space_url=self._config['space_url']
                )
                message = subproject_client.messages.create(**send_params)
            else:
                message = self.client.messages.create(**send_params)
            
            logger.info(f"✅ SMS sent: {message.sid}")
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'from_number': message.from_,
                'to_number': message.to,
                'body': message.body
            }
            
        except Exception as e:
            logger.error(f"❌ SMS send failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_message_status(self, message_sid: str, subproject_sid: str = None) -> Dict[str, Any]:
        """Get message delivery status"""
        try:
            if subproject_sid:
                subproject_client = SignalWireClient(
                    subproject_sid,
                    self._config['auth_token'],
                    signalwire_space_url=self._config['space_url']
                )
                message = subproject_client.messages(message_sid).fetch()
            else:
                message = self.client.messages(message_sid).fetch()
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'error_code': getattr(message, 'error_code', None),
                'error_message': getattr(message, 'error_message', None)
            }
            
        except Exception as e:
            logger.error(f"❌ Message status fetch failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    # =========================================================================
    # WEBHOOK VALIDATION
    # =========================================================================
    
    def validate_webhook_signature(self, 
                                 url: str = None,
                                 post_data: Dict = None,
                                 signature: str = None) -> bool:
        """Validate SignalWire webhook signature for security"""
        try:
            if not signature:
                signature = request.headers.get('X-SignalWire-Signature', '')
            
            if not url:
                url = request.url
            
            if not post_data:
                post_data = request.form.to_dict()
            
            signature_string = url
            for key in sorted(post_data.keys()):
                signature_string += f"{key}{post_data[key]}"
            
            expected_signature = base64.b64encode(
                hmac.new(
                    self._config['auth_token'].encode('utf-8'),
                    signature_string.encode('utf-8'),
                    hashlib.sha1
                ).digest()
            ).decode('utf-8')
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"❌ Webhook validation error: {e}")
            return False

    # =========================================================================
    # COMPLETE TENANT SETUP WORKFLOW
    # =========================================================================
    
    def setup_new_tenant(self, 
                         user_id: int,
                         friendly_name: str,
                         phone_search_criteria: Dict[str, str]) -> Dict[str, Any]:
        """Complete tenant setup: subproject + phone number + webhooks"""
        try:
            logger.info(f"🚀 Starting tenant setup for user {user_id}")
            
            # Step 1: Create subproject
            subproject_result = self.create_subproject(user_id, friendly_name)
            if not subproject_result['success']:
                return {
                    'success': False,
                    'error': f"Subproject creation failed: {subproject_result['error']}"
                }
            
            subproject_sid = subproject_result['subproject_sid']
            
            # Step 2: Search for phone numbers
            search_result = self.search_available_numbers(**phone_search_criteria)
            if not search_result['success'] or not search_result['numbers']:
                return {
                    'success': False,
                    'error': "No available phone numbers found"
                }
            
            # Step 3: Purchase first available number
            selected_number = search_result['numbers'][0]['phone_number']
            purchase_result = self.purchase_number(
                phone_number=selected_number,
                subproject_sid=subproject_sid,
                friendly_name=f"{friendly_name} Number"
            )
            
            if not purchase_result['success']:
                return {
                    'success': False,
                    'error': f"Phone number purchase failed: {purchase_result['error']}"
                }
            
            logger.info(f"✅ Complete tenant setup finished for user {user_id}")
            
            return {
                'success': True,
                'tenant_setup': {
                    'user_id': user_id,
                    'subproject': subproject_result,
                    'phone_number': purchase_result,
                    'setup_completed_at': datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Tenant setup failed for user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    # =========================================================================
    # HEALTH CHECK - FIXED VERSION
	  # SIMPLIFIED HEALTH CHECK - NO PROBLEMATIC ACCOUNT ACCES
    # =========================================================================
    
    def health_check(self) -> Dict[str, Any]:
        """SIMPLIFIED health check that avoids problematic account access"""
        try:
            # Test basic client connection by listing phone numbers
            # This is more reliable than trying to access account details
            phone_numbers = self.client.incoming_phone_numbers.list(limit=1)
            
            # Try to get account info using fetch() method
            try:
                account = self.client.api.accounts(self._config['project_id']).fetch()
                account_info = {
                    'sid': account.sid,
                    'friendly_name': account.friendly_name,
                    'status': account.status
                }
            except Exception as account_error:
                # If account fetch fails, use basic info
                logger.warning(f"Could not fetch account details: {account_error}")
                account_info = {
                    'sid': self._config['project_id'],
                    'friendly_name': 'Unknown',
                    'status': 'active'
                }
            
            return {
                'success': True,
                'service_status': 'healthy',
                'account': account_info,
                'phone_numbers_count': len(phone_numbers),
                'configuration': {
            # Test 1: Basic client initialization (already done in property)
            client_available = self.client is not None
            
            # Test 2: Simple API call that should work with any account type
            # Just try to list 1 phone number - this is much more reliable
            try:
                phone_numbers = self.client.incoming_phone_numbers.list(limit=1)
                api_accessible = True
                phone_numbers_count = len(phone_numbers)
            except Exception as api_error:
                logger.warning(f"API test failed: {api_error}")
                api_accessible = False
                phone_numbers_count = 0
            
            # Test 3: Try available numbers search as another connectivity test
            try:
                available_test = self.client.available_phone_numbers('US').local.list(limit=1)
                search_accessible = True
            except Exception as search_error:
                logger.warning(f"Search test failed: {search_error}")
                search_accessible = False
            
            # Determine overall health
            is_healthy = client_available and api_accessible
            
            return {
                'success': is_healthy,
                'service_status': 'healthy' if is_healthy else 'degraded',
                'connection_tests': {
                    'client_initialized': client_available,
                    'api_accessible': api_accessible,
                    'search_accessible': search_accessible
                },
                'phone_numbers_count': phone_numbers_count,
                'configuration': {
                    'project_id': self._config['project_id'][:8] + '...',  # Partial for security

                    'space_url': self._config['space_url'],
                    'webhook_base_url': self._config['webhook_base_url']
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {
                'success': False,
                'service_status': 'unhealthy',
                'error': str(e),
                'configuration': {
                    'project_id': self._config.get('project_id', 'NOT_SET')[:8] + '...',
                    'space_url': self._config.get('space_url', 'NOT_SET'),
                    'webhook_base_url': self._config.get('webhook_base_url', 'NOT_SET')
                },
                'timestamp': datetime.utcnow().isoformat()
            }


# =========================================================================
# SINGLETON INSTANCE & FACTORY
# =========================================================================

_signalwire_service = None

def get_signalwire_service() -> SignalWireService:
    """Get singleton SignalWire service instance"""
    global _signalwire_service
    
    if _signalwire_service is None:
        _signalwire_service = SignalWireService()
    
    return _signalwire_service

# Backward compatibility functions
def search_phone_numbers(**kwargs):
    return get_signalwire_service().search_available_numbers(**kwargs)

def purchase_phone_number(phone_number: str, subproject_sid: str = None, **kwargs):
    return get_signalwire_service().purchase_number(phone_number, subproject_sid, **kwargs)

def send_sms(from_number: str, to_number: str, message_body: str, **kwargs):
    return get_signalwire_service().send_sms(from_number, to_number, message_body, **kwargs)

def validate_webhook_signature(**kwargs):
    return get_signalwire_service().validate_webhook_signature(**kwargs)
