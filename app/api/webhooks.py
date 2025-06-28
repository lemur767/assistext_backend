from flask import Blueprint, request, jsonify, current_app
from app.models.profile import Profile
from app.models.message import Message  # Assuming you have a Message model
from app.services.llm_service import generate_ai_response  # Your LLM service
from app.services.signalwire_service import send_sms_response  # SMS sending service
import logging
from app.extensions import db;
from app.services.signalwire_helpers import format_phone_display;

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/signalwire/sms', methods=['POST'])
def handle_incoming_sms():
    """
    Handle incoming SMS messages from SignalWire webhook
    Process message and send AI-generated response
    """
    try:
        # Get webhook data from SignalWire
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        message_body = request.form.get('Body', '').strip()
        message_sid = request.form.get('MessageSid')
        account_sid = request.form.get('AccountSid')
        
        logger.info(f"Incoming SMS: From={from_number}, To={to_number}, Body='{message_body}'")
        
        if not all([from_number, to_number, message_body]):
            logger.warning("Missing required webhook parameters")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Find the profile associated with this phone number
        profile = Profile.query.filter_by(phone_number=to_number, is_active=True).first()
        
        if not profile:
            logger.warning(f"No active profile found for number {to_number}")
            return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
        # Save incoming message to database
        incoming_message = Message(
            profile_id=profile.id,
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            message_sid=message_sid,
            direction='inbound',
            status='received'
        )
        db.session.add(incoming_message)
        db.session.commit()
        
        # Generate AI response using your LLM service
        try:
            ai_response = generate_ai_response(
                message_body=message_body,
                from_number=from_number,
                profile=profile
            )
            
            if ai_response:
                # Send AI response back via SignalWire
                response_sent = send_sms_response(
                    to_number=from_number,
                    from_number=to_number,
                    message_body=ai_response,
                    profile_id=profile.id
                )
                
                if response_sent:
                    logger.info(f"AI response sent successfully to {from_number}")
                else:
                    logger.error(f"Failed to send AI response to {from_number}")
            
        except Exception as ai_error:
            logger.error(f"Error generating/sending AI response: {str(ai_error)}")
        
        # Return XML response to SignalWire (required format)
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200
        
    except Exception as e:
        logger.error(f"Error handling incoming SMS webhook: {str(e)}")
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 500
