

import requests
from flask import current_app
from signalwire.rest import Client as SignalWireClient
import base64

def get_signalwire_client():
    """Get configured SignalWire client"""
    return SignalWireClient(
        current_app.config['SIGNALWIRE_PROJECT_ID'],
        current_app.config['SIGNALWIRE_API_TOKEN'],
        signalwire_space_url=current_app.config['SIGNALWIRE_SPACE_URL']
    )

def get_available_numbers(area_code=None, limit=10, country='CA'):
    """Get available phone numbers from SignalWire"""
    client = get_signalwire_client()
    
    try:
        # Search for available numbers
        available_numbers = client.available_phone_numbers('CA').local.list(
            area_code=area_code,
            limit=limit
        )
        
        # Format the response
        formatted_numbers = []
        for number in available_numbers:
            formatted_numbers.append({
                'phone_number': number.phone_number,
                'locality': number.locality,
                'region': number.region,
                'postal_code': number.postal_code,
                'iso_country': number.iso_country,
                'capabilities': {
                    'voice': getattr(number.capabilities, 'voice', True),
                    'sms': getattr(number.capabilities, 'sms', True),
                    'mms': getattr(number.capabilities, 'mms', True)
                }
            })
        
        return formatted_numbers
        
    except Exception as e:
        current_app.logger.error(f"Error fetching available numbers: {e}")
        raise

def purchase_phone_number(phone_number):
    """Purchase a phone number from SignalWire"""
    client = get_signalwire_client()
    
    try:
        # Purchase the number
        purchased_number = client.incoming_phone_numbers.create(
            phone_number=phone_number
        )
        
        return {
            'sid': purchased_number.sid,
            'phone_number': purchased_number.phone_number,
            'account_sid': purchased_number.account_sid,
            'friendly_name': purchased_number.friendly_name
        }
        
    except Exception as e:
        current_app.logger.error(f"Error purchasing number {phone_number}: {e}")
        raise

def configure_number_webhook(phone_number, webhook_url):
    """Configure webhook URL for a phone number"""
    client = get_signalwire_client()
    
    try:
        # Find the phone number resource
        numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if not numbers:
            raise Exception(f"Phone number {phone_number} not found in account")
        
        number = numbers[0]
        
        # Update the webhook URL
        number.update(
            sms_url=webhook_url,
            sms_method='POST'
        )
        
        current_app.logger.info(f"Webhook configured for {phone_number}: {webhook_url}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error configuring webhook for {phone_number}: {e}")
        raise

def send_sms(from_number, to_number, body):
    """Send SMS using SignalWire"""
    client = get_signalwire_client()
    
    try:
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to_number
        )
        
        return {
            'sid': message.sid,
            'status': message.status,
            'error_code': message.error_code,
            'error_message': message.error_message
        }
        
    except Exception as e:
        current_app.logger.error(f"Error sending SMS from {from_number} to {to_number}: {e}")
        raise

def validate_signalwire_request(request):
    """Validate that request came from SignalWire"""
    if not current_app.config.get('VERIFY_SIGNALWIRE_SIGNATURE', True):
        return True
    
    try:
        from signalwire.webhook import WebhookValidator
        
        # Get SignalWire signature from request headers
        signalwire_signature = request.headers.get('X-SignalWire-Signature', '')
        
        # Create validator
        validator = WebhookValidator(current_app.config['SIGNALWIRE_API_TOKEN'])
        
        # Validate request
        return validator.validate(
            request.url,
            request.form,
            signalwire_signature
        )
        
    except ImportError:
        # Fallback validation if SignalWire webhook validator not available
        return True
    except Exception as e:
        current_app.logger.warning(f"SignalWire signature validation failed: {e}")
        return False

def get_number_info(phone_number):
    """Get information about a purchased phone number"""
    client = get_signalwire_client()
    
    try:
        numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if not numbers:
            return None
        
        number = numbers[0]
        return {
            'sid': number.sid,
            'phone_number': number.phone_number,
            'friendly_name': number.friendly_name,
            'sms_url': number.sms_url,
            'voice_url': number.voice_url,
            'status': number.status,
            'capabilities': {
                'voice': number.capabilities.get('voice', False),
                'sms': number.capabilities.get('sms', False),
                'mms': number.capabilities.get('mms', False)
            }
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting number info for {phone_number}: {e}")
        return None

def release_phone_number(phone_number):
    """Release a phone number back to SignalWire"""
    client = get_signalwire_client()
    
    try:
        # Find the phone number resource
        numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        
        if not numbers:
            raise Exception(f"Phone number {phone_number} not found in account")
        
        number = numbers[0]
        
        # Delete the number
        number.delete()
        
        current_app.logger.info(f"Phone number {phone_number} released successfully")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error releasing number {phone_number}: {e}")
        raise

# Optional: Webhook handler for incoming SMS
def handle_incoming_sms(request):
    """Process incoming SMS from SignalWire webhook"""
    
    if not validate_signalwire_request(request):
        current_app.logger.warning("Invalid SignalWire signature")
        return {'error': 'Invalid signature'}, 403
    
    # Extract message details
    message_body = request.form.get('Body', '').strip()
    from_number = request.form.get('From', '')
    to_number = request.form.get('To', '')
    message_sid = request.form.get('MessageSid', '')
    
    return {
        'body': message_body,
        'from': from_number,
        'to': to_number,
        'sid': message_sid
    }