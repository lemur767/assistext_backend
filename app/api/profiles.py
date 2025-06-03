from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.profile import Profile
from app.models.user import User
from app.models.auto_reply import AutoReply
from app.models.text_example import TextExample
from app.services.twilio_service import TwilioService
from app.extensions import db
import json

profiles_bp = Blueprint('profiles', __name__)

@profiles_bp.route('', methods=['GET'])
@jwt_required()
def get_profiles():
    user_id = get_jwt_identity()
    
    
    # Fetch profiles
    profiles = Profile.query.filter_by(user_id=user_id).all()
    
    return jsonify([profile.to_dict() for profile in profiles]), 200

@profiles_bp.route('/<int:profile_id>', methods=['GET'])
@jwt_required()
def get_profile(profile_id):
    user_id = get_jwt_identity()
    
    # Find profile
    profile = Profile.query.get_or_404(profile_id)
    
    # Check ownership
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    return jsonify(profile.to_dict()), 200

@profiles_bp.route('', methods=['POST'])
@jwt_required()
def create_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.json
    
    # Validate required fields
    if not all([data.get('name')]):
        return jsonify({"error": "Profile name is required"}), 400
    
    # Check if user has a Twilio account
    if not user.twilio_account_sid:
        return jsonify({
            "error": "You need to set up a Twilio account first",
            "details": "Please set up a Twilio account in your account settings before creating a profile"
        }), 400
    
    # Determine phone number acquisition method
    phone_number = None
    phone_source = data.get('phone_source', 'new')  # 'new', 'existing', 'manual'
    
    if phone_source == 'new':
        # Purchase a new number
        area_code = data.get('area_code')
        country_code = data.get('country_code', 'US')
        
        # Create TwilioService instance with the user
        twilio_service = TwilioService(user)
        success, result = twilio_service.purchase_phone_number(area_code, country_code)
        
        if not success:
            return jsonify({"error": f"Failed to purchase phone number: {result}"}), 400
        
        phone_number = result
        
    elif phone_source == 'existing':
        # Use an existing number from the user's Twilio account
        phone_number = data.get('phone_number')
        if not phone_number:
            return jsonify({"error": "Phone number is required when using an existing number"}), 400
        
        # Create TwilioService instance with the user
        twilio_service = TwilioService(user)
        success, result = twilio_service.setup_sms_webhook(phone_number)
        
        if not success:
            return jsonify({"error": f"Failed to configure webhook for phone number: {result}"}), 400
        
    elif phone_source == 'manual':
        # Manually entered number (no Twilio provisioning)
        phone_number = data.get('phone_number')
        if not phone_number:
            return jsonify({"error": "Phone number is required when manually entering a number"}), 400
    
    else:
        return jsonify({"error": "Invalid phone_source value"}), 400
    
    # Create default business hours
    default_hours = {
        "monday": {"start": "10:00", "end": "22:00"},
        "tuesday": {"start": "10:00", "end": "22:00"},
        "wednesday": {"start": "10:00", "end": "22:00"},
        "thursday": {"start": "10:00", "end": "22:00"},
        "friday": {"start": "10:00", "end": "22:00"},
        "saturday": {"start": "12:00", "end": "22:00"},
        "sunday": {"start": "12:00", "end": "22:00"},
    }
    
    # Create new profile
    profile = Profile(
        user_id=user_id,
        name=data['name'],
        phone_number=phone_number,
        description=data.get('description', ''),
        business_hours=json.dumps(default_hours)
    )
    
    db.session.add(profile)
    db.session.commit()
    
    return jsonify(profile.to_dict()), 201

@profiles_bp.route('/<int:profile_id>/toggle_ai', methods=['POST'])
@jwt_required()
def toggle_ai(profile_id):
    user_id = get_jwt_identity()
    data = request.json
    
    # Find profile
    profile = Profile.query.get_or_404(profile_id)
    
    # Check ownership
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Update AI setting
    profile.ai_enabled = data.get('enabled', not profile.ai_enabled)
    db.session.commit()
    
    return jsonify({
        "success": True,
        "ai_enabled": profile.ai_enabled
    }), 200

# Auto-reply endpoints
@profiles_bp.route('/<int:profile_id>/auto_replies', methods=['GET'])
@jwt_required()
def get_auto_replies(profile_id):
    user_id = get_jwt_identity()
    
    # Find profile
    profile = Profile.query.get_or_404(profile_id)
    
    # Check ownership
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get auto replies
    auto_replies = AutoReply.query.filter_by(profile_id=profile_id).all()
    
    return jsonify([ar.to_dict() for ar in auto_replies]), 200

# Text examples endpoints
@profiles_bp.route('/<int:profile_id>/text_examples', methods=['GET'])
@jwt_required()
def get_text_examples(profile_id):
    user_id = get_jwt_identity()
    
    # Find profile
    profile = Profile.query.get_or_404(profile_id)
    
    # Check ownership
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get text examples
    examples = TextExample.query.filter_by(profile_id=profile_id).all()
    
    return jsonify([ex.to_dict() for ex in examples]), 200
