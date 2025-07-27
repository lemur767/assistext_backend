# app/api/auth.py - Complete auth implementation with subscription checking
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from app.models import User, db
from app.services import get_signalwire_service
from datetime import datetime, timedelta
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
def register():
    """Step 1: Register user and create SignalWire subproject"""
    try:
        if request.method == 'OPTIONS':
            return '', 204
        
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'confirm_password', 'first_name', 'last_name']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            }), 400
        
        # Validate password confirmation
        if data['password'] != data['confirm_password']:
            return jsonify({
                'success': False,
                'error': 'Passwords do not match'
            }), 400
        
        # Check if user already exists
        existing_user = User.query.filter(
            (User.email == data['email']) | (User.username == data['username'])
        ).first()
        
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'User with this email or username already exists'
            }), 400
        
        logger.info(f"Starting registration for: {data['email']}")
        
        # Create user account
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            personal_phone=data.get('personal_phone'),
            signalwire_setup_step=0  # Step 0: Account created, no subproject yet
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Step 1: Create SignalWire subproject
        signalwire_service = get_signalwire_service()
        subproject_result = signalwire_service.create_subproject_for_user(user.id, user.username, user.email)
        
        if not subproject_result['success']:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': 'Failed to create communication account',
                'details': subproject_result['error']
            }), 500
        
        # Store subproject details
        user.signalwire_subproject_sid = subproject_result['subproject_sid']
        user.signalwire_subproject_token = subproject_result['subproject_token']
        user.signalwire_setup_step = 1  # Step 1: Subproject created, ready for phone number
        user.trial_phone_expires_at = datetime.utcnow() + timedelta(days=14)
        
        db.session.commit()
        
        # Create JWT token
        access_token = create_access_token(identity=user.id)
        
        logger.info(f"Registration successful for user {user.id} with subproject {subproject_result['subproject_sid']}")
        
        return jsonify({
            'message': 'User registered successfully',
            'access_token': access_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'signalwire_setup_step': user.signalwire_setup_step,
                'signalwire_setup_completed': False,
                'trial_phone_expires_at': user.trial_phone_expires_at.isoformat()
            },
            'next_step': 'phone_number_setup'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Registration failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Registration failed'
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login with subscription/trial checking and SignalWire number management"""
    try:
        data = request.get_json() or {}
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Missing username or password'
            }), 400
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user or not user.check_password(password):
            return jsonify({
                'success': False,
                'error': 'Invalid credentials'
            }), 401
        
        # Update last login
        user.last_login = datetime.utcnow()
        
        # Check user profile and subscription status
        profile_status = _check_user_profile_status(user)
        
        # Handle SignalWire number suspension/activation based on status
        signalwire_service = get_signalwire_service()
        if user.signalwire_phone_number:
            if profile_status['should_suspend_number']:
                # Suspend the number
                suspension_result = signalwire_service.suspend_user_number(user)
                logger.info(f"Suspended number for user {user.id}: {suspension_result}")
            elif profile_status['should_activate_number']:
                # Reactivate the number
                activation_result = signalwire_service.activate_user_number(user)
                logger.info(f"Activated number for user {user.id}: {activation_result}")
        
        db.session.commit()
        
        # Create JWT token
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
            'access_token': access_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'personal_phone': user.personal_phone,
                'signalwire_phone_number': user.signalwire_phone_number,
                'signalwire_setup_completed': user.signalwire_setup_completed,
                'signalwire_setup_step': user.signalwire_setup_step,
                'is_active': user.is_active,
                'last_login': user.last_login.isoformat(),
                'trial_phone_expires_at': user.trial_phone_expires_at.isoformat() if user.trial_phone_expires_at else None
            },
            'profile_status': profile_status,
            'banner': profile_status.get('banner_message'),
            'requires_payment': profile_status.get('requires_payment', False)
        })
        
    except Exception as e:
        logger.error(f"Login failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed'
        }), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user profile with subscription status"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Check profile status
        profile_status = _check_user_profile_status(user)
        
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'personal_phone': user.personal_phone,
            'signalwire_phone_number': user.signalwire_phone_number,
            'signalwire_setup_completed': user.signalwire_setup_completed,
            'signalwire_setup_step': user.signalwire_setup_step,
            'is_active': user.is_active,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'trial_phone_expires_at': user.trial_phone_expires_at.isoformat() if user.trial_phone_expires_at else None,
            'profile_status': profile_status,
            'banner': profile_status.get('banner_message'),
            'requires_payment': profile_status.get('requires_payment', False)
        })
        
    except Exception as e:
        logger.error(f"Get user failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to get user profile'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user"""
    try:
        # You can add logout logic here if needed (blacklist tokens, etc.)
        # For now, just return success - frontend will clear tokens
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Logout failed'
        }), 500

@auth_bp.route('/search-numbers', methods=['POST'])
@jwt_required()
def search_phone_numbers():
    """Search available phone numbers for user's subproject"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        # Check if user is ready for phone number setup
        if not user or user.signalwire_setup_step < 1:
            return jsonify({
                'success': False,
                'error': 'User not ready for phone number setup. Please complete registration first.'
            }), 400
        
        data = request.get_json() or {}
        search_criteria = {
            'country': data.get('country', 'CA'),
            'area_code': data.get('area_code'),
            'locality': data.get('locality'),
            'limit': data.get('limit', 5)
        }
        
        # Use SignalWire service to search numbers
        signalwire_service = get_signalwire_service()
        result = signalwire_service.search_available_numbers(user, search_criteria)
        
        if result['success']:
            # Store selection token for purchase
            user.phone_number_selection_token = result['selection_token']
            user.phone_number_selection_expires = datetime.utcnow() + timedelta(minutes=15)
            db.session.commit()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Number search failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Number search failed'
        }), 500

@auth_bp.route('/purchase-number', methods=['POST'])
@jwt_required()
def purchase_phone_number():
    """Purchase selected phone number and attach to user's subproject"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        # Check if user is ready for phone number purchase
        if not user or user.signalwire_setup_step < 1:
            return jsonify({
                'success': False,
                'error': 'User not ready for phone number purchase'
            }), 400
        
        data = request.get_json()
        phone_number = data.get('phone_number')
        selection_token = data.get('selection_token')
        
        if not phone_number or not selection_token:
            return jsonify({
                'success': False,
                'error': 'Missing phone number or selection token'
            }), 400
        
        # Validate selection token
        if (not user.phone_number_selection_token or 
            user.phone_number_selection_token != selection_token or
            datetime.utcnow() > user.phone_number_selection_expires):
            return jsonify({
                'success': False,
                'error': 'Invalid or expired selection token'
            }), 400
        
        # Use SignalWire service to purchase number
        signalwire_service = get_signalwire_service()
        result = signalwire_service.purchase_and_configure_number(user, phone_number, selection_token)
        
        if result['success']:
            # Update user with phone number details
            user.signalwire_phone_number = result['phone_number']
            user.signalwire_phone_number_sid = result['phone_number_sid']
            user.signalwire_setup_step = 2  # Setup complete
            user.signalwire_setup_completed = True
            user.phone_number_selection_token = None  # Clear token
            user.phone_number_selection_expires = None
            
            db.session.commit()
            
            logger.info(f"Phone number {result['phone_number']} purchased successfully for user {user.id}")
            
            return jsonify({
                'success': True,
                'message': 'Phone number purchased successfully',
                'phone_number': result['phone_number'],
                'phone_number_sid': result['phone_number_sid'],
                'webhook_endpoints': result.get('webhook_endpoints', {}),
                'setup_complete': True
            })
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Number purchase failed: {e}")
        return jsonify({
            'success': False,
            'error': 'Number purchase failed'
        }), 500

def _check_user_profile_status(user):
    """Check user subscription/trial status and determine actions needed"""
    try:
        current_time = datetime.utcnow()
        
        # Check if user has an active subscription
        # TODO: Replace with actual subscription checking logic
        has_active_subscription = False  # user.subscription and user.subscription.status == 'active'
        has_outstanding_balance = False  # user.outstanding_balance > 0
        
        # Check trial status
        trial_expired = False
        if user.trial_phone_expires_at:
            trial_expired = current_time > user.trial_phone_expires_at
        
        # Determine status and actions
        if has_active_subscription:
            return {
                'status': 'active_subscription',
                'should_suspend_number': False,
                'should_activate_number': True,
                'requires_payment': False,
                'banner_message': None
            }
        elif not trial_expired:
            return {
                'status': 'trial_active',
                'should_suspend_number': False,
                'should_activate_number': True,
                'requires_payment': False,
                'banner_message': f"Trial expires {user.trial_phone_expires_at.strftime('%Y-%m-%d')}"
            }
        elif has_outstanding_balance:
            return {
                'status': 'outstanding_balance',
                'should_suspend_number': True,
                'should_activate_number': False,
                'requires_payment': True,
                'banner_message': 'NUMBER SUSPENDED - PLEASE PAY OUTSTANDING BALANCE'
            }
        else:
            return {
                'status': 'no_subscription',
                'should_suspend_number': True,
                'should_activate_number': False,
                'requires_payment': True,
                'banner_message': 'NUMBER SUSPENDED - PLEASE PICK A PLAN OR PAY OUTSTANDING BALANCE'
            }
            
    except Exception as e:
        logger.error(f"Error checking profile status: {e}")
        return {
            'status': 'error',
            'should_suspend_number': True,
            'should_activate_number': False,
            'requires_payment': True,
            'banner_message': 'NUMBER SUSPENDED - ACCOUNT STATUS UNCLEAR'
        }