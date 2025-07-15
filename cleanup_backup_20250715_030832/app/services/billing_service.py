import stripe
from flask import current_app
from datetime import datetime, timedelta
from app.extensions import db
import logging
import json

logger = logging.getLogger(__name__)

def initialize_stripe():
    """Configure Stripe with API key"""
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

def create_subscription(user_id, plan_id, payment_method_id):
    """Create a new subscription for a user"""
    from app.models.user import User
    from app.models.billing import SubscriptionPlan, Subscription, Invoice
    from app.models.payment import PaymentMethod
    from app.models.subscription_payment_method import SubscriptionPaymentMethod
    
    initialize_stripe()
    
    # Get user, plan, and payment method
    user = User.query.get(user_id)
    if not user:
        raise ValueError("User not found")
    
    plan = SubscriptionPlan.query.get(plan_id)
    if not plan:
        raise ValueError("Subscription plan not found")
    
    payment_method = PaymentMethod.query.get(payment_method_id)
    if not payment_method:
        raise ValueError("Payment method not found")
    
    # Check payment method belongs to user
    if payment_method.user_id != user_id:
        raise ValueError("Payment method does not belong to user")
    
    # Ensure user has a Stripe customer ID
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=f"{user.first_name} {user.last_name}".strip(),
            phone=user.phone_number
        )
        user.stripe_customer_id = customer.id
        db.session.commit()
    
    # Set the payment method as default for the customer
    stripe.Customer.modify(
        user.stripe_customer_id,
        invoice_settings={
            'default_payment_method': payment_method.stripe_payment_method_id
        }
    )
    
    # Create Stripe subscription
    stripe_subscription = stripe.Subscription.create(
        customer=user.stripe_customer_id,
        items=[
            {'price': plan.stripe_price_id},
        ],
        payment_behavior='default_incomplete',
        expand=['latest_invoice.payment_intent'],
        metadata={
            'user_id': user_id,
            'plan_id': plan_id
        }
    )
    
    # Determine renewal/end dates based on billing cycle
    start_date = datetime.fromtimestamp(stripe_subscription.current_period_start)
    renewal_date = datetime.fromtimestamp(stripe_subscription.current_period_end)
    
    meta = {
        'created_by': 'billing_service',
        'version': '1.0',
        'initial_plan': plan.name
    }
    
    # Create subscription record in database
    subscription = Subscription(
        user_id=user_id,
        plan_id=plan_id,
        stripe_subscription_id=stripe_subscription.id,
        stripe_customer_id=user.stripe_customer_id,
        payment_method_id=payment_method_id,
        start_date=start_date,
        renewal_date=renewal_date,
        is_active=True,
        payment_status=stripe_subscription.status,
        auto_renew=True,
        subscription_metadata=json.dumps(meta)
    )
    
    db.session.add(subscription)
    db.session.commit()
    
    # Create subscription-payment method relationship
    spm = SubscriptionPaymentMethod(
        subscription_id=subscription.id,
        payment_method_id=payment_method_id,
        is_primary=True
    )
    db.session.add(spm)
    db.session.commit()
    
    return subscription

def update_subscription(subscription_id, plan_id):
    """Update a subscription to a new plan"""
    from app.models.billing import Subscription, SubscriptionPlan
    
    initialize_stripe()
    
    subscription = Subscription.query.get(subscription_id)
    if not subscription:
        raise ValueError("Subscription not found")
    
    new_plan = SubscriptionPlan.query.get(plan_id)
    if not new_plan:
        raise ValueError("Subscription plan not found")
    
    if subscription.plan_id == plan_id:
        return subscription  # No change needed
    
    try:
        # Update Stripe subscription
        stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        item_id = stripe_subscription['items']['data'][0].id
        
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            items=[{
                'id': item_id,
                'price': new_plan.stripe_price_id,
            }],
            proration_behavior='create_prorations',
            metadata={
                'user_id': subscription.user_id,
                'plan_id': plan_id
            }
        )
        
        # Update local subscription
        subscription.plan_id = plan_id
        db.session.commit()
        
        return subscription
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error updating subscription: {str(e)}")
        raise ValueError(f"Error updating subscription: {str(e)}")

def cancel_subscription(subscription_id):
    """Cancel a subscription"""
    from app.models.billing import Subscription
    
    initialize_stripe()
    
    subscription = Subscription.query.get(subscription_id)
    if not subscription:
        raise ValueError("Subscription not found")
    
    try:
        stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        subscription.auto_renew = False
        subscription.end_date = subscription.get_current_period_end()
        
        db.session.commit()
        
        return subscription
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error canceling subscription: {str(e)}")
        raise ValueError(f"Error canceling subscription: {str(e)}")

def check_subscription_status(subscription_id):
    """Check current status of a subscription with Stripe"""
    from app.models.billing import Subscription
    
    initialize_stripe()
    
    subscription = Subscription.query.get(subscription_id)
    if not subscription:
        raise ValueError("Subscription not found")
    
    try:
        stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
        
        subscription.payment_status = stripe_subscription.status
        
        if stripe_subscription.status in ['canceled', 'unpaid']:
            subscription.is_active = False
            subscription.end_date = datetime.fromtimestamp(stripe_subscription.ended_at) if hasattr(stripe_subscription, 'ended_at') and stripe_subscription.ended_at else datetime.utcnow()
        
        db.session.commit()
        
        return subscription
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error checking subscription: {str(e)}")
        raise ValueError(f"Error checking subscription: {str(e)}")

def create_checkout_session(user_id, plan_id, success_url, cancel_url):
    """Create a Stripe checkout session for a subscription"""
    from app.models.user import User
    from app.models.billing import SubscriptionPlan
    
    initialize_stripe()
    
    user = User.query.get(user_id)
    if not user:
        raise ValueError("User not found")
    
    plan = SubscriptionPlan.query.get(plan_id)
    if not plan:
        raise ValueError("Subscription plan not found")
    
    # Create or retrieve Stripe customer
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=f"{user.first_name} {user.last_name}".strip(),
            phone=user.phone_number
        )
        user.stripe_customer_id = customer.id
        db.session.commit()
    
    try:
        session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': plan.stripe_price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': user_id,
                'plan_id': plan_id
            }
        )
        
        return session.id, session.url
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise ValueError(f"Error creating checkout session: {str(e)}")