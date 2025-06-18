# app/api/signup.py - Updated signup API with SignalWire phone number selection

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models.user import User
from app.models.profile import Profile
from app.extensions import db
from app.utils.signalwire_helpers import (
    get_signalwire_client, 
    purchase_phone_number,
    configure_number_webhook,
    get_available_phone_numbers
)
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)
signup_bp = Blueprint('signup', __name__)

# Canadian area codes mapping
CANADA_AREA_CODES = {
    'toronto': ['416', '647', '437'],
    'ottawa': ['613', '343'],
    'vancouver': ['604', '778', '236'],
    'montreal': ['514', '438'],
    'calgary': ['403', '587', '825'],
    'edmonton': ['780', '587', '825'],
    'mississauga': ['905', '289', '365'],
    'hamilton': ['905', '289'],
    'london': ['519', '226', '548'],
    'winnipeg': ['204', '431']
}

@signup_bp.route('/search-numbers', methods=['POST'])
def search_available_numbers():
    """Search for available phone numbers by area code"""
    try:
        data = request.json
        area_code = data.get('area_code')
        city = data.get('city', '').lower()
        
        logger.info(f"Searching numbers for area_code={area_code}, city={city}")
        
        if not area_code and not city:
            return jsonify({'error': 'Area code or city is required'}), 400
        
        # If city provided, get area codes for that city
        if city and not area_code:
            area_codes = CANADA_AREA_CODES.get(city, [])
            if not area_codes:
                return jsonify({'error': f'No area codes found for city: {city}'}), 400
        else:
            area_codes = [area_code]
        
        # Search for available numbers across area codes
        all_numbers = []
        client = get_signalwire_client()
        
        for code in area_codes:
            try:
                # Search Canadian numbers with this area code
                numbers = client.available_phone_numbers('CA').list(
                    area_code=code,
                    sms_enabled=True,
                    limit=10
                )
                
                for num in numbers:
                    all_numbers.append({
                        'phone_number': num.phone_number,
                        'formatted_number': format_phone_number(num.phone_number),
                        'locality': getattr(num, 'locality', 'Unknown'),
                        'region': getattr(num, 'region', 'ON'),
                        'area_code': code,
                        'capabilities': {
                            'sms': True,
                            'voice': getattr(num, 'voice', True),
                            'mms': getattr(num, 'mms', True)
                        },
                        'setup_cost': '$5.00',
                        'monthly_cost': '$2.00'
                    })
                
                # Stop when we have enough numbers
                if len(all_numbers) >= 5:
                    break
                    
            except Exception as e:
                logger.warning(f"Error searching area code {code}: {str(e)}")
                continue
        
        # Return up to 5 numbers
        selected_numbers = all_numbers[:5]
        
        if not selected_numbers:
            return jsonify({
                'error': 'No available numbers found for the requested area',
                'available_numbers': []
            }), 404
        
        return jsonify({
            'available_numbers': selected_numbers,
            'total_found': len(selected_numbers),
            'search_area_codes': area_codes
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching for phone numbers: {str(e)}")
        return jsonify({
            'error': 'Failed to search for available numbers',
            'details': str(e)
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


@signup_bp.route('/complete-signup', methods=['POST'])
def complete_signup():
    """Complete the multi-step signup process with phone number purchase and webhook setup"""
    data = request.json
    
    # Validate required fields
    required_fields = [
        'username', 'email', 'password', 'firstName', 'lastName',
        'profileName', 'selectedPhoneNumber'
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
        
        # Check if phone number is already taken
        phone_number = data['selectedPhoneNumber']
        existing_profile = Profile.query.filter_by(phone_number=phone_number).first()
        if existing_profile:
            return jsonify({'error': 'Selected phone number is no longer available'}), 400
        
        # Create new user
        user = User(
            username=data['username'],
            email=data['email'],
            first_name=data['firstName'],
            last_name=data['lastName'],
            phone_number=data.get('personalPhone', ''),
            is_active=True,
            created_at=datetime.utcnow()
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.flush()  # Get user ID without committing
        
        logger.info(f"Created user {user.id}: {user.username}")
        
        # Purchase the phone number through SignalWire
        try:
            friendly_name = f"{data['profileName']} - {data['username']}"
            purchase_result = purchase_phone_number(
                phone_number=phone_number,
                friendly_name=friendly_name
            )
            
            if not purchase_result:
                raise Exception("Failed to purchase phone number")
            
            logger.info(f"Successfully purchased {phone_number}")
            
        except Exception as phone_error:
            logger.error(f"Phone number purchase failed: {str(phone_error)}")
            db.session.rollback()
            return jsonify({
                'error': 'Failed to purchase phone number',
                'details': str(phone_error)
            }), 500
        
        # Configure webhook for SMS AI responses
        try:
            # Set webhook URL to point to your SMS handler
            webhook_url = f"{current_app.config['BASE_URL']}/api/webhooks/sms"
            
            webhook_success = configure_number_webhook(phone_number, webhook_url)
            if not webhook_success:
                logger.warning(f"Webhook configuration failed for {phone_number}")
                # Don't fail registration for webhook issues - can be fixed later
            else:
                logger.info(f"Webhook configured for {phone_number}: {webhook_url}")
                
        except Exception as webhook_error:
            logger.warning(f"Webhook setup failed: {str(webhook_error)}")
            # Continue with registration - webhook can be configured later
        
        # Create profile with phone number
        profile = Profile(
            user_id=user.id,
            name=data['profileName'],
            phone_number=phone_number,
            description=data.get('profileDescription', ''),
            timezone=data.get('timezone', 'America/Toronto'),
            is_active=True,
            ai_enabled=True,  # Enable AI by default
            daily_auto_response_limit=100,  # Default limit
            signalwire_sid=purchase_result.get('sid'),
            created_at=datetime.utcnow()
        )
        
        db.session.add(profile)
        db.session.commit()
        
        logger.info(f"Created profile {profile.id} for user {user.id} with phone {phone_number}")
        
        # Create access token
        access_token = create_access_token(
            identity=user.id,
            expires_delta=timedelta(days=30)
        )
        
        return jsonify({
            'success': True,
            'message': 'Registration completed successfully',
            'access_token': access_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'firstName': user.first_name,
                'lastName': user.last_name
            },
            'profile': {
                'id': profile.id,
                'name': profile.name,
                'phone_number': profile.phone_number,
                'ai_enabled': profile.ai_enabled
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Registration failed: {str(e)}")
        return jsonify({
            'error': 'Registration failed',
            'details': str(e)
        }), 500


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


# Additional endpoints for registration flow
@signup_bp.route('/cities', methods=['GET'])
def get_supported_cities():
    """Get list of supported cities with their area codes"""
    cities = []
    for city, area_codes in CANADA_AREA_CODES.items():
        cities.append({
            'name': city.title(),
            'value': city,
            'area_codes': area_codes,
            'primary_area_code': area_codes[0]
        })
    
    return jsonify({'cities': cities}), 200


@signup_bp.route('/number-info/<phone_number>', methods=['GET'])
def get_number_info(phone_number):
    """Get detailed information about a specific phone number"""
    try:
        client = get_signalwire_client()
        
        # Search for this specific number to get details
        numbers = client.available_phone_numbers('CA').list(
            phone_number=phone_number,
            limit=1
        )
        
        if not numbers:
            return jsonify({'error': 'Number not found or no longer available'}), 404
        
        num = numbers[0]
        number_info = {
            'phone_number': num.phone_number,
            'formatted_number': format_phone_number(num.phone_number),
            'locality': getattr(num, 'locality', 'Unknown'),
            'region': getattr(num, 'region', 'ON'),
            'capabilities': {
                'sms': getattr(num, 'sms', True),
                'voice': getattr(num, 'voice', True),
                'mms': getattr(num, 'mms', True)
            },
            'is_available': True
        }
        
        return jsonify(number_info), 200
        
    except Exception as e:
        logger.error(f"Error getting number info: {str(e)}")
        return jsonify({
            'error': 'Failed to get number information',
            'details': str(e)
        }), 500


