# app/api/auth.py - Updated authentication routes with CORS handling

from flask import Blueprint, request, jsonify, make_response, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity
)
from app.models.user import User
from app.extensions import db
from app.utils.cors_middleware import cors_enabled
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

# Apply CORS to all routes in this blueprint
@auth_bp.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    
    if origin and origin in current_app.config.get('CORS_ORIGINS', ['http://localhost:5173']):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = (
            'Content-Type, Authorization, X-Requested-With, Accept, Origin'
        )
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    
    return response

@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
@cors_enabled
def register():
    if request.method == 'OPTIONS':
        return make_response('', 200)
    
    data = request.get_json()
    
    # Validate required fields
    if not all([data.get('username'), data.get('email'), data.get('password')]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Check if username or email already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "Username already taken"}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"error": "Email already registered"}), 400
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        phone_number=data.get('phone_number')
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    # Generate tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        "message": "User registered successfully",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict()
    }), 201

@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
@cors_enabled
def login():
    if request.method == 'OPTIONS':
        return make_response('', 200)
    
    data = request.get_json()
    additional_claims = {
        'iss': 'assitext',
        'sub': str(user.id),
        'type': 'access'
    }
    # Validate required fields
    if not all([data.get('username'), data.get('password')]):
        return jsonify({"error": "Missing username or password"}), 400
    
    # Find user
    user = User.query.filter_by(username=data['username']).first()
    
    # Verify credentials
    if not user or not user.check_password(data['password']):
        return jsonify({"error": "Invalid credentials"}), 401

    
  
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate tokens
    access_token = create_access_token(identity=user.id,additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=user.id,additional_claims=additional_claims)
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict()
    }), 200

@auth_bp.route('/me', methods=['GET', 'OPTIONS'])
@jwt_required()
@cors_enabled
def get_user_profile():
    if request.method == 'OPTIONS':
        return make_response('', 200)
    
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify(user.to_dict()), 200

@auth_bp.route('/refresh-token', methods=['POST', 'OPTIONS'])
@jwt_required(refresh=True)
@cors_enabled
def refresh():
    if request.method == 'OPTIONS':
        return make_response('', 200)
    
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    
    return jsonify({
        "access_token": access_token
    }), 200