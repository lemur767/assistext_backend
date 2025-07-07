# app/api/auth.py
from flask import Blueprint, request, jsonify, current_app
from flask_restful import Resource, Api
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app.extensions import db
from marshmallow import Schema, fields, validate, ValidationError
import logging
from datetime import datetime

# Import ONLY the User model to avoid circular imports
from app.models.user import User

logger = logging.getLogger(__name__)

# CREATE THE BLUEPRINT - this was missing!
auth_bp = Blueprint('auth', __name__)
api = Api(auth_bp)


class UserRegistrationSchema(Schema):
    """Schema for simplified user registration validation"""
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    passwordConfirm = fields.Str(required=True)
    firstName = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    lastName = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    personal_phone = fields.Str(allow_none=True, validate=validate.Length(max=20))


class RegistrationAPI(Resource):
    """Handle user registration endpoint - simplified to avoid mapper errors"""
    
    def post(self):
        try:
            # Log the incoming request
            logger.info("Registration attempt received")
            
            # Validate JSON data
            if not request.json:
                logger.warning("Registration request missing JSON data")
                return {'error': 'Request must include JSON data'}, 400
            
            schema = UserRegistrationSchema()
            data = schema.load(request.json)
            
            # Validate passwords match
            if data['password'] != data['confirm_password']:
                logger.warning("Password confirmation mismatch")
                return {'error': 'Passwords do not match'}, 400
            
            # Check if user exists
            existing_user = User.query.filter(
                (User.username == data['username']) | 
                (User.email == data['email'])
            ).first()
            
            if existing_user:
                logger.warning(f"User registration failed - user exists: {data['username']}")
                return {'error': 'User already exists'}, 409
            
            # Create user - NO PROFILE CREATION YET
            user = User(
                username=data['username'],
                email=data['email'],
                firstName=data['firstName'],
                lastName=data['lastName'],
                personal_phone=data.get('personal_phone')
            )
            user.set_password(data['password'])
            
            try:
                db.session.add(user)
                db.session.commit()
                logger.info(f"User {user.username} registered successfully")
                
                # Generate tokens
                access_token = create_access_token(identity=user.id)
                refresh_token = create_refresh_token(identity=user.id)
                
                return {
                    'message': 'User registered successfully',
                    'user': user.to_dict(),
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }, 201
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Database error during registration: {e}")
                return {'error': 'Registration failed - database error'}, 500
                
        except ValidationError as e:
            logger.warning(f"Validation error during registration: {e.messages}")
            return {'error': 'Validation failed', 'details': e.messages}, 400
        except Exception as e:
            logger.error(f"Unexpected error during registration: {e}")
            return {'error': 'Registration failed - internal error'}, 500


class LoginAPI(Resource):
    """Handle user login endpoint"""
    
    def post(self):
        try:
            logger.info("Login attempt received")
            
            if not request.json:
                return {'error': 'Request must include JSON data'}, 400
                
            data = request.get_json()
            
            if not data or not data.get('username') or not data.get('password'):
                logger.warning("Login request missing credentials")
                return {'error': 'Username and password required'}, 400
            
            # Find user by username or email
            user = User.query.filter(
                (User.username == data['username']) | 
                (User.email == data['username'])
            ).first()
            
            if not user or not user.check_password(data['password']):
                logger.warning(f"Invalid login attempt for: {data['username']}")
                return {'error': 'Invalid credentials'}, 401
            
            if not user.is_active:
                logger.warning(f"Login attempt for disabled account: {data['username']}")
                return {'error': 'Account is disabled'}, 403
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            logger.info(f"Successful login for user: {user.username}")
            
            return {
                'message': 'Login successful',
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }, 200
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {'error': 'Login failed'}, 500


class UserProfileAPI(Resource):
    """Get current user profile"""
    
    @jwt_required()
    def get(self):
        try:
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            
            if not user:
                return {'error': 'User not found'}, 404
            
            return {'user': user.to_dict()}, 200
            
        except Exception as e:
            logger.error(f"Profile fetch error: {e}")
            return {'error': 'Could not fetch profile'}, 500


class RefreshTokenAPI(Resource):
    """Refresh access token"""
    
    @jwt_required(refresh=True)
    def post(self):
        try:
            user_id = get_jwt_identity()
            access_token = create_access_token(identity=user_id)
            
            return {'access_token': access_token}, 200
            
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return {'error': 'Token refresh failed'}, 500


# Register the API resources with routes
api.add_resource(RegistrationAPI, '/register')
api.add_resource(LoginAPI, '/login')
api.add_resource(UserProfileAPI, '/me')
api.add_resource(RefreshTokenAPI, '/refresh')

# Add a simple test route
@auth_bp.route('/test', methods=['GET'])
def test_auth():
    """Test endpoint to verify auth blueprint is working"""
    return {'message': 'Auth blueprint is working', 'status': 'ok'}, 200
