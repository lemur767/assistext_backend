"""
Signup API with Unified SignalWire Service
"""
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from app.services.signalwire_service import get_signalwire_service
import logging

signup_bp = Blueprint('signup', __name__)

@signup_bp.route('/search-numbers', methods=['POST', 'OPTIONS'])
@cross_origin()
def search_phone_numbers():
    """Search for available phone numbers using unified service"""
    try:
        if request.method == 'OPTIONS':
            return '', 204
        
        data = request.get_json() or {}
        
        search_criteria = {
            'country': data.get('country', 'US'),
            'area_code': data.get('area_code'),
            'city': data.get('city'),
            'region': data.get('region'),
            'contains': data.get('contains'),
            'limit': min(data.get('limit', 20), 50)
        }
        
        # Remove None values
        search_criteria = {k: v for k, v in search_criteria.items() if v is not None}
        
        logging.info(f"Searching phone numbers: {search_criteria}")
        
        # Use unified service
        signalwire = get_signalwire_service()
        result = signalwire.search_available_numbers(**search_criteria)
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Phone number search error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@signup_bp.route('/purchase-number', methods=['POST', 'OPTIONS'])
@cross_origin()
def purchase_phone_number():
    """Purchase a phone number using unified service"""
    try:
        if request.method == 'OPTIONS':
            return '', 204
        
        data = request.get_json() or {}
        
        phone_number = data.get('phone_number')
        if not phone_number:
            return jsonify({
                'success': False,
                'error': 'Phone number is required'
            }), 400
        
        logging.info(f"Purchasing phone number: {phone_number}")
        
        # Use unified service
        signalwire = get_signalwire_service()
        result = signalwire.purchase_number(
            phone_number=phone_number,
            subproject_sid=data.get('subproject_sid'),
            friendly_name=data.get('friendly_name', 'AssisText Number')
        )
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Phone number purchase error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
