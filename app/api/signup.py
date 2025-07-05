"""
Signup API Blueprint with SignalWire Phone Number Search
Fixed version with proper regional parameters for Canadian searches
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models.user import User
#from app.models.profile import Profile # Removed - using User model now
from app.extensions import db
from typing import Tuple, List, Dict, Optional
import logging
import traceback
import os

logger = logging.getLogger(__name__)
signup_bp = Blueprint('signup', __name__)

# Canadian cities and their area codes
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
    'winnipeg': ['204', '431'],
    'quebec_city': ['418', '581'],
    'halifax': ['902', '782'],
    'saskatoon': ['306', '639'],
    'regina': ['306', '639'],
    'burlington': ['905', '289'],
    'niagara': ['905', '289'],
    'st_johns': ['709']
}

# Check if SignalWire is available
SIGNALWIRE_CLIENT_AVAILABLE = False
try:
    from signalwire.rest import Client as SignalWireClient
    SIGNALWIRE_CLIENT_AVAILABLE = True
    logger.info("SignalWire client library loaded successfully")
except ImportError as e:
    logger.error(f"SignalWire client library not available: {e}")
    SIGNALWIRE_CLIENT_AVAILABLE = False

# =============================================================================
# SIGNALWIRE HELPER FUNCTIONS (INLINE)
# =============================================================================

def get_signalwire_client() -> Optional[SignalWireClient]:
    """Get configured SignalWire client - FIXED VERSION"""
    try:
        space_url = current_app.config.get('SIGNALWIRE_SPACE_URL')
        project_id = current_app.config.get('SIGNALWIRE_PROJECT_ID')
        auth_token = current_app.config.get('SIGNALWIRE_AUTH_TOKEN')
        
        logger.info(f"SignalWire config check: space_url={bool(space_url)}, project_id={bool(project_id)}, auth_token={bool(auth_token)}")
        
        if not all([space_url, project_id, auth_token]):
            logger.error("SignalWire credentials not configured properly")
            logger.error(f"Missing: space_url={not space_url}, project_id={not project_id}, auth_token={not auth_token}")
            return None
        
        client = SignalWireClient(project_id, auth_token, signalwire_space_url=space_url)
        logger.info("SignalWire client created successfully")
        return client
        
    except Exception as e:
        logger.error(f"Failed to create SignalWire client: {str(e)}")
        return None

def format_phone_display(phone_number: str) -> str:
    """Format phone number for display - FIXED VERSION"""
    if not phone_number:
        return ""
        
    clean_number = phone_number.replace('+1', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '')
    
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    
    return phone_number

def get_available_phone_numbers(area_code: str = None, city: str = None, country: str = 'CA', limit: int = 5) -> Tuple[List[Dict], str]:
    """Search for available phone numbers - FIXED VERSION WITH REGIONAL PARAMETERS"""
    try:
        logger.info(f"Searching for numbers: area_code={area_code}, city={city}, country={country}")
        
        client = get_signalwire_client()
        if not client:
            error_msg = "SignalWire service unavailable - client not initialized"
            logger.error(error_msg)
            return [], error_msg
        
        # ✅ FIX: Build search parameters properly
        search_params = {'limit': limit, 'sms_enabled': True}
        
        if area_code:
            search_params['area_code'] = area_code
        
        # ✅ FIX: Add regional parameters for Canadian searches
        if country.upper() == 'CA' and city:
            # Map cities to provinces  
            city_to_province = {
                'toronto': 'ON', 'ottawa': 'ON', 'mississauga': 'ON', 'london': 'ON', 'hamilton': 'ON',
                'burlington': 'ON', 'niagara': 'ON',
                'montreal': 'QC', 'quebec_city': 'QC',
                'vancouver': 'BC',
                'calgary': 'AB', 'edmonton': 'AB',
                'winnipeg': 'MB',
                'halifax': 'NS',
                'saskatoon': 'SK', 'regina': 'SK',
                'st_johns': 'NL'
            }
            
            province = city_to_province.get(city.lower(), 'ON')
            search_params['in_region'] = province
            search_params['in_locality'] = city.title()
        
        logger.info(f"Search params with regional data: {search_params}")
        
        # ✅ FIX: Use .local.list() instead of just .list()
        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').local.list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').local.list(**search_params)
        
        logger.info(f"Found {len(available_numbers)} numbers from SignalWire")
        
        # Format results
        formatted_numbers = []
        for number in available_numbers:
            formatted_number = {
                'phone_number': number.phone_number,
                'formatted_number': format_phone_display(number.phone_number),
                'locality': getattr(number, 'locality', city or 'Unknown'),
                'region': getattr(number, 'region', search_params.get('in_region', 'ON')),
                'area_code': area_code or number.phone_number[2:5],
                'capabilities': {
                    'sms': getattr(number, 'sms_enabled', True),
                    'mms': getattr(number, 'mms_enabled', True),
                    'voice': getattr(number, 'voice_enabled', True)
                },
                'setup_cost': '$1.00',
                'monthly_cost': '$1.00'
            }
            formatted_numbers.append(formatted_number)
        
        return formatted_numbers, ""
        
    except Exception as e:
        logger.error(f"Failed to search available numbers: {str(e)}")
        return [], f"Failed to search available numbers: {str(e)}"

def purchase_phone_number(phone_number: str, friendly_name: str = None, webhook_url: str = None) -> Tuple[Optional[Dict], str]:
    """Purchase a phone number from SignalWire - FIXED VERSION"""
    try:
        client = get_signalwire_client()
        if not client:
            return None, "SignalWire service unavailable"
        
        purchase_data = {
            'phone_number': phone_number,
            'friendly_name': friendly_name or f"Purchased Number {phone_number}"
        }
        
        if webhook_url:
            purchase_data['sms_url'] = webhook_url
            purchase_data['sms_method'] = 'POST'
        
        purchased_number = client.incoming_phone_numbers.create(**purchase_data)
        
        return {
            'phone_number': purchased_number.phone_number,
            'sid': purchased_number.sid,
            'friendly_name': purchased_number.friendly_name,
            'status': 'purchased'
        }, ""
        
    except Exception as e:
        logger.error(f"Failed to purchase phone number {phone_number}: {str(e)}")
        return None, f"Failed to purchase phone number: {str(e)}"

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
    """Registration Step 3: Search for available phone numbers - FIXED VERSION"""
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
                
                # ✅ FIX: Use the fixed function with proper regional parameters
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
                'available_numbers': []
            }), 200
        
        logger.info(f"Returning {len(final_numbers)} available numbers for {city}")
        
        return jsonify({
            'success': True,
            'city': city.title(),
            'available_numbers': final_numbers,
            'count': len(final_numbers),
            'searched_area_codes': area_codes
        }), 200
        
    except Exception as e:
        logger.error(f"Search numbers error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': 'Phone number search failed',
            'details': str(e)
        }), 500

@signup_bp.route('/complete-signup', methods=['POST'])
def complete_signup():
    """Complete the user registration with selected phone number"""
    try:
        logger.info("Complete signup called")
        
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Required fields
        required_fields = ['username', 'email', 'password', 'firstName', 'lastName', 'profileName', 'selectedPhoneNumber']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Check if username/email already exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({
                'success': False,
                'error': 'Username already exists'
            }), 400
        
        if User.query.filter_by(email=data['email']).first():
            return jsonify({
                'success': False,
                'error': 'Email already exists'
            }), 400
        
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
                  
           
            
            logger.info(f"User {user.username} created successfully")
            
            # Generate tokens
            access_token = create_access_token(identity=user.id)
            refresh_token = create_refresh_token(identity=user.id)
            
            selected_number = data['selectedPhoneNumber']
            
            return jsonify({
                'success': True,
                'message': f'Welcome to AssistExt! Your SMS number {format_phone_display(selected_number)} is ready.',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name
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
logger.info(f"✅ Signup blueprint loaded - Client available: {SIGNALWIRE_CLIENT_AVAILABLE}")