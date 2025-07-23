"""
Trial Management Background Tasks
Handles 14-day trial lifecycle, phone number suspension, and notifications
"""

from celery import Celery
from datetime import datetime, timedelta
from app.extensions import db
from app.models.user import User
from app.services.signalwire_service import get_signalwire_service
import logging

# Initialize Celery (adjust this based on your Celery setup)
celery = Celery('trial_tasks')

@celery.task
def schedule_trial_expiry(user_id, trial_end_date_iso):
    """
    Schedule trial expiry for a user
    Called during registration to set up trial monitoring
    """
    try:
        user = User.query.get(user_id)
        if not user:
            logging.error(f"User {user_id} not found for trial scheduling")
            return {'success': False, 'error': 'User not found'}
        
        trial_end_date = datetime.fromisoformat(trial_end_date_iso.replace('Z', '+00:00'))
        
        # Schedule warning notifications
        warning_dates = [
            trial_end_date - timedelta(days=7),  # 7 days warning
            trial_end_date - timedelta(days=3),  # 3 days warning  
            trial_end_date - timedelta(days=1),  # 1 day warning
        ]
        
        for warning_date in warning_dates:
            if warning_date > datetime.utcnow():
                days_before = (trial_end_date - warning_date).days
                send_trial_warning.apply_async(
                    args=[user_id, days_before],
                    eta=warning_date
                )
        
        # Schedule trial expiry
        expire_trial.apply_async(
            args=[user_id],
            eta=trial_end_date
        )
        
        logging.info(f"✅ Scheduled trial expiry for user {user_id} at {trial_end_date}")
        
        return {
            'success': True,
            'user_id': user_id,
            'trial_end_date': trial_end_date_iso,
            'warnings_scheduled': len([d for d in warning_dates if d > datetime.utcnow()])
        }
        
    except Exception as e:
        logging.error(f"❌ Failed to schedule trial expiry for user {user_id}: {e}")
        return {'success': False, 'error': str(e)}

@celery.task
def send_trial_warning(user_id, days_remaining):
    """
    Send trial warning notification to user
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        if user.trial_status != 'active':
            return {'success': False, 'error': 'Trial not active'}
        
        # Update user's remaining days
        user.trial_days_remaining = days_remaining
        db.session.commit()
        
        # Send warning email
        from app.tasks.email_tasks import send_trial_warning_email
        send_trial_warning_email.delay(
            user_id=user_id,
            email=user.email,
            first_name=user.first_name,
            days_remaining=days_remaining,
            phone_number=user.signalwire_phone_number
        )
        
        logging.info(f"✅ Sent {days_remaining}-day trial warning to user {user_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'days_remaining': days_remaining,
            'warning_sent': True
        }
        
    except Exception as e:
        logging.error(f"❌ Failed to send trial warning to user {user_id}: {e}")
        return {'success': False, 'error': str(e)}

@celery.task
def expire_trial(user_id):
    """
    Expire user trial and suspend their phone number
    Called automatically when trial period ends
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        if user.trial_status != 'active':
            logging.info(f"Trial for user {user_id} already expired or inactive")
            return {'success': False, 'error': 'Trial already expired'}
        
        logging.info(f"🔒 Expiring trial for user {user_id}")
        
        # Step 1: Suspend SignalWire phone number
        signalwire_result = None
        if user.signalwire_phone_sid:
            signalwire = get_signalwire_service()
            signalwire_result = signalwire.suspend_phone_number(
                phone_number_sid=user.signalwire_phone_sid,
                reason="trial_expired"
            )
            
            if signalwire_result['success']:
                user.signalwire_number_active = False
                logging.info(f"✅ Suspended phone number {user.signalwire_phone_number}")
            else:
                logging.error(f"❌ Failed to suspend phone number: {signalwire_result['error']}")
        
        # Step 2: Update user trial status
        user.trial_status = 'expired'
        user.trial_days_remaining = 0
        user.trial_expired_at = datetime.utcnow()
        user.is_trial = False
        
        db.session.commit()
        
        # Step 3: Send trial expired notification
        from app.tasks.email_tasks import send_trial_expired_email
        send_trial_expired_email.delay(
            user_id=user_id,
            email=user.email,
            first_name=user.first_name,
            phone_number=user.signalwire_phone_number
        )
        
        logging.info(f"✅ Trial expired for user {user_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'trial_expired_at': user.trial_expired_at.isoformat(),
            'phone_number_suspended': signalwire_result['success'] if signalwire_result else False,
            'notification_sent': True
        }
        
    except Exception as e:
        logging.error(f"❌ Failed to expire trial for user {user_id}: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}

@celery.task
def reactivate_user_after_subscription(user_id, subscription_plan_id):
    """
    Reactivate user's phone number after they subscribe
    Called when user completes payment after trial
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        logging.info(f"🚀 Reactivating user {user_id} after subscription")
        
        # Step 1: Reactivate SignalWire phone number
        signalwire_result = None
        if user.signalwire_phone_sid:
            signalwire = get_signalwire_service()
            signalwire_result = signalwire.reactivate_phone_number(
                phone_number_sid=user.signalwire_phone_sid,
                friendly_name=f"{user.first_name} {user.last_name} - Active"
            )
            
            if signalwire_result['success']:
                user.signalwire_number_active = True
                logging.info(f"✅ Reactivated phone number {user.signalwire_phone_number}")
            else:
                logging.error(f"❌ Failed to reactivate phone number: {signalwire_result['error']}")
        
        # Step 2: Update user status
        user.trial_status = 'converted'
        user.is_trial = False
        user.subscription_active = True
        user.subscription_plan_id = subscription_plan_id
        user.subscription_activated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Step 3: Send welcome to paid plan email
        from app.tasks.email_tasks import send_subscription_welcome_email
        send_subscription_welcome_email.delay(
            user_id=user_id,
            email=user.email,
            first_name=user.first_name,
            phone_number=user.signalwire_phone_number,
            plan_id=subscription_plan_id
        )
        
        logging.info(f"✅ User {user_id} reactivated with subscription {subscription_plan_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'subscription_plan_id': subscription_plan_id,
            'phone_number_reactivated': signalwire_result['success'] if signalwire_result else False,
            'subscription_activated_at': user.subscription_activated_at.isoformat()
        }
        
    except Exception as e:
        logging.error(f"❌ Failed to reactivate user {user_id}: {e}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}

@celery.task
def check_trial_status_daily():
    """
    Daily task to check trial statuses and handle any missed expirations
    Run this as a scheduled task via Celery Beat
    """
    try:
        # Find trials that should have expired but are still active
        expired_trials = User.query.filter(
            User.is_trial == True,
            User.trial_status == 'active',
            User.trial_end_date < datetime.utcnow()
        ).all()
        
        results = []
        for user in expired_trials:
            logging.warning(f"⚠️ Found missed trial expiry for user {user.id}")
            result = expire_trial.delay(user.id)
            results.append({
                'user_id': user.id,
                'task_id': result.id,
                'action': 'expired_missed_trial'
            })
        
        # Update trial days remaining for active trials
        active_trials = User.query.filter(
            User.is_trial == True,
            User.trial_status == 'active',
            User.trial_end_date > datetime.utcnow()
        ).all()
        
        for user in active_trials:
            remaining_time = user.trial_end_date - datetime.utcnow()
            days_remaining = max(0, remaining_time.days)
            
            if user.trial_days_remaining != days_remaining:
                user.trial_days_remaining = days_remaining
                db.session.commit()
        
        logging.info(f"✅ Daily trial check complete: {len(expired_trials)} expired, {len(active_trials)} active")
        
        return {
            'success': True,
            'expired_trials': len(expired_trials),
            'active_trials': len(active_trials),
            'actions_taken': results
        }
        
    except Exception as e:
        logging.error(f"❌ Daily trial check failed: {e}")
        return {'success': False, 'error': str(e)}

@celery.task
def extend_trial(user_id, additional_days):
    """
    Extend a user's trial period (admin function)
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        if not user.is_trial:
            return {'success': False, 'error': 'User is not on trial'}
        
        # Extend trial end date
        old_end_date = user.trial_end_date
        user.trial_end_date = user.trial_end_date + timedelta(days=additional_days)
        user.trial_days_remaining = (user.trial_end_date - datetime.utcnow()).days
        
        db.session.commit()
        
        logging.info(f"✅ Extended trial for user {user_id} by {additional_days} days")
        
        return {
            'success': True,
            'user_id': user_id,
            'additional_days': additional_days,
            'old_end_date': old_end_date.isoformat(),
            'new_end_date': user.trial_end_date.isoformat(),
            'days_remaining': user.trial_days_remaining
        }
        
    except Exception as e:
        logging.error(f"❌ Failed to extend trial for user {user_id}: {e}")
        return {'success': False, 'error': str(e)}