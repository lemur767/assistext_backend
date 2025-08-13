from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    jwt_required, get_jwt_identity, create_access_token, 
    create_refresh_token, get_jwt
)
from marshmallow import Schema, fields, ValidationError
from datetime import datetime

from app.services import get_user_service
from app.models import User
from app.extensions import db
from app.utils.validators import validate_request_json

auth_bp = Blueprint('auth', __name__)

# Request Schemas
class RegisterSchema(Schema):
    username = fields.Str(required=True, validate=lambda x: len(x) >= 3)
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=lambda x: len(x) >= 8)
    first_name = fields.Str(allow_none=True)
    last_name = fields.Str(allow_none=True)
    phone_number = fields.Str(allow_none=True)
    timezone = fields.Str(missing='UTC')

class LoginSchema(Schema):
    email_or_username = fields.Str(required=True)
    password = fields.Str(required=True)

class StartTrialSchema(Schema):
    payment_method_id = fields.Str(required=True)
    preferred_area_code = fields.Str(missing='416')
    billing_address = fields.Dict(allow_none=True)

@auth_bp.route('/register', methods=['POST'])
@validate_request_json(RegisterSchema())
def register():
    """Register new user"""
    try:
        data = request.get_json()
        user_service = get_user_service()
        
        result = user_service.register_user(data)
        
        if result['success']:
            return jsonify({
                'success': True,
                'user': result['user'],
                'tokens': result['tokens'],
                'message': result['message']
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': result.get('error'),
                'errors': result.get('errors')
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Registration error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Registration failed'
        }), 500

@auth_bp.route('/login', methods=['POST'])
@validate_request_json(LoginSchema())
def login():
    """Authenticate user and return tokens"""
    try:
        data = request.get_json()
        user_service = get_user_service()
        
        result = user_service.authenticate_user(
            data['email_or_username'],
            data['password']
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'user': result['user'],
                'tokens': result['tokens']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 401
            
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Authentication failed'
        }), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(current_user_id)
        
        if not user or not user.is_active:
            return jsonify({
                'success': False,
                'error': 'User not found or inactive'
            }), 401
        
        # Create new access token
        additional_claims = {
            'user_id': user.id,
            'username': user.username,
            'trial_status': user.trial_status,
            'subscription_status': user.subscription.status if user.subscription else None
        }
        
        access_token = create_access_token(
            identity=current_user_id,
            additional_claims=additional_claims
        )
        
        return jsonify({
            'success': True,
            'access_token': access_token
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Token refresh failed'
        }), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    try:
        user_id = get_jwt_identity()
        user_service = get_user_service()
        
        result = user_service.get_user_profile(user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'profile': result['profile']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 404
            
    except Exception as e:
        current_app.logger.error(f"Get profile error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch profile'
        }), 500

@auth_bp.route('/start-trial', methods=['POST'])
@jwt_required()
@validate_request_json(StartTrialSchema())
def start_trial():
    """Start trial subscription"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        user_service = get_user_service()
        
        result = user_service.start_trial(user_id, data)
        
        if result['success']:
            return jsonify({
                'success': True,
                'trial_ends_at': result['trial_ends_at'],
                'phone_number': result['phone_number'],
                'message': result['message']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Start trial error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to start trial'
        }), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client-side token invalidation)"""
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200