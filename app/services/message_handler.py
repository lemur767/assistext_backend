# app/services/message_handler.py
"""Message handling service refactored for SignalWire integration"""

from app.models.message import Message
from app.models.profile import Profile
from app.models.client import Client
from app.models.auto_reply import AutoReply
from app.models.flagged_message import FlaggedMessage
from app.models.signalwire_account import SignalWireAccount, SignalWirePhoneNumber
from app.services.ai_service import generate_ai_response
from app.services.usage_tracking import UsageTracker
from app.utils.signalwire_helpers import get_signalwire_client
from app.utils.audit_logger import AuditLogger
from app.extensions import db, socketio
from datetime import datetime
import re
import json
from flask import current_app

# Flag words and phrases to watch for
FLAG_WORDS = [
    "police", "cop", "law enforcement", "arrest", "sting", "setup",
    "underage", "minor", "illegal", "bust", "law", "investigation"
]

def handle_incoming_message(profile_id, message_text, sender_number, subaccount_sid=None):
    """
    Process incoming message and determine appropriate response
    Main message handling function for SignalWire
    """
    try:
        # Get profile information
        profile = Profile.query.get(profile_id)
        if not profile:
            current_app.logger.error(f"Profile {profile_id} not found")
            return None

        # Get SignalWire phone number for this profile
        phone_number_record = SignalWirePhoneNumber.query.filter_by(
            profile_id=profile_id,
            is_active=True,
            is_assigned=True
        ).first()

        if not phone_number_record:
            current_app.logger.error(f"No SignalWire number assigned to profile {profile_id}")
            return None

        # Get or create client record
        client = Client.query.filter_by(phone_number=sender_number).first()
        if not client:
            client = Client(phone_number=sender_number)
            db.session.add(client)
            db.session.commit()

        # Check if client is blocked
        if client.is_blocked:
            current_app.logger.info(f"Ignoring message from blocked client: {sender_number}")
            return None

        # Check usage limits before processing
        signalwire_account = phone_number_record.account
        if not UsageTracker.check_message_limit(signalwire_account.id):
            current_app.logger.warning(f"Message limit reached for account {signalwire_account.id}")
            # Could send a notification to user about limit reached
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
        db.session.add(message)
        db.session.commit()

        # Log the incoming message
        AuditLogger.log_event(
            event_type='message_received',
            entity_type='message',
            entity_id=message.id,
            details={
                'profile_id': profile.id,
                'sender_number': sender_number,
                'message_length': len(message_text),
                'subaccount_sid': subaccount_sid
            }
        )

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
            # Save flag information
            flagged_message = FlaggedMessage(
                message_id=message.id,
                reasons=json.dumps(flag_reasons),
                is_reviewed=False
            )
            db.session.add(flagged_message)
            db.session.commit()
            
            # Log flagged content
            AuditLogger.log_event(
                event_type='message_flagged',
                entity_type='message',
                entity_id=message.id,
                details={
                    'reasons': flag_reasons,
                    'sender_number': sender_number,
                    'profile_id': profile.id
                }
            )

        # If AI responses are not enabled, just store the message and don't respond
        if not profile.ai_enabled:
            current_app.logger.info(f"AI disabled for profile {profile.id}, storing message only")
            return None

        # Check for automatic responses based on keywords first
        for auto_reply in AutoReply.query.filter_by(profile_id=profile.id, is_active=True).all():
            if auto_reply.keyword.lower() in message_text.lower():
                current_app.logger.info(f"Auto-reply triggered for keyword: {auto_reply.keyword}")
                return send_signalwire_response(
                    phone_number_record=phone_number_record,
                    profile=profile,
                    response_text=auto_reply.response,
                    recipient_number=sender_number,
                    is_ai_generated=False
                )

        # Check if within business hours - if not, send "out of office" message
        if not is_within_business_hours(profile):
            out_of_office_reply = profile.out_of_office_replies.first()
            if out_of_office_reply:
                current_app.logger.info(f"Sending out-of-office reply for profile {profile.id}")
                return send_signalwire_response(
                    phone_number_record=phone_number_record,
                    profile=profile,
                    response_text=out_of_office_reply.message,
                    recipient_number=sender_number,
                    is_ai_generated=False
                )

        # Generate AI response
        ai_response = generate_ai_response(profile, message_text, sender_number)
        if ai_response:
            current_app.logger.info(f"Generated AI response for profile {profile.id}")
            return send_signalwire_response(
                phone_number_record=phone_number_record,
                profile=profile,
                response_text=ai_response,
                recipient_number=sender_number,
                is_ai_generated=True
            )

        # Fallback response if AI generation fails
        fallback_response = "I'll get back to you soon! 😊"
        current_app.logger.warning(f"AI generation failed, using fallback for profile {profile.id}")
        return send_signalwire_response(
            phone_number_record=phone_number_record,
            profile=profile,
            response_text=fallback_response,
            recipient_number=sender_number,
            is_ai_generated=False
        )

    except Exception as e:
        current_app.logger.error(f"Error handling incoming message: {e}")
        # Log the error for debugging
        AuditLogger.log_event(
            event_type='message_handler_error',
            details={
                'error': str(e),
                'profile_id': profile_id,
                'sender_number': sender_number
            }
        )
        return None

def send_signalwire_response(phone_number_record, profile, response_text, recipient_number, is_ai_generated=True):
    """Send response via SignalWire and save to database"""
    
    try:
        # Check message limits before sending
        if not UsageTracker.check_message_limit(phone_number_record.account.id):
            current_app.logger.warning(f"Cannot send response - message limit reached for account {phone_number_record.account.id}")
            return None

        # Save outgoing message to database first
        message = Message(
            content=response_text,
            is_incoming=False,
            sender_number=recipient_number,
            profile_id=profile.id,
            ai_generated=is_ai_generated,
            timestamp=datetime.utcnow(),
            send_status='pending'
        )
        db.session.add(message)
        db.session.commit()

        # Get SignalWire client for the subaccount
        signalwire_account = phone_number_record.account
        client = get_signalwire_client()

        # Send via SignalWire
        signalwire_response = client.send_sms(
            subaccount_sid=signalwire_account.subaccount_sid,
            from_number=phone_number_record.phone_number,
            to_number=recipient_number,
            body=response_text
        )

        if signalwire_response:
            # Update message with SignalWire SID and success status
            message.signalwire_sid = signalwire_response.get('sid')
            message.send_status = 'sent'
            
            # Record usage for billing/limits
            UsageTracker.record_message_sent(
                signalwire_account_id=signalwire_account.id,
                message_id=message.id,
                cost=0.01  # Approximate cost per SMS
            )
            
            db.session.commit()

            # Log successful send
            AuditLogger.log_event(
                event_type='message_sent',
                entity_type='message',
                entity_id=message.id,
                details={
                    'profile_id': profile.id,
                    'recipient_number': recipient_number,
                    'signalwire_sid': signalwire_response.get('sid'),
                    'ai_generated': is_ai_generated,
                    'subaccount_sid': signalwire_account.subaccount_sid
                }
            )

            # Emit WebSocket event for real-time updates
            socketio.emit('new_message', {
                "id": message.id,
                "content": message.content,
                "is_incoming": message.is_incoming,
                "sender_number": message.sender_number,
                "ai_generated": message.ai_generated,
                "timestamp": message.timestamp.isoformat(),
                "is_read": message.is_read,
                "profile_id": profile.id,
                "send_status": message.send_status
            })

            current_app.logger.info(f"Successfully sent message via SignalWire: {signalwire_response.get('sid')}")
            return message

        else:
            # Update message status to reflect sending failure
            message.send_status = 'failed'
            message.send_error = 'SignalWire API returned no response'
            db.session.commit()
            
            current_app.logger.error(f"SignalWire API returned no response for message {message.id}")
            return None

    except Exception as e:
        # Update message status to reflect sending failure
        if 'message' in locals():
            message.send_status = 'failed'
            message.send_error = str(e)
            db.session.commit()
        
        current_app.logger.error(f"Failed to send SignalWire SMS: {e}")
        
        # Log the error
        AuditLogger.log_event(
            event_type='message_send_failed',
            details={
                'error': str(e),
                'profile_id': profile.id,
                'recipient_number': recipient_number,
                'phone_number': phone_number_record.phone_number
            }
        )
        
        return None

def check_flagged_content(message_text):
    """
    Check if message contains flagged content
    Returns a tuple of (is_flagged, reasons)
    """
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
    price_pattern = r'\$\d+|(\d+)\s*(dollars|usd|cad|hr|hour|session)'
    if re.search(price_pattern, lower_text, re.IGNORECASE):
        is_flagged = True
        reasons.append("Contains explicit pricing")
    
    # Check for suspicious phrases
    suspicious_phrases = [
        "meet up", "in person", "your place", "my place", "hotel", "outcall", "incall",
        "rates", "donation", "tribute", "generous", "screening"
    ]
    
    for phrase in suspicious_phrases:
        if phrase in lower_text:
            is_flagged = True
            reasons.append(f"Contains suspicious phrase: '{phrase}'")
    
    # Check for potential law enforcement indicators
    law_enforcement_phrases = [
        "are you a cop", "law enforcement", "police officer", "investigation",
        "wire", "recording", "evidence", "bust", "sting operation"
    ]
    
    for phrase in law_enforcement_phrases:
        if phrase in lower_text:
            is_flagged = True
            reasons.append(f"Potential law enforcement indicator: '{phrase}'")
    
    return is_flagged, reasons

def is_within_business_hours(profile):
    """Check if current time is within business hours for profile"""
    import pytz
    from datetime import datetime, timedelta
    
    try:
        # Get current time in profile's timezone
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
        if not day_hours or 'start' not in day_hours or 'end' not in day_hours:
            return True  # Default to available if hours not properly configured
            
        start_time_str = day_hours["start"]
        end_time_str = day_hours["end"]
        
        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_hour, end_minute = map(int, end_time_str.split(':'))
        
        start_time = current_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        
        # Handle cases where end time is on the next day (e.g., 22:00 to 02:00)
        if end_hour < start_hour:
            end_time = current_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0) + timedelta(days=1)
        else:
            end_time = current_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        
        return start_time <= current_time <= end_time
        
    except Exception as e:
        current_app.logger.error(f"Error checking business hours: {e}")
        return True  # Default to available if there's an error

def mark_messages_as_read(profile_id, sender_number):
    """Mark all unread messages from sender as read"""
    try:
        unread_messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == sender_number,
            Message.is_incoming == True,
            Message.is_read == False
        ).all()
        
        count = len(unread_messages)
        for msg in unread_messages:
            msg.is_read = True
        
        db.session.commit()
        
        # Log the read action
        if count > 0:
            AuditLogger.log_event(
                event_type='messages_marked_read',
                entity_type='message',
                details={
                    'profile_id': profile_id,
                    'sender_number': sender_number,
                    'count': count
                }
            )
        
        return count
        
    except Exception as e:
        current_app.logger.error(f"Error marking messages as read: {e}")
        return 0

def get_conversation_history(profile_id, sender_number, limit=20):
    """Get conversation history between profile and client"""
    try:
        messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == sender_number
        ).order_by(Message.timestamp.desc()).limit(limit).all()
        
        # Reverse to get chronological order (oldest first)
        return messages[::-1]
        
    except Exception as e:
        current_app.logger.error(f"Error getting conversation history: {e}")
        return []

def block_client(profile_id, client_phone_number, reason=None):
    """Block a client from sending messages to a profile"""
    try:
        client = Client.query.filter_by(phone_number=client_phone_number).first()
        if not client:
            client = Client(phone_number=client_phone_number)
            db.session.add(client)
        
        client.is_blocked = True
        client.blocked_reason = reason
        client.blocked_at = datetime.utcnow()
        
        db.session.commit()
        
        # Log the blocking action
        AuditLogger.log_event(
            event_type='client_blocked',
            entity_type='client',
            entity_id=client.id,
            details={
                'profile_id': profile_id,
                'phone_number': client_phone_number,
                'reason': reason
            }
        )
        
        current_app.logger.info(f"Blocked client {client_phone_number} for profile {profile_id}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error blocking client: {e}")
        return False

def unblock_client(profile_id, client_phone_number):
    """Unblock a client"""
    try:
        client = Client.query.filter_by(phone_number=client_phone_number).first()
        if client:
            client.is_blocked = False
            client.blocked_reason = None
            client.blocked_at = None
            
            db.session.commit()
            
            # Log the unblocking action
            AuditLogger.log_event(
                event_type='client_unblocked',
                entity_type='client',
                entity_id=client.id,
                details={
                    'profile_id': profile_id,
                    'phone_number': client_phone_number
                }
            )
            
            current_app.logger.info(f"Unblocked client {client_phone_number} for profile {profile_id}")
            return True
        
        return False
        
    except Exception as e:
        current_app.logger.error(f"Error unblocking client: {e}")
        return False

def get_message_statistics(profile_id, days=30):
    """Get message statistics for a profile"""
    try:
        from datetime import datetime, timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get message counts
        total_messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.timestamp >= start_date
        ).count()
        
        incoming_messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.is_incoming == True,
            Message.timestamp >= start_date
        ).count()
        
        outgoing_messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.is_incoming == False,
            Message.timestamp >= start_date
        ).count()
        
        ai_generated_messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.is_incoming == False,
            Message.ai_generated == True,
            Message.timestamp >= start_date
        ).count()
        
        # Get unique clients
        unique_clients = db.session.query(Message.sender_number).filter(
            Message.profile_id == profile_id,
            Message.is_incoming == True,
            Message.timestamp >= start_date
        ).distinct().count()
        
        # Get flagged messages
        flagged_messages = db.session.query(Message).join(FlaggedMessage).filter(
            Message.profile_id == profile_id,
            Message.timestamp >= start_date
        ).count()
        
        return {
            'total_messages': total_messages,
            'incoming_messages': incoming_messages,
            'outgoing_messages': outgoing_messages,
            'ai_generated_messages': ai_generated_messages,
            'unique_clients': unique_clients,
            'flagged_messages': flagged_messages,
            'period_days': days,
            'ai_usage_percentage': round((ai_generated_messages / max(outgoing_messages, 1)) * 100, 2)
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting message statistics: {e}")
        return {
            'total_messages': 0,
            'incoming_messages': 0,
            'outgoing_messages': 0,
            'ai_generated_messages': 0,
            'unique_clients': 0,
            'flagged_messages': 0,
            'period_days': days,
            'ai_usage_percentage': 0
        }

# Export the main functions that will be used by the webhook
__all__ = [
    'handle_incoming_message',
    'send_signalwire_response', 
    'mark_messages_as_read',
    'block_client',
    'unblock_client',
    'get_conversation_history',
    'get_message_statistics'
]