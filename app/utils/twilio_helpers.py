from twilio.rest import Client
from flask import current_app
from app.extensions import db

def get_twilio_client():
    """Get configured Twilio client"""
    return Client(
        current_app.config['TWILIO_ACCOUNT_SID'],
        current_app.config['TWILIO_AUTH_TOKEN']
    )



def validate_twilio_request(request):
    """Validate that request came from Twilio"""
    if not current_app.config['VERIFY_TWILIO_SIGNATURE']:
        return True
        
    from twilio.request_validator import RequestValidator
    
    # Get Twilio signature from request headers
    twilio_signature = request.headers.get('X-Twilio-Signature', '')
    
    # Create validator
    validator = RequestValidator(current_app.config['TWILIO_AUTH_TOKEN'])
    
    # Validate request
    return validator.validate(
        request.url,
        request.form,
        twilio_signature
    )


def validate_twilio_request_for_user(request, user):
    """Validate that request came from a specific user's Twilio account"""
    if not current_app.config['VERIFY_TWILIO_SIGNATURE']:
        return True
        
    from twilio.request_validator import RequestValidator
    
    # Get Twilio signature from request headers
    twilio_signature = request.headers.get('X-Twilio-Signature', '')
    
    # Create validator with user's auth token
    validator = RequestValidator(user.twilio_auth_token)
    
    # Validate request
    return validator.validate(
        request.url,
        request.form,
        twilio_signature
    )
    # app/utils/twilio_helpers.py
def validate_twilio_signature(request, auth_token=None):
    """
    Validate that a request came from Twilio
    If auth_token is provided, use it for validation
    Otherwise use the master account auth token
    """
    if not current_app.config['VERIFY_TWILIO_SIGNATURE']:
        return True
        
    from twilio.request_validator import RequestValidator
    
    # Get Twilio signature from request headers
    twilio_signature = request.headers.get('X-Twilio-Signature', '')
    
    # Determine which auth token to use
    token = auth_token or current_app.config['TWILIO_AUTH_TOKEN']
    
    # Create validator with the appropriate auth token
    validator = RequestValidator(token)
    
    # Validate request
    return validator.validate(
        request.url,
        request.form,
        twilio_signature
    )

def get_twilio_client(user=None):
    """
    Get a configured Twilio client
    If user is provided, use their credentials
    Otherwise use the master account credentials
    """
    if user and user.twilio_account_sid:
        if user.twilio_account_type == 'subaccount' and user.twilio_auth_token:
            # For subaccounts, we have the auth token
            return Client(user.twilio_account_sid, user.twilio_auth_token)
        elif user.twilio_account_type == 'external' and user.twilio_api_key_sid and user.twilio_api_key_secret:
            # For external accounts, we use API key
            return Client(user.twilio_api_key_sid, user.twilio_api_key_secret, 
                         account_sid=user.twilio_account_sid)
    
    # Fallback to master account
    return Client(
        current_app.config['TWILIO_ACCOUNT_SID'],
        current_app.config['TWILIO_AUTH_TOKEN']
    )

def send_sms(from_number, to_number, body, user=None):
    """
    Send SMS using Twilio
    If user is provided, use their Twilio account
    Otherwise use the master account
    """
    client = get_twilio_client(user)
    
    message = client.messages.create(
        body=body,
        from_=from_number,
        to=to_number
    )
    # If using the master account but sending on behalf of a user with a subaccount,
    # update their usage tracker
    if user and user.twilio_usage_tracker and not user.twilio_account_sid:
        user.twilio_usage_tracker.sms_count += 1
        db.session.commit()
    
    return message