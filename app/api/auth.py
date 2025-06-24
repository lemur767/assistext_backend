from flask import request, jsonify, current_app
from flask_restful import Resource
from flask_jwt_extended import create_access_token, create_refresh_token
from app import db
from app.models.user import User
from app.models.profile import Profile
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime, timedelta
import logging
import uuid
from signalwire.rest import Client as SignalWireClient

logger = logging.getLogger(__name__)

class UserRegistrationSchema(Schema):
    """Schema for user registration validation"""
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    confirm_password = fields.Str(required=True)
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    personal_phone = fields.Str(allow_none=True, validate=validate.Length(max=20))

class RegistrationAPI(Resource):
    """Handle user registration endpoint"""
    
    def post(self):
        try:
            schema = UserRegistrationSchema()
            data = schema.load(request.json)
            
            # Validate passwords match
            if data['password'] != data['confirm_password']:
                return {'error': 'Passwords do not match'}, 400
            
            # Check if user exists
            existing_user = User.query.filter(
                (User.username == data['username']) | 
                (User.email == data['email'])
            ).first()
            
            if existing_user:
                return {'error': 'User already exists'}, 409
            
            # Create user
            user = User(
                username=data['username'],
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                personal_phone=data.get('personal_phone')
            )
            user.set_password(data['password'])
            
            db.session.add(user)
            db.session.commit()
            
            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            return {
                'success': True,
                'message': 'User registered successfully',
                'user': user.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }, 201
            
        except ValidationError as e:
            return {'error': 'Validation failed', 'details': e.messages}, 400
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {str(e)}")
            return {'error': 'Registration failed'}, 500

class PhoneNumberSearchAPI(Resource):
    """Handle phone number search"""
    
    def post(self):
        try:
            data = request.json
            city = data.get('city', 'toronto')
            
            # Mock phone numbers for testing
            mock_numbers = [
                {
                    'phone_number': '+14165551001',
                    'formatted_number': '(416) 555-1001',
                    'locality': city.title(),
                    'region': 'ON',
                    'area_code': '416',
                    'setup_cost': '$1.00',
                    'monthly_cost': '$1.00',
                    'capabilities': {'sms': True, 'voice': True, 'mms': True}
                },
                {
                    'phone_number': '+14165551002',
                    'formatted_number': '(416) 555-1002',
                    'locality': city.title(),
                    'region': 'ON',
                    'area_code': '416',
                    'setup_cost': '$1.00',
                    'monthly_cost': '$1.00',
                    'capabilities': {'sms': True, 'voice': True, 'mms': True}
                }
            ]
            
            return {
                'success': True,
                'city': city,
                'available_numbers': mock_numbers,
                'count': len(mock_numbers)
            }, 200
            
        except Exception as e:
            logger.error(f"Phone search error: {str(e)}")
            return {'error': 'Phone number search failed'}, 500

class CompleteSignupAPI(Resource):
    """Handle complete signup with profile creation"""
    
    def post(self):
        try:
            data = request.json
            
            # Create user
            user = User(
                username=data['username'],
                email=data['email'],
                first_name=data['firstName'],
                last_name=data['lastName'],
                personal_phone=data.get('personalPhone'),
                timezone=data.get('timezone', 'America/Toronto')
            )
            user.set_password(data['password'])
            
            db.session.add(user)
            db.session.flush()
            
            # Create profile
            profile = Profile(
                user_id=user.id,
                name=data['profileName'],
                description=data.get('profileDescription'),
                phone_number=data['selectedPhoneNumber'],
                preferred_city=data.get('preferredCity', 'toronto')
            )
            
            db.session.add(profile)
            db.session.commit()
            
            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            return {
                'success': True,
                'message': 'Account created successfully',
                'user': user.to_dict(),
                'profile': profile.to_dict(),
                'access_token': access_token,
                'refresh_token': refresh_token
            }, 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Complete signup error: {str(e)}")
            return {'error': 'Registration failed'}, 500

def register_auth_routes(api, limiter):
    """Register authentication routes with rate limiting"""
    
    # Apply rate limiting
    RegistrationAPI.decorators = [limiter.limit("5 per minute")]
    PhoneNumberSearchAPI.decorators = [limiter.limit("10 per minute")]
    CompleteSignupAPI.decorators = [limiter.limit("3 per minute")]
    
    # Register routes
    api.add_resource(RegistrationAPI, '/api/auth/register')
    api.add_resource(PhoneNumberSearchAPI, '/api/signup/search-numbers')
    api.add_resource(CompleteSignupAPI, '/api/signup/complete-signup')
