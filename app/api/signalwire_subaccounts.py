from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.signalwire_subaccount_service import SignalWireSubAccountService
import asyncio

subaccounts_bp = Blueprint('signalwire_subaccounts', __name__)

@subaccounts_bp.route('/sub-accounts/create', methods=['POST'])
@jwt_required()
async def create_subaccount():
    """Create sub-account and search for available numbers"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['username', 'email']
        if not all(field in data for field in required_fields):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: username, email'
            }), 400
        
        # Build search criteria
        search_criteria = {
            'friendly_name': data.get('friendlyName'),
            'area_code': data.get('searchCriteria', {}).get('areaCode'),
            'country': data.get('searchCriteria', {}).get('country', 'US'),
            'region': data.get('searchCriteria', {}).get('region'),
            'contains': data.get('searchCriteria', {}).get('contains'),
            'sms_enabled': True
        }
        
        # Remove None values
        search_criteria = {k: v for k, v in search_criteria.items() if v is not None}
        
        service = SignalWireSubAccountService()
        result = await service.create_subaccount_and_search_numbers(
            user_id=user_id,
            search_criteria=search_criteria
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@subaccounts_bp.route('/sub-accounts/purchase', methods=['POST'])
@jwt_required()
async def complete_purchase():
    """Complete phone number purchase and webhook setup"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['selectionToken', 'selectedPhoneNumber']
        if not all(field in data for field in required_fields):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: selectionToken, selectedPhoneNumber'
            }), 400
        
        service = SignalWireSubAccountService()
        result = await service.complete_purchase_and_setup(
            selection_token=data['selectionToken'],
            selected_phone_number=data['selectedPhoneNumber'],
            webhook_url=data.get('webhookUrl')
        )
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@subaccounts_bp.route('/sub-accounts/<account_sid>', methods=['GET'])
@jwt_required()
def get_subaccount_details(account_sid):
    """Get sub-account details and phone numbers"""
    try:
        user_id = get_jwt_identity()
        
        # Get sub-account details
        subaccount = db.session.execute(
            """
            SELECT sa.*, array_agg(
                json_build_object(
                    'phone_number', spn.phone_number,
                    'capabilities', spn.capabilities,
                    'webhook_configured', spn.webhook_configured
                )
            ) as phone_numbers
            FROM signalwire_subaccounts sa
            LEFT JOIN subaccount_phone_numbers spn ON sa.id = spn.subaccount_id
            WHERE sa.subaccount_sid = %(sid)s AND sa.user_id = %(user_id)s
            GROUP BY sa.id
            """,
            {'sid': account_sid, 'user_id': user_id}
        ).fetchone()
        
        if not subaccount:
            return jsonify({'error': 'Sub-account not found'}), 404
        
        return jsonify({
            'success': True,
            'subaccount': {
                'sid': subaccount.subaccount_sid,
                'friendly_name': subaccount.friendly_name,
                'status': subaccount.status,
                'monthly_limit': subaccount.monthly_message_limit,
                'current_usage': subaccount.current_usage,
                'phone_numbers': subaccount.phone_numbers,
                'created_at': subaccount.created_at.isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500