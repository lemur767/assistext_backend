from flask import Blueprint, request, jsonify, current_app
from app.models.user import User
from app.models.profile import Profile
from app.extensions import db
from app.utils.signalwire_helpers import get_signalwire_client
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)
signup_bp = Blueprint('signup', __name__)

# Canadian area codes mapping (same as before)
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
    """
    Registration flow: Search for exactly 5 available phone numbers 
    Frontend → Backend → SignalWire API → Backend → Frontend (5 numbers)
    """
    try:
        data = request.json
        city = data.get('city', '').lower()
        area_code = data.get('area_code')  # Optional specific area code
        
        logger.info(f"Registration phone search for city: {city}")
        
        if not city:
            return jsonify({
                'error': 'City is required',
                'available_numbers': []
            }), 400
        
        # Get SignalWire client
        client = get_signalwire_client()
        if not client:
            logger.error("SignalWire client not available for registration")
            return jsonify({
                'error': 'Phone number service temporarily unavailable. Please try again.',
                'available_numbers': []
            }), 503
        
        # Get area codes for the selected city
        if area_code:
            area_codes_to_search = [area_code]
        else:
            area_codes_to_search = CANADA_AREA_CODES.get(city, ['416'])  # Default to Toronto if city not found
        
        all_numbers = []
        target_count = 5  # Exactly 5 numbers for registration
        
        # Search through area codes until we have 5 numbers
        for code in area_codes_to_search:
            if len(all_numbers) >= target_count:
                break
                
            try:
                logger.info(f"Searching SignalWire for area code {code} in Canada")
                
                # Call SignalWire API for Canadian numbers
                available_numbers = client.available_phone_numbers('CA').list(
                    area_code=code,
                    sms_enabled=True,  # Must support SMS
                    limit=10  # Get more than needed to filter
                )
                
                # Process each number from SignalWire
                for number in available_numbers:
                    if len(all_numbers) >= target_count:
                        break
                        
                    # Format the number data for frontend
                    formatted_number = {
                        'phone_number': number.phone_number,
                        'formatted_number': format_phone_number(number.phone_number),
                        'locality': getattr(number, 'locality', city.title()),
                        'region': getattr(number, 'region', _get_province_for_city(city)),
                        'area_code': code,
                        'setup_cost': '$1.00',
                        'monthly_cost': '$1.00',
                        'capabilities': {
                            'sms': getattr(number, 'sms_enabled', True),
                            'voice': getattr(number, 'voice_enabled', True),
                            'mms': getattr(number, 'mms_enabled', True)
                        }
                    }
                    
                    all_numbers.append(formatted_number)
                    
            except Exception as area_error:
                logger.warning(f"Failed searching area code {code}: {str(area_error)}")
                continue
        
        # Check if we got enough numbers
        if len(all_numbers) == 0:
            logger.warning(f"No SignalWire numbers found for {city}")
            return jsonify({
                'error': f'No phone numbers currently available in {city.title()}. Please try a different city or contact support.',
                'available_numbers': [],
                'city': city.title()
            }), 200
        
        # Return exactly what we found (up to 5)
        final_numbers = all_numbers[:target_count]
        
        logger.info(f"Registration: Found {len(final_numbers)} SignalWire numbers for {city}")
        
        return jsonify({
            'success': True,
            'available_numbers': final_numbers,
            'city': city.title(),
            'count': len(final_numbers),
            'message': f'Found {len(final_numbers)} available numbers in {city.title()}'
        }), 200
        
    except Exception as e:
        logger.error(f"Registration phone search error: {str(e)}")
        return jsonify({
            'error': 'Unable to search for phone numbers. Please try again.',
            'available_numbers': [],
            'details': str(e) if current_app.debug else None
        }), 500


def format_phone_number(phone_number: str) -> str:
    """Format phone number for display as (XXX) XXX-XXXX"""
    # Remove +1 country code if present
    if phone_number.startswith('+1'):
        phone_number = phone_number[2:]
    elif phone_number.startswith('1'):
        phone_number = phone_number[1:]
    
    # Format as (XXX) XXX-XXXX
    if len(phone_number) == 10:
        return f"({phone_number[:3]}) {phone_number[3:6]}-{phone_number[6:]}"
    
    return phone_number


def _get_province_for_city(city: str) -> str:
    """Get Canadian province for city"""
    city_to_province = {
        'toronto': 'ON',
        'ottawa': 'ON', 
        'mississauga': 'ON',
        'london': 'ON',
        'hamilton': 'ON',
        'montreal': 'QC',
        'vancouver': 'BC',
        'calgary': 'AB',
        'edmonton': 'AB',
        'winnipeg': 'MB'
    }
    return city_to_province.get(city.lower(), 'ON')


# Keep your existing endpoints like /complete-signup, /cities, etc.
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


@signup_bp.route('/complete-signup', methods=['POST'])
def complete_signup():
    """Complete the registration and purchase the selected phone number"""
    try:
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
        db.session.flush()  # Get user ID without committing
        
        # Create profile
        profile = Profile(
            user_id=user.id,
            name=data['profileName'],
            description=data.get('profileDescription', ''),
            phone_number=data['selectedPhoneNumber'],
            is_active=True,
            is_default=True
        )
        
        db.session.add(profile)
        
        # Now purchase the phone number from SignalWire
        selected_number = data['selectedPhoneNumber']
        logger.info(f"Purchasing SignalWire number {selected_number} for user {user.username}")
        
        try:
            client = get_signalwire_client()
            if client:
                # Purchase the number with webhook configuration
                webhook_url = f"https://backend.assitext.ca/api/webhooks/signalwire"
                
                purchased_number = client.incoming_phone_numbers.create(
                    phone_number=selected_number,
                    friendly_name=f"SMS AI - {data['profileName']}",
                    sms_url=webhook_url,
                    sms_method='POST'
                )
                
                logger.info(f"Successfully purchased {selected_number} with SID {purchased_number.sid}")
                
                # Update profile with SignalWire SID
                profile.signalwire_phone_sid = purchased_number.sid
                
            else:
                logger.warning("SignalWire client unavailable during signup - number not purchased")
                
        except Exception as purchase_error:
            logger.error(f"Failed to purchase number {selected_number}: {str(purchase_error)}")
            # Continue with signup even if purchase fails - can be retried later
        
        # Commit all changes
        db.session.commit()
        
        # Generate JWT tokens
        from flask_jwt_extended import create_access_token, create_refresh_token
        
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        logger.info(f"Registration completed for user {user.username} with profile {profile.name}")
        
        return jsonify({
            'success': True,
            'message': 'Account created successfully!',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            },
            'profile': {
                'id': profile.id,
                'name': profile.name,
                'phone_number': profile.phone_number
            },
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Complete signup error: {str(e)}")
        return jsonify({
            'error': 'Registration failed. Please try again.',
            'details': str(e) if current_app.debug else None
        }), 500