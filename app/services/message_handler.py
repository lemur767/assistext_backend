from app.extensions import db, socketio
from app.utils.twilio_helpers import send_sms
from datetime import datetime, timedelta
import re
import json
import logging

logger = logging.getLogger(__name__)

# Flag words and phrases to watch for
FLAG_WORDS = [
    "police", "cop", "law enforcement", "arrest", "sting", "setup",
    "underage", "minor", "illegal", "bust", "investigation"
]

def handle_incoming_message(profile_id, message_text, sender_number, message_data=None):
    """Process incoming message and determine appropriate response"""
    from app.models.message import Message
    from app.models.profile import Profile
    from app.models.client import Client
    from app.models.auto_reply import AutoReply
    from app.models.flagged_message import FlaggedMessage
    
    logger.info(f"Handling incoming message for profile {profile_id} from {sender_number}")
    
    # Get profile information
    profile = Profile.query.get(profile_id)
    if not profile:
        logger.error(f"Profile {profile_id} not found")
        return None
    
    # Get or create client record
    client = Client.query.filter_by(phone_number=sender_number).first()
    if not client:
        client = Client(phone_number=sender_number)
        db.session.add(client)
        db.session.commit()
        logger.info(f"Created new client record for {sender_number}")
    
    # Check if client is blocked
    if client.is_blocked:
        logger.info(f"Client {sender_number} is blocked, ignoring message")
        return None
    
    # Save incoming message to database
    message = Message(
        content=message_text,
        is_incoming=True,
        sender_number=sender_number,
        profile_id=profile.id,
        ai_generated=False,
        timestamp=datetime.utcnow()
    )
    
    # Add Twilio metadata if available
    if message_data:
        message.twilio_sid = message_data.get('message_sid')
    
    db.session.add(message)
    db.session.commit()
    logger.info(f"Saved incoming message with ID {message.id}")
    
    # Emit WebSocket event for real-time updates
    socketio.emit('new_message', {
        "id": message.id,
        "content": message.content,
        "is_incoming": message.is_incoming,
        "sender_number": message.sender_number,
        "ai_generated": message.ai_generated,
        "timestamp": message.timestamp.isoformat(),
        "is_read": message.is_read,
        "profile_id": profile.id
    })
    
    # Check if message contains flagged content
    is_flagged, flag_reasons = check_flagged_content(message_text)
    if is_flagged:
        flagged_message = FlaggedMessage(
            message_id=message.id,
            reasons=json.dumps(flag_reasons),
            is_reviewed=False
        )
        db.session.add(flagged_message)
        db.session.commit()
    
    # If AI responses are not enabled, just store the message and don't respond
    if not profile.ai_enabled:
        logger.info(f"AI disabled for profile {profile_id}, not generating response")
        return None
    
    # Check for automatic responses based on keywords
    for auto_reply in AutoReply.query.filter_by(profile_id=profile.id, is_active=True).all():
        if auto_reply.keyword.lower() in message_text.lower():
            logger.info(f"Auto-reply triggered for keyword: {auto_reply.keyword}")
            return send_response(profile, auto_reply.response, sender_number, is_ai_generated=False)
    
    # Check if within business hours
    if not is_within_business_hours(profile):
        from app.models.auto_reply import OutOfOfficeReply
        out_of_office_reply = OutOfOfficeReply.query.filter_by(
            profile_id=profile.id, 
            is_active=True
        ).first()
        if out_of_office_reply:
            logger.info(f"Outside business hours, sending out-of-office reply")
            return send_response(profile, out_of_office_reply.message, sender_number, is_ai_generated=False)
    
    # Generate AI response using your local LLM
    try:
        from app.services.llm_service import LLMService
        llm_service = LLMService()
        ai_response = llm_service.generate_response(
            profile=profile,
            message=message_text,
            sender_number=sender_number,
            conversation_history=get_conversation_history(profile.id, sender_number)
        )
        
        if ai_response:
            logger.info(f"Generated AI response: {ai_response}")
            return send_response(profile, ai_response, sender_number, is_ai_generated=True)
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}", exc_info=True)
    
    # Fallback response if AI generation fails
    fallback_response = "I'll get back to you soon!"
    logger.info(f"Using fallback response")
    return send_response(profile, fallback_response, sender_number, is_ai_generated=False)


def send_response(profile, response_text, recipient_number, is_ai_generated=True):
    """Send response via Twilio and save to database"""
    from app.models.message import Message
    from app.models.user import User
    
    # Get the user who owns this profile
    user = User.query.get(profile.user_id)
    
    # Save outgoing message to database
    message = Message(
        content=response_text,
        is_incoming=False,
        sender_number=recipient_number,
        profile_id=profile.id,
        ai_generated=is_ai_generated,
        timestamp=datetime.utcnow()
    )
    db.session.add(message)
    db.session.commit()
    
    # Send via Twilio using the appropriate account
    try:
        twilio_message = send_sms(
            from_number=profile.phone_number,
            to_number=recipient_number,
            body=response_text,
            user=user  # Pass the user to determine which Twilio account to use
        )
        
        # Update message with Twilio SID
        message.twilio_sid = twilio_message.sid
        message.send_status = 'sent'
        
        # Update usage tracking
        if user.twilio_usage_tracker:
            user.twilio_usage_tracker.sms_count += 1
        
        db.session.commit()
        
        # Emit WebSocket event
        socketio.emit('new_message', {
            "id": message.id,
            "content": message.content,
            "is_incoming": message.is_incoming,
            "sender_number": message.sender_number,
            "ai_generated": message.ai_generated,
            "timestamp": message.timestamp.isoformat(),
            "is_read": message.is_read,
            "profile_id": profile.id
        })
        
        return message
    
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}", exc_info=True)
        # Update message status to reflect sending failure
        message.send_status = 'failed'
        message.send_error = str(e)
        db.session.commit()
        return None


def format_outgoing_message(message_text, profile):
    """Format outgoing message according to profile preferences"""
    formatted_text = message_text
    
    # Add signature if configured
    if hasattr(profile, 'signature') and profile.signature:
        formatted_text += f"\n\n{profile.signature}"
    
    # Ensure message isn't too long (SMS limit is 160 chars for single SMS)
    if len(formatted_text) > 1600:  # Allowing for longer messages
        formatted_text = formatted_text[:1600] + "..."
    
    return formatted_text


def get_conversation_history(profile_id, client_phone, limit=10):
    """Get recent conversation history between profile and client"""
    from app.models.message import Message
    
    messages = Message.query.filter(
        Message.profile_id == profile_id,
        Message.sender_number == client_phone
    ).order_by(Message.timestamp.desc()).limit(limit).all()
    
    # Reverse to get chronological order
    return messages[::-1]


def check_flagged_content(message_text):
    """Check if message contains flagged content"""
    is_flagged = False
    reasons = []
    
    # Convert to lowercase for case-insensitive matching
    lower_text = message_text.lower()
    
    # Check for flag words
    for word in FLAG_WORDS:
        if word.lower() in lower_text:
            is_flagged = True
            reasons.append(f"Contains flagged word: '{word}'")
    
    # Check for explicit prices or services
    price_pattern = r'\$\d+|(\d+)\s*(dollars|usd|hr|hour|session)'
    if re.search(price_pattern, lower_text):
        is_flagged = True
        reasons.append("Contains explicit pricing")
    
    return is_flagged, reasons


def is_within_business_hours(profile):
    """Check if current time is within business hours for profile"""
    import pytz
    
    timezone = pytz.timezone(profile.timezone or 'UTC')
    current_time = datetime.now(timezone)
    
    # Get day of week as lowercase string
    day_of_week = current_time.strftime('%A').lower()
    
    # Get business hours for profile
    business_hours = profile.get_business_hours()
    
    # If no business hours are set, return True (always available)
    if not business_hours:
        return True
    
    # Check if day exists in business hours
    if day_of_week not in business_hours:
        return False
    
    # Parse start and end times
    day_hours = business_hours[day_of_week]
    start_time_str = day_hours.get("start", "00:00")
    end_time_str = day_hours.get("end", "23:59")
    
    try:
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_hour, end_minute = map(int, end_time_str.split(':'))
        
        start_time = current_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        
        # Handle cases where end time is on the next day
        if end_hour < start_hour:
            end_time = current_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0) + timedelta(days=1)
        else:
            end_time = current_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        
        return start_time <= current_time <= end_time
    except (ValueError, IndexError):
        # If parsing fails, assume always available
        return True