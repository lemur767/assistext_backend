
import os
import logging
from typing import Dict, Optional, List
from signalwire.rest import Client
from flask import current_app


class SignalWireClient:
    """SignalWire client wrapper with subproject management and error handling"""
    
    def __init__(self):
        # Use actual environment variable names
        self.project_id = os.getenv('SIGNALWIRE_PROJECT_ID')
        self.auth_token = os.getenv('SIGNALWIRE_API_TOKEN')
        self.space_url = os.getenv('SIGNALWIRE_SPACE_URL')
        
        if not all([self.project_id, self.auth_token, self.space_url]):
            raise ValueError("SignalWire credentials not properly configured. Check SIGNALWIRE_PROJECT_ID, SIGNALWIRE_API_TOKEN, and SIGNALWIRE_SPACE_URL")
        
        self.client = Client(
            self.project_id,
            self.auth_token,
            signalwire_space_url=self.space_url
        )
        
        self.logger = logging.getLogger(__name__)
    
    def create_subproject(self, friendly_name: str) -> Dict:
        """Create SignalWire subproject for user isolation"""
        try:
            subproject = self.client.api.accounts.create(
                friendly_name=friendly_name
            )
            
            self.logger.info(f"Subproject created successfully: {subproject.sid}")
            
            return {
                'success': True,
                'data': {
                    'sid': subproject.sid,
                    'friendly_name': subproject.friendly_name,
                    'auth_token': subproject.auth_token,
                    'status': subproject.status,
                    'date_created': subproject.date_created.isoformat() if subproject.date_created else None
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create subproject: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_message_via_subproject(self, subproject_sid: str, from_number: str, 
                                  to_number: str, body: str) -> Dict:
        """Send SMS message via specific subproject"""
        try:
            # Create subproject client
            subproject_client = Client(
                subproject_sid,
                self.auth_token,  # Parent auth token works for subprojects
                signalwire_space_url=self.space_url
            )
            
            message = subproject_client.messages.create(
                from_=from_number,
                to=to_number,
                body=body
            )
            
            self.logger.info(f"Message sent via subproject {subproject_sid}: {message.sid}")
            
            return {
                'success': True,
                'data': {
                    'sid': message.sid,
                    'status': message.status,
                    'from': message.from_,
                    'to': message.to,
                    'body': message.body,
                    'price': message.price,
                    'subproject_sid': subproject_sid,
                    'date_sent': message.date_sent.isoformat() if message.date_sent else None
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to send message via subproject: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_message(self, from_number: str, to_number: str, body: str) -> Dict:
        """Send SMS message via main project (for compatibility)"""
        try:
            message = self.client.messages.create(
                from_=from_number,
                to=to_number,
                body=body
            )
            
            self.logger.info(f"Message sent successfully: {message.sid}")
            
            return {
                'success': True,
                'data': {
                    'sid': message.sid,
                    'status': message.status,
                    'from': message.from_,
                    'to': message.to,
                    'body': message.body,
                    'price': message.price
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_phone_numbers(self, area_code: str = None, country: str = 'US', 
                           limit: int = 10) -> Dict:
        """Search for available phone numbers"""
        try:
            if area_code:
                numbers = self.client.available_phone_numbers(country).local.list(
                    area_code=area_code,
                    limit=limit
                )
            else:
                numbers = self.client.available_phone_numbers(country).local.list(
                    limit=limit
                )
            
            available_numbers = []
            for number in numbers:
                available_numbers.append({
                    'phone_number': number.phone_number,
                    'friendly_name': number.friendly_name,
                    'locality': number.locality,
                    'region': number.region,
                    'postal_code': number.postal_code,
                    'capabilities': {
                        'voice': getattr(number.capabilities, 'voice', False),
                        'sms': getattr(number.capabilities, 'sms', False),
                        'mms': getattr(number.capabilities, 'mms', False)
                    }
                })
            
            self.logger.info(f"Found {len(available_numbers)} available numbers")
            
            return {
                'success': True,
                'data': available_numbers
            }
            
        except Exception as e:
            self.logger.error(f"Failed to search phone numbers: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def purchase_phone_number(self, phone_number: str, subproject_sid: str = None, 
                            sms_webhook_url: str = None, voice_webhook_url: str = None) -> Dict:
        """Purchase a phone number and assign to subproject"""
        try:
            # Purchase phone number
            purchase_data = {
                'phone_number': phone_number
            }
            
            # Assign to subproject if provided
            if subproject_sid:
                purchase_data['account_sid'] = subproject_sid
            
            # Configure webhooks
            if sms_webhook_url:
                purchase_data['sms_url'] = sms_webhook_url
                purchase_data['sms_method'] = 'POST'
            
            if voice_webhook_url:
                purchase_data['voice_url'] = voice_webhook_url
                purchase_data['voice_method'] = 'POST'
            
            number = self.client.incoming_phone_numbers.create(**purchase_data)
            
            self.logger.info(f"Phone number purchased successfully: {number.sid}")
            
            return {
                'success': True,
                'data': {
                    'sid': number.sid,
                    'phone_number': number.phone_number,
                    'friendly_name': number.friendly_name,
                    'account_sid': getattr(number, 'account_sid', None),
                    'sms_url': getattr(number, 'sms_url', None),
                    'voice_url': getattr(number, 'voice_url', None),
                    'status': 'purchased'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to purchase phone number: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def configure_webhooks(self, phone_number_sid: str, sms_url: str = None, 
                          voice_url: str = None, status_url: str = None) -> Dict:
        """Configure webhooks for a phone number"""
        try:
            update_data = {}
            
            if sms_url:
                update_data['sms_url'] = sms_url
                update_data['sms_method'] = 'POST'
            
            if voice_url:
                update_data['voice_url'] = voice_url
                update_data['voice_method'] = 'POST'
            
            if status_url:
                update_data['status_callback'] = status_url
                update_data['status_callback_method'] = 'POST'
            
            number = self.client.incoming_phone_numbers(phone_number_sid).update(**update_data)
            
            self.logger.info(f"Webhooks configured for: {number.phone_number}")
            
            return {
                'success': True,
                'data': {
                    'phone_number': number.phone_number,
                    'sms_url': getattr(number, 'sms_url', None),
                    'voice_url': getattr(number, 'voice_url', None),
                    'status_callback': getattr(number, 'status_callback', None)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to configure webhooks: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def remove_webhooks_from_number(self, phone_number_sid: str) -> Dict:
        """Remove webhooks from phone number (for suspension)"""
        try:
            number = self.client.incoming_phone_numbers(phone_number_sid).update(
                sms_url='',
                voice_url='',
                status_callback=''
            )
            
            self.logger.info(f"Webhooks removed from: {number.phone_number}")
            
            return {
                'success': True,
                'data': {
                    'phone_number': number.phone_number,
                    'status': 'webhooks_removed'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to remove webhooks: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def release_phone_number(self, phone_number_sid: str) -> Dict:
        """Release a phone number (permanently)"""
        try:
            self.client.incoming_phone_numbers(phone_number_sid).delete()
            
            self.logger.info(f"Phone number released: {phone_number_sid}")
            
            return {
                'success': True,
                'data': {
                    'phone_number_sid': phone_number_sid,
                    'status': 'released'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to release phone number: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_message_status(self, message_sid: str, subproject_sid: str = None) -> Dict:
        """Get message delivery status"""
        try:
            if subproject_sid:
                # Use subproject client
                subproject_client = Client(
                    subproject_sid,
                    self.auth_token,
                    signalwire_space_url=self.space_url
                )
                message = subproject_client.messages(message_sid).fetch()
            else:
                message = self.client.messages(message_sid).fetch()
            
            return {
                'success': True,
                'data': {
                    'sid': message.sid,
                    'status': message.status,
                    'error_code': message.error_code,
                    'error_message': message.error_message,
                    'price': message.price,
                    'date_sent': message.date_sent.isoformat() if message.date_sent else None,
                    'date_updated': message.date_updated.isoformat() if message.date_updated else None
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get message status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_subproject_usage(self, subproject_sid: str, start_date: str = None, 
                           end_date: str = None) -> Dict:
        """Get usage statistics for a subproject"""
        try:
            # Create subproject client
            subproject_client = Client(
                subproject_sid,
                self.auth_token,
                signalwire_space_url=self.space_url
            )
            
            # Get usage records
            filter_params = {}
            if start_date:
                filter_params['start_date'] = start_date
            if end_date:
                filter_params['end_date'] = end_date
            
            usage = subproject_client.usage.records.list(**filter_params)
            
            # Aggregate usage data
            sms_sent = 0
            sms_received = 0
            voice_minutes = 0
            total_cost = 0
            
            for record in usage:
                if record.category == 'sms-outbound':
                    sms_sent += int(record.count or 0)
                elif record.category == 'sms-inbound':
                    sms_received += int(record.count or 0)
                elif record.category == 'voice-outbound':
                    voice_minutes += int(record.count or 0)
                
                if record.price:
                    total_cost += float(record.price)
            
            return {
                'success': True,
                'data': {
                    'subproject_sid': subproject_sid,
                    'sms_sent': sms_sent,
                    'sms_received': sms_received,
                    'voice_minutes': voice_minutes,
                    'total_cost': total_cost,
                    'currency': 'USD',
                    'start_date': start_date,
                    'end_date': end_date
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get subproject usage: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def suspend_subproject(self, subproject_sid: str) -> Dict:
        """Suspend a subproject (disable all services)"""
        try:
            # Get all phone numbers for this subproject
            subproject_client = Client(
                subproject_sid,
                self.auth_token,
                signalwire_space_url=self.space_url
            )
            
            phone_numbers = subproject_client.incoming_phone_numbers.list()
            
            # Remove webhooks from all phone numbers
            suspended_numbers = []
            for number in phone_numbers:
                result = self.remove_webhooks_from_number(number.sid)
                if result['success']:
                    suspended_numbers.append(number.phone_number)
            
            self.logger.info(f"Subproject suspended: {subproject_sid}")
            
            return {
                'success': True,
                'data': {
                    'subproject_sid': subproject_sid,
                    'suspended_numbers': suspended_numbers,
                    'status': 'suspended'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to suspend subproject: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def reactivate_subproject(self, subproject_sid: str, webhook_base_url: str) -> Dict:
        """Reactivate a suspended subproject"""
        try:
            # Get all phone numbers for this subproject
            subproject_client = Client(
                subproject_sid,
                self.auth_token,
                signalwire_space_url=self.space_url
            )
            
            phone_numbers = subproject_client.incoming_phone_numbers.list()
            
            # Restore webhooks for all phone numbers
            reactivated_numbers = []
            for number in phone_numbers:
                # Extract user_id from subproject friendly name or use a default webhook
                webhook_url = f"{webhook_base_url}/api/webhooks/sms"
                
                result = self.configure_webhooks(
                    number.sid,
                    sms_url=webhook_url
                )
                
                if result['success']:
                    reactivated_numbers.append(number.phone_number)
            
            self.logger.info(f"Subproject reactivated: {subproject_sid}")
            
            return {
                'success': True,
                'data': {
                    'subproject_sid': subproject_sid,
                    'reactivated_numbers': reactivated_numbers,
                    'status': 'active'
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to reactivate subproject: {e}")
            return {
                'success': False,
                'error': str(e)
            }

