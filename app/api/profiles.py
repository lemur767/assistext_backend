from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.profile import Profile
from app.models.user import User
from app.utils.signalwire_helpers import (
    get_signalwire_phone_numbers,
    is_signalwire_number_available,
    format_phone_number
)
from app.services.signalwire_service import configure_profile_signalwire_webhook
from app.extensions import db
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)
profiles_bp = Blueprint('profiles', __name__)

@profiles_bp.route('', methods=['GET'])
@jwt_required()
def get_profiles():
    """Get all profiles for the authenticated user"""
    try:
        user_id = get_jwt_identity()
        
        profiles = Profile.query.filter_by(user_id=user_id).all()
        
        return jsonify({
            'success': True,
            'profiles': [profile.to_dict() for profile in profiles]
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting profiles: {str(e)}")
        return jsonify({'error': 'Failed to retrieve profiles'}), 500

@profiles_bp.route('/<int:profile_id>', methods=['GET'])
@jwt_required()
def get_profile(profile_id):
    """Get specific profile by ID"""
    try:
        user_id = get_jwt_identity()
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        # Include additional SignalWire information
        profile_data = profile.to_dict()
        
        # Add SignalWire status information
        if profile.phone_number:
            profile_data['signalwire_number_available'] = is_signalwire_number_available(profile.phone_number)
        
        return jsonify({
            'success': True,
            'profile': profile_data
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve profile'}), 500

@profiles_bp.route('', methods=['POST'])
@jwt_required()
def create_profile():
    """Create a new profile"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        # Validate required fields
        if not all([data.get('name'), data.get('phone_number')]):
            return jsonify({'error': 'Missing required fields: name and phone_number'}), 400
        
        # Format and validate phone number
        try:
            formatted_phone = format_phone_number(data['phone_number'])
        except ValueError as e:
            return jsonify({'error': f'Invalid phone number format: {str(e)}'}), 400
        
        # Check if phone number is already in use
        if Profile.query.filter_by(phone_number=formatted_phone).first():
            return jsonify({'error': 'Phone number already in use by another profile'}), 400
        
        # Verify phone number is available in SignalWire
        if not is_signalwire_number_available(formatted_phone):
            available_numbers = get_signalwire_phone_numbers()
            return jsonify({
                'error': 'Phone number not available in your SignalWire project',
                'available_numbers': [num['phone_number'] for num in available_numbers]
            }), 400
        
        # Create default business hours
        default_hours = {
            "monday": {"start": "09:00", "end": "22:00"},
            "tuesday": {"start": "09:00", "end": "22:00"},
            "wednesday": {"start": "09:00", "end": "22:00"},
            "thursday": {"start": "09:00", "end": "22:00"},
            "friday": {"start": "09:00", "end": "22:00"},
            "saturday": {"start": "10:00", "end": "22:00"},
            "sunday": {"start": "10:00", "end": "20:00"}
        }
        
        # Create new profile
        profile = Profile(
            user_id=user_id,
            name=data['name'],
            phone_number=formatted_phone,
            description=data.get('description', ''),
            timezone=data.get('timezone', 'UTC'),
            business_hours=json.dumps(default_hours),
            ai_enabled=data.get('ai_enabled', False),
            daily_auto_response_limit=data.get('daily_auto_response_limit', 100)
        )
        
        db.session.add(profile)
        db.session.commit()
        
        # Configure SignalWire webhook for this profile
        webhook_result = configure_profile_signalwire_webhook(profile.id)
        
        logger.info(f"Created profile {profile.name} for user {user_id}")
        
        response_data = profile.to_dict()
        response_data['signalwire_webhook_setup'] = webhook_result
        
        return jsonify({
            'success': True,
            'message': 'Profile created successfully',
            'profile': response_data
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating profile: {str(e)}")
        return jsonify({'error': 'Failed to create profile'}), 500

@profiles_bp.route('/<int:profile_id>', methods=['PUT'])
@jwt_required()
def update_profile(profile_id):
    """Update existing profile"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        # Update basic fields
        if 'name' in data:
            profile.name = data['name']
        
        if 'description' in data:
            profile.description = data['description']
        
        if 'timezone' in data:
            profile.timezone = data['timezone']
        
        if 'ai_enabled' in data:
            profile.ai_enabled = data['ai_enabled']
        
        if 'daily_auto_response_limit' in data:
            profile.daily_auto_response_limit = data['daily_auto_response_limit']
        
        if 'business_hours' in data:
            profile.set_business_hours(data['business_hours'])
        
        # Handle phone number change
        if 'phone_number' in data:
            try:
                formatted_phone = format_phone_number(data['phone_number'])
            except ValueError as e:
                return jsonify({'error': f'Invalid phone number format: {str(e)}'}), 400
            
            # Check if new phone number is already in use (by another profile)
            existing_profile = Profile.query.filter_by(phone_number=formatted_phone).first()
            if existing_profile and existing_profile.id != profile.id:
                return jsonify({'error': 'Phone number already in use by another profile'}), 400
            
            # Verify new phone number is available in SignalWire
            if not is_signalwire_number_available(formatted_phone):
                available_numbers = get_signalwire_phone_numbers()
                return jsonify({
                    'error': 'Phone number not available in your SignalWire project',
                    'available_numbers': [num['phone_number'] for num in available_numbers]
                }), 400
            
            profile.phone_number = formatted_phone
            
            # Reconfigure SignalWire webhook for new number
            webhook_result = configure_profile_signalwire_webhook(profile.id)
            if not webhook_result['success']:
                logger.warning(f"Failed to configure SignalWire webhook for updated profile: {webhook_result}")
        
        profile.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated profile {profile.name}")
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'profile': profile.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500

@profiles_bp.route('/<int:profile_id>', methods=['DELETE'])
@jwt_required()
def delete_profile(profile_id):
    """Delete profile"""
    try:
        user_id = get_jwt_identity()
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        profile_name = profile.name
        
        # Delete associated messages first (cascade should handle this, but let's be explicit)
        from app.models.message import Message
        Message.query.filter_by(profile_id=profile.id).delete()
        
        # Delete the profile
        db.session.delete(profile)
        db.session.commit()
        
        logger.info(f"Deleted profile {profile_name}")
        
        return jsonify({
            'success': True,
            'message': 'Profile deleted successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete profile'}), 500

@profiles_bp.route('/<int:profile_id>/toggle_ai', methods=['POST'])
@jwt_required()
def toggle_ai(profile_id):
    """Toggle AI responses for profile"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        # Toggle AI setting
        if 'enabled' in data:
            profile.ai_enabled = data['enabled']
        else:
            profile.ai_enabled = not profile.ai_enabled
        
        profile.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Toggled AI for profile {profile.name}: {profile.ai_enabled}")
        
        return jsonify({
            'success': True,
            'ai_enabled': profile.ai_enabled,
            'message': f"AI responses {'enabled' if profile.ai_enabled else 'disabled'} for {profile.name}"
        }), 200
        
    except Exception as e:
        logger.error(f"Error toggling AI for profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to toggle AI setting'}), 500

@profiles_bp.route('/<int:profile_id>/signalwire/configure', methods=['POST'])
@jwt_required()
def configure_signalwire_webhook(profile_id):
    """Configure SignalWire webhook for specific profile"""
    try:
        user_id = get_jwt_identity()
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        # Configure SignalWire webhook
        result = configure_profile_signalwire_webhook(profile.id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'SignalWire webhook configured for {profile.name}',
                'signalwire_number_sid': result.get('number_sid')
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to configure SignalWire webhook')
            }), 400
        
    except Exception as e:
        logger.error(f"Error configuring SignalWire webhook for profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to configure SignalWire webhook'}), 500

@profiles_bp.route('/<int:profile_id>/signalwire/status', methods=['GET'])
@jwt_required()
def get_signalwire_status(profile_id):
    """Get SignalWire configuration status for profile"""
    try:
        user_id = get_jwt_identity()
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        # Check SignalWire configuration
        signalwire_configured = profile.is_signalwire_configured()
        number_available = is_signalwire_number_available(profile.phone_number) if profile.phone_number else False
        
        return jsonify({
            'success': True,
            'signalwire_status': {
                'configured': signalwire_configured,
                'phone_number': profile.phone_number,
                'number_available_in_signalwire': number_available,
                'webhook_configured': profile.signalwire_webhook_configured,
                'number_sid': profile.signalwire_number_sid,
                'last_sync': profile.signalwire_last_sync.isoformat() if profile.signalwire_last_sync else None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting SignalWire status for profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to get SignalWire status'}), 500

@profiles_bp.route('/signalwire/available-numbers', methods=['GET'])
@jwt_required()
def get_available_signalwire_numbers():
    """Get available SignalWire phone numbers"""
    try:
        numbers = get_signalwire_phone_numbers()
        
        # Check which numbers are already assigned to profiles
        assigned_numbers = {p.phone_number for p in Profile.query.all() if p.phone_number}
        
        for number in numbers:
            number['assigned'] = number['phone_number'] in assigned_numbers
        
        return jsonify({
            'success': True,
            'available_numbers': numbers
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting available SignalWire numbers: {str(e)}")
        return jsonify({'error': 'Failed to get available SignalWire numbers'}), 500

@profiles_bp.route('/<int:profile_id>/messages', methods=['GET'])
@jwt_required()
def get_profile_messages(profile_id):
    """Get recent messages for profile"""
    try:
        user_id = get_jwt_identity()
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Get messages
        from app.models.message import Message
        messages = Message.query.filter_by(profile_id=profile.id) \
                                .order_by(Message.timestamp.desc()) \
                                .offset(offset) \
                                .limit(limit) \
                                .all()
        
        return jsonify({
            'success': True,
            'messages': [message.to_dict() for message in messages],
            'total_count': Message.query.filter_by(profile_id=profile.id).count()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting messages for profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to get profile messages'}), 500

@profiles_bp.route('/health', methods=['GET'])
def profiles_health():
    """Health check for profiles service"""
    try:
        # Count profiles and check database connectivity
        total_profiles = Profile.query.count()
        configured_profiles = Profile.query.filter_by(signalwire_webhook_configured=True).count()
        
        return jsonify({
            'status': 'healthy',
            'service': 'profiles',
            'total_profiles': total_profiles,
            'signalwire_configured_profiles': configured_profiles
        }), 200
        
    except Exception as e:
        logger.error(f"Profiles health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503
