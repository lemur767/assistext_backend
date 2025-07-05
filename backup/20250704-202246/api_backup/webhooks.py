from flask import Blueprint, request, jsonify, current_app
from app.services.ai_service import AIService
import hmac
import hashlib

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/webhooks')

@webhooks_bp.route('/signalwire/sms', methods=['POST'])
def handle_signalwire_sms():
    """Handle incoming SMS from SignalWire"""
    try:
       # Verify webhook signature (optional but recommended)
        signature = request.headers.get('X-SignalWire-Signature', '')
        if not verify_signalwire_signature(request.data, signature):
            return jsonify({'error': 'Invalid signature'}), 403
        
        # Get form data from SignalWire
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        message_body = request.form.get('Body', '')
        
        if not all([from_number, to_number, message_body]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Process the message with AI service
        result = AIService.process_incoming_message(
            from_number=from_number,
            to_number=to_number,
            content=message_body
        )
        
        # Log the result
        current_app.logger.info(f"SMS processed: {result}")
        
        # Return TwiML response (SignalWire expects this format)
        if result['success']:
            return '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Message>Response sent via AI</Message>
            </Response>''', 200, {'Content-Type': 'application/xml'}
        else:
            # Even if processing failed, we return 200 to acknowledge receipt
            return '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Message>Message received</Message>
            </Response>''', 200, {'Content-Type': 'application/xml'}
        
    except Exception as e:
        current_app.logger.error(f"Webhook error: {str(e)}")
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Message>Error processing message</Message>
        </Response>''', 200, {'Content-Type': 'application/xml'}