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


class StripeSubscriptionClient:
    """
    Simplified Stripe client for subscription billing.
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
        if not user.stripe_customer_id:
            customer = self.create_customer(user)
            return customer.id
        return user.stripe_customer_id
    
    # ===================================
    # SUBSCRIPTION OPERATIONS
    # ===================================
    
    @handle_stripe_errors
    def create_subscription(self, user: User, price_id: str, 
                          trial_days: Optional[int] = None,
                          payment_method_id: Optional[str] = None) -> stripe.Subscription:
        """
        Create a subscription for a user.
        
        Args:
            user: User model instance
            price_id: Stripe price ID for the subscription
            trial_days: Optional trial period in days
            payment_method_id: Optional payment method ID
            
        Returns:
            Created Stripe Subscription object
        """
        customer_id = self.ensure_customer(user)
        
        subscription_data = {
            'customer': customer_id,
            'items': [{'price': price_id}],
            'metadata': {
                'user_id': str(user.id),
                'created_via': 'app'
            },
            'expand': ['latest_invoice.payment_intent']
        }
        
        # Add trial period if specified
        if trial_days:
            subscription_data['trial_period_days'] = trial_days
        
        # Set default payment method if provided
        if payment_method_id:
            subscription_data['default_payment_method'] = payment_method_id
        
        subscription = stripe.Subscription.create(**subscription_data)
        
        self.logger.info(f"Created subscription {subscription.id} for user {user.id}")
        return subscription
    
    @handle_stripe_errors
    def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Get subscription by ID"""
        return stripe.Subscription.retrieve(subscription_id)
    
    @handle_stripe_errors
    def cancel_subscription(self, subscription_id: str, 
                          immediate: bool = False) -> stripe.Subscription:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Subscription ID to cancel
            immediate: If True, cancel immediately. If False, cancel at period end.
            
        Returns:
            Updated subscription object
        """
        if immediate:
            subscription = stripe.Subscription.delete(subscription_id)
            self.logger.info(f"Immediately cancelled subscription {subscription_id}")
        else:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            self.logger.info(f"Scheduled cancellation for subscription {subscription_id}")
        
        return subscription
    
    @handle_stripe_errors
    def reactivate_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Reactivate a subscription that was set to cancel at period end"""
        subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=False
        )
        
        self.logger.info(f"Reactivated subscription {subscription_id}")
        return subscription
    
    @handle_stripe_errors
    def update_subscription(self, subscription_id: str, new_price_id: str) -> stripe.Subscription:
        """
        Update subscription to a new price/plan.
        
        Args:
            subscription_id: Existing subscription ID
            new_price_id: New price ID to switch to
            
        Returns:
            Updated subscription object
        """
        # Get current subscription
        subscription = self.get_subscription(subscription_id)
        
        # Update to new price
        updated_subscription = stripe.Subscription.modify(
            subscription_id,
            items=[{
                'id': subscription['items']['data'][0].id,
                'price': new_price_id,
            }],
            proration_behavior='create_prorations'
        )
        
        self.logger.info(f"Updated subscription {subscription_id} to price {new_price_id}")
        return updated_subscription
    
    # ===================================
    # PAYMENT METHOD SETUP
    # ===================================
    
    @handle_stripe_errors
    def create_setup_intent(self, user: User) -> stripe.SetupIntent:
        """
        Create a setup intent for collecting payment method.
        
        Args:
            user: User model instance
            
        Returns:
            Created SetupIntent object
        """
        customer_id = self.ensure_customer(user)
        
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            usage='off_session',  # For future payments
            metadata={
                'user_id': str(user.id)
            }
        )
        
        self.logger.info(f"Created setup intent {setup_intent.id} for user {user.id}")
        return setup_intent
    
    @handle_stripe_errors
    def list_payment_methods(self, customer_id: str) -> list:
        """List customer's payment methods"""
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type='card'
        )
        return payment_methods.data
    
    # ===================================
    # WEBHOOK HANDLING
    # ===================================
    
    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        """
        Verify webhook signature and return event.
        
        Args:
            payload: Raw webhook payload
            signature: Stripe-Signature header value
            
        Returns:
            Webhook event dictionary
            
        Raises:
            StripeWebhookError: If verification fails
        """
        if not self.webhook_secret:
            raise StripeWebhookError("Webhook secret not configured")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            
            self.logger.info(f"Verified webhook: {event['type']} - {event['id']}")
            return event
            
        except ValueError as e:
            self.logger.error(f"Invalid webhook payload: {str(e)}")
            raise StripeWebhookError(f"Invalid payload: {str(e)}")
            
        except stripe.error.SignatureVerificationError as e:
            self.logger.error(f"Webhook signature verification failed: {str(e)}")
            raise StripeWebhookError(f"Invalid signature: {str(e)}")
    
    def handle_subscription_event(self, event: dict) -> bool:
        """
        Handle subscription-related webhook events.
        
        Args:
            event: Webhook event dictionary
            
        Returns:
            True if event was handled successfully
        """
        event_type = event['type']
        subscription = event['data']['object']
        
        # Extract user ID from metadata
        user_id = subscription.get('metadata', {}).get('user_id')
        if not user_id:
            self.logger.warning(f"No user_id in subscription metadata for event {event['id']}")
            return False
        
        try:
            user = User.query.get(int(user_id))
            if not user:
                self.logger.error(f"User {user_id} not found for subscription event")
                return False
            
            # Handle different subscription events
            if event_type == 'customer.subscription.created':
                self._handle_subscription_created(user, subscription)
            elif event_type == 'customer.subscription.updated':
                self._handle_subscription_updated(user, subscription)
            elif event_type == 'customer.subscription.deleted':
                self._handle_subscription_cancelled(user, subscription)
            elif event_type == 'invoice.payment_succeeded':
                self._handle_payment_succeeded(user, event['data']['object'])
            elif event_type == 'invoice.payment_failed':
                self._handle_payment_failed(user, event['data']['object'])
            else:
                self.logger.info(f"Unhandled subscription event: {event_type}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling subscription event {event['id']}: {str(e)}")
            return False
    
    def _handle_subscription_created(self, user: User, subscription: dict):
        """Handle new subscription creation"""
        self.logger.info(f"Subscription created for user {user.id}: {subscription['id']}")
        # Add your business logic here
        # e.g., update user's subscription status in database
    
    def _handle_subscription_updated(self, user: User, subscription: dict):
        """Handle subscription updates"""
        self.logger.info(f"Subscription updated for user {user.id}: {subscription['id']}")
        # Add your business logic here
        # e.g., handle plan changes, trial endings, etc.
    
    def _handle_subscription_cancelled(self, user: User, subscription: dict):
        """Handle subscription cancellation"""
        self.logger.info(f"Subscription cancelled for user {user.id}: {subscription['id']}")
        # Add your business logic here
        # e.g., revoke access, send notifications
    
    def _handle_payment_succeeded(self, user: User, invoice: dict):
        """Handle successful payment"""
        self.logger.info(f"Payment succeeded for user {user.id}: ${invoice['amount_paid']/100}")
        # Add your business logic here
        # e.g., extend subscription, send confirmation email
    
    def _handle_payment_failed(self, user: User, invoice: dict):
        """Handle failed payment"""
        self.logger.warning(f"Payment failed for user {user.id}: ${invoice['amount_due']/100}")
        # Add your business logic here
        # e.g., send dunning emails, suspend service
    
    # ===================================
    # UTILITY METHODS
    # ===================================
    
    def test_connection(self) -> dict:
        """
        Test Stripe API connection.
        
        Returns:
            Connection test results
        """
        try:
            # Simple API call to test connectivity
            stripe.Customer.list(limit=1)
            
            return {
                'success': True,
                'message': 'Stripe connection successful',
                'webhook_configured': bool(self.webhook_secret),
                'timestamp': datetime.now().isoformat()
            }
            
        except stripe.error.AuthenticationError:
            return {
                'success': False,
                'message': 'Invalid Stripe API key',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }


# ===================================
# CONVENIENCE FUNCTIONS
# ===================================

def get_stripe_client() -> StripeSubscriptionClient:
    """Get configured Stripe client instance"""
    return StripeSubscriptionClient()


# ===================================
# USAGE EXAMPLES
# ===================================

"""
Example usage in your application:

# 1. Create subscription for user
from app.utils.stripe_client import get_stripe_client

stripe_client = get_stripe_client()

# Create subscription with trial
subscription = stripe_client.create_subscription(
    user=current_user,
    price_id="price_1234567890",
    trial_days=14
)

# 2. Handle webhooks in Flask route
@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    stripe_client = get_stripe_client()
    
    try:
        event = stripe_client.verify_webhook(
            request.data,
            request.headers.get('Stripe-Signature')
        )
        
        # Handle subscription events
        if event['type'].startswith('customer.subscription'):
            stripe_client.handle_subscription_event(event)
        
        return jsonify({'status': 'success'}), 200
        
    except StripeWebhookError as e:
        return jsonify({'error': str(e)}), 400

# 3. Setup payment method collection
setup_intent = stripe_client.create_setup_intent(user=current_user)
# Send setup_intent.client_secret to frontend

# 4. Cancel subscription
stripe_client.cancel_subscription(
    subscription_id="sub_1234567890",
    immediate=False  # Cancel at period end
)
"""