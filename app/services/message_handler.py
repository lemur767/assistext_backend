from app.models.profile import Profile
from app.models.message import Message
from app.services.signalwire_service import send_sms_response  # Use correct function name
from app import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def handle_incoming_signalwire_message(profile_id, message_text, sender_number, 
                                     signalwire_message_sid=None, 
                                     signalwire_account_sid=None,
                                     signalwire_status='received'):
    """Handle incoming SMS message from SignalWire"""
    try:
        # Get profile
        profile = Profile.query.get(profile_id)
        if not profile:
            logger.error(f"Profile {profile_id} not found")
            return None
        
        logger.info(f"Processing SignalWire message for profile {profile.name} from {sender_number}")
        
        # Save incoming message to database
        incoming_message = Message(
            profile_id=profile.id,
            content=message_text,
            is_incoming=True,
            sender_number=sender_number,
            signalwire_message_sid=signalwire_message_sid,
            signalwire_account_sid=signalwire_account_sid,
            signalwire_status=signalwire_status,
            ai_generated=False,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(incoming_message)
        db.session.commit()
        
        logger.info(f"Saved incoming SignalWire message: {incoming_message.id}")
        
        # Check if profile has AI responses enabled
        if not profile.ai_enabled:
            logger.info(f"AI responses disabled for profile {profile.name}")
            return incoming_message
        
        # Check if profile is active
        if not profile.is_active:
            logger.info(f"Profile {profile.name} is not active")
            return incoming_message
        
        # Generate and send response
        response_text = generate_response_for_message(profile, message_text, sender_number)
        
        if response_text:
            result = send_sms_response(
                profile=profile,
                response_text=response_text,
                recipient_number=sender_number,
                original_message_id=incoming_message.id
            )
            
            if result:
                logger.info(f"SignalWire response sent successfully")
                return result
            else:
                logger.error(f"Failed to send SignalWire response")
                return incoming_message
        else:
            logger.warning(f"No response generated for message")
            return incoming_message
        
    except Exception as e:
        logger.error(f"Error handling SignalWire message: {str(e)}")
        return None

def send_signalwire_response(profile, response_text, recipient_number, original_message_id=None):
    """Send response via SignalWire and save to database"""
    try:
        # Create outgoing message record
        outgoing_message = Message(
            profile_id=profile.id,
            content=response_text,
            is_incoming=False,
            sender_number=recipient_number,
            ai_generated=True,
            signalwire_status='pending',
            timestamp=datetime.utcnow()
        )
        
        db.session.add(outgoing_message)
        db.session.commit()
        
        # Send via SignalWire
        try:
            signalwire_message = send_sms_response(
                from_number=profile.phone_number,
                to_number=recipient_number,
                body=response_text
            )
            
            # Update message with SignalWire details
            outgoing_message.signalwire_message_sid = signalwire_message.sid
            outgoing_message.signalwire_account_sid = signalwire_message.account_sid
            outgoing_message.signalwire_status = signalwire_message.status
            
            db.session.commit()
            
            logger.info(f"SignalWire response sent: {signalwire_message.sid}")
            return outgoing_message
            
        except Exception as e:
            # Update message with error status
            outgoing_message.signalwire_status = 'failed'
            outgoing_message.signalwire_error_message = str(e)
            db.session.commit()
            
            logger.error(f"Failed to send SignalWire message: {str(e)}")
            return None
        
    except Exception as e:
        logger.error(f"Error creating SignalWire response: {str(e)}")
        return None

def generate_response_for_message(profile, message_text, sender_number):
    """Generate appropriate response for incoming message"""
    try:
        # Check for business hours
        if not is_within_business_hours(profile):
            return get_out_of_office_response(profile)
        
        # Check for simple keyword responses first
        keyword_response = check_keyword_responses(profile, message_text)
        if keyword_response:
            return keyword_response
        
        # Generate AI response if available
        if profile.ai_enabled:
            ai_response = generate_ai_response(profile, message_text, sender_number)
            if ai_response:
                return ai_response
        
        # Fallback response
        return get_fallback_response(profile)
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return get_fallback_response(profile)

def is_within_business_hours(profile):
    """Check if current time is within profile's business hours"""
    try:
        import pytz
        from datetime import datetime
        
        # Get current time in profile's timezone
        timezone = pytz.timezone(profile.timezone or 'UTC')
        current_time = datetime.now(timezone)
        
        # Get day of week
        day_of_week = current_time.strftime('%A').lower()
        
        # Get business hours
        business_hours = profile.get_business_hours()
        
        if not business_hours or day_of_week not in business_hours:
            return True  # Default to always available if not configured
        
        day_hours = business_hours[day_of_week]
        if not day_hours or 'start' not in day_hours or 'end' not in day_hours:
            return True
        
        # Parse time strings
        start_time_str = day_hours['start']
        end_time_str = day_hours['end']
        
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_hour, end_minute = map(int, end_time_str.split(':'))
        
        current_minutes = current_time.hour * 60 + current_time.minute
        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute
        
        # Handle overnight hours
        if end_minutes < start_minutes:
            return current_minutes >= start_minutes or current_minutes <= end_minutes
        else:
            return start_minutes <= current_minutes <= end_minutes
        
    except Exception as e:
        logger.error(f"Error checking business hours: {e}")
        return True  # Default to available

def check_keyword_responses(profile, message_text):
    """Check for simple keyword-based responses"""
    message_lower = message_text.lower().strip()
    
    # Basic keyword responses
    keyword_responses = {
        'hi': "Hi there! Thanks for reaching out.",
        'hello': "Hello! Thanks for your message.",
        'hey': "Hey! Thanks for texting.",
        'info': "Thanks for your interest! I'll get back to you with more information.",
        'price': "Thanks for asking! I'll send you pricing details shortly.",
        'available': "Thanks for checking! Let me confirm my availability.",
        'booking': "Thank you for your interest in booking! I'll get back to you soon.",
        'location': "Thanks for asking about location! I'll send you details."
    }
    
    for keyword, response in keyword_responses.items():
        if keyword in message_lower:
            return response
    
    return None

def generate_ai_response(profile, message_text, sender_number):
    """Generate AI response (placeholder for now)"""
    try:
        # This is where you'd integrate with your LLM service
        # For now, return a personalized response
        
        client_greeting = "there"
        if sender_number:
            # Extract last 4 digits for personalization
            last_digits = sender_number[-4:] if len(sender_number) >= 4 else sender_number
            client_greeting = f"#{last_digits}"
        
        responses = [
            f"Hi {client_greeting}! Thanks for your message. I'll get back to you soon! 😊",
            f"Hello {client_greeting}! I received your message and will respond shortly.",
            f"Hey {client_greeting}! Thanks for reaching out. I'll be in touch!",
            f"Hi {client_greeting}! Got your message. I'll get back to you as soon as I can.",
        ]
        
        import random
        return random.choice(responses)
        
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        return None

def get_out_of_office_response(profile):
    """Get out of office response"""
    return f"Thanks for your message! I'm currently outside my business hours. I'll get back to you during my next available time. - {profile.name}"

def get_fallback_response(profile):
    """Get fallback response when other methods fail"""
    return f"Thanks for your message! I'll get back to you soon. - {profile.name}"
