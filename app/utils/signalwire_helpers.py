from signalwire.rest import Client as SignalWireClient
from flask import current_app
import logging
import requests
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

def get_signalwire_client():
    """Get configured SignalWire client"""
    return SignalWireClient(
        current_app.config['SIGNALWIRE_PROJECT_ID'],
        current_app.config['SIGNALWIRE_API_TOKEN'],
        signalwire_space_url=current_app.config['SIGNALWIRE_SPACE_URL']
    )

def format_phone_number(phone_number):
    """Format phone number to E.164 format (+1XXXXXXXXXX)"""
    if not phone_number:
        return None
        
    # Remove all non-digit characters
    digits_only = ''.join(filter(str.isdigit, phone_number))
    
    # Handle different input formats
    if len(digits_only) == 10:
        # US number without country code
        return f"+1{digits_only}"
    elif len(digits_only) == 11 and digits_only.startswith('1'):
        # US number with country code
        return f"+{digits_only}"
    elif len(digits_only) > 11:
        # International number
        return f"+{digits_only}"
    else:
        raise ValueError(f"Invalid phone number format: {phone_number}")

def send_signalwire_sms(from_number, to_number, body):
    """Send SMS using SignalWire"""
    client = get_signalwire_client()
    
    try:
        # Format phone numbers
        formatted_from = format_phone_number(from_number)
        formatted_to = format_phone_number(to_number)
        
        # Verify the from_number is in your SignalWire project
        if not is_signalwire_number_available(formatted_from):
            available_numbers = get_signalwire_phone_numbers()
            logger.error(f"From number {formatted_from} not found in SignalWire project. Available: {[n['phone_number'] for n in available_numbers]}")
            raise ValueError(f"From number {formatted_from} not configured in SignalWire project")
        
        message = client.messages.create(
            body=body,
            from_=formatted_from,
            to=formatted_to
        )
        
        logger.info(f"SignalWire SMS sent successfully: {message.sid} from {formatted_from} to {formatted_to}")
        return message
        
    except Exception as e:
        logger.error(f"SignalWire SMS send failed: {str(e)}")
        raise

# Backward compatibility aliases
def send_sms(from_number, to_number, body):
    """Backward compatibility alias for send_signalwire_sms"""
    return send_signalwire_sms(from_number, to_number, body)

def is_signalwire_number_available(phone_number):
    """Check if phone number exists in your SignalWire project"""
    try:
        client = get_signalwire_client()
        numbers = client.incoming_phone_numbers.list()
        project_numbers = [num.phone_number for num in numbers]
        return phone_number in project_numbers
    except Exception as e:
        logger.error(f"Error checking SignalWire numbers: {str(e)}")
        return False

def get_signalwire_phone_numbers():
    """Get all phone numbers available in your SignalWire project with details"""
    try:
        client = get_signalwire_client()
        numbers = client.incoming_phone_numbers.list()
        
        number_details = []
        for num in numbers:
            number_details.append({
                'phone_number': num.phone_number,
                'sid': num.sid,
                'friendly_name': num.friendly_name,
                'sms_url': num.sms_url,
                'sms_method': num.sms_method,
                'capabilities': {
                    'sms': getattr(num.capabilities, 'sms', False),
                    'voice': getattr(num.capabilities, 'voice', False),
                    'mms': getattr(num.capabilities, 'mms', False)
                }
            })
        
        return number_details
        
    except Exception as e:
        logger.error(f"Error fetching SignalWire numbers: {str(e)}")
        return []

def setup_signalwire_webhook_for_number(phone_number, webhook_url=None):
    """Set up SignalWire webhook for a specific phone number"""
    try:
        client = get_signalwire_client()
        
        if not webhook_url:
            webhook_url = urljoin(current_app.config['BASE_URL'], '/api/webhooks/signalwire/sms')
        
        # Find the phone number in your SignalWire project
        numbers = client.incoming_phone_numbers.list()
        target_number = None
        
        for number in numbers:
            if number.phone_number == format_phone_number(phone_number):
                target_number = number
                break
        
        if not target_number:
            logger.error(f"Phone number {phone_number} not found in SignalWire project")
            return False, None
        
        # Update the webhook URL
        updated_number = target_number.update(
            sms_url=webhook_url, 
            sms_method='POST'
        )
        
        logger.info(f"SignalWire webhook configured for {phone_number}: {webhook_url}")
        return True, updated_number.sid
        
    except Exception as e:
        logger.error(f"Error setting up SignalWire webhook for {phone_number}: {str(e)}")
        return False, None

def setup_all_signalwire_webhooks():
    """Set up SignalWire webhooks for all phone numbers in the project"""
    try:
        webhook_url = urljoin(current_app.config['BASE_URL'], '/api/webhooks/signalwire/sms')
        client = get_signalwire_client()
        
        numbers = client.incoming_phone_numbers.list()
        results = []
        
        for number in numbers:
            try:
                updated_number = number.update(
                    sms_url=webhook_url, 
                    sms_method='POST'
                )
                results.append({
                    'phone_number': number.phone_number,
                    'sid': updated_number.sid,
                    'success': True,
                    'webhook_url': webhook_url
                })
                logger.info(f"SignalWire webhook configured for {number.phone_number}")
            except Exception as e:
                results.append({
                    'phone_number': number.phone_number,
                    'sid': number.sid,
                    'success': False,
                    'error': str(e)
                })
                logger.error(f"Failed to configure SignalWire webhook for {number.phone_number}: {str(e)}")
        
        success_count = len([r for r in results if r['success']])
        logger.info(f"SignalWire webhooks configured: {success_count}/{len(numbers)} numbers")
        
        return results
        
    except Exception as e:
        logger.error(f"Error setting up SignalWire webhooks: {str(e)}")
        return []

def validate_signalwire_webhook_request(request):
    """Validate that request came from SignalWire"""
    try:
        # SignalWire uses X-SignalWire-Signature header
        signalwire_signature = request.headers.get('X-SignalWire-Signature', '')
        
        if not signalwire_signature:
            logger.warning("No SignalWire signature found in request headers")
            return False
        
        # Check if request contains expected SignalWire parameters
        required_params = ['AccountSid', 'From', 'To', 'Body']
        has_required = all(param in request.form for param in required_params)
        
        if not has_required:
            logger.warning("Missing required SignalWire parameters")
            return False
        
        # Verify AccountSid matches your project
        account_sid = request.form.get('AccountSid', '')
        if account_sid != current_app.config['SIGNALWIRE_PROJECT_ID']:
            logger.warning(f"Invalid AccountSid: {account_sid}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"SignalWire request validation error: {str(e)}")
        return False

# Create aliases for backward compatibility
def validate_signalwire_request(request):
    """Alias for validate_signalwire_webhook_request"""
    return validate_signalwire_webhook_request(request)

def validate_twilio_request(request):
    """Legacy alias - redirects to SignalWire validation"""
    logger.warning("validate_twilio_request called - redirecting to SignalWire validation")
    return validate_signalwire_webhook_request(request)

def get_signalwire_account_info():
    """Get SignalWire account information"""
    try:
        client = get_signalwire_client()
        account = client.api.accounts(current_app.config['SIGNALWIRE_PROJECT_ID']).fetch()
        
        return {
            'sid': account.sid,
            'friendly_name': account.friendly_name,
            'status': account.status,
            'type': account.type
        }
        
    except Exception as e:
        logger.error(f"Error fetching SignalWire account info: {str(e)}")
        return None

def get_signalwire_integration_status():
    """Get complete SignalWire integration status"""
    try:
        client = get_signalwire_client()
        
        # Test connection with account info
        account = client.api.accounts(current_app.config['SIGNALWIRE_PROJECT_ID']).fetch()
        
        # Get phone numbers with webhook status
        numbers = get_signalwire_phone_numbers()
        
        # Check webhook configuration
        webhook_url = urljoin(current_app.config['BASE_URL'], '/api/webhooks/signalwire/sms')
        configured_webhooks = 0
        
        for number in numbers:
            if number['sms_url'] == webhook_url:
                configured_webhooks += 1
        
        return {
            'status': 'connected',
            'account': {
                'sid': account.sid,
                'friendly_name': account.friendly_name,
                'status': account.status
            },
            'phone_numbers_count': len(numbers),
            'phone_numbers': numbers,
            'webhooks_configured': configured_webhooks,
            'webhook_url': webhook_url,
            'space_url': current_app.config['SIGNALWIRE_SPACE_URL']
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'space_url': current_app.config.get('SIGNALWIRE_SPACE_URL', 'Not configured')
        }
# Add these functions to your app/utils/signalwire_helpers.py if they don't exist

def get_available_phone_numbers(area_code=None, country='CA', limit=20):
    """Get available phone numbers from SignalWire"""
    try:
        client = get_signalwire_client()
        
        search_params = {
            'limit': limit,
            'sms_enabled': True
        }
        
        if area_code:
            search_params['area_code'] = area_code
            
        if country.upper() == 'CA':
            numbers = client.available_phone_numbers('CA').list(**search_params)
        else:
            numbers = client.available_phone_numbers('US').list(**search_params)
        
        return [
            {
                'phone_number': num.phone_number,
                'locality': getattr(num, 'locality', None),
                'region': getattr(num, 'region', None),
                'price': '1.00'
            }
            for num in numbers
        ]
        
    except Exception as e:
        logger.error(f"Error getting available numbers: {e}")
        return []

def purchase_phone_number(phone_number, friendly_name=None, subaccount_sid=None):
    """Purchase a phone number"""
    try:
        client = get_signalwire_client()
        
        purchase_params = {
            'phone_number': phone_number
        }
        
        if friendly_name:
            purchase_params['friendly_name'] = friendly_name
            
        if subaccount_sid:
            purchase_params['account_sid'] = subaccount_sid
        
        purchased_number = client.incoming_phone_numbers.create(**purchase_params)
        
        return {
            'sid': purchased_number.sid,
            'phone_number': purchased_number.phone_number,
            'friendly_name': purchased_number.friendly_name,
            'status': 'active'
        }
        
    except Exception as e:
        logger.error(f"Error purchasing phone number {phone_number}: {e}")
        raise Exception(f"Failed to purchase phone number: {str(e)}")

def configure_number_webhook(phone_number, webhook_url):
    """Configure webhook for a phone number"""
    try:
        client = get_signalwire_client()
        
        # Find the phone number
        numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if not numbers:
            raise Exception(f"Phone number {phone_number} not found in account")
        
        number = numbers[0]
        
        # Update webhook URL
        updated_number = number.update(
            sms_url=webhook_url,
            sms_method='POST'
        )
        
        logger.info(f"Webhook configured for {phone_number}: {webhook_url}")
        return True
        
    except Exception as e:
        logger.error(f"Error configuring webhook for {phone_number}: {e}")
        raise Exception(f"Failed to configure webhook: {str(e)}")

def get_signalwire_phone_numbers():
    """Get all phone numbers in the SignalWire account"""
    try:
        client = get_signalwire_client()
        numbers = client.incoming_phone_numbers.list()
        
        return [
            {
                'phone_number': num.phone_number,
                'friendly_name': num.friendly_name,
                'sid': num.sid,
                'sms_url': getattr(num, 'sms_url', None),
                'status': 'active',
                'capabilities': {
                    'sms': True,
                    'mms': True,
                    'voice': True
                }
            }
            for num in numbers
        ]
        
    except Exception as e:
        logger.error(f"Error getting SignalWire phone numbers: {e}")
        return []
    
# Additional helper functions that might be expected
def get_twilio_client():
    """Legacy function that redirects to SignalWire"""
    logger.warning("get_twilio_client called - redirecting to SignalWire client")
    return get_signalwire_client()

def send_twilio_sms(from_number, to_number, body):
    """Legacy function that redirects to SignalWire SMS"""
    logger.warning("send_twilio_sms called - redirecting to SignalWire SMS")
    return send_signalwire_sms(from_number, to_number, body)
