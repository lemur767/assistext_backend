from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.profile import Profile
from app.models.message import Message
from app.models.user import User
from app.utils.signalwire_helpers import get_signalwire_integration_status
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/overview', methods=['GET'])
@jwt_required()
def get_dashboard_overview():
    """Get dashboard overview for authenticated user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Profile statistics
        user_profiles = Profile.query.filter_by(user_id=user_id).all()
        total_profiles = len(user_profiles)
        active_profiles = len([p for p in user_profiles if p.is_active])
        ai_enabled_profiles = len([p for p in user_profiles if p.ai_enabled])
        signalwire_configured = len([p for p in user_profiles if p.is_signalwire_configured()])
        
        # Message statistics (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        profile_ids = [p.id for p in user_profiles]
        
        if profile_ids:
            total_messages = Message.query.filter(
                Message.profile_id.in_(profile_ids),
                Message.timestamp >= seven_days_ago
            ).count()
            
            incoming_messages = Message.query.filter(
                Message.profile_id.in_(profile_ids),
                Message.timestamp >= seven_days_ago,
                Message.is_incoming == True
            ).count()
            
            outgoing_messages = Message.query.filter(
                Message.profile_id.in_(profile_ids),
                Message.timestamp >= seven_days_ago,
                Message.is_incoming == False
            ).count()
            
            ai_generated_messages = Message.query.filter(
                Message.profile_id.in_(profile_ids),
                Message.timestamp >= seven_days_ago,
                Message.ai_generated == True
            ).count()
        else:
            total_messages = incoming_messages = outgoing_messages = ai_generated_messages = 0
        
        # SignalWire status
        signalwire_status = get_signalwire_integration_status()
        
        return jsonify({
            'success': True,
            'user': user.to_dict(),
            'profile_stats': {
                'total': total_profiles,
                'active': active_profiles,
                'ai_enabled': ai_enabled_profiles,
                'signalwire_configured': signalwire_configured
            },
            'message_stats_7_days': {
                'total': total_messages,
                'incoming': incoming_messages,
                'outgoing': outgoing_messages,
                'ai_generated': ai_generated_messages
            },
            'signalwire_status': signalwire_status
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting dashboard overview: {str(e)}")
        return jsonify({'error': 'Failed to get dashboard overview'}), 500

@dashboard_bp.route('/recent-activity', methods=['GET'])
@jwt_required()
def get_recent_activity():
    """Get recent activity for user's profiles"""
    try:
        user_id = get_jwt_identity()
        
        # Get user's profiles
        user_profiles = Profile.query.filter_by(user_id=user_id).all()
        profile_ids = [p.id for p in user_profiles]
        
        if not profile_ids:
            return jsonify({
                'success': True,
                'recent_messages': [],
                'activity_summary': {'total': 0, 'profiles_active': 0}
            }), 200
        
        # Get recent messages (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(hours=24)
        
        recent_messages = Message.query.filter(
            Message.profile_id.in_(profile_ids),
            Message.timestamp >= yesterday
        ).order_by(Message.timestamp.desc()).limit(20).all()
        
        # Get activity summary
        active_profiles = set()
        for message in recent_messages:
            active_profiles.add(message.profile_id)
        
        activity_summary = {
            'total_messages': len(recent_messages),
            'profiles_active': len(active_profiles)
        }
        
        # Format messages with profile information
        messages_data = []
        for message in recent_messages:
            message_dict = message.to_dict()
            # Add profile name
            profile = next((p for p in user_profiles if p.id == message.profile_id), None)
            if profile:
                message_dict['profile_name'] = profile.name
            messages_data.append(message_dict)
        
        return jsonify({
            'success': True,
            'recent_messages': messages_data,
            'activity_summary': activity_summary
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        return jsonify({'error': 'Failed to get recent activity'}), 500

@dashboard_bp.route('/health', methods=['GET'])
def dashboard_health():
    """Health check for dashboard service"""
    return jsonify({
        'status': 'healthy',
        'service': 'dashboard'
    }), 200
