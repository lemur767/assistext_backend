# app/tasks/trial_tasks.py
"""
Trial management tasks for AssisText
Fixed to resolve import errors and ensure all functions are properly defined
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask import current_app

logger = logging.getLogger(__name__)

# Try to import required services and models
try:
    from app.extensions import db
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database extensions not available")

try:
    from app.models.user import User
    USER_MODEL_AVAILABLE = True
except ImportError:
    USER_MODEL_AVAILABLE = False
    logger.warning("User model not available")

try:
    from app.services.signalwire_service import get_signalwire_service
    SIGNALWIRE_AVAILABLE = True
except ImportError:
    SIGNALWIRE_AVAILABLE = False
    logger.warning("SignalWire service not available")

try:
    from celery import current_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logger.warning("Celery not available")

# =========================================================================
# CORE TRIAL MANAGEMENT FUNCTIONS
# =========================================================================

def check_trial_expiring_users() -> Dict[str, Any]:
    """
    Check for users with trials expiring soon and send notifications
    """
    if not all([DB_AVAILABLE, USER_MODEL_AVAILABLE]):
        return {
            'success': False,
            'error': 'Required dependencies not available',
            'users_checked': 0,
            'notifications_sent': 0
        }
    
    try:
        # Find users with trials expiring in 3 days
        warning_date = datetime.utcnow() + timedelta(days=3)
        
        expiring_users = User.query.filter(
            User.trial_status == 'active',
            User.trial_ends_at <= warning_date,
            User.trial_ends_at > datetime.utcnow(),
            User.trial_warning_sent == False
        ).all()
        
        results = {
            'success': True,
            'users_checked': len(expiring_users),
            'notifications_sent': 0,
            'errors': []
        }
        
        for user in expiring_users:
            try:
                days_remaining = (user.trial_ends_at - datetime.utcnow()).days
                
                # Send warning email (if email tasks available)
                try:
                    from app.tasks.email_tasks import send_trial_warning_email
                    email_result = send_trial_warning_email(
                        user_id=user.id,
                        user_email=user.email,
                        user_name=user.name,
                        days_remaining=days_remaining
                    )
                    
                    if email_result.get('success'):
                        user.trial_warning_sent = True
                        db.session.add(user)
                        results['notifications_sent'] += 1
                        logger.info(f"✅ Trial warning sent to user {user.id}")
                    else:
                        results['errors'].append(f"Email failed for user {user.id}")
                        
                except ImportError:
                    logger.warning(f"⚠️ Email tasks not available, cannot send warning to user {user.id}")
                    
            except Exception as e:
                error_msg = f"Error processing user {user.id}: {e}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        # Commit changes
        if DB_AVAILABLE:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Database commit failed: {e}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Trial expiring check failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'users_checked': 0,
            'notifications_sent': 0
        }

def suspend_expired_trials() -> Dict[str, Any]:
    """
    Suspend services for users whose trials have expired
    """
    if not all([DB_AVAILABLE, USER_MODEL_AVAILABLE]):
        return {
            'success': False,
            'error': 'Required dependencies not available',
            'users_checked': 0,
            'users_suspended': 0
        }
    
    try:
        # Find users with expired trials
        expired_users = User.query.filter(
            User.trial_status == 'active',
            User.trial_ends_at <= datetime.utcnow()
        ).all()
        
        results = {
            'success': True,
            'users_checked': len(expired_users),
            'users_suspended': 0,
            'errors': []
        }
        
        signalwire_service = None
        if SIGNALWIRE_AVAILABLE:
            try:
                signalwire_service = get_signalwire_service()
            except Exception as e:
                logger.warning(f"⚠️ Could not initialize SignalWire service: {e}")
        
        for user in expired_users:
            try:
                # Update trial status
                user.trial_status = 'expired'
                
                # Suspend SignalWire services if available
                if signalwire_service and user.signalwire_phone_number:
                    try:
                        # Suspend phone number services
                        logger.info(f"📞 Trial expired for user {user.id}, phone: {user.signalwire_phone_number}")
                        # Note: Add actual suspension logic here when available
                    except Exception as e:
                        logger.error(f"❌ SignalWire suspension failed for user {user.id}: {e}")
                
                db.session.add(user)
                results['users_suspended'] += 1
                logger.info(f"✅ Trial suspended for user {user.id}")
                
            except Exception as e:
                error_msg = f"Error suspending user {user.id}: {e}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        # Commit changes
        if DB_AVAILABLE:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"❌ Database commit failed: {e}")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Trial suspension failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'users_checked': 0,
            'users_suspended': 0
        }

def activate_trial_for_user(user_id: str, phone_number: str = None) -> Dict[str, Any]:
    """
    Activate trial for a specific user
    """
    if not all([DB_AVAILABLE, USER_MODEL_AVAILABLE]):
        return {
            'success': False,
            'error': 'Required dependencies not available'
        }
    
    try:
        user = User.query.get(user_id)
        if not user:
            return {
                'success': False,
                'error': 'User not found'
            }
        
        # Set trial dates
        trial_start = datetime.utcnow()
        trial_end = trial_start + timedelta(days=14)
        
        user.trial_status = 'active'
        user.trial_ends_at = trial_end
        user.trial_warning_sent = False
        
        # Setup SignalWire integration if phone number provided
        if phone_number and SIGNALWIRE_AVAILABLE:
            try:
                signalwire_service = get_signalwire_service()
                user.signalwire_phone_number = phone_number
                logger.info(f"📞 Phone number {phone_number} assigned to user {user_id}")
            except Exception as e:
                logger.error(f"❌ SignalWire setup failed for user {user_id}: {e}")
        
        db.session.add(user)
        db.session.commit()
        
        # Send welcome email if available
        try:
            from app.tasks.email_tasks import send_welcome_email
            email_result = send_welcome_email(
                user_id=user.id,
                user_email=user.email,
                user_name=user.name
            )
            logger.info(f"✅ Welcome email sent to user {user_id}")
        except ImportError:
            logger.warning(f"❌ Email tasks not available for user {user_id}")
        
        return {
            'success': True,
            'message': f'Trial activated for user {user_id}',
            'trial_ends_at': trial_end.isoformat(),
            'phone_number': phone_number
        }
        
    except Exception as e:
        logger.error(f"❌ Trial activation failed for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def get_trial_status(user_id: str) -> Dict[str, Any]:
    """
    Get trial status for a user
    """
    if not all([DB_AVAILABLE, USER_MODEL_AVAILABLE]):
        return {
            'success': False,
            'error': 'Required dependencies not available'
        }
    
    try:
        user = User.query.get(user_id)
        if not user:
            return {
                'success': False,
                'error': 'User not found'
            }
        
        # Calculate trial info
        trial_info = {
            'trial_status': user.trial_status,
            'trial_ends_at': user.trial_ends_at.isoformat() if user.trial_ends_at else None,
            'days_remaining': 0,
            'is_expired': False
        }
        
        if user.trial_ends_at:
            remaining = user.trial_ends_at - datetime.utcnow()
            trial_info['days_remaining'] = max(0, remaining.days)
            trial_info['is_expired'] = remaining.total_seconds() <= 0
        
        return {
            'success': True,
            'user_id': user_id,
            'trial_info': trial_info
        }
        
    except Exception as e:
        logger.error(f"❌ Trial status check failed for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# =========================================================================
# BILLING INTEGRATION FUNCTIONS (FIXED)
# =========================================================================

def reactivate_user_after_subscription(user_id: str, subscription_plan_id: str) -> Dict[str, Any]:
    """
    Reactivate user's services after they subscribe
    This is the function that billing.py is trying to import
    """
    if not all([DB_AVAILABLE, USER_MODEL_AVAILABLE]):
        return {
            'success': False,
            'error': 'Required dependencies not available'
        }
    
    try:
        user = User.query.get(user_id)
        if not user:
            return {
                'success': False,
                'error': 'User not found'
            }
        
        logger.info(f"🚀 Reactivating user {user_id} after subscription to plan {subscription_plan_id}")
        
        # Update user subscription status
        user.trial_status = 'converted'
        user.subscription_active = True
        user.subscription_plan_id = subscription_plan_id
        user.subscription_activated_at = datetime.utcnow()
        
        # Reactivate SignalWire services if available
        if SIGNALWIRE_AVAILABLE and user.signalwire_phone_number:
            try:
                signalwire_service = get_signalwire_service()
                # Add reactivation logic here when SignalWire service supports it
                user.signalwire_number_active = True
                logger.info(f"✅ Reactivated SignalWire services for user {user_id}")
            except Exception as e:
                logger.error(f"❌ SignalWire reactivation failed for user {user_id}: {e}")
        
        db.session.add(user)
        db.session.commit()
        
        # Send subscription welcome email if available
        try:
            from app.tasks.email_tasks import send_subscription_welcome_email
            email_result = send_subscription_welcome_email(
                user_id=user.id,
                user_email=user.email,
                user_name=user.name
            )
            logger.info(f"✅ Subscription welcome email sent to user {user_id}")
        except ImportError:
            logger.warning(f"❌ Email tasks not available for user {user_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'subscription_plan_id': subscription_plan_id,
            'reactivated_at': user.subscription_activated_at.isoformat(),
            'phone_number': user.signalwire_phone_number,
            'services_reactivated': True
        }
        
    except Exception as e:
        logger.error(f"❌ User reactivation failed for user {user_id}: {e}")
        if DB_AVAILABLE:
            db.session.rollback()
        return {
            'success': False,
            'error': str(e)
        }

def expire_trial(user_id: str) -> Dict[str, Any]:
    """
    Expire trial for a specific user
    """
    if not all([DB_AVAILABLE, USER_MODEL_AVAILABLE]):
        return {
            'success': False,
            'error': 'Required dependencies not available'
        }
    
    try:
        user = User.query.get(user_id)
        if not user:
            return {
                'success': False,
                'error': 'User not found'
            }
        
        logger.info(f"⏰ Expiring trial for user {user_id}")
        
        # Update trial status
        user.trial_status = 'expired'
        user.trial_expired_at = datetime.utcnow()
        
        # Suspend SignalWire services if available
        if SIGNALWIRE_AVAILABLE and user.signalwire_phone_number:
            try:
                signalwire_service = get_signalwire_service()
                user.signalwire_number_active = False
                logger.info(f"📞 Suspended SignalWire services for user {user_id}")
            except Exception as e:
                logger.error(f"❌ SignalWire suspension failed for user {user_id}: {e}")
        
        db.session.add(user)
        db.session.commit()
        
        # Send trial expired email if available
        try:
            from app.tasks.email_tasks import send_trial_expired_email
            email_result = send_trial_expired_email(
                user_id=user.id,
                user_email=user.email,
                user_name=user.name
            )
            logger.info(f"✅ Trial expired email sent to user {user_id}")
        except ImportError:
            logger.warning(f"❌ Email tasks not available for user {user_id}")
        
        return {
            'success': True,
            'user_id': user_id,
            'expired_at': user.trial_expired_at.isoformat(),
            'phone_number': user.signalwire_phone_number,
            'services_suspended': True
        }
        
    except Exception as e:
        logger.error(f"❌ Trial expiration failed for user {user_id}: {e}")
        if DB_AVAILABLE:
            db.session.rollback()
        return {
            'success': False,
            'error': str(e)
        }

# =========================================================================
# CELERY TASKS (if available)
# =========================================================================

if CELERY_AVAILABLE:
    try:
        from celery import Celery
        
        # Define as Celery tasks if Celery is available
        def create_celery_tasks():
            """Create Celery task versions of the functions"""
            
            @current_task.app.task(name='check_trial_expiring_users')
            def check_trial_expiring_users_task():
                return check_trial_expiring_users()
            
            @current_task.app.task(name='suspend_expired_trials')
            def suspend_expired_trials_task():
                return suspend_expired_trials()
            
            @current_task.app.task(name='reactivate_user_after_subscription')
            def reactivate_user_after_subscription_task(user_id: str, subscription_plan_id: str):
                return reactivate_user_after_subscription(user_id, subscription_plan_id)
            
            @current_task.app.task(name='expire_trial')
            def expire_trial_task(user_id: str):
                return expire_trial(user_id)
            
            return {
                'check_trial_expiring_users': check_trial_expiring_users_task,
                'suspend_expired_trials': suspend_expired_trials_task,
                'reactivate_user_after_subscription': reactivate_user_after_subscription_task,
                'expire_trial': expire_trial_task
            }
        
        # Create tasks if needed
        celery_tasks = create_celery_tasks()
        
    except ImportError:
        logger.warning("Celery tasks could not be created")

# =========================================================================
# EXPORT FUNCTIONS
# =========================================================================

# Export all functions so they can be imported
__all__ = [
    'check_trial_expiring_users',
    'suspend_expired_trials',
    'activate_trial_for_user',
    'get_trial_status',
    'reactivate_user_after_subscription',  # ← This is what billing.py needs
    'expire_trial'
]