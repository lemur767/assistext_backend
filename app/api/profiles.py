# app/api/profiles.py - Clean and working version
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.profile import Profile
from app.models.user import User
from app.extensions import db
from datetime import datetime
import logging
from signalwire.rest import Client as SignalWireClient

# Import SignalWire functions - only once, cleanly
try:
    from app.utils.signalwire_helpers import (
        
        send_sms,
        get_signalwire_phone_numbers,
        configure_number_webhook,
        format_phone_display
    )
    SIGNALWIRE_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("✅ SignalWire helpers imported successfully in profiles.py")
except ImportError as e:
    SIGNALWIRE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.error(f"❌ SignalWire import error in profiles.py: {e}")

profiles_bp = Blueprint('profiles', __name__)

# =============================================================================
# PROFILE CRUD OPERATIONS
# =============================================================================

@profiles_bp.route('', methods=['GET'])
@jwt_required()
def get_profiles():
    """Get all profiles for the authenticated user"""
    try:
        user_id = get_jwt_identity()
        
        profiles = Profile.query.filter_by(user_id=user_id).all()
        
        # Add SignalWire status to each profile
        profiles_data = []
        for profile in profiles:
            profile_data = profile.to_dict()
            
            # Add SignalWire information if available
            if SIGNALWIRE_AVAILABLE and profile.phone_number:
                profile_data['signalwire_configured'] = True
                profile_data['formatted_number'] = format_phone_display(profile.phone_number)
            else:
                profile_data['signalwire_configured'] = False
                
            profiles_data.append(profile_data)
        
        return jsonify({
            'success': True,
            'profiles': profiles_data
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
        
        # Get profile data
        profile_data = profile.to_dict()
        
        # Add SignalWire status information
        if SIGNALWIRE_AVAILABLE and profile.phone_number:
            profile_data['signalwire_configured'] = True
            profile_data['formatted_number'] = format_phone_display(profile.phone_number)
        else:
            profile_data['signalwire_configured'] = False
        
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
        if not data.get('name'):
            return jsonify({'error': 'Profile name is required'}), 400
        
        # Check if phone number is provided and format it
        phone_number = data.get('phone_number')
        if phone_number:
            # Basic phone number formatting
            phone_number = phone_number.strip()
            if not phone_number.startswith('+'):
                if len(phone_number) == 10:
                    phone_number = '+1' + phone_number
                elif len(phone_number) == 11 and phone_number.startswith('1'):
                    phone_number = '+' + phone_number
        
        # Check if phone number is already in use
        if phone_number:
            existing_profile = Profile.query.filter_by(phone_number=phone_number).first()
            if existing_profile:
                return jsonify({'error': 'Phone number already in use by another profile'}), 400
        
        # Create the profile
        profile = Profile(
            user_id=user_id,
            name=data['name'],
            description=data.get('description', ''),
            phone_number=phone_number,
            is_active=data.get('is_active', True),
            is_default=data.get('is_default', False)
        )
        
        # If this is the user's first profile, make it default
        user_profile_count = Profile.query.filter_by(user_id=user_id).count()
        if user_profile_count == 0:
            profile.is_default = True
        
        db.session.add(profile)
        db.session.commit()
        
        # Configure SignalWire webhook if phone number provided and SignalWire available
        if phone_number and SIGNALWIRE_AVAILABLE:
            try:
                webhook_url = f"{current_app.config.get('BASE_URL', 'https://backend.assitext.ca')}/api/webhooks/signalwire/sms"
                webhook_configured = configure_number_webhook(phone_number, webhook_url)
                
                if webhook_configured:
                    logger.info(f"SignalWire webhook configured for profile {profile.name}")
                else:
                    logger.warning(f"Failed to configure SignalWire webhook for profile {profile.name}")
                    
            except Exception as webhook_error:
                logger.error(f"Error configuring SignalWire webhook: {str(webhook_error)}")
        
        logger.info(f"Created new profile: {profile.name}")
        
        return jsonify({
            'success': True,
            'profile': profile.to_dict(),
            'message': 'Profile created successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating profile: {str(e)}")
        return jsonify({'error': 'Failed to create profile'}), 500

@profiles_bp.route('/<int:profile_id>', methods=['PUT'])
@jwt_required()
def update_profile(profile_id):
    """Update an existing profile"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        # Update fields
        if 'name' in data:
            profile.name = data['name']
        if 'description' in data:
            profile.description = data['description']
        if 'is_active' in data:
            profile.is_active = data['is_active']
        if 'is_default' in data:
            profile.is_default = data['is_default']
            
        # Handle phone number updates
        if 'phone_number' in data:
            new_phone = data['phone_number']
            if new_phone:
                # Format phone number
                if not new_phone.startswith('+'):
                    if len(new_phone) == 10:
                        new_phone = '+1' + new_phone
                    elif len(new_phone) == 11 and new_phone.startswith('1'):
                        new_phone = '+' + new_phone
                
                # Check if already in use by another profile
                existing = Profile.query.filter(
                    Profile.phone_number == new_phone,
                    Profile.id != profile_id
                ).first()
                
                if existing:
                    return jsonify({'error': 'Phone number already in use by another profile'}), 400
                
                profile.phone_number = new_phone
                
                # Configure webhook for new number
                if SIGNALWIRE_AVAILABLE:
                    try:
                        webhook_url = f"{current_app.config.get('BASE_URL', 'https://backend.assitext.ca')}/api/webhooks/signalwire/sms"
                        configure_number_webhook(new_phone, webhook_url)
                    except Exception as webhook_error:
                        logger.error(f"Error configuring webhook for updated number: {str(webhook_error)}")
        
        profile.updated_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Updated profile: {profile.name}")
        
        return jsonify({
            'success': True,
            'profile': profile.to_dict(),
            'message': 'Profile updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500

@profiles_bp.route('/<int:profile_id>', methods=['DELETE'])
@jwt_required()
def delete_profile(profile_id):
    """Delete a profile"""
    try:
        user_id = get_jwt_identity()
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        profile_name = profile.name
        
        # Delete the profile (cascading should handle related records)
        db.session.delete(profile)
        db.session.commit()
        
        logger.info(f"Deleted profile: {profile_name}")
        
        return jsonify({
            'success': True,
            'message': 'Profile deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete profile'}), 500

# =============================================================================
# SIGNALWIRE INTEGRATION
# =============================================================================

@profiles_bp.route('/signalwire/numbers', methods=['GET'])
@jwt_required()
def get_signalwire_numbers():
    """Get available SignalWire phone numbers"""
    try:
        if not SIGNALWIRE_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'SignalWire service not available',
                'available_numbers': []
            }), 503
        
        # Get SignalWire phone numbers
        numbers = get_signalwire_phone_numbers()
        
        # Get assigned numbers
        assigned_profiles = Profile.query.filter(Profile.phone_number.isnot(None)).all()
        assigned_numbers = {profile.phone_number for profile in assigned_profiles}
        
        # Mark which numbers are assigned
        for number in numbers:
            number['assigned'] = number['phone_number'] in assigned_numbers
        
        return jsonify({
            'success': True,
            'available_numbers': numbers
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting SignalWire numbers: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get SignalWire numbers',
            'available_numbers': []
        }), 500

@profiles_bp.route('/<int:profile_id>/signalwire/configure', methods=['POST'])
@jwt_required()
def configure_signalwire_webhook_endpoint(profile_id):
    """Configure SignalWire webhook for a profile"""
    try:
        user_id = get_jwt_identity()
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        if not profile.phone_number:
            return jsonify({'error': 'Profile has no phone number configured'}), 400
        
        if not SIGNALWIRE_AVAILABLE:
            return jsonify({'error': 'SignalWire service not available'}), 503
        
        # Configure webhook
        webhook_url = f"{current_app.config.get('BASE_URL', 'https://backend.assitext.ca')}/api/webhooks/signalwire/sms"
        
        success = configure_number_webhook(profile.phone_number, webhook_url)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'SignalWire webhook configured for {profile.name}',
                'webhook_url': webhook_url
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to configure SignalWire webhook'
            }), 500
            
    except Exception as e:
        logger.error(f"Error configuring SignalWire webhook for profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to configure SignalWire webhook'}), 500

@profiles_bp.route('/<int:profile_id>/test-sms', methods=['POST'])
@jwt_required()
def send_test_sms(profile_id):
    """Send a test SMS from a profile"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        if not profile.phone_number:
            return jsonify({'error': 'Profile has no phone number configured'}), 400
        
        to_number = data.get('to_number')
        message = data.get('message', 'Test message from AssisText!')
        
        if not to_number:
            return jsonify({'error': 'Recipient phone number is required'}), 400
        
        if not SIGNALWIRE_AVAILABLE:
            return jsonify({'error': 'SignalWire service not available'}), 503
        
        # Send SMS
        result = send_sms(
            from_number=profile.phone_number,
            to_number=to_number,
            body=message
        )
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Test SMS sent successfully',
                'message_sid': result.get('message_sid')
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to send SMS')
            }), 500
            
    except Exception as e:
        logger.error(f"Error sending test SMS from profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to send test SMS'}), 500

# =============================================================================
# PROFILE MESSAGES
# =============================================================================

@profiles_bp.route('/<int:profile_id>/messages', methods=['GET'])
@jwt_required()
def get_profile_messages(profile_id):
    """Get messages for a profile"""
    try:
        user_id = get_jwt_identity()
        
        profile = Profile.query.get_or_404(profile_id)
        
        # Check ownership
        if profile.user_id != user_id:
            return jsonify({'error': 'Unauthorized access to profile'}), 403
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Try to import Message model
        try:
            from app.models.message import Message
            
            # Get messages
            messages = Message.query.filter_by(profile_id=profile.id) \
                                    .order_by(Message.created_at.desc()) \
                                    .offset(offset) \
                                    .limit(limit) \
                                    .all()
            
            total_count = Message.query.filter_by(profile_id=profile.id).count()
            
            return jsonify({
                'success': True,
                'messages': [message.to_dict() for message in messages],
                'total_count': total_count
            }), 200
            
        except ImportError:
            # Message model doesn't exist yet
            return jsonify({
                'success': True,
                'messages': [],
                'total_count': 0,
                'note': 'Message model not implemented yet'
            }), 200
        
    except Exception as e:
        logger.error(f"Error getting messages for profile {profile_id}: {str(e)}")
        return jsonify({'error': 'Failed to get profile messages'}), 500

# =============================================================================
# HEALTH CHECK
# =============================================================================

@profiles_bp.route('/health', methods=['GET'])
def profiles_health():
    """Health check for profiles service"""
    try:
        # Count profiles and check database connectivity
        total_profiles = Profile.query.count()
        active_profiles = Profile.query.filter_by(is_active=True).count()
        
        return jsonify({
            'status': 'healthy',
            'service': 'profiles',
            'total_profiles': total_profiles,
            'active_profiles': active_profiles,
            'signalwire_available': SIGNALWIRE_AVAILABLE
        }), 200
        
    except Exception as e:
        logger.error(f"Profiles health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503

# Log successful module loading
logger.info(f"Profiles blueprint loaded successfully - SignalWire available: {SIGNALWIRE_AVAILABLE}")
