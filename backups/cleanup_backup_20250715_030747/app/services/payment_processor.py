# app/services/payment_processor.py
"""
Payment processor service with Stripe integration
Handles all payment processing, subscription management, and webhook events
"""

import stripe
import logging
from datetime import datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models.user import User
from app.models.subscription import Subscription
from app.models.payment import Payment, PaymentMethod
from app.models.invoice import Invoice
from app.utils.billing_helpers import BillingHelpers

logger = logging.getLogger(__name__)

class PaymentProcessor:
    """Payment processor using Stripe as the backend"""
    
    @staticmethod
    def initialize():
        """Initialize Stripe with API key"""
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
    
    @classmethod
    def create_customer(cls, user_id: str, email: str, name: str = None) -> dict:
        """Create a customer in Stripe"""
        try:
            cls.initialize()
            
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={'user_id': user_id}
            )
            
            return {
                'success': True,
                'customer_id': customer.id,
                'customer': customer
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}")
            return {'success': False, 'error': 'Failed to create customer'}
    
    @classmethod
    def create_payment_method(cls, user_id: str, token: str, billing_address: dict = None) -> dict:
        """Create and attach payment method to customer"""
        try:
            cls.initialize()
            
            # Get or create customer
            user = User.query.get(user_id)
            if not user.stripe_customer_id:
                customer_result = cls.create_customer(user_id, user.email, f"{user.first_name} {user.last_name}")
                if not customer_result['success']:
                    return customer_result
                user.stripe_customer_id = customer_result['customer_id']
                db.session.commit()
            
            # Create payment method
            payment_method = stripe.PaymentMethod.create(
                type='card',
                card={'token': token}
            )
            
            # Attach to customer
            payment_method.attach(customer=user.stripe_customer_id)
            
            return {
                'success': True,
                'processor_id': payment_method.id,
                'card_details': {
                    'brand': payment_method.card.brand,
                    'last4': payment_method.card.last4,
                    'exp_month': payment_method.card.exp_month,
                    'exp_year': payment_method.card.exp_year
                }
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment method: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error creating payment method: {str(e)}")
            return {'success': False, 'error': 'Failed to create payment method'}
    
    @classmethod
    def process_payment(cls, amount: float, currency: str, payment_method_id: str, 
                       description: str = None, metadata: dict = None) -> dict:
        """Process a one-time payment"""
        try:
            cls.initialize()
            
            # Get payment method from database
            pm = PaymentMethod.query.get(payment_method_id)
            if not pm:
                return {'success': False, 'error': 'Payment method not found'}
            
            # Get customer
            user = User.query.get(pm.user_id)
            if not user.stripe_customer_id:
                return {'success': False, 'error': 'Customer not found'}
            
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                customer=user.stripe_customer_id,
                payment_method=pm.processor_id,
                description=description,
                metadata=metadata or {},
                confirm=True,
                return_url=current_app.config.get('FRONTEND_URL', 'https://app.example.com')
            )
            
            if intent.status == 'succeeded':
                return {
                    'success': True,
                    'processor_id': intent.id,
                    'status': intent.status,
                    'amount': amount,
                    'currency': currency
                }
            else:
                return {
                    'success': False,
                    'error': f"Payment failed with status: {intent.status}",
                    'processor_id': intent.id,
                    'status': intent.status
                }
            
        except stripe.error.CardError as e:
            logger.error(f"Card error: {str(e)}")
            return {'success': False, 'error': e.user_message or str(e)}
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error processing payment: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            return {'success': False, 'error': 'Payment processing failed'}
    
    @classmethod
    def create_subscription(cls, user_id: str, plan_id: str, payment_method_id: str = None,
                           trial_days: int = None, coupon: str = None) -> dict:
        """Create a subscription in Stripe"""
        try:
            cls.initialize()
            
            user = User.query.get(user_id)
            if not user.stripe_customer_id:
                customer_result = cls.create_customer(user_id, user.email, f"{user.first_name} {user.last_name}")
                if not customer_result['success']:
                    return customer_result
                user.stripe_customer_id = customer_result['customer_id']
                db.session.commit()
            
            # Set default payment method if provided
            if payment_method_id:
                pm = PaymentMethod.query.get(payment_method_id)
                if pm:
                    stripe.Customer.modify(
                        user.stripe_customer_id,
                        invoice_settings={'default_payment_method': pm.processor_id}
                    )
            
            # Create subscription
            subscription_data = {
                'customer': user.stripe_customer_id,
                'items': [{'price': plan_id}],
                'metadata': {'user_id': user_id}
            }
            
            if trial_days:
                subscription_data['trial_period_days'] = trial_days
            
            if coupon:
                subscription_data['coupon'] = coupon
            
            subscription = stripe.Subscription.create(**subscription_data)
            
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status,
                'current_period_start': datetime.fromtimestamp(subscription.current_period_start),
                'current_period_end': datetime.fromtimestamp(subscription.current_period_end),
                'trial_end': datetime.fromtimestamp(subscription.trial_end) if subscription.trial_end else None
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating subscription: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            return {'success': False, 'error': 'Failed to create subscription'}
    
    @classmethod
    def update_subscription(cls, subscription_id: str, plan_id: str = None, 
                           quantity: int = None, prorate: bool = True) -> dict:
        """Update a subscription"""
        try:
            cls.initialize()
            
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            update_data = {'proration_behavior': 'create_prorations' if prorate else 'none'}
            
            if plan_id:
                update_data['items'] = [{
                    'id': subscription['items']['data'][0].id,
                    'price': plan_id,
                }]
            
            if quantity:
                update_data['items'][0]['quantity'] = quantity
            
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                **update_data
            )
            
            return {
                'success': True,
                'subscription': updated_subscription,
                'proration_amount': cls._calculate_proration_amount(updated_subscription)
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error updating subscription: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error updating subscription: {str(e)}")
            return {'success': False, 'error': 'Failed to update subscription'}
    
    @classmethod
    def cancel_subscription(cls, subscription_id: str, at_period_end: bool = True) -> dict:
        """Cancel a subscription"""
        try:
            cls.initialize()
            
            if at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = stripe.Subscription.delete(subscription_id)
            
            return {
                'success': True,
                'subscription': subscription,
                'canceled_at': datetime.fromtimestamp(subscription.canceled_at) if subscription.canceled_at else None
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error canceling subscription: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error canceling subscription: {str(e)}")
            return {'success': False, 'error': 'Failed to cancel subscription'}
    
    @classmethod
    def create_billing_portal_session(cls, user_id: str, return_url: str) -> str:
        """Create a billing portal session"""
        try:
            cls.initialize()
            
            user = User.query.get(user_id)
            if not user.stripe_customer_id:
                raise ValueError("User has no Stripe customer ID")
            
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url
            )
            
            return session.url
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating billing portal: {str(e)}")
            raise Exception(f"Failed to create billing portal: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating billing portal: {str(e)}")
            raise Exception("Failed to create billing portal")
    
    @classmethod
    def refund_payment(cls, payment_intent_id: str, amount: float = None, reason: str = None) -> dict:
        """Refund a payment"""
        try:
            cls.initialize()
            
            refund_data = {'payment_intent': payment_intent_id}
            
            if amount:
                refund_data['amount'] = int(amount * 100)  # Convert to cents
            
            if reason:
                refund_data['reason'] = reason
            
            refund = stripe.Refund.create(**refund_data)
            
            return {
                'success': True,
                'refund_id': refund.id,
                'amount': refund.amount / 100,  # Convert back to dollars
                'status': refund.status
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error processing refund: {str(e)}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error processing refund: {str(e)}")
            return {'success': False, 'error': 'Failed to process refund'}
    
    @classmethod
    def handle_webhook_event(cls, event: dict) -> dict:
        """Handle Stripe webhook events"""
        try:
            event_type = event['type']
            
            if event_type == 'customer.subscription.created':
                return cls._handle_subscription_created(event['data']['object'])
            elif event_type == 'customer.subscription.updated':
                return cls._handle_subscription_updated(event['data']['object'])
            elif event_type == 'customer.subscription.deleted':
                return cls._handle_subscription_deleted(event['data']['object'])
            elif event_type == 'invoice.payment_succeeded':
                return cls._handle_payment_succeeded(event['data']['object'])
            elif event_type == 'invoice.payment_failed':
                return cls._handle_payment_failed(event['data']['object'])
            elif event_type == 'payment_intent.succeeded':
                return cls._handle_payment_intent_succeeded(event['data']['object'])
            elif event_type == 'payment_method.attached':
                return cls._handle_payment_method_attached(event['data']['object'])
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                return {'success': True, 'message': 'Event acknowledged but not processed'}
            
        except Exception as e:
            logger.error(f"Error handling webhook event: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def _handle_subscription_created(cls, stripe_subscription: dict) -> dict:
        """Handle subscription creation webhook"""
        try:
            user_id = stripe_subscription['metadata'].get('user_id')
            if not user_id:
                logger.warning("No user_id in subscription metadata")
                return {'success': False, 'error': 'No user_id in metadata'}
            
            # Update local subscription record
            subscription = Subscription.query.filter_by(
                user_id=user_id,
                stripe_subscription_id=stripe_subscription['id']
            ).first()
            
            if subscription:
                subscription.status = stripe_subscription['status']
                subscription.current_period_start = datetime.fromtimestamp(stripe_subscription['current_period_start'])
                subscription.current_period_end = datetime.fromtimestamp(stripe_subscription['current_period_end'])
                db.session.commit()
            
            return {'success': True, 'message': 'Subscription created webhook processed'}
            
        except Exception as e:
            logger.error(f"Error handling subscription created: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def _handle_subscription_updated(cls, stripe_subscription: dict) -> dict:
        """Handle subscription update webhook"""
        try:
            # Find subscription by Stripe ID
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=stripe_subscription['id']
            ).first()
            
            if not subscription:
                logger.warning(f"No local subscription found for Stripe ID: {stripe_subscription['id']}")
                return {'success': False, 'error': 'Subscription not found'}
            
            # Update subscription status and dates
            subscription.status = stripe_subscription['status']
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription['current_period_start'])
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription['current_period_end'])
            
            if stripe_subscription.get('canceled_at'):
                subscription.canceled_at = datetime.fromtimestamp(stripe_subscription['canceled_at'])
            
            db.session.commit()
            
            return {'success': True, 'message': 'Subscription updated webhook processed'}
            
        except Exception as e:
            logger.error(f"Error handling subscription updated: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def _handle_payment_succeeded(cls, stripe_invoice: dict) -> dict:
        """Handle successful payment webhook"""
        try:
            # Find subscription
            if stripe_invoice.get('subscription'):
                subscription = Subscription.query.filter_by(
                    stripe_subscription_id=stripe_invoice['subscription']
                ).first()
                
                if subscription:
                    # Create payment record
                    payment = Payment(
                        user_id=subscription.user_id,
                        subscription_id=subscription.id,
                        amount=stripe_invoice['amount_paid'] / 100,  # Convert from cents
                        currency=stripe_invoice['currency'].upper(),
                        status='succeeded',
                        stripe_payment_intent_id=stripe_invoice.get('payment_intent'),
                        stripe_invoice_id=stripe_invoice['id'],
                        processed_at=datetime.fromtimestamp(stripe_invoice['status_transitions']['paid_at'])
                    )
                    
                    db.session.add(payment)
                    
                    # Update subscription status if needed
                    if subscription.status in ['past_due', 'unpaid']:
                        subscription.status = 'active'
                    
                    db.session.commit()
            
            return {'success': True, 'message': 'Payment succeeded webhook processed'}
            
        except Exception as e:
            logger.error(f"Error handling payment succeeded: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def _handle_payment_failed(cls, stripe_invoice: dict) -> dict:
        """Handle failed payment webhook"""
        try:
            # Find subscription
            if stripe_invoice.get('subscription'):
                subscription = Subscription.query.filter_by(
                    stripe_subscription_id=stripe_invoice['subscription']
                ).first()
                
                if subscription:
                    # Update subscription status
                    subscription.status = 'past_due'
                    
                    # Create failed payment record
                    payment = Payment(
                        user_id=subscription.user_id,
                        subscription_id=subscription.id,
                        amount=stripe_invoice['amount_due'] / 100,  # Convert from cents
                        currency=stripe_invoice['currency'].upper(),
                        status='failed',
                        stripe_invoice_id=stripe_invoice['id'],
                        failure_reason=stripe_invoice.get('last_payment_error', {}).get('message', 'Payment failed')
                    )
                    
                    db.session.add(payment)
                    db.session.commit()
                    
                    # Send notification to user
                    # TODO: Implement notification service
                    logger.info(f"Payment failed for subscription {subscription.id}")
            
            return {'success': True, 'message': 'Payment failed webhook processed'}
            
        except Exception as e:
            logger.error(f"Error handling payment failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def _calculate_proration_amount(cls, subscription: dict) -> float:
        """Calculate proration amount from subscription"""
        # This is a simplified calculation
        # In production, you'd want more sophisticated proration logic
        latest_invoice = subscription.get('latest_invoice')
        if latest_invoice and latest_invoice.get('amount_due'):
            return latest_invoice['amount_due'] / 100
        return 0.0
    
    @staticmethod
    def validate_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
        """Validate Stripe webhook signature"""
        try:
            stripe.Webhook.construct_event(payload, signature, secret)
            return True
        except Exception:
            return False