# app/api/webhooks.py
from flask import Blueprint, request, jsonify, current_app
from app.models.user import User
from app.models.profile import Profile
from app.utils.twilio_helpers import validate_twilio_signature
from app.services.message_handler import handle_incoming_message
from app.extensions import db
from app.models.twilio_usage import TwilioUsage

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/sms', methods=['POST'])
def sms_webhook():
    """Webhook for incoming SMS messages from Twilio"""
    # Extract message details
    message_text = request.form.get('Body', '').strip()
    sender_number = request.form.get('From', '')
    recipient_number = request.form.get('To', '')
    account_sid = request.form.get('AccountSid', '')
    
    # Find profile based on recipient number
    profile = Profile.query.filter_by(phone_number=recipient_number).first()
    if not profile:
        current_app.logger.warning(f"Received message for unknown number: {recipient_number}")
        return '', 204
    
    # Get the user who owns this profile
    user = User.query.get(profile.user_id)
    
    # Validate the request came from this user's Twilio account or a subaccount
    valid_account = False
    
    if user.twilio_account_sid == account_sid:
        # Direct match with user's account
        valid_account = True
    elif user.twilio_parent_account:
        # This is a subaccount under our master account, so we can validate with master creds
        valid_account = validate_twilio_signature(request)
    else:
        # External account - we need to validate using API key
        valid_account = validate_twilio_signature(request, user.twilio_api_key_secret)
    
    if not valid_account:
        current_app.logger.warning(f"Invalid Twilio signature for profile {profile.id}")
        return 'Invalid request signature', 403
    
    # Update usage tracking (increment SMS count)
    if user.twilio_usage_tracker:
        user.twilio_usage_tracker.sms_count += 1
        db.session.commit()
    
    # Process message asynchronously
    task_queue.enqueue(
        handle_incoming_message,
        profile.id,
        message_text,
        sender_number
    )
    
    # Return empty response to Twilio
    return '', 204