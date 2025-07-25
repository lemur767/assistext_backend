"""
Fixed Synchronous SMS Webhook Handler
No external SignalWire SDK dependency - uses manual HMAC validation
"""
from flask import Blueprint, request, Response, current_app
from app.extensions import db
from app.models.client import Client
from app.models.message import Message
import os
import logging
import hmac
import hashlib
import base64
from datetime import datetime
import time

# Create blueprint
sync_webhooks_bp = Blueprint('sync_webhooks', __name__)

def validate_signalwire_webhook():
    """
    Validate SignalWire webhook signature using manual HMAC validation
    """
    try:
        # Skip validation in development if configured
        if os.getenv('FLASK_ENV') == 'development' and os.getenv('SKIP_WEBHOOK_VALIDATION') == 'true':
            current_app.logger.warning("⚠️  Skipping webhook validation in development mode")
            return True
        
        # Get signature from headers
        signature = request.headers.get('X-SignalWire-Signature', '')
        if not signature:
            current_app.logger.error("❌ Missing X-SignalWire-Signature header")
            return False
        
        # Get auth token
        auth_token = os.getenv('SIGNALWIRE_AUTH_TOKEN')
        if not auth_token:
            current_app.logger.error("❌ SIGNALWIRE_AUTH_TOKEN not configured")
            return False
        
        # Build the string to validate
        url = request.url
        
        # Get form data and sort it
        form_data = dict(request.form)
        sorted_params = []
        
        for key in sorted(form_data.keys()):
            sorted_params.append(f"{key}{form_data[key]}")
        
        # Construct the validation string: URL + sorted parameters
        validation_string = url + ''.join(sorted_params)
        
        # Calculate expected signature using HMAC-SHA256 + Base64
        expected_signature = base64.b64encode(
            hmac.new(
                auth_token.encode('utf-8'),
                validation_string.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Compare signatures
        is_valid = hmac.compare_digest(signature, expected_signature)
        
        if is_valid:
            current_app.logger.info("✅ SignalWire webhook signature validated")
            return True
        else:
            current_app.logger.error(f"❌ Invalid SignalWire signature")
            current_app.logger.debug(f"Expected: {expected_signature}")
            current_app.logger.debug(f"Received: {signature}")
            current_app.logger.debug(f"Validation string: {validation_string}")
            return False
            
    except Exception as e:
        current_app.logger.error(f"❌ Webhook validation error: {str(e)}")
        return False

def create_signalwire_cxml(message_body: str = None, to_number: str = None) -> str:
    """
    Create proper cXML response for SignalWire
    """
    if message_body and to_number:
        # Escape XML special characters
        escaped_message = (
            str(message_body)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;')
        )
        
        cxml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message to="{to_number}">{escaped_message}</Message>
</Response>'''
        
        current_app.logger.info(f"📤 Created cXML response: '{escaped_message[:50]}...'")
        return cxml
    else:
        # Empty response (message processed but no reply)
        cxml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <!-- Message processed -->
</Response>'''
        current_app.logger.info("📤 Created empty cXML response")
        return cxml

@sync_webhooks_bp.route('/sms', methods=['POST'])
def handle_sms_synchronous():
    """
    Handle incoming SMS with synchronous processing and immediate cXML response
    
    Flow: SMS → Webhook → LLM → cXML → SignalWire → Response SMS
    """
    start_time = time.time()
    
    try:
        current_app.logger.info("📥 Received SMS webhook - processing synchronously")
        
        # 1. Validate SignalWire signature
        if not validate_signalwire_webhook():
            current_app.logger.error("🚫 Webhook validation failed")
            return Response('Unauthorized', status=401)
        
        # 2. Extract and validate webhook data
        message_sid = request.form.get('MessageSid', '').strip()
        from_number = request.form.get('From', '').strip()
        to_number = request.form.get('To', '').strip()
        message_body = request.form.get('Body', '').strip()
        sms_status = request.form.get('SmsStatus', 'received')
        num_media = int(request.form.get('NumMedia', '0'))
        
        # Log the incoming message
        current_app.logger.info(f"📨 SMS Details: {message_sid}")
        current_app.logger.info(f"   From: {from_number}")
        current_app.logger.info(f"   To: {to_number}")
        current_app.logger.info(f"   Message: '{message_body}'")
        current_app.logger.info(f"   Status: {sms_status}")
        
        # Validate required fields
        if not all([message_sid, from_number, to_number]):
            current_app.logger.error(f"❌ Missing required webhook fields")
            return Response(create_signalwire_cxml(), mimetype='text/xml')
        
        # 3. Handle empty messages (MMS-only or test messages)
        if not message_body and num_media == 0:
            current_app.logger.info("ℹ️  Empty SMS message - sending acknowledgment")
            ack_response = "Message received!"
            return Response(
                create_signalwire_cxml(ack_response, from_number),
                mimetype='text/xml'
            )
        
        # 4. Find user by phone number
        user = find_user_by_phone_number(to_number)
        if not user:
            current_app.logger.warning(f"⚠️  No user found for phone number: {to_number}")
            # Send a generic response or ignore
            generic_response = "Thank you for your message. We'll get back to you soon."
            return Response(
                create_signalwire_cxml(generic_response, from_number),
                mimetype='text/xml'
            )
        
        current_app.logger.info(f"👤 Found user: {user.id} ({user.name or 'Unknown'})")
        
        # 5. Check if AI is enabled for this user
        if not getattr(user, 'ai_enabled', True):
            current_app.logger.info(f"🚫 AI disabled for user {user.id}")
            fallback_message = "Thank you for your message. Someone will get back to you soon."
            return Response(
                create_signalwire_cxml(fallback_message, from_number),
                mimetype='text/xml'
            )
        
        # 6. Store incoming message in database (optional but recommended)
        try:
            store_incoming_message(message_sid, from_number, to_number, message_body, user.id)
        except Exception as e:
            current_app.logger.warning(f"⚠️  Failed to store incoming message: {str(e)}")
            # Continue processing even if storage fails
        
        # 7. Generate AI response using your LLM client
        current_app.logger.info("🤖 Generating AI response...")
        ai_start = time.time()
        
        # Build context for the LLM
        context = {
            'user_id': user.id,
            'company_name': getattr(user, 'company_name', user.name or 'Your Business'),
            'business_type': getattr(user, 'business_type', 'customer service'),
            'from_number': from_number,
            'to_number': to_number
        }
        
        # Get AI response using your existing LLM client
        ai_result = generate_ai_response(message_body, context)
        
        ai_duration = time.time() - ai_start
        current_app.logger.info(f"🤖 AI generation took {ai_duration:.2f}s")
        
        # 8. Handle AI response
        if ai_result.get('success') and ai_result.get('response'):
            ai_response = ai_result['response']
            ai_source = ai_result.get('source', 'unknown')
            
            current_app.logger.info(f"✅ AI response generated: '{ai_response}'")
            current_app.logger.info(f"🔧 AI source: {ai_source}")
            
            # Store outgoing message (optional)
            try:
                store_outgoing_message(from_number, to_number, ai_response, user.id, message_sid)
            except Exception as e:
                current_app.logger.warning(f"⚠️  Failed to store outgoing message: {str(e)}")
            
            # Create and return cXML response
            total_time = time.time() - start_time
            current_app.logger.info(f"⚡ Total processing time: {total_time:.2f}s")
            
            return Response(
                create_signalwire_cxml(ai_response, from_number),
                mimetype='text/xml'
            )
            
        else:
            # AI failed - use fallback
            error_reason = ai_result.get('reason', 'unknown')
            current_app.logger.error(f"❌ AI response failed: {error_reason}")
            
            fallback_message = "Thank you for your message! I'll get back to you shortly."
            
            return Response(
                create_signalwire_cxml(fallback_message, from_number),
                mimetype='text/xml'
            )
        
    except Exception as e:
        # Critical error - log and return empty response to avoid webhook retries
        total_time = time.time() - start_time
        current_app.logger.error(f"💥 Critical SMS webhook error after {total_time:.2f}s: {str(e)}", exc_info=True)
        
        return Response(
            create_signalwire_cxml(),
            mimetype='text/xml'
        )

def find_user_by_phone_number(phone_number: str):
    """Find user by phone number with multiple format attempts"""
    try:
        # Normalize phone number
        normalized = normalize_phone_number(phone_number)
        
        # Try to find user with multiple phone number formats
        user = (db.session.query(Client)
                .filter(db.or_(
                    Client.signalwire_phone_number == phone_number,
                    Client.signalwire_phone_number == normalized,
                    Client.phone_number == phone_number,
                    Client.phone_number == normalized
                ))
                .filter(Client.is_active == True)
                .first())
        
        return user
        
    except Exception as e:
        current_app.logger.error(f"❌ Error finding user by phone: {str(e)}")
        return None

def normalize_phone_number(phone: str) -> str:
    """Normalize phone number to E.164 format"""
    if not phone:
        return phone
    
    # Remove all non-digits
    digits = ''.join(filter(str.isdigit, phone))
    
    # Add +1 for North American numbers
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith('1'):
        return f"+{digits}"
    else:
        return phone

def generate_ai_response(message: str, context: dict):
    """Generate AI response using your existing LLM client"""
    try:
        # Import your LLM client
        from app.utils.llm_client import get_llm_client
        
        llm_client = get_llm_client()
        result = llm_client.generate_response(message, context)
        
        return result
        
    except ImportError:
        current_app.logger.error("❌ Could not import LLM client")
        return {
            'success': True,
            'response': "Thank you for your message. I'm here to help!",
            'source': 'fallback_import_error'
        }
    except Exception as e:
        current_app.logger.error(f"❌ AI generation error: {str(e)}")
        return {
            'success': True,
            'response': "Thank you for your message. How can I assist you?",
            'source': 'fallback_error'
        }

def store_incoming_message(message_sid: str, from_number: str, to_number: str, 
                          body: str, user_id: int):
    """Store incoming message in database"""
    try:
        message = Message(
            external_id=message_sid,
            user_id=user_id,
            from_number=from_number,
            to_number=to_number,
            body=body,
            direction='inbound',
            status='received',
            ai_generated=False,
            created_at=datetime.utcnow()
        )
        
        db.session.add(message)
        db.session.commit()
        
        current_app.logger.info(f"💾 Stored incoming message: {message.id}")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error storing incoming message: {str(e)}")
        raise

def store_outgoing_message(from_number: str, to_number: str, body: str, 
                          user_id: int, original_message_sid: str):
    """Store outgoing AI response in database"""
    try:
        # Find the original message to link to
        original_message = db.session.query(Message).filter_by(
            external_id=original_message_sid
        ).first()
        
        message = Message(
            external_id=f"sync_{int(time.time() * 1000)}",  # Generate unique ID
            user_id=user_id,
            from_number=from_number,
            to_number=to_number,
            body=body,
            direction='outbound',
            status='sent',
            ai_generated=True,
            thread_id=original_message.id if original_message else None,
            created_at=datetime.utcnow()
        )
        
        db.session.add(message)
        db.session.commit()
        
        current_app.logger.info(f"💾 Stored outgoing message: {message.id}")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ Error storing outgoing message: {str(e)}")
        # Don't raise - we don't want to fail the response if storage fails

@sync_webhooks_bp.route('/voice', methods=['POST'])
def handle_voice_synchronous():
    """Handle incoming voice calls with immediate cXML response"""
    try:
        if not validate_signalwire_webhook():
            return Response('Unauthorized', status=401)
        
        call_sid = request.form.get('CallSid', '')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        call_status = request.form.get('CallStatus', '')
        
        current_app.logger.info(f"📞 Voice call: {from_number} -> {to_number} ({call_status})")
        
        # Create voice response directing to SMS
        voice_cxml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        Hello! Thank you for calling. For faster service, please send us a text message instead. 
        We have AI-powered assistance that can help you right away via SMS. Have a great day!
    </Say>
    <Hangup/>
</Response>'''
        
        return Response(voice_cxml, mimetype='text/xml')
        
    except Exception as e:
        current_app.logger.error(f"❌ Voice webhook error: {str(e)}")
        # Simple hangup on error
        return Response(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Hangup/></Response>',
            mimetype='text/xml'
        )

@sync_webhooks_bp.route('/status', methods=['POST'])
def handle_status_callback():
    """Handle message status callbacks from SignalWire"""
    try:
        if not validate_signalwire_webhook():
            return Response('Unauthorized', status=401)
        
        message_sid = request.form.get('MessageSid', '')
        message_status = request.form.get('MessageStatus', '')
        error_code = request.form.get('ErrorCode', '')
        
        current_app.logger.info(f"📊 Status update: {message_sid} -> {message_status}")
        
        # Update message status in database if possible
        if message_sid:
            try:
                message = db.session.query(Message).filter_by(external_id=message_sid).first()
                if message:
                    message.status = message_status
                    if error_code:
                        message.error_code = error_code
                    message.updated_at = datetime.utcnow()
                    db.session.commit()
                    current_app.logger.info(f"✅ Updated message {message_sid} status")
            except Exception as e:
                current_app.logger.warning(f"⚠️  Failed to update message status: {str(e)}")
                db.session.rollback()
        
        return Response('', status=200)
        
    except Exception as e:
        current_app.logger.error(f"❌ Status webhook error: {str(e)}")
        return Response('', status=200)

@sync_webhooks_bp.route('/test', methods=['GET', 'POST'])
def test_webhook_system():
    """Test endpoint for webhook and LLM functionality"""
    try:
        if request.method == 'POST':
            test_message = request.json.get('message', 'Hello, this is a test!')
            
            # Test AI generation
            context = {
                'company_name': 'Test Business',
                'business_type': 'testing'
            }
            
            ai_result = generate_ai_response(test_message, context)
            
            return {
                'success': True,
                'test_message': test_message,
                'ai_response': ai_result.get('response', 'No response'),
                'ai_source': ai_result.get('source', 'unknown'),
                'ai_success': ai_result.get('success', False),
                'webhook_mode': 'synchronous',
                'environment': os.getenv('FLASK_ENV', 'production'),
                'validation_skipped': os.getenv('SKIP_WEBHOOK_VALIDATION') == 'true'
            }
        else:
            return {
                'success': True,
                'message': 'Synchronous SMS webhook system operational',
                'endpoints': {
                    'sms': '/api/webhooks/sync/sms - Synchronous SMS processing',
                    'voice': '/api/webhooks/sync/voice - Voice call handling',
                    'status': '/api/webhooks/sync/status - Message status updates',
                    'test': '/api/webhooks/sync/test - System testing'
                },
                'validation_method': 'manual_hmac',
                'environment': os.getenv('FLASK_ENV', 'production')
            }
            
    except Exception as e:
        current_app.logger.error(f"❌ Test endpoint error: {str(e)}")
        return {'success': False, 'error': str(e)}, 500