# app/routes/webhooks.py
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import logging
import json
import os
import re

from app.models.user import User
from app.models.message import Message
from app.extensions import db

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')

def format_phone_number(phone: str) -> str:
    """Format phone number to E.164 format"""
    # Remove all non-digit characters
    digits = re.sub(r'[^\d]', '', phone)
    
    # Add +1 for North American numbers if not present
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    
    return phone  # Return as-is if can't format

@webhooks_bp.route('/sms', methods=['POST'])
def handle_incoming_sms():
    """
    Handle incoming SMS messages from SignalWire
    
    SignalWire sends webhook data as application/x-www-form-urlencoded
    """
    try:
        # Get signature for validation
        signature = request.headers.get('X-SignalWire-Signature', '')
        
        # Validate webhook signature for security (skip in development)
        if os.getenv('FLASK_ENV') != 'development':
            if not validate_signalwire_signature(request.get_data(), signature):
                logger.warning(f"Invalid SignalWire signature from {request.remote_addr}")
                return jsonify({'error': 'Invalid signature'}), 403
        
        # Extract form data (SignalWire sends form-encoded data)
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        message_body = request.form.get('Body', '')
        message_sid = request.form.get('MessageSid', '')
        account_sid = request.form.get('AccountSid', '')
        
        # Log the incoming message
        logger.info(f"Incoming SMS: {from_number} -> {to_number}: {message_body[:50]}...")
        
        # Find user by phone number
        user = User.find_by_signalwire_phone(to_number)
        if not user:
            logger.warning(f"No user found for phone number: {to_number}")
            return generate_error_response("User not found")
        
        # Verify the account SID matches user's subproject
        if user.signalwire_subproject_id != account_sid:
            logger.warning(f"Account SID mismatch for user {user.id}")
            return generate_error_response("Account mismatch")
        
        # Check if user's trial has expired
        if user.is_trial_user and user.trial_days_remaining <= 0:
            logger.info(f"Trial expired for user {user.id}")
            return generate_trial_expired_response(user)
        
        # Save incoming message to database
        incoming_message = Message(
            user_id=user.id,
            from_number=format_phone_number(from_number),
            to_number=format_phone_number(to_number),
            body=message_body,
            direction='inbound',
            status='received',
            external_id=message_sid,
            received_at=datetime.utcnow()
        )
        
        db.session.add(incoming_message)
        db.session.commit()
        
        # Check if user has AI enabled
        if not user.ai_enabled:
            logger.info(f"AI disabled for user {user.id}")
            return generate_success_response("Message received (AI disabled)")
        
        # Check business hours if configured
        if not is_within_business_hours(user):
            logger.info(f"Outside business hours for user {user.id}")
            return generate_out_of_hours_response(user, from_number)
        
        # Process message with AI (async)
        try:
            # Queue AI processing task
            from app.tasks.ai_tasks import process_incoming_message_task
            process_incoming_message_task.delay(
                user_id=user.id,
                message_id=incoming_message.id,
                from_number=from_number,
                message_body=message_body
            )
            
            logger.info(f"Queued AI processing for message {incoming_message.id}")
            
        except Exception as e:
            logger.error(f"Failed to queue AI processing: {e}")
            # Send simple acknowledgment if AI processing fails
            return generate_ai_error_response()
        
        return generate_success_response("Message received and queued for AI processing")
        
    except Exception as e:
        logger.error(f"SMS webhook error: {e}")
        return generate_error_response("Internal server error"), 500


@webhooks_bp.route('/voice', methods=['POST'])
def handle_incoming_voice():
    """Handle incoming voice calls (basic response)"""
    try:
        # Parse form data
        body = request.get_data()
        webhook_data = parse_signalwire_form_data(body.decode('utf-8'))
        
        from_number = webhook_data.get('From', '')
        to_number = webhook_data.get('To', '')
        
        logger.info(f"Incoming voice call: {from_number} -> {to_number}")
        
        # Find user
        user = User.find_by_signalwire_phone(to_number)
        if not user:
            return generate_voice_error_response()
        
        # Generate TwiML response to handle the call
        return generate_voice_response(user)
        
    except Exception as e:
        logger.error(f"Voice webhook error: {e}")
        return generate_voice_error_response()


@webhooks_bp.route('/status', methods=['POST'])
def handle_message_status():
    """Handle message delivery status updates"""
    try:
        body = request.get_data()
        webhook_data = parse_signalwire_form_data(body.decode('utf-8'))
        
        message_sid = webhook_data.get('MessageSid', '')
        message_status = webhook_data.get('MessageStatus', '')
        
        logger.info(f"Message status update: {message_sid} -> {message_status}")
        
        # Update message status in database
        message = Message.query.filter_by(external_id=message_sid).first()
        if message:
            message.status = message_status
            message.updated_at = datetime.utcnow()
            
            # Add delivery timestamp for delivered messages
            if message_status == 'delivered':
                message.delivered_at = datetime.utcnow()
            elif message_status == 'failed':
                message.failed_at = datetime.utcnow()
                message.error_message = webhook_data.get('ErrorMessage', '')
            
            db.session.commit()
            logger.info(f"Updated message {message.id} status to {message_status}")
        else:
            logger.warning(f"Message not found for SID: {message_sid}")
        
        return generate_success_response("Status updated")
        
    except Exception as e:
        logger.error(f"Status webhook error: {e}")
        return generate_error_response("Status update failed"), 500


# Helper functions for generating responses

def generate_success_response(message: str = "OK"):
    """Generate successful TwiML response"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <!-- {message} -->
</Response>''', 200, {'Content-Type': 'application/xml'}


def generate_error_response(error: str):
    """Generate error TwiML response"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Sorry, we're unable to process your message at this time. Please try again later.</Message>
    <!-- Error: {error} -->
</Response>''', 200, {'Content-Type': 'application/xml'}


def generate_trial_expired_response(user: User):
    """Generate response for expired trial users"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Your free trial has expired. Please upgrade your account to continue receiving AI responses.</Message>
</Response>''', 200, {'Content-Type': 'application/xml'}


def generate_out_of_hours_response(user: User, from_number: str):
    """Generate response for messages outside business hours"""
    business_hours = user.business_hours or {}
    
    if business_hours.get('auto_reply_message'):
        auto_reply = business_hours['auto_reply_message']
    else:
        auto_reply = "Thank you for your message. I'm currently unavailable but will respond during business hours."
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message to="{from_number}">{auto_reply}</Message>
</Response>''', 200, {'Content-Type': 'application/xml'}


def generate_ai_error_response():
    """Generate response when AI processing fails"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>Thank you for your message. I'll respond shortly.</Message>
</Response>''', 200, {'Content-Type': 'application/xml'}


def generate_voice_response(user: User):
    """Generate TwiML response for voice calls"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello! You've reached {user.full_name}. I'm not available to take your call right now, but please send me a text message and I'll respond as soon as possible. Thank you!</Say>
    <Hangup/>
</Response>''', 200, {'Content-Type': 'application/xml'}


def generate_voice_error_response():
    """Generate error response for voice calls"""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Sorry, this number is not available. Please try again later.</Say>
    <Hangup/>
</Response>''', 200, {'Content-Type': 'application/xml'}


def is_within_business_hours(user: User) -> bool:
    """Check if current time is within user's business hours"""
    if not user.business_hours:
        return True  # No business hours configured, always available
    
    business_hours = user.business_hours
    if not business_hours.get('enabled', True):
        return True  # Business hours disabled
    
    from datetime import datetime, time
    import pytz
    
    now = datetime.utcnow()
    
    # Get user's timezone, default to UTC
    timezone_str = business_hours.get('timezone', 'UTC')
    try:
        user_tz = pytz.timezone(timezone_str)
        user_time = now.replace(tzinfo=pytz.UTC).astimezone(user_tz)
    except:
        user_time = now  # Fallback to UTC
    
    # Get day of week (0 = Monday, 6 = Sunday)
    weekday = user_time.weekday()
    
    # Check if today is a working day
    working_days = business_hours.get('working_days', [0, 1, 2, 3, 4])  # Default Mon-Fri
    if weekday not in working_days:
        return False
    
    # Check if current time is within working hours
    start_time_str = business_hours.get('start_time', '09:00')
    end_time_str = business_hours.get('end_time', '17:00')
    
    try:
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        current_time = user_time.time()
        
        return start_time <= current_time <= end_time
    except:
        return True  # Default to available if parsing fails


# Test endpoint for webhook validation
@webhooks_bp.route('/test', methods=['POST'])
def test_webhook():
    """Test webhook endpoint for development"""
    try:
        data = request.get_json() or {}
        logger.info(f"Test webhook received: {data}")
        
        return jsonify({
            'success': True,
            'message': 'Webhook test successful',
            'received_data': data,
            'headers': dict(request.headers),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Test webhook error: {e}")
        return jsonify({'error': str(e)}), 500