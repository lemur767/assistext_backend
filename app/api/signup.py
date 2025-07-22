

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from app.utils.signalwire_client import get_signalwire_client
import logging

signup_bp = Blueprint('signup', __name__)

@signup_bp.route('/search-numbers', methods=['POST', 'OPTIONS'])
@cross_origin()
def search_phone_numbers():
    """Search for available phone numbers"""
    try:
        # Handle preflight request
        if request.method == 'OPTIONS':
            return '', 204
        
        # Get request data
        data = request.get_json() or {}
        
        # Extract search criteria
        search_criteria = {
            'country': data.get('country', 'US'),
            'area_code': data.get('area_code'),
            'city': data.get('city'),
            'region': data.get('region'),
            'contains': data.get('contains'),
            'limit': min(data.get('limit', 20), 50)  # Cap at 50 results
        }
        
        # Remove None values
        search_criteria = {k: v for k, v in search_criteria.items() if v is not None}
        
        logging.info(f"Searching phone numbers with criteria: {search_criteria}")
        
        # Get SignalWire client and search
        signalwire = get_signalwire_client()
        result = signalwire.search_available_numbers(search_criteria)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f"Found {result['count']} available phone numbers",
                'numbers': result['numbers'],
                'search_criteria': result['search_criteria']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Phone number search failed')
            }), 400
            
    except Exception as e:
        logging.error(f"Phone number search error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error during phone number search'
        }), 500

@signup_bp.route('/purchase-number', methods=['POST', 'OPTIONS'])
@cross_origin()
def purchase_phone_number():
    """Purchase a phone number"""
    try:
        # Handle preflight request
        if request.method == 'OPTIONS':
            return '', 204
        
        # Get request data
        data = request.get_json() or {}
        
        phone_number = data.get('phone_number')
        if not phone_number:
            return jsonify({
                'success': False,
                'error': 'Phone number is required'
            }), 400
        
        # Webhook configuration
        webhook_config = {
            'friendly_name': data.get('friendly_name', 'AssisText Number')
        }
        
        logging.info(f"Purchasing phone number: {phone_number}")
        
        # Get SignalWire client and purchase
        signalwire = get_signalwire_client()
        result = signalwire.purchase_phone_number(phone_number, webhook_config)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f"Successfully purchased {phone_number}",
                'phone_number': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Phone number purchase failed')
            }), 400
            
    except Exception as e:
        logging.error(f"Phone number purchase error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error during phone number purchase'
        }), 500