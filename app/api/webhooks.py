# app/api/webhooks.py (Updated for SignalWire)
# app/api/webhooks.py - Updated for SignalWire Integration
"""Webhook handlers for SignalWire SMS and Voice"""

from flask import Blueprint, request, current_app, jsonify
from app.services.message_handler import handle_incoming_message
from app.models.signalwire_account import SignalWirePhoneNumber
from app.utils.webhook_security import WebhookSecurity
from app.utils.audit_logger import AuditLogger
from app.extensions import task_queue
import json

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/sms', methods=['POST'])
def signalwire_sms_webhook():
    """
    Webhook for incoming SMS messages from SignalWire
    This replaces the old Twilio webhook completely
    """
    
    # Log webhook received for debugging
    current_app.logger.info(f"SignalWire SMS webhook received from {request.remote_addr}")
    
    # Get signature from headers for security validation
    signature = request.headers.get('X-SignalWire-Signature', '')
    
    # Validate signature if verification is enabled
    if current_app.config.get('VERIFY_SIGNALWIRE_SIGNATURE', True):
        auth_token = current_app.config['SIGNALWIRE_AUTH_TOKEN']
        if not WebhookSecurity.validate_signalwire_signature(signature, request.data, auth_token):
            current_app.logger.warning(f"Invalid SignalWire signature from {request.remote_addr}")
            AuditLogger.log_event(
                event_type='webhook_signature_invalid',
                details={
                    'source': 'signalwire_sms', 
                    'ip': request.remote_addr,
                    'headers': dict(request.headers)
                }
            )
            return 'Invalid signature', 403
    
    # Extract message details from SignalWire webhook payload
    message_text = request.form.get('Body', '').strip()
    sender_number = request.form.get('From', '')
    recipient_number = request.form.get('To', '')
    subaccount_sid = request.form.get('AccountSid', '')
    message_sid = request.form.get('MessageSid', '')
    message_status = request.form.get('MessageStatus', '')
    
    # Log incoming webhook details
    current_app.logger.info(
        f"SMS received: {sender_number} -> {recipient_number} "
        f"(SubAccount: {subaccount_sid}, SID: {message_sid})"
    )
    
    # Find which phone number this message is for
    phone_number = SignalWirePhoneNumber.query.filter_by(
        phone_number=recipient_number,
        is_active=True
    ).first()
    
    if not phone_number:
        current_app.logger.warning(f"Received message for unknown number: {recipient_number}")
        AuditLogger.log_event(
            event_type='webhook_unknown_number',
            details={
                'recipient_number': recipient_number,
                'sender_number': sender_number,
                'subaccount_sid': subaccount_sid
            }
        )
        return '', 204
    
    if not phone_number.profile_id:
        current_app.logger.warning(f"Received message for unassigned number: {recipient_number}")
        AuditLogger.log_event(
            event_type='webhook_unassigned_number',
            details={
                'recipient_number': recipient_number,
                'sender_number': sender_number,
                'phone_number_id': phone_number.id
            }
        )
        return '', 204
    
    # Log webhook received successfully
    AuditLogger.log_event(
        event_type='webhook_received',
        details={
            'source': 'signalwire_sms',
            'from': sender_number,
            'to': recipient_number,
            'profile_id': phone_number.profile_id,
            'subaccount_sid': subaccount_sid,
            'message_sid': message_sid,
            'message_length': len(message_text)
        }
    )
    
    # Process message asynchronously if task queue is available
    if task_queue:
        current_app.logger.info(f"Queuing message processing for profile {phone_number.profile_id}")
        task_queue.enqueue(
            handle_incoming_message,
            phone_number.profile_id,
            message_text,
            sender_number,
            subaccount_sid
        )
    else:
        # Process synchronously if no task queue (development mode)
        current_app.logger.info(f"Processing message synchronously for profile {phone_number.profile_id}")
        try:
            handle_incoming_message(
                phone_number.profile_id,
                message_text,
                sender_number,
                subaccount_sid
            )
        except Exception as e:
            current_app.logger.error(f"Error processing message synchronously: {e}")
            return 'Error processing message', 500
    
    # Return 204 No Content to SignalWire (standard response)
    return '', 204

@webhooks_bp.route('/voice', methods=['POST'])
def signalwire_voice_webhook():
    """
    Webhook for incoming voice calls from SignalWire
    Currently just logs and returns basic response
    """
    
    current_app.logger.info(f"SignalWire Voice webhook received from {request.remote_addr}")
    
    # Extract call details
    caller_number = request.form.get('From', '')
    called_number = request.form.get('To', '')
    call_sid = request.form.get('CallSid', '')
    call_status = request.form.get('CallStatus', '')
    
    # Log the call
    AuditLogger.log_event(
        event_type='voice_call_received',
        details={
            'from': caller_number,
            'to': called_number,
            'call_sid': call_sid,
            'call_status': call_status
        }
    )
    
    # Find the phone number
    phone_number = SignalWirePhoneNumber.query.filter_by(
        phone_number=called_number,
        is_active=True
    ).first()
    
    if not phone_number or not phone_number.profile_id:
        # Return basic "number not available" message
        response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">I'm sorry, this number is not available right now. Please send a text message instead.</Say>
    <Hangup/>
</Response>"""
        return response, 200, {'Content-Type': 'application/xml'}
    
    # For now, direct callers to send SMS instead
    # You can expand this later to handle voice calls
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hi! I prefer text messages. Please send me a text and I'll get back to you soon!</Say>
    <Hangup/>
</Response>"""
    
    return response, 200, {'Content-Type': 'application/xml'}

@webhooks_bp.route('/message-status', methods=['POST'])
def signalwire_message_status_webhook():
    """
    Webhook for SignalWire message status updates
    Updates message delivery status in database
    """
    
    current_app.logger.info(f"SignalWire message status webhook received from {request.remote_addr}")
    
    # Extract status details
    message_sid = request.form.get('MessageSid', '')
    message_status = request.form.get('MessageStatus', '')
    error_code = request.form.get('ErrorCode', '')
    error_message = request.form.get('ErrorMessage', '')
    
    if message_sid:
        # Update message status in database
        from app.models.message import Message
        message = Message.query.filter_by(signalwire_sid=message_sid).first()
        
        if message:
            message.send_status = message_status
            if error_code:
                message.send_error = f"Error {error_code}: {error_message}"
            
            from app.extensions import db
            db.session.commit()
            
            current_app.logger.info(f"Updated message {message_sid} status to {message_status}")
            
            # Log status update
            AuditLogger.log_event(
                event_type='message_status_updated',
                entity_type='message',
                entity_id=message.id,
                details={
                    'message_sid': message_sid,
                    'status': message_status,
                    'error_code': error_code,
                    'error_message': error_message
                }
            )
        else:
            current_app.logger.warning(f"Message with SID {message_sid} not found for status update")
    
    return '', 204

@webhooks_bp.route('/health', methods=['GET'])
def webhook_health():
    """Health check endpoint for webhook service"""
    return jsonify({
        'status': 'healthy',
        'service': 'signalwire_webhooks',
        'endpoints': [
            '/api/webhooks/sms',
            '/api/webhooks/voice', 
            '/api/webhooks/message-status'
        ]
    }), 200

@webhooks_bp.route('/test', methods=['POST'])
def webhook_test():
    """Test endpoint for webhook validation during development"""
    
    if not current_app.config.get('DEBUG', False):
        return 'Test endpoint only available in debug mode', 403
    
    # Log test webhook
    current_app.logger.info("Test webhook called")
    
    # Return test response
    return jsonify({
        'message': 'Webhook test successful',
        'received_data': {
            'form': dict(request.form),
            'headers': dict(request.headers),
            'method': request.method
        }
    }), 200

# Error handlers for webhook blueprint
@webhooks_bp.errorhandler(400)
def bad_request(error):
    current_app.logger.error(f"Webhook bad request: {error}")
    return '', 400

@webhooks_bp.errorhandler(403)
def forbidden(error):
    current_app.logger.error(f"Webhook forbidden: {error}")
    return '', 403

@webhooks_bp.errorhandler(500)
def internal_error(error):
    current_app.logger.error(f"Webhook internal error: {error}")
    return '', 500

# Add webhook blueprint registration instructions
"""
To register this blueprint in your Flask app, add this to app/__init__.py:

from app.api.webhooks import webhooks_bp
app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')

Then configure your SignalWire numbers to use these webhook URLs:
- SMS URL: https://yourdomain.com/api/webhooks/sms
- Voice URL: https://yourdomain.com/api/webhooks/voice
- Status Callback URL: https://yourdomain.com/api/webhooks/message-status
"""