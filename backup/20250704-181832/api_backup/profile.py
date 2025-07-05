from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.client import Client
from app.extensions import db
from typing import Dict, Any
import json

profile_bp = Blueprint('profile', __name__, url_prefix='/api/profile')


@profile_bp.route('/', methods=['GET'])
@jwt_required()
def get_profile():
    """Get the current user's profile (their account settings)"""
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


@profile_bp.route('/', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update the current user's profile settings"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        
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
        
        # Update business settings
        if 'business_hours' in data:
            user.set_business_hours(data['business_hours'])
        if 'auto_reply_enabled' in data:
            user.auto_reply_enabled = data['auto_reply_enabled']
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
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'profile': user.to_dict()
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
        return jsonify({'error': 'Failed to get SignalWire configuration'}), 500


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
        
        # Update SignalWire settings
        if 'phone_number' in data:
            # Check if phone number is already taken by another user
            existing = User.query.filter(
                User.signalwire_phone_number == data['phone_number'],
                User.id != user_id
            ).first()
            
            if existing:
                return jsonify({'error': 'Phone number already in use'}), 400
            
            user.signalwire_phone_number = data['phone_number']
        
        if 'project_id' in data:
            user.signalwire_project_id = data['project_id']
        if 'auth_token' in data:
            user.signalwire_auth_token = data['auth_token']
        if 'space_url' in data:
            user.signalwire_space_url = data['space_url']
        if 'webhook_configured' in data:
            user.signalwire_webhook_configured = data['webhook_configured']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'SignalWire configuration updated successfully',
            'is_configured': user.is_signalwire_configured()
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
            'ai_settings': user.get_ai_settings()
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
        
        # Update AI settings
        if 'enabled' in data:
            user.ai_enabled = data['enabled']
        if 'personality' in data:
            user.ai_personality = data['personality']
        if 'instructions' in data:
            user.ai_instructions = data['instructions']
        if 'model' in data:
            user.ai_model = data['model']
        if 'temperature' in data:
            user.ai_temperature = float(data['temperature'])
        if 'max_tokens' in data:
            user.ai_max_tokens = int(data['max_tokens'])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'AI settings updated successfully',
            'ai_settings': user.get_ai_settings()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating AI settings: {str(e)}")
        return jsonify({'error': 'Failed to update AI settings'}), 500


@profile_bp.route('/clients', methods=['GET'])
@jwt_required()
def get_clients():
    """Get all clients for the current user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        
        # Build query
        query = user.clients
        
        if search:
            query = query.filter(
                db.or_(
                    Client.name.ilike(f'%{search}%'),
                    Client.nickname.ilike(f'%{search}%'),
                    Client.phone_number.ilike(f'%{search}%'),
                    Client.notes.ilike(f'%{search}%')
                )
            )
        
        if status:
            query = query.filter(Client.relationship_status == status)
        
        # Order by last interaction
        query = query.order_by(Client.last_interaction.desc())
        
        # Paginate
        clients = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'clients': [client.to_dict() for client in clients.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': clients.total,
                'pages': clients.pages,
                'has_next': clients.has_next,
                'has_prev': clients.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting clients: {str(e)}")
        return jsonify({'error': 'Failed to get clients'}), 500


@profile_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_profile_stats():
    """Get profile statistics and usage data"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Reset monthly count if needed
        user.reset_monthly_count_if_needed()
        
        # Get client statistics
        total_clients = user.clients.count()
        active_clients = user.clients.filter(
            Client.last_interaction >= db.func.date_trunc('month', db.func.now())
        ).count()
        blocked_clients = user.clients.filter(Client.is_blocked == True).count()
        favorite_clients = user.clients.filter(Client.is_favorite == True).count()
        
        # Get message statistics for this month
        from datetime import datetime, timedelta
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        monthly_sent = user.messages.filter(
            user.messages.c.direction == 'outgoing',
            user.messages.c.created_at >= current_month
        ).count()
        
        monthly_received = user.messages.filter(
            user.messages.c.direction == 'incoming',
            user.messages.c.created_at >= current_month
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'clients': {
                    'total': total_clients,
                    'active_this_month': active_clients,
                    'blocked': blocked_clients,
                    'favorites': favorite_clients
                },
                'messages': {
                    'total_sent': user.total_messages_sent,
                    'total_received': user.total_messages_received,
                    'monthly_sent': monthly_sent,
                    'monthly_received': monthly_received,
                    'monthly_limit': user.daily_message_limit * 30,  # Rough monthly limit
                    'usage_percentage': (user.monthly_message_count / (user.daily_message_limit * 30)) * 100 if user.daily_message_limit > 0 else 0
                },
                'configuration': {
                    'signalwire_configured': user.is_signalwire_configured(),
                    'ai_enabled': user.ai_enabled,
                    'auto_reply_enabled': user.auto_reply_enabled,
                    'out_of_office_enabled': user.out_of_office_enabled
                }
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting profile stats: {str(e)}")
        return jsonify({'error': 'Failed to get profile statistics'}), 500