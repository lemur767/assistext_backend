# app/services/signalwire_service.py
import os
import json
import secrets
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import current_app
from signalwire.rest import Client
from app.extensions import db
from app.models.user import User

class SignalWireService:
    """Complete SignalWire REST API integration service"""
    
    def __init__(self):
        # SignalWire credentials from environment
        self.project_id = os.getenv('SIGNALWIRE_PROJECT')
        self.auth_token = os.getenv('SIGNALWIRE_TOKEN')
        self.space_url = os.getenv('SIGNALWIRE_SPACE')
        self.webhook_base_url = os.getenv('WEBHOOK_BASE_URL', 'https://your-domain.com')
        
        # Validate credentials
        if not all([self.project_id, self.auth_token, self.space_url]):
            raise ValueError("Missing required SignalWire credentials")
        
        # Initialize SignalWire client
        self.client = Client(
            self.project_id,
            self.auth_token,
            signalwire_space_url=f"https://{self.space_url}"
        )
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
    
    def search_and_create_subaccount(self, user_id: int, search_criteria: Dict) -> Dict:
        """Step 1: Create subaccount and search for available numbers"""
        
        try:
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # 1. Create SignalWire subaccount
            friendly_name = f"AssisText - {user.first_name} {user.last_name}"
            subaccount = self._create_subaccount(friendly_name)
            
            self.logger.info(f"Created subaccount {subaccount['sid']} for user {user_id}")
            
            # 2. Search for available numbers using the subaccount
            available_numbers = self._search_available_numbers(
                subaccount['sid'],
                subaccount['auth_token'],
                search_criteria
            )
            
            if not available_numbers:
                # Clean up subaccount if no numbers found
                self._delete_subaccount(subaccount['sid'])
                raise Exception("No available numbers found for your criteria")
            
            # 3. Create selection token (15-minute expiry)
            selection_token = self._generate_selection_token()
            expires_at = datetime.utcnow() + timedelta(minutes=15)
            
            # 4. Store selection session in database
            db.session.execute(
                """
                INSERT INTO number_selection_sessions 
                (selection_token, user_id, subaccount_data, available_numbers, expires_at)
                VALUES (%(token)s, %(user_id)s, %(subaccount)s, %(numbers)s, %(expires)s)
                """,
                {
                    'token': selection_token,
                    'user_id': user_id,
                    'subaccount': json.dumps(subaccount),
                    'numbers': json.dumps(available_numbers),
                    'expires': expires_at
                }
            )
            db.session.commit()
            
            return {
                'success': True,
                'subaccount': {
                    'sid': subaccount['sid'],
                    'friendly_name': subaccount['friendly_name'],
                    'status': subaccount['status']
                },
                'available_numbers': available_numbers[:10],  # Limit to 10
                'selection_token': selection_token,
                'expires_in': 15 * 60  # 15 minutes in seconds
            }
            
        except Exception as e:
            self.logger.error(f"Search and subaccount creation failed: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    def purchase_number_and_configure_webhook(
        self, 
        selection_token: str, 
        selected_phone_number: str,
        custom_webhook_url: Optional[str] = None
    ) -> Dict:
        """Step 2: Purchase selected number and configure webhook"""
        
        try:
            # 1. Retrieve and validate selection session
            session = db.session.execute(
                """
                SELECT user_id, subaccount_data, available_numbers 
                FROM number_selection_sessions 
                WHERE selection_token = %(token)s AND expires_at > %(now)s
                """,
                {'token': selection_token, 'now': datetime.utcnow()}
            ).fetchone()
            
            if not session:
                raise Exception("Invalid or expired selection token")
            
            user_id, subaccount_json, numbers_json = session
            subaccount_data = json.loads(subaccount_json)
            available_numbers = json.loads(numbers_json)
            
            # 2. Validate selected number is in available list
            selected_number = next(
                (num for num in available_numbers 
                 if num['phone_number'] == selected_phone_number),
                None
            )
            
            if not selected_number:
                raise Exception("Selected number not in available list")
            
            # 3. Purchase the phone number
            purchased_number = self._purchase_phone_number(
                subaccount_data['sid'],
                subaccount_data['auth_token'],
                selected_phone_number,
                custom_webhook_url
            )
            
            # 4. Store subaccount and phone number in database
            subaccount_id = self._store_subaccount_data(
                user_id, 
                subaccount_data, 
                purchased_number
            )
            
            # 5. Clean up selection session
            db.session.execute(
                "DELETE FROM number_selection_sessions WHERE selection_token = %(token)s",
                {'token': selection_token}
            )
            db.session.commit()
            
            return {
                'success': True,
                'subaccount': {
                    'sid': subaccount_data['sid'],
                    'friendly_name': subaccount_data['friendly_name'],
                    'phone_numbers': [{
                        'phone_number': purchased_number['phone_number'],
                        'phone_number_sid': purchased_number['sid'],
                        'capabilities': purchased_number['capabilities'],
                        'webhook_configured': purchased_number['webhook_configured']
                    }],
                    'webhook_configured': purchased_number['webhook_configured']
                },
                'message': 'Phone number purchased and configured successfully!'
            }
            
        except Exception as e:
            self.logger.error(f"Number purchase failed: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_user_subaccount(self, user_id: int) -> Dict:
        """Get existing subaccount for user"""
        
        try:
            # Query database for existing subaccount
            result = db.session.execute(
                """
                SELECT sa.*, 
                       array_agg(
                           json_build_object(
                               'phone_number', spn.phone_number,
                               'phone_number_sid', spn.phone_number_sid,
                               'capabilities', spn.capabilities,
                               'webhook_configured', spn.webhook_configured
                           )
                       ) as phone_numbers
                FROM signalwire_subaccounts sa
                LEFT JOIN subaccount_phone_numbers spn ON sa.id = spn.subaccount_id
                WHERE sa.user_id = %(user_id)s AND sa.status = 'active'
                GROUP BY sa.id
                ORDER BY sa.created_at DESC
                LIMIT 1
                """,
                {'user_id': user_id}
            ).fetchone()
            
            if not result:
                return {'success': True, 'subaccount': None}
            
            return {
                'success': True,
                'subaccount': {
                    'sid': result.subaccount_sid,
                    'friendly_name': result.friendly_name,
                    'status': result.status,
                    'monthly_limit': result.monthly_message_limit,
                    'current_usage': result.current_usage,
                    'phone_numbers': result.phone_numbers if result.phone_numbers[0] else [],
                    'created_at': result.created_at.isoformat()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get subaccount: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def test_webhook(self, subaccount_sid: str) -> Dict:
        """Test webhook configuration for subaccount"""
        
        try:
            # Get subaccount phone number
            result = db.session.execute(
                """
                SELECT spn.phone_number, spn.phone_number_sid
                FROM subaccount_phone_numbers spn
                JOIN signalwire_subaccounts sa ON spn.subaccount_id = sa.id
                WHERE sa.subaccount_sid = %(sid)s
                LIMIT 1
                """,
                {'sid': subaccount_sid}
            ).fetchone()
            
            if not result:
                raise Exception("No phone number found for subaccount")
            
            # Send test message to webhook
            webhook_url = f"{self.webhook_base_url}/api/webhooks/signalwire/sms/{subaccount_sid}"
            
            # Test webhook by sending a test SMS (optional - can be a simple HTTP test)
            test_response = self._test_webhook_endpoint(webhook_url)
            
            return {
                'success': True,
                'message': 'Webhook test successful',
                'webhook_url': webhook_url,
                'response': test_response
            }
            
        except Exception as e:
            self.logger.error(f"Webhook test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # Private helper methods
    
    def _create_subaccount(self, friendly_name: str) -> Dict:
        """Create SignalWire subaccount"""
        
        try:
            subaccount = self.client.api.accounts.create(
                friendly_name=friendly_name
            )
            
            return {
                'sid': subaccount.sid,
                'auth_token': subaccount.auth_token,
                'friendly_name': subaccount.friendly_name,
                'status': subaccount.status
            }
            
        except Exception as e:
            raise Exception(f"Subaccount creation failed: {e}")
    
    def _search_available_numbers(
        self, 
        subaccount_sid: str, 
        subaccount_token: str,
        criteria: Dict
    ) -> List[Dict]:
        """Search available numbers using subaccount"""
        
        try:
            # Create client for subaccount
            subaccount_client = Client(
                subaccount_sid,
                subaccount_token,
                signalwire_space_url=f"https://{self.space_url}"
            )
            
            # Search local numbers based on criteria
            search_params = {}
            if criteria.get('area_code'):
                search_params['area_code'] = criteria['area_code']
            if criteria.get('locality'):
                search_params['in_locality'] = criteria['locality']
            
            numbers = subaccount_client.available_phone_numbers(
                criteria.get('country', 'CA')
            ).local.list(
                limit=criteria.get('limit', 20),
                **search_params
            )
            
            return [
                {
                    'phone_number': num.phone_number,
                    'friendly_name': num.friendly_name or num.phone_number,
                    'locality': num.locality,
                    'region': num.region,
                    'capabilities': {
                        'voice': getattr(num.capabilities, 'voice', True),
                        'sms': getattr(num.capabilities, 'sms', True),
                        'mms': getattr(num.capabilities, 'mms', True)
                    }
                }
                for num in numbers
            ]
            
        except Exception as e:
            self.logger.error(f"Number search failed: {e}")
            return []
    
    def _purchase_phone_number(
        self, 
        subaccount_sid: str, 
        subaccount_token: str,
        phone_number: str,
        custom_webhook_url: Optional[str] = None
    ) -> Dict:
        """Purchase phone number with webhook configuration"""
        
        try:
            # Create client for subaccount
            subaccount_client = Client(
                subaccount_sid,
                subaccount_token,
                signalwire_space_url=f"https://{self.space_url}"
            )
            
            # Default webhook URL
            webhook_url = (custom_webhook_url or 
                          f"{self.webhook_base_url}/api/webhooks/signalwire/sms/{subaccount_sid}")
            
            # Purchase number with webhook configuration
            purchased_number = subaccount_client.incoming_phone_numbers.create(
                phone_number=phone_number,
                friendly_name=f"AssisText - {phone_number}",
                sms_url=webhook_url,
                sms_method='POST',
                voice_url=f"{webhook_url}/voice",
                voice_method='POST',
                status_callback=f"{webhook_url}/status",
                status_callback_method='POST'
            )
            
            return {
                'sid': purchased_number.sid,
                'phone_number': purchased_number.phone_number,
                'capabilities': {
                    'voice': getattr(purchased_number.capabilities, 'voice', True),
                    'sms': getattr(purchased_number.capabilities, 'sms', True),
                    'mms': getattr(purchased_number.capabilities, 'mms', True)
                },
                'webhook_configured': True,
                'webhook_url': webhook_url
            }
            
        except Exception as e:
            raise Exception(f"Number purchase failed: {e}")
    
    def _store_subaccount_data(
        self, 
        user_id: int, 
        subaccount_data: Dict, 
        purchased_number: Dict
    ) -> int:
        """Store subaccount and phone number data in database"""
        
        # Insert subaccount record
        subaccount_id = db.session.execute(
            """
            INSERT INTO signalwire_subaccounts 
            (user_id, subaccount_sid, friendly_name, auth_token, webhook_url, status, monthly_message_limit)
            VALUES (%(user_id)s, %(sid)s, %(name)s, %(token)s, %(webhook)s, %(status)s, %(limit)s)
            RETURNING id
            """,
            {
                'user_id': user_id,
                'sid': subaccount_data['sid'],
                'name': subaccount_data['friendly_name'],
                'token': subaccount_data['auth_token'],
                'webhook': purchased_number['webhook_url'],
                'status': 'active',
                'limit': 1000  # Default limit
            }
        ).fetchone()[0]
        
        # Insert phone number record
        db.session.execute(
            """
            INSERT INTO subaccount_phone_numbers 
            (subaccount_id, phone_number, phone_number_sid, capabilities, webhook_configured)
            VALUES (%(subaccount_id)s, %(phone)s, %(sid)s, %(caps)s, %(webhook)s)
            """,
            {
                'subaccount_id': subaccount_id,
                'phone': purchased_number['phone_number'],
                'sid': purchased_number['sid'],
                'caps': json.dumps(purchased_number['capabilities']),
                'webhook': purchased_number['webhook_configured']
            }
        )
        
        return subaccount_id
    
    def _delete_subaccount(self, subaccount_sid: str):
        """Delete SignalWire subaccount"""
        try:
            self.client.api.accounts(subaccount_sid).delete()
        except Exception as e:
            self.logger.error(f"Failed to delete subaccount {subaccount_sid}: {e}")
    
    def _generate_selection_token(self) -> str:
        """Generate secure selection token"""
        return secrets.token_urlsafe(32)
    
    def _test_webhook_endpoint(self, webhook_url: str) -> Dict:
        """Test webhook endpoint availability"""
        import requests
        
        try:
            response = requests.post(
                webhook_url + '/test',
                json={'test': True, 'timestamp': datetime.utcnow().isoformat()},
                timeout=5
            )
            return {
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            return {
                'error': str(e)
            }