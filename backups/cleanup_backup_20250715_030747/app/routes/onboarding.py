# app/routes/onboarding.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import logging

from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.billing import PaymentMethod
from app.services.signalwire_service import SignalWireService
from app.extensions import db
from app.utils.validators import validate_json_data

logger = logging.getLogger(__name__)

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/api/onboarding')

@onboarding_bp.route('/status', methods=['GET'])
@jwt_required()
def get_onboarding_status():
    """Get user's onboarding status and requirements"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check subscription status
        subscription = Subscription.query.filter_by(
            user_id=user.id,
            status='active'
        ).first() or Subscription.query.filter_by(
            user_id=user.id,
            status='trialing'
        ).first()
        
        # Check payment method
        payment_method = PaymentMethod.query.filter_by(
            user_id=user.id,
            status='active',
            is_default=True
        ).first()
        
        onboarding_status = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'is_trial_user': subscription and subscription.status == 'trialing',
            'has_active_subscription': subscription and subscription.status == 'active',
            'has_valid_payment_method': payment_method is not None,
            'signalwire_setup_completed': user.signalwire_setup_completed,
            'signalwire_phone_number': user.signalwire_phone_number,
            'trial_phone_expires_at': user.trial_phone_expires_at.isoformat() if user.trial_phone_expires_at else None,
            'requires_onboarding': False
        }
        
        # Determine if onboarding is required
        if not subscription:
            onboarding_status['requires_onboarding'] = True
            onboarding_status['onboarding_step'] = 'subscription_required'
        elif not payment_method:
            onboarding_status['requires_onboarding'] = True
            onboarding_status['onboarding_step'] = 'payment_method_required'
        elif not user.signalwire_setup_completed:
            onboarding_status['requires_onboarding'] = True
            onboarding_status['onboarding_step'] = 'phone_setup_required'
        
        return jsonify({
            'success': True,
            'onboarding_status': onboarding_status
        })
        
    except Exception as e:
        logger.error(f"Failed to get onboarding status: {e}")
        return jsonify({'error': 'Failed to get onboarding status'}), 500


@onboarding_bp.route('/search-numbers', methods=['POST'])
@jwt_required()
def search_phone_numbers():
    """Search for available phone numbers in Ontario"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate user has payment method and selected plan
        payment_method = PaymentMethod.query.filter_by(
            user_id=user.id,
            status='active',
            is_default=True
        ).first()
        
        if not payment_method:
            return jsonify({
                'error': 'Valid payment method required before phone number setup'
            }), 400
        
        # Check if user already has SignalWire setup
        if user.signalwire_setup_completed:
            return jsonify({
                'error': 'Phone number already configured',
                'current_number': user.signalwire_phone_number
            }), 400
        
        # Validate request data
        schema = {
            'area_code': {'type': 'string', 'required': False},
            'locality': {'type': 'string', 'required': False},
            'limit': {'type': 'integer', 'required': False, 'min': 1, 'max': 10}
        }
        
        data = request.get_json() or {}
        validation_error = validate_json_data(data, schema)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Initialize SignalWire service
        signalwire_service = SignalWireService()
        
        # Search for numbers (Ontario only)
        result = signalwire_service.search_available_numbers(
            country='CA',
            area_code=data.get('area_code'),
            locality=data.get('locality', 'Toronto'),  # Default to Toronto
            limit=data.get('limit', 5)
        )
        
        if not result['success']:
            return jsonify({
                'error': result['error']
            }), 400
        
        return jsonify({
            'success': True,
            'available_numbers': result['available_numbers'],
            'selection_token': result['selection_token'],
            'expires_in': result['expires_in']
        })
        
    except Exception as e:
        logger.error(f"Phone number search failed: {e}")
        return jsonify({'error': 'Failed to search phone numbers'}), 500


@onboarding_bp.route('/purchase-number', methods=['POST'])
@jwt_required()
def purchase_phone_number():
    """Purchase selected phone number and complete SignalWire setup"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate user has payment method
        payment_method = PaymentMethod.query.filter_by(
            user_id=user.id,
            status='active',
            is_default=True
        ).first()
        
        if not payment_method:
            return jsonify({
                'error': 'Valid payment method required'
            }), 400
        
        # Check if user already has SignalWire setup
        if user.signalwire_setup_completed:
            return jsonify({
                'error': 'Phone number already configured'
            }), 400
        
        # Validate request data
        schema = {
            'selectedPhoneNumber': {'type': 'string', 'required': True},
            'selectionToken': {'type': 'string', 'required': True}
        }
        
        data = request.get_json()
        validation_error = validate_json_data(data, schema)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Initialize SignalWire service
        signalwire_service = SignalWireService()
        
        # Create subproject and purchase number
        result = signalwire_service.create_subproject_and_purchase_number(
            user_id=user.id,
            username=user.username,
            selected_number=data['selectedPhoneNumber'],
            selection_token=data['selectionToken']
        )
        
        if not result['success']:
            return jsonify({'error': result['error']}), 400
        
        # Update user with SignalWire information
        user.signalwire_subproject_id = result['subproject']['sid']
        user.signalwire_subproject_token = result['subproject']['auth_token']
        user.signalwire_phone_number = result['phone_number']['number']
        user.signalwire_phone_number_sid = result['phone_number']['sid']
        user.signalwire_setup_completed = True
        user.trial_phone_expires_at = datetime.fromisoformat(result['trial_expires_at'].replace('Z', '+00:00'))
        
        # Create or update trial subscription
        subscription = Subscription.query.filter_by(user_id=user.id).first()
        if not subscription:
            # Get the basic plan for trial
            basic_plan = SubscriptionPlan.query.filter_by(name='Basic').first()
            if basic_plan:
                subscription = Subscription(
                    user_id=user.id,
                    plan_id=basic_plan.id,
                    status='trialing',
                    billing_cycle='monthly',
                    auto_renew=True,
                    amount=basic_plan.monthly_price,
                    current_period_start=datetime.utcnow(),
                    current_period_end=datetime.utcnow() + timedelta(days=14),
                    trial_end=datetime.utcnow() + timedelta(days=14)
                )
                db.session.add(subscription)
        
        db.session.commit()
        
        # Test webhook configuration
        webhook_test = signalwire_service.test_webhook_configuration(
            result['subproject']['sid'],
            result['phone_number']['number']
        )
        
        return jsonify({
            'success': True,
            'message': 'Phone number purchased and configured successfully!',
            'subproject': result['subproject'],
            'phone_number': result['phone_number'],
            'trial_expires_at': result['trial_expires_at'],
            'webhook_configured': result['webhook_configured'],
            'webhook_test_passed': webhook_test['success']
        })
        
    except Exception as e:
        logger.error(f"Phone number purchase failed: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to purchase phone number'}), 500


@onboarding_bp.route('/verify-requirements', methods=['POST'])
@jwt_required()
def verify_onboarding_requirements():
    """Verify user has met all requirements for phone number setup"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check payment method
        payment_method = PaymentMethod.query.filter_by(
            user_id=user.id,
            status='active',
            is_default=True
        ).first()
        
        # Check subscription plan selection
        subscription = Subscription.query.filter_by(user_id=user.id).first()
        
        requirements_met = {
            'has_payment_method': payment_method is not None,
            'has_selected_plan': subscription is not None,
            'can_proceed_to_phone_setup': payment_method is not None and subscription is not None
        }
        
        if not requirements_met['can_proceed_to_phone_setup']:
            missing_requirements = []
            if not payment_method:
                missing_requirements.append('valid_payment_method')
            if not subscription:
                missing_requirements.append('subscription_plan')
            
            return jsonify({
                'success': False,
                'requirements_met': requirements_met,
                'missing_requirements': missing_requirements,
                'message': 'Please complete billing setup before configuring your phone number'
            })
        
        return jsonify({
            'success': True,
            'requirements_met': requirements_met,
            'message': 'All requirements met. Ready for phone number setup.'
        })
        
    except Exception as e:
        logger.error(f"Requirements verification failed: {e}")
        return jsonify({'error': 'Failed to verify requirements'}), 500


@onboarding_bp.route('/complete', methods=['POST'])
@jwt_required()
def complete_onboarding():
    """Mark onboarding as complete and finalize setup"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.signalwire_setup_completed:
            return jsonify({
                'error': 'SignalWire setup must be completed first'
            }), 400
        
        # Get usage statistics
        signalwire_service = SignalWireService()
        usage_stats = signalwire_service.get_subproject_usage(user.signalwire_subproject_id)
        
        return jsonify({
            'success': True,
            'message': 'Onboarding completed successfully!',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone_number': user.signalwire_phone_number,
                'trial_expires_at': user.trial_phone_expires_at.isoformat() if user.trial_phone_expires_at else None
            },
            'usage_stats': usage_stats.get('usage', {}) if usage_stats['success'] else {}
        })
        
    except Exception as e:
        logger.error(f"Onboarding completion failed: {e}")
        return jsonify({'error': 'Failed to complete onboarding'}), 500