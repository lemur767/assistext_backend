from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields

from app.services import get_signalwire_service
from app.utils.validators import validate_request_json

signalwire_bp = Blueprint('signalwire', __name__)

class SearchNumbersSchema(Schema):
    area_code = fields.Str(allow_none=True)
    region = fields.Str(allow_none=True)
    country = fields.Str(missing='US')
    limit = fields.Int(missing=10, validate=lambda x: 1 <= x <= 50)

class PurchaseNumberSchema(Schema):
    phone_number = fields.Str(allow_none=True)
    area_code = fields.Str(allow_none=True)

@signalwire_bp.route('/numbers/search', methods=['GET'])
@jwt_required()
def search_numbers():
    """Search for available phone numbers"""
    try:
        area_code = request.args.get('area_code')
        region = request.args.get('region')
        country = request.args.get('country', 'US')
        limit = min(request.args.get('limit', 10, type=int), 50)
        
        signalwire_service = get_signalwire_service()
        result = signalwire_service.search_available_numbers(
            area_code=area_code,
            region=region,
            country=country,
            limit=limit
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'numbers': result['numbers'],
                'count': result['count'],
                'search_params': result['search_params']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Search numbers error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to search numbers'
        }), 500

@signalwire_bp.route('/numbers/purchase', methods=['POST'])
@jwt_required()
@validate_request_json(PurchaseNumberSchema())
def purchase_number():
    """Purchase a phone number"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        signalwire_service = get_signalwire_service()
        result = signalwire_service.purchase_phone_number(
            user_id=user_id,
            phone_number=data.get('phone_number'),
            area_code=data.get('area_code')
        )
        
        if result['success']:
            # Update user record with new phone number
            from app.models import User
            from app.extensions import db
            
            user = User.query.get(user_id)
            if user:
                user.signalwire_phone_number = result['phone_number']
                user.signalwire_phone_number_sid = result['phone_number_sid']
                db.session.commit()
            
            return jsonify({
                'success': True,
                'phone_number': result['phone_number'],
                'phone_number_sid': result['phone_number_sid'],
                'capabilities': result['capabilities']
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Purchase number error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to purchase number'
        }), 500

@signalwire_bp.route('/numbers', methods=['GET'])
@jwt_required()
def get_user_numbers():
    """Get user's phone numbers"""
    try:
        user_id = get_jwt_identity()
        signalwire_service = get_signalwire_service()
        
        result = signalwire_service.get_user_phone_numbers(user_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'numbers': result['numbers'],
                'count': result['count']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Get user numbers error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch numbers'
        }), 500

@signalwire_bp.route('/test-connection', methods=['GET'])
@jwt_required()
def test_signalwire_connection():
    """Test SignalWire connection"""
    try:
        signalwire_service = get_signalwire_service()
        result = signalwire_service.test_connection()
        
        return jsonify(result), 200 if result['success'] else 400
        
    except Exception as e:
        current_app.logger.error(f"Test connection error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Connection test failed'
        }), 500
