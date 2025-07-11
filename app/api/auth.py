from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    jwt_required, get_jwt_identity, create_access_token, 
    create_refresh_token, get_jwt
)
from app.models.user import User
from app.extensions import db
from datetime import datetime, timedelta
import re

auth_bp = Blueprint('auth', __name__)




@auth_bp.route('/register', methods=['POST'])
def register():
  
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['username', 'email', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, data['email']):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate password strength
        if len(data['password']) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == data['username']) | (User.email == data['email'])
        ).first()
        
        if existing_user:
            if existing_user.username == data['username']:
                return jsonify({'error': 'Username already exists'}), 409
            else:
                return jsonify({'error': 'Email already exists'}), 409
        
        # Create user with integrated profile
        user = User(
            username=data['username'],
            email=data['email'],
            # Basic profile information
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            phone_number=data.get('phone_number', ''),
            timezone=data.get('timezone', 'UTC'),
            
            # Default business settings
            auto_reply_enabled=data.get('auto_reply_enabled', True),
            daily_message_limit=data.get('daily_message_limit', 100),
            
            # Default AI settings
            ai_enabled=data.get('ai_enabled', True),
            ai_personality=data.get('ai_personality', 'Seductive mistress, flirty and fun.  Keep responses short.  Use emojis'),
            ai_instructions=data.get('ai_instructions','Flirty, short, polite responses.'),
                    
            signalwire_project_id=data.get('signalwire_project_id'),
            signalwire_auth_token=data.get('signalwire_auth_token'),
            signalwire_space_url=data.get('signalwire_space_url'),
        )
        
        # Set password
        user.set_password(data['password'])
        
        #Adding the signalwire phone number
        if 'signalwire_phone_number' in data:
            user.signalwire_phone_number=data['signalwire_phone_number']
        
        # Set default business hours if not provided
        if 'business_hours' in data:
            user.set_business_hours(data['business_hours'])
        
        # Set auto reply keywords if provided
        if 'auto_reply_keywords' in data:
            user.set_auto_reply_keywords(data['auto_reply_keywords'])
        
    
        
        db.session.add(user)
        db.session.commit()
        
        # Generate tokens
        access_token = create_access_token(
            identity=user.id,
            expires_delta=timedelta(hours=24)
        )
        refresh_token = create_refresh_token(
            identity=user.id,
            expires_delta=timedelta(days=30)
        )
        
        current_app.logger.info(f"New user registered: {user.username} ({user.email})")
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """User login with complete profile data"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if not all([data.get('username'), data.get('password')]):
            return jsonify({'error': 'Missing username or password'}), 400
        
        # Find user (allow login with username or email)
        user = User.query.filter(
            (User.username == data['username']) | (User.email == data['username'])
        ).first()
        
        # Verify credentials
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if user is active
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        # Update last login
        user.last_login = datetime.utcnow()
        
        # Reset monthly count if needed
       # user.reset_monthly_count_if_needed()
        
        
        db.session.commit()
        
        # Generate tokens
        access_token = create_access_token(
            identity=user.id,
            expires_delta=timedelta(hours=24)
        )
        refresh_token = create_refresh_token(
            identity=user.id,
            expires_delta=timedelta(days=30)
        )
        
        current_app.logger.info(f"User logged in: {user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Get current user profile (complete profile data)
    UPDATED: Returns integrated profile data instead of separate user + profile
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        
        # Reset monthly count if needed
        user.reset_monthly_count_if_needed()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'user': user.to_dict(include_sensitive=True)  # Include SignalWire config for profile settings
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting current user: {str(e)}")
        return jsonify({'error': 'Failed to get user information'}), 500


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            return jsonify({'error': 'Invalid user'}), 401
        
        # Generate new access token
        access_token = create_access_token(
            identity=user_id,
            expires_delta=timedelta(hours=24)
        )
        
        return jsonify({
            'success': True,
            'access_token': access_token
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return jsonify({'error': 'Token refresh failed'}), 500


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout user (blacklist token)
    Note: This requires implementing a token blacklist system
    """
    try:
        # TODO: Implement token blacklisting
        # For now, just return success
        # In a production system, you'd add the token to a blacklist
        
        user_id = get_jwt_identity()
        current_app.logger.info(f"User logged out: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500


@auth_bp.route('/update-password', methods=['PUT'])
@jwt_required()
def update_password():
    """Update user password"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['current_password', 'new_password']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Verify current password
        if not user.check_password(data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Validate new password
        new_password = data['new_password']
        if len(new_password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters long'}), 400
        
        # Update password
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        current_app.logger.info(f"Password updated for user: {user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Password updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password update error: {str(e)}")
        return jsonify({'error': 'Password update failed'}), 500


@auth_bp.route('/verify-email', methods=['POST'])
@jwt_required()
def verify_email():
    """
    Email verification endpoint
    TODO: Implement actual email verification with tokens
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # TODO: Implement actual email verification logic
        # For now, just mark as verified
        user.is_verified = True
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Email verified successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Email verification error: {str(e)}")
        return jsonify({'error': 'Email verification failed'}), 500


@auth_bp.route('/deactivate', methods=['POST'])
@jwt_required()
def deactivate_account():
    """Deactivate user account"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json() or {}
        
        # Verify password for security
        if 'password' not in data:
            return jsonify({'error': 'Password required for account deactivation'}), 400
        
        if not user.check_password(data['password']):
            return jsonify({'error': 'Incorrect password'}), 400
        
        # Deactivate account
        user.is_active = False
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        current_app.logger.info(f"Account deactivated: {user.username}")
        
        return jsonify({
            'success': True,
            'message': 'Account deactivated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Account deactivation error: {str(e)}")
        return jsonify({'error': 'Account deactivation failed'}), 500


# Admin endpoints (if needed)

@auth_bp.route('/admin/users', methods=['GET'])
@jwt_required()
def list_users():
    """List all users (admin only)"""
    try:
        user_id = get_jwt_identity()
        current_user = User.query.get(user_id)
        
        if not current_user or not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        users_query = User.query.order_by(User.created_at.desc())
        result = users_query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'users': [user.to_dict() for user in result.items],
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
        current_app.logger.error(f"Error listing users: {str(e)}")
        return jsonify({'error': 'Failed to list users'}), 500