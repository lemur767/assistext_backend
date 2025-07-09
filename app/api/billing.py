# app/api/billing.py
"""
Backend API endpoints for billing and subscription management
Corresponds to the BillingService frontend methods
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.payment import Payment, PaymentMethod, Invoice
from app.models.usage import Usage 
from app.models.billing_settings import BillingSettings
from app.extensions import db
from app.services.payment_processor import PaymentProcessor
from app.services.usage_tracker import UsageTracker
from app.services.invoice_generator import InvoiceGenerator
from app.utils.billing_helpers import BillingHelpers
from datetime import datetime, timedelta
from sqlalchemy import func, or_, and_
import stripe
import io
import csv
import json

billing_bp = Blueprint('billing', __name__)

# ============ SUBSCRIPTION MANAGEMENT ============

@billing_bp.route('/subscription', methods=['GET'])
@jwt_required()
def get_current_subscription():
    """Get current user's subscription details"""
    try:
        user_id = get_jwt_identity()
        
        subscription = Subscription.query.filter_by(
            user_id=user_id,
            status__in=['active', 'trialing', 'past_due']
        ).first()
        
        if not subscription:
            return jsonify({'error': 'No active subscription found'}), 404
        
        return jsonify({
            'success': True,
            'data': subscription.to_dict(include_relationships=True)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching subscription: {str(e)}")
        return jsonify({'error': 'Failed to fetch subscription'}), 500

@billing_bp.route('/subscriptions', methods=['POST'])
@jwt_required()
def create_subscription():
    """Create new subscription"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        # Validate required fields
        required_fields = ['plan_id', 'billing_cycle']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if user already has active subscription
        existing_subscription = Subscription.query.filter_by(
            user_id=user_id,
            status__in=['active', 'trialing']
        ).first()
        
        if existing_subscription:
            return jsonify({'error': 'User already has an active subscription'}), 400
        
        # Get plan details
        plan = SubscriptionPlan.query.get(data['plan_id'])
        if not plan or plan.status != 'active':
            return jsonify({'error': 'Invalid or inactive plan'}), 400
        
        # Calculate pricing
        amount = plan.monthly_price if data['billing_cycle'] == 'monthly' else plan.annual_price
        
        # Apply coupon if provided
        discount_amount = 0
        if data.get('coupon_code'):
            coupon_result = BillingHelpers.validate_coupon(data['coupon_code'], plan.id)
            if coupon_result['valid']:
                discount_amount = coupon_result.get('discount_amount', 0)
            else:
                return jsonify({'error': 'Invalid coupon code'}), 400
        
        # Process payment if payment method provided
        payment_method = None
        if data.get('payment_method_id'):
            payment_method = PaymentMethod.query.filter_by(
                id=data['payment_method_id'],
                user_id=user_id,
                status='active'
            ).first()
            
            if not payment_method:
                return jsonify({'error': 'Invalid payment method'}), 400
        
        # Create subscription
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            status='trialing' if plan.trial_period_days else 'active',
            billing_cycle=data['billing_cycle'],
            amount=amount - discount_amount,
            currency=plan.currency,
            discount_amount=discount_amount,
            auto_renew=data.get('auto_renew', True),
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(
                days=plan.trial_period_days or (30 if data['billing_cycle'] == 'monthly' else 365)
            ),
            trial_end=datetime.utcnow() + timedelta(days=plan.trial_period_days) if plan.trial_period_days else None
        )
        
        # Process initial payment if not in trial
        if not plan.trial_period_days and payment_method:
            payment_result = PaymentProcessor.process_payment(
                amount=amount - discount_amount,
                currency=plan.currency,
                payment_method_id=payment_method.id,
                description=f"Subscription to {plan.name}",
                metadata={'subscription_id': subscription.id}
            )
            
            if not payment_result['success']:
                return jsonify({'error': f"Payment failed: {payment_result['error']}"}), 400
        
        db.session.add(subscription)
        db.session.commit()
        
        # Initialize usage tracking
        UsageTracker.initialize_usage_for_subscription(subscription.id)
        
        return jsonify({
            'success': True,
            'data': subscription.to_dict(include_relationships=True),
            'message': 'Subscription created successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating subscription: {str(e)}")
        return jsonify({'error': 'Failed to create subscription'}), 500

@billing_bp.route('/subscriptions/<subscription_id>', methods=['PUT'])
@jwt_required()
def update_subscription(subscription_id):
    """Update existing subscription"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            user_id=user_id
        ).first()
        
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        # Handle plan change
        if 'plan_id' in data and data['plan_id'] != subscription.plan_id:
            new_plan = SubscriptionPlan.query.get(data['plan_id'])
            if not new_plan or new_plan.status != 'active':
                return jsonify({'error': 'Invalid plan'}), 400
            
            # Calculate proration
            proration_result = BillingHelpers.calculate_proration(
                subscription, new_plan, data.get('billing_cycle', subscription.billing_cycle)
            )
            
            subscription.plan_id = new_plan.id
            subscription.amount = proration_result['new_amount']
            
        # Update other fields
        if 'billing_cycle' in data:
            subscription.billing_cycle = data['billing_cycle']
        if 'auto_renew' in data:
            subscription.auto_renew = data['auto_renew']
        if 'pause_until' in data:
            subscription.pause_until = datetime.fromisoformat(data['pause_until']) if data['pause_until'] else None
        
        subscription.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': subscription.to_dict(include_relationships=True),
            'message': 'Subscription updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating subscription: {str(e)}")
        return jsonify({'error': 'Failed to update subscription'}), 500

@billing_bp.route('/subscriptions/<subscription_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_subscription(subscription_id):
    """Cancel subscription"""
    try:
        user_id = get_jwt_identity()
        data = request.json or {}
        
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            user_id=user_id
        ).first()
        
        if not subscription:
            return jsonify({'error': 'Subscription not found'}), 404
        
        if subscription.status in ['canceled', 'expired']:
            return jsonify({'error': 'Subscription already canceled'}), 400
        
        cancel_at_period_end = data.get('cancel_at_period_end', True)
        
        if cancel_at_period_end:
            subscription.cancel_at_period_end = True
            subscription.cancellation_reason = data.get('reason', '')
        else:
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
            subscription.cancellation_reason = data.get('reason', '')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': subscription.to_dict(include_relationships=True),
            'message': 'Subscription canceled successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error canceling subscription: {str(e)}")
        return jsonify({'error': 'Failed to cancel subscription'}), 500

# ============ SUBSCRIPTION PLANS ============

@billing_bp.route('/plans', methods=['GET'])
def get_subscription_plans():
    """Get all available subscription plans"""
    try:
        plans = SubscriptionPlan.query.filter_by(status='active').all()
        
        return jsonify({
            'success': True,
            'data': [plan.to_dict() for plan in plans]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching plans: {str(e)}")
        return jsonify({'error': 'Failed to fetch plans'}), 500

@billing_bp.route('/plans/<plan_id>', methods=['GET'])
def get_subscription_plan(plan_id):
    """Get specific subscription plan"""
    try:
        plan = SubscriptionPlan.query.filter_by(id=plan_id, status='active').first()
        
        if not plan:
            return jsonify({'error': 'Plan not found'}), 404
        
        return jsonify({
            'success': True,
            'data': plan.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching plan: {str(e)}")
        return jsonify({'error': 'Failed to fetch plan'}), 500

@billing_bp.route('/plans/compare', methods=['GET'])
def compare_plans():
    """Compare multiple subscription plans"""
    try:
        plan_ids = request.args.getlist('plan_ids')
        
        if not plan_ids:
            return jsonify({'error': 'No plan IDs provided'}), 400
        
        plans = SubscriptionPlan.query.filter(
            SubscriptionPlan.id.in_(plan_ids),
            SubscriptionPlan.status == 'active'
        ).all()
        
        return jsonify({
            'success': True,
            'data': [plan.to_dict() for plan in plans]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error comparing plans: {str(e)}")
        return jsonify({'error': 'Failed to compare plans'}), 500

# ============ PAYMENT METHODS ============

@billing_bp.route('/payment-methods', methods=['GET'])
@jwt_required()
def get_payment_methods():
    """Get all payment methods for user"""
    try:
        user_id = get_jwt_identity()
        
        payment_methods = PaymentMethod.query.filter_by(
            user_id=user_id,
            status='active'
        ).all()
        
        return jsonify({
            'success': True,
            'data': [method.to_dict() for method in payment_methods]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching payment methods: {str(e)}")
        return jsonify({'error': 'Failed to fetch payment methods'}), 500

@billing_bp.route('/payment-methods', methods=['POST'])
@jwt_required()
def add_payment_method():
    """Add new payment method"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        # Validate required fields
        if not data.get('token'):
            return jsonify({'error': 'Payment token required'}), 400
        
        # Process payment method with payment processor
        processor_result = PaymentProcessor.create_payment_method(
            user_id=user_id,
            token=data['token'],
            billing_address=data.get('billing_address')
        )
        
        if not processor_result['success']:
            return jsonify({'error': processor_result['error']}), 400
        
        # Create payment method record
        payment_method = PaymentMethod(
            user_id=user_id,
            type=data['type'],
            processor_id=processor_result['processor_id'],
            is_default=data.get('is_default', False),
            billing_address=data.get('billing_address'),
            status='active'
        )
        
        # Set card details if card type
        if data['type'] == 'card' and 'card_details' in processor_result:
            card = processor_result['card_details']
            payment_method.card_brand = card.get('brand')
            payment_method.card_last4 = card.get('last4')
            payment_method.card_exp_month = card.get('exp_month')
            payment_method.card_exp_year = card.get('exp_year')
        
        # If this is set as default, unset other defaults
        if payment_method.is_default:
            PaymentMethod.query.filter_by(user_id=user_id).update({'is_default': False})
        
        db.session.add(payment_method)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': payment_method.to_dict(),
            'message': 'Payment method added successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding payment method: {str(e)}")
        return jsonify({'error': 'Failed to add payment method'}), 500

# ============ PAYMENTS & TRANSACTIONS ============

@billing_bp.route('/payments', methods=['POST'])
@jwt_required()
def process_payment():
    """Process a payment"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        # Validate required fields
        required_fields = ['amount', 'currency']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Get payment method
        payment_method = None
        if data.get('payment_method_id'):
            payment_method = PaymentMethod.query.filter_by(
                id=data['payment_method_id'],
                user_id=user_id,
                status='active'
            ).first()
        else:
            # Use default payment method
            payment_method = PaymentMethod.query.filter_by(
                user_id=user_id,
                is_default=True,
                status='active'
            ).first()
        
        if not payment_method:
            return jsonify({'error': 'No valid payment method found'}), 400
        
        # Process payment
        payment_result = PaymentProcessor.process_payment(
            amount=data['amount'],
            currency=data['currency'],
            payment_method_id=payment_method.id,
            description=data.get('description', 'Payment'),
            pm_metadata=data.get('pm_metadata', {})
        )
        
        if not payment_result['success']:
            return jsonify({'error': f"Payment failed: {payment_result['error']}"}), 400
        
        # Create payment record
        payment = Payment(
            user_id=user_id,
            payment_method_id=payment_method.id,
            amount=data['amount'],
            currency=data['currency'],
            status='succeeded',
            processor_id=payment_result['processor_id'],
            description=data.get('description'),
            pay_metadata=data.get('pay_metadata'),
            processed_at=datetime.utcnow()
        )
        
        db.session.add(payment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': payment.to_dict(include_relationships=True),
            'message': 'Payment processed successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing payment: {str(e)}")
        return jsonify({'error': 'Failed to process payment'}), 500

@billing_bp.route('/payments', methods=['GET'])
@jwt_required()
def get_payment_history():
    """Get payment history"""
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        query = Payment.query.filter_by(user_id=user_id)
        
        # Apply filters
        if status:
            query = query.filter(Payment.status == status)
        if date_from:
            query = query.filter(Payment.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.filter(Payment.created_at <= datetime.fromisoformat(date_to))
        
        # Order by most recent first
        query = query.order_by(Payment.created_at.desc())
        
        # Paginate
        result = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'data': [payment.to_dict(include_relationships=True) for payment in result.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': result.total,
                'pages': result.pages,
                'has_next': result.has_next,
                'has_prev': result.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching payment history: {str(e)}")
        return jsonify({'error': 'Failed to fetch payment history'}), 500

# ============ INVOICES ============

@billing_bp.route('/invoices', methods=['GET'])
@jwt_required()
def get_invoices():
    """Get invoice history"""
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        status = request.args.get('status')
        
        query = Invoice.query.filter_by(user_id=user_id)
        
        # Apply filters
        if status:
            query = query.filter(Invoice.status == status)
        
        # Order by most recent first
        query = query.order_by(Invoice.created_at.desc())
        
        # Paginate
        result = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'data': [invoice.to_dict(include_relationships=True) for invoice in result.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': result.total,
                'pages': result.pages,
                'has_next': result.has_next,
                'has_prev': result.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching invoices: {str(e)}")
        return jsonify({'error': 'Failed to fetch invoices'}), 500

@billing_bp.route('/invoices/<invoice_id>/download', methods=['GET'])
@jwt_required()
def download_invoice(invoice_id):
    """Download invoice PDF"""
    try:
        user_id = get_jwt_identity()
        
        invoice = Invoice.query.filter_by(
            id=invoice_id,
            user_id=user_id
        ).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Generate PDF if not exists
        if not invoice.pdf_url:
            pdf_data = InvoiceGenerator.generate_pdf(invoice)
            invoice.pdf_url = f"invoices/{invoice.id}.pdf"
            db.session.commit()
        else:
            pdf_data = InvoiceGenerator.get_pdf(invoice.pdf_url)
        
        return send_file(
            io.BytesIO(pdf_data),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'invoice_{invoice.invoice_number}.pdf'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error downloading invoice: {str(e)}")
        return jsonify({'error': 'Failed to download invoice'}), 500

# ============ USAGE & LIMITS ============

@billing_bp.route('/usage/current', methods=['GET'])
@jwt_required()
def get_current_usage():
    """Get current usage metrics"""
    try:
        user_id = get_jwt_identity()
        
        # Get current subscription
        subscription = Subscription.query.filter_by(
            user_id=user_id,
            status__in=['active', 'trialing']
        ).first()
        
        if not subscription:
            return jsonify({'error': 'No active subscription found'}), 404
        
        # Get current usage
        usage = Usage.query.filter_by(
            subscription_id=subscription.id,
            period_start__lte=datetime.utcnow(),
            period_end__gte=datetime.utcnow()
        ).first()
        
        if not usage:
            # Initialize usage if not exists
            usage = UsageTracker.initialize_usage_for_subscription(subscription.id)
        
        return jsonify({
            'success': True,
            'data': usage.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching current usage: {str(e)}")
        return jsonify({'error': 'Failed to fetch usage'}), 500

@billing_bp.route('/usage/history', methods=['GET'])
@jwt_required()
def get_usage_history():
    """Get usage history"""
    try:
        user_id = get_jwt_identity()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        granularity = request.args.get('granularity', 'day')
        
        if not start_date or not end_date:
            return jsonify({'error': 'Start date and end date are required'}), 400
        
        # Get subscription
        subscription = Subscription.query.filter_by(
            user_id=user_id,
            status__in=['active', 'trialing', 'canceled']
        ).first()
        
        if not subscription:
            return jsonify({'error': 'No subscription found'}), 404
        
        # Get usage metrics
        usage_history = UsageTracker.get_usage_history(
            subscription.id,
            start_date,
            end_date,
            granularity
        )
        
        return jsonify({
            'success': True,
            'data': usage_history
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching usage history: {str(e)}")
        return jsonify({'error': 'Failed to fetch usage history'}), 500

# ============ BILLING SETTINGS ============

@billing_bp.route('/settings', methods=['GET'])
@jwt_required()
def get_billing_settings():
    """Get billing settings"""
    try:
        user_id = get_jwt_identity()
        
        settings = BillingSettings.query.filter_by(user_id=user_id).first()
        
        if not settings:
            # Create default settings
            settings = BillingSettings.create_default(user_id)
            db.session.add(settings)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'data': settings.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching billing settings: {str(e)}")
        return jsonify({'error': 'Failed to fetch billing settings'}), 500

@billing_bp.route('/settings', methods=['PUT'])
@jwt_required()
def update_billing_settings():
    """Update billing settings"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        settings = BillingSettings.query.filter_by(user_id=user_id).first()
        
        if not settings:
            settings = BillingSettings.create_default(user_id)
            db.session.add(settings)
        
        # Update settings
        updatable_fields = [
            'auto_pay', 'billing_email', 'billing_address',
            'invoice_delivery', 'invoice_format', 'notifications',
            'usage_alert_thresholds', 'tax_id', 'tax_exempt',
            'currency', 'locale', 'timezone'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(settings, field, data[field])
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': settings.to_dict(),
            'message': 'Billing settings updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating billing settings: {str(e)}")
        return jsonify({'error': 'Failed to update billing settings'}), 500

# ============ ANALYTICS & REPORTING ============

@billing_bp.route('/analytics', methods=['GET'])
@jwt_required()
def get_billing_analytics():
    """Get billing analytics"""
    try:
        user_id = get_jwt_identity()
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            # Default to last 90 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)
        else:
            start_date = datetime.fromisoformat(start_date)
            end_date = datetime.fromisoformat(end_date)
        
        analytics = BillingHelpers.generate_analytics(user_id, start_date, end_date)
        
        return jsonify({
            'success': True,
            'data': analytics
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching billing analytics: {str(e)}")
        return jsonify({'error': 'Failed to fetch billing analytics'}), 500

# ============ UTILITY ENDPOINTS ============

@billing_bp.route('/coupons/validate', methods=['POST'])
def validate_coupon():
    """Validate coupon code"""
    try:
        data = request.json
        coupon_code = data.get('coupon_code')
        plan_id = data.get('plan_id')
        
        if not coupon_code:
            return jsonify({'error': 'Coupon code required'}), 400
        
        result = BillingHelpers.validate_coupon(coupon_code, plan_id)
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error validating coupon: {str(e)}")
        return jsonify({'error': 'Failed to validate coupon'}), 500

@billing_bp.route('/portal', methods=['POST'])
@jwt_required()
def get_billing_portal():
    """Get billing portal URL"""
    try:
        user_id = get_jwt_identity()
        data = request.json or {}
        return_url = data.get('return_url', request.host_url)
        
        portal_url = PaymentProcessor.create_billing_portal_session(
            user_id=user_id,
            return_url=return_url
        )
        
        return jsonify({
            'success': True,
            'data': {
                'url': portal_url,
                'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat()
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error creating billing portal: {str(e)}")
        return jsonify({'error': 'Failed to create billing portal'}), 500

@billing_bp.route('/export', methods=['GET'])
@jwt_required()
def export_billing_data():
    """Export billing data"""
    try:
        user_id = get_jwt_identity()
        export_type = request.args.get('type', 'invoices')
        format_type = request.args.get('format', 'csv')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Generate export data
        export_data = BillingHelpers.generate_export_data(
            user_id=user_id,
            export_type=export_type,
            start_date=start_date,
            end_date=end_date
        )
        
        if format_type == 'csv':
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=export_data[0].keys() if export_data else [])
            writer.writeheader()
            writer.writerows(export_data)
            
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'billing_{export_type}_export.csv'
            )
        
        elif format_type == 'json':
            return send_file(
                io.BytesIO(json.dumps(export_data, indent=2).encode('utf-8')),
                mimetype='application/json',
                as_attachment=True,
                download_name=f'billing_{export_type}_export.json'
            )
        
        else:
            return jsonify({'error': 'Unsupported format'}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error exporting billing data: {str(e)}")
        return jsonify({'error': 'Failed to export billing data'}), 500

# ============ WEBHOOK ENDPOINTS ============

@billing_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    try:
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        
        # Verify webhook signature
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
            )
        except ValueError:
            return jsonify({'error': 'Invalid payload'}), 400
        except stripe.error.SignatureVerificationError:
            return jsonify({'error': 'Invalid signature'}), 400
        
        # Handle the event
        result = PaymentProcessor.handle_webhook_event(event)
        
        if result['success']:
            return jsonify({'received': True}), 200
        else:
            return jsonify({'error': result['error']}), 400
        
    except Exception as e:
        current_app.logger.error(f"Error handling webhook: {str(e)}")
        return jsonify({'error': 'Webhook handling failed'}), 500