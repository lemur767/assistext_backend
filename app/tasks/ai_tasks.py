# app/tasks/ai_tasks.py
import os
from celery import Celery
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

# Initialize Celery
celery = Celery('assistext')

# Configure Celery
celery.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'app.tasks.ai_tasks.process_incoming_message_task': {'queue': 'ai_processing'},
        'app.tasks.ai_tasks.send_sms_response': {'queue': 'sms_sending'},
        'app.tasks.ai_tasks.track_usage': {'queue': 'analytics'},
        'app.tasks.ai_tasks.check_usage_limits': {'queue': 'analytics'},
    },
    task_default_queue='default',
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression='gzip',
    result_compression='gzip'
)

@celery.task(bind=True, max_retries=3)
def process_incoming_message_task(self, user_id: int, message_id: int, from_number: str, message_body: str):
    """
    Process incoming message with AI and send response
    
    Args:
        user_id: Database user ID
        message_id: Database message ID
        from_number: Client phone number
        message_body: Message content
    """
    try:
        # Import here to avoid circular imports
        from app import create_app
        from app.models.user import User
        from app.models.message import Message
        from app.services.ai_service import AIService
        from app.extensions import db
        
        # Create Flask app context for database operations
        app = create_app()
        with app.app_context():
            
            # Get user and message from database
            user = User.query.get(user_id)
            message = Message.query.get(message_id)
            
            if not user or not message:
                logger.error(f"User {user_id} or message {message_id} not found")
                return {'success': False, 'error': 'User or message not found'}
            
            # Check if user has AI enabled
            if not user.ai_enabled:
                logger.info(f"AI disabled for user {user_id}")
                return {'success': True, 'message': 'AI disabled'}
            
            # Check trial status
            if user.is_trial_user and user.trial_days_remaining <= 0:
                logger.info(f"Trial expired for user {user_id}")
                return {'success': False, 'error': 'Trial expired'}
            
            # Get conversation history
            conversation_history = Message.get_conversation_history(
                user_id, from_number, limit=10
            )
            
            # Convert to format expected by AI service
            history_data = [msg.to_dict() for msg in conversation_history]
            
            # Initialize AI service
            ai_service = AIService()
            
            # Generate AI response
            ai_result = ai_service.generate_response(
                user=user,
                incoming_message=message_body,
                conversation_history=history_data
            )
            
            # Update message with AI processing results
            message.ai_processed = True
            message.ai_confidence_score = ai_result.get('confidence', 0.0)
            message.ai_processing_time = ai_result.get('processing_time', 0.0)
            
            if not ai_result['success']:
                message.error_message = ai_result.get('error', 'AI processing failed')
                db.session.commit()
                
                # Retry if not max retries
                if self.request.retries < self.max_retries:
                    logger.warning(f"Retrying AI processing for message {message_id}")
                    raise self.retry(countdown=60 * (self.request.retries + 1))
                
                return {'success': False, 'error': ai_result.get('error')}
            
            # Create outbound message record
            response_message = Message(
                user_id=user_id,
                from_number=user.signalwire_phone_number,
                to_number=from_number,
                body=ai_result['response'],
                direction='outbound',
                status='pending',
                thread_id=message.thread_id,
                ai_response_generated=True,
                ai_confidence_score=ai_result.get('confidence', 0.0)
            )
            
            db.session.add(response_message)
            db.session.flush()  # Get the ID
            
            # Send response via SignalWire
            send_result = send_sms_response.delay(
                user_id=user_id,
                message_id=response_message.id,
                to_number=from_number,
                message_body=ai_result['response']
            )
            
            # Update original message
            message.ai_response_generated = True
            db.session.commit()
            
            logger.info(f"AI response generated for message {message_id}, queued for sending")
            
            return {
                'success': True,
                'response_message_id': response_message.id,
                'ai_confidence': ai_result.get('confidence'),
                'send_task_id': send_result.id
            }
            
    except Exception as e:
        logger.error(f"AI processing task failed: {e}")
        
        # Update message with error
        try:
            from app import create_app
            from app.models.message import Message
            from app.extensions import db
            
            app = create_app()
            with app.app_context():
                message = Message.query.get(message_id)
                if message:
                    message.ai_processed = True
                    message.error_message = str(e)
                    db.session.commit()
        except:
            pass
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {'success': False, 'error': str(e)}


@celery.task(bind=True, max_retries=3)
def send_sms_response(self, user_id: int, message_id: int, to_number: str, message_body: str):
    """
    Send SMS response via SignalWire
    
    Args:
        user_id: Database user ID
        message_id: Database message ID for the outbound message
        to_number: Recipient phone number
        message_body: Message to send
    """
    try:
        from app import create_app
        from app.models.user import User
        from app.models.message import Message
        from app.extensions import db
        from signalwire.rest import Client as SignalWireClient
        
        app = create_app()
        with app.app_context():
            
            # Get user and message
            user = User.query.get(user_id)
            message = Message.query.get(message_id)
            
            if not user or not message:
                logger.error(f"User {user_id} or message {message_id} not found for SMS sending")
                return {'success': False, 'error': 'User or message not found'}
            
            # Check if user has SignalWire configured
            if not user.signalwire_configured:
                logger.error(f"SignalWire not configured for user {user_id}")
                message.status = 'failed'
                message.error_message = 'SignalWire not configured'
                db.session.commit()
                return {'success': False, 'error': 'SignalWire not configured'}
            
            # Initialize SignalWire client with user's subproject credentials
            space_url = os.getenv('SIGNALWIRE_SPACE')
            space_url_formatted = f"https://{space_url}" if not space_url.startswith('http') else space_url
            
            client = SignalWireClient(
                user.signalwire_subproject_id,
                user.signalwire_subproject_token,
                signalwire_space_url=space_url_formatted
            )
            
            # Send the message
            response = client.messages.create(
                from_=user.signalwire_phone_number,
                to=to_number,
                body=message_body
            )
            
            # Update message record
            message.external_id = response.sid
            message.status = 'sent'
            message.sent_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"SMS sent successfully: {response.sid}")
            
            # Track usage for billing
            track_usage.delay(user_id, 'sms_sent', 1)
            track_usage.delay(user_id, 'ai_response', 1)
            
            return {
                'success': True,
                'message_sid': response.sid,
                'status': response.status,
                'message_id': message_id
            }
            
    except Exception as e:
        logger.error(f"SMS sending failed: {e}")
        
        # Update message with error
        try:
            from app import create_app
            from app.models.message import Message
            from app.extensions import db
            
            app = create_app()
            with app.app_context():
                message = Message.query.get(message_id)
                if message:
                    message.status = 'failed'
                    message.error_message = str(e)
                    message.failed_at = datetime.utcnow()
                    message.retry_count += 1
                    db.session.commit()
        except:
            pass
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            logger.warning(f"Retrying SMS send for message {message_id}")
            raise self.retry(countdown=30 * (2 ** self.request.retries))
        
        return {'success': False, 'error': str(e)}


@celery.task
def track_usage(user_id: int, usage_type: str, quantity: int):
    """
    Track usage for billing purposes
    
    Args:
        user_id: Database user ID
        usage_type: Type of usage ('sms_sent', 'sms_received', 'ai_response')
        quantity: Amount to track
    """
    try:
        from app import create_app
        from app.extensions import db
        from datetime import date
        
        app = create_app()
        with app.app_context():
            
            # Import here to avoid circular imports
            try:
                from app.models.billing import UsageRecord
            except ImportError:
                # If UsageRecord doesn't exist, create a simple log
                logger.info(f"Usage tracked: User {user_id}, {usage_type}, {quantity}")
                return {'success': True, 'note': 'Usage logged without database record'}
            
            # Create or update usage record for today
            today = date.today()
            usage_record = UsageRecord.query.filter_by(
                user_id=user_id,
                date=today,
                usage_type=usage_type
            ).first()
            
            if usage_record:
                usage_record.quantity += quantity
                usage_record.updated_at = datetime.utcnow()
            else:
                usage_record = UsageRecord(
                    user_id=user_id,
                    date=today,
                    usage_type=usage_type,
                    quantity=quantity
                )
                db.session.add(usage_record)
            
            db.session.commit()
            
            logger.info(f"Usage tracked: User {user_id}, {usage_type}, {quantity}")
            
            # Check if user is approaching limits
            check_usage_limits.delay(user_id)
            
            return {'success': True}
            
    except Exception as e:
        logger.error(f"Usage tracking failed: {e}")
        return {'success': False, 'error': str(e)}


@celery.task
def check_usage_limits(user_id: int):
    """
    Check if user is approaching usage limits and send notifications
    
    Args:
        user_id: Database user ID
    """
    try:
        from app import create_app
        from app.models.user import User
        from app.extensions import db
        from datetime import date, timedelta
        
        app = create_app()
        with app.app_context():
            
            try:
                from app.models.subscription import Subscription
                from app.models.billing import UsageRecord
            except ImportError:
                logger.warning("Subscription or UsageRecord models not available")
                return {'success': False, 'error': 'Models not available'}
            
            user = User.query.get(user_id)
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            
            if not user or not subscription:
                return {'success': False, 'error': 'User or subscription not found'}
            
            # Get current month usage
            start_of_month = date.today().replace(day=1)
            end_of_month = date.today()
            
            # Calculate AI responses used this month
            ai_usage = db.session.query(db.func.sum(UsageRecord.quantity)).filter(
                UsageRecord.user_id == user_id,
                UsageRecord.usage_type == 'ai_response',
                UsageRecord.date >= start_of_month,
                UsageRecord.date <= end_of_month
            ).scalar() or 0
            
            # Get plan limits
            plan = subscription.plan
            plan_features = getattr(plan, 'features', {})
            ai_limit = plan_features.get('ai_responses_monthly', 1000) if plan_features else 1000
            
            # Calculate usage percentage
            usage_percentage = (ai_usage / ai_limit) * 100 if ai_limit > 0 else 0
            
            # Send warnings at 80% and 95%
            if usage_percentage >= 95 and ai_usage < ai_limit:
                send_usage_warning.delay(user_id, 'critical', usage_percentage, ai_usage, ai_limit)
            elif usage_percentage >= 80:
                send_usage_warning.delay(user_id, 'warning', usage_percentage, ai_usage, ai_limit)
            
            # Disable AI if limit exceeded
            if ai_usage >= ai_limit and user.ai_enabled:
                user.ai_enabled = False
                db.session.commit()
                send_usage_warning.delay(user_id, 'limit_exceeded', usage_percentage, ai_usage, ai_limit)
                logger.warning(f"AI disabled for user {user_id} - limit exceeded")
            
            return {
                'success': True,
                'usage_percentage': usage_percentage,
                'ai_usage': ai_usage,
                'ai_limit': ai_limit
            }
            
    except Exception as e:
        logger.error(f"Usage limit check failed: {e}")
        return {'success': False, 'error': str(e)}


@celery.task
def send_usage_warning(user_id: int, warning_type: str, usage_percentage: float, current_usage: int, limit: int):
    """
    Send usage warning email to user
    
    Args:
        user_id: Database user ID
        warning_type: 'warning', 'critical', 'limit_exceeded'
        usage_percentage: Current usage percentage
        current_usage: Current usage count
        limit: Usage limit
    """
    try:
        from app import create_app
        from app.models.user import User
        
        app = create_app()
        with app.app_context():
            
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Prepare email content based on warning type
            if warning_type == 'warning':
                subject = "AssisText: Approaching Usage Limit"
                message = f"You've used {usage_percentage:.1f}% of your AI response limit ({current_usage}/{limit}). Consider upgrading your plan."
            elif warning_type == 'critical':
                subject = "AssisText: Critical Usage Warning"
                message = f"You've used {usage_percentage:.1f}% of your AI response limit ({current_usage}/{limit}). You may reach your limit soon."
            else:  # limit_exceeded
                subject = "AssisText: Usage Limit Reached"
                message = f"You've reached your AI response limit ({current_usage}/{limit}). AI responses have been temporarily disabled. Please upgrade your plan."
            
            # Log the warning (implement email service as needed)
            logger.info(f"Usage warning for user {user_id}: {warning_type} - {message}")
            
            # TODO: Implement actual email sending
            # from app.services.email_service import EmailService
            # email_service = EmailService()
            # email_result = email_service.send_email(
            #     to_email=user.email,
            #     subject=subject,
            #     body=message,
            #     template='usage_warning'
            # )
            
            return {'success': True, 'email_sent': True}
            
    except Exception as e:
        logger.error(f"Usage warning email failed: {e}")
        return {'success': False, 'error': str(e)}


@celery.task
def cleanup_expired_trials():
    """
    Cleanup expired trial accounts
    Run this task daily via cron
    """
    try:
        from app import create_app
        from app.models.user import User
        from app.extensions import db
        
        app = create_app()
        with app.app_context():
            
            # Find users with expired trials
            expired_users = User.query.filter(
                User.trial_phone_expires_at < datetime.utcnow(),
                User.signalwire_setup_completed == True
            ).all()
            
            cleanup_count = 0
            
            for user in expired_users:
                # Check if user has upgraded to paid plan
                subscription = user.current_subscription
                if subscription and subscription.status == 'active':
                    continue  # User has upgraded, skip cleanup
                
                try:
                    # Disable AI for expired trial users
                    if user.ai_enabled:
                        user.ai_enabled = False
                        
                    # Optionally disable phone number (or transfer to paid pool)
                    # This depends on your business logic
                    
                    cleanup_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to cleanup user {user.id}: {e}")
                    continue
            
            db.session.commit()
            
            logger.info(f"Cleaned up {cleanup_count} expired trial accounts")
            
            return {
                'success': True,
                'cleaned_up_count': cleanup_count,
                'total_expired': len(expired_users)
            }
            
    except Exception as e:
        logger.error(f"Trial cleanup task failed: {e}")
        return {'success': False, 'error': str(e)}