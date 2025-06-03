# app/services/twilio_service.py
from flask import current_app
from twilio.rest import Client
from app.exceptions import TwilioAccountError, TwilioNumberError, TwilioBillingError
from app.models.twilio_usage import TwilioUsage
from app.extensions import db
import secrets
import string

class TwilioService:
    def __init__(self, user=None):
        """Initialize with master Twilio credentials or user credentials"""
        self.master_account_sid = current_app.config['TWILIO_ACCOUNT_SID']
        self.master_auth_token = current_app.config['TWILIO_AUTH_TOKEN']
        self.master_client = Client(self.master_account_sid, self.master_auth_token)
        
        self.user = user
        if user and user.twilio_account_sid:
            if user.twilio_account_type == 'subaccount' and user.twilio_auth_token:
                # For subaccounts, we have the auth token
                self.client = Client(user.twilio_account_sid, user.twilio_auth_token)
            elif user.twilio_account_type == 'external' and user.twilio_api_key_sid and user.twilio_api_key_secret:
                # For external accounts, we use API key
                self.client = Client(user.twilio_api_key_sid, user.twilio_api_key_secret, 
                                    account_sid=user.twilio_account_sid)
            else:
                # Fallback to master account if incomplete credentials
                self.client = self.master_client
        else:
            self.client = self.master_client
    
    def create_subaccount(self, user):
        """Create a Twilio subaccount under the master account"""
        # Generate a friendly name for the subaccount
        friendly_name = f"SMS-AI-{user.username}-{user.id}"
        
        try:
            # Create the subaccount
            subaccount = self.master_client.api.accounts.create(friendly_name=friendly_name)
            
            # Store the SID and auth token
            user.twilio_account_sid = subaccount.sid
            user.twilio_auth_token = subaccount.auth_token
            user.twilio_account_type = 'subaccount'
            user.twilio_parent_account = True
            
            # Create API Key for better security
            subaccount_client = Client(subaccount.sid, subaccount.auth_token)
            api_key = subaccount_client.new_keys.create(friendly_name=f"API Key for {user.username}")
            
            # Store the API key credentials
            user.twilio_api_key_sid = api_key.sid
            user.twilio_api_key_secret = api_key.secret
            
            # Create usage tracker
            if not user.twilio_usage_tracker:
                usage = TwilioUsage(user_id=user.id)
                db.session.add(usage)
            
            # Set reasonable limits for trial accounts
            if current_app.config.get('TWILIO_SET_TRIAL_LIMITS', True):
                subaccount.update(status="active")
            
            return True, None
            
        except Exception as e:
            current_app.logger.error(f"Error creating Twilio subaccount: {str(e)}")
            return False, str(e)
    
    def verify_external_account(self, account_sid, auth_token):
        """Verify external Twilio account credentials and permissions"""
        try:
            # Try to connect with the provided credentials
            test_client = Client(account_sid, auth_token)
            
            # Test if we can access account information
            account = test_client.api.accounts(account_sid).fetch()
            
            # Test if we can create API keys
            return True, account.friendly_name
            
        except Exception as e:
            current_app.logger.error(f"Error verifying external Twilio account: {str(e)}")
            return False, str(e)
    
    def connect_external_account(self, user, account_sid, auth_token):
        """Connect a user's existing Twilio account"""
        # First verify the account
        is_valid, account_name = self.verify_external_account(account_sid, auth_token)
        
        if not is_valid:
            return False, f"Invalid Twilio credentials: {account_name}"
        
        try:
            # Create an API key in the external account
            external_client = Client(account_sid, auth_token)
            api_key = external_client.new_keys.create(
                friendly_name=f"SMS-AI-Responder Integration Key"
            )
            
            # Store account information
            user.twilio_account_sid = account_sid
            user.twilio_auth_token = None  # Don't store auth token for external accounts
            user.twilio_api_key_sid = api_key.sid
            user.twilio_api_key_secret = api_key.secret
            user.twilio_account_type = 'external'
            user.twilio_parent_account = False
            
            # Create usage tracker
            if not user.twilio_usage_tracker:
                usage = TwilioUsage(user_id=user.id)
                db.session.add(usage)
            
            return True, None
            
        except Exception as e:
            current_app.logger.error(f"Error connecting external Twilio account: {str(e)}")
            return False, str(e)
    
    def purchase_phone_number(self, area_code=None, country_code='US'):
        """Purchase a phone number for a user's profile"""
        if not self.user or not self.user.twilio_account_sid:
            return False, "User does not have a Twilio account"
        
        try:
            # Search for available numbers
            numbers = self.client.available_phone_numbers(country_code).local.list(
                area_code=area_code,
                sms_enabled=True,
                limit=1
            )
            
            if not numbers:
                return False, f"No available numbers found in area code {area_code}"
            
            # Purchase the first available number
            purchased_number = self.client.incoming_phone_numbers.create(
                phone_number=numbers[0].phone_number,
                sms_url=f"{current_app.config['BASE_URL']}/api/webhooks/sms"
            )
            
            # Update usage tracking
            if self.user.twilio_usage_tracker:
                self.user.twilio_usage_tracker.phone_numbers += 1
                db.session.commit()
            
            return True, purchased_number.phone_number
            
        except Exception as e:
            current_app.logger.error(f"Error purchasing phone number: {str(e)}")
            return False, str(e)
    
    def setup_sms_webhook(self, phone_number):
        """Configure the SMS webhook for a phone number"""
        if not self.user or not self.user.twilio_account_sid:
            return False, "User does not have a Twilio account"
            
        try:
            # Find the phone number in the user's account
            incoming_numbers = self.client.incoming_phone_numbers.list(
                phone_number=phone_number
            )
            
            if not incoming_numbers:
                return False, "Phone number not found in user's account"
            
            # Update the webhook URL
            webhook_url = f"{current_app.config['BASE_URL']}/api/webhooks/sms"
            incoming_numbers[0].update(
                sms_url=webhook_url,
                sms_method='POST'
            )
            
            return True, None
            
        except Exception as e:
            current_app.logger.error(f"Error setting up SMS webhook: {str(e)}")
            return False, str(e)
    
    def get_account_phone_numbers(self):
        """Get all phone numbers in the user's account"""
        if not self.user or not self.user.twilio_account_sid:
            return False, "User does not have a Twilio account"
            
        try:
            numbers = self.client.incoming_phone_numbers.list()
            
            phone_numbers = []
            for number in numbers:
                phone_numbers.append({
                    'sid': number.sid,
                    'phone_number': number.phone_number,
                    'friendly_name': number.friendly_name,
                    'sms_url': number.sms_url,
                    'voice_url': number.voice_url,
                    'capabilities': {
                        'sms': number.capabilities.get('sms', False),
                        'voice': number.capabilities.get('voice', False),
                        'mms': number.capabilities.get('mms', False)
                    }
                })
            
            return True, phone_numbers
            
        except Exception as e:
            current_app.logger.error(f"Error fetching account phone numbers: {str(e)}")
            return False, str(e)
    
    def update_usage_tracking(self):
        """Update usage statistics for billing"""
        if not self.user or not self.user.twilio_account_sid or not self.user.twilio_usage_tracker:
            return False, "User does not have a Twilio account or usage tracker"
        
        try:
            # Get usage records for the current billing period
            today = datetime.today()
            start_date = today.replace(day=1).strftime('%Y-%m-%d')
            
            # Get SMS usage
            sms_usage = self.client.usage.records.today.list(
                category='sms'
            )
            
            # Get voice usage
            voice_usage = self.client.usage.records.today.list(
                category='calls'
            )
            
            # Calculate totals
            sms_count = sum(record.count for record in sms_usage)
            voice_minutes = sum(record.usage for record in voice_usage)
            
            # Update usage tracker
            self.user.twilio_usage_tracker.sms_count = sms_count
            self.user.twilio_usage_tracker.voice_minutes = voice_minutes
            
            # Calculate estimated bill based on your pricing model
            # This is a simplified example - you'll need to customize based on your pricing
            sms_rate = current_app.config.get('SMS_RATE', 0.0075)  # Cost per SMS
            voice_rate = current_app.config.get('VOICE_RATE', 0.015)  # Cost per minute
            number_rate = current_app.config.get('NUMBER_RATE', 1.0)  # Cost per number per month
            
            bill_amount = (
                (sms_count * sms_rate) +
                (voice_minutes * voice_rate) +
                (self.user.twilio_usage_tracker.phone_numbers * number_rate)
            )
            
            self.user.twilio_usage_tracker.current_bill_amount = bill_amount
            db.session.commit()
            
            return True, {
                'sms_count': sms_count,
                'voice_minutes': voice_minutes,
                'phone_numbers': self.user.twilio_usage_tracker.phone_numbers,
                'current_bill_amount': bill_amount
            }
            
        except Exception as e:
            current_app.logger.error(f"Error updating usage tracking: {str(e)}")
            return False, str(e)