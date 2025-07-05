"""
SignalWire Webhook Handlers with AI Response Integration
app/api/webhooks.py - Complete implementation for AssisText
"""
from flask import Blueprint, request, Response, current_app, jsonify
from app.services.ai_service import AIService
from app.models.profile import Profile
from app.models.client import Client
from app.models.message import Message
from app.extensions import db
import logging
import hmac
import hashlib
import base64
import os
from urllib.parse import quote_plus

webhooks_bp = Blueprint('webhooks', __name__)

# Initialize AI service
ai_service = AIService()

def validate_signalwire_signature():
    """
    Validate SignalWire webhook signature using HMAC SHA-256
    SignalWire uses X-SignalWire-Signature header
    """
    try:
        # Get signature from headers
        signature = request.headers.get('X-SignalWire-Signature', '')
        
        if not signature:
            current_app.logger.warning("Missing SignalWire webhook signature")
            return False
        
        # Get auth token from environment
        auth_token = os.getenv('SIGNALWIRE_API_TOKEN')
        if not auth_token:
            current_app.logger.error("SIGNALWIRE_API_TOKEN not configured")
            return False
        
        # Build validation string
        url = request.url
        if request.query_string:
            url += '?' + request.query_string.decode('utf-8')
        
        # Get POST data and sort
        post_data = request.form.to_dict()
        sorted_data = []
        for key in sorted(post_data.keys()):
            sorted_data.append(f"{key}{post_data[key]}")
        
        validation_string = url + ''.join(sorted_data)
        
        # Calculate expected signature
        expected_signature = base64.b64encode(
            hmac.new(
                auth_token.encode('utf-8'),
                validation_string.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Compare signatures
        is_valid = hmac.compare_digest(signature, expected_signature)
        
        if not is_valid:
            current_app.logger.warning(f"Invalid SignalWire signature. Expected: {expected_signature}, Got: {signature}")
            return False
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Webhook signature validation error: {str(e)}")
        return False

def create_cxml_response(message_body=None, to_number=None, from_number=None):
    """
    Create cXML response for SignalWire
    SignalWire requires XML responses, not JSON
    """
    if message_body and to_number and from_number:
        # Escape XML special characters
        escaped_message = (message_body
                          .replace('&', '&amp;')
                          .replace('<', '&lt;')
                          .replace('>', '&gt;')
                          .replace('"', '&quot;')
                          .replace("'", '&#39;'))
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message to="{to_number}" from="{from_number}">{escaped_message}</Message>
</Response>'''
    else:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <!-- Message processed successfully -->
</Response>'''

def store_message_in_db(message_sid, from_number, to_number, body, direction='inbound', status='received'):
    """Store message in database for tracking"""
    try:
        # Find or create client
        client = Client.query.filter_by(phone_number=from_number).first()
        if not client:
            client = Client(
                phone_number=from_number,
                name=f"Client {from_number[-4:]}",  # Default name using last 4 digits
                first_contact=db.func.now(),
                last_contact=db.func.now(),
                is_active=True
            )
            db.session.add(client)
            db.session.flush()  # Get the ID
        else:
            client.last_contact = db.func.now()
        
        # Find profile by phone number
        profile = Profile.query.filter_by(phone_number=to_number).first()
        
        # Create message record
        message = Message(
            message_sid=message_sid,
            profile_id=profile.id if profile else None,
            client_id=client.id,
            sender_number=from_number,
            recipient_number=to_number,
            message_body=body,
            direction=direction,
            status=status,
            timestamp=db.func.now()
        )
        
        db.session.add(message)
        db.session.commit()
        
        return message
        
    except Exception as e:
        current_app.logger.error(f"Error storing message in database: {str(e)}")
        db.session.rollback()
        return None

@webhooks_bp.route('/sms', methods=['POST'])
def handle_incoming_sms():
    """
    Handle incoming SMS messages from SignalWire
    Flow: SignalWire -> Webhook -> AI Service -> Response -> SignalWire
    """
    try:
        # Validate SignalWire signature for security
        if not validate_signalwire_signature():
            current_app.logger.warning("Unauthorized webhook request")
            return Response('Unauthorized', status=401)
        
        # Extract message data from SignalWire webhook
        message_sid = request.form.get('MessageSid', '')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        message_body = request.form.get('Body', '').strip()
        message_status = request.form.get('SmsStatus', 'received')
        account_sid = request.form.get('AccountSid', '')
        
        current_app.logger.info(f"Received SMS {message_sid}: {from_number} -> {to_number}: '{message_body}'")
        
        # Store incoming message in database
        stored_message = store_message_in_db(
            message_sid=message_sid,
            from_number=from_number,
            to_number=to_number,
            body=message_body,
            direction='inbound',
            status=message_status
        )
        
        # Skip processing if empty message
        if not message_body:
            current_app.logger.info("Empty message body, skipping AI processing")
            return Response(create_cxml_response(), mimetype='text/xml')
        
        # Find profile by phone number
        profile = Profile.query.filter_by(phone_number=to_number).first()
        if not profile:
            current_app.logger.warning(f"No profile found for phone number: {to_number}")
            # Send default response for unknown numbers
            default_response = "Thank you for your message. We'll get back to you soon!"
            return Response(
                create_cxml_response(default_response, from_number, to_number),
                mimetype='text/xml'
            )
        
        # Check if AI is enabled for this profile
        if not profile.ai_enabled:
            current_app.logger.info(f"AI disabled for profile {profile.id}, skipping response generation")
            return Response(create_cxml_response(), mimetype='text/xml')
        
        # Generate AI response
        ai_response = ai_service.generate_response(
            profile=profile,
            message=message_body,
            sender_number=from_number,
            context={
                'message_sid': message_sid,
                'account_sid': account_sid
            }
        )
        
        if ai_response:
            current_app.logger.info(f"Generated AI response for {message_sid}: {ai_response[:50]}...")
            
            # Store outgoing AI response in database
            store_message_in_db(
                message_sid=f"ai_response_{message_sid}",
                from_number=to_number,
                to_number=from_number,
                body=ai_response,
                direction='outbound',
                status='queued'
            )
            
            # Return cXML response to SignalWire
            return Response(
                create_cxml_response(ai_response, from_number, to_number),
                mimetype='text/xml'
            )
        else:
            current_app.logger.warning(f"Failed to generate AI response for {message_sid}")
            return Response(create_cxml_response(), mimetype='text/xml')
        
    except Exception as e:
        current_app.logger.error(f"SMS webhook error: {str(e)}", exc_info=True)
        # Return valid cXML even on error
        return Response(create_cxml_response(), mimetype='text/xml')

@webhooks_bp.route('/voice', methods=['POST'])
def handle_incoming_voice():
    """
    Handle incoming voice calls from SignalWire
    Play message directing callers to text instead
    """
    try:
        # Validate webhook
        if not validate_signalwire_signature():
            return Response('Unauthorized', status=401)
        
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        call_sid = request.form.get('CallSid', '')
        
        current_app.logger.info(f"Received voice call {call_sid}: {from_number} -> {to_number}")
        
        # Create cXML response to direct caller to text
        cxml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Thank you for calling AssisText. For faster service, please send us a text message instead. We'll respond right away with AI-powered assistance. Thank you!</Say>
    <Pause length="1"/>
    <Hangup/>
</Response>'''
        
        return Response(cxml_response, mimetype='text/xml')
        
    except Exception as e:
        current_app.logger.error(f"Voice webhook error: {str(e)}")
        # Simple hangup on error
        cxml_response = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Hangup/>
</Response>'''
        return Response(cxml_response, mimetype='text/xml')

@webhooks_bp.route('/status', methods=['POST'])
def handle_message_status():
    """
    Handle message delivery status updates from SignalWire
    Update message status in database
    """
    try:
        # Validate webhook
        if not validate_signalwire_signature():
            return Response('Unauthorized', status=401)
        
        message_sid = request.form.get('MessageSid', '')
        message_status = request.form.get('MessageStatus', '')
        error_code = request.form.get('ErrorCode', '')
        error_message = request.form.get('ErrorMessage', '')
        
        current_app.logger.info(f"Message status update: {message_sid} -> {message_status}")
        
        # Update message status in database
        try:
            message = Message.query.filter_by(message_sid=message_sid).first()
            if message:
                message.status = message_status
                if error_code:
                    message.error_code = error_code
                    message.error_message = error_message
                db.session.commit()
                current_app.logger.info(f"Updated message {message_sid} status to {message_status}")
            else:
                current_app.logger.warning(f"Message {message_sid} not found in database")
                
        except Exception as db_error:
            current_app.logger.error(f"Database error updating message status: {str(db_error)}")
            db.session.rollback()
        
        if error_code:
            current_app.logger.error(f"Message delivery error [{error_code}]: {error_message}")
        
        return Response(create_cxml_response(), mimetype='text/xml')
        
    except Exception as e:
        current_app.logger.error(f"Status webhook error: {str(e)}")
        return Response(create_cxml_response(), mimetype='text/xml')

@webhooks_bp.route('/test', methods=['GET', 'POST'])
def test_webhook():
    """
    Test webhook endpoint for development
    """
    try:
        if request.method == 'POST':
            # Simulate incoming SMS for testing
            test_data = request.get_json() or {}
            test_message = test_data.get('message', 'Hello, this is a test message!')
            test_from = test_data.get('from', '+1234567890')
            test_to = test_data.get('to', '+1987654321')
            
            current_app.logger.info(f"Test webhook called with message: {test_message}")
            
            # Test AI service
            ai_response = ai_service.generate_response(
                profile=None,  # Will use default context
                message=test_message,
                sender_number=test_from
            )
            
            return jsonify({
                'success': True,
                'received_message': test_message,
                'ai_response': ai_response,
                'timestamp': db.func.now().isoformat() if hasattr(db.func, 'now') else 'N/A'
            })
        else:
            # GET request - show webhook status
            return jsonify({
                'webhook_status': 'active',
                'signalwire_configured': bool(os.getenv('SIGNALWIRE_API_TOKEN')),
                'ai_service_ready': ai_service.is_configured(),
                'endpoints': {
                    'sms': '/api/webhooks/sms',
                    'voice': '/api/webhooks/voice',
                    'status': '/api/webhooks/status'
                }
            })
        
    except Exception as e:
        current_app.logger.error(f"Test webhook error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@webhooks_bp.route('/health', methods=['GET'])
def webhook_health():
    """Health check for webhook service"""
    try:
        return jsonify({
            'status': 'healthy',
            'signalwire_token_configured': bool(os.getenv('SIGNALWIRE_API_TOKEN')),
            'ai_service_configured': ai_service.is_configured(),
            'database_connected': bool(db.engine.execute('SELECT 1').scalar()),
            'timestamp': db.func.now().isoformat() if hasattr(db.func, 'now') else 'N/A'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500