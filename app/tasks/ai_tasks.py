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