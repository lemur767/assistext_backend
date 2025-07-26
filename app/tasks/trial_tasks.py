# app/tasks/trial_tasks.py
"""
Trial management tasks for AssisText
Fixed to handle missing services gracefully
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from flask import current_app

logger = logging.getLogger(__name__)

# Try to import required services, handle gracefully if missing
try:
    from app.services.signalwire_service import SignalWireService
    SIGNALWIRE_AVAILABLE = True
except ImportError:
    SIGNALWIRE_AVAILABLE = False
    logger.warning("SignalWire service not available")

try:
    from app.tasks.email_tasks import send_trial_warning_email, send_welcome_email
    EMAIL_TASKS_AVAILABLE = True
except ImportError:
    EMAIL_TASKS_AVAILABLE = False
    logger.warning("Email tasks not available")

def check_trial_expiring_users() -> Dict[str, Any]:
    """
    Check for users with trials expiring soon and send notifications
    """
    try:
        from app.models.user import User
        from app.extensions import db
        
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
                
                if EMAIL_TASKS_AVAILABLE:
                    # Send warning email
                    email_result = send_trial_warning_email(
                        user_id=user.id,
                        user_email=user.email,
                        user_name=user.name,
                        days_remaining=days_remaining
                    )
                    
                    if email_result.get('success'):
                        # Mark warning as sent
                        user.trial_warning_sent = True
                        db.session.add(user)
                        results['notifications_sent'] += 1
                        logger.info(f"✅ Trial warning sent to user {user.id}")
                    else:
                        results['errors'].append(f"Email failed for user {user.id}: {email_result.get('error')}")
                else:
                    logger.warning(f"⚠️ Email not available, cannot send trial warning to user {user.id}")
                    
            except Exception as e:
                error_msg = f"Error processing user {user.id}: {e}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        # Commit changes
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
    try:
        from app.models.user import User
        from app.extensions import db
        
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
        
        signalwire_service = SignalWireService()
        if not SIGNALWIRE_AVAILABLE:
            logger.warning("⚠️ SignalWire service not available, skipping phone number suspension")
            return results
        
        for user in expired_users:
            try:
                # Update trial status
                user.trial_status = 'expired'
                
                # Suspend SignalWire services if available
                if signalwire_service and user.signalwire_phone_number:
                    try:
                        # You can implement phone number suspension logic here
                        # For now, we'll just log it
                        logger.info(f"📞 Trial expired for user {user.id}, phone: {user.signalwire_phone_number}")
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
    try:
        from app.models.user import User
        from app.extensions import db
        
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
                signalwire_service = SignalWireService()
                if not signalwire_service:
                    raise ImportError("SignalWire service not available")   
                # You can implement phone number setup logic here
                user.signalwire_phone_number = phone_number
                logger.info(f"📞 Phone number {phone_number} assigned to user {user_id}")
            except Exception as e:
                logger.error(f"❌ SignalWire setup failed for user {user_id}: {e}")
        
        db.session.add(user)
        db.session.commit()
        
        # Send welcome email if available
        if EMAIL_TASKS_AVAILABLE:
            try:
                email_result = send_welcome_email(
                    user_id=user.id,
                    user_email=user.email,
                    user_name=user.name
                )
                logger.info(f"✅ Welcome email sent to user {user_id}")
            except Exception as e:
                logger.error(f"❌ Welcome email failed for user {user_id}: {e}")
        
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
    try:
        from app.models.user import User
        
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

# Celery tasks (if available)
try:
    from celery import Celery
    
    # These would be actual Celery tasks in a full implementation
    def schedule_trial_checks():
        """Schedule trial checks to run periodically"""
        logger.info("Running scheduled trial checks...")
        
        # Check for expiring trials
        expiring_result = check_trial_expiring_users()
        logger.info(f"Trial expiring check: {expiring_result}")
        
        # Suspend expired trials
        suspension_result = suspend_expired_trials()
        logger.info(f"Trial suspension: {suspension_result}")
        
        return {
            'expiring_check': expiring_result,
            'suspension_check': suspension_result
        }
        
except ImportError:
    logger.warning("Celery not available for trial task scheduling")

# Export functions
__all__ = [
    'check_trial_expiring_users',
    'suspend_expired_trials',
    'activate_trial_for_user',
    'get_trial_status'
]