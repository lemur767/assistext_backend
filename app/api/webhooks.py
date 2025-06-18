# app/api/webhooks.py - Updated webhook handler for SMS AI responses

from flask import Blueprint, request, jsonify, current_app
from app.models.profile import Profile
from app.models.message import Message
from app.models.client import Client
from app.extensions import db, socketio
from app.utils.signalwire_helpers import (
    validate_signalwire_webhook_request,
    send_signalwire_sms
)
from app.utils.ollama_helpers import generate_ai_response
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/sms', methods=['POST'])
def sms_webhook():
    """Handle incoming SMS messages from SignalWire and generate AI responses"""
    try:
        # Validate SignalWire request
        if current_app.config.get('VERIFY_SIGNALWIRE_SIGNATURE', True):
            if not validate_signalwire_webhook_request(request):
                logger.warning("Invalid SignalWire signature")
                return jsonify({'error': 'Invalid signature'}), 403
        
        # Extract message data from SignalWire webhook
        message_body = request.form.get('Body', '').strip()
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        message_sid = request.form.get('MessageSid', '')
        account_sid = request.form.get('AccountSid', '')
        
        logger.info(f"SMS received: {from_number} -> {to_number}: {message_body}")
        
        if not all([message_body, from_number, to_number]):
            logger.error("Missing required webhook parameters")
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Find the profile associated with this phone number
        profile = Profile.query.filter_by(phone_number=to_number).first()
        
        if not profile:
            logger.warning(f"No profile found for phone number: {to_number}")
            # Return empty response - don't auto-reply to unknown numbers
            return '', 204
        
        if not profile.is_active:
            logger.info(f"Profile {profile.id} is inactive, ignoring message")
            return '', 204
        
        # Get or create client record
        client = Client.query.filter_by(phone_number=from_number).first()
        if not client:
            client = Client(
                phone_number=from_number,
                first_contact=datetime.utcnow(),
                last_contact=datetime.utcnow(),
                total_messages=1
            )
            db.session.add(client)
        else:
            client.last_contact = datetime.utcnow()
            client.total_messages = (client.total_messages or 0) + 1
        
        # Check if client is blocked
        if client.is_blocked:
            logger.info(f"Client {from_number} is blocked, ignoring message")
            return '', 204
        
        # Save incoming message to database
        incoming_message = Message(
            content=message_body,
            is_incoming=True,
            sender_number=from_number,
            profile_id=profile.id,
            ai_generated=False,
            timestamp=datetime.utcnow(),
            signalwire_sid=message_sid
        )
        db.session.add(incoming_message)
        
        # Emit WebSocket event for real-time UI updates
        try:
            socketio.emit('new_message', {
                "id": incoming_message.id,
                "content": incoming_message.content,
                "is_incoming": True,
                "sender_number": from_number,
                "ai_generated": False,
                "timestamp": incoming_message.timestamp.isoformat(),
                "profile_id": profile.id
            })
        except Exception as ws_error:
            logger.warning(f"WebSocket emit failed: {str(ws_error)}")
        
        # Check if AI is enabled for this profile
        if not profile.ai_enabled:
            logger.info(f"AI disabled for profile {profile.id}, not responding")
            db.session.commit()
            return '', 204
        
        # Generate AI response using local LLM
        try:
            ai_response = generate_ai_response_for_profile(profile, message_body, from_number)
            
            if ai_response and ai_response.strip():
                # Send AI response via SignalWire
                response_result = send_signalwire_sms(
                    from_number=to_number,  # Profile's SignalWire number
                    to_number=from_number,  # Reply to sender
                    body=ai_response
                )
                
                if response_result:
                    # Save outgoing AI response to database
                    outgoing_message = Message(
                        content=ai_response,
                        is_incoming=False,
                        sender_number=from_number,
                        profile_id=profile.id,
                        ai_generated=True,
                        timestamp=datetime.utcnow(),
                        signalwire_sid=response_result.get('sid'),
                        send_status='sent'
                    )
                    db.session.add(outgoing_message)
                    
                    # Emit WebSocket event for AI response
                    try:
                        socketio.emit('new_message', {
                            "id": outgoing_message.id,
                            "content": outgoing_message.content,
                            "is_incoming": False,
                            "sender_number": from_number,
                            "ai_generated": True,
                            "timestamp": outgoing_message.timestamp.isoformat(),
                            "profile_id": profile.id
                        })
                    except Exception as ws_error:
                        logger.warning(f"WebSocket emit failed for AI response: {str(ws_error)}")
                    
                    logger.info(f"AI response sent successfully: {response_result.get('sid')}")
                else:
                    logger.error("Failed to send AI response via SignalWire")
            else:
                logger.info("No AI response generated or empty response")
                
        except Exception as ai_error:
            logger.error(f"AI response generation failed: {str(ai_error)}")
            # Don't fail the webhook for AI errors
        
        # Commit all database changes
        db.session.commit()
        
        # Return empty 204 response to SignalWire
        return '', 204
        
    except Exception as e:
        logger.error(f"Error processing SMS webhook: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500


def generate_ai_response_for_profile(profile: Profile, message_text: str, sender_number: str) -> str:
    """Generate AI response using the local LLM for a specific profile"""
    try:
        # Build context for the AI
        context = build_ai_context(profile, sender_number)
        
        # Create system prompt based on profile
        system_prompt = f"""You are an AI assistant for {profile.name}. 
{profile.description or 'You provide helpful and professional responses.'}

Guidelines:
- Keep responses concise and friendly
- Maintain a professional tone
- Be helpful and informative
- Don't reveal that you are an AI unless directly asked
- Respond as if you are {profile.name}

Context about this conversation:
{context}
"""
        
        # Generate response using local LLM on 10.0.0.4
        ai_response = generate_ai_response(
            prompt=message_text,
            system_prompt=system_prompt,
            max_tokens=150,
            temperature=0.7
        )
        
        if ai_response:
            logger.info(f"Generated AI response for profile {profile.id}: {len(ai_response)} chars")
            return ai_response.strip()
        else:
            logger.warning(f"No AI response generated for profile {profile.id}")
            return ""
            
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        return ""


def build_ai_context(profile: Profile, sender_number: str) -> str:
    """Build context information for AI response generation"""
    try:
        # Get recent conversation history
        recent_messages = Message.query.filter_by(
            profile_id=profile.id,
            sender_number=sender_number
        ).order_by(Message.timestamp.desc()).limit(5).all()
        
        context_parts = []
        
        # Add profile info
        if profile.description:
            context_parts.append(f"Profile: {profile.description}")
        
        # Add recent conversation context
        if recent_messages:
            context_parts.append("Recent conversation:")
            for msg in reversed(recent_messages):  # Reverse to show chronological order
                sender = "Contact" if msg.is_incoming else profile.name
                context_parts.append(f"{sender}: {msg.content}")
        
        # Add any relevant profile settings or business hours
        if profile.business_hours:
            try:
                hours = json.loads(profile.business_hours)
                if hours:
                    context_parts.append(f"Business hours: {hours}")
            except:
                pass
        
        return "\n".join(context_parts)
        
    except Exception as e:
        logger.error(f"Error building AI context: {str(e)}")
        return "No additional context available."


@webhooks_bp.route('/sms/status', methods=['POST'])
def sms_status_webhook():
    """Handle SMS delivery status updates from SignalWire"""
    try:
        message_sid = request.form.get('MessageSid', '')
        status = request.form.get('MessageStatus', '')
        error_code = request.form.get('ErrorCode')
        
        if message_sid and status:
            # Update message status in database
            message = Message.query.filter_by(signalwire_sid=message_sid).first()
            if message:
                message.send_status = status
                if error_code:
                    message.error_code = error_code
                db.session.commit()
                
                logger.info(f"Updated message {message_sid} status to {status}")
            else:
                logger.warning(f"Message {message_sid} not found for status update")
        
        return '', 204
        
    except Exception as e:
        logger.error(f"Error processing status webhook: {str(e)}")
        return '', 500


@webhooks_bp.route('/health', methods=['GET'])
def webhook_health():
    """Health check endpoint for webhook service"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        # Check LLM connection
        from app.utils.ollama_helpers import is_llm_available
        llm_status = is_llm_available()
        
        # Check SignalWire connection
        from app.utils.signalwire_helpers import get_signalwire_integration_status
        signalwire_status = get_signalwire_integration_status()
        
        return jsonify({
            'status': 'healthy',
            'service': 'SMS webhook handler',
            'database': 'connected',
            'llm_server': 'connected' if llm_status else 'disconnected',
            'signalwire': signalwire_status['status'],
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Webhook health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503


@webhooks_bp.route('/test', methods=['POST'])
def test_webhook():
    """Test endpoint for webhook functionality"""
    try:
        data = request.json or {}
        
        return jsonify({
            'status': 'success',
            'message': 'Webhook test successful',
            'received_data': data,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Webhook test failed: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# Legacy endpoints for backward compatibility
@webhooks_bp.route('/signalwire/sms', methods=['POST'])
def legacy_signalwire_sms():
    """Legacy SignalWire SMS webhook - redirects to main handler"""
    logger.info("Legacy SignalWire webhook called, redirecting to main handler")
    return sms_webhook()


