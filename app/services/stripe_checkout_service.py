# app/services/stripe_checkout_service.py
import stripe
from flask import current_app, url_for
from datetime import datetime, timedelta
import logging

from app.extensions import db
from app.models.user import User
from app.models.billing import PaymentMethod
from app.services.trial_membership_service import TrialMembershipService

logger = logging.getLogger(__name__)

class StripeCheckoutService:
    """Service for handling Stripe checkout and payment method setup"""
    
    @classmethod
    def initialize_stripe(cls):
        """Initialize Stripe with API key"""
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
    @classmethod
    def create_setup_intent_for_trial(cls, user_id: int) -> dict:
        """Create a Stripe SetupIntent for trial payment method collection"""
        try:
            cls.initialize_stripe()
            
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Ensure user has a Stripe customer ID
            if not user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=f"{user.first_name} {user.last_name}".strip(),
                    metadata={'user_id': user_id}
                )
                user.stripe_customer_id = customer.id
                db.session.commit()
            
            # Create SetupIntent for payment method collection
            setup_intent = stripe.SetupIntent.create(
                customer=user.stripe_customer_id,
                usage='off_session',  # For future payments
                metadata={
                    'user_id': user_id,
                    'purpose': 'trial_payment_method'
                }
            )
            
            logger.info(f"Created SetupIntent for user {user_id}: {setup_intent.id}")
            
            return {
                'success': True,
                'client_secret': setup_intent.client_secret,
                'setup_intent_id': setup_intent.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating SetupIntent: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error creating SetupIntent: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def confirm_payment_method_setup(cls, user_id: int, setup_intent_id: str) -> dict:
        """Confirm payment method setup and save to database"""
        try:
            cls.initialize_stripe()
            
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            # Retrieve the SetupIntent to get payment method
            setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
            
            if setup_intent.status != 'succeeded':
                return {'success': False, 'error': 'Payment method setup not completed'}
            
            payment_method_id = setup_intent.payment_method
            if not payment_method_id:
                return {'success': False, 'error': 'No payment method found'}
            
            # Get payment method details
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            
            # Check if payment method already exists
            existing_pm = PaymentMethod.query.filter_by(
                stripe_payment_method_id=payment_method_id
            ).first()
            
            if existing_pm:
                # Update existing payment method status
                existing_pm.status = 'active'
                existing_pm.is_default = True
                db.session.commit()
                
                payment_method_record = existing_pm
            else:
                # Create new payment method record
                payment_method_record = PaymentMethod(
                    user_id=user_id,
                    stripe_payment_method_id=payment_method_id,
                    payment_type=payment_method.type,
                    status='active',
                    is_default=True,
                    last_four=payment_method.card.last4 if payment_method.card else None,
                    brand=payment_method.card.brand if payment_method.card else None,
                    expires_month=payment_method.card.exp_month if payment_method.card else None,
                    expires_year=payment_method.card.exp_year if payment_method.card else None
                )
                
                # Set other payment methods as non-default
                PaymentMethod.query.filter_by(
                    user_id=user_id,
                    is_default=True
                ).update({'is_default': False})
                
                db.session.add(payment_method_record)
                db.session.commit()
            
            # Set as default payment method for customer
            stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={'default_payment_method': payment_method_id}
            )
            
            # Create success notification
            TrialMembershipService.create_trial_notification(
                user_id=user_id,
                notification_type='payment_method_added',
                title='Payment Method Added Successfully',
                message='Your payment method has been securely saved. You can now start your 14-day free trial.',
                priority='medium'
            )
            
            logger.info(f"Payment method confirmed for user {user_id}: {payment_method_id}")
            
            return {
                'success': True,
                'payment_method_id': payment_method_record.id,
                'last_four': payment_method_record.last_four,
                'brand': payment_method_record.brand
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment method: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error confirming payment method: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def create_checkout_session_for_subscription(cls, user_id: int, plan_id: int, 
                                               trial_days: int = 14) -> dict:
        """Create Stripe Checkout session for subscription with trial"""
        try:
            cls.initialize_stripe()
            
            from app.models.subscription import SubscriptionPlan
            
            user = User.query.get(user_id)
            plan = SubscriptionPlan.query.get(plan_id)
            
            if not user or not plan:
                return {'success': False, 'error': 'User or plan not found'}
            
            # Ensure user has Stripe customer ID
            if not user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=f"{user.first_name} {user.last_name}".strip(),
                    metadata={'user_id': user_id}
                )
                user.stripe_customer_id = customer.id
                db.session.commit()
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=user.stripe_customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': plan.stripe_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                subscription_data={
                    'trial_period_days': trial_days,
                    'metadata': {
                        'user_id': user_id,
                        'plan_id': plan_id,
                        'trial_days': trial_days
                    }
                },
                success_url=f"{current_app.config['FRONTEND_URL']}/trial/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{current_app.config['FRONTEND_URL']}/trial/checkout",
                metadata={
                    'user_id': user_id,
                    'plan_id': plan_id,
                    'purpose': 'trial_subscription'
                }
            )
            
            logger.info(f"Created checkout session for user {user_id}: {session.id}")
            
            return {
                'success': True,
                'checkout_url': session.url,
                'session_id': session.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def handle_checkout_session_completed(cls, session_id: str) -> dict:
        """Handle completed checkout session for trial subscription"""
        try:
            cls.initialize_stripe()
            
            session = stripe.checkout.Session.retrieve(session_id)
            
            if session.mode != 'subscription' or not session.subscription:
                return {'success': False, 'error': 'Invalid session type'}
            
            user_id = int(session.metadata.get('user_id'))
            plan_id = int(session.metadata.get('plan_id'))
            
            # Retrieve subscription details
            subscription = stripe.Subscription.retrieve(session.subscription)
            
            # Create local subscription record
            from app.models.subscription import Subscription
            
            trial_end = None
            if subscription.trial_end:
                trial_end = datetime.fromtimestamp(subscription.trial_end)
            
            local_subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                status=subscription.status,
                billing_cycle='monthly',
                amount=subscription.items.data[0].price.unit_amount / 100,  # Convert from cents
                currency=subscription.currency.upper(),
                current_period_start=datetime.fromtimestamp(subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(subscription.current_period_end),
                trial_end=trial_end,
                stripe_subscription_id=subscription.id,
                stripe_customer_id=subscription.customer
            )
            
            db.session.add(local_subscription)
            
            # Update user trial status
            user = User.query.get(user_id)
            if trial_end:
                user.trial_started_at = datetime.utcnow()
                user.trial_expires_at = trial_end
            
            db.session.commit()
            
            # Create notification
            TrialMembershipService.create_trial_notification(
                user_id=user_id,
                notification_type='subscription_created',
                title='Subscription Created Successfully',
                message=f'Your subscription has been created with a {subscription.trial_end and "14-day" or "no"} trial period.',
                priority='medium'
            )
            
            logger.info(f"Completed checkout session for user {user_id}: {session_id}")
            
            return {
                'success': True,
                'subscription_id': local_subscription.id,
                'trial_end': trial_end.isoformat() if trial_end else None
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error handling checkout completion: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error handling checkout completion: {e}")
            return {'success': False, 'error': str(e)}