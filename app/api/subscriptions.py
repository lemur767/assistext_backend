from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import Subscription
from app.services.billing_service import get_billing_service 

from app.extensions import db

subscription_bp = Blueprint('subscription', __name__)

@subscription_bp.route('/create', methods=['POST'])
@jwt_required()
def create_subscription():
    """Create new subscription with SignalWire provisioning"""
    user_id = get_jwt_identity()
    data = request.json
    
    required_fields = ['plan_id']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if user already has active subscription
    existing_subscription = Subscription.query.filter_by(
        user_id=user_id,
        status='active'
    ).first()
    
    if existing_subscription:
        return jsonify({'error': 'User already has active subscription'}), 400
    
    result = SubscriptionService.create_subscription_with_signalwire(
        user_id=user_id,
        plan_id=data['plan_id'],
        stripe_subscription_id=data.get('stripe_subscription_id')
    )
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400

@subscription_bp.route('/current', methods=['GET'])
@jwt_required()
def get_current_subscription():
    """Get current user subscription with SignalWire details"""
    user_id = get_jwt_identity()
    
    subscription = Subscription.query.filter_by(
        user_id=user_id,
        status='active'
    ).first()
    
    if not subscription:
        return jsonify({'error': 'No active subscription found'}), 404
    
    response_data = {
        'subscription': subscription.to_dict(),
        'signalwire_account': None,
        'phone_numbers': []
    }
    
    if subscription.signalwire_account:
        signalwire_account = subscription.signalwire_account
        response_data['signalwire_account'] = signalwire_account.to_dict()
        response_data['phone_numbers'] = [
            phone.to_dict() for phone in signalwire_account.phone_numbers
        ]
    
    return jsonify(response_data), 200



@subscription_bp.route('/cancel', methods=['POST'])
@jwt_required()
def cancel_subscription():
    """Cancel current subscription"""
    user_id = get_jwt_identity()
    
    subscription = Subscription.query.filter_by(
        user_id=user_id,
        status='active'
    ).first()
    
    if not subscription:
        return jsonify({'error': 'No active subscription found'}), 404
    
    result = SubscriptionService.cancel_subscription(subscription.id)
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400