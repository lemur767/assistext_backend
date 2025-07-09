from flask import Blueprint, request, jsonify, current_app
from app.models.user import User
from app.models.client import Client
from app.models.message import Message
from app.extensions import db
from datetime import datetime
import logging

webhooks_bp = Blueprint('webhooks', __name__)




def validate_signalwire_signature():
    """Validate SignalWire webhook signature for security"""
    # TODO: Implement actual signature validation
    # This should validate the webhook signature using your SignalWire credentials
    # For now, we'll return True but you should implement proper validation
    return True


def store_message_in_database(message_sid, from_number, to_number, body, 
                            direction, status, user_id=None, client_id=None,
                            related_message_sid=None, is_ai_generated=False,
                            error_message=None):
    """Store message in database with error handling"""
    try:
        # Find or create client for incoming messages
        if direction == 'inbound' and not client_id:
            client = Client.find_or_create(from_number, user_id)
            client_id = client.id
        
        # Create message record
        message = Message(
            message_sid=message_sid,
            user_id=user_id,  # UPDATED: use user_id instead of profile_id
            client_id=client_id,
            sender_number=from_number,
            recipient_number=to_number,
            message_body=body,
            direction=direction,
            status=status,
            timestamp=datetime.utcnow(),
            is_ai_generated=is_ai_generated,
            related_message_sid=related_message_sid,
            error_message=error_message
        )
        
        db.session.add(message)
        db.session.commit()
        
        return message
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Database error storing message: {str(e)}")
        return None


@webhooks_bp.route('/sms', methods=['POST'])
def handle_incoming_sms():
    """
    Handle incoming SMS messages from SignalWire
    UPDATED: Find user by SignalWire phone number instead of profile
    """
    try:
        # Validate SignalWire signature for security
        if not validate_signalwire_signature():
            current_app.logger.warning("Unauthorized webhook attempt")
            return jsonify({"error": "Unauthorized"}), 401
        
        # Parse SignalWire webhook data
        data = request.form
        
        message_sid = data.get('MessageSid')
        from_number = data.get('From')
        to_number = data.get('To')
        body = data.get('Body', '')
        message_status = data.get('MessageStatus', 'received')
        
        current_app.logger.info(f"Incoming SMS: {from_number} -> {to_number}: {body[:50]}...")
        
        # UPDATED: Find user by SignalWire phone number instead of profile
        user = User.query.filter_by(signalwire_phone_number=to_number).first()
        
        if not user:
            current_app.logger.warning(f"No user found for SignalWire number: {to_number}")
            return jsonify({"error": "User not found"}), 404
        
        if not user.is_active:
            current_app.logger.warning(f"User {user.id} is inactive")
            return jsonify({"error": "User inactive"}), 403
        
        # Store incoming message in database
        message = store_message_in_database(
            message_sid=message_sid,
            from_number=from_number,
            to_number=to_number,
            body=body,
            direction='inbound',
            status='received',
            user_id=user.id  # UPDATED: use user.id instead of profile.id
        )
        
        if not message:
            return jsonify({"error": "Failed to store message"}), 500
        
        # Update user message count
        user.update_message_count(received=1)
        db.session.commit()
        
        # Process the message for auto-response
        try:
            from app.services.message_handler import process_incoming_message
            response_message = process_incoming_message(user, body, from_number, message_sid)
            
            if response_message:
                current_app.logger.info(f"Auto-response sent: {response_message.message_body[:50]}...")
        
        except Exception as e:
            current_app.logger.error(f"Error processing incoming message: {str(e)}")
            # Don't fail the webhook - message was stored successfully
        
        return jsonify({"status": "success", "message": "Message processed"}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error handling incoming SMS: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@webhooks_bp.route('/status', methods=['POST'])
def handle_message_status():
    """
    Handle message delivery status updates from SignalWire
    UPDATED: Use user_id instead of profile_id
    """
    try:
        # Validate SignalWire signature
        if not validate_signalwire_signature():
            current_app.logger.warning("Unauthorized status webhook attempt")
            return jsonify({"error": "Unauthorized"}), 401
        
        # Parse status data
        data = request.form
        
        message_sid = data.get('MessageSid')
        message_status = data.get('MessageStatus')
        error_code = data.get('ErrorCode')
        error_message = data.get('ErrorMessage')
        
        current_app.logger.info(f"Status update for {message_sid}: {message_status}")
        
        # Find and update the message
        message = Message.query.filter_by(message_sid=message_sid).first()
        
        if message:
            message.status = message_status
            
            if error_code or error_message:
                message.error_message = f"Error {error_code}: {error_message}" if error_code else error_message
                
                # If message failed, increment retry count
                if message_status in ['failed', 'undelivered']:
                    message.retry_count += 1
            
            message.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"Updated message {message_sid} status to {message_status}")
        else:
            current_app.logger.warning(f"Message not found for SID: {message_sid}")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error handling status update: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@webhooks_bp.route('/test', methods=['GET', 'POST'])
def test_webhook():
    """Test endpoint for webhook configuration"""
    try:
        method = request.method
        
        if method == 'GET':
            return jsonify({
                "status": "success",
                "message": "Webhook endpoint is active",
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        
        elif method == 'POST':
            data = request.form or request.get_json() or {}
            
            current_app.logger.info(f"Test webhook received: {data}")
            
            return jsonify({
                "status": "success",
                "message": "Test webhook processed successfully",
                "received_data": dict(data),
                "timestamp": datetime.utcnow().isoformat()
            }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error in test webhook: {str(e)}")
        return jsonify({"error": "Test webhook failed"}), 500


# Auto-response processing functions (UPDATED to work with User model)

def should_respond_to_message(user, message_body, sender_number):
    """Determine if we should auto-respond to this message"""
    
    # Check if user has AI enabled
    if not user.ai_enabled:
        current_app.logger.info(f"AI disabled for user {user.id}")
        return False
    
    # Check if user has auto-reply enabled
    if not user.auto_reply_enabled:
        current_app.logger.info(f"Auto-reply disabled for user {user.id}")
        return False
    
    # Check daily message limit
    from app.models.message import Message
    today_count = Message.get_daily_count(user.id)
    if today_count >= user.daily_message_limit:
        current_app.logger.info(f"Daily limit reached for user {user.id}: {today_count}/{user.daily_message_limit}")
        return False
    
    # Check if within business hours
    if not is_within_business_hours(user):
        current_app.logger.info(f"Outside business hours for user {user.id}")
        # Check if out of office is enabled
        return user.out_of_office_enabled
    
    # Check for blocked client
    client = Client.query.filter_by(phone_number=sender_number).first()
    if client and client.is_blocked:
        current_app.logger.info(f"Client {sender_number} is blocked")
        return False
    
    # Check user-specific blocking
    if client:
        relationship = client.get_user_relationship(user.id)
        if relationship and relationship.get('is_blocked'):
            current_app.logger.info(f"Client {sender_number} is blocked by user {user.id}")
            return False
    
    return True


def is_within_business_hours(user):
    """Check if current time is within user's business hours"""
    try:
        import pytz
        from datetime import datetime, time
        
        business_hours = user.get_business_hours()
        if not business_hours:
            return True  # Default to always available if no hours set
        
        # Get current time in user's timezone
        user_tz = pytz.timezone(user.timezone or 'UTC')
        current_time = datetime.now(user_tz)
        current_day = current_time.strftime('%A').lower()
        
        # Check if today has business hours configured
        if current_day not in business_hours:
            return False
        
        day_config = business_hours[current_day]
        
        # Check if business hours are enabled for today
        if not day_config.get('enabled', False):
            return False
        
        # Parse start and end times
        start_str = day_config.get('start', '09:00')
        end_str = day_config.get('end', '17:00')
        
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time = datetime.strptime(end_str, '%H:%M').time()
        
        current_time_only = current_time.time()
        
        # Handle overnight hours (e.g., 22:00 to 06:00)
        if start_time > end_time:
            return current_time_only >= start_time or current_time_only <= end_time
        else:
            return start_time <= current_time_only <= end_time
    
    except Exception as e:
        current_app.logger.error(f"Error checking business hours: {str(e)}")
        return True  # Default to available on error


def generate_auto_response(user, message_body, sender_number):
    """Generate appropriate auto-response"""
    
    # Check for keyword-based auto-replies first
    auto_replies = user.get_auto_reply_keywords()
    message_lower = message_body.lower()
    
    for keyword, response in auto_replies.items():
        if keyword.lower() in message_lower:
            current_app.logger.info(f"Keyword match for '{keyword}': {response[:50]}...")
            return response
    
    # Check if outside business hours and out of office is enabled
    if not is_within_business_hours(user) and user.out_of_office_enabled:
        if user.out_of_office_message:
            return user.out_of_office_message
        else:
            return f"Thanks for your message! I'm currently outside my business hours. I'll get back to you during my next available time."
    
    # Generate AI response if enabled
    if user.ai_enabled:
        try:
            from app.services.ai_service import generate_ai_response
            ai_response = generate_ai_response(user, message_body, sender_number)
            if ai_response:
                return ai_response
        except Exception as e:
            current_app.logger.error(f"Error generating AI response: {str(e)}")
    
    # Fallback response
    return "Thanks for your message! I'll get back to you soon."


def send_auto_response(user, response_text, recipient_number, related_message_sid=None):
    """Send auto-response via SignalWire"""
    
    if not user.is_signalwire_configured():
        current_app.logger.error(f"SignalWire not configured for user {user.id}")
        return None
    
    try:
        # TODO: Implement actual SignalWire sending
        # from app.utils.signalwire_helpers import send_sms
        # 
        # signalwire_response = send_sms(
        #     from_number=user.signalwire_phone_number,
        #     to_number=recipient_number,
        #     body=response_text,
        #     user=user
        # )
        
        # For now, create a mock response
        mock_sid = f"SM{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Store outgoing message
        response_message = store_message_in_database(
            message_sid=mock_sid,  # Would be signalwire_response.sid
            from_number=user.signalwire_phone_number,
            to_number=recipient_number,
            body=response_text,
            direction='outbound',
            status='sent',
            user_id=user.id,
            related_message_sid=related_message_sid,
            is_ai_generated=True
        )
        
        if response_message:
            # Update user message count
            user.update_message_count(sent=1)
            db.session.commit()
            
            current_app.logger.info(f"Auto-response sent to {recipient_number}: {response_text[:50]}...")
        
        return response_message
        
    except Exception as e:
        current_app.logger.error(f"Error sending auto-response: {str(e)}")
        return None