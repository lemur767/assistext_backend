# app/api/signup.py - New signup API endpoints

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.profile import Profile
from app.extensions import db
from app.utils.signalwire_helpers import get_available_numbers, purchase_phone_number
from datetime import datetime
import json

signup_bp = Blueprint('signup', __name__)

@signup_bp.route('/available-numbers', methods=['GET'])
def get_available_numbers_for_signup():
    """Get available phone numbers for a specific city during signup"""
    city = request.args.get('city', 'toronto')
    
    # Map cities to their area codes
    city_area_codes = {
        'toronto': ['416', '647', '437'],
        'ottawa': ['613', '343'],
        'mississauga': ['905', '289', '365'],
        'london': ['519', '226', '548'],
        'hamilton': ['905', '289']
    }
    
    area_codes = city_area_codes.get(city, ['416'])
    
    try:
        # Get available numbers from SignalWire
        available_numbers = []
        
        for area_code in area_codes:
            numbers = get_available_numbers(
                area_code=area_code,
                limit=2  # Get 2 numbers per area code
            )
            available_numbers.extend(numbers)
        
        # Limit to 5 numbers total for UI
        available_numbers = available_numbers[:5]
        
        # Format the response
        formatted_numbers = []
        for num in available_numbers:
            formatted_numbers.append({
                'phone_number': num['phone_number'],
                'formatted_number': format_phone_number(num['phone_number']),
                'locality': num.get('locality', 'Unknown'),
                'region': num.get('region', 'ON'),
                'area_code': num['phone_number'][2:5],  # Extract area code
                'setup_cost': '$5.00',  # Standard setup cost
                'monthly_cost': '$2.00',  # Standard monthly cost
                'capabilities': {
                    'sms': True,
                    'voice': num.get('voice_enabled', True),
                    'mms': num.get('mms_enabled', True)
                }
            })
        
        return jsonify({
            'available_numbers': formatted_numbers,
            'city': city
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to fetch available numbers: {str(e)}'
        }), 500


@signup_bp.route('/complete-signup', methods=['POST'])
def complete_signup():
    """Complete the multi-step signup process"""
    data = request.json
    
    # Validate required fields
    required_fields = [
        'username', 'email', 'password', 'profileName', 
        'selected_phone_number'
    ]
    
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    # Validate password confirmation
    if data.get('password') != data.get('confirmPassword'):
        return jsonify({'error': 'Passwords do not match'}), 400
    
    try:
        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == data['username']) | 
            (User.email == data['email'])
        ).first()
        
        if existing_user:
            if existing_user.username == data['username']:
                return jsonify({'error': 'Username already taken'}), 400
            else:
                return jsonify({'error': 'Email already registered'}), 400
        
        # Check if phone number is already in use
        existing_profile = Profile.query.filter_by(
            phone_number=data['selected_phone_number']
        ).first()
        
        if existing_profile:
            return jsonify({'error': 'Phone number already in use'}), 400
        
        # Purchase the phone number from SignalWire
        try:
            purchased_number = purchase_phone_number(data['selected_phone_number'])
            signalwire_sid = purchased_number.get('sid')
        except Exception as e:
            return jsonify({
                'error': f'Failed to purchase phone number: {str(e)}'
            }), 500
        
        # Create the user
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data.get('firstName', ''),
            last_name=data.get('lastName', ''),
            phone_number=data.get('personalPhone', ''),
            is_active=True
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.flush()  # Get the user ID
        
        # Create default business hours
        default_hours = {
            "monday": {"start": "10:00", "end": "22:00"},
            "tuesday": {"start": "10:00", "end": "22:00"},
            "wednesday": {"start": "10:00", "end": "22:00"},
            "thursday": {"start": "10:00", "end": "22:00"},
            "friday": {"start": "10:00", "end": "22:00"},
            "saturday": {"start": "12:00", "end": "22:00"},
            "sunday": {"start": "12:00", "end": "22:00"},
        }
        
        # Create the profile
        profile = Profile(
            user_id=user.id,
            name=data['profileName'],
            phone_number=data['selected_phone_number'],
            description=data.get('profile_description', ''),
            timezone='America/Toronto',  # Default for Canadian numbers
            is_active=True,
            ai_enabled=True,  # Enable AI by default
            business_hours=json.dumps(default_hours),
            daily_auto_response_limit=100,
            signalwire_sid=signalwire_sid
        )
        
        db.session.add(profile)
        
        # Set up webhook URL for the phone number
        webhook_url = f"{current_app.config['BASE_URL']}/api/webhooks/sms"
        
        try:
            configure_webhook(data['selected_phone_number'], webhook_url)
        except Exception as e:
            current_app.logger.warning(f"Failed to configure webhook: {e}")
            # Don't fail the signup for this
        
        # Commit all changes
        db.session.commit()
        
        # Generate JWT tokens
        from flask_jwt_extended import create_access_token, create_refresh_token
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Account created successfully',
            'tokens': {
                'access_token': access_token,
                'refresh_token': refresh_token
            },
            'user': user.to_dict(),
            'profile': profile.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Signup error: {e}")
        return jsonify({
            'error': 'Failed to create account. Please try again.'
        }), 500


@signup_bp.route('/validate-username', methods=['POST'])
def validate_username():
    """Check if username is available"""
    data = request.json
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    
    # Check if username exists
    existing_user = User.query.filter_by(username=username).first()
    
    if existing_user:
        return jsonify({'available': False, 'error': 'Username already taken'}), 200
    
    return jsonify({'available': True}), 200


@signup_bp.route('/validate-email', methods=['POST'])
def validate_email():
    """Check if email is available"""
    data = request.json
    email = data.get('email', '').strip()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    # Check if email exists
    existing_user = User.query.filter_by(email=email).first()
    
    if existing_user:
        return jsonify({'available': False, 'error': 'Email already registered'}), 200
    
    return jsonify({'available': True}), 200


def format_phone_number(phone_number):
    """Format phone number for display"""
    # Remove +1 country code if present
    if phone_number.startswith('+1'):
        phone_number = phone_number[2:]
    elif phone_number.startswith('1'):
        phone_number = phone_number[1:]
    
    # Format as (XXX) XXX-XXXX
    if len(phone_number) == 10:
        return f"({phone_number[:3]}) {phone_number[3:6]}-{phone_number[6:]}"
    
    return phone_number


def configure_webhook(phone_number, webhook_url):
    """Configure SignalWire webhook for the phone number"""
    from app.utils.signalwire_helpers import configure_number_webhook
    
    try:
        configure_number_webhook(phone_number, webhook_url)
        return True
    except Exception as e:
        current_app.logger.error(f"Webhook configuration failed: {e}")
        raise


# Add to your main app initialization
# In app/__init__.py, add this line in the create_app function:
# app.register_blueprint(signup_bp, url_prefix='/api/signup')