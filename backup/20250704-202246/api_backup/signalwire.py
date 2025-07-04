

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.signalwire_helpers import get_signalwire_client, get_available_phone_numbers, purchase_phone_number
from app.models.profile import Profile
from app.extensions import db
import logging

logger = logging.getLogger(__name__)
signalwire_bp = Blueprint('signalwire', __name__)

@signalwire_bp.route('/phone-numbers/search', methods=['GET'])
@jwt_required()
def search_phone_numbers():
    """Search for available phone numbers with proper regional parameters - FIXED VERSION"""
    try:
        # Get search parameters
        area_code = request.args.get('area_code')
        country = request.args.get('country', 'US')
        contains = request.args.get('contains')
        city = request.args.get('city')  
        sms_enabled = request.args.get('sms_enabled', 'true').lower() == 'true'
        limit = int(request.args.get('limit', 20))
        
        logger.info(f"Searching for numbers: area_code={area_code}, city={city}, country={country}, limit={limit}")
        
        # Get SignalWire client
        client = get_signalwire_client()
        if not client:
            return jsonify({
                'error': 'SignalWire service unavailable',
                'available_numbers': []
            }), 503
        
  
        search_params = {
            'limit': limit,
            'sms_enabled': sms_enabled
        }
        
        if area_code:
            search_params['area_code'] = area_code
        if contains:
            search_params['contains'] = contains
        
  
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
        

        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').local.list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').local.list(**search_params)
        
        # Format response
        formatted_numbers = []
        for num in available_numbers:
            formatted_numbers.append({
                'phone_number': num.phone_number,
                'locality': getattr(num, 'locality', city or 'Unknown'),
                'region': getattr(num, 'region', search_params.get('in_region')),
                'capabilities': {
                    'sms': getattr(num, 'sms', True),
                    'mms': getattr(num, 'mms', True),
                    'voice': getattr(num, 'voice', True)
                },
                'price': '1.00',
                'friendly_name': f"{num.phone_number} - {getattr(num, 'locality', city or 'Unknown')}",
                'setup_cost': 1.0,
                'monthly_cost': 1.0
            })
        
        return jsonify({
            'available_numbers': formatted_numbers,
            'total_found': len(formatted_numbers),
            'search_params': search_params  
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching for phone numbers: {str(e)}")
        return jsonify({
            'error': 'Failed to search for phone numbers',
            'details': str(e)
        }), 500

@signalwire_bp.route('/phone-numbers/purchase', methods=['POST'])
@jwt_required()
def purchase_phone_number_endpoint():
    """Purchase a phone number"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        phone_number = data.get('phone_number')
        if not phone_number:
            return jsonify({'error': 'Phone number is required'}), 400
        
        # Purchase the number
        result, error = purchase_phone_number(
            phone_number=phone_number,
            friendly_name=data.get('friendly_name'),
            webhook_url=data.get('webhook_url')
        )
        
        if error:
            return jsonify({'error': error}), 400
        
        # Update user's profile with the purchased number
        profile = Profile.query.filter_by(user_id=user_id).first()
        if profile:
            profile.phone_number = phone_number
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Phone number purchased successfully',
            'phone_number': result
        }), 200
        
    except Exception as e:
        logger.error(f"Error purchasing phone number: {str(e)}")
        return jsonify({
            'error': 'Failed to purchase phone number',
            'details': str(e)
        }), 500

@signalwire_bp.route('/phone-numbers/owned', methods=['GET'])
@jwt_required()
def get_owned_phone_numbers():
    """Get phone numbers owned by the user"""
    try:
        user_id = get_jwt_identity()
        
        # Get client
        client = get_signalwire_client()
        if not client:
            return jsonify({'error': 'SignalWire service unavailable'}), 503
        
        # Get owned numbers from SignalWire
        owned_numbers = client.incoming_phone_numbers.list()
        
        # Format response
        formatted_numbers = []
        for num in owned_numbers:
            formatted_numbers.append({
                'phone_number': num.phone_number,
                'friendly_name': num.friendly_name,
                'capabilities': {
                    'sms': getattr(num, 'sms_enabled', True),
                    'mms': getattr(num, 'mms_enabled', True),
                    'voice': getattr(num, 'voice_enabled', True)
                },
                'date_created': num.date_created.isoformat() if num.date_created else None,
                'status': getattr(num, 'status', 'active')
            })
        
        return jsonify({
            'owned_numbers': formatted_numbers,
            'total_count': len(formatted_numbers)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting owned phone numbers: {str(e)}")
        return jsonify({
            'error': 'Failed to get owned phone numbers',
            'details': str(e)
        }), 500

# Log successful loading
logger.info("✅ Fixed SignalWire blueprint loaded successfully")