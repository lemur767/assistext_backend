# app/api/twilio.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.profile import Profile
from app.services.twilio_service import TwilioService
from app.extensions import db
from datetime import datetime

twilio_bp = Blueprint('twilio', __name__)

@twilio_bp.route('/account', methods=['GET'])
@jwt_required()
def get_twilio_account():
    """Get Twilio account information"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user.twilio_account_sid:
        return jsonify({
            "has_account": False,
            "message": "No Twilio account is set up",
            "account_options": {
                "can_create_subaccount": True,
                "can_connect_external": True
            }
        }), 200
    
    # Return account info without exposing sensitive credentials
    return jsonify({
        "has_account": True,
        "account_sid": user.twilio_account_sid,
        "api_key_sid": user.twilio_api_key_sid,
        "account_type": user.twilio_account_type,
        "using_parent_account": user.twilio_parent_account
    }), 200

@twilio_bp.route('/account/subaccount', methods=['POST'])
@jwt_required()
def create_twilio_subaccount():
    """Create a new Twilio subaccount"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    # Check if user already has an account
    if user.twilio_account_sid:
        return jsonify({
            "error": "User already has a Twilio account"
        }), 400
    
    # Create Twilio subaccount
    twilio_service = TwilioService()
    success, error = twilio_service.create_subaccount(user)
    
    if not success:
        return jsonify({
            "error": f"Failed to create Twilio account: {error}"
        }), 500
    
    # Save the Twilio credentials
    db.session.commit()
    
    return jsonify({
        "message": "Twilio subaccount created successfully",
        "account_sid": user.twilio_account_sid,
        "api_key_sid": user.twilio_api_key_sid,
        "account_type": "subaccount"
    }), 201

@twilio_bp.route('/account/external', methods=['POST'])
@jwt_required()
def connect_external_account():
    """Connect an existing external Twilio account"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.json
    
    # Check if user already has an account
    if user.twilio_account_sid:
        return jsonify({
            "error": "User already has a Twilio account"
        }), 400
    
    # Get credentials
    account_sid = data.get('account_sid')
    auth_token = data.get('auth_token')
    
    if not account_sid or not auth_token:
        return jsonify({
            "error": "Account SID and Auth Token are required"
        }), 400
    
    # Connect external account
    twilio_service = TwilioService()
    success, error = twilio_service.connect_external_account(user, account_sid, auth_token)
    
    if not success:
        return jsonify({
            "error": f"Failed to connect Twilio account: {error}"
        }), 500
    
    # Save the Twilio credentials
    db.session.commit()
    
    return jsonify({
        "message": "External Twilio account connected successfully",
        "account_sid": user.twilio_account_sid,
        "api_key_sid": user.twilio_api_key_sid,
        "account_type": "external"
    }), 201

@twilio_bp.route('/phone-numbers/available', methods=['GET'])
@jwt_required()
def get_available_phone_numbers():
    """Get available phone numbers for purchase"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    # Required parameters
    country_code = request.args.get('country', 'US')
    area_code = request.args.get('area_code')
    
    if not user.twilio_account_sid:
        return jsonify({
            "error": "User does not have a Twilio account"
        }), 400
    
    try:
        # Connect with user's credentials
        twilio_service = TwilioService(user)
        
        # Search for available numbers
        search_params = {
            'sms_enabled': True,
            'limit': 10
        }
        
        if area_code:
            search_params['area_code'] = area_code
        
        # Use the client from TwilioService
        numbers = twilio_service.client.available_phone_numbers(country_code).local.list(**search_params)
        
        # Format the response
        available_numbers = [{
            'phone_number': n.phone_number,
            'friendly_name': n.friendly_name,
            'locality': getattr(n, 'locality', None),
            'region': getattr(n, 'region', None)
        } for n in numbers]
        
        return jsonify({
            "available_numbers": available_numbers
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error searching for phone numbers: {str(e)}")
        return jsonify({
            "error": f"Failed to search for phone numbers: {str(e)}"
        }), 500

@twilio_bp.route('/phone-numbers', methods=['GET'])
@jwt_required()
def get_account_phone_numbers():
    """Get all phone numbers in the user's Twilio account"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user.twilio_account_sid:
        return jsonify({
            "error": "User does not have a Twilio account"
        }), 400
    
    # Get phone numbers
    twilio_service = TwilioService(user)
    success, result = twilio_service.get_account_phone_numbers()
    
    if not success:
        return jsonify({
            "error": f"Failed to get phone numbers: {result}"
        }), 500
    
    return jsonify({
        "phone_numbers": result
    }), 200

@twilio_bp.route('/phone-numbers', methods=['POST'])
@jwt_required()
def purchase_phone_number():
    """Purchase a phone number"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.json
    
    if not user.twilio_account_sid:
        return jsonify({
            "error": "User does not have a Twilio account"
        }), 400
    
    # Get parameters
    phone_number = data.get('phone_number')
    area_code = data.get('area_code')
    country_code = data.get('country_code', 'US')
    profile_id = data.get('profile_id')
    
    if not phone_number and not area_code:
        return jsonify({
            "error": "Either phone_number or area_code is required"
        }), 400
    
    # Purchase phone number
    twilio_service = TwilioService(user)
    success, result = twilio_service.purchase_phone_number(area_code, country_code)
    
    if not success:
        return jsonify({
            "error": f"Failed to purchase phone number: {result}"
        }), 500
    
    # If profile_id is provided, assign the number to that profile
    if profile_id:
        profile = Profile.query.get(profile_id)
        if profile and profile.user_id == user_id:
            profile.phone_number = result
            db.session.commit()
    
    return jsonify({
        "message": "Phone number purchased successfully",
        "phone_number": result
    }), 201

@twilio_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage():
    """Get Twilio usage information for billing"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user.twilio_account_sid or not user.twilio_usage_tracker:
        return jsonify({
            "error": "User does not have a Twilio account or usage tracker"
        }), 400
    
    # Update usage data first
    twilio_service = TwilioService(user)
    success, result = twilio_service.update_usage_tracking()
    
    if not success:
        return jsonify({
            "error": f"Failed to update usage data: {result}"
        }), 500
    
    # Return usage data
    return jsonify({
        "usage": {
            "sms_count": user.twilio_usage_tracker.sms_count,
            "voice_minutes": user.twilio_usage_tracker.voice_minutes,
            "phone_numbers": user.twilio_usage_tracker.phone_numbers,
            "current_bill_amount": user.twilio_usage_tracker.current_bill_amount,
            "last_bill_amount": user.twilio_usage_tracker.last_bill_amount,
            "last_bill_date": user.twilio_usage_tracker.last_bill_date.isoformat() if user.twilio_usage_tracker.last_bill_date else None
        },
        "rates": {
            "sms_rate": current_app.config.get('SMS_RATE'),
            "voice_rate": current_app.config.get('VOICE_RATE'),
            "number_rate": current_app.config.get('NUMBER_RATE')
        }
    }), 200