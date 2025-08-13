import os
import logging
import stripe
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    User, Subscription, SubscriptionPlan, PaymentMethod, 
    Invoice, UsageRecord
)


class StripeConfig:
    """Stripe configuration management"""
    
    def __init__(self):
        self.secret_key = os.getenv('STRIPE_SECRET_KEY')
        self.public_key = os.getenv('STRIPE_PUBLIC_KEY')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        if not self.secret_key:
            raise ValueError("Missing STRIPE_SECRET_KEY environment variable")
        
        stripe.api_key = self.secret_key


class BillingService:
    """
    Complete billing service with Stripe integration
    Handles subscriptions, payments, and usage tracking
    """
    
    def __init__(self):
        self.config = StripeConfig()
        self.logger = logging.getLogger(__name__)
    
    # =============================================================================
    # CUSTOMER MANAGEMENT
    # =============================================================================
    
    def create_stripe_customer(self, user_id: int) -> Dict[str, Any]:
        """
        Create Stripe customer for user
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Check if customer already exists
            if hasattr(user, 'stripe_customer_id') and user.stripe_customer_id:
                try:
                    customer = stripe.Customer.retrieve(user.stripe_customer_id)
                    if customer.deleted:
                        # Customer was deleted, create new one
                        pass
                    else:
                        return {
                            'success': True,
                            'customer_id': user.stripe_customer_id,
                            'existing': True
                        }
                except stripe.error.InvalidRequestError:
                    # Customer doesn't exist, create new one
                    pass
            
            # Create new Stripe customer
            customer_data = {
                'email': user.email,
                'name': f"{user.first_name or ''} {user.last_name or ''}".strip(),
                'metadata': {
                    'user_id': str(user.id),
                    'username': user.username
                }
            }
            
            if user.phone_number:
                customer_data['phone'] = user.phone_number
            
            customer = stripe.Customer.create(**customer_data)
            
            # Store customer ID in user model
            user.stripe_customer_id = customer.id
            db.session.commit()
            
            self.logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
            
            return {
                'success': True,
                'customer_id': customer.id,
                'existing': False
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Create Stripe customer error: {str(e)}")
            return {'success': False, 'error': 'Failed to create customer'}
    
    def get_stripe_customer(self, user_id: int) -> Dict[str, Any]:
        """
        Get or create Stripe customer for user
        """
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}
        
        if hasattr(user, 'stripe_customer_id') and user.stripe_customer_id:
            try:
                customer = stripe.Customer.retrieve(user.stripe_customer_id)
                return {
                    'success': True,
                    'customer': customer
                }
            except stripe.error.InvalidRequestError:
                # Customer doesn't exist, create new one
                pass
        
        # Create new customer
        return self.create_stripe_customer(user_id)
    
    # =============================================================================
    # PAYMENT METHOD MANAGEMENT
    # =============================================================================
    
    def add_payment_method(self, user_id: int, payment_method_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add payment method for user
        """
        try:
            # Get or create Stripe customer
            customer_result = self.get_stripe_customer(user_id)
            if not customer_result['success']:
                return customer_result
            
            customer_id = customer_result['customer'].id
            
            # Attach payment method to customer
            payment_method = stripe.PaymentMethod.attach(
                payment_method_data['payment_method_id'],
                customer=customer_id
            )
            
            # Store payment method in database
            payment_method_record = PaymentMethod(
                user_id=user_id,
                type=payment_method.type,
                stripe_payment_method_id=payment_method.id,
                is_default=payment_method_data.get('is_default', False)
            )
            
            # Add card details if it's a card
            if payment_method.type == 'card':
                card = payment_method.card
                payment_method_record.card_brand = card.brand
                payment_method_record.card_last4 = card.last4
                payment_method_record.card_exp_month = card.exp_month
                payment_method_record.card_exp_year = card.exp_year
            
            # Set as default if requested or if it's the first payment method
            if payment_method_data.get('is_default', False) or not PaymentMethod.query.filter_by(user_id=user_id).first():
                # Remove default flag from other payment methods
                PaymentMethod.query.filter_by(user_id=user_id, is_default=True).update({'is_default': False})
                payment_method_record.is_default = True
            
            db.session.add(payment_method_record)
            db.session.commit()
            
            return {
                'success': True,
                'payment_method': payment_method_record.to_dict()
            }
            
        except stripe.error.StripeError as e:
            self.logger.error(f"Stripe payment method error: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Add payment method error: {str(e)}")
            return {'success': False, 'error': 'Failed to add payment method'}
    
    def get_payment_methods(self, user_id: int) -> Dict[str, Any]:
        """
        Get user's payment methods
        """
        try:
            payment_methods = PaymentMethod.query.filter_by(
                user_id=user_id,
                status='active'
            ).order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc()).all()
            
            return {
                'success': True,
                'payment_methods': [pm.to_dict() for pm in payment_methods]
            }
            
        except Exception as e:
            self.logger.error(f"Get payment methods error: {str(e)}")
            return {'success': False, 'error': 'Failed to fetch payment methods'}
    
    def set_default_payment_method(self, user_id: int, payment_method_id: int) -> Dict[str, Any]:
        """
        Set default payment method for user
        """
        try:
            # Remove default flag from all payment methods
            PaymentMethod.query.filter_by(user_id=user_id, is_default=True).update({'is_default': False})
            
            # Set new default
            payment_method = PaymentMethod.query.filter_by(
                id=payment_method_id,
                user_id=user_id
            ).first()
            
            if not payment_method:
                return {'success': False, 'error': 'Payment method not found'}
            
            payment_method.is_default = True
            db.session.commit()
            
            return {
                'success': True,
                'payment_method': payment_method.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Set default payment method error: {str(e)}")
            return {'success': False, 'error': 'Failed to set default payment method'}
    
    # =============================================================================
    # SUBSCRIPTION MANAGEMENT
    # =============================================================================
    
    def create_subscription(self, user_id: int, plan_id: int, 
                          billing_cycle: str = 'monthly') -> Dict[str, Any]:
        """
        Create new subscription for user
        """
        try:
            user = User.query.get(user_id)
            plan = SubscriptionPlan.query.get(plan_id)
            
            if not user or not plan:
                return {'success': False, 'error': 'User or plan not found'}
            
            # Check if user already has active subscription
            existing_subscription = Subscription.query.filter_by(
                user_id=user_id,
                status='active'
            ).first()
            
            if existing_subscription:
                return {'success': False, 'error': 'User already has active subscription'}
            
            # Get Stripe customer
            customer_result = self.get_stripe_customer(user_id)
            if not customer_result['success']:
                return customer_result
            
            customer_id = customer_result['customer'].id
            
            # Get default payment method
            default_pm = PaymentMethod.query.filter_by(
                user_id=user_id,
                is_default=True,
                status='active'
            ).first()
            
            if not default_pm:
                return {'success': False, 'error': 'No payment method available'}
            
            # Determine price based on billing cycle
            price_amount = plan.monthly_price if billing_cycle == 'monthly' else plan.annual_price
            stripe_price_id = plan.stripe_price_id_monthly if billing_cycle == 'monthly' else plan.stripe_price_id_annual
            
            if not stripe_price_id:
                return {'success': False, 'error': 'Plan not configured for this billing cycle'}
            
            # Create Stripe subscription
            stripe_subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': stripe_price_id}],
                default_payment_method=default_pm.stripe_payment_method_id,
                metadata={
                    'user_id': str(user_id),
                    'plan_id': str(plan_id)
                }
            )
            
            # Create local subscription record
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                status=stripe_subscription.status,
                billing_cycle=billing_cycle,
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                amount=price_amount,
                stripe_subscription_id=stripe_subscription.id,
                stripe_customer_id=customer_id
            )
            
            # Handle trial period
            if stripe_subscription.trial_end:
                subscription.trial_end = datetime.fromtimestamp(stripe_subscription.trial_end)
            
            db.session.add(subscription)
            db.session.commit()
            
            self.logger.info(f"Created subscription {subscription.id} for user {user_id}")
            
            return {
                'success': True,
                'subscription': subscription.to_dict()
            }
            
        except stripe.error.StripeError as e:
            db.session.rollback()
            self.logger.error(f"Stripe subscription error: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Create subscription error: {str(e)}")
            return {'success': False, 'error': 'Failed to create subscription'}
    
    def create_trial_subscription(self, user_id: int, plan_id: int) -> Dict[str, Any]:
        """
        Create trial subscription for user
        """
        try:
            user = User.query.get(user_id)
            plan = SubscriptionPlan.query.get(plan_id)
            
            if not user or not plan:
                return {'success': False, 'error': 'User or plan not found'}
            
            # Create trial subscription (local only, no Stripe subscription yet)
            trial_end = datetime.utcnow() + timedelta(days=plan.trial_period_days or 14)
            
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                status='trialing',
                billing_cycle='monthly',  # Default to monthly
                current_period_start=datetime.utcnow(),
                current_period_end=trial_end,
                trial_end=trial_end,
                amount=plan.monthly_price
            )
            
            db.session.add(subscription)
            db.session.commit()
            
            return {
                'success': True,
                'subscription': subscription.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Create trial subscription error: {str(e)}")
            return {'success': False, 'error': 'Failed to create trial subscription'}
    
    def cancel_subscription(self, user_id: int, reason: str = None) -> Dict[str, Any]:
        """
        Cancel user's subscription
        """
        try:
            subscription = Subscription.query.filter_by(
                user_id=user_id,
                status='active'
            ).first()
            
            if not subscription:
                return {'success': False, 'error': 'No active subscription found'}
            
            # Cancel Stripe subscription if it exists
            if subscription.stripe_subscription_id:
                stripe_subscription = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True,
                    metadata={'cancellation_reason': reason or 'User requested'}
                )
                
                subscription.status = 'canceled'
                subscription.canceled_at = datetime.utcnow()
            else:
                # Trial subscription, cancel immediately
                subscription.status = 'canceled'
                subscription.canceled_at = datetime.utcnow()
                subscription.ended_at = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'success': True,
                'subscription': subscription.to_dict(),
                'message': 'Subscription canceled successfully'
            }
            
        except stripe.error.StripeError as e:
            self.logger.error(f"Stripe cancellation error: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Cancel subscription error: {str(e)}")
            return {'success': False, 'error': 'Failed to cancel subscription'}
    
    def get_user_subscription(self, user_id: int) -> Dict[str, Any]:
        """
        Get user's current subscription
        """
        try:
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            
            if not subscription:
                return {
                    'success': True,
                    'subscription': None,
                    'has_subscription': False
                }
            
            return {
                'success': True,
                'subscription': subscription.to_dict(),
                'has_subscription': True
            }
            
        except Exception as e:
            self.logger.error(f"Get subscription error: {str(e)}")
            return {'success': False, 'error': 'Failed to fetch subscription'}
    
    # =============================================================================
    # USAGE TRACKING
    # =============================================================================
    
    def track_usage(self, user_id: int, metric_type: str, quantity: int = 1, 
                   resource_id: str = None, resource_type: str = None) -> Dict[str, Any]:
        """
        Track usage for billing purposes
        """
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            
            # Calculate billing period
            now = datetime.utcnow()
            if subscription and subscription.current_period_start:
                billing_start = subscription.current_period_start
                billing_end = subscription.current_period_end
            else:
                # Default to monthly period
                billing_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if billing_start.month == 12:
                    billing_end = billing_start.replace(year=billing_start.year + 1, month=1)
                else:
                    billing_end = billing_start.replace(month=billing_start.month + 1)
            
            # Create usage record
            usage_record = UsageRecord(
                user_id=user_id,
                subscription_id=subscription.id if subscription else None,
                metric_type=metric_type,
                quantity=quantity,
                resource_id=resource_id,
                resource_type=resource_type,
                billing_period_start=billing_start,
                billing_period_end=billing_end
            )
            
            # Calculate cost based on metric type (if applicable)
            unit_cost = self._get_unit_cost(metric_type)
            if unit_cost:
                usage_record.unit_cost = Decimal(str(unit_cost))
                usage_record.total_cost = Decimal(str(unit_cost)) * quantity
            
            db.session.add(usage_record)
            db.session.commit()
            
            return {
                'success': True,
                'usage_record': usage_record.to_dict()
            }
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Track usage error: {str(e)}")
            return {'success': False, 'error': 'Failed to track usage'}
    
    def get_usage_summary(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get usage summary for user
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            usage_records = UsageRecord.query.filter(
                UsageRecord.user_id == user_id,
                UsageRecord.created_at >= start_date
            ).all()
            
            summary = {
                'sms_sent': 0,
                'sms_received': 0,
                'ai_responses': 0,
                'total_cost': Decimal('0.00'),
                'period_days': days
            }
            
            for record in usage_records:
                if record.metric_type in summary:
                    summary[record.metric_type] += record.quantity
                if record.total_cost:
                    summary['total_cost'] += record.total_cost
            
            # Convert Decimal to float for JSON serialization
            summary['total_cost'] = float(summary['total_cost'])
            
            return {
                'success': True,
                'usage_summary': summary
            }
            
        except Exception as e:
            self.logger.error(f"Get usage summary error: {str(e)}")
            return {'success': False, 'error': 'Failed to fetch usage summary'}
    
    def check_usage_limits(self, user_id: int) -> Dict[str, Any]:
        """
        Check if user has exceeded usage limits
        """
        try:
            user = User.query.get(user_id)
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            
            if not subscription or not subscription.plan:
                return {
                    'success': True,
                    'within_limits': False,
                    'reason': 'No active subscription'
                }
            
            plan_features = subscription.plan.features
            
            # Get current period usage
            current_usage = self._get_current_period_usage(user_id, subscription)
            
            # Check SMS limits
            sms_limit = plan_features.get('sms_credits_monthly', 0)
            if subscription.billing_cycle == 'annual':
                sms_limit = plan_features.get('sms_credits_annual', sms_limit * 12)
            
            sms_used = current_usage.get('sms_sent', 0) + current_usage.get('sms_received', 0)
            
            # Check AI response limits
            ai_limit = plan_features.get('ai_responses_monthly', 0)
            if subscription.billing_cycle == 'annual':
                ai_limit = plan_features.get('ai_responses_annual', ai_limit * 12)
            
            ai_used = current_usage.get('ai_responses', 0)
            
            limits_check = {
                'sms': {
                    'limit': sms_limit,
                    'used': sms_used,
                    'remaining': max(0, sms_limit - sms_used),
                    'percentage': (sms_used / sms_limit * 100) if sms_limit > 0 else 0
                },
                'ai_responses': {
                    'limit': ai_limit,
                    'used': ai_used,
                    'remaining': max(0, ai_limit - ai_used),
                    'percentage': (ai_used / ai_limit * 100) if ai_limit > 0 else 0
                }
            }
            
            within_limits = (sms_used < sms_limit and ai_used < ai_limit)
            
            return {
                'success': True,
                'within_limits': within_limits,
                'limits': limits_check,
                'current_usage': current_usage
            }
            
        except Exception as e:
            self.logger.error(f"Check usage limits error: {str(e)}")
            return {'success': False, 'error': 'Failed to check usage limits'}
    
    # =============================================================================
    # WEBHOOK PROCESSING
    # =============================================================================
    
    def process_stripe_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Process Stripe webhook events
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.config.webhook_secret
            )
            
            event_type = event['type']
            event_data = event['data']['object']
            
            self.logger.info(f"Processing Stripe webhook: {event_type}")
            
            # Handle different event types
            if event_type == 'customer.subscription.updated':
                return self._handle_subscription_updated(event_data)
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(event_data)
            elif event_type == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(event_data)
            elif event_type == 'invoice.payment_failed':
                return self._handle_payment_failed(event_data)
            elif event_type == 'customer.subscription.trial_will_end':
                return self._handle_trial_will_end(event_data)
            else:
                return {
                    'success': True,
                    'message': f'Unhandled event type: {event_type}'
                }
                
        except stripe.error.SignatureVerificationError as e:
            self.logger.error(f"Webhook signature verification failed: {str(e)}")
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            self.logger.error(f"Webhook processing error: {str(e)}")
            return {'success': False, 'error': 'Webhook processing failed'}
    
    def _handle_subscription_updated(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription update webhook"""
        try:
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_data['id']
            ).first()
            
            if subscription:
                subscription.status = subscription_data['status']
                subscription.current_period_start = datetime.fromtimestamp(
                    subscription_data['current_period_start']
                )
                subscription.current_period_end = datetime.fromtimestamp(
                    subscription_data['current_period_end']
                )
                
                if subscription_data.get('canceled_at'):
                    subscription.canceled_at = datetime.fromtimestamp(
                        subscription_data['canceled_at']
                    )
                
                db.session.commit()
            
            return {'success': True, 'message': 'Subscription updated'}
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Handle subscription updated error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_subscription_deleted(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription deletion webhook"""
        try:
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_data['id']
            ).first()
            
            if subscription:
                subscription.status = 'canceled'
                subscription.ended_at = datetime.utcnow()
                db.session.commit()
            
            return {'success': True, 'message': 'Subscription deleted'}
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Handle subscription deleted error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _handle_payment_succeeded(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment webhook"""
        # Implementation for successful payment processing
        return {'success': True, 'message': 'Payment succeeded'}
    
    def _handle_payment_failed(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment webhook"""
        # Implementation for failed payment processing
        return {'success': True, 'message': 'Payment failed processed'}
    
    def _handle_trial_will_end(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle trial ending webhook"""
        # Implementation for trial ending notification
        return {'success': True, 'message': 'Trial ending processed'}
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================
    
    def _get_unit_cost(self, metric_type: str) -> Optional[float]:
        """Get unit cost for metric type"""
        costs = {
            'sms_sent': 0.01,    # $0.01 per SMS
            'sms_received': 0.005,  # $0.005 per received SMS
            'ai_response': 0.02   # $0.02 per AI response
        }
        return costs.get(metric_type)
    
    def _get_current_period_usage(self, user_id: int, subscription: Subscription) -> Dict[str, int]:
        """Get usage for current billing period"""
        start_date = subscription.current_period_start
        end_date = subscription.current_period_end
        
        usage_records = UsageRecord.query.filter(
            UsageRecord.user_id == user_id,
            UsageRecord.billing_period_start >= start_date,
            UsageRecord.billing_period_end <= end_date
        ).all()
        
        usage_summary = {}
        for record in usage_records:
            metric = record.metric_type
            if metric not in usage_summary:
                usage_summary[metric] = 0
            usage_summary[metric] += record.quantity
        
        return usage_summary