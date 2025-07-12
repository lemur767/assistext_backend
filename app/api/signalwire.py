# app/api/signalwire.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.signalwire_service import SignalWireService
from app.extensions import db
import logging

# Create blueprint
signalwire_bp = Blueprint('signalwire', __name__, url_prefix='/api/signalwire')

# Set up logging
logger = logging.getLogger(__name__)

@signalwire_bp.route('/search-numbers', methods=['POST'])
@jwt_required()
def search_numbers():
    """
    Search for available phone numbers and create subaccount
    Frontend call: POST /api/signalwire/search-numbers
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['country', 'region', 'locality']
        if not all(field in data for field in required_fields):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: country, region, locality'
            }), 400
        
        # Build search criteria
        search_criteria = {
            'country': data.get('country', 'CA'),
            'region': data.get('region'),
            'locality': data.get('locality'),
            'area_code': data.get('area_code'),
            'limit': min(data.get('limit', 10), 20)  # Max 20 numbers
        }
        
        # Call SignalWire service
        service = SignalWireService()
        result = service.search_and_create_subaccount(user_id, search_criteria)
        
        if result['success']:
            logger.info(f"Number search successful for user {user_id}")
            return jsonify(result), 200
        else:
            logger.error(f"Number search failed for user {user_id}: {result['error']}")
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Search numbers endpoint error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@signalwire_bp.route('/purchase-number', methods=['POST'])
@jwt_required()
def purchase_number():
    """
    Purchase selected phone number and configure webhook
    Frontend call: POST /api/signalwire/purchase-number
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['selectionToken', 'selectedPhoneNumber']
        if not all(field in data for field in required_fields):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: selectionToken, selectedPhoneNumber'
            }), 400
        
        # Call SignalWire service
        service = SignalWireService()
        result = service.purchase_number_and_configure_webhook(
            selection_token=data['selectionToken'],
            selected_phone_number=data['selectedPhoneNumber'],
            custom_webhook_url=data.get('webhookUrl')
        )
        
        if result['success']:
            logger.info(f"Number purchase successful for user {user_id}: {data['selectedPhoneNumber']}")
            return jsonify(result), 200
        else:
            logger.error(f"Number purchase failed for user {user_id}: {result['error']}")
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Purchase number endpoint error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@signalwire_bp.route('/subaccount', methods=['GET'])
@jwt_required()
def get_subaccount():
    """
    Get existing subaccount for authenticated user
    Frontend call: GET /api/signalwire/subaccount
    """
    try:
        user_id = get_jwt_identity()
        
        # Call SignalWire service
        service = SignalWireService()
        result = service.get_user_subaccount(user_id)
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Get subaccount endpoint error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@signalwire_bp.route('/test-webhook', methods=['POST'])
@jwt_required()
def test_webhook():
    """
    Test webhook configuration for user's subaccount
    Frontend call: POST /api/signalwire/test-webhook
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        if 'subaccount_sid' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: subaccount_sid'
            }), 400
        
        # Verify user owns this subaccount
        subaccount_check = db.session.execute(
            """
            SELECT id FROM signalwire_subaccounts 
            WHERE subaccount_sid = %(sid)s AND user_id = %(user_id)s
            """,
            {'sid': data['subaccount_sid'], 'user_id': user_id}
        ).fetchone()
        
        if not subaccount_check:
            return jsonify({
                'success': False,
                'error': 'Subaccount not found or access denied'
            }), 403
        
        # Call SignalWire service
        service = SignalWireService()
        result = service.test_webhook(data['subaccount_sid'])
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Test webhook endpoint error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@signalwire_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage_stats():
    """
    Get usage statistics for user's subaccount
    Frontend call: GET /api/signalwire/usage
    """
    try:
        user_id = get_jwt_identity()
        
        # Get usage data from database
        result = db.session.execute(
            """
            SELECT 
                sa.monthly_message_limit,
                sa.current_usage,
                COUNT(sc.id) as total_conversations,
                COUNT(CASE WHEN sc.created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as recent_messages
            FROM signalwire_subaccounts sa
            LEFT JOIN subaccount_phone_numbers spn ON sa.id = spn.subaccount_id
            LEFT JOIN sms_conversations sc ON sc.user_id = sa.user_id
            WHERE sa.user_id = %(user_id)s AND sa.status = 'active'
            GROUP BY sa.id, sa.monthly_message_limit, sa.current_usage
            """,
            {'user_id': user_id}
        ).fetchone()
        
        if not result:
            return jsonify({
                'success': False,
                'error': 'No active subaccount found'
            }), 404
        
        usage_percentage = (result.current_usage / result.monthly_message_limit) * 100 if result.monthly_message_limit > 0 else 0
        
        return jsonify({
            'success': True,
            'usage': {
                'monthly_limit': result.monthly_message_limit,
                'current_usage': result.current_usage,
                'usage_percentage': round(usage_percentage, 2),
                'total_conversations': result.total_conversations or 0,
                'recent_messages': result.recent_messages or 0,
                'remaining_messages': result.monthly_message_limit - result.current_usage
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get usage stats endpoint error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

# Webhook endpoints for incoming messages
@signalwire_bp.route('/webhook/sms/<subaccount_sid>', methods=['POST'])
def handle_sms_webhook(subaccount_sid):
  
    try:
        # Validate SignalWire signature (implement signature validation)
        if not _validate_signalwire_signature(request):
            logger.warning(f"Invalid SignalWire signature for subaccount {subaccount_sid}")
            return 'Unauthorized', 401
        
        # Parse webhook data
        webhook_data = {
            'AccountSid': request.form.get('AccountSid'),
            'MessageSid': request.form.get('MessageSid'),
            'From': request.form.get('From'),
            'To': request.form.get('To'),
            'Body': request.form.get('Body'),
            'NumMedia': request.form.get('NumMedia', '0')
        }
        
        logger.info(f"Received SMS webhook for subaccount {subaccount_sid}: {webhook_data['From']} -> {webhook_data['To']}")
        
        # Queue for async processing (using Celery or similar)
        from app.tasks import process_incoming_sms
        process_incoming_sms.delay(subaccount_sid, webhook_data)
        
        # Return immediate LaML response (required by SignalWire)
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {'Content-Type': 'application/xml'}
        
    except Exception as e:
        logger.error(f"SMS webhook error for subaccount {subaccount_sid}: {e}")
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {'Content-Type': 'application/xml'}

@signalwire_bp.route('/webhook/sms/<subaccount_sid>/test', methods=['POST'])
def handle_webhook_test(subaccount_sid):
 
   
    try:
        data = request.get_json()
        logger.info(f"Webhook test received for subaccount {subaccount_sid}: {data}")
        
        return jsonify({
            'success': True,
            'message': 'Webhook test successful',
            'timestamp': data.get('timestamp'),
            'subaccount_sid': subaccount_sid
        }), 200
        
    except Exception as e:
        logger.error(f"Webhook test error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Helper functions

def _validate_signalwire_signature(request) -> bool:

    import hmac
    import hashlib
    import os
    
    try:
        signature = request.headers.get('X-SignalWire-Signature', '')
        url = request.url
        body = request.get_data(as_text=True)
        
        # Your SignalWire auth token as signing key
        auth_token = os.getenv('SIGNALWIRE_TOKEN')
        
        expected = hmac.new(
            auth_token.encode('utf-8'),
            (url + body).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
        
    except Exception as e:
        logger.error(f"Signature validation error: {e}")
        return False

# Error handlers
@signalwire_bp.errorhandler(400)
def bad_request(error):
    return jsonify({
        'success': False,
        'error': 'Bad request'
    }), 400

@signalwire_bp.errorhandler(401)
def unauthorized(error):
    return jsonify({
        'success': False,
        'error': 'Unauthorized'
    }), 401

@signalwire_bp.errorhandler(403)
def forbidden(error):
    return jsonify({
        'success': False,
        'error': 'Forbidden'
    }), 403

@signalwire_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Not found'
    }), 404

@signalwire_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500