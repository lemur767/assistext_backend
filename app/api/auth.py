# app/api/auth.py - Updated registration endpoint
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required
from marshmallow import Schema, fields, ValidationError, validate
from app.models.user import User
from app.extensions import db
import logging

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

class RegistrationSchema(Schema):
    """Validation schema for user registration - matches frontend exactly"""
    username = fields.Str(required=True, validate=validate.Length(min=3, max=100))
    email = fields.Email(required=True, validate=validate.Length(max=255))
    password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)  # Note: confirm_password (not password_confirm)
    first_name = fields.Str(validate=validate.Length(max=100))
    last_name = fields.Str(validate=validate.Length(max=100))
    personal_phone = fields.Str(validate=validate.Length(max=20))
    
    def validate_passwords_match(self, data, **kwargs):
        """Ensure passwords match"""
        if data.get('password') != data.get('confirm_password'):
            raise ValidationError('Passwords do not match', field_name='confirm_password')

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user with consolidated model
    
    Expected JSON:
    {
        "username": "string",
        "email": "string", 
        "password": "string",
        "confirm_password": "string",
        "first_name": "string",
        "last_name": "string",
        "personal_phone": "string" (optional)
    }
    """
    try:
        # Validate input data
        schema = RegistrationSchema()
        data = schema.load(request.json)
        
        # Additional password validation
        schema.validate_passwords_match(data)
        
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == data['username']) | 
            (User.email == data['email'])
        ).first()
        
        if existing_user:
            if existing_user.username == data['username']:
                return jsonify({'error': 'Username already exists'}), 409
            else:
                return jsonify({'error': 'Email already exists'}), 409
        
        # Create new user with consolidated model
        user = User(
            username=data['username'],
            email=data['email'].lower(),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            personal_phone=data.get('personal_phone'),
            
            # Set default values for new fields
            business_name=None,  # User can set later
            ai_enabled=True,
            auto_reply_enabled=True,
            daily_response_limit=100,
            subscription_status='free',
            is_verified=False
        )
        
        # Set password
        user.set_password(data['password'])
        
        try:
            db.session.add(user)
            db.session.commit()
            logger.info(f"User {user.username} registered successfully")
            
            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            return jsonify({
                'message': 'User registered successfully',
                'user': user.to_dict(),  # Uses consolidated model
                'access_token': access_token,
                'refresh_token': refresh_token
            }), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error during registration: {e}")
            return jsonify({'error': 'Registration failed - database error'}), 500
            
    except ValidationError as e:
        logger.warning(f"Validation error during registration: {e.messages}")
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Unexpected error during registration: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login endpoint with consolidated user model"""
    try:
        data = request.json
        username_or_email = data.get('username')
        password = data.get('password')
        
        if not username_or_email or not password:
            return jsonify({'error': 'Username/email and password required'}), 400
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == username_or_email) | 
            (User.email == username_or_email)
        ).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 401
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Generate tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        logger.info(f"User {user.username} logged in successfully")
        
        return jsonify({
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user data"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user.to_dict()}), 200
        
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return jsonify({'error': 'Failed to get user data'}), 500

@auth_bp.route('/update', methods=['PUT'])
@jwt_required()
def update_user():
    """Update user data with consolidated model"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.json
        
        # Update allowed fields (all snake_case)
        updatable_fields = [
            'first_name', 'last_name', 'personal_phone',
            'business_name', 'business_description', 'timezone',
            'ai_enabled', 'ai_model', 'ai_temperature', 'ai_max_tokens', 'ai_personality',
            'auto_reply_enabled', 'daily_response_limit', 'response_delay_seconds'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(user, field, data[field])
        
        # Handle business hours separately (JSON field)
        if 'business_hours' in data:
            user.set_business_hours(data['business_hours'])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"User {user.username} updated successfully")
        
        return jsonify({
            'message': 'User updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update user error: {e}")
        return jsonify({'error': 'Failed to update user'}), 500