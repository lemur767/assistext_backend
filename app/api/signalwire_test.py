# app/api/signalwire_test.py - Test connection endpoint for SignalWire

from flask import Blueprint, jsonify
from flask_restful import Resource, Api
from flask_jwt_extended import jwt_required
from app.utils.signalwire_helpers import test_signalwire_connection, get_purchased_numbers
import logging

logger = logging.getLogger(__name__)

# Create blueprint
signalwire_test_bp = Blueprint('signalwire_test', __name__)
api = Api(signalwire_test_bp)

class SignalWireConnectionTestAPI(Resource):
    """Test SignalWire connection and return account status"""
    
    @jwt_required()
    def get(self):
        try:
            # Test the connection
            is_connected, error_message, account_info = test_signalwire_connection()
            
            if is_connected:
                # Also get current phone numbers to show full status
                phone_numbers, phone_error = get_purchased_numbers()
                
                return {
                    'is_connected': True,
                    'error_message': '',
                    'account_info': account_info,
                    'phone_numbers_count': len(phone_numbers),
                    'phone_numbers': phone_numbers[:5],  # Return first 5 for preview
                    'status': 'operational'
                }, 200
            else:
                return {
                    'is_connected': False,
                    'error_message': error_message,
                    'account_info': {},
                    'status': 'error'
                }, 200
                
        except Exception as e:
            logger.error(f"Connection test error: {str(e)}")
            return {
                'is_connected': False,
                'error_message': f'Connection test failed: {str(e)}',
                'account_info': {},
                'status': 'error'
            }, 500

class SignalWireAccountInfoAPI(Resource):
    """Get detailed SignalWire account information"""
    
    @jwt_required()
    def get(self):
        try:
            is_connected, error_message, account_info = test_signalwire_connection()
            
            if not is_connected:
                return {
                    'error': error_message,
                    'connected': False
                }, 503
            
            # Get additional account details
            phone_numbers, phone_error = get_purchased_numbers()
            
            # Calculate usage statistics
            sms_enabled_count = sum(1 for num in phone_numbers if num.get('capabilities', {}).get('sms', False))
            voice_enabled_count = sum(1 for num in phone_numbers if num.get('capabilities', {}).get('voice', False))
            
            return {
                'connected': True,
                'account_info': account_info,
                'statistics': {
                    'total_phone_numbers': len(phone_numbers),
                    'sms_enabled_numbers': sms_enabled_count,
                    'voice_enabled_numbers': voice_enabled_count
                },
                'phone_numbers': phone_numbers,
                'last_updated': datetime.utcnow().isoformat()
            }, 200
            
        except Exception as e:
            logger.error(f"Account info error: {str(e)}")
            return {
                'error': f'Failed to get account info: {str(e)}',
                'connected': False
            }, 500

# Register endpoints
api.add_resource(SignalWireConnectionTestAPI, '/test-connection')
api.add_resource(SignalWireAccountInfoAPI, '/account-info')

# Simple health check endpoint
@signalwire_test_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check for SignalWire integration"""
    try:
        is_connected, error_message, _ = test_signalwire_connection()
        
        if is_connected:
            return jsonify({
                'status': 'healthy',
                'signalwire_connected': True,
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'degraded',
                'signalwire_connected': False,
                'error': error_message,
                'timestamp': datetime.utcnow().isoformat()
            }), 200
            
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'signalwire_connected': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500