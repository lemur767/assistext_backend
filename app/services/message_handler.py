from app.models.message import Message
from app.models.user import User  # Changed from Profile
from app.models.client import Client
from app.services.ai_service import generate_ai_response
from app.utils.signalwire_helpers import send_sms
from app.extensions import db
from datetime import datetime

def handle_incoming_message(user_id, message_text, sender_number):
    """
    Process incoming message for a user (not profile)
    """
    # Get user information (instead of profile)
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return None
    
    # Get or create client record
    client = Client.query.filter_by(phone_number=sender_number).first()
    if not client:
        client = Client(
            phone_number=sender_number,
            user_id=user_id  # Associate client with user directly
        )
        db.session.add(client)
        db.session.commit()
    
    # Check if client is blocked
    if client.is_blocked:
        return None
    
    # Save incoming message
    message = Message(
        content=message_text,
        is_incoming=True,
        sender_number=sender_number,
        recipient_number=user.business_phone,
        user_id=user.id,  # Changed from profile_id
        ai_generated=False,
        timestamp=datetime.utcnow()
    )
    db.session.add(message)
    user.increment_message_count(sent=False)
    db.session.commit()
    
    # Generate AI response if enabled
    if user.ai_enabled and user.auto_reply_enabled:
        ai_response = generate_ai_response(user, message_text, sender_number)
        if ai_response:
            # Send AI response via SignalWire
            send_sms(user.business_phone, sender_number, ai_response)
            
            # Save AI response to database
            response_message = Message(
                content=ai_response,
                is_incoming=False,
                sender_number=user.business_phone,
                recipient_number=sender_number,
                user_id=user.id,
                ai_generated=True,
                timestamp=datetime.utcnow()
            )
            db.session.add(response_message)
            user.increment_message_count(sent=True)
            db.session.commit()
    
    return message