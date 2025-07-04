from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app.models.user import User
from app.extensions import db
from typing import Dict, Any

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        required_fields = ['username', 'email', 'password', 'first_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if user already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create new user
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data.get('last_name', ''),
            display_name=data.get('display_name'),
            phone_number=data.get('phone_number'),
            timezone=data.get('timezone', 'UTC'),
            ai_personality=data.get('ai_personality', 'You are a helpful assistant.'),
            ai_instructions=data.get('ai_instructions', 'Respond professionally.')
        )
        
        user.set_password(data['password'])
        
        # Set default business hours
        default_hours = {
            'monday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'tuesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'wednesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'thursday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'friday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
            'saturday': {'enabled': False, 'start': '09:00', 'end': '17:00'},
            'sunday': {'enabled': False, 'start': '09:00', 'end': '17:00'}
        }
        user.set_business_hours(default_hours)
        
        db.session.add(user)
        db.session.commit()
        
        # Create JWT tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'success': True,
            'message': 'Account created successfully',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.get_json()
        
        user = User.query.filter(
            (User.username == data.get('username')) | 
            (User.email == data.get('username'))
        ).first()
        
        if not user or not user.check_password(data.get('password', '')):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Create JWT tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500
