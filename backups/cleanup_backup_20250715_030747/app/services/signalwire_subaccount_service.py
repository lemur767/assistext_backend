import asyncio
import json
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp
import asyncpg
from flask import current_app

from app.extensions import db
from app.models.user import User

class SignalWireSubAccountService:
    """Enhanced SignalWire sub-account management"""
    
    def __init__(self):
        self.space_url = current_app.config['SIGNALWIRE_SPACE_URL']
        self.project_id = current_app.config['SIGNALWIRE_PROJECT_ID']
        self.api_token = current_app.config['SIGNALWIRE_API_TOKEN']
        self.webhook_base_url = current_app.config['SIGNALWIRE_WEBHOOK_BASE_URL']
    
    async def create_subaccount_and_search_numbers(
        self, 
        user_id: int,
        search_criteria: Dict
    ) -> Dict:
        """Step 1: Create sub-account and return available numbers"""
        
        try:
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # 1. Create SignalWire sub-account
            subaccount_data = await self._create_signalwire_subaccount(
                friendly_name=search_criteria.get(
                    'friendly_name', 
                    f"{user.username} - SMS Account"
                )
            )
            
            # 2. Search for available numbers
            available_numbers = await self._search_available_numbers(
                subaccount_data['sid'],
                search_criteria
            )
            
            if not available_numbers:
                # Clean up sub-account if no numbers found
                await self._delete_signalwire_subaccount(subaccount_data['sid'])
                raise Exception("No available numbers found for your criteria")
            
            # 3. Store selection session
            selection_token = self._generate_selection_token()
            expires_at = datetime.utcnow() + timedelta(minutes=15)
            
            # Store in database
            db.session.execute(
                """
                INSERT INTO number_selection_sessions 
                (selection_token, user_id, subaccount_data, available_numbers, expires_at)
                VALUES (%(token)s, %(user_id)s, %(subaccount)s, %(numbers)s, %(expires)s)
                """,
                {
                    'token': selection_token,
                    'user_id': user_id,
                    'subaccount': json.dumps(subaccount_data),
                    'numbers': json.dumps(available_numbers),
                    'expires': expires_at
                }
            )
            db.session.commit()
            
            return {
                'success': True,
                'subaccount': {
                    'sid': subaccount_data['sid'],
                    'friendly_name': subaccount_data['friendly_name'],
                    'status': subaccount_data['status']
                },
                'available_numbers': [
                    {
                        'phone_number': num['phone_number'],
                        'friendly_name': num.get('friendly_name'),
                        'locality': num.get('locality'),
                        'region': num.get('region'),
                        'capabilities': num.get('capabilities', {})
                    }
                    for num in available_numbers[:5]  # Limit to 5
                ],
                'selection_token': selection_token,
                'expires_in': 15 * 60  # 15 minutes
            }
            
        except Exception as e:
            current_app.logger.error(f"Sub-account creation failed: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def complete_purchase_and_setup(
        self,
        selection_token: str,
        selected_phone_number: str,
        webhook_url: Optional[str] = None
    ) -> Dict:
        """Step 2: Purchase selected number and configure webhook"""
        
        try:
            # 1. Retrieve and validate selection session
            session_result = db.session.execute(
                """
                SELECT user_id, subaccount_data, available_numbers 
                FROM number_selection_sessions 
                WHERE selection_token = %(token)s 
                AND expires_at > %(now)s
                """,
                {'token': selection_token, 'now': datetime.utcnow()}
            ).fetchone()
            
            if not session_result:
                raise Exception("Invalid or expired selection token")
            
            user_id, subaccount_json, numbers_json = session_result
            subaccount_data = json.loads(subaccount_json)
            available_numbers = json.loads(numbers_json)
            
            # 2. Validate selected number
            selected_number = next(
                (num for num in available_numbers 
                 if num['phone_number'] == selected_phone_number),
                None
            )
            
            if not selected_number:
                raise Exception("Selected number not in available list")
            
            # 3. Purchase the number
            purchased_number = await self._purchase_phone_number(
                subaccount_data['sid'],
                selected_phone_number
            )
            
            # 4. Configure webhook
            final_webhook_url = webhook_url or f"{self.webhook_base_url}/api/webhooks/signalwire/sms/{subaccount_data['sid']}"
            
            webhook_configured = await self._configure_number_webhook(
                subaccount_data['sid'],
                purchased_number['sid'],
                final_webhook_url
            )
            
            # 5. Store in permanent tables
            # Insert sub-account record
            subaccount_id = db.session.execute(
                """
                INSERT INTO signalwire_subaccounts 
                (user_id, subaccount_sid, friendly_name, auth_token, webhook_url)
                VALUES (%(user_id)s, %(sid)s, %(name)s, %(token)s, %(webhook)s)
                RETURNING id
                """,
                {
                    'user_id': user_id,
                    'sid': subaccount_data['sid'],
                    'name': subaccount_data['friendly_name'],
                    'token': subaccount_data['auth_token'],
                    'webhook': final_webhook_url if webhook_configured else None
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
                    'caps': json.dumps(purchased_number.get('capabilities', {})),
                    'webhook': webhook_configured
                }
            )
            
            # Clean up selection session
            db.session.execute(
                "DELETE FROM number_selection_sessions WHERE selection_token = %(token)s",
                {'token': selection_token}
            )
            
            db.session.commit()
            
            return {
                'success': True,
                'subaccount': {
                    'sid': subaccount_data['sid'],
                    'friendly_name': subaccount_data['friendly_name']
                },
                'purchased_number': {
                    'sid': purchased_number['sid'],
                    'phone_number': purchased_number['phone_number'],
                    'capabilities': purchased_number.get('capabilities', {})
                },
                'webhook_configured': webhook_configured,
                'webhook_url': final_webhook_url if webhook_configured else None
            }
            
        except Exception as e:
            current_app.logger.error(f"Purchase completion failed: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _create_signalwire_subaccount(self, friendly_name: str) -> Dict:
        """Create SignalWire sub-account via API"""
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.project_id, self.api_token)
            
            async with session.post(
                f"https://{self.space_url}/api/laml/2010-04-01/Accounts.json",
                auth=auth,
                data={'FriendlyName': friendly_name}
            ) as response:
                if response.status != 201:
                    raise Exception(f"Failed to create sub-account: {await response.text()}")
                
                return await response.json()
    
    async def _search_available_numbers(
        self, 
        account_sid: str, 
        criteria: Dict
    ) -> List[Dict]:
        """Search for available phone numbers"""
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.project_id, self.api_token)
            
            # Build search parameters
            params = {
                'SmsEnabled': 'true',
                'PageSize': '20'  # Get more than we need
            }
            
            if criteria.get('area_code'):
                params['AreaCode'] = criteria['area_code']
            if criteria.get('contains'):
                params['Contains'] = criteria['contains']
            
            country = criteria.get('country', 'US')
            url = f"https://{self.space_url}/api/laml/2010-04-01/Accounts/{account_sid}/AvailablePhoneNumbers/{country}/Local.json"
            
            async with session.get(url, auth=auth, params=params) as response:
                if response.status != 200:
                    raise Exception(f"Failed to search numbers: {await response.text()}")
                
                data = await response.json()
                return data.get('available_phone_numbers', [])
    
    async def _purchase_phone_number(
        self, 
        account_sid: str, 
        phone_number: str
    ) -> Dict:
        """Purchase a specific phone number"""
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(self.project_id, self.api_token)
            
            async with session.post(
                f"https://{self.space_url}/api/laml/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers.json",
                auth=auth,
                data={'PhoneNumber': phone_number}
            ) as response:
                if response.status != 201:
                    raise Exception(f"Failed to purchase number: {await response.text()}")
                
                return await response.json()
    
    async def _configure_number_webhook(
        self, 
        account_sid: str, 
        phone_number_sid: str, 
        webhook_url: str
    ) -> bool:
        """Configure SMS webhook for purchased number"""
        try:
            async with aiohttp.ClientSession() as session:
                auth = aiohttp.BasicAuth(self.project_id, self.api_token)
                
                async with session.post(
                    f"https://{self.space_url}/api/laml/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers/{phone_number_sid}.json",
                    auth=auth,
                    data={
                        'SmsUrl': webhook_url,
                        'SmsMethod': 'POST',
                        'SmsStatusCallback': f"{webhook_url}/status"
                    }
                ) as response:
                    return response.status == 200
        except:
            return False
    
    def _generate_selection_token(self) -> str:
        """Generate secure selection token"""
        return f"sel_{int(datetime.utcnow().timestamp())}_{secrets.token_urlsafe(16)}"
    
    @staticmethod
    def cleanup_expired_sessions():
        """Clean up expired selection sessions (run as background task)"""
        db.session.execute(
            "DELETE FROM number_selection_sessions WHERE expires_at < %(now)s",
            {'now': datetime.utcnow()}
        )
        db.session.commit()