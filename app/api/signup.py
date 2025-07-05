"""
Updated Signup API with Automatic Webhook Configuration
app/api/signup.py - Complete phone number purchasing with webhook setup
"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.signalwire_service import SignalWireService
from app.models.user import User
from app.models.profile import Profile
from app.extensions import db
import logging

signup_bp = Blueprint('signup', __name__)

# Initialize SignalWire service
signalwire_service = SignalWireService()

@signup_bp.route('/search-numbers', methods=['POST'])
@jwt_required()
def search_available_numbers():
    """
    Search for available phone numbers
    
    Request body:
    {
        "country": "US|CA",
        "area_code": "416",
        "city": "Toronto", 
        "region": "ON",
        "contains": "555",
        "limit": 10
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Validate search parameters
        search_criteria = {
            'country': data.get('country', 'US').upper(),
            'area_code': data.get('area_code'),
            'city': data.get('city'),
            'region': data.get('region'),
            'contains': data.get('contains'),
            'limit': min(data.get('limit', 10), 20)  # Max 20 for performance
        }
        
        # Remove None values
        search_criteria = {k: v for k, v in search_criteria.items() if v is not None}
        
        current_app.logger.info(f"User {user_id} searching numbers with criteria: {search_criteria}")
        
        # Search for available numbers
        result = signalwire_service.search_available_numbers(search_criteria)
        
        if result['success']:
            return jsonify({
                'success': True,
                'numbers': result['numbers'],
                'count': result['count'],
                'search_criteria': result['search_criteria']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Number search error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@signup_bp.route('/purchase-number', methods=['POST'])
@jwt_required()
def purchase_phone_number():
    """
    Purchase phone number and automatically configure webhooks
    
    Request body:
    {
        "phone_number": "+14165551234",
        "friendly_name": "My Business Line",
        "profile_name": "Business Profile",
        "business_type": "Restaurant",
        "timezone": "America/Toronto"
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Validate required fields
        phone_number = data.get('phone_number')
        if not phone_number:
            return jsonify({'error': 'phone_number is required'}), 400
        
        # Normalize phone number format
        if not phone_number.startswith('+'):
            phone_number = f"+{phone_number.strip()}"
        
        # Get user details
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check if user already has this number
        existing_profile = Profile.query.filter_by(
            user_id=user_id,
            phone_number=phone_number
        ).first()
        
        if existing_profile:
            return jsonify({'error': 'Phone number already associated with your account'}), 400
        
        # Prepare profile data for purchase
        profile_data = {
            'user_id': user_id,
            'friendly_name': data.get('friendly_name', f"AssisText Number {phone_number[-4:]}"),
            'profile_name': data.get('profile_name', 'Default Profile'),
            'business_type': data.get('business_type', 'General'),
            'timezone': data.get('timezone', 'America/Toronto')
        }
        
        current_app.logger.info(f"User {user_id} purchasing number: {phone_number}")
        
        # Purchase phone number with automatic webhook configuration
        purchase_result = signalwire_service.purchase_phone_number(phone_number, profile_data)
        
        if not purchase_result['success']:
            return jsonify({
                'success': False,
                'error': purchase_result['error']
            }), 400
        
        # Create profile in database
        try:
            new_profile = Profile(
                user_id=user_id,
                name=profile_data['profile_name'],
                phone_number=phone_number,
                phone_number_sid=purchase_result['purchase_details']['phone_number_sid'],
                business_type=profile_data['business_type'],
                timezone=profile_data['timezone'],
                ai_enabled=True,  # Enable AI by default
                is_active=True,
                friendly_name=profile_data['friendly_name']
            )
            
            db.session.add(new_profile)
            db.session.commit()
            
            current_app.logger.info(f"Created profile {new_profile.id} for user {user_id}")
            
        except Exception as db_error:
            current_app.logger.error(f"Database error: {str(db_error)}")
            db.session.rollback()
            
            # Try to release the purchased number if database fails
            try:
                signalwire_service.release_phone_number(
                    purchase_result['purchase_details']['phone_number_sid']
                )
            except:
                pass  # Best effort cleanup
            
            return jsonify({'error': 'Failed to create profile'}), 500
        
        # Return success response with all details
        return jsonify({
            'success': True,
            'message': 'Phone number purchased and configured successfully',
            'purchase_details': purchase_result['purchase_details'],
            'webhook_configuration': purchase_result['webhook_configuration'],
            'profile': {
                'id': new_profile.id,
                'name': new_profile.name,
                'phone_number': new_profile.phone_number,
                'business_type': new_profile.business_type,
                'ai_enabled': new_profile.ai_enabled
            }
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Phone number purchase error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@signup_bp.route('/verify-webhooks/<profile_id>', methods=['GET'])
@jwt_required()
def verify_webhook_configuration(profile_id):
    """Verify webhook configuration for a profile's phone number"""
    try:
        user_id = get_jwt_identity()
        
        # Get profile
        profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        if not profile.phone_number_sid:
            return jsonify({'error': 'No phone number SID found for profile'}), 400
        
        # Verify webhook configuration
        verification_result = signalwire_service._verify_webhook_configuration(profile.phone_number_sid)
        
        return jsonify({
            'success': True,
            'profile_id': profile_id,
            'phone_number': profile.phone_number,
            'webhook_verification': verification_result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Webhook verification error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@signup_bp.route('/update-webhooks/<profile_id>', methods=['PUT'])
@jwt_required()
def update_webhook_configuration(profile_id):
    """
    Update webhook configuration for a profile's phone number
    
    Request body:
    {
        "sms_url": "https://custom.webhook.url/sms",
        "voice_url": "https://custom.webhook.url/voice",
        "status_callback": "https://custom.webhook.url/status"
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Get profile
        profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        if not profile.phone_number_sid:
            return jsonify({'error': 'No phone number SID found for profile'}), 400
        
        # Update webhook configuration
        update_result = signalwire_service.update_phone_number_webhooks(
            profile.phone_number_sid,
            data
        )
        
        if update_result['success']:
            return jsonify({
                'success': True,
                'profile_id': profile_id,
                'phone_number': profile.phone_number,
                'updated_configuration': update_result['updated_configuration']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': update_result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Webhook update error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@signup_bp.route('/my-numbers', methods=['GET'])
@jwt_required()
def list_user_phone_numbers():
    """List all phone numbers owned by the current user"""
    try:
        user_id = get_jwt_identity()
        
        # Get user's profiles with phone numbers
        profiles = Profile.query.filter_by(user_id=user_id, is_active=True).all()
        
        user_numbers = []
        for profile in profiles:
            if profile.phone_number:
                number_info = {
                    'profile_id': profile.id,
                    'profile_name': profile.name,
                    'phone_number': profile.phone_number,
                    'phone_number_sid': profile.phone_number_sid,
                    'business_type': profile.business_type,
                    'ai_enabled': profile.ai_enabled,
                    'friendly_name': profile.friendly_name,
                    'created_at': profile.created_at.isoformat() if profile.created_at else None
                }
                user_numbers.append(number_info)
        
        return jsonify({
            'success': True,
            'phone_numbers': user_numbers,
            'count': len(user_numbers)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error listing user numbers: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@signup_bp.route('/release-number/<profile_id>', methods=['DELETE'])
@jwt_required()
def release_phone_number(profile_id):
    """Release (delete) a phone number"""
    try:
        user_id = get_jwt_identity()
        
        # Get profile
        profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        if not profile.phone_number_sid:
            return jsonify({'error': 'No phone number SID found for profile'}), 400
        
        phone_number = profile.phone_number
        
        # Release the number from SignalWire
        release_result = signalwire_service.release_phone_number(profile.phone_number_sid)
        
        if release_result['success']:
            # Deactivate the profile
            profile.is_active = False
            profile.phone_number_sid = None
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Phone number {phone_number} has been released',
                'profile_id': profile_id
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': release_result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Number release error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@signup_bp.route('/signalwire-status', methods=['GET'])
@jwt_required()
def get_signalwire_status():
    """Get SignalWire service status and configuration"""
    try:
        status = signalwire_service.get_service_status()
        
        return jsonify({
            'success': True,
            'signalwire_status': status,
            'webhook_urls': signalwire_service.webhook_urls
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Status check error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@signup_bp.route('/test-signalwire', methods=['POST'])
@jwt_required()
def test_signalwire_connection():
    """Test SignalWire API connectivity"""
    try:
        if not signalwire_service.is_configured():
            return jsonify({
                'success': False,
                'error': 'SignalWire not configured'
            }), 400
        
        # Test with a simple number search
        test_result = signalwire_service.search_available_numbers({
            'country': 'US',
            'area_code': '555',
            'limit': 1
        })
        
        return jsonify({
            'success': test_result['success'],
            'message': 'SignalWire API test completed',
            'test_result': test_result,
            'service_status': signalwire_service.get_service_status()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"SignalWire test error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500