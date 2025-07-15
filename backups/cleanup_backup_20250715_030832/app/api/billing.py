

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import func, or_, and_

# Create blueprint
billing_bp = Blueprint('billing', __name__)

# Import models after blueprint creation to prevent circular imports
def get_models():
    """Lazy import models to prevent circular imports"""
    from app.models.user import User
    from app.models.subscription import Subscription, SubscriptionPlan
    from app.models.billing import PaymentMethod, Payment, Invoice, InvoiceItem
    from app.models.credit_transaction import CreditTransaction
    from app.models.billing_settings import BillingSettings
    from app.extensions import db
    
    return {
        'User': User,
        'Subscription': Subscription,
        'SubscriptionPlan': SubscriptionPlan,
        'PaymentMethod': PaymentMethod,
        'Payment': Payment,
        'Invoice': Invoice,
        'InvoiceItem': InvoiceItem,
        'CreditTransaction': CreditTransaction,
        'BillingSettings': BillingSettings,
        'db': db
    }

# ============ SUBSCRIPTION MANAGEMENT ============

@billing_bp.route('/subscription', methods=['GET'])
@jwt_required()
def get_current_subscription():
    """Get current user's subscription details"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        
        subscription = models['Subscription'].query.filter_by(
            user_id=user_id
        ).filter(
            models['Subscription'].status.in_(['active', 'trialing', 'past_due'])
        ).first()
        
        if not subscription:
            return jsonify({'error': 'No active subscription found'}), 404
        
        return jsonify({
            'success': True,
            'data': subscription.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching subscription: {str(e)}")
        return jsonify({'error': 'Failed to fetch subscription'}), 500


@billing_bp.route('/subscriptions', methods=['POST'])
@jwt_required()
def create_subscription():
    """Create new subscription"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        data = request.json
        
        # Validate required fields
        required_fields = ['plan_id', 'billing_cycle']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if user already has active subscription
        existing_subscription = models['Subscription'].query.filter_by(
            user_id=user_id
        ).filter(
            models['Subscription'].status.in_(['active', 'trialing'])
        ).first()
        
        if existing_subscription:
            return jsonify({'error': 'User already has an active subscription'}), 400
        
        # Validate plan exists
        plan = models['SubscriptionPlan'].query.get(data['plan_id'])
        if not plan:
            return jsonify({'error': 'Invalid plan ID'}), 400
        
        # Create subscription
        subscription = models['Subscription'](
            user_id=user_id,
            plan_id=data['plan_id'],
            billing_cycle=data['billing_cycle'],
            status='active',
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30)
        )
        
        models['db'].session.add(subscription)
        models['db'].session.commit()
        
        return jsonify({
            'success': True,
            'data': subscription.to_dict()
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Error creating subscription: {str(e)}")
        models['db'].session.rollback()
        return jsonify({'error': 'Failed to create subscription'}), 500


# ============ PAYMENT METHODS ============

@billing_bp.route('/payment-methods', methods=['GET'])
@jwt_required()
def get_payment_methods():
    """Get user's payment methods"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        
        payment_methods = models['PaymentMethod'].query.filter_by(
            user_id=user_id,
            status='active'
        ).order_by(models['PaymentMethod'].is_default.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [pm.to_dict() for pm in payment_methods]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching payment methods: {str(e)}")
        return jsonify({'error': 'Failed to fetch payment methods'}), 500


@billing_bp.route('/payment-methods', methods=['POST'])
@jwt_required()
def add_payment_method():
    """Add new payment method"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        data = request.json
        
        # Validate required fields
        required_fields = ['type', 'stripe_payment_method_id']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Create payment method
        payment_method = models['PaymentMethod'](
            user_id=user_id,
            type=data['type'],
            stripe_payment_method_id=data['stripe_payment_method_id'],
            is_default=data.get('is_default', False),
            card_brand=data.get('card_brand'),
            card_last4=data.get('card_last4'),
            card_exp_month=data.get('card_exp_month'),
            card_exp_year=data.get('card_exp_year'),
            billing_address=data.get('billing_address')
        )
        
        models['db'].session.add(payment_method)
        models['db'].session.commit()
        
        return jsonify({
            'success': True,
            'data': payment_method.to_dict()
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Error adding payment method: {str(e)}")
        models['db'].session.rollback()
        return jsonify({'error': 'Failed to add payment method'}), 500


@billing_bp.route('/payment-methods/<int:payment_method_id>', methods=['DELETE'])
@jwt_required()
def delete_payment_method(payment_method_id):
    """Delete payment method"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        
        payment_method = models['PaymentMethod'].query.filter_by(
            id=payment_method_id,
            user_id=user_id
        ).first()
        
        if not payment_method:
            return jsonify({'error': 'Payment method not found'}), 404
        
        # Mark as inactive instead of deleting
        payment_method.status = 'inactive'
        models['db'].session.commit()
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error deleting payment method: {str(e)}")
        models['db'].session.rollback()
        return jsonify({'error': 'Failed to delete payment method'}), 500


# ============ INVOICES ============

@billing_bp.route('/invoices', methods=['GET'])
@jwt_required()
def get_invoices():
    """Get user's invoices"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status = request.args.get('status')
        
        # Build query
        query = models['Invoice'].query.filter_by(user_id=user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        # Paginate
        invoices = query.order_by(models['Invoice'].created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'data': [invoice.to_dict() for invoice in invoices.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': invoices.total,
                'pages': invoices.pages
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching invoices: {str(e)}")
        return jsonify({'error': 'Failed to fetch invoices'}), 500


@billing_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
@jwt_required()
def get_invoice(invoice_id):
    """Get specific invoice"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        
        invoice = models['Invoice'].query.filter_by(
            id=invoice_id,
            user_id=user_id
        ).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        return jsonify({
            'success': True,
            'data': invoice.to_dict(include_items=True)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching invoice: {str(e)}")
        return jsonify({'error': 'Failed to fetch invoice'}), 500


# ============ BILLING SETTINGS ============

@billing_bp.route('/settings', methods=['GET'])
@jwt_required()
def get_billing_settings():
    """Get user's billing settings"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        
        settings = models['BillingSettings'].query.filter_by(user_id=user_id).first()
        
        if not settings:
            # Create default settings
            settings = models['BillingSettings'].create_default(user_id)
            models['db'].session.add(settings)
            models['db'].session.commit()
        
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
    """Update user's billing settings"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        data = request.json
        
        settings = models['BillingSettings'].query.filter_by(user_id=user_id).first()
        
        if not settings:
            settings = models['BillingSettings'].create_default(user_id)
            models['db'].session.add(settings)
        
        # Update fields
        if 'auto_pay' in data:
            settings.auto_pay = data['auto_pay']
        if 'billing_email' in data:
            settings.billing_email = data['billing_email']
        if 'billing_address' in data:
            settings.billing_address = data['billing_address']
        if 'notifications' in data:
            settings.notifications = data['notifications']
        
        settings.updated_at = datetime.utcnow()
        models['db'].session.commit()
        
        return jsonify({
            'success': True,
            'data': settings.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error updating billing settings: {str(e)}")
        models['db'].session.rollback()
        return jsonify({'error': 'Failed to update billing settings'}), 500


# ============ USAGE AND CREDITS ============

@billing_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage():
    """Get user's usage statistics"""
    try:
        models = get_models()
        user_id = get_jwt_identity()
        
        # Get current month usage
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # This would typically query a usage tracking table
        usage_stats = {
            'sms_sent': 0,
            'ai_responses': 0,
            'storage_used': 0,
            'api_calls': 0,
            'period_start': current_month.isoformat(),
            'period_end': (current_month + timedelta(days=32)).replace(day=1).isoformat()
        }
        
        return jsonify({
            'success': True,
            'data': usage_stats
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error fetching usage: {str(e)}")
        return jsonify({'error': 'Failed to fetch usage'}), 500


# ============ HEALTH CHECK ============

@billing_bp.route('/health', methods=['GET'])
def billing_health():
    """Billing API health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'billing',
        'timestamp': datetime.utcnow().isoformat()
    }), 200