
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields

from app.services import get_billing_service
from app.utils.validators import validate_request_json

billing_bp = Blueprint('billing', __name__)

class AddPaymentMethodSchema(Schema):
    payment_method_id = fields.Str(required=True)
    is_default = fields.Bool(missing=False)

class CreateSubscriptionSchema(Schema):
    plan_id = fields.Int(required=True)
    billing_cycle = fields.Str(validate=lambda x: x in ['monthly', 'annual'], missing='monthly')

@billing_bp.route('/subscription', methods=['GET'])
@jwt_required()
def get_subscription():
    """Get user's current subscription"""
    try:
        user_id = get_jwt_identity()
        billing_service = get_billing_service()
        
        result = billing_service.get_user_subscription(user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'subscription': result['subscription'],
                'has_subscription': result['has_subscription']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Get subscription error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch subscription'
        }), 500

@billing_bp.route('/subscription', methods=['POST'])
@jwt_required()
@validate_request_json(CreateSubscriptionSchema())
def create_subscription():
    """Create new subscription"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        billing_service = get_billing_service()
        
        result = billing_service.create_subscription(
            user_id=user_id,
            plan_id=data['plan_id'],
            billing_cycle=data['billing_cycle']
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'subscription': result['subscription']
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Create subscription error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to create subscription'
        }), 500

@billing_bp.route('/subscription/cancel', methods=['POST'])
@jwt_required()
def cancel_subscription():
    """Cancel user's subscription"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        reason = data.get('reason', 'User requested')
        
        billing_service = get_billing_service()
        result = billing_service.cancel_subscription(user_id, reason)
        
        if result['success']:
            return jsonify({
                'success': True,
                'subscription': result['subscription'],
                'message': result['message']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Cancel subscription error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to cancel subscription'
        }), 500

@billing_bp.route('/payment-methods', methods=['GET'])
@jwt_required()
def get_payment_methods():
    """Get user's payment methods"""
    try:
        user_id = get_jwt_identity()
        billing_service = get_billing_service()
        
        result = billing_service.get_payment_methods(user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'payment_methods': result['payment_methods']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Get payment methods error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch payment methods'
        }), 500

@billing_bp.route('/payment-methods', methods=['POST'])
@jwt_required()
@validate_request_json(AddPaymentMethodSchema())
def add_payment_method():
    """Add payment method"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        billing_service = get_billing_service()
        
        result = billing_service.add_payment_method(user_id, data)
        
        if result['success']:
            return jsonify({
                'success': True,
                'payment_method': result['payment_method']
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Add payment method error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to add payment method'
        }), 500

@billing_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage():
    """Get user's usage summary"""
    try:
        user_id = get_jwt_identity()
        days = request.args.get('days', 30, type=int)
        
        billing_service = get_billing_service()
        result = billing_service.get_usage_summary(user_id, days)
        
        if result['success']:
            return jsonify({
                'success': True,
                'usage_summary': result['usage_summary']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Get usage error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch usage'
        }), 500

@billing_bp.route('/usage/limits', methods=['GET'])
@jwt_required()
def check_usage_limits():
    """Check user's usage limits"""
    try:
        user_id = get_jwt_identity()
        billing_service = get_billing_service()
        
        result = billing_service.check_usage_limits(user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'within_limits': result['within_limits'],
                'limits': result.get('limits'),
                'current_usage': result.get('current_usage'),
                'reason': result.get('reason')
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Check usage limits error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to check usage limits'
        }), 500

@billing_bp.route('/plans', methods=['GET'])
def get_subscription_plans():
    """Get available subscription plans"""
    try:
        from app.models import SubscriptionPlan
        
        plans = SubscriptionPlan.query.filter_by(status='active')\
            .order_by(SubscriptionPlan.sort_order, SubscriptionPlan.monthly_price).all()
        
        return jsonify({
            'success': True,
            'plans': [plan.to_dict() for plan in plans]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Get plans error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch plans'
        }), 500

@billing_bp.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    try:
        payload = request.get_data()
        signature = request.headers.get('stripe-signature')
        
        billing_service = get_billing_service()
        result = billing_service.process_stripe_webhook(payload, signature)
        
        if result['success']:
            return jsonify({'received': True}), 200
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        current_app.logger.error(f"Stripe webhook error: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 400