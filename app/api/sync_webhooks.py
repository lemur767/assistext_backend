from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import logging

from app.services import get_messaging_service, get_signalwire_service
from app.models import Message, User
from app.extensions import db

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/sms', methods=['POST'])
def handle_sms_webhook():
    """
    Handle incoming SMS from SignalWire
    """
    try:
        # Log the incoming webhook
        current_app.logger.info(f"Received SMS webhook: {request.form.to_dict()}")
        
        signalwire_service = get_signalwire_service()
        
        # Validate webhook signature for security
        webhook_url = request.url
        post_vars = request.form.to_dict()
        signature = request.headers.get('X-Twilio-Signature', '')
        
        if not signalwire_service.validate_webhook_signature(webhook_url, post_vars, signature):
            current_app.logger.warning("Invalid webhook signature")
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Validate and extract webhook data
        validation_result = signalwire_service.validate_webhook_request(post_vars)
        
        if not validation_result['valid']:
            current_app.logger.error(f"Invalid webhook data: {validation_result['error']}")
            return jsonify({'error': validation_result['error']}), 400
        
        webhook_data = validation_result['data']
        
        # Process the incoming SMS
        messaging_service = get_messaging_service()
        result = messaging_service.process_incoming_sms(webhook_data)
        
        if result['success']:
            # Return TwiML response to acknowledge receipt
            twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
            return twiml_response, 200, {'Content-Type': 'text/xml'}
        else:
            current_app.logger.error(f"Failed to process SMS: {result['error']}")
            return jsonify({'error': 'Failed to process SMS'}), 500
            
    except Exception as e:
        current_app.logger.error(f"SMS webhook error: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

@webhooks_bp.route('/status', methods=['POST'])
def handle_status_webhook():
    """
    Handle message status updates from SignalWire
    """
    try:
        current_app.logger.info(f"Received status webhook: {request.form.to_dict()}")
        
        # Extract status data
        message_sid = request.form.get('MessageSid')
        status = request.form.get('MessageStatus')
        error_code = request.form.get('ErrorCode')
        error_message = request.form.get('ErrorMessage')
        
        if not message_sid or not status:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Update message status in database
        message = Message.query.filter_by(signalwire_message_sid=message_sid).first()
        
        if message:
            message.signalwire_status = status
            message.updated_at = datetime.utcnow()
            
            if status == 'delivered':
                message.delivered_at = datetime.utcnow()
            elif status == 'failed':
                message.signalwire_error_code = error_code
                message.signalwire_error_message = error_message
            
            db.session.commit()
            
            current_app.logger.info(f"Updated message {message_sid} status to {status}")
        else:
            current_app.logger.warning(f"Message not found for SID: {message_sid}")
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Status webhook error: {str(e)}")
        return jsonify({'error': 'Status update failed'}), 500

@webhooks_bp.route('/voice', methods=['POST'])
def handle_voice_webhook():
    """
    Handle incoming voice calls from SignalWire
    """
    try:
        current_app.logger.info(f"Received voice webhook: {request.form.to_dict()}")
        
        # Extract call data
        call_sid = request.form.get('CallSid')
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        call_status = request.form.get('CallStatus')
        
        # Find user by phone number
        user = User.query.filter_by(signalwire_phone_number=to_number).first()
        
        if not user:
            # Return busy signal for unknown numbers
            twiml_response = '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say>Sorry, this number is not available. Please send a text message instead.</Say>
                <Hangup/>
            </Response>'''
        else:
            # Return voicemail prompt
            twiml_response = f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say>Hello, you've reached {user.first_name or user.username}. 
                I'm not available to take your call right now, but I respond to text messages quickly. 
                Please hang up and send me a text message instead.</Say>
                <Hangup/>
            </Response>'''
        
        return twiml_response, 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        current_app.logger.error(f"Voice webhook error: {str(e)}")
        # Return generic error response
        twiml_response = '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say>Sorry, there was an error. Please try again later.</Say>
            <Hangup/>
        </Response>'''
        return twiml_response, 200, {'Content-Type': 'text/xml'}

@webhooks_bp.route('/test', methods=['GET', 'POST'])
def test_webhook():
    """
    Test webhook endpoint for debugging
    """
    try:
        if request.method == 'POST':
            # Test with sample data
            test_data = {
                'MessageSid': 'test_' + str(datetime.utcnow().timestamp()),
                'From': '+16475551234',
                'To': '+14165551234',
                'Body': 'Test message from webhook test endpoint',
                'SmsStatus': 'received'
            }
            
            messaging_service = get_messaging_service()
            result = messaging_service.process_incoming_sms(test_data)
            
            return jsonify({
                'success': True,
                'test_result': result,
                'message': 'Webhook test completed'
            }), 200
        else:
            return jsonify({
                'success': True,
                'message': 'Webhook endpoints are active',
                'endpoints': {
                    'sms': '/api/webhooks/sms',
                    'status': '/api/webhooks/status',
                    'voice': '/api/webhooks/voice'
                },
                'timestamp': datetime.utcnow().isoformat()
            }), 200
            
    except Exception as e:
        current_app.logger.error(f"Webhook test error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500