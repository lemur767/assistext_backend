"""
SignalWire API with Unified Service
"""
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from app.services.signalwire_service import SignalWireService
import logging

signalwire_bp = Blueprint('signalwire', __name__)

@signalwire_bp.route('/search-numbers', methods=['POST', 'OPTIONS'])
@cross_origin()
def search_numbers():
    """Search for available phone numbers"""
    try:
        if request.method == 'OPTIONS':
            return '', 204
        
        data = request.get_json() or {}
        signalwire = SignalWireService()
        result = signalwire.search_available_numbers(**data)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@signalwire_bp.route('/subaccount', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin()
def handle_subaccount():
    """Create or get subaccount"""
    try:
        if request.method == 'OPTIONS':
            return '', 204
            
        signalwire = SignalWireService()
        
        if request.method == 'POST':
            data = request.get_json() or {}
            result = signalwire.create_subproject(
                user_id=data.get('user_id'),
                friendly_name=data.get('friendly_name', 'User Subproject')
            )
        else:
            # For GET, return a placeholder or implement actual subaccount lookup
            result = {
                'success': True,
                'subproject': {
                    'sid': 'placeholder-subproject-sid',
                    'friendly_name': 'User Subproject',
                    'status': 'active'
                }
            }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@signalwire_bp.route('/purchase-number', methods=['POST', 'OPTIONS'])
@cross_origin()
def purchase_number():
    """Purchase a phone number"""
    try:
        if request.method == 'OPTIONS':
            return '', 204
        
        data = request.get_json() or {}
        signalwire = SignalWireService()
        result = signalwire.purchase_number(
            phone_number=data.get('phone_number'),
            subproject_sid=data.get('subproject_sid'),
            friendly_name=data.get('friendly_name')
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@signalwire_bp.route('/setup-tenant', methods=['POST', 'OPTIONS'])
@cross_origin()
def setup_complete_tenant():
    """Complete tenant setup workflow"""
    try:
        if request.method == 'OPTIONS':
            return '', 204
        
        data = request.get_json() or {}
        signalwire = SignalWireService()
        
        result = signalwire.setup_new_tenant(
            user_id=data.get('user_id'),
            friendly_name=data.get('friendly_name'),
            phone_search_criteria=data.get('phone_search', {})
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@signalwire_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """SignalWire service health check"""
    try:
        signalwire = SignalWireService()
        result = signalwire.health_check()
        
        status_code = 200 if result['success'] else 503
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'success': False,
            'service_status': 'unhealthy',
            'error': str(e)
        }), 503
