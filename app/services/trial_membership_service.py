# app/services/trial_membership_service.py
from flask import current_app
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging
import stripe

from app.extensions import db
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.billing import PaymentMethod
from app.services.signalwire_service import SignalWireService
from app.services.payment_processor import PaymentProcessor

logger = logging.getLogger(__name__)

class TrialMembershipService:
    """Service for managing 14-day trial memberships with SignalWire integration"""
    
    TRIAL_DURATION_DAYS = 14
    
    @classmethod
    def get_trial_status(cls, user_id: int) -> Dict[str, Any]:
        """Get comprehensive trial status for a user"""
        user = User.query.get(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Check for existing payment method
        payment_method = PaymentMethod.query.filter_by(
            user_id=user_id,
            status='active',
            is_default=True
        ).first()
        
        # Check for subscription
        subscription = Subscription.query.filter_by(
            user_id=user_id
        ).filter(
            Subscription.status.in_(['trialing', 'active', 'past_due'])
        ).first()
        
        trial_status = {
            'user_id': user_id,
            'has_payment_method': payment_method is not None,
            'payment_method_id': payment_method.id if payment_method else None,
            'has_subscription': subscription is not None,
            'subscription_status': subscription.status if subscription else None,
            'trial_started': user.trial_started_at is not None,
            'trial_active': cls._is_trial_active(user),
            'trial_expires_at': user.trial_expires_at.isoformat() if user.trial_expires_at else None,
            'signalwire_setup_complete': user.trial_signalwire_setup,
            'selected_phone_number': user.selected_phone_number,
            'can_start_trial': cls._can_start_trial(user, payment_method, subscription),
            'notifications': cls._get_trial_notifications(user_id)
        }
        
        if user.trial_expires_at:
            trial_status['days_remaining'] = max(0, (user.trial_expires_at.date() - datetime.utcnow().date()).days)
        
        return trial_status
    
    @classmethod
    def create_trial_notification(cls, user_id: int, notification_type: str, 
                                title: str, message: str, priority: str = 'medium',
                                expires_in_hours: Optional[int] = None) -> None:
        """Create a trial notification for the user"""
        from app.models.trial_notification import TrialNotification
        
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        notification = TrialNotification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            expires_at=expires_at
        )
        
        db.session.add(notification)
        db.session.commit()
        
        logger.info(f"Created trial notification for user {user_id}: {notification_type}")
    
    @classmethod
    def validate_payment_method_for_trial(cls, user_id: int, plan_id: int) -> Dict[str, Any]:
        """Validate that user has a payment method before starting trial"""
        user = User.query.get(user_id)
        plan = SubscriptionPlan.query.get(plan_id)
        
        if not user or not plan:
            return {'success': False, 'error': 'User or plan not found'}
        
        # Check if payment method is required for this plan
        if not plan.requires_payment_method:
            return {'success': True, 'payment_required': False}
        
        # Check for valid payment method
        payment_method = PaymentMethod.query.filter_by(
            user_id=user_id,
            status='active',
            is_default=True
        ).first()
        
        if not payment_method:
            cls.create_trial_notification(
                user_id=user_id,
                notification_type='payment_required',
                title='Payment Method Required',
                message=f'Please add a valid payment method to start your {cls.TRIAL_DURATION_DAYS}-day free trial. You will not be charged during the trial period.',
                priority='high'
            )
            return {
                'success': False, 
                'payment_required': True,
                'error': 'Valid payment method required to start trial'
            }
        
        # Validate payment method with Stripe
        try:
            stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
            stripe_pm = stripe.PaymentMethod.retrieve(payment_method.stripe_payment_method_id)
            
            if stripe_pm.type != 'card':
                return {'success': False, 'error': 'Credit card payment method required'}
                
            return {
                'success': True,
                'payment_required': True,
                'payment_method_id': payment_method.id,
                'payment_method_last4': stripe_pm.card.last4 if stripe_pm.card else None
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error validating payment method: {e}")
            return {'success': False, 'error': 'Invalid payment method'}
    
    @classmethod
    def start_trial_with_subscription(cls, user_id: int, plan_id: int) -> Dict[str, Any]:
        """Start trial by creating subscription with trial period"""
        try:
            user = User.query.get(user_id)
            plan = SubscriptionPlan.query.get(plan_id)
            
            if not user or not plan:
                return {'success': False, 'error': 'User or plan not found'}
            
            # Validate payment method first
            payment_validation = cls.validate_payment_method_for_trial(user_id, plan_id)
            if not payment_validation['success']:
                return payment_validation
            
            # Check if user already has an active subscription
            existing_subscription = Subscription.query.filter_by(
                user_id=user_id
            ).filter(
                Subscription.status.in_(['active', 'trialing'])
            ).first()
            
            if existing_subscription:
                return {'success': False, 'error': 'User already has an active subscription'}
            
            # Create Stripe subscription with trial
            payment_method = PaymentMethod.query.get(payment_validation['payment_method_id'])
            
            subscription_result = PaymentProcessor.create_subscription(
                user_id=str(user_id),
                plan_id=plan.stripe_price_id,
                payment_method_id=payment_method.stripe_payment_method_id,
                trial_days=cls.TRIAL_DURATION_DAYS
            )
            
            if not subscription_result['success']:
                return subscription_result
            
            # Create local subscription record
            trial_end = datetime.utcnow() + timedelta(days=cls.TRIAL_DURATION_DAYS)
            
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                status='trialing',
                billing_cycle='monthly',
                amount=plan.monthly_price,
                currency=plan.currency,
                current_period_start=datetime.utcnow(),
                current_period_end=trial_end,
                trial_end=trial_end,
                stripe_subscription_id=subscription_result['subscription_id'],
                stripe_customer_id=user.stripe_customer_id
            )
            
            db.session.add(subscription)
            
            # Update user trial status
            user.trial_started_at = datetime.utcnow()
            user.trial_expires_at = trial_end
            
            db.session.commit()
            
            # Create success notification
            cls.create_trial_notification(
                user_id=user_id,
                notification_type='trial_starting',
                title='Trial Started Successfully!',
                message=f'Your {cls.TRIAL_DURATION_DAYS}-day free trial has started. You can now set up your SignalWire phone number.',
                priority='medium'
            )
            
            logger.info(f"Started trial subscription for user {user_id}, plan {plan_id}")
            
            return {
                'success': True,
                'subscription_id': subscription.id,
                'trial_expires_at': trial_end.isoformat(),
                'next_step': 'signalwire_setup'
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error starting trial subscription: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def setup_signalwire_number(cls, user_id: int, selected_phone_number: str) -> Dict[str, Any]:
        """Set up SignalWire number for trial user"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Verify user has active trial
            if not cls._is_trial_active(user):
                return {'success': False, 'error': 'No active trial found'}
            
            # Create friendly name: username_userid_last4digits
            last_4_digits = selected_phone_number[-4:]
            friendly_name = f"{user.username}_{user.id}_{last_4_digits}"
            
            # Setup SignalWire subproject and purchase number
            signalwire_service = SignalWireService()
            
            # Create subproject
            subproject_result = signalwire_service.create_subproject(
                user_id=user_id,
                friendly_name=friendly_name
            )
            
            if not subproject_result['success']:
                return subproject_result
            
            # Purchase phone number
            purchase_result = signalwire_service.purchase_phone_number(
                subproject_sid=subproject_result['subproject_sid'],
                phone_number=selected_phone_number,
                webhook_url=f"{current_app.config['WEBHOOK_BASE_URL']}/api/webhooks/sms/{user_id}"
            )
            
            if not purchase_result['success']:
                return purchase_result
            
            # Update user record
            user.selected_phone_number = selected_phone_number
            user.signalwire_subproject_sid = subproject_result['subproject_sid']
            user.signalwire_friendly_name = friendly_name
            user.trial_signalwire_setup = True
            
            db.session.commit()
            
            # Create success notification
            cls.create_trial_notification(
                user_id=user_id,
                notification_type='signalwire_setup_complete',
                title='Phone Number Activated!',
                message=f'Your SignalWire number {selected_phone_number} is now active and ready to receive SMS messages.',
                priority='medium'
            )
            
            logger.info(f"Completed SignalWire setup for user {user_id}: {selected_phone_number}")
            
            return {
                'success': True,
                'phone_number': selected_phone_number,
                'subproject_sid': subproject_result['subproject_sid'],
                'friendly_name': friendly_name,
                'webhook_url': f"{current_app.config['WEBHOOK_BASE_URL']}/api/webhooks/sms/{user_id}"
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error setting up SignalWire number: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def _is_trial_active(cls, user: User) -> bool:
        """Check if user has an active trial"""
        if not user.trial_started_at or not user.trial_expires_at:
            return False
        return datetime.utcnow() < user.trial_expires_at
    
    @classmethod
    def _can_start_trial(cls, user: User, payment_method: Optional[PaymentMethod], 
                        subscription: Optional[Subscription]) -> bool:
        """Determine if user can start a trial"""
        # Can't start if already had a trial
        if user.trial_started_at:
            return False
        
        # Can't start if already has active subscription
        if subscription and subscription.status in ['active', 'trialing']:
            return False
        
        # For now, we'll allow trial without payment method but show warning
        return True
    
    @classmethod
    def _get_trial_notifications(cls, user_id: int) -> List[Dict[str, Any]]:
        """Get active trial notifications for user"""
        from app.models.trial_notification import TrialNotification
        
        notifications = TrialNotification.query.filter_by(
            user_id=user_id,
            is_dismissed=False
        ).filter(
            db.or_(
                TrialNotification.expires_at.is_(None),
                TrialNotification.expires_at > datetime.utcnow()
            )
        ).order_by(
            TrialNotification.priority.desc(),
            TrialNotification.created_at.desc()
        ).all()
        
        return [notification.to_dict() for notification in notifications]