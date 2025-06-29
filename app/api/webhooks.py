from flask import Blueprint, request, jsonify, current_app
from app.models.profile import Profile
from app.extensions import db
import logging

# Import SignalWire functions
try:
    from app.utils.signalwire_helpers import validate_signalwire_webhook_request, send_sms
    SIGNALWIRE_AVAILABLE = True
    print("✅ SignalWire helpers imported successfully in webhooks.py")
except ImportError as e:
    SIGNALWIRE_AVAILABLE = False
    print(f"❌ SignalWire import error in webhooks.py: {e}")

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/signalwire/sms', methods=['POST'])
def handle_incoming_sms():
    """Handle incoming SMS messages from SignalWire webhook"""
    try:
        # Log the incoming request
        logger.info("Received SignalWire webhook request")
        
        # Get webhook data from SignalWire
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        message_body = request.form.get('Body', '').strip()
        message_sid = request.form.get('MessageSid')
        
        logger.info(f"Incoming SMS: From={from_number}, To={to_number}, Body='{message_body}'")
        
        if not all([from_number, to_number, message_body]):
            logger.warning("Missing required webhook parameters")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Find the profile associated with this phone number
        profile = Profile.query.filter_by(phone_number=to_number, is_active=True).first()
        
        if not profile:
            logger.warning(f"No active profile found for number {to_number}")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Generate basic auto-response
        try:
            message_lower = message_body.lower().strip()
            
            if any(word in message_lower for word in ['hi', 'hello', 'hey']):
                ai_response = f"Hello! Thanks for contacting {profile.name}. How can I help you today?"
            elif any(word in message_lower for word in ['help', 'info']):
                ai_response = f"Hi! I'm the AI assistant for {profile.name}. What would you like to know?"
            elif 'stop' in message_lower:
                ai_response = "You have been unsubscribed. Reply START to opt back in."
            elif 'start' in message_lower:
                ai_response = f"Welcome back to {profile.name}! You're subscribed to receive messages."
            else:
                ai_response = f"Thanks for your message! I'm {profile.name}'s AI assistant. I'll respond as soon as possible."
            
            if ai_response and SIGNALWIRE_AVAILABLE:
                # Send AI response back via SignalWire
                response_result = send_sms(
                    from_number=to_number,  # Your SignalWire number
                    to_number=from_number,  # User's number
                    body=ai_response
                )
                
                if response_result.get('success'):
                    logger.info(f"AI response sent successfully to {from_number}")
                else:
                    logger.error(f"Failed to send AI response to {from_number}: {response_result.get('error')}")
            else:
                logger.warning("AI response not sent - SignalWire not available or no response generated")
        
        except Exception as ai_error:
            logger.error(f"Error generating/sending AI response: {str(ai_error)}")
        
        # Return XML response to SignalWire (required format)
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
    except Exception as e:
        logger.error(f"Error handling incoming SMS webhook: {str(e)}")
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 500

@webhooks_bp.route('/test', methods=['GET', 'POST'])
def test_webhook():
    """Test webhook endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'SignalWire webhook endpoint is working',
        'method': request.method,
        'signalwire_available': SIGNALWIRE_AVAILABLE
    }), 200

@webhooks_bp.route('/signalwire/test-sms', methods=['POST'])
def test_sms_webhook():
    """Test SMS webhook with sample data"""
    try:
        # Simulate SignalWire webhook data
        test_data = {
            'From': '+1234567890',
            'To': '+1416555xxxx',
            'Body': 'Test message',
            'MessageSid': 'test_message_sid'
        }
        
        return jsonify({
            'status': 'test_completed',
            'message': 'SMS webhook test completed',
            'test_data': test_data,
            'signalwire_available': SIGNALWIRE_AVAILABLE
        }), 200
        
    except Exception as e:
        logger.error(f"Error in test SMS webhook: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
