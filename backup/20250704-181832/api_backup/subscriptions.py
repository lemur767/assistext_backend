from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.subscription_service import SubscriptionService
from app.models.billing import Subscription
from app.models.signalwire_account import SignalWireAccount
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

@subscription_bp.route('/phone-numbers', methods=['GET'])
@jwt_required()
def get_phone_numbers():
    """Get available phone numbers for user"""
    user_id = get_jwt_identity()
    
    # Get user's SignalWire account
    signalwire_account = SignalWireAccount.query.join(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == 'active',
        SignalWireAccount.is_active == True
    ).first()
    
    if not signalwire_account:
        return jsonify({'error': 'No active SignalWire account found'}), 404
    
    phone_numbers = [phone.to_dict() for phone in signalwire_account.phone_numbers]
    
    return jsonify({
        'phone_numbers': phone_numbers,
        'account_info': {
            'monthly_limit': signalwire_account.monthly_limit,
            'current_usage': signalwire_account.current_usage
        }
    }), 200

@subscription_bp.route('/assign-number', methods=['POST'])
@jwt_required()
def assign_phone_number():
    """Assign phone number to a profile"""
    user_id = get_jwt_identity()
    data = request.json
    
    required_fields = ['phone_number_id', 'profile_id']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Get user's SignalWire account
    signalwire_account = SignalWireAccount.query.join(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.status == 'active'
    ).first()
    
    if not signalwire_account:
        return jsonify({'error': 'No active SignalWire account found'}), 404
    
    # Get phone number
    phone_number = signalwire_account.phone_numbers.filter_by(
        id=data['phone_number_id'],
        is_active=True,
        is_assigned=False
    ).first()
    
    if not phone_number:
        return jsonify({'error': 'Phone number not available'}), 404
    
    # Assign to profile
    phone_number.profile_id = data['profile_id']
    phone_number.is_assigned = True
    phone_number.assigned_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'phone_number': phone_number.to_dict()
    }), 200

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