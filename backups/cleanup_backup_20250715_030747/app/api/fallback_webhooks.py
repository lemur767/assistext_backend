"""
Fallback Webhook Handler for SignalWire
app/api/fallback_webhooks.py - Backup webhook endpoints in case primary fails
"""
from flask import Blueprint, request, Response, jsonify, current_app
from app.utils.signalwire_helpers import (
    validate_signalwire_signature,
    create_cxml_response,
    create_voice_cxml_response,
    parse_signalwire_webhook_data,
    log_webhook_request,
    escape_xml
)
from app.models.message import Message
from app.extensions import db
import logging

fallback_bp = Blueprint('fallback', __name__)

@fallback_bp.route('/sms', methods=['POST'])
def fallback_sms_handler():
    """
    Fallback SMS webhook handler
    Provides basic SMS handling when main webhook fails
    """
    try:
        # Validate signature
        if not validate_signalwire_signature():
            log_webhook_request('fallback_sms', {}, success=False, error='Invalid signature')
            return Response('Unauthorized', status=401)
        
        # Parse webhook data
        webhook_data = parse_signalwire_webhook_data(request.form)
        
        current_app.logger.info(f"Fallback SMS handler: {webhook_data['from_number']} -> {webhook_data['to_number']}")
        
        # Store message for manual processing
        try:
            fallback_message = Message(
                message_sid=webhook_data['message_sid'],
                sender_number=webhook_data['from_number'],
                recipient_number=webhook_data['to_number'],
                message_body=webhook_data['message_body'],
                direction='inbound',
                status='fallback_received',
                timestamp=db.func.now(),
                error_message='Processed by fallback handler'
            )
            
            db.session.add(fallback_message)
            db.session.commit()
            
        except Exception as db_error:
            current_app.logger.error(f"Fallback DB error: {str(db_error)}")
            db.session.rollback()
        
        # Send basic auto-response
        fallback_response = "Thank you for your message. We're experiencing technical difficulties but will respond as soon as possible."
        
        log_webhook_request('fallback_sms', webhook_data, success=True)
        
        return Response(
            create_cxml_response(
                fallback_response, 
                webhook_data['from_number'], 
                webhook_data['to_number']
            ),
            mimetype='text/xml'
        )
        
    except Exception as e:
        current_app.logger.error(f"Fallback SMS handler error: {str(e)}")
        log_webhook_request('fallback_sms', {}, success=False, error=str(e))
        return Response(create_cxml_response(), mimetype='text/xml')

@fallback_bp.route('/voice', methods=['POST'])
def fallback_voice_handler():
    """
    Fallback voice webhook handler
    Provides basic voice message when main webhook fails
    """
    try:
        # Validate signature
        if not validate_signalwire_signature():
            log_webhook_request('fallback_voice', {}, success=False, error='Invalid signature')
            return Response('Unauthorized', status=401)
        
        # Parse webhook data
        webhook_data = parse_signalwire_webhook_data(request.form)
        
        current_app.logger.info(f"Fallback voice handler: {webhook_data['from_number']} -> {webhook_data['to_number']}")
        
        # Create fallback voice message
        fallback_message = """
        Thank you for calling AssisText. 
        We're currently experiencing technical difficulties with our system.
        Please send us a text message instead, and we'll respond as soon as our service is restored.
        Thank you for your patience.
        """
        
        log_webhook_request('fallback_voice', webhook_data, success=True)
        
        return Response(
            create_voice_cxml_response(fallback_message, voice="alice", action_after="hangup"),
            mimetype='text/xml'
        )
        
    except Exception as e:
        current_app.logger.error(f"Fallback voice handler error: {str(e)}")
        log_webhook_request('fallback_voice', {}, success=False, error=str(e))
        return Response(create_voice_cxml_response(), mimetype='text/xml')

@fallback_bp.route('/status', methods=['POST'])
def fallback_status_handler():
    """
    Fallback status webhook handler
    Basic status logging when main webhook fails
    """
    try:
        # Validate signature
        if not validate_signalwire_signature():
            return Response('Unauthorized', status=401)
        
        # Parse webhook data
        webhook_data = parse_signalwire_webhook_data(request.form)
        
        current_app.logger.info(
            f"Fallback status: {webhook_data['message_sid']} -> {webhook_data['message_status']}"
        )
        
        # Log status for manual review
        if webhook_data['error_code']:
            current_app.logger.error(
                f"Message error [{webhook_data['error_code']}]: {webhook_data['error_message']}"
            )
        
        # Try to update message status in database
        try:
            message = Message.query.filter_by(message_sid=webhook_data['message_sid']).first()
            if message:
                message.status = webhook_data['message_status']
                if webhook_data['error_code']:
                    message.error_code = webhook_data['error_code']
                    message.error_message = webhook_data['error_message']
                db.session.commit()
        except Exception as db_error:
            current_app.logger.error(f"Fallback status DB error: {str(db_error)}")
            db.session.rollback()
        
        log_webhook_request('fallback_status', webhook_data, success=True)
        
        return Response(create_cxml_response(), mimetype='text/xml')
        
    except Exception as e:
        current_app.logger.error(f"Fallback status handler error: {str(e)}")
        return Response(create_cxml_response(), mimetype='text/xml')

@fallback_bp.route('/health', methods=['GET'])
def fallback_health():
    """Health check for fallback webhook service"""
    return jsonify({
        'status': 'healthy',
        'service': 'fallback_webhooks',
        'endpoints': [
            '/api/webhooks/fallback/sms',
            '/api/webhooks/fallback/voice', 
            '/api/webhooks/fallback/status'
        ]
    }), 200

# Additional webhook endpoint for updating the main webhooks to use the SignalWire utils
@fallback_bp.route('/update-main-webhooks', methods=['POST'])
def update_main_webhook_implementation():
    """
    Utility endpoint to show how to update your main webhooks.py to use the new utilities
    This is for reference - you would integrate this into your existing webhooks.py
    """
    example_sms_handler = '''
# Updated SMS handler using SignalWire utilities
from app.utils.signalwire_helpers import (
    validate_signalwire_signature,
    create_cxml_response,
    parse_signalwire_webhook_data,
    log_webhook_request
)

@webhooks_bp.route('/sms', methods=['POST'])
def handle_incoming_sms():
    try:
        # Use utility for signature validation
        if not validate_signalwire_signature():
            return Response('Unauthorized', status=401)
        
        # Use utility to parse webhook data
        webhook_data = parse_signalwire_webhook_data(request.form)
        
        # Your existing AI processing logic here
        ai_response = ai_service.generate_response(
            profile=profile,
            message=webhook_data['message_body'],
            sender_number=webhook_data['from_number']
        )
        
        # Use utility to create cXML response
        if ai_response:
            cxml_response = create_cxml_response(
                ai_response,
                webhook_data['from_number'],
                webhook_data['to_number']
            )
        else:
            cxml_response = create_cxml_response()
        
        # Log the webhook request
        log_webhook_request('sms', webhook_data, success=True)
        
        return Response(cxml_response, mimetype='text/xml')
        
    except Exception as e:
        log_webhook_request('sms', {}, success=False, error=str(e))
        return Response(create_cxml_response(), mimetype='text/xml')
    '''
    
    return jsonify({
        'message': 'Example webhook implementation using SignalWire utilities',
        'example_code': example_sms_handler,
        'utilities_available': [
            'validate_signalwire_signature()',
            'create_cxml_response()',
            'parse_signalwire_webhook_data()',
            'log_webhook_request()',
            'format_phone_number()',
            'get_signalwire_client()'
        ]
    }), 200