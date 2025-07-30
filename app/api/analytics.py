from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.messaging import Client, Message

from app.models.usage_analytics import UsageAnalytics, ConversationAnalytics
from app.services.signalwire_service import SignalWireService
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func, extract, case, and_, or_
from app.tasks.analytics_tasks import celery


analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_analytics():
    """
    Comprehensive dashboard analytics
    GET /api/analytics/dashboard?period=7d&include_signalwire=true
    """
    try:
        user_id = get_jwt_identity()
        
        # Get query parameters
        period = request.args.get('period', '7d')  # 1d, 7d, 30d, 90d, 1y
        include_signalwire = request.args.get('include_signalwire', 'false').lower() == 'true'
        timezone_offset = request.args.get('timezone_offset', 0, type=int)
        
        # Calculate date ranges
        now = datetime.utcnow()
        if period == '1d':
            start_date = now - timedelta(days=1)
        elif period == '7d':
            start_date = now - timedelta(days=7)
        elif period == '30d':
            start_date = now - timedelta(days=30)
        elif period == '90d':
            start_date = now - timedelta(days=90)
        elif period == '1y':
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=7)
        
        # Core message analytics
        message_stats = _get_message_analytics(user_id, start_date, now)
        
        # Client analytics
        client_stats = _get_client_analytics(user_id, start_date, now)
        
        # AI performance analytics
        ai_stats = _get_ai_analytics(user_id, start_date, now)
        
        # Conversation analytics
        conversation_stats = _get_conversation_analytics(user_id, start_date, now)
        
        # Usage analytics from database
        usage_stats = _get_usage_analytics(user_id, start_date, now)
        
        # Time-based analytics
        time_stats = _get_time_based_analytics(user_id, start_date, now, period)
        
        # Optional SignalWire usage stats
        signalwire_stats = None
        if include_signalwire:
            signalwire_stats = _get_signalwire_usage_stats(user_id)
        
        response_data = {
            'success': True,
            'period': period,
            'date_range': {
                'start': start_date.isoformat(),
                'end': now.isoformat()
            },
            'summary': {
                'total_messages': message_stats['total_messages'],
                'total_clients': client_stats['total_clients'],
                'ai_response_rate': ai_stats['response_rate'],
                'avg_response_time': conversation_stats['avg_response_time'],
                'engagement_score': conversation_stats['avg_engagement_score']
            },
            'messages': message_stats,
            'clients': client_stats,
            'ai_performance': ai_stats,
            'conversations': conversation_stats,
            'usage': usage_stats,
            'time_analytics': time_stats,
            'signalwire': signalwire_stats
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting dashboard analytics: {str(e)}")
        return jsonify({'error': 'Failed to retrieve analytics'}), 500


@analytics_bp.route('/messages', methods=['GET'])
@jwt_required()
def get_message_analytics():
    """
    Detailed message analytics
    GET /api/analytics/messages?period=30d&breakdown=daily
    """
    try:
        user_id = get_jwt_identity()
        
        # Get parameters
        period = request.args.get('period', '30d')
        breakdown = request.args.get('breakdown', 'daily')  # hourly, daily, weekly, monthly
        
        # Calculate date range
        now = datetime.utcnow()
        if period == '7d':
            start_date = now - timedelta(days=7)
        elif period == '30d':
            start_date = now - timedelta(days=30)
        elif period == '90d':
            start_date = now - timedelta(days=90)
        else:
            start_date = now - timedelta(days=30)
        
        # Message volume analytics
        volume_stats = _get_message_volume_analytics(user_id, start_date, now, breakdown)
        
        # Message type breakdown
        type_breakdown = _get_message_type_breakdown(user_id, start_date, now)
        
        # Response time analytics
        response_times = _get_response_time_analytics(user_id, start_date, now)
        
        # Peak activity analysis
        peak_analysis = _get_peak_activity_analysis(user_id, start_date, now)
        
        # Message success rates
        delivery_stats = _get_message_delivery_stats(user_id, start_date, now)
        
        return jsonify({
            'success': True,
            'period': period,
            'breakdown': breakdown,
            'volume': volume_stats,
            'types': type_breakdown,
            'response_times': response_times,
            'peak_activity': peak_analysis,
            'delivery': delivery_stats
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting message analytics: {str(e)}")
        return jsonify({'error': 'Failed to retrieve message analytics'}), 500


@analytics_bp.route('/clients', methods=['GET'])
@jwt_required()
def get_client_analytics():
    """
    Detailed client analytics
    GET /api/analytics/clients?period=30d&include_segments=true
    """
    try:
        user_id = get_jwt_identity()
        
        # Get parameters
        period = request.args.get('period', '30d')
        include_segments = request.args.get('include_segments', 'false').lower() == 'true'
        
        # Date range
        now = datetime.utcnow()
        if period == '30d':
            start_date = now - timedelta(days=30)
        elif period == '90d':
            start_date = now - timedelta(days=90)
        elif period == '1y':
            start_date = now - timedelta(days=365)
        else:
            start_date = now - timedelta(days=30)
        
        # Client growth analytics
        growth_stats = _get_client_growth_analytics(user_id, start_date, now)
        
        # Client engagement analytics
        engagement_stats = _get_client_engagement_analytics(user_id, start_date, now)
        
        # Client lifecycle analytics
        lifecycle_stats = _get_client_lifecycle_analytics(user_id, start_date, now)
        
        # Geographic distribution (if available)
        geo_stats = _get_client_geographic_stats(user_id)
        
        # Client segmentation (optional)
        segment_stats = None
        if include_segments:
            segment_stats = _get_client_segmentation_analytics(user_id, start_date, now)
        
        return jsonify({
            'success': True,
            'period': period,
            'growth': growth_stats,
            'engagement': engagement_stats,
            'lifecycle': lifecycle_stats,
            'geographic': geo_stats,
            'segments': segment_stats
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting client analytics: {str(e)}")
        return jsonify({'error': 'Failed to retrieve client analytics'}), 500


@analytics_bp.route('/performance', methods=['GET'])
@jwt_required()
def get_performance_analytics():
    """
    AI and system performance analytics
    GET /api/analytics/performance?period=30d
    """
    try:
        user_id = get_jwt_identity()
        
        period = request.args.get('period', '30d')
        
        # Date range
        now = datetime.utcnow()
        if period == '30d':
            start_date = now - timedelta(days=30)
        else:
            start_date = now - timedelta(days=30)
        
        # AI performance metrics
        ai_performance = _get_detailed_ai_performance(user_id, start_date, now)
        
        # Response quality metrics
        quality_metrics = _get_response_quality_metrics(user_id, start_date, now)
        
        # Business metrics
        business_impact = _get_business_impact_metrics(user_id, start_date, now)
        
        return jsonify({
            'success': True,
            'period': period,
            'ai_performance': ai_performance,
            'quality_metrics': quality_metrics,
            'business_impact': business_impact
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting performance analytics: {str(e)}")
        return jsonify({'error': 'Failed to retrieve performance analytics'}), 500


@analytics_bp.route('/export', methods=['POST'])
@jwt_required()
def export_analytics():
    """
    Export analytics data
    POST /api/analytics/export
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        export_type = data.get('type', 'csv')  # csv, json, pdf
        include_sections = data.get('sections', ['all'])
        period = data.get('period', '30d')
        
        # Generate export data
        export_data = _generate_export_data(user_id, period, include_sections)
        
        # Format based on export type
        if export_type == 'json':
            formatted_data = export_data
        elif export_type == 'csv':
            formatted_data = _format_as_csv(export_data)
        else:
            formatted_data = export_data
        
        return jsonify({
            'success': True,
            'export_type': export_type,
            'data': formatted_data,
            'generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error exporting analytics: {str(e)}")
        return jsonify({'error': 'Failed to export analytics'}), 500


# Helper Functions for Analytics Calculations

def _get_message_analytics(user_id, start_date, end_date):
    """Calculate comprehensive message analytics"""
    
    # Basic message counts
    total_messages = Message.query.filter(
        Message.user_id == user_id,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).count()
    
    sent_messages = Message.query.filter(
        Message.user_id == user_id,
        Message.is_incoming == False,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).count()
    
    received_messages = Message.query.filter(
        Message.user_id == user_id,
        Message.is_incoming == True,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).count()
    
    ai_messages = Message.query.filter(
        Message.user_id == user_id,
        Message.ai_generated == True,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).count()
    
    # Calculate rates
    ai_response_rate = (ai_messages / sent_messages * 100) if sent_messages > 0 else 0
    response_rate = (sent_messages / received_messages * 100) if received_messages > 0 else 0
    
    return {
        'total_messages': total_messages,
        'sent_messages': sent_messages,
        'received_messages': received_messages,
        'ai_messages': ai_messages,
        'ai_response_rate': round(ai_response_rate, 2),
        'response_rate': round(response_rate, 2)
    }


def _get_client_analytics(user_id, start_date, end_date):
    """Calculate client analytics"""
    
    # Total clients
    total_clients = Client.query.filter(Client.user_id == user_id).count()
    
    # New clients in period
    new_clients = Client.query.filter(
        Client.user_id == user_id,
        Client.created_at >= start_date,
        Client.created_at <= end_date
    ).count()
    
    # Active clients (had messages in period)
    active_clients = db.session.query(Client).join(Message).filter(
        Client.user_id == user_id,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).distinct().count()
    
    # Client types
    client_types = db.session.query(
        Client.client_type,
        func.count(Client.id)
    ).filter(Client.user_id == user_id).group_by(Client.client_type).all()
    
    type_breakdown = {client_type: count for client_type, count in client_types}
    
    return {
        'total_clients': total_clients,
        'new_clients': new_clients,
        'active_clients': active_clients,
        'type_breakdown': type_breakdown
    }


def _get_ai_analytics(user_id, start_date, end_date):
    """Calculate AI performance analytics"""
    
    # AI message stats
    ai_messages = Message.query.filter(
        Message.user_id == user_id,
        Message.ai_generated == True,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).count()
    
    total_outbound = Message.query.filter(
        Message.user_id == user_id,
        Message.is_incoming == False,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).count()
    
    response_rate = (ai_messages / total_outbound * 100) if total_outbound > 0 else 0
    
    # Get average AI confidence scores if available
    avg_confidence = db.session.query(func.avg(Message.ai_confidence)).filter(
        Message.user_id == user_id,
        Message.ai_generated == True,
        Message.ai_confidence.isnot(None),
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).scalar() or 0
    
    return {
        'ai_messages': ai_messages,
        'total_outbound': total_outbound,
        'response_rate': round(response_rate, 2),
        'avg_confidence': round(float(avg_confidence), 2) if avg_confidence else 0
    }


def _get_conversation_analytics(user_id, start_date, end_date):
    """Get conversation analytics from conversation_analytics table"""
    
    # Query conversation analytics
    conversations = ConversationAnalytics.query.filter(
        ConversationAnalytics.user_id == user_id,
        ConversationAnalytics.updated_at >= start_date
    ).all()
    
    if not conversations:
        return {
            'total_conversations': 0,
            'avg_response_time': 0,
            'avg_engagement_score': 0,
            'avg_sentiment_score': 0
        }
    
    # Calculate averages
    total_conversations = len(conversations)
    avg_response_time = sum(c.avg_response_time or 0 for c in conversations) / total_conversations
    avg_engagement = sum(c.engagement_score or 0 for c in conversations) / total_conversations
    avg_sentiment = sum(c.sentiment_score or 0 for c in conversations) / total_conversations
    
    return {
        'total_conversations': total_conversations,
        'avg_response_time': round(avg_response_time, 0),
        'avg_engagement_score': round(float(avg_engagement), 2),
        'avg_sentiment_score': round(float(avg_sentiment), 2)
    }


def _get_usage_analytics(user_id, start_date, end_date):
    """Get usage analytics from usage_analytics table"""
    
    # Get usage analytics for the period
    usage_records = UsageAnalytics.query.filter(
        UsageAnalytics.user_id == user_id,
        UsageAnalytics.created_at >= start_date
    ).all()
    
    if not usage_records:
        return {
            'messages_sent': 0,
            'messages_received': 0,
            'ai_responses_generated': 0,
            'total_cost': 0
        }
    
    # Sum up usage
    total_sent = sum(r.messages_sent or 0 for r in usage_records)
    total_received = sum(r.messages_received or 0 for r in usage_records)
    total_ai = sum(r.ai_responses_generated or 0 for r in usage_records)
    total_cost = sum(r.total_cost or 0 for r in usage_records)
    
    return {
        'messages_sent': total_sent,
        'messages_received': total_received,
        'ai_responses_generated': total_ai,
        'total_cost': round(float(total_cost), 2)
    }


def _get_time_based_analytics(user_id, start_date, end_date, period):
    """Get time-based analytics with proper breakdown"""
    
    if period == '1d':
        # Hourly breakdown for 1 day
        breakdown_data = _get_hourly_breakdown(user_id, start_date, end_date)
    elif period in ['7d', '30d']:
        # Daily breakdown
        breakdown_data = _get_daily_breakdown(user_id, start_date, end_date)
    else:
        # Weekly breakdown for longer periods
        breakdown_data = _get_weekly_breakdown(user_id, start_date, end_date)
    
    return {
        'breakdown_type': 'hourly' if period == '1d' else 'daily' if period in ['7d', '30d'] else 'weekly',
        'data': breakdown_data
    }


def _get_hourly_breakdown(user_id, start_date, end_date):
    """Get hourly message breakdown"""
    
    hourly_data = db.session.query(
        extract('hour', Message.timestamp).label('hour'),
        func.count(case([(Message.is_incoming == False, 1)])).label('sent'),
        func.count(case([(Message.is_incoming == True, 1)])).label('received')
    ).filter(
        Message.user_id == user_id,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).group_by(extract('hour', Message.timestamp)).all()
    
    # Format for frontend
    return [
        {
            'hour': hour,
            'sent': sent,
            'received': received,
            'total': sent + received
        }
        for hour, sent, received in hourly_data
    ]


def _get_daily_breakdown(user_id, start_date, end_date):
    """Get daily message breakdown"""
    
    daily_data = db.session.query(
        func.date(Message.timestamp).label('date'),
        func.count(case([(Message.is_incoming == False, 1)])).label('sent'),
        func.count(case([(Message.is_incoming == True, 1)])).label('received'),
        func.count(case([(Message.ai_generated == True, 1)])).label('ai_generated')
    ).filter(
        Message.user_id == user_id,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).group_by(func.date(Message.timestamp)).all()
    
    return [
        {
            'date': date.isoformat(),
            'sent': sent,
            'received': received,
            'ai_generated': ai_generated,
            'total': sent + received
        }
        for date, sent, received, ai_generated in daily_data
    ]


def _get_weekly_breakdown(user_id, start_date, end_date):
    """Get weekly message breakdown"""
    
    weekly_data = db.session.query(
        func.date_trunc('week', Message.timestamp).label('week'),
        func.count(case([(Message.is_incoming == False, 1)])).label('sent'),
        func.count(case([(Message.is_incoming == True, 1)])).label('received')
    ).filter(
        Message.user_id == user_id,
        Message.timestamp >= start_date,
        Message.timestamp <= end_date
    ).group_by(func.date_trunc('week', Message.timestamp)).all()
    
    return [
        {
            'week': week.isoformat(),
            'sent': sent,
            'received': received,
            'total': sent + received
        }
        for week, sent, received in weekly_data
    ]


def _get_signalwire_usage_stats(user_id):
    """Get SignalWire usage statistics"""
    try:
        user = User.query.get(user_id)
        if not user or not user.signalwire_configured:
            return None
        
        signalwire_service = SignalWireService(user)
        success, usage_data = signalwire_service.get_usage_statistics()
        
        if success:
            return usage_data
        else:
            current_app.logger.warning(f"Failed to get SignalWire usage for user {user_id}")
            return None
            
    except Exception as e:
        current_app.logger.error(f"Error getting SignalWire usage: {str(e)}")
        return None


# Additional helper functions for detailed analytics...

def _get_message_volume_analytics(user_id, start_date, end_date, breakdown):
    """Detailed message volume analytics"""
    # Implementation for volume trends
    pass

def _get_message_type_breakdown(user_id, start_date, end_date):
    """Message type breakdown (incoming/outgoing/AI)"""
    # Implementation for message types
    pass

def _get_response_time_analytics(user_id, start_date, end_date):
    """Response time analytics"""
    # Implementation for response times
    pass

def _get_peak_activity_analysis(user_id, start_date, end_date):
    """Peak activity analysis"""
    # Implementation for peak hours/days
    pass

def _get_message_delivery_stats(user_id, start_date, end_date):
    """Message delivery success rates"""
    # Implementation for delivery stats
    pass

def _get_client_growth_analytics(user_id, start_date, end_date):
    """Client growth over time"""
    # Implementation for client growth
    pass

def _get_client_engagement_analytics(user_id, start_date, end_date):
    """Client engagement metrics"""
    # Implementation for engagement
    pass

def _get_client_lifecycle_analytics(user_id, start_date, end_date):
    """Client lifecycle analytics"""
    # Implementation for lifecycle
    pass

def _get_client_geographic_stats(user_id):
    """Geographic distribution of clients"""
    # Implementation for geo stats
    pass

def _get_client_segmentation_analytics(user_id, start_date, end_date):
    """Client segmentation analytics"""
    # Implementation for segmentation
    pass

def _get_detailed_ai_performance(user_id, start_date, end_date):
    """Detailed AI performance metrics"""
    # Implementation for detailed AI metrics
    pass

def _get_response_quality_metrics(user_id, start_date, end_date):
    """Response quality metrics"""
    # Implementation for quality metrics
    pass

def _get_business_impact_metrics(user_id, start_date, end_date):
    """Business impact metrics"""
    # Implementation for business metrics
    pass

def _generate_export_data(user_id, period, sections):
    """Generate data for export"""
    # Implementation for export data
    pass

def _format_as_csv(data):
    """Format data as CSV"""
    # Implementation for CSV formatting
    pass