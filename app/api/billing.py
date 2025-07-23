"""
Billing Integration for Trial to Subscription Conversion
Handles reactivation of SignalWire services after payment
"""

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.subscription import Subscription
# from app.tasks.trial_tasks import reactivate_user_after_subscription
try:
    from app.tasks.trial_tasks import reactivate_user_after_subscription
except ImportError:
    # Fallback or mock for development if the module does not exist
    def reactivate_user_after_subscription(*args, **kwargs):
        class DummyTask:
            id = "dummy-task-id"
            def delay(self, *a, **kw):
                return self
        return DummyTask()
from app.services.signalwire_service import get_signalwire_service
from datetime import datetime
import logging

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/activate-subscription', methods=['POST'])
@jwt_required()
@cross_origin()
def activate_subscription():
    """
    Activate user subscription and reactivate SignalWire services
    Called after successful payment processing
    """
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json() or {}
        
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        subscription_plan_id = data.get('subscription_plan_id')
        payment_method_id = data.get('payment_method_id')
        stripe_subscription_id = data.get('stripe_subscription_id')
        
        if not all([subscription_plan_id, payment_method_id]):
            return jsonify({
                'success': False,
                'error': 'Missing required subscription details'
            }), 400
        
        logging.info(f"🔄 Activating subscription for user {current_user_id}")
        
        # Create subscription record
        subscription = Subscription(
            user_id=current_user_id,
            plan_id=subscription_plan_id,
            stripe_subscription_id=stripe_subscription_id,
            status='active',
            current_period_start=datetime.utcnow(),
            payment_method_id=payment_method_id
        )
        
        db.session.add(subscription)
        db.session.flush()
        
        # Update user status immediately for quick response
        user.subscription_active = True
        user.subscription_plan_id = subscription_plan_id
        user.trial_status = 'converted' if user.is_trial else 'not_applicable'
        
        db.session.commit()
        
        # Trigger background reactivation of SignalWire services
        reactivate_task = reactivate_user_after_subscription.delay(
            user_id=current_user_id,
            subscription_plan_id=subscription_plan_id
        )
        
        # Get current SignalWire status
        signalwire_status = "unknown"
        if user.signalwire_phone_sid:
            try:
                signalwire = get_signalwire_service()
                phone_status = signalwire.get_phone_number_status(user.signalwire_phone_sid)
                signalwire_status = phone_status.get('status', 'unknown')
            except Exception as e:
                logging.warning(f"Could not get phone status: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Subscription activated successfully!',
            'subscription': {
                'id': subscription.id,
                'plan_id': subscription_plan_id,
                'status': 'active',
                'activated_at': subscription.current_period_start.isoformat()
            },
            'user': {
                'id': user.id,
                'subscription_active': True,
                'trial_status': user.trial_status
            },
            'signalwire': {
                'phone_number': user.signalwire_phone_number,
                'current_status': signalwire_status,
                'reactivation_task_id': reactivate_task.id,
                'reactivation_in_progress': True
            }
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"❌ Subscription activation failed for user {current_user_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Subscription activation failed'
        }), 500

@billing_bp.route('/reactivation-status/<task_id>', methods=['GET'])
@jwt_required()
def get_reactivation_status(task_id):
    """
    Check status of SignalWire reactivation task
    """
    try:
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id)
        
        if result.ready():
            task_result = result.get()
            return jsonify({
                'success': True,
                'task_status': 'completed',
                'result': task_result
            })
        else:
            return jsonify({
                'success': True,
                'task_status': 'pending',
                'message': 'SignalWire reactivation in progress...'
            })
            
    except Exception as e:
        logging.error(f"Error checking reactivation status: {e}")
        return jsonify({
            'success': False,
            'error': 'Could not check reactivation status'
        }), 500

@billing_bp.route('/trial-to-subscription-flow/<int:user_id>', methods=['POST'])
@jwt_required()
@cross_origin()
def complete_trial_conversion(user_id):
    """
    Complete the trial to subscription conversion flow
    Handles the entire process from payment to SignalWire reactivation
    """
    try:
        current_user_id = get_jwt_identity()
        
        # Ensure user can only convert their own trial
        if current_user_id != user_id:
            return jsonify({
                'success': False,
                'error': 'Unauthorized'
            }), 403
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        data = request.get_json() or {}
        
        # Validate that user is eligible for conversion
        if user.subscription_active:
            return jsonify({
                'success': False,
                'error': 'User already has active subscription'
            }), 400
        
        logging.info(f"🔄 Starting trial conversion for user {user_id}")
        
        # Step 1: Process payment (integrate with your payment processor)
        payment_result = process_subscription_payment(
            user_id=user_id,
            plan_id=data.get('plan_id'),
            payment_method=data.get('payment_method')
        )
        
        if not payment_result['success']:
            return jsonify({
                'success': False,
                'error': 'Payment processing failed',
                'payment_error': payment_result['error']
            }), 400
        
        # Step 2: Create subscription
        subscription = Subscription(
            user_id=user_id,
            plan_id=data.get('plan_id'),
            stripe_subscription_id=payment_result.get('subscription_id'),
            status='active',
            current_period_start=datetime.utcnow()
        )
        
        db.session.add(subscription)
        
        # Step 3: Update user
        user.subscription_active = True
        user.subscription_plan_id = data.get('plan_id')
        user.trial_status = 'converted'
        user.trial_converted_at = datetime.utcnow()
        
        db.session.commit()
        
        # Step 4: Reactivate SignalWire services
        reactivation_result = reactivate_user_after_subscription.delay(
            user_id=user_id,
            subscription_plan_id=data.get('plan_id')
        )
        
        return jsonify({
            'success': True,
            'message': 'Trial conversion completed successfully!',
            'conversion': {
                'user_id': user_id,
                'converted_at': user.trial_converted_at.isoformat(),
                'plan_id': data.get('plan_id'),
                'subscription_id': subscription.id
            },
            'signalwire': {
                'phone_number': user.signalwire_phone_number,
                'reactivation_task_id': reactivation_result.id,
                'expected_active_in': '1-2 minutes'
            },
            'next_steps': [
                'Your phone number is being reactivated',
                'SMS automation will resume shortly',
                'You will receive a confirmation email'
            ]
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"❌ Trial conversion failed for user {user_id}: {e}")
        return jsonify({
            'success': False,
            'error': 'Trial conversion failed'
        }), 500

@billing_bp.route('/user-status/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user_billing_status(user_id):
    """
    Get complete billing and SignalWire status for a user
    """
    try:
        current_user_id = get_jwt_identity()
        
        # Users can only check their own status (unless admin)
        if current_user_id != user_id:
            return jsonify({
                'success': False,
                'error': 'Unauthorized'
            }), 403
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get SignalWire status
        signalwire_status = None
        if user.signalwire_phone_sid:
            try:
                signalwire = get_signalwire_service()
                signalwire_status = signalwire.get_phone_number_status(user.signalwire_phone_sid)
            except Exception as e:
                logging.warning(f"Could not get SignalWire status: {e}")
        
        # Calculate trial info
        trial_info = None
        if user.is_trial and user.trial_end_date:
            remaining_time = user.trial_end_date - datetime.utcnow()
            trial_info = {
                'active': user.trial_status == 'active',
                'status': user.trial_status,
                'days_remaining': max(0, remaining_time.days),
                'end_date': user.trial_end_date.isoformat(),
                'can_convert': user.trial_status in ['active', 'expired']
            }
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'subscription_active': user.subscription_active,
                'subscription_plan_id': user.subscription_plan_id
            },
            'trial': trial_info,
            'signalwire': {
                'phone_number': user.signalwire_phone_number,
                'setup_completed': user.signalwire_setup_completed,
                'number_active': user.signalwire_number_active,
                'status': signalwire_status['status'] if signalwire_status else 'unknown'
            },
            'billing_status': 'trial' if user.is_trial else ('active' if user.subscription_active else 'inactive')
        })
        
    except Exception as e:
        logging.error(f"Error getting user status: {e}")
        return jsonify({
            'success': False,
            'error': 'Could not get user status'
        }), 500

def process_subscription_payment(user_id, plan_id, payment_method):
    """
    Process subscription payment - integrate with your payment processor
    This is a placeholder - replace with your actual payment processing
    """
    try:
        # Integrate with Stripe, PayPal, etc.
        # This is just a placeholder
        logging.info(f"Processing payment for user {user_id}, plan {plan_id}")
        
        # Simulate successful payment
        return {
            'success': True,
            'subscription_id': f'sub_{user_id}_{plan_id}',
            'payment_id': f'pay_{user_id}_{datetime.utcnow().timestamp()}'
        }
        
    except Exception as e:
        logging.error(f"Payment processing failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }