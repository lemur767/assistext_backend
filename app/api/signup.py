from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models.user import User
from app.models.profile import Profile
from app.extensions import db
<<<<<<< HEAD
=======
from app.utils.signalwire_helpers import get_signalwire_client, search_available_numbers, purchase_phone_number
from werkzeug.security import generate_password_hash
import json
>>>>>>> refs/remotes/origin/main
import logging

# Import SignalWire functions directly
try:
    from app.utils.signalwire_helpers import get_signalwire_client, get_available_phone_numbers, purchase_phone_number
    SIGNALWIRE_AVAILABLE = True
    print("✅ SignalWire helpers imported successfully in signup.py")
except ImportError as e:
    SIGNALWIRE_AVAILABLE = False
    print(f"❌ SignalWire import error in signup.py: {e}")

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

def format_phone_display(phone_number: str) -> str:
    """Format phone number for display"""
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number

@signup_bp.route('/search-numbers', methods=['POST'])
def search_available_numbers_endpoint():
<<<<<<< HEAD
    """Registration Step 3: Search for available phone numbers"""
=======
    """
    Registration Step 3: Search for exactly 5 available phone numbers
    Frontend → Backend → SignalWire API → Backend → Frontend (5 numbers)
    """
>>>>>>> refs/remotes/origin/main
    try:
        if not SIGNALWIRE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'SignalWire service not available. Please contact support.',
                'available_numbers': []
            }), 503
            
        data = request.json
        city = data.get('city', '').lower()
        area_code = data.get('area_code')
        
        logger.info(f"Registration phone search for city: {city}")
        
        if not city:
            return jsonify({
                'success': False,
                'error': 'City is required',
                'available_numbers': []
            }), 400
        
        # Get SignalWire client
        client = get_signalwire_client()
        if not client:
            logger.error("SignalWire client not available")
            return jsonify({
                'success': False,
<<<<<<< HEAD
                'error': 'Phone number service temporarily unavailable. Please try again later.',
=======
                'error': 'Phone number service temporarily unavailable. Please try again.',
>>>>>>> refs/remotes/origin/main
                'available_numbers': []
            }), 503
        
        # Get area codes for the city
        area_codes = CANADA_AREA_CODES.get(city, ['416'])  # Default to Toronto if not found
        
        if area_code:
            # Use specific area code if provided
            area_codes = [area_code]
        
        logger.info(f"Searching area codes: {area_codes} for city: {city}")
        
        # Search for available numbers across all area codes for the city
        all_numbers = []
        
        for ac in area_codes:
            try:
<<<<<<< HEAD
                # Use the helper function
                numbers, error = get_available_phone_numbers(
                    area_code=ac,
                    city=city,
                    country='CA',
                    limit=10
                )
                
                if error:
                    logger.warning(f"Error searching area code {ac}: {error}")
                    continue
                    
                all_numbers.extend(numbers)
=======
                # Search SignalWire API for available numbers
                available_numbers = client.available_phone_numbers('CA').list(
                    area_code=ac,
                    sms_enabled=True,
                    limit=10  # Get more than we need
                )
                
                # Format numbers for frontend
                for number in available_numbers:
                    formatted_number = {
                        'phone_number': number.phone_number,
                        'formatted_number': format_phone_display(number.phone_number),
                        'locality': getattr(number, 'locality', city.title()),
                        'region': getattr(number, 'region', 'ON'),
                        'area_code': ac,
                        'setup_cost': '$1.00',  # SignalWire standard setup cost
                        'monthly_cost': '$1.00', # SignalWire standard monthly cost
                        'capabilities': {
                            'sms': True,
                            'voice': True,
                            'mms': True
                        }
                    }
                    all_numbers.append(formatted_number)
>>>>>>> refs/remotes/origin/main
                
                # Stop if we have enough numbers
                if len(all_numbers) >= 5:
                    break
                    
            except Exception as e:
                logger.warning(f"Error searching area code {ac}: {str(e)}")
                continue
        
        # Return only the first 5 numbers
        final_numbers = all_numbers[:5]
        
        if not final_numbers:
            return jsonify({
                'success': False,
                'error': f'No phone numbers available in {city}. Please try a different city.',
                'available_numbers': [],
                'city': city,
                'count': 0
            }), 404
        
        logger.info(f"Found {len(final_numbers)} numbers for {city}")
        
        return jsonify({
            'success': True,
            'available_numbers': final_numbers,
            'city': city.title(),
            'count': len(final_numbers),
            'message': f'Found {len(final_numbers)} available numbers in {city.title()}'
        }), 200
        
    except Exception as e:
        logger.error(f"Error in phone number search: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to search for phone numbers. Please try again.',
            'available_numbers': []
        }), 500

@signup_bp.route('/complete-signup', methods=['POST'])
def complete_signup():
<<<<<<< HEAD
    """Complete registration: Create user, purchase phone number, setup webhook"""
    try:
        if not SIGNALWIRE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'SignalWire service not available. Please contact support.'
            }), 503
            
=======
    """
    Complete registration: Create user, purchase SignalWire number, setup webhook
    """
    try:
>>>>>>> refs/remotes/origin/main
        data = request.json
        
        # Validate required fields
        required_fields = [
            'username', 'email', 'password', 'firstName', 'lastName',
            'profileName', 'selectedPhoneNumber'
        ]
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'{field} is required'
                }), 400
        
        # Validate password confirmation
        if data.get('password') != data.get('confirmPassword'):
            return jsonify({
                'success': False,
                'error': 'Passwords do not match'
            }), 400
        
        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == data['username']) | 
            (User.email == data['email'])
        ).first()
        
        if existing_user:
<<<<<<< HEAD
            error_msg = 'Username already taken' if existing_user.username == data['username'] else 'Email already registered'
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
=======
            if existing_user.username == data['username']:
                return jsonify({
                    'success': False,
                    'error': 'Username already taken'
                }), 400
            else:
                return jsonify({
                    'success': False,
                    'error': 'Email already registered'
                }), 400
>>>>>>> refs/remotes/origin/main
        
        # Start database transaction
        try:
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
            
<<<<<<< HEAD
            # Purchase the phone number from SignalWire
=======
            # Purchase the phone number from SignalWire FIRST
>>>>>>> refs/remotes/origin/main
            selected_number = data['selectedPhoneNumber']
            profile_name = data['profileName']
            
            logger.info(f"Purchasing SignalWire number {selected_number} for user {user.username}")
            
<<<<<<< HEAD
            webhook_url = f"{current_app.config.get('BASE_URL', 'https://backend.assitext.ca')}/api/webhooks/signalwire/sms"
=======
            # Configure webhook URL for your backend
            webhook_url = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/api/webhooks/signalwire/sms"
>>>>>>> refs/remotes/origin/main
            
            # Purchase number with webhook configuration
            purchased_data, error = purchase_phone_number(
                phone_number=selected_number,
                friendly_name=f"{profile_name} - {user.username}",
                webhook_url=webhook_url
            )
            
            if error or not purchased_data:
                # Rollback user creation if number purchase fails
                db.session.rollback()
<<<<<<< HEAD
                logger.error(f"Phone number purchase failed: {error}")
=======
>>>>>>> refs/remotes/origin/main
                return jsonify({
                    'success': False,
                    'error': f'Failed to purchase phone number: {error or "Unknown error"}'
                }), 500
            
            # Create profile with purchased number
            profile = Profile(
                user_id=user.id,
                name=profile_name,
                description=data.get('profileDescription', ''),
                phone_number=selected_number,
                is_active=True,
                is_default=True
            )
            
            db.session.add(profile)
            
            # Commit everything
            db.session.commit()
            
            # Generate JWT tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            logger.info(f"Successfully created account for {user.username} with number {selected_number}")
            
            return jsonify({
                'success': True,
                'message': f'Account created successfully! Your SMS number {format_phone_display(selected_number)} is ready.',
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
            
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database transaction error: {str(db_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to create account. Please try again.'
            }), 500
            
    except Exception as e:
        logger.error(f"Complete signup error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Registration failed. Please try again.'
        }), 500

@signup_bp.route('/cities', methods=['GET'])
def get_supported_cities():
    """Get list of supported Canadian cities with their area codes"""
    cities = []
    for city, area_codes in CANADA_AREA_CODES.items():
        cities.append({
            'name': city.title(),
            'value': city,
            'area_codes': area_codes,
            'primary_area_code': area_codes[0]
        })
    
    return jsonify({'cities': cities}), 200

<<<<<<< HEAD
@signup_bp.route('/test', methods=['GET'])
def test_signup():
    """Test signup endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Signup endpoint is working',
        'signalwire_available': SIGNALWIRE_AVAILABLE
    }), 200
=======
def format_phone_display(phone_number: str) -> str:
    """Format phone number for display: +1234567890 -> (123) 456-7890"""
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number
>>>>>>> refs/remotes/origin/main
