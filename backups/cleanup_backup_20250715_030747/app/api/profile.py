from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.extensions import db
from datetime import datetime
import json

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('', methods=['GET'])
@jwt_required()
def get_user_profile():
    """Get current user's profile (single profile per user)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'success': True,
            'profile': user.to_dict(include_sensitive=True)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting profile: {str(e)}")
        return jsonify({'error': 'Failed to get profile'}), 500


@profile_bp.route('', methods=['PUT'])
@jwt_required()
def update_user_profile():
    """Update current user's profile"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update basic profile information
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'display_name' in data:
            user.display_name = data['display_name']
        if 'phone_number' in data:
            user.phone_number = data['phone_number']
        if 'timezone' in data:
            user.timezone = data['timezone']
        if 'email' in data and data['email'] != user.email:
            # Check if email is already taken
            existing_user = User.query.filter_by(email=data['email']).first()
            if existing_user and existing_user.id != user.id:
                return jsonify({'error': 'Email already in use'}), 400
            user.email = data['email']
        
        # Update business settings
        if 'business_hours' in data:
            user.set_business_hours(data['business_hours'])
        if 'auto_reply_enabled' in data:
            user.auto_reply_enabled = data['auto_reply_enabled']
        if 'auto_reply_keywords' in data:
            user.set_auto_reply_keywords(data['auto_reply_keywords'])
        if 'out_of_office_enabled' in data:
            user.out_of_office_enabled = data['out_of_office_enabled']
        if 'out_of_office_message' in data:
            user.out_of_office_message = data['out_of_office_message']
        if 'daily_message_limit' in data:
            user.daily_message_limit = data['daily_message_limit']
        
        # Update AI settings
        if 'ai_enabled' in data:
            user.ai_enabled = data['ai_enabled']
        if 'ai_personality' in data:
            user.ai_personality = data['ai_personality']
        if 'ai_instructions' in data:
            user.ai_instructions = data['ai_instructions']
        if 'ai_model' in data:
            user.ai_model = data['ai_model']
        if 'ai_temperature' in data:
            user.ai_temperature = float(data['ai_temperature'])
        if 'ai_max_tokens' in data:
            user.ai_max_tokens = int(data['ai_max_tokens'])
        
        # Update text examples
      
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'profile': user.to_dict(include_sensitive=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating profile: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500


@profile_bp.route('/signalwire', methods=['GET'])
@jwt_required()
def get_signalwire_config():
    """Get SignalWire configuration"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'success': True,
            'signalwire': {
                'phone_number': user.signalwire_phone_number,
                'project_id': user.signalwire_project_id,
                'space_url': user.signalwire_space_url,
                'webhook_configured': user.signalwire_webhook_configured,
                'is_configured': user.is_signalwire_configured()
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting SignalWire config: {str(e)}")
        return jsonify({'error': 'Failed to get SignalWire config'}), 500


@profile_bp.route('/signalwire', methods=['PUT'])
@jwt_required()
def update_signalwire_config():
    """Update SignalWire configuration"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['project_id', 'auth_token', 'space_url']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Update SignalWire configuration
        user.signalwire_project_id = data['project_id']
        user.signalwire_auth_token = data['auth_token']
        user.signalwire_space_url = data['space_url']
        
        if 'phone_number' in data:
            # Check if phone number is already taken by another user
            existing_user = User.query.filter_by(
                signalwire_phone_number=data['phone_number']
            ).first()
            if existing_user and existing_user.id != user.id:
                return jsonify({'error': 'Phone number already in use'}), 400
            user.signalwire_phone_number = data['phone_number']
        
        # Test connection (you'd implement this based on your SignalWire setup)
        try:
            # TODO: Add actual SignalWire connection test here
            user.signalwire_webhook_configured = True
        except Exception as test_error:
            current_app.logger.warning(f"SignalWire connection test failed: {test_error}")
            user.signalwire_webhook_configured = False
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'SignalWire configuration updated successfully',
            'signalwire': {
                'phone_number': user.signalwire_phone_number,
                'project_id': user.signalwire_project_id,
                'space_url': user.signalwire_space_url,
                'webhook_configured': user.signalwire_webhook_configured,
                'is_configured': user.is_signalwire_configured()
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating SignalWire config: {str(e)}")
        return jsonify({'error': 'Failed to update SignalWire configuration'}), 500


@profile_bp.route('/ai-settings', methods=['GET'])
@jwt_required()
def get_ai_settings():
    """Get AI configuration"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'success': True,
            'ai_settings': user.get_ai_settings(),
            
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting AI settings: {str(e)}")
        return jsonify({'error': 'Failed to get AI settings'}), 500


@profile_bp.route('/ai-settings', methods=['PUT'])
@jwt_required()
def update_ai_settings():
    """Update AI configuration"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update AI settings
        if 'enabled' in data:
            user.ai_enabled = data['enabled']
        if 'personality' in data:
            user.ai_personality = data['personality']
        if 'instructions' in data:
            user.ai_instructions = data['instructions']
        if 'model' in data:
            # Validate model name
            valid_models = ['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo', 'claude-3-sonnet', 'claude-3-opus']
            if data['model'] in valid_models:
                user.ai_model = data['model']
            else:
                return jsonify({'error': 'Invalid AI model'}), 400
        if 'temperature' in data:
            temp = float(data['temperature'])
            if 0.0 <= temp <= 2.0:
                user.ai_temperature = temp
            else:
                return jsonify({'error': 'Temperature must be between 0.0 and 2.0'}), 400
        if 'max_tokens' in data:
            tokens = int(data['max_tokens'])
            if 1 <= tokens <= 1000:
                user.ai_max_tokens = tokens
            else:
                return jsonify({'error': 'Max tokens must be between 1 and 1000'}), 400
        
       
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'AI settings updated successfully',
            'ai_settings': user.get_ai_settings(),
          
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating AI settings: {str(e)}")
        return jsonify({'error': 'Failed to update AI settings'}), 500


@profile_bp.route('/usage-stats', methods=['GET'])
@jwt_required()
def get_usage_stats():
    """Get usage statistics for the user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Reset monthly count if needed
        user.reset_monthly_count_if_needed()
        
        # Get additional stats
        from app.models.message import Message
        from app.models.client import Client
        
        # Count messages for today
        today_count = Message.get_daily_count(user_id)
        
        # Count total clients
        total_clients = Client.get_user_clients(user_id, active_only=False)
        active_clients = Client.get_user_clients(user_id, active_only=True)
        
        # Count unread messages
        unread_count = Message.count_unread(user_id)
        
        return jsonify({
            'success': True,
            'usage_stats': {
                'total_messages_sent': user.total_messages_sent,
                'total_messages_received': user.total_messages_received,
                'monthly_count': user.monthly_message_count,
                'daily_count': today_count,
                'daily_limit': user.daily_message_limit,
                'daily_remaining': max(0, user.daily_message_limit - today_count),
                'total_clients': len(total_clients),
                'active_clients': len(active_clients),
                'unread_messages': unread_count,
                'last_reset_date': user.last_reset_date.isoformat()
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting usage stats: {str(e)}")
        return jsonify({'error': 'Failed to get usage statistics'}), 500


@profile_bp.route('/business-hours', methods=['PUT'])
@jwt_required()
def update_business_hours():
    """Update business hours configuration"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        if not data or 'business_hours' not in data:
            return jsonify({'error': 'Business hours data required'}), 400
        
        # Validate business hours format
        business_hours = data['business_hours']
        required_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        
        for day in required_days:
            if day not in business_hours:
                return jsonify({'error': f'Missing business hours for {day}'}), 400
            
            day_config = business_hours[day]
            if not isinstance(day_config, dict):
                return jsonify({'error': f'Invalid format for {day}'}), 400
            
            required_fields = ['start', 'end', 'enabled']
            for field in required_fields:
                if field not in day_config:
                    return jsonify({'error': f'Missing {field} for {day}'}), 400
        
        user.set_business_hours(business_hours)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Business hours updated successfully',
            'business_hours': user.get_business_hours()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating business hours: {str(e)}")
        return jsonify({'error': 'Failed to update business hours'}), 500