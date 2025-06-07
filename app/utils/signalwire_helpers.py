from signalwire.rest import Client
from signalwire.request_validator import RequestValidator
from flask import current_app
import os


def get_signalwire_client():
    """Get configured SignalWire client"""
    return Client(
        current_app.config['SIGNALWIRE_PROJECT_ID'],
        current_app.config['SIGNALWIRE_AUTH_TOKEN'],
        signalwire_space_url=current_app.config['SIGNALWIRE_SPACE_URL']
    )


def send_sms(from_number, to_number, body):
    """Send SMS using SignalWire"""
    client = get_signalwire_client()
    
    message = client.messages.create(
        body=body,
        from_=from_number,
        to=to_number
    )
    
    return message


def validate_signalwire_request(request):
    """Validate that request came from SignalWire"""
    if not current_app.config['VERIFY_SIGNALWIRE_SIGNATURE']:
        return True
    
    # Get SignalWire signature from request headers
    signalwire_signature = request.headers.get('X-SignalWire-Signature', '')
    
    if not signalwire_signature:
        current_app.logger.warning("No SignalWire signature found in request")
        return False
    
    # Create validator with signing key from dashboard
    validator = RequestValidator(current_app.config['SIGNALWIRE_SIGNING_KEY'])
    
    # Validate request
    return validator.validate(
        request.url,
        request.form,
        signalwire_signature
    )