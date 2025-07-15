from app.models.user import User
from app.models.client import Client
from app.models.message import Message, FlaggedMessage
from app.extensions import db
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

# UPDATED: All functions now work with User model instead of Profile model


def process_incoming_message(user, message_text, sender_number, message_sid=None):
    """
    Process incoming message and generate appropriate response
    UPDATED: Works with User model instead of Profile
    """
    try:
        # Check if we should respond to this message
        if not should_respond_to_message(user, message_text, sender_number):
            logger.info(f"Not responding to message from {sender_number} for user {user.id}")
            return None
        
        # Check for inappropriate content and flag if necessary
        if is_inappropriate_content(message_text):
            flag_inappropriate_message(user.id, sender_number, message_text, message_sid)
        
        # Generate response
        response_text = generate_response(user, message_text, sender_number)
        
        if response_text:
            # Send response
            response_message = send_response(user, response_text, sender_number, message_sid)
            return response_message
        
        return None
        
    except Exception as e:
        logger.error(f"Error processing incoming message: {str(e)}")
        return None


def should_respond_to_message(user, message_text, sender_number):
    """
    Determine if we should auto-respond to this message
    UPDATED: Uses User model settings
    """
    
    # Check if user has AI/auto-reply enabled
    if not user.ai_enabled or not user.auto_reply_enabled:
        return False
    
    # Check daily message limit
    today_count = Message.get_daily_count(user.id)
    if today_count >= user.daily_message_limit:
        logger.info(f"Daily limit reached for user {user.id}: {today_count}/{user.daily_message_limit}")
        return False
    
    # Check if client is blocked
    client = Client.query.filter_by(phone_number=sender_number).first()
    if client:
        # Check global block status
        if client.is_blocked:
            return False
        
        # Check user-specific block status
        relationship = client.get_user_relationship(user.id)
        if relationship and relationship.get('is_blocked'):
            return False
    
    # Check business hours (always respond if out of office is enabled)
    if not is_within_business_hours(user):
        return user.out_of_office_enabled
    
    return True


def is_within_business_hours(user):
    """
    Check if current time is within user's business hours
    UPDATED: Uses User model business_hours
    """
    try:
        import pytz
        from datetime import datetime, time
        
        business_hours = user.get_business_hours()
        if not business_hours:
            return True  # Default to always available if no hours set
        
        # Get current time in user's timezone
        user_tz = pytz.timezone(user.timezone or 'UTC')
        current_time = datetime.now(user_tz)
        current_day = current_time.strftime('%A').lower()
        
        # Check if today has business hours configured
        if current_day not in business_hours:
            return False
        
        day_config = business_hours[current_day]
        
        # Check if business hours are enabled for today
        if not day_config.get('enabled', False):
            return False
        
        # Parse start and end times
        start_str = day_config.get('start', '09:00')
        end_str = day_config.get('end', '17:00')
        
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time = datetime.strptime(end_str, '%H:%M').time()
        
        current_time_only = current_time.time()
        
        # Handle overnight hours (e.g., 22:00 to 06:00)
        if start_time > end_time:
            return current_time_only >= start_time or current_time_only <= end_time
        else:
            return start_time <= current_time_only <= end_time
    
    except Exception as e:
        logger.error(f"Error checking business hours: {str(e)}")
        return True  # Default to available on error


def generate_response(user, message_text, sender_number):
    """
    Generate appropriate response based on user settings
    UPDATED: Uses User model auto-reply settings and AI configuration
    """
    
    # 1. Check for keyword-based auto-replies first
    auto_replies = user.get_auto_reply_keywords()
    if auto_replies:
        message_lower = message_text.lower()
        
        # Sort keywords by length (longer first) for better matching
        sorted_keywords = sorted(auto_replies.keys(), key=len, reverse=True)
        
        for keyword in sorted_keywords:
            if keyword.lower() in message_lower:
                logger.info(f"Keyword match for '{keyword}' for user {user.id}")
                return auto_replies[keyword]
    
    # 2. Check if outside business hours and out of office is enabled
    if not is_within_business_hours(user) and user.out_of_office_enabled:
        if user.out_of_office_message:
            return user.out_of_office_message
        else:
            return get_default_out_of_office_message(user)
    
    # 3. Generate AI response if enabled
    if user.ai_enabled:
        ai_response = generate_ai_response(user, message_text, sender_number)
        if ai_response:
            return ai_response
    
    # 4. Fallback to default response
    return get_default_response(user)


def generate_ai_response(user, message_text, sender_number):
    """
    Generate AI response using user's AI settings
    UPDATED: Uses User model AI configuration
    """
    try:
        # Get user's AI settings
        ai_settings = user.get_ai_settings()
        
        if not ai_settings['enabled']:
            return None
        
        # Get text examples for context
        text_examples = user.get_text_examples()
        
        # Build context for AI
        context = {
            'user_name': user.display_name or user.full_name,
            'personality': ai_settings['personality'],
            'instructions': ai_settings['instructions'],
            'text_examples': text_examples,
            'business_hours': user.get_business_hours(),
            'sender_number': sender_number[-4:] if sender_number else 'there'
        }
        
        # TODO: Implement actual AI service call
        # This would call your LLM service (OpenAI, Claude, etc.)
        # For now, return a contextual response
        
        return generate_contextual_response(message_text, context)
        
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        return None


def generate_contextual_response(message_text, context):
    """
    Generate a contextual response (placeholder for actual AI implementation)
    """
    message_lower = message_text.lower()
    sender_ref = context['sender_number']
    user_name = context['user_name']
    
    # Basic keyword responses with personality
    if any(word in message_lower for word in ['hello', 'hi', 'hey']):
        responses = [
            f"Hi {sender_ref}! Thanks for reaching out. How can I help you today? 😊",
            f"Hello! Great to hear from you. What can I do for you?",
            f"Hey {sender_ref}! Thanks for the message. What's on your mind?"
        ]
    elif any(word in message_lower for word in ['price', 'cost', 'rate']):
        responses = [
            f"Thanks for asking about pricing! I'll send you my rates and availability shortly.",
            f"Hi {sender_ref}! I'd be happy to discuss pricing with you. Let me get back to you with details.",
            f"Thanks for your interest! I'll send over my current rates and we can chat about what works best."
        ]
    elif any(word in message_lower for word in ['available', 'free', 'booking']):
        responses = [
            f"Thanks for checking my availability! Let me look at my schedule and get back to you.",
            f"Hi {sender_ref}! I appreciate you reaching out about booking. I'll check my calendar and respond soon.",
            f"Thanks for your interest in booking! I'll review my availability and send you some options."
        ]
    elif any(word in message_lower for word in ['location', 'where', 'incall', 'outcall']):
        responses = [
            f"Thanks for asking about location! I'll send you details about my available options.",
            f"Hi {sender_ref}! I'd be happy to discuss location options with you. Let me get back to you with details.",
            f"Thanks for your message! I'll send you information about location and arrangements."
        ]
    else:
        # Generic responses
        responses = [
            f"Hi {sender_ref}! Thanks for your message. I'll get back to you soon! 😊",
            f"Hello! I received your message and will respond shortly. Thanks for reaching out!",
            f"Thanks for texting {sender_ref}! I'll be in touch soon with more details.",
            f"Hi there! I got your message and will get back to you as soon as I can!"
        ]
    
    import random
    return random.choice(responses)


def get_default_out_of_office_message(user):
    """Get default out of office message"""
    return (f"Thanks for your message! I'm currently outside my business hours. "
            f"I'll get back to you during my next available time. - {user.display_name or user.full_name}")


def get_default_response(user):
    """Get default fallback response"""
    return f"Thanks for your message! I'll get back to you soon. - {user.display_name or user.full_name}"


def send_response(user, response_text, recipient_number, related_message_sid=None):
    """
    Send response via SignalWire and save to database
    UPDATED: Uses User model SignalWire configuration
    """
    
    if not user.is_signalwire_configured():
        logger.error(f"SignalWire not configured for user {user.id}")
        return None
    
    try:
        # Find or create client
        client = Client.find_or_create(recipient_number, user.id)
        
        # Create outgoing message record first
        message = Message(
            user_id=user.id,  # UPDATED: use user_id instead of profile_id
            client_id=client.id,
            sender_number=user.signalwire_phone_number,
            recipient_number=recipient_number,
            message_body=response_text,
            direction='outbound',
            status='pending',
            is_ai_generated=True,
            related_message_sid=related_message_sid
        )
        db.session.add(message)
        db.session.flush()  # Get the ID
        
        # TODO: Send via actual SignalWire API
        # from app.utils.signalwire_helpers import send_sms
        # 
        # signalwire_message = send_sms(
        #     from_number=user.signalwire_phone_number,
        #     to_number=recipient_number,
        #     body=response_text,
        #     user=user
        # )
        # 
        # # Update message with SignalWire SID
        # message.message_sid = signalwire_message.sid
        # message.status = 'sent'
        
        # For now, simulate successful sending
        message.message_sid = f"SM{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{message.id}"
        message.status = 'sent'
        
        # Update user message count
        user.update_message_count(sent=1)
        
        db.session.commit()
        
        logger.info(f"Response sent to {recipient_number}: {response_text[:50]}...")
        
        # TODO: Emit WebSocket event for real-time updates
        # from app.extensions import socketio
        # socketio.emit('new_message', {
        #     'message': message.to_dict(),
        #     'user_id': user.id
        # }, room=f"user_{user.id}")
        
        return message
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error sending response: {str(e)}")
        return None


def is_inappropriate_content(message_text):
    """
    Check if message contains inappropriate content
    """
    # Basic inappropriate content detection
    inappropriate_keywords = [
        # Add your inappropriate keywords here
        'spam', 'scam', 'free money', 'click here', 'urgent',
        # Add more based on your needs
    ]
    
    message_lower = message_text.lower()
    
    # Check for obvious spam patterns
    if any(keyword in message_lower for keyword in inappropriate_keywords):
        return True
    
    # Check for excessive capitalization
    if len(message_text) > 10 and sum(1 for c in message_text if c.isupper()) / len(message_text) > 0.7:
        return True
    
    # Check for suspicious URLs
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    if re.search(url_pattern, message_text):
        return True
    
    return False


def flag_inappropriate_message(user_id, sender_number, message_text, message_sid=None):
    """
    Flag inappropriate message for review
    UPDATED: Uses user_id instead of profile_id
    """
    try:
        # Find the message record
        message = None
        if message_sid:
            message = Message.query.filter_by(message_sid=message_sid).first()
        
        if not message:
            # Find by content and sender (less reliable but better than nothing)
            message = Message.query.filter(
                Message.user_id == user_id,
                Message.sender_number == sender_number,
                Message.message_body == message_text
            ).order_by(Message.timestamp.desc()).first()
        
        if message:
            # Flag the message
            message.mark_as_flagged("Inappropriate content detected")
            
            # Create detailed flag record
            flagged_message = FlaggedMessage(
                message_id=message.id,
                user_id=user_id,  # UPDATED: use user_id instead of profile_id
                reason='inappropriate_content',
                severity='medium',
                detection_method='auto',
                confidence_score=0.8
            )
            db.session.add(flagged_message)
            db.session.commit()
            
            logger.warning(f"Flagged inappropriate message from {sender_number}: {message_text[:50]}...")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error flagging inappropriate message: {str(e)}")


# Utility functions for message analysis

def analyze_message_sentiment(message_text):
    """Analyze message sentiment (placeholder for actual implementation)"""
    # TODO: Implement actual sentiment analysis
    # Could use libraries like TextBlob, VADER, or cloud APIs
    
    positive_words = ['thanks', 'great', 'awesome', 'love', 'perfect', 'excellent']
    negative_words = ['bad', 'terrible', 'awful', 'hate', 'horrible', 'worst']
    
    message_lower = message_text.lower()
    
    positive_count = sum(1 for word in positive_words if word in message_lower)
    negative_count = sum(1 for word in negative_words if word in message_lower)
    
    if positive_count > negative_count:
        return 'positive'
    elif negative_count > positive_count:
        return 'negative'
    else:
        return 'neutral'


def extract_intent(message_text):
    """Extract intent from message (placeholder for actual implementation)"""
    # TODO: Implement actual intent recognition
    # Could use NLP libraries or cloud APIs
    
    message_lower = message_text.lower()
    
    if any(word in message_lower for word in ['price', 'cost', 'rate', 'fee']):
        return 'pricing_inquiry'
    elif any(word in message_lower for word in ['available', 'book', 'appointment', 'schedule']):
        return 'booking_inquiry'
    elif any(word in message_lower for word in ['location', 'where', 'address']):
        return 'location_inquiry'
    elif any(word in message_lower for word in ['hello', 'hi', 'hey']):
        return 'greeting'
    else:
        return 'general_inquiry'


def get_response_suggestions(user, message_text, sender_number):
    """
    Get suggested responses for manual review
    UPDATED: Uses User model for context
    """
    try:
        intent = extract_intent(message_text)
        sentiment = analyze_message_sentiment(message_text)
        
        # Get user context
        ai_settings = user.get_ai_settings()
        personality = ai_settings.get('personality', 'professional')
        
        suggestions = []
        
        # Generate suggestions based on intent
        if intent == 'pricing_inquiry':
            suggestions = [
                "Thanks for asking about pricing! I'll send you my current rates and packages.",
                "Hi! I'd be happy to discuss my rates with you. Let me get back to you with details.",
                "Thanks for your interest! I'll send over my pricing information shortly."
            ]
        elif intent == 'booking_inquiry':
            suggestions = [
                "Thanks for reaching out about booking! Let me check my availability and get back to you.",
                "Hi! I appreciate your interest in scheduling. I'll review my calendar and send you some options.",
                "Thanks for the booking inquiry! I'll get back to you with my available times."
            ]
        elif intent == 'location_inquiry':
            suggestions = [
                "Thanks for asking about location! I'll send you details about my available arrangements.",
                "Hi! I'd be happy to discuss location options with you. Let me get back to you with details."
            ]
        else:
            suggestions = [
                f"Thanks for your message! I'll get back to you soon.",
                f"Hi! I received your message and will respond shortly.",
                f"Thanks for reaching out! I'll be in touch with more details."
            ]
        
        return {
            'intent': intent,
            'sentiment': sentiment,
            'suggestions': suggestions[:3]  # Return top 3 suggestions
        }
        
    except Exception as e:
        logger.error(f"Error generating response suggestions: {str(e)}")
        return {
            'intent': 'unknown',
            'sentiment': 'neutral',
            'suggestions': ["Thanks for your message! I'll get back to you soon."]
        }