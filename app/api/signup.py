from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models.user import User
from app.models.profile import Profile
from app.extensions import db
import logging
import traceback
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime

# Import SignalWire directly in this file
try:
    from signalwire.rest import Client as SignalWireClient
    SIGNALWIRE_CLIENT_AVAILABLE = True
except ImportError:
    SignalWireClient = None
    SIGNALWIRE_CLIENT_AVAILABLE = False

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

# =============================================================================
# INLINE SIGNALWIRE FUNCTIONS - No external imports needed
# =============================================================================

def get_signalwire_client():
    """Get configured SignalWire client - INLINE VERSION"""
    try:
        if not SIGNALWIRE_CLIENT_AVAILABLE:
            logger.error("SignalWire client library not available")
            return None
            
        space_url = current_app.config.get('SIGNALWIRE_SPACE_URL')
        project_id = current_app.config.get('SIGNALWIRE_PROJECT_ID') 
        auth_token = current_app.config.get('SIGNALWIRE_AUTH_TOKEN')
        
        logger.info(f"SignalWire config check: space_url={bool(space_url)}, project_id={bool(project_id)}, auth_token={bool(auth_token)}")
        
        if not all([space_url, project_id, auth_token]):
            logger.error("SignalWire credentials not configured properly")
            logger.error(f"Missing: space_url={not space_url}, project_id={not project_id}, auth_token={not auth_token}")
            return None
        
        client = SignalWireClient(project_id, auth_token, space_url)
        logger.info("SignalWire client created successfully")
        return client
        
    except Exception as e:
        logger.error(f"Failed to create SignalWire client: {str(e)}")
        return None

def format_phone_display(phone_number: str) -> str:
    """Format phone number for display - INLINE VERSION"""
    if not phone_number:
        return ""
        
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number

def get_available_phone_numbers(area_code: str = None, city: str = None, country: str = 'CA', limit: int = 5) -> Tuple[List[Dict], str]:
    """Search for available phone numbers - INLINE VERSION"""
    try:
        logger.info(f"Searching for numbers: area_code={area_code}, city={city}, country={country}")
        
        client = get_signalwire_client()
        if not client:
            error_msg = "SignalWire service unavailable - client not initialized"
            logger.error(error_msg)
            return [], error_msg
        
        search_params = {'limit': limit, 'sms_enabled': True}
        
        if area_code:
            search_params['area_code'] = area_code
        
        logger.info(f"Search params: {search_params}")
        
        # Search for numbers
        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').list(**search_params)
        
        logger.info(f"Found {len(available_numbers)} numbers from SignalWire")
        
        # Format results
        formatted_numbers = []
        for number in available_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'locality': getattr(number, 'locality', city or 'Unknown'),
                'region': getattr(number, 'region', 'ON'),
                'area_code': area_code or number.phone_number[2:5] if len(number.phone_number) > 5 else area_code,
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                },
                'setup_cost': '$1.00',
                'monthly_cost': '$1.00'
            }
            formatted_numbers.append(formatted_number)
        
        logger.info(f"Formatted {len(formatted_numbers)} numbers for return")
        return formatted_numbers, ""
        
    except Exception as e:
        error_msg = f"Failed to search available numbers: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

def purchase_phone_number(phone_number: str, friendly_name: str = None, webhook_url: str = None) -> Tuple[Optional[Dict], str]:
    """Purchase a phone number and configure webhook - INLINE VERSION"""
    try:
        logger.info(f"Attempting to purchase number: {phone_number}")
        
        client = get_signalwire_client()
        if not client:
            error_msg = "SignalWire service unavailable for purchase"
            logger.error(error_msg)
            return None, error_msg
        
        purchase_params = {'phone_number': phone_number}
        
        if friendly_name:
            purchase_params['friendly_name'] = friendly_name
        
        if webhook_url:
            purchase_params['sms_url'] = webhook_url
            purchase_params['sms_method'] = 'POST'
            logger.info(f"Configuring webhook: {webhook_url}")
        
        logger.info(f"Purchase params: {purchase_params}")
        
        # Purchase the number
        purchased_number = client.incoming_phone_numbers.create(**purchase_params)
        
        result_data = {
            'phone_number': purchased_number.phone_number,
            'friendly_name': purchased_number.friendly_name,
            'sid': purchased_number.sid,
            'capabilities': {'sms': True, 'mms': True, 'voice': True},
            'webhook_configured': webhook_url is not None,
            'status': 'active',
            'purchased_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Successfully purchased number {phone_number} with SID {purchased_number.sid}")
        return result_data, ""
        
    except Exception as e:
        error_msg = f"Failed to purchase phone number: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

# =============================================================================
# API ENDPOINTS
# =============================================================================

@signup_bp.route('/debug', methods=['GET'])
def debug_imports():
    """Debug endpoint to check SignalWire availability"""
    try:
        # Test client creation
        client = get_signalwire_client()
        client_available = client is not None
        
        return jsonify({
            'signalwire_client_library': SIGNALWIRE_CLIENT_AVAILABLE,
            'signalwire_client_created': client_available,
            'config_check': {
                'space_url': bool(current_app.config.get('SIGNALWIRE_SPACE_URL')),
                'project_id': bool(current_app.config.get('SIGNALWIRE_PROJECT_ID')),
                'auth_token': bool(current_app.config.get('SIGNALWIRE_AUTH_TOKEN'))
            },
            'functions_available': {
                'get_signalwire_client': callable(get_signalwire_client),
                'get_available_phone_numbers': callable(get_available_phone_numbers),
                'purchase_phone_number': callable(purchase_phone_number)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@signup_bp.route('/search-numbers', methods=['POST'])
def search_available_numbers_endpoint():
    """Registration Step 3: Search for available phone numbers"""
    try:
        logger.info(f"Search numbers called - SignalWire client available: {SIGNALWIRE_CLIENT_AVAILABLE}")
        
        if not SIGNALWIRE_CLIENT_AVAILABLE:
            logger.error("SignalWire client library not available")
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
        
        # Get area codes for the city
        area_codes = CANADA_AREA_CODES.get(city, ['416'])
        
        if area_code:
            area_codes = [area_code]
        
        logger.info(f"Searching area codes: {area_codes} for city: {city}")
        
        # Search for available numbers across all area codes for the city
        all_numbers = []
        
        for ac in area_codes:
            try:
                logger.info(f"Calling get_available_phone_numbers for area code: {ac}")
                
                # Use the inline function
                numbers, error = get_available_phone_numbers(
                    area_code=ac,
                    city=city,
                    country='CA',
                    limit=10
                )
                
                logger.info(f"get_available_phone_numbers returned: {len(numbers) if numbers else 0} numbers, error: {error}")
                
                if error:
                    logger.warning(f"Error searching area code {ac}: {error}")
                    continue
                    
                all_numbers.extend(numbers)
                
                # Stop if we have enough numbers
                if len(all_numbers) >= 5:
                    break
                    
            except Exception as e:
                logger.error(f"Exception searching area code {ac}: {str(e)}")
                logger.error(f"Exception traceback: {traceback.format_exc()}")
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
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'Phone number search failed',
            'details': str(e)
        }), 500

@signup_bp.route('/complete-signup', methods=['POST'])
def complete_signup():
    """Complete registration: Create user, purchase phone number, setup webhook"""
    try:
        if not SIGNALWIRE_CLIENT_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'SignalWire service not available. Please contact support.'
            }), 503
            
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
            error_msg = 'Username already taken' if existing_user.username == data['username'] else 'Email already registered'
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
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
            db.session.flush()
            
            # Purchase the phone number from SignalWire
            selected_number = data['selectedPhoneNumber']
            profile_name = data['profileName']
            
            logger.info(f"Purchasing SignalWire number {selected_number} for user {user.username}")
            
            webhook_url = f"{current_app.config.get('BASE_URL', 'https://backend.assitext.ca')}/api/webhooks/signalwire/sms"
            
            # Purchase number with webhook configuration
            purchased_data, error = purchase_phone_number(
                phone_number=selected_number,
                friendly_name=f"{profile_name} - {user.username}",
                webhook_url=webhook_url
            )
            
            if error or not purchased_data:
                db.session.rollback()
                logger.error(f"Phone number purchase failed: {error}")
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

@signup_bp.route('/test', methods=['GET'])
def test_signup():
    """Test signup endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Signup endpoint is working',
        'signalwire_available': SIGNALWIRE_CLIENT_AVAILABLE
    }), 200

# Log the module loading
logger.info(f"Signup blueprint loaded with inline SignalWire functions - Client available: {SIGNALWIRE_CLIENT_AVAILABLE}")