from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.billing import (
    Subscription, SubscriptionPlan, Invoice, PaymentMethod,
    get_user_invoices, get_user_payment_methods
)
from app.extensions import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

billing_bp = Blueprint('billing', __name__)


@billing_bp.route('/subscription', methods=['GET'])
@jwt_required()
def get_user_subscription():
    """Get user's current subscription"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get active subscription
        subscription = user.get_active_subscription()
        
        if not subscription:
            return jsonify({"subscription": None}), 200
        
        return jsonify({
            "subscription": subscription.to_dict(),
            "plan": subscription.plan.to_dict(),
            "usage_limits": subscription.get_usage_limits()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        return jsonify({"error": "Internal server error"}), 500


@billing_bp.route('/plans', methods=['GET'])
def get_subscription_plans():
    """Get all available subscription plans"""
    try:
        plans = SubscriptionPlan.query.filter_by(is_active=True).order_by(
            SubscriptionPlan.sort_order.asc()
        ).all()
        
        return jsonify([plan.to_dict() for plan in plans]), 200
        
    except Exception as e:
        logger.error(f"Error getting subscription plans: {e}")
        return jsonify({"error": "Internal server error"}), 500


@billing_bp.route('/invoices', methods=['GET'])
@jwt_required()
def get_invoices():
    """Get user's invoices"""
    try:
        user_id = get_jwt_identity()
        
        # Get query parameters
        limit = request.args.get('limit', type=int)
        status = request.args.get('status')
        
        # Get invoices
        invoices = get_user_invoices(user_id, limit=limit, status=status)
        
        return jsonify([invoice.to_dict() for invoice in invoices]), 200
        
    except Exception as e:
        logger.error(f"Error getting invoices: {e}")
        return jsonify({"error": "Internal server error"}), 500


@billing_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
@jwt_required()
def get_invoice(invoice_id):
    """Get specific invoice details"""
    try:
        user_id = get_jwt_identity()
        
        # Find invoice and verify ownership
        invoice = db.session.query(Invoice).join(Subscription).filter(
            Invoice.id == invoice_id,
            Subscription.user_id == user_id
        ).first()
        
        if not invoice:
            return jsonify({"error": "Invoice not found"}), 404
        
        return jsonify(invoice.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error getting invoice: {e}")
        return jsonify({"error": "Internal server error"}), 500


@billing_bp.route('/payment-methods', methods=['GET'])
@jwt_required()
def get_payment_methods():
    """Get user's payment methods"""
    try:
        user_id = get_jwt_identity()
        
        payment_methods = get_user_payment_methods(user_id, active_only=True)
        
        return jsonify([pm.to_dict() for pm in payment_methods]), 200
        
    except Exception as e:
        logger.error(f"Error getting payment methods: {e}")
        return jsonify({"error": "Internal server error"}), 500


@billing_bp.route('/payment-methods/<int:pm_id>/set-default', methods=['POST'])
@jwt_required()
def set_default_payment_method(pm_id):
    """Set a payment method as default"""
    try:
        user_id = get_jwt_identity()
        
        # Find payment method and verify ownership
        payment_method = PaymentMethod.query.filter_by(
            id=pm_id,
            user_id=user_id,
            is_active=True
        ).first()
        
        if not payment_method:
            return jsonify({"error": "Payment method not found"}), 404
        
        # Set as default
        payment_method.set_as_default()
        
        return jsonify({
            "message": "Payment method set as default",
            "payment_method": payment_method.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error setting default payment method: {e}")
        return jsonify({"error": "Internal server error"}), 500


@billing_bp.route('/payment-methods/<int:pm_id>', methods=['DELETE'])
@jwt_required()
def delete_payment_method(pm_id):
    """Delete/deactivate a payment method"""
    try:
        user_id = get_jwt_identity()
        
        # Find payment method and verify ownership
        payment_method = PaymentMethod.query.filter_by(
            id=pm_id,
            user_id=user_id
        ).first()
        
        if not payment_method:
            return jsonify({"error": "Payment method not found"}), 404
        
        # Deactivate the payment method
        payment_method.deactivate()
        
        return jsonify({"message": "Payment method deleted"}), 200
        
    except Exception as e:
        logger.error(f"Error deleting payment method: {e}")
        return jsonify({"error": "Internal server error"}), 500


@billing_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage_statistics():
    """Get user's usage statistics"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get active subscription
        subscription = user.get_active_subscription()
        
        if not subscription:
            return jsonify({"error": "No active subscription"}), 404
        
        # Get usage statistics
        from app.models.profile import Profile
        from app.models.message import Message
        from datetime import datetime, timedelta
        
        # Current month usage
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        profiles_count = Profile.query.filter_by(user_id=user_id).count()
        
        # Messages sent this month
        messages_this_month = db.session.query(Message).join(Profile).filter(
            Profile.user_id == user_id,
            Message.is_incoming == False,
            Message.timestamp >= current_month_start
        ).count()
        
        # AI responses this month
        ai_responses_this_month = db.session.query(Message).join(Profile).filter(
            Profile.user_id == user_id,
            Message.is_incoming == False,
            Message.ai_generated == True,
            Message.timestamp >= current_month_start
        ).count()
        
        usage_stats = {
            "subscription": subscription.to_dict(),
            "usage_limits": subscription.get_usage_limits(),
            "current_usage": {
                "profiles": profiles_count,
                "messages_this_month": messages_this_month,
                "ai_responses_this_month": ai_responses_this_month,
                "billing_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                "billing_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None
            }
        }
        
        return jsonify(usage_stats), 200
        
    except Exception as e:
        logger.error(f"Error getting usage statistics: {e}")
        return jsonify({"error": "Internal server error"}), 500


@billing_bp.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    try:
        import stripe
        import os
        
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        
        endpoint_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        if not endpoint_secret:
            logger.error("Stripe webhook secret not configured")
            return jsonify({"error": "Webhook not configured"}), 400
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError:
            logger.error("Invalid payload in Stripe webhook")
            return jsonify({"error": "Invalid payload"}), 400
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid signature in Stripe webhook")
            return jsonify({"error": "Invalid signature"}), 400
        
        # Handle the event
        if event['type'] == 'invoice.payment_succeeded':
            handle_invoice_payment_succeeded(event['data']['object'])
        elif event['type'] == 'invoice.payment_failed':
            handle_invoice_payment_failed(event['data']['object'])
        elif event['type'] == 'customer.subscription.updated':
            handle_subscription_updated(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            handle_subscription_deleted(event['data']['object'])
        elif event['type'] == 'invoice.created':
            handle_invoice_created(event['data']['object'])
        else:
            logger.info(f"Unhandled Stripe webhook event type: {event['type']}")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Error handling Stripe webhook: {e}")
        return jsonify({"error": "Webhook processing failed"}), 500


def handle_invoice_payment_succeeded(stripe_invoice):
    """Handle successful invoice payment"""
    try:
        # Find the invoice in our database
        invoice = Invoice.query.filter_by(
            stripe_invoice_id=stripe_invoice['id']
        ).first()
        
        if invoice:
            # Mark as paid
            invoice.mark_as_paid(
                amount_paid=stripe_invoice['amount_paid'] / 100,
                paid_at=datetime.fromtimestamp(stripe_invoice['status_transitions']['paid_at'])
            )
            logger.info(f"Invoice {invoice.id} marked as paid")
        else:
            # Create invoice if it doesn't exist
            from app.models.invoice import create_invoice_from_stripe
            import stripe
            
            stripe_invoice_obj = stripe.Invoice.retrieve(stripe_invoice['id'])
            invoice = create_invoice_from_stripe(stripe_invoice_obj)
            logger.info(f"Created and marked invoice {invoice.id} as paid")
        
    except Exception as e:
        logger.error(f"Error handling invoice payment succeeded: {e}")


def handle_invoice_payment_failed(stripe_invoice):
    """Handle failed invoice payment"""
    try:
        # Find the invoice
        invoice = Invoice.query.filter_by(
            stripe_invoice_id=stripe_invoice['id']
        ).first()
        
        if invoice:
            invoice.status = 'payment_failed'
            db.session.commit()
            
            # TODO: Send notification to user about failed payment
            logger.warning(f"Payment failed for invoice {invoice.id}")
        
    except Exception as e:
        logger.error(f"Error handling invoice payment failed: {e}")


def handle_subscription_updated(stripe_subscription):
    """Handle subscription updates"""
    try:
        # Find the subscription
        subscription = Subscription.query.filter_by(
            stripe_subscription_id=stripe_subscription['id']
        ).first()
        
        if subscription:
            # Update subscription details
            subscription.status = stripe_subscription['status']
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription['current_period_start']
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription['current_period_end']
            )
            subscription.cancel_at_period_end = stripe_subscription.get('cancel_at_period_end', False)
            
            db.session.commit()
            logger.info(f"Updated subscription {subscription.id}")
        
    except Exception as e:
        logger.error(f"Error handling subscription updated: {e}")


def handle_subscription_deleted(stripe_subscription):
    """Handle subscription cancellation"""
    try:
        # Find the subscription
        subscription = Subscription.query.filter_by(
            stripe_subscription_id=stripe_subscription['id']
        ).first()
        
        if subscription:
            subscription.status = 'cancelled'
            db.session.commit()
            
            # TODO: Disable user's profiles or downgrade features
            logger.info(f"Cancelled subscription {subscription.id}")
        
    except Exception as e:
        logger.error(f"Error handling subscription deleted: {e}")


def handle_invoice_created(stripe_invoice):
    """Handle new invoice creation"""
    try:
        # Check if invoice already exists
        existing_invoice = Invoice.query.filter_by(
            stripe_invoice_id=stripe_invoice['id']
        ).first()
        
        if not existing_invoice:
            # Create new invoice
            from app.models.invoice import create_invoice_from_stripe
            import stripe
            
            stripe_invoice_obj = stripe.Invoice.retrieve(stripe_invoice['id'])
            invoice = create_invoice_from_stripe(stripe_invoice_obj)
            logger.info(f"Created invoice {invoice.id} from Stripe webhook")
        
    except Exception as e:
        logger.error(f"Error handling invoice created: {e}")


@billing_bp.route('/create-setup-intent', methods=['POST'])
@jwt_required()
def create_setup_intent():
    """Create a Stripe SetupIntent for adding payment methods"""
    try:
        import stripe
        import os
        
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
        
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Create or get Stripe customer
        stripe_customer_id = None
        
        # Check if user has existing subscription with customer ID
        subscription = user.get_active_subscription()
        if subscription and subscription.stripe_customer_id:
            stripe_customer_id = subscription.stripe_customer_id
        else:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip() or user.username,
                metadata={'user_id': user.id}
            )
            stripe_customer_id = customer.id
        
        # Create SetupIntent
        setup_intent = stripe.SetupIntent.create(
            customer=stripe_customer_id,
            payment_method_types=['card'],
            usage='off_session'
        )
        
        return jsonify({
            "client_secret": setup_intent.client_secret,
            "setup_intent_id": setup_intent.id
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating setup intent: {e}")
        return jsonify({"error": "Could not create setup intent"}), 500


@billing_bp.route('/confirm-payment-method', methods=['POST'])
@jwt_required()
def confirm_payment_method():
    """Confirm and save a payment method after SetupIntent completion"""
    try:
        import stripe
        import os
        
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
        
        data = request.json
        setup_intent_id = data.get('setup_intent_id')
        
        if not setup_intent_id:
            return jsonify({"error": "Setup intent ID required"}), 400
        
        user_id = get_jwt_identity()
        
        # Retrieve the SetupIntent
        setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
        
        if setup_intent.status != 'succeeded':
            return jsonify({"error": "Setup intent not completed"}), 400
        
        # Retrieve the payment method
        payment_method = stripe.PaymentMethod.retrieve(setup_intent.payment_method)
        
        # Save to our database
        from app.models.payment_method import create_payment_method_from_stripe
        
        saved_pm = create_payment_method_from_stripe(user_id, payment_method)
        
        # Set as default if it's the first payment method
        user_payment_methods = get_user_payment_methods(user_id)
        if len(user_payment_methods) == 1:
            saved_pm.set_as_default()
        
        return jsonify({
            "message": "Payment method saved successfully",
            "payment_method": saved_pm.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error confirming payment method: {e}")
        return jsonify({"error": "Could not save payment method"}), 500


@billing_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for billing service"""
    return jsonify({"status": "healthy", "service": "billing"}), 200
