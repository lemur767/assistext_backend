from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.billing import Subscription,SubscriptionPlan,Invoice

from app.models.payment import PaymentMethod
from app.services.billing_service import create_subscription, update_subscription, cancel_subscription
from app.extensions import db
import stripe
from datetime import datetime, timezone
import pytz

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/plans', methods=['GET'])
def get_plans():
    """Get all available subscription plans"""
    plans = SubscriptionPlan.query.filter_by(is_active=True).all()
    return jsonify([plan.to_dict() for plan in plans]), 200

@billing_bp.route('/subscription', methods=['GET'])
@jwt_required()
def get_user_subscription():
    """Get current user's subscription"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    subscription = Subscription.query.filter_by(user_id=user_id, is_active=True).first()
    
    if not subscription:
        return jsonify({"message": "No active subscription found"}), 404
    
    return jsonify(subscription.to_dict()), 200

@billing_bp.route('/subscription', methods=['POST'])
@jwt_required()
def create_user_subscription():
    """Create a new subscription for the user"""
    user_id = get_jwt_identity()
    data = request.json
    
    # Validate required fields
    if not all([data.get('plan_id'), data.get('payment_method_id')]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Get user
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Check if user already has an active subscription
    existing_subscription = Subscription.query.filter_by(user_id=user_id, is_active=True).first()
    if existing_subscription:
        return jsonify({"error": "User already has an active subscription"}), 400
    
    # Get subscription plan
    plan = SubscriptionPlan.query.get(data['plan_id'])
    if not plan:
        return jsonify({"error": "Subscription plan not found"}), 404
    
    try:
        # Create subscription using billing service
        subscription = create_subscription(
            user_id=user_id,
            plan_id=data['plan_id'],
            payment_method_id=data['payment_method_id']
        )
        
        return jsonify({
            "message": "Subscription created successfully",
            "subscription": subscription.to_dict()
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@billing_bp.route('/subscription', methods=['PUT'])
@jwt_required()
def update_user_subscription():
    """Update user's subscription (change plan)"""
    user_id = get_jwt_identity()
    data = request.json
    
    # Validate required fields
    if not data.get('plan_id'):
        return jsonify({"error": "Missing plan_id"}), 400
    
    # Get user's active subscription
    subscription = Subscription.query.filter_by(user_id=user_id, is_active=True).first()
    if not subscription:
        return jsonify({"error": "No active subscription found"}), 404
    
    # Get new plan
    plan = SubscriptionPlan.query.get(data['plan_id'])
    if not plan:
        return jsonify({"error": "Subscription plan not found"}), 404
    
    try:
        # Update subscription using billing service
        updated_subscription = update_subscription(
            subscription_id=subscription.id,
            plan_id=data['plan_id']
        )
        
        return jsonify({
            "message": "Subscription updated successfully",
            "subscription": updated_subscription.to_dict()
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@billing_bp.route('/subscription', methods=['DELETE'])
@jwt_required()
def cancel_user_subscription():
    """Cancel user's subscription"""
    user_id = get_jwt_identity()
    
    # Get user's active subscription
    subscription = Subscription.query.filter_by(user_id=user_id, is_active=True).first()
    if not subscription:
        return jsonify({"error": "No active subscription found"}), 404
    
    try:
        # Cancel subscription using billing service
        cancel_subscription(subscription_id=subscription.id)
        
        return jsonify({
            "message": "Subscription cancelled successfully"
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@billing_bp.route('/payment_methods', methods=['GET'])
@jwt_required()
def get_payment_methods():
    """Get user's saved payment methods"""
    user_id = get_jwt_identity()
    
    payment_methods = PaymentMethod.query.filter_by(user_id=user_id).all()
    
    return jsonify([pm.to_dict() for pm in payment_methods]), 200

@billing_bp.route('/payment_methods', methods=['POST'])
@jwt_required()
def add_payment_method():
    """Add a new payment method for the user"""
    user_id = get_jwt_identity()
    data = request.json
    
    # Validate required fields
    if not data.get('payment_method_token'):
        return jsonify({"error": "Missing payment method token"}), 400
    
    try:
        # Configure Stripe
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        
        # Check if user has a Stripe customer ID
        user = User.query.get(user_id)
        
        # If no customer ID, create a customer in Stripe
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                phone=user.phone_number
            )
            user.stripe_customer_id = customer.id
            db.session.commit()
        
        # Attach payment method to customer
        payment_method = stripe.PaymentMethod.attach(
            data['payment_method_token'],
            customer=user.stripe_customer_id
        )
        
        # Get payment method details
        card = payment_method.card
        
        # Save payment method to database
        new_payment_method = PaymentMethod(
            user_id=user_id,
            stripe_payment_method_id=payment_method.id,
            card_last4=card.last4,
            card_brand=card.brand,
            card_exp_month=card.exp_month,
            card_exp_year=card.exp_year,
            is_default=(not PaymentMethod.query.filter_by(user_id=user_id).count())
        )
        
        db.session.add(new_payment_method)
        db.session.commit()
        
        return jsonify({
            "message": "Payment method added successfully",
            "payment_method": new_payment_method.to_dict()
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@billing_bp.route('/payment_methods/<int:payment_method_id>/default', methods=['POST'])
@jwt_required()
def set_default_payment_method(payment_method_id):
    """Set a payment method as default"""
    user_id = get_jwt_identity()
    
    # Find the payment method
    payment_method = PaymentMethod.query.get(payment_method_id)
    if not payment_method:
        return jsonify({"error": "Payment method not found"}), 404
    
    # Check ownership
    if payment_method.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Reset all payment methods for this user
    PaymentMethod.query.filter_by(user_id=user_id).update({'is_default': False})
    
    # Set the selected payment method as default
    payment_method.is_default = True
    db.session.commit()
    
    return jsonify({
        "message": "Default payment method updated successfully"
    }), 200

@billing_bp.route('/payment_methods/<int:payment_method_id>', methods=['DELETE'])
@jwt_required()
def delete_payment_method(payment_method_id):
    """Delete a payment method"""
    user_id = get_jwt_identity()
    
    # Find the payment method
    payment_method = PaymentMethod.query.get(payment_method_id)
    if not payment_method:
        return jsonify({"error": "Payment method not found"}), 404
    
    # Check ownership
    if payment_method.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Check if this is the default payment method used for subscription
    if payment_method.is_default:
        subscription = Subscription.query.filter_by(user_id=user_id, is_active=True).first()
        if subscription:
            return jsonify({
                "error": "Cannot delete default payment method while subscription is active"
            }), 400
    
    try:
        # Configure Stripe
        stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
        
        # Detach payment method in Stripe
        stripe.PaymentMethod.detach(payment_method.stripe_payment_method_id)
        
        # Delete from database
        db.session.delete(payment_method)
        db.session.commit()
        
        return jsonify({
            "message": "Payment method deleted successfully"
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@billing_bp.route('/invoices', methods=['GET'])
@jwt_required()
def get_invoices():
    """Get user's invoices"""
    user_id = get_jwt_identity()
    
    invoices = Invoice.query.filter_by(user_id=user_id).order_by(Invoice.created_at.desc()).all()
    
    return jsonify([invoice.to_dict() for invoice in invoices]), 200

@billing_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    # Get Stripe webhook secret
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']
    
    # Get request data
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        current_app.logger.error(f"Invalid Stripe webhook payload: {e}")
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        current_app.logger.error(f"Invalid Stripe signature: {e}")
        return 'Invalid signature', 400
    
    # Handle the event based on its type
    if event['type'] == 'invoice.payment_succeeded':
        handle_invoice_payment_succeeded(event['data']['object'])
    elif event['type'] == 'invoice.payment_failed':
        handle_invoice_payment_failed(event['data']['object'])
    elif event['type'] == 'customer.subscription.deleted':
        handle_subscription_deleted(event['data']['object'])
    # Add more event handlers as needed
    
    return '', 200

def handle_invoice_payment_succeeded(invoice_data):
    """Handle successful payment event"""
    # Find subscription by Stripe ID
    subscription = Subscription.query.filter_by(stripe_subscription_id=invoice_data['subscription']).first()
    if not subscription:
        current_app.logger.error(f"Subscription not found for Stripe ID: {invoice_data['subscription']}")
        return
    
    # Create invoice record
    invoice = Invoice(
        user_id=subscription.user_id,
        subscription_id=subscription.id,
        stripe_invoice_id=invoice_data['id'],
        amount=invoice_data['amount_paid'] / 100,  # Convert from cents to dollars
        status='paid',
        invoice_date=datetime.fromtimestamp(invoice_data['created']),
        payment_method_id=subscription.payment_method_id
    )
    
    db.session.add(invoice)
    db.session.commit()
    
    current_app.logger.info(f"Invoice payment recorded: {invoice.id}")

def handle_invoice_payment_failed(invoice_data):
    """Handle failed payment event"""
    # Find subscription by Stripe ID
    subscription = Subscription.query.filter_by(stripe_subscription_id=invoice_data['subscription']).first()
    if not subscription:
        current_app.logger.error(f"Subscription not found for Stripe ID: {invoice_data['subscription']}")
        return
    
    # Update subscription status to reflect payment failure
    subscription.payment_status = 'failed'
    
    # Create invoice record
    invoice = Invoice(
        user_id=subscription.user_id,
        subscription_id=subscription.id,
        stripe_invoice_id=invoice_data['id'],
        amount=invoice_data['amount_due'] / 100,  # Convert from cents to dollars
        status='failed',
        invoice_date=datetime.fromtimestamp(invoice_data['created']),
        payment_method_id=subscription.payment_method_id
    )
    
    db.session.add(invoice)
    db.session.commit()
    
    current_app.logger.info(f"Invoice payment failed: {invoice.id}")

def handle_subscription_deleted(subscription_data):
    """Handle subscription cancellation event"""
    # Find subscription by Stripe ID
    subscription = Subscription.query.filter_by(stripe_subscription_id=subscription_data['id']).first()
    if not subscription:
        current_app.logger.error(f"Subscription not found for Stripe ID: {subscription_data['id']}")
        return
    
    # Update subscription status
    subscription.is_active = False
    subscription.end_date = datetime.fromtimestamp(subscription_data['ended_at']) if subscription_data.get('ended_at') else datetime.utcnow()
    
    db.session.commit()
    
    current_app.logger.info(f"Subscription cancelled: {subscription.id}")

@billing_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage():
    """Get user's current usage statistics"""
    user_id = get_jwt_identity()
    
    # Get active subscription
    subscription = Subscription.query.filter_by(user_id=user_id, is_active=True).first()
    if not subscription:
        return jsonify({"error": "No active subscription found"}), 404
    
    # Get subscription plan
    plan = subscription.plan
    
    # Get usage for current billing period
    from app.models.usage_record import UsageRecord
    from sqlalchemy import func
    
    # Calculate start of current billing period
    billing_start = subscription.get_current_period_start()
    
    # Get usage summary
    usage_summary = UsageRecord.query.with_entities(
        func.sum(UsageRecord.message_count).label('total_messages'),
        func.sum(UsageRecord.ai_response_count).label('total_ai_responses')
    ).filter(
        UsageRecord.user_id == user_id,
        UsageRecord.date >= billing_start
    ).first()
    
    # Format response
    response = {
        "current_period": {
            "start": billing_start.isoformat(),
            "end": subscription.get_current_period_end().isoformat()
        },
        "usage": {
            "messages": {
                "used": usage_summary.total_messages or 0,
                "limit": plan.monthly_message_limit or 'unlimited',
                "remaining": plan.monthly_message_limit - (usage_summary.total_messages or 0) if plan.monthly_message_limit else 'unlimited'
            },
            "ai_responses": {
                "used": usage_summary.total_ai_responses or 0,
                "limit": plan.monthly_ai_response_limit or 'unlimited',
                "remaining": plan.monthly_ai_response_limit - (usage_summary.total_ai_responses or 0) if plan.monthly_ai_response_limit else 'unlimited'
            }
        },
        "plan": {
            "name": plan.name,
            "price": plan.price,
            "billing_cycle": plan.billing_cycle
        }
    }
    
    return jsonify(response), 200