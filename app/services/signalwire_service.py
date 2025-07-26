# app/services/signalwire_service.py - Separated functions with clear responsibilities
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import secrets
from signalwire.rest import Client as SignalWireClient

logger = logging.getLogger(__name__)

class SignalWireService:
    def __init__(self):
        self.project_id = os.getenv('SIGNALWIRE_PROJECT_ID')
        self.auth_token = os.getenv('SIGNALWIRE_AUTH_TOKEN')
        self.space = os.getenv('SIGNALWIRE_SPACE_URL').replace('https://', '')
        self.webhook_base_url = os.getenv('WEBHOOK_BASE_URL')
        
        # Main account client
        self.client = SignalWireClient(
            self.project_id,
            self.auth_token,
            signalwire_space_url=f"https://{self.space}"
        )

    # ============================================================================
    # SUBPROJECT MANAGEMENT
    # ============================================================================
    
    def create_subproject_for_user(self, user_id: int, username: str, email: str) -> Dict[str, Any]:
        """Create dedicated subproject for user during registration"""
        try:
            friendly_name = f"AssisText-{username}-{user_id}"
            
            logger.info(f"Creating subproject for user {user_id}: {friendly_name}")
            
            # Create subproject under main account
            subproject = self.client.api.accounts.create(
                friendly_name=friendly_name
            )
            
            logger.info(f"✅ Created subproject {subproject.sid} for user {user_id}")
            
            return {
                'success': True,
                'subproject_sid': subproject.sid,
                'subproject_token': subproject.auth_token,
                'friendly_name': subproject.friendly_name,
                'status': subproject.status,
                'created_at': subproject.date_created
            }
            
        except Exception as e:
            logger.error(f"❌ Subproject creation failed for user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_subproject_client(self, user):
        """Get SignalWire client for user's subproject"""
        try:
            if not user.signalwire_subproject_sid or not user.signalwire_subproject_token:
                raise Exception("User does not have subproject configured")
            
            return SignalWireClient(
                user.signalwire_subproject_sid,
                user.signalwire_subproject_token,
                signalwire_space_url=f"https://{self.space}"
            )
        except Exception as e:
            logger.error(f"Failed to get subproject client for user {user.id}: {e}")
            return None

    # ============================================================================
    # PHONE NUMBER SEARCH
    # ============================================================================
    
    def search_available_numbers(self, user, search_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Search available numbers using user's subproject"""
        try:
            # Get subproject client
            subproject_client = self.get_subproject_client(user)
            if not subproject_client:
                return {
                    'success': False,
                    'error': 'User subproject not configured'
                }
            
            # Search parameters
            country = search_criteria.get('country', 'CA')
            area_code = search_criteria.get('area_code')
            locality = search_criteria.get('locality')
            limit = min(search_criteria.get('limit', 5), 10)
            
            logger.info(f"Searching numbers for user {user.id} in {country} area {area_code}")
            
            # Search available numbers
            if country.upper() == 'CA':
                available_numbers = subproject_client.available_phone_numbers('CA').local.list(
                    area_code=area_code,
                    in_locality=locality,
                    limit=limit
                )
            else:
                available_numbers = subproject_client.available_phone_numbers('US').local.list(
                    area_code=area_code,
                    in_locality=locality,
                    limit=limit
                )
            
            # Format results
            numbers = []
            for num in available_numbers:
                numbers.append({
                    'phone_number': num.phone_number,
                    'friendly_name': num.friendly_name,
                    'locality': num.locality,
                    'region': num.region,
                    'country': country.upper(),
                    'capabilities': {
                        'voice': getattr(num.capabilities, 'voice', True),
                        'sms': getattr(num.capabilities, 'SMS', True),
                        'mms': getattr(num.capabilities, 'MMS', True)
                    },
                    'monthly_cost': '$1.00'
                })
            
            # Create selection token (15 minutes)
            selection_token = self._create_selection_token(user.signalwire_subproject_sid, numbers)
            
            logger.info(f"✅ Found {len(numbers)} numbers for user {user.id}")
            
            return {
                'success': True,
                'numbers': numbers,
                'count': len(numbers),
                'selection_token': selection_token,
                'expires_in': 900,  # 15 minutes
                'search_criteria': search_criteria
            }
            
        except Exception as e:
            logger.error(f"❌ Number search failed for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'numbers': [],
                'count': 0
            }

    # ============================================================================
    # PHONE NUMBER PURCHASE AND CONFIGURATION
    # ============================================================================
    
    def purchase_and_configure_number(self, user, phone_number: str, selection_token: str) -> Dict[str, Any]:
        """Purchase number and configure webhooks for user's subproject"""
        try:
            # Validate selection token
            if not self._validate_selection_token(selection_token, phone_number):
                return {
                    'success': False,
                    'error': 'Invalid or expired selection token'
                }
            
            # Get subproject client
            subproject_client = self.get_subproject_client(user)
            if not subproject_client:
                return {
                    'success': False,
                    'error': 'User subproject not configured'
                }
            
            logger.info(f"Purchasing number {phone_number} for user {user.id}")
            
            # Purchase phone number with webhook configuration
            purchased_number = subproject_client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=f"AssisText-User-{user.id}",
                # Configure webhooks to point to sync_webhooks endpoints
                sms_url=f"{self.webhook_base_url}/api/webhooks/sync/sms",
                sms_method='POST',
                voice_url=f"{self.webhook_base_url}/api/webhooks/sync/voice",
                voice_method='POST',
                status_callback=f"{self.webhook_base_url}/api/webhooks/sync/status",
                status_callback_method='POST'
            )
            
            logger.info(f"✅ Purchased {phone_number} for user {user.id} (subproject: {user.signalwire_subproject_sid})")
            
            return {
                'success': True,
                'phone_number_sid': purchased_number.sid,
                'phone_number': purchased_number.phone_number,
                'friendly_name': purchased_number.friendly_name,
                'capabilities': purchased_number.capabilities,
                'sms_url': purchased_number.sms_url,
                'voice_url': purchased_number.voice_url,
                'webhook_configured': True,
                'webhook_endpoints': {
                    'sms': f"{self.webhook_base_url}/api/webhooks/sms",
                    'voice': f"{self.webhook_base_url}/api/webhooks/voice",
                    'status': f"{self.webhook_base_url}/api/webhooks/status"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Number purchase failed for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    # ============================================================================
    # PHONE NUMBER SUSPENSION/ACTIVATION
    # ============================================================================
    
    def suspend_user_number(self, user) -> Dict[str, Any]:
        """Suspend user's phone number due to payment issues"""
        try:
            if not user.signalwire_phone_number_sid:
                return {'success': False, 'error': 'No phone number to suspend'}
            
            # Get subproject client
            subproject_client = self.get_subproject_client(user)
            if not subproject_client:
                return {'success': False, 'error': 'Cannot access user subproject'}
            
            # Update phone number to remove webhooks (effectively suspending)
            suspended_number = subproject_client.incoming_phone_numbers(user.signalwire_phone_number_sid).update(
                sms_url='',  # Remove SMS webhook
                voice_url='',  # Remove voice webhook
                status_callback='',  # Remove status callback
                friendly_name= f"AssisText-User-{user.id}-Suspended"
            )
            
            logger.info(f"✅ Suspended number {user.signalwire_phone_number} for user {user.id}")
            
            return {
                'success': True,
                'action': 'suspended',
                'phone_number': user.signalwire_phone_number,
                'message': 'Phone number suspended due to payment issues'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to suspend number for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def activate_user_number(self, user) -> Dict[str, Any]:
        """Reactivate user's phone number after payment"""
        try:
            if not user.signalwire_phone_number_sid:
                return {'success': False, 'error': 'No phone number to activate'}
            
            # Get subproject client
            subproject_client = self.get_subproject_client(user)
            if not subproject_client:
                return {'success': False, 'error': 'Cannot access user subproject'}
            
            # Restore webhooks to reactivate the number
            activated_number = subproject_client.incoming_phone_numbers(user.signalwire_phone_number_sid).update(
                sms_url=f"{self.webhook_base_url}/api/webhooks/sync/sms",
                sms_method='POST',
                voice_url=f"{self.webhook_base_url}/api/webhooks/sync/voice",
                voice_method='POST',
                status_callback=f"{self.webhook_base_url}/api/webhooks/sync/status",
                status_callback_method='POST',
                friendly_name= f"AssisText-User-{user.id}-Active"
            )
            
            logger.info(f"✅ Activated number {user.signalwire_phone_number} for user {user.id}")
            
            return {
                'success': True,
                'action': 'activated',
                'phone_number': user.signalwire_phone_number,
                'message': 'Phone number reactivated'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to activate number for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    # ============================================================================
    # UTILITY FUNCTIONS
    # ============================================================================
    
    def _create_selection_token(self, subproject_sid: str, numbers: List[Dict]) -> str:
        """Create secure selection token for number purchase"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=15)
        
        # Store in Redis or cache (implement based on your caching solution)
        token_data = {
            'subproject_sid': subproject_sid,
            'numbers': numbers,
            'expires_at': expires_at.isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        # TODO: Implement actual token storage
        #cache.set(f"selection_token:{token}", json.dumps(token_data), timeout=900)
        
        return token
    
    def _validate_selection_token(self, token: str, phone_number: str) -> bool:
        """Validate selection token and check if number is in allowed list"""
        try:
            
            #token_data = cache.get(f"selection_token:{token}")
            #if not token_data:
             #   return False
            
            token_data = json.loads(token_data)
            return True
        except Exception:
            return False
    
    def get_user_phone_number_info(self, user) -> Dict[str, Any]:
        """Get detailed info about user's phone number"""
        try:
            if not user.signalwire_phone_number_sid:
                return {'success': False, 'error': 'No phone number configured'}
            
            subproject_client = self.get_subproject_client(user)
            if not subproject_client:
                return {'success': False, 'error': 'Cannot access user subproject'}
            
            number_info = subproject_client.incoming_phone_numbers(user.signalwire_phone_number_sid).fetch()
            
            return {
                'success': True,
                'phone_number': number_info.phone_number,
                'friendly_name': number_info.friendly_name,
                'sms_url': number_info.sms_url,
                'voice_url': number_info.voice_url,
                'status_callback': number_info.status_callback,
                'is_suspended': not bool(number_info.sms_url),  # Suspended if no SMS URL
                'capabilities': number_info.capabilities
            }
            
        except Exception as e:
            logger.error(f"Failed to get number info for user {user.id}: {e}")
            return {'success': False, 'error': str(e)}
        
_signalwire_service = None

def get_signalwire_service() -> SignalWireService:
    """Get singleton SignalWire service instance"""
    global _signalwire_service
    
    if _signalwire_service is None:
        _signalwire_service = SignalWireService()
    
    return _signalwire_service