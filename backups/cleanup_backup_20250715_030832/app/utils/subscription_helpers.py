# app/utils/subscription_helpers.py
from datetime import datetime, timedelta
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User

def is_trial_expired(user: User) -> bool:
    """Check if user's trial has expired"""
    if not user.trial_phone_expires_at:
        return False
    
    return datetime.utcnow() > user.trial_phone_expires_at

def calculate_trial_end_date(days: int = 14) -> datetime:
    """Calculate trial end date"""
    return datetime.utcnow() + timedelta(days=days)

def get_user_subscription_status(user_id: int) -> Dict[str, Any]:
    """Get comprehensive subscription status for user"""
    subscription = Subscription.query.filter_by(user_id=user_id).first()
    user = User.query.get(user_id)
    
    if not subscription:
        return {
            'has_subscription': False,
            'status': 'none',
            'is_trial': False,
            'trial_expired': False
        }
    
    trial_expired = is_trial_expired(user) if user else False
    
    return {
        'has_subscription': True,
        'status': subscription.status,
        'is_trial': subscription.status == 'trialing',
        'trial_expired': trial_expired,
        'plan_name': subscription.plan.name if subscription.plan else None,
        'current_period_end': subscription.current_period_end,
        'trial_end': subscription.trial_end
    }