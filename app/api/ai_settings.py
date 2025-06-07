from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.ai_model_settings import AIModelSettings
from app.models.profile import Profile
from app.extensions import db

ai_settings_bp = Blueprint('ai_settings', __name__)

@ai_settings_bp.route('/<int:profile_id>', methods=['GET'])
@jwt_required()
def get_ai_settings(profile_id):
    user_id = get_jwt_identity()
    
    # Verify profile ownership
    profile = Profile.query.get_or_404(profile_id)
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get or create AI settings
    settings = AIModelSettings.query.filter_by(profile_id=profile_id).first()
    if not settings:
        settings = AIModelSettings(profile_id=profile_id)
        db.session.add(settings)
        db.session.commit()
    
    return jsonify(settings.to_dict()), 200


@ai_settings_bp.route('/<int:profile_id>', methods=['PUT'])
@jwt_required()
def update_ai_settings(profile_id):
    user_id = get_jwt_identity()
    data = request.json
    
    # Verify profile ownership
    profile = Profile.query.get_or_404(profile_id)
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get or create AI settings
    settings = AIModelSettings.query.filter_by(profile_id=profile_id).first()
    if not settings:
        settings = AIModelSettings(profile_id=profile_id)
        db.session.add(settings)
    
    # Update fields
    if 'model_version' in data:
        settings.model_version = data['model_version']
    if 'temperature' in data:
        settings.temperature = float(data['temperature'])
    if 'response_length' in data:
        settings.response_length = int(data['response_length'])
    if 'custom_instructions' in data:
        settings.custom_instructions = data['custom_instructions']
    if 'style_notes' in data:
        settings.style_notes = data['style_notes']
    
    db.session.commit()
    
    return jsonify(settings.to_dict()), 200