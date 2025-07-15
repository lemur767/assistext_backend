
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.extensions import db
#from app.utils.signalwire_helpers import get_signalwire_client, seac
from marshmallow import Schema, fields, validate, ValidationError
import logging

logger = logging.getLogger(__name__)

user_profile_bp = Blueprint('user_profile', __name__)

# =============================================================================
# VALIDATION SCHEMAS
# =============================================================================

class ProfileUpdateSchema(Schema):
    first_name = fields.Str(allow_none=True, validate=validate.Length(min=1, max=50))
    last_name = fields.Str(allow_none=True, validate=validate.Length(min=1, max=50))
    display_name = fields.Str(allow_none=True, validate=validate.Length(max=100))
    personal_phone = fields.Str(allow_none=True, validate=validate.Length(max=20))
    timezone = fields.Str(allow_none=True, validate=validate.Length(max=50))

class AISettingsSchema(Schema):
    ai_enabled = fields.Bool(allow_none=True)
    ai_personality = fields.Str(allow_none=True)
    ai_response_style = fields.Str(allow_none=True, validate=validate.OneOf(['professional', 'casual', 'custom']))
    ai_language = fields.Str(allow_none=True, validate=validate.Length(max=10))
    use_emojis = fields.Bool(allow_none=True)
    casual_language = fields.Bool(allow_none=True)
    custom_instructions = fields.Str(allow_none=True)

class AutoReplySettingsSchema(Schema):
    auto_reply_enabled = fields.Bool(allow_none=True)
    custom_greeting = fields.Str(allow_none=True)
    out_of_office_enabled = fields.Bool(allow_none=True)
    out_of_office_message = fields.Str(allow_none=True)
    out_of_office_start = fields.DateTime(allow_none=True)
    out_of_office_end = fields.DateTime(allow_none=True)

class BusinessHoursSchema(Schema):
    business_hours_enabled = fields.Bool(allow_none=True)
    business_hours_start = fields.Time(allow_none=True)
    business_hours_end = fields.Time(allow_none=True)
    business_days = fields.Str(allow_none=True)  # Comma-separated numbers 1-7
    after_hours_message = fields.Str(allow_none=True)

class SecuritySettingsSchema(Schema):
    enable_flagged_word_detection = fields.Bool(allow_none=True)
    custom_flagged_words = fields.Str(allow_none=True)
    auto_block_suspicious = fields.Bool(allow_none=True)
    require_manual_review = fields.Bool(allow_none=True)

class SignalWireSettingsSchema(Schema):
    signalwire_phone_number = fields.Str(allow_none=True, validate=validate.Length(max=20))
    signalwire_project_id = fields.Str(allow_none=True, validate=validate.Length(max=100))
    signalwire_space_url = fields.Str(allow_none=True, validate=validate.Length(max=200))

# =============================================================================
# PROFILE ENDPOINTS
# =============================================================================

@user_profile_bp.route('/', methods=['GET'])
@jwt_required()
def get_user_profile():
    """Get the current user's profile information"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        include_settings = request.args.get('include_settings', 'true').lower() == 'true'
        
        return jsonify(user.to_dict(include_settings=include_settings)), 200
        
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        return jsonify({'error': 'Failed to retrieve user profile'}), 500

@user_profile_bp.route('/', methods=['PUT'])
@jwt_required()
def update_user_profile():
    """Update the current user's profile information"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate request data
        schema = ProfileUpdateSchema()
        data = schema.load(request.json)
        
        # Update user fields
        for field in ['first_name', 'last_name', 'display_name', 'personal_phone', 'timezone']:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated profile for user {user_id}")
        
        return jsonify(user.to_dict(include_settings=True)), 200
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update user profile'}), 500

# =============================================================================
# AI SETTINGS
# =============================================================================

@user_profile_bp.route('/ai-settings', methods=['GET'])
@jwt_required()
def get_ai_settings():
    """Get the current user's AI settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        ai_settings = {
            'ai_enabled': user.ai_enabled,
            'ai_personality': user.ai_personality,
            'ai_response_style': user.ai_response_style,
            'ai_language': user.ai_language,
            'use_emojis': user.use_emojis,
            'casual_language': user.casual_language,
            'custom_instructions': user.custom_instructions,
        }
        
        return jsonify(ai_settings), 200
        
    except Exception as e:
        logger.error(f"Error getting AI settings: {str(e)}")
        return jsonify({'error': 'Failed to retrieve AI settings'}), 500

@user_profile_bp.route('/ai-settings', methods=['PUT'])
@jwt_required()
def update_ai_settings():
    """Update the current user's AI settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate request data
        schema = AISettingsSchema()
        data = schema.load(request.json)
        
        # Update AI settings
        for field in ['ai_enabled', 'ai_personality', 'ai_response_style', 'ai_language', 
                     'use_emojis', 'casual_language', 'custom_instructions']:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated AI settings for user {user_id}")
        
        return jsonify({
            'message': 'AI settings updated successfully',
            'ai_settings': {
                'ai_enabled': user.ai_enabled,
                'ai_personality': user.ai_personality,
                'ai_response_style': user.ai_response_style,
                'ai_language': user.ai_language,
                'use_emojis': user.use_emojis,
                'casual_language': user.casual_language,
                'custom_instructions': user.custom_instructions,
            }
        }), 200
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error updating AI settings: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update AI settings'}), 500

# =============================================================================
# AUTO REPLY SETTINGS
# =============================================================================

@user_profile_bp.route('/auto-reply-settings', methods=['GET'])
@jwt_required()
def get_auto_reply_settings():
    """Get the current user's auto reply settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        settings = {
            'auto_reply_enabled': user.auto_reply_enabled,
            'custom_greeting': user.custom_greeting,
            'out_of_office_enabled': user.out_of_office_enabled,
            'out_of_office_message': user.out_of_office_message,
            'out_of_office_start': user.out_of_office_start.isoformat() if user.out_of_office_start else None,
            'out_of_office_end': user.out_of_office_end.isoformat() if user.out_of_office_end else None,
        }
        
        return jsonify(settings), 200
        
    except Exception as e:
        logger.error(f"Error getting auto reply settings: {str(e)}")
        return jsonify({'error': 'Failed to retrieve auto reply settings'}), 500

@user_profile_bp.route('/auto-reply-settings', methods=['PUT'])
@jwt_required()
def update_auto_reply_settings():
    """Update the current user's auto reply settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate request data
        schema = AutoReplySettingsSchema()
        data = schema.load(request.json)
        
        # Update auto reply settings
        for field in ['auto_reply_enabled', 'custom_greeting', 'out_of_office_enabled', 
                     'out_of_office_message', 'out_of_office_start', 'out_of_office_end']:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated auto reply settings for user {user_id}")
        
        return jsonify({'message': 'Auto reply settings updated successfully'}), 200
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error updating auto reply settings: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update auto reply settings'}), 500

# =============================================================================
# BUSINESS HOURS SETTINGS
# =============================================================================

@user_profile_bp.route('/business-hours', methods=['GET'])
@jwt_required()
def get_business_hours():
    """Get the current user's business hours settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        settings = {
            'business_hours_enabled': user.business_hours_enabled,
            'business_hours_start': user.business_hours_start.isoformat() if user.business_hours_start else None,
            'business_hours_end': user.business_hours_end.isoformat() if user.business_hours_end else None,
            'business_days': user.business_days,
            'after_hours_message': user.after_hours_message,
            'is_business_hours': user.is_business_hours(),
        }
        
        return jsonify(settings), 200
        
    except Exception as e:
        logger.error(f"Error getting business hours: {str(e)}")
        return jsonify({'error': 'Failed to retrieve business hours'}), 500

@user_profile_bp.route('/business-hours', methods=['PUT'])
@jwt_required()
def update_business_hours():
    """Update the current user's business hours settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate request data
        schema = BusinessHoursSchema()
        data = schema.load(request.json)
        
        # Update business hours settings
        for field in ['business_hours_enabled', 'business_hours_start', 'business_hours_end', 
                     'business_days', 'after_hours_message']:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated business hours for user {user_id}")
        
        return jsonify({'message': 'Business hours updated successfully'}), 200
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error updating business hours: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update business hours'}), 500

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

@user_profile_bp.route('/security-settings', methods=['GET'])
@jwt_required()
def get_security_settings():
    """Get the current user's security settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        settings = {
            'enable_flagged_word_detection': user.enable_flagged_word_detection,
            'custom_flagged_words': user.custom_flagged_words,
            'auto_block_suspicious': user.auto_block_suspicious,
            'require_manual_review': user.require_manual_review,
            'flagged_words_list': user.get_flagged_words(),
        }
        
        return jsonify(settings), 200
        
    except Exception as e:
        logger.error(f"Error getting security settings: {str(e)}")
        return jsonify({'error': 'Failed to retrieve security settings'}), 500

@user_profile_bp.route('/security-settings', methods=['PUT'])
@jwt_required()
def update_security_settings():
    """Update the current user's security settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate request data
        schema = SecuritySettingsSchema()
        data = schema.load(request.json)
        
        # Update security settings
        for field in ['enable_flagged_word_detection', 'custom_flagged_words', 
                     'auto_block_suspicious', 'require_manual_review']:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated security settings for user {user_id}")
        
        return jsonify({'message': 'Security settings updated successfully'}), 200
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error updating security settings: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update security settings'}), 500

# =============================================================================
# SIGNALWIRE SETTINGS
# =============================================================================

@user_profile_bp.route('/signalwire-settings', methods=['GET'])
@jwt_required()
def get_signalwire_settings():
    """Get the current user's SignalWire settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        settings = {
            'signalwire_phone_number': user.signalwire_phone_number,
            'signalwire_configured': user.signalwire_configured,
            'signalwire_project_id': user.signalwire_project_id,
            'signalwire_space_url': user.signalwire_space_url,
        }
        
        return jsonify(settings), 200
        
    except Exception as e:
        logger.error(f"Error getting SignalWire settings: {str(e)}")
        return jsonify({'error': 'Failed to retrieve SignalWire settings'}), 500

@user_profile_bp.route('/signalwire-settings', methods=['PUT'])
@jwt_required()
def update_signalwire_settings():
    """Update the current user's SignalWire settings"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate request data
        schema = SignalWireSettingsSchema()
        data = schema.load(request.json)
        
        # Update SignalWire settings
        for field in ['signalwire_phone_number', 'signalwire_project_id', 'signalwire_space_url']:
            if field in data and data[field] is not None:
                setattr(user, field, data[field])
        
        # Auto-set configured flag if phone number is provided
        if data.get('signalwire_phone_number'):
            user.signalwire_configured = True
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated SignalWire settings for user {user_id}")
        
        return jsonify({'message': 'SignalWire settings updated successfully'}), 200
        
    except ValidationError as e:
        return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
    except Exception as e:
        logger.error(f"Error updating SignalWire settings: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update SignalWire settings'}), 500
    

# =============================================================================
# ACCOUNT MANAGEMENT
# =============================================================================

@user_profile_bp.route('/deactivate', methods=['POST'])
@jwt_required()
def deactivate_account():
    """Deactivate the current user's account"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user.is_active = False
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Deactivated account for user {user_id}")
        
        return jsonify({'message': 'Account deactivated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deactivating account: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to deactivate account'}), 500

@user_profile_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change the current user's password"""
    user_id = get_jwt_identity()
    
    try:
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.json
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            return jsonify({'error': 'All password fields are required'}), 400
        
        # Verify current password
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Validate new password
        if len(new_password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters long'}), 400
        
        if new_password != confirm_password:
            return jsonify({'error': 'New passwords do not match'}), 400
        
        # Update password
        user.set_password(new_password)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Password changed for user {user_id}")
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to change password'}), 500

# =============================================================================
# DASHBOARD SUMMARY
# =============================================================================

@user_profile_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_summary():
    """Get dashboard summary for the current user"""
    user_id = get_jwt_identity()
    
    try:
        from datetime import timedelta
        from app.models.message import Message
        from app.models.client import Client
        
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Time ranges
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Message stats
        total_messages = Message.query.filter_by(user_id=user_id).count()
        messages_today = Message.query.filter(
            Message.user_id == user_id,
            Message.timestamp >= today
        ).count()
        messages_week = Message.query.filter(
            Message.user_id == user_id,
            Message.timestamp >= week_ago
        ).count()
        
        # Client stats
        total_clients = Client.query.filter_by(user_id=user_id).count()
        new_clients_week = Client.query.filter(
            Client.user_id == user_id,
            Client.created_at >= week_ago
        ).count()
        
        # AI usage
        ai_messages = Message.query.filter_by(
            user_id=user_id, ai_generated=True
        ).count()
        
        # Unread messages
        unread_messages = Message.query.filter_by(
            user_id=user_id, is_read=False, is_incoming=True
        ).count()
        
        summary = {
            'user': user.to_dict(),
            'stats': {
                'total_messages': total_messages,
                'messages_today': messages_today,
                'messages_this_week': messages_week,
                'total_clients': total_clients,
                'new_clients_this_week': new_clients_week,
                'ai_messages': ai_messages,
                'ai_usage_percentage': round((ai_messages / total_messages * 100) if total_messages > 0 else 0, 1),
                'unread_messages': unread_messages,
            },
            'status': {
                'ai_enabled': user.ai_enabled,
                'auto_reply_enabled': user.auto_reply_enabled,
                'signalwire_configured': user.signalwire_configured,
                'out_of_office': user.is_out_of_office(),
                'business_hours': user.is_business_hours(),
            }
        }
        
        return jsonify(summary), 200
        
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {str(e)}")
        return jsonify({'error': 'Failed to retrieve dashboard summary'}), 500