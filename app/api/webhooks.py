from flask import Blueprint, request, jsonify, current_app
from app.utils.signalwire_helpers import validate_signalwire_webhook_request
from app.services.message_handler import handle_incoming_signalwire_message
from app.models.profile import Profile
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/signalwire/sms', methods=['POST'])
def signalwire_sms_webhook():
    """Webhook for incoming SMS messages from SignalWire"""
    try:
        logger.info(f"Received SignalWire SMS webhook: {request.form.to_dict()}")
        
        # Validate SignalWire request (optional in development)
        if current_app.config.get('VALIDATE_SIGNALWIRE_SIGNATURE', False):
            if not validate_signalwire_webhook_request(request):
                logger.warning("Invalid SignalWire signature or parameters")
                return 'Invalid request', 403
        
        # Extract SignalWire message details
        message_text = request.form.get('Body', '').strip()
        sender_number = request.form.get('From', '')
        recipient_number = request.form.get('To', '')
        message_sid = request.form.get('MessageSid', '')
        account_sid = request.form.get('AccountSid', '')
        
        logger.info(f"SignalWire SMS: From {sender_number} to {recipient_number}")
        
        if not message_text or not sender_number or not recipient_number:
            logger.warning("Missing required fields in SignalWire SMS webhook")
            return 'Missing required fields', 400
        
        # Find which profile this message is for
        profile = Profile.query.filter_by(phone_number=recipient_number).first()
        if not profile:
            logger.warning(f"Received SignalWire message for unknown number: {recipient_number}")
            return 'Unknown recipient number', 404
        
        # Process message directly (synchronously for now)
        try:
            result = handle_incoming_signalwire_message(
                profile_id=profile.id,
                message_text=message_text,
                sender_number=sender_number,
                signalwire_message_sid=message_sid,
                signalwire_account_sid=account_sid
            )
            
            if result:
                logger.info(f"SignalWire message processed successfully")
            else:
                logger.warning(f"SignalWire message processing returned no result")
                
        except Exception as e:
            logger.error(f"Error processing SignalWire message: {str(e)}")
        
        return '', 200
        
    except Exception as e:
        logger.error(f"SignalWire webhook error: {str(e)}")
        return 'Internal error', 200

@webhooks_bp.route('/signalwire/status', methods=['POST'])
def signalwire_status_webhook():
    """Webhook for SignalWire SMS delivery status updates"""
    try:
        logger.info(f"SignalWire status update: {request.form.to_dict()}")
        
        message_sid = request.form.get('MessageSid', '')
        message_status = request.form.get('MessageStatus', '')
        error_code = request.form.get('ErrorCode', '')
        error_message = request.form.get('ErrorMessage', '')
        
        # Update message status in database
        from app.models.message import Message
        from app import db
        
        if message_sid:
            message = Message.query.filter_by(signalwire_message_sid=message_sid).first()
            if message:
                message.signalwire_status = message_status
                if error_code:
                    message.signalwire_error_code = error_code
                if error_message:
                    message.signalwire_error_message = error_message
                
                db.session.commit()
                logger.info(f"Updated SignalWire message {message_sid} status to {message_status}")
            else:
                logger.warning(f"SignalWire status update for unknown message SID: {message_sid}")
        
        return '', 200
        
    except Exception as e:
        logger.error(f"SignalWire status webhook error: {str(e)}")
        return '', 200

@webhooks_bp.route('/signalwire/test', methods=['GET', 'POST'])
def test_signalwire_webhook():
    """Test endpoint to verify SignalWire webhook connectivity"""
    return jsonify({
        'status': 'SignalWire webhook endpoint active',
        'service': 'AssisText SignalWire Integration',
        'method': request.method,
        'timestamp': datetime.utcnow().isoformat(),
        'headers': dict(request.headers),
        'form_data': request.form.to_dict() if request.method == 'POST' else None,
        'webhook_url': request.url
    }), 200

# Legacy endpoints for backward compatibility
@webhooks_bp.route('/sms', methods=['POST'])
def legacy_sms_webhook():
    """Legacy SMS webhook - redirects to SignalWire handler"""
    logger.info("Legacy SMS webhook called, redirecting to SignalWire handler")
    return signalwire_sms_webhook()

@webhooks_bp.route('/twilio/sms', methods=['POST'])
def legacy_twilio_webhook():
    """Legacy Twilio webhook - redirects to SignalWire handler"""
    logger.info("Legacy Twilio webhook called, redirecting to SignalWire handler")
    return signalwire_sms_webhook()

@webhooks_bp.route('/health', methods=['GET'])
def webhooks_health():
    """Health check for SignalWire webhook service"""
    try:
        from app.utils.signalwire_helpers import get_signalwire_integration_status
        
        signalwire_status = get_signalwire_integration_status()
        
        return jsonify({
            'status': 'healthy',
            'service': 'SignalWire webhooks',
            'signalwire_integration': signalwire_status['status'],
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Webhook health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503
