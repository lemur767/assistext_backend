"""
Stripe Client - Fixed for Import Issues
"""
import stripe
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps
from flask import current_app

from app.extensions import db
from app.models.user import User


class StripeSubscriptionError(Exception):
    """Custom exception for Stripe subscription errors"""
    pass


class StripeWebhookError(Exception):
    """Custom exception for webhook verification errors"""
    pass


def handle_stripe_errors(func):
    """Decorator to handle common Stripe errors"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except stripe.error.CardError as e:
            logging.error(f"Card error: {str(e)}")
            raise StripeSubscriptionError(f"Payment failed: {e.user_message}")
        except stripe.error.RateLimitError as e:
            logging.error(f"Rate limit error: {str(e)}")
            raise StripeSubscriptionError("Too many requests. Please try again later.")
        except stripe.error.InvalidRequestError as e:
            logging.error(f"Invalid request: {str(e)}")
            raise StripeSubscriptionError(f"Invalid request: {str(e)}")
        except stripe.error.AuthenticationError as e:
            logging.error(f"Authentication error: {str(e)}")
            raise StripeSubscriptionError("Payment system authentication failed")
        except stripe.error.APIConnectionError as e:
            logging.error(f"Network error: {str(e)}")
            raise StripeSubscriptionError("Network error. Please try again.")
        except stripe.error.StripeError as e:
            logging.error(f"Stripe error: {str(e)}")
            raise StripeSubscriptionError(f"Payment system error: {str(e)}")
    
    return wrapper


class StripeClient:
    """
    Main Stripe client for subscription billing.
    Handles customer creation, subscriptions, and webhooks.
    """
    
    def __init__(self):
        """Initialize with Flask app configuration"""
        self.logger = logging.getLogger(__name__)
        self._configure_stripe()
    
    def _configure_stripe(self):
        """Configure Stripe from Flask app settings"""
        if not current_app:
            raise ValueError("Flask application context required")
        
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        if not stripe.api_key:
            raise ValueError("STRIPE_SECRET_KEY is required")
        
        # Set API version for consistency
        stripe.api_version = current_app.config.get('STRIPE_API_VERSION', '2023-10-16')
        
        self.webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
        if not self.webhook_secret:
            self.logger.warning("STRIPE_WEBHOOK_SECRET not set - webhook verification disabled")
    
    # ===================================
    # CUSTOMER OPERATIONS
    # ===================================
    
    @handle_stripe_errors
    def create_customer(self, user: User) -> stripe.Customer:
        """
        Create a Stripe customer for a user.
        
        Args:
            user: User model instance
            
        Returns:
            Created Stripe Customer object
        """
        customer = stripe.Customer.create(
            email=user.email,
            name=f"{user.first_name} {user.last_name}".strip(),
            metadata={
                'user_id': str(user.id),
                'created_via': 'app'
            }
        )
        
        # Save customer ID to user
        user.stripe_customer_id = customer.id
        db.session.commit()
        
        self.logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
        return customer
    
    @handle_stripe_errors
    def get_customer(self, customer_id: str) -> stripe.Customer:
        """Get customer by ID"""
        return stripe.Customer.retrieve(customer_id)
    
    def ensure_customer(self, user: User) -> str:
        """
        Ensure user has a Stripe customer ID, create if needed.
        
        Args:
            user: User model instance
            
        Returns:
            Stripe customer ID
        """
        if user.stripe_customer_id:
            return user.stripe_customer_id
        
        customer = self.create_customer(user)
        return customer.id
    
    # ===================================
    # SUBSCRIPTION OPERATIONS
    # ===================================
    
    @handle_stripe_errors
    def create_subscription(self, customer_id: str, price_id: str, 
                          payment_method_id: str = None, trial_days: int = None) -> stripe.Subscription:
        """
        Create a subscription for a customer.
        
        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            payment_method_id: Payment method ID (optional for trials)
            trial_days: Trial period in days
            
        Returns:
            Created Stripe Subscription object
        """
        subscription_data = {
            'customer': customer_id,
            'items': [{'price': price_id}],
            'expand': ['latest_invoice.payment_intent']
        }
        
        if payment_method_id:
            subscription_data['default_payment_method'] = payment_method_id
        
        if trial_days:
            subscription_data['trial_period_days'] = trial_days
        
        return stripe.Subscription.create(**subscription_data)
    
    @handle_stripe_errors
    def update_subscription(self, subscription_id: str, **kwargs) -> stripe.Subscription:
        """Update subscription"""
        return stripe.Subscription.modify(subscription_id, **kwargs)
    
    @handle_stripe_errors
    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> stripe.Subscription:
        """Cancel subscription"""
        return stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=at_period_end
        )
    
    # ===================================
    # PAYMENT METHODS
    # ===================================
    
    @handle_stripe_errors
    def create_setup_intent(self, customer_id: str) -> stripe.SetupIntent:
        """Create setup intent for payment method collection"""
        return stripe.SetupIntent.create(
            customer=customer_id,
            usage='off_session'
        )
    
    @handle_stripe_errors
    def attach_payment_method(self, payment_method_id: str, customer_id: str) -> stripe.PaymentMethod:
        """Attach payment method to customer"""
        return stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id
        )
    
    # ===================================
    # WEBHOOK HANDLING
    # ===================================
    
    def construct_webhook_event(self, payload: bytes, signature: str) -> stripe.Event:
        """
        Construct and verify webhook event.
        
        Args:
            payload: Raw webhook payload
            signature: Stripe webhook signature
            
        Returns:
            Verified Stripe Event object
            
        Raises:
            StripeWebhookError: If verification fails
        """
        if not self.webhook_secret:
            raise StripeWebhookError("Webhook secret not configured")
        
        try:
            return stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
        except ValueError as e:
            raise StripeWebhookError(f"Invalid payload: {str(e)}")
        except stripe.error.SignatureVerificationError as e:
            raise StripeWebhookError(f"Invalid signature: {str(e)}")
    
    # ===================================
    # HEALTH CHECK
    # ===================================
    
    def health_check(self) -> Dict[str, Any]:
        """Check Stripe API connectivity"""
        try:
            # Simple API call to verify connectivity
            stripe.Account.retrieve()
            return {
                'status': 'healthy',
                'available': True,
                'message': 'Stripe API accessible'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'available': False,
                'error': str(e)
            }


# Backward compatibility alias
