"""
Celery Tasks for Async Processing
app/tasks.py - Background tasks for SMS processing, AI responses, and maintenance
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from celery import current_task
from celery.exceptions import Retry
from app.extensions import celery, db
from app.models.messaging import Message

from app.models.user import User as user
from app.services.signalwire_service import SignalWireService
from app.services.billing_service import BillingService
from app.
from sqlalchemy.exc import SQLAlchemyError
import time

# Initialize services
ai_service = AIService()
signalwire_service = SignalWireService()

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_incoming_sms(self, webhook_data: Dict[str, Any]):
    """
    Process incoming SMS message asynchronously
    
    Args:
        webhook_data: Parsed webhook data from SignalWire
    
    Returns:
        Dict with processing result
    """
    try:
        message_sid = webhook_data.get('message_sid', '')
        from_number = webhook_data.get('from_number', '')
        to_number = webhook_data.get('to_number', '')
        message_body = webhook_data.get('message_body', '')
        
        logging.info(f"[TASK] Processing SMS {message_sid}: {from_number} -> {to_number}")
        
        # Store incoming message in database
        stored_message = store_message_in_db(
            message_sid=message_sid,
            from_number=from_number,
            to_number=to_number,
            body=message_body,
            direction='inbound',
            status='processing'
        )
        
        if not stored_message:
            raise Exception("Failed to store message in database")
        
        # Find profile
        user = user.query.filter_by(phone_number=to_number, is_active=True).first()
        
        if not user:
            logging.warning(f"No active user found for number: {to_number}")
            return {
                'success': False,
                'error': 'No active profile found',
                'message_sid': message_sid
            }
        
        # Check if AI is enabled
        if not user.ai_enabled:
            logging.info(f"AI disabled for {user.id}")
            return {
                'success': True,
                'ai_response_generated': False,
                'reason': 'AI disabled for user'
            }
        
        # Queue AI response generation
        generate_ai_response.delay(
            message_sid=message_sid,
            profile_id=user.id,
            message_body=message_body,
            from_number=from_number,
            to_number=to_number
        )
        
        return {
            'success': True,
            'message_sid': message_sid,
            'user_id': user.id,
            'ai_task_queued': True
        }
        
    except Exception as e:
        logging.error(f"[TASK] SMS processing failed: {str(e)}")
        
        # Update message status to failed
        if 'message_sid' in webhook_data:
            update_message_status.delay(
                webhook_data['message_sid'],
                'failed',
                error_message=str(e)
            )
        
        # Retry the task
        raise self.retry(countdown=60, max_retries=3)

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 30})
def generate_ai_response(self, message_sid: str, user_id: int, message_body: str, 
                        from_number: str, to_number: str):
    """
    Generate AI response and send SMS
    
    Args:
        message_sid: Original message SID
        user_id: User ID for context
        message_body: Incoming message text
        from_number: Sender's phone number
        to_number: Recipient's phone number (profile number)
    
    Returns:
        Dict with AI response result
    """
    try:
        logging.info(f"[TASK] Generating AI response for {message_sid}")
        
        # Get profile
        user = user.query.filter_by(id=user_id, is_active=True).first()
        if not user:
            raise Exception(f"${user.username} was not found")
        
        # Generate AI response
        ai_response = ai_service.generate_response(
            user=user,
            message=message_body,
            sender_number=from_number,
            context={'message_sid': message_sid}
        )
        
        if not ai_response:
            logging.warning(f"No AI response generated for {message_sid}")
            return {
                'success': False,
                'error': 'AI response generation failed',
                'message_sid': message_sid
            }
        
        logging.info(f"[TASK] AI response generated: {ai_response[:50]}...")
        
        # Queue SMS sending
        send_sms_message.delay(
            to_number=from_number,
            from_number=to_number,
            message_body=ai_response,
            original_message_sid=message_sid,
            user_id=user_id
        )
        
        return {
            'success': True,
            'ai_response': ai_response,
            'message_sid': message_sid,
            'sms_task_queued': True
        }
        
    except Exception as e:
        logging.error(f"[TASK] AI response generation failed: {str(e)}")
        
        # Send fallback response
        fallback_response = "Thank you for your message. I'll get back to you soon!"
        
        send_sms_message.delay(
            to_number=from_number,
            from_number=to_number,
            message_body=fallback_response,
            original_message_sid=message_sid,
            user_id=user_id,
            is_fallback=True
        )
        
        raise self.retry(countdown=30, max_retries=2)

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 15})
def send_sms_message(self, to_number: str, from_number: str, message_body: str,
                    original_message_sid: str = None, user_id: int = None,
                    is_fallback: bool = False):
    """
    Send SMS message via SignalWire
    
    Args:
        to_number: Recipient phone number
        from_number: Sender phone number
        message_body: Message content
        original_message_sid: Original incoming message SID
        user_id: User ID for tracking
        is_fallback: Whether this is a fallback response
    
    Returns:
        Dict with sending result
    """
    try:
        logging.info(f"[TASK] Sending SMS: {from_number} -> {to_number}")
        
        # Send via SignalWire
        result = signalwire_service.send_sms(
            to_number=to_number,
            from_number=from_number,
            message_body=message_body
        )
        
        if result['success']:
            # Store outgoing message in database
            store_message_in_db(
                message_sid=result['message_sid'],
                from_number=from_number,
                to_number=to_number,
                body=message_body,
                direction='outbound',
                status='sent',
                user_id=user_id,
                related_message_sid=original_message_sid,
                is_ai_generated=not is_fallback
            )
            
            logging.info(f"[TASK] SMS sent successfully: {result['message_sid']}")
            
            return {
                'success': True,
                'message_sid': result['message_sid'],
                'original_message_sid': original_message_sid,
                'is_fallback': is_fallback
            }
        else:
            raise Exception(f"SignalWire send failed: {result['error']}")
            
    except Exception as e:
        logging.error(f"[TASK] SMS sending failed: {str(e)}")
        
        # Store failed message
        if original_message_sid:
            store_message_in_db(
                message_sid=f"failed_{int(time.time())}",
                from_number=from_number,
                to_number=to_number,
                body=message_body,
                direction='outbound',
                status='failed',
                user_id=user_id,
                error_message=str(e)
            )
        
        raise self.retry(countdown=15, max_retries=3)

@celery.task
def update_message_status(message_sid: str, status: str, error_code: str = None, 
                         error_message: str = None):
    """
    Update message status in database
    
    Args:
        message_sid: Message SID to update
        status: New status
        error_code: Error code if applicable
        error_message: Error message if applicable
    """
    try:
        message = Message.query.filter_by(message_sid=message_sid).first()
        
        if message:
            message.status = status
            if error_code:
                message.error_code = error_code
            if error_message:
                message.error_message = error_message
            
            message.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            logging.info(f"[TASK] Updated message {message_sid} status to {status}")
        else:
            logging.warning(f"[TASK] Message {message_sid} not found for status update")
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"[TASK] Database error updating message status: {str(e)}")
    except Exception as e:
        logging.error(f"[TASK] Error updating message status: {str(e)}")

@celery.task
def cleanup_old_messages():
    """
    Cleanup old messages and maintain database health
    Runs periodically via Celery Beat
    """
    try:
        # Delete messages older than 90 days
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        old_messages = Message.query.filter(Message.timestamp < cutoff_date).all()
        
        for message in old_messages:
            db.session.delete(message)
        
        db.session.commit()
        
        logging.info(f"[TASK] Cleaned up {len(old_messages)} old messages")
        
        return {
            'success': True,
            'deleted_count': len(old_messages),
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"[TASK] Cleanup failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery.task
def health_check():
    """
    Periodic health check task
    Monitors system health and logs status
    """
    try:
        health_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'database': False,
            'ai_service': False,
            'signalwire': False,
            'redis': False
        }
        
        # Check database
        try:
            db.session.execute('SELECT 1')
            health_status['database'] = True
        except:
            pass
        
        # Check AI service
        health_status['ai_service'] = ai_service.is_configured()
        
        # Check SignalWire
        health_status['signalwire'] = signalwire_service.is_configured()
        
        # Check Redis
        try:
            from app.extensions import get_redis
            redis_client = get_redis()
            if redis_client:
                redis_client.ping()
                health_status['redis'] = True
        except:
            pass
        
        # Log health status
        healthy_services = sum(health_status.values() if isinstance(v, bool) else 0 for v in health_status.values())
        total_services = len([v for v in health_status.values() if isinstance(v, bool)])
        
        logging.info(f"[HEALTH] {healthy_services}/{total_services} services healthy: {health_status}")
        
        return health_status
        
    except Exception as e:
        logging.error(f"[TASK] Health check failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery.task
def batch_send_messages(messages: list):
    """
    Send multiple messages in batch
    
    Args:
        messages: List of message dictionaries with to, from, body
    """
    try:
        results = []
        
        for msg in messages:
            result = send_sms_message.delay(
                to_number=msg['to'],
                from_number=msg['from'],
                message_body=msg['body'],
                user_id=msg.get('user_id')
            )
            results.append(result.id)
        
        logging.info(f"[TASK] Queued {len(results)} messages for batch sending")
        
        return {
            'success': True,
            'queued_count': len(results),
            'task_ids': results
        }
        
    except Exception as e:
        logging.error(f"[TASK] Batch send failed: {str(e)}")
        return {'success': False, 'error': str(e)}

# Helper function for database operations
def store_message_in_db(message_sid: str, from_number: str, to_number: str, 
                       body: str, direction: str, status: str = 'received',
                       user_id: int = None, client_id: int = None,
                       related_message_sid: str = None, is_ai_generated: bool = False,
                       error_message: str = None) -> Optional[Message]:
    """
    Store message in database with error handling
    
    Returns:
        Message instance or None if failed
    """
    try:
        # Find or create client for incoming messages
        if direction == 'inbound' and not client_id:
            client = Client.query.filter_by(phone_number=from_number).first()
            if not client:
                client = Client(
                    phone_number=from_number,
                    name=f"Client {from_number[-4:]}",
                    first_contact=datetime.utcnow(),
                    last_contact=datetime.utcnow(),
                    is_active=True
                )
                db.session.add(client)
                db.session.flush()
            else:
                client.last_contact = datetime.utcnow()
            
            client_id = client.id
        
        # Create message record
        message = Message(
            message_sid=message_sid,
            user_id=user_id,
            client_id=client_id,
            sender_number=from_number,
            recipient_number=to_number,
            message_body=body,
            direction=direction,
            status=status,
            timestamp=datetime.utcnow(),
            is_ai_generated=is_ai_generated,
            related_message_sid=related_message_sid,
            error_message=error_message
        )
        
        db.session.add(message)
        db.session.commit()
        
        return message
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error storing message: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Error storing message: {str(e)}")
        return None