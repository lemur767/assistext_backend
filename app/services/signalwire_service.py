"""
UNIFIED SignalWire Service Layer
Consolidates ALL SignalWire functionality into ONE service
"""

import os
import logging
import hmac
import hashlib
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
from flask import request
from signalwire.rest import Client as SignalWireClient

logger = logging.getLogger(__name__)

class SignalWireServiceError(Exception):
    """Custom exception for SignalWire service errors"""
    pass

class SignalWireService:
    """UNIFIED SignalWire Service"""
    
    def __init__(self):
        self._client = None
        self._config = self._load_config()
        self._validate_config()
    
    def _load_config(self):
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
    def client(self):
        """Lazy-load SignalWire client"""
        if self._client is None:
            try:
                self._client = SignalWireClient(
                    self._config['project_id'],
                    self._config['auth_token'],
                    signalwire_space_url=self._config['space_url']
                )
                logger.info("SignalWire client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize SignalWire client: {e}")
                raise SignalWireServiceError(f"SignalWire connection failed: {e}")
        
        return self._client

    def create_subproject(self, user_id, friendly_name):
        """Create a dedicated sub-project for multi-tenant isolation"""
        try:
            subproject_name = f"User_{user_id}_{friendly_name}"
            
            subproject = self.client.api.accounts.create(
                friendly_name=subproject_name
            )
            
            logger.info(f"Created subproject: {subproject.sid} for user {user_id}")
            
            return {
                'success': True,
                'subproject_sid': subproject.sid,
                'auth_token': subproject.auth_token,
                'friendly_name': subproject.friendly_name,
                'status': subproject.status,
                'date_created': str(subproject.date_created) if subproject.date_created else None
            }
            
        except Exception as e:
            logger.error(f"Subproject creation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def search_available_numbers(self, country='US', area_code=None, city=None, region=None, contains=None, limit=20):
        """Search for available phone numbers"""
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
                        'sms': True,
                        'mms': True,
                        'voice': True
                    },
                    'monthly_cost': '$1.00'
                })
            
            logger.info(f"Found {len(formatted_numbers)} available numbers")
            
            return {
                'success': True,
                'numbers': formatted_numbers,
                'count': len(formatted_numbers)
            }
            
        except Exception as e:
            logger.error(f"Phone number search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'numbers': [],
                'count': 0
            }

    def purchase_number(self, phone_number, subproject_sid=None, friendly_name=None):
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
            
            logger.info(f"Successfully purchased {phone_number}")
            
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
            logger.error(f"Phone number purchase failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def send_sms(self, from_number, to_number, message_body, subproject_sid=None):
        """Send SMS message"""
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
            
            logger.info(f"SMS sent: {message.sid}")
            
            return {
                'success': True,
                'message_sid': message.sid,
                'status': message.status,
                'from_number': message.from_,
                'to_number': message.to,
                'body': message.body
            }
            
        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_message_status(self, message_sid, subproject_sid=None):
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
            logger.error(f"Message status fetch failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def validate_webhook_signature(self, url=None, post_data=None, signature=None):
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
            logger.error(f"Webhook validation error: {e}")
            return False

    def setup_new_tenant(self, user_id, friendly_name, phone_search_criteria):
        """Complete tenant setup: subproject + phone number + webhooks"""
        try:
            logger.info(f"Starting tenant setup for user {user_id}")
            
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
            
            logger.info(f"Complete tenant setup finished for user {user_id}")
            
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
            logger.error(f"Tenant setup failed for user {user_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def health_check(self):
        """Simplified health check"""
        try:
            # Test basic connectivity by listing phone numbers
            phone_numbers = self.client.incoming_phone_numbers.list(limit=1)
            
            return {
                'success': True,
                'service_status': 'healthy',
                'phone_numbers_count': len(phone_numbers),
                'configuration': {
                    'project_id': self._config['project_id'][:8] + '...',
                    'space_url': self._config['space_url'],
                    'webhook_base_url': self._config['webhook_base_url']
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'success': False,
                'service_status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    def suspend_phone_number(self, phone_number_sid, reason="trial_expired"):
        """
        Suspend a phone number by removing webhook URLs
        This makes the number inactive for receiving/sending SMS
        """
        try:
            # Update the phone number to remove webhook URLs
            updated_number = self.client.incoming_phone_numbers(phone_number_sid).update(
                sms_url='',  # Remove SMS webhook
                voice_url='',  # Remove voice webhook
                status_callback='',  # Remove status callback
                friendly_name=f"SUSPENDED - {reason}"
            )
            
            logger.info(f"✅ Suspended phone number: {updated_number.phone_number} (reason: {reason})")
            
            return {
                'success': True,
                'phone_number': updated_number.phone_number,
                'phone_number_sid': updated_number.sid,
                'status': 'suspended',
                'reason': reason,
                'suspended_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to suspend phone number {phone_number_sid}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

def reactivate_phone_number(self, phone_number_sid, friendly_name=None):
    """
    Reactivate a suspended phone number by restoring webhook URLs
    Called when user subscribes after trial
    """
    try:
        webhook_base = self._config['webhook_base_url']
        
        # Restore webhook URLs
        updated_number = self.client.incoming_phone_numbers(phone_number_sid).update(
            sms_url=f"{webhook_base}/api/webhooks/sms",
            sms_method='POST',
            voice_url=f"{webhook_base}/api/webhooks/voice",
            voice_method='POST', 
            status_callback=f"{webhook_base}/api/webhooks/status",
            status_callback_method='POST',
            friendly_name=friendly_name or 'AssisText Number - Active'
        )
        
        logger.info(f"✅ Reactivated phone number: {updated_number.phone_number}")
        
        return {
            'success': True,
            'phone_number': updated_number.phone_number,
            'phone_number_sid': updated_number.sid,
            'status': 'active',
            'reactivated_at': datetime.utcnow().isoformat(),
            'webhooks': {
                'sms_url': updated_number.sms_url,
                'voice_url': updated_number.voice_url,
                'status_callback': updated_number.status_callback
            }
        }
    except Exception as e:
        logger.error(f"❌ Failed to reactivate phone number {phone_number_sid}: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def transfer_number_ownership(self, phone_number_sid, old_subproject_sid, new_subproject_sid):
    """
    Transfer phone number from trial subproject to paid subproject
    Used when user upgrades from trial
    """
    try:
        # Transfer the phone number to new subproject
        updated_number = self.client.incoming_phone_numbers(phone_number_sid).update(
            account_sid=new_subproject_sid
        )
        
        logger.info(f"✅ Transferred number {updated_number.phone_number} from {old_subproject_sid} to {new_subproject_sid}")
        
        return {
            'success': True,
            'phone_number': updated_number.phone_number,
            'phone_number_sid': updated_number.sid,
            'old_subproject': old_subproject_sid,
            'new_subproject': new_subproject_sid,
            'transferred_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to transfer phone number: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def get_phone_number_status(self, phone_number_sid):
    """
    Get current status of a phone number (active/suspended)
    """
    try:
        phone_number = self.client.incoming_phone_numbers(phone_number_sid).fetch()
        
        # Determine if number is active based on webhook URLs
        is_active = bool(phone_number.sms_url and phone_number.voice_url)
        
        return {
            'success': True,
            'phone_number': phone_number.phone_number,
            'phone_number_sid': phone_number.sid,
            'status': 'active' if is_active else 'suspended',
            'friendly_name': phone_number.friendly_name,
            'webhooks': {
                'sms_url': phone_number.sms_url,
                'voice_url': phone_number.voice_url,
                'status_callback': phone_number.status_callback
            },
            'account_sid': phone_number.account_sid,
            'capabilities': {
                'sms': getattr(phone_number.capabilities, 'sms', False),
                'voice': getattr(phone_number.capabilities, 'voice', False)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get phone number status: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Also add these backward compatibility functions at the bottom of the file:

def suspend_user_phone_number(phone_number_sid, reason="trial_expired"):
    """Backward compatibility function"""
    return get_signalwire_service().suspend_phone_number(phone_number_sid, reason)

def reactivate_user_phone_number(phone_number_sid, friendly_name=None):
    """Backward compatibility function"""
    return get_signalwire_service().reactivate_phone_number(phone_number_sid, friendly_name)

def get_phone_status(phone_number_sid):
    """Backward compatibility function"""
    return get_signalwire_service().get_phone_number_status(phone_number_sid)

# Singleton instance
_signalwire_service = None

def get_signalwire_service():
    """Get singleton SignalWire service instance"""
    global _signalwire_service
    
    if _signalwire_service is None:
        _signalwire_service = SignalWireService()
    
    return _signalwire_service

# Backward compatibility functions
def search_phone_numbers(**kwargs):
    return get_signalwire_service().search_available_numbers(**kwargs)

def purchase_phone_number(phone_number, subproject_sid=None, **kwargs):
    return get_signalwire_service().purchase_number(phone_number, subproject_sid, **kwargs)

def send_sms(from_number, to_number, message_body, **kwargs):
    return get_signalwire_service().send_sms(from_number, to_number, message_body, **kwargs)

def validate_webhook_signature(**kwargs):
    return get_signalwire_service().validate_webhook_signature(**kwargs)
