# app/api/signalwire.py
from flask import Blueprint, request, jsonify, current_app
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
    get_signalwire_client, 
    get_available_phone_numbers,
    purchase_phone_number,
    configure_number_webhook,
    get_signalwire_phone_numbers,
    validate_signalwire_webhook_request
)
from app.models.profile import Profile
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
from app.models.user import User
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
from app.extensions import db
from app.utils.signalwire_helpers import get_signalwire_client, send_sms, get_signalwire_phone_numbers, get_available_phone_numbers, purchase_phone_number, configure_number_webhook, validate_signalwire_webhook_request, format_phone_display
import logging

logger = logging.getLogger(__name__)
signalwire_bp = Blueprint('signalwire', __name__)

@signalwire_bp.route('/phone-numbers/search', methods=['GET'])
def search_available_numbers():
    """Search for available phone numbers"""
    try:
        # Get query parameters
        area_code = request.args.get('area_code')
        country = request.args.get('country', 'CA')
        contains = request.args.get('contains')
        sms_enabled = request.args.get('sms_enabled', 'true').lower() == 'true'
        limit = int(request.args.get('limit', 20))
        
        logger.info(f"Searching for numbers: area_code={area_code}, country={country}, limit={limit}")
        
        # Get SignalWire client
        client = get_signalwire_client()
        
        # Search for available numbers
        search_params = {
            'limit': limit,
            'sms_enabled': sms_enabled
        }
        
        if area_code:
            search_params['area_code'] = area_code
        if contains:
            search_params['contains'] = contains
            
        # Use SignalWire API to search for numbers
        if country.upper() == 'CA':
            available_numbers = client.available_phone_numbers('CA').list(**search_params)
        else:
            available_numbers = client.available_phone_numbers('US').list(**search_params)
        
        # Format response
        formatted_numbers = []
        for num in available_numbers:
            formatted_numbers.append({
                'phone_number': num.phone_number,
                'locality': getattr(num, 'locality', None),
                'region': getattr(num, 'region', None),
                'capabilities': {
                    'sms': getattr(num, 'sms', True),
                    'mms': getattr(num, 'mms', True),
                    'voice': getattr(num, 'voice', True)
                },
                'price': '1.00',  # Default price - you may want to get actual pricing
                'friendly_name': f"{num.phone_number} - {getattr(num, 'locality', 'Unknown')}",
                'setup_cost': 1.0,
                'monthly_cost': 1.0
            })
        
        return jsonify({
            'available_numbers': formatted_numbers,
            'total_found': len(formatted_numbers)
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
        data = request.json
        user_id = get_jwt_identity()
        
        phone_number = data.get('phone_number')
        profile_id = data.get('profile_id')
        friendly_name = data.get('friendly_name', f'SMS AI Number')
        
        if not phone_number:
            return jsonify({'error': 'Phone number is required'}), 400
            
        logger.info(f"Purchasing number {phone_number} for user {user_id}")
        
        # Purchase the number
        purchased_number = purchase_phone_number(
            phone_number=phone_number,
            friendly_name=friendly_name
        )
        
        if not purchased_number:
            return jsonify({'error': 'Failed to purchase phone number'}), 500
            
        # Configure webhook
        webhook_url = f"{current_app.config['BASE_URL']}/api/webhooks/signalwire/sms"
        try:
            configure_number_webhook(phone_number, webhook_url)
            logger.info(f"Webhook configured for {phone_number}: {webhook_url}")
        except Exception as webhook_error:
            logger.warning(f"Webhook configuration failed: {webhook_error}")
            # Don't fail the purchase for webhook issues
        
        return jsonify({
            'success': True,
            'phone_number': {
                'phone_number': phone_number,
                'sid': purchased_number.get('sid'),
                'friendly_name': friendly_name,
                'capabilities': {
                    'sms': True,
                    'mms': True,
                    'voice': True
                }
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Error purchasing phone number: {str(e)}")
        return jsonify({
            'error': 'Failed to purchase phone number',
            'details': str(e)
        }), 500

@signalwire_bp.route('/phone-numbers', methods=['GET'])
@jwt_required()
def get_phone_numbers():
    """Get all SignalWire phone numbers for the user"""
    try:
        user_id = get_jwt_identity()
        
        # Get user's phone numbers
        user_profiles = Profile.query.filter_by(user_id=user_id).all()
        phone_numbers = [profile.phone_number for profile in user_profiles if profile.phone_number]
        
        # Get SignalWire phone number details
        signalwire_numbers = get_signalwire_phone_numbers()
        
        # Filter to only user's numbers
        user_numbers = [
            num for num in signalwire_numbers 
            if num['phone_number'] in phone_numbers
        ]
        
        return jsonify({
            'phone_numbers': user_numbers,
            'total_count': len(user_numbers)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting phone numbers: {str(e)}")
        return jsonify({'error': 'Failed to get phone numbers'}), 500

@signalwire_bp.route('/phone-numbers/<phone_number>/webhook', methods=['PUT'])
@jwt_required()
def configure_phone_webhook(phone_number):
    """Configure webhook for a specific phone number"""
    try:
        data = request.json
        webhook_url = data.get('webhook_url')
        
        if not webhook_url:
            webhook_url = f"{current_app.config['BASE_URL']}/api/webhooks/signalwire/sms"
        
        # Configure the webhook
        configure_number_webhook(phone_number, webhook_url)
        
        return jsonify({
            'success': True,
            'phone_number': phone_number,
            'webhook_url': webhook_url
        }), 200
        
    except Exception as e:
        logger.error(f"Error configuring webhook for {phone_number}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@signalwire_bp.route('/status', methods=['GET'])
@jwt_required()
def get_signalwire_status():
    """Get SignalWire account status and configuration"""
    try:
        
        status = get_signalwire_status()
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"Error getting SignalWire status: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500