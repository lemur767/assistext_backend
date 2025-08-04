# app/services/analytics_queries.py
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from app.models.user import User
from app.models.messaging import Message, Client
from app.extensions import db

def get_user_analytics_data(user_id: int, period: str = '7d'):
    """
    Get comprehensive analytics data for a user from the database
    Returns data structure that matches frontend expectations
    """
    
    # Calculate date range
    end_date = datetime.utcnow()
    if period == '24h':
        start_date = end_date - timedelta(hours=24)
    elif period == '7d':
        start_date = end_date - timedelta(days=7)
    elif period == '30d':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=7)
    
    # Core Metrics Queries
    core_metrics = get_core_metrics(user_id, start_date, end_date)
    
    # Message Type Breakdown
    message_types = get_message_types(user_id, start_date, end_date)
    
    # Time Series Data (daily breakdown)
    time_series = get_time_series_data(user_id, start_date, end_date)
    
    # Client Activity
    client_activity = get_client_activity(user_id, start_date, end_date)
    
    # Get user's phone number
    phone_number = get_user_phone_number(user_id)
    
    return {
        'success': True,
        'signalwire_number': phone_number,
        'core_metrics': core_metrics,
        'messages': {
            'types': message_types,
            'peak_hours': get_peak_hours(user_id, start_date, end_date),
            'avg_message_length': get_avg_message_length(user_id, start_date, end_date)
        },
        'time_series': time_series,
        'client_activity': client_activity
    }

def get_core_metrics(user_id: int, start_date: datetime, end_date: datetime):
    """Get core usage metrics from database using your actual Message model"""
    
    # Total messages query using your Message model
    total_messages = db.session.query(func.count(Message.id))\
        .filter(and_(
            Message.user_id == user_id,
            Message.created_at >= start_date,
            Message.created_at <= end_date
        )).scalar() or 0
    
    # Sent messages (outgoing) - using your 'direction' field
    sent_messages = db.session.query(func.count(Message.id))\
        .filter(and_(
            Message.user_id == user_id,
            Message.direction == 'outbound',
            Message.created_at >= start_date,
            Message.created_at <= end_date
        )).scalar() or 0
    
    # Received messages (incoming) - using your 'direction' field
    received_messages = db.session.query(func.count(Message.id))\
        .filter(and_(
            Message.user_id == user_id,
            Message.direction == 'inbound',
            Message.created_at >= start_date,
            Message.created_at <= end_date
        )).scalar() or 0
    
    # AI generated messages - using your 'is_ai_generated' field
    ai_messages = db.session.query(func.count(Message.id))\
        .filter(and_(
            Message.user_id == user_id,
            Message.is_ai_generated == True,
            Message.created_at >= start_date,
            Message.created_at <= end_date
        )).scalar() or 0
    
    # Active clients (clients who sent/received messages) - using your 'client_phone' field
    active_clients = db.session.query(func.count(func.distinct(Message.client_phone)))\
        .filter(and_(
            Message.user_id == user_id,
            Message.created_at >= start_date,
            Message.created_at <= end_date,
            Message.client_phone.isnot(None)
        )).scalar() or 0
    
    # Total clients from your Client model
    total_clients = db.session.query(func.count(Client.id))\
        .filter(Client.user_id == user_id).scalar() or 0
    
    # New clients in period - using your Client model
    new_clients = db.session.query(func.count(Client.id))\
        .filter(and_(
            Client.user_id == user_id,
            Client.created_at >= start_date,
            Client.created_at <= end_date
        )).scalar() or 0
    
    # Calculate rates
    ai_adoption_rate = round((ai_messages / total_messages * 100) if total_messages > 0 else 0, 1)
    response_rate = round((sent_messages / received_messages * 100) if received_messages > 0 else 0, 1)
    client_activity_rate = round((active_clients / total_clients * 100) if total_clients > 0 else 0, 1)
    
    # Average response time (in minutes)
    avg_response_time = get_avg_response_time(user_id, start_date, end_date)
    
    return {
        'total_messages': total_messages,
        'sent_messages': sent_messages,
        'received_messages': received_messages,
        'ai_messages': ai_messages,
        'total_clients': total_clients,
        'active_clients': active_clients,
        'new_clients': new_clients,
        'ai_adoption_rate': ai_adoption_rate,
        'response_rate': response_rate,
        'client_activity_rate': client_activity_rate,
        'avg_response_time_minutes': avg_response_time
    }

def get_message_types(user_id: int, start_date: datetime, end_date: datetime):
    """Get message type breakdown using your Message model fields"""
    
    # Incoming messages
    incoming = db.session.query(func.count(Message.id))\
        .filter(and_(
            Message.user_id == user_id,
            Message.direction == 'inbound',
            Message.created_at >= start_date,
            Message.created_at <= end_date
        )).scalar() or 0
    
    # Outgoing messages
    outgoing = db.session.query(func.count(Message.id))\
        .filter(and_(
            Message.user_id == user_id,
            Message.direction == 'outbound',
            Message.created_at >= start_date,
            Message.created_at <= end_date
        )).scalar() or 0
    
    # AI generated messages
    ai_generated = db.session.query(func.count(Message.id))\
        .filter(and_(
            Message.user_id == user_id,
            Message.is_ai_generated == True,
            Message.created_at >= start_date,
            Message.created_at <= end_date
        )).scalar() or 0
    
    # Manual messages (outgoing but not AI generated)
    manual = db.session.query(func.count(Message.id))\
        .filter(and_(
            Message.user_id == user_id,
            Message.direction == 'outbound',
            Message.is_ai_generated == False,
            Message.created_at >= start_date,
            Message.created_at <= end_date
        )).scalar() or 0
    
    return {
        'incoming': incoming,
        'outgoing': outgoing,
        'ai_generated': ai_generated,
        'manual': manual
    }

def get_time_series_data(user_id: int, start_date: datetime, end_date: datetime):
    """Get daily time series data for charts and tables using your Message model"""
    
    # Query messages grouped by date using your Message model
    daily_stats = db.session.query(
        func.date(Message.created_at).label('date'),
        func.count().label('total'),
        func.sum(func.case([(Message.direction == 'outbound', 1)], else_=0)).label('sent'),
        func.sum(func.case([(Message.direction == 'inbound', 1)], else_=0)).label('received'),
        func.sum(func.case([(Message.is_ai_generated == True, 1)], else_=0)).label('ai_generated')
    ).filter(and_(
        Message.user_id == user_id,
        Message.created_at >= start_date,
        Message.created_at <= end_date
    )).group_by(func.date(Message.created_at))\
     .order_by(func.date(Message.created_at)).all()
    
    # Convert to list of dictionaries
    time_series = []
    for stat in daily_stats:
        time_series.append({
            'date': stat.date.isoformat(),
            'total': int(stat.total or 0),
            'sent': int(stat.sent or 0),
            'received': int(stat.received or 0),
            'ai_generated': int(stat.ai_generated or 0)
        })
    
    return time_series

def get_client_activity(user_id: int, start_date: datetime, end_date: datetime):
    """Get client activity data using your Message model with client_phone field"""
    
    client_stats = db.session.query(
        Message.client_phone.label('client_id'),
        func.sum(func.case([(Message.direction == 'outbound', 1)], else_=0)).label('messages_sent'),
        func.sum(func.case([(Message.direction == 'inbound', 1)], else_=0)).label('messages_received'),
        func.sum(func.case([(Message.is_ai_generated == True, 1)], else_=0)).label('ai_messages'),
        func.max(Message.created_at).label('last_active')
    ).filter(and_(
        Message.user_id == user_id,
        Message.created_at >= start_date,
        Message.created_at <= end_date,
        Message.client_phone.isnot(None)
    )).group_by(Message.client_phone)\
     .order_by(func.max(Message.created_at).desc()).all()
    
    activity = []
    for stat in client_stats:
        activity.append({
            'client_id': stat.client_id,
            'messages_sent': int(stat.messages_sent or 0),
            'messages_received': int(stat.messages_received or 0),
            'ai_messages': int(stat.ai_messages or 0),
            'last_active': stat.last_active.isoformat() if stat.last_active else None
        })
    
    return activity

def get_peak_hours(user_id: int, start_date: datetime, end_date: datetime):
    """Get peak activity hours using your Message model"""
    
    hourly_stats = db.session.query(
        func.extract('hour', Message.created_at).label('hour'),
        func.count().label('count')
    ).filter(and_(
        Message.user_id == user_id,
        Message.created_at >= start_date,
        Message.created_at <= end_date
    )).group_by(func.extract('hour', Message.created_at))\
     .order_by(func.count().desc()).all()
    
    return [{'hour': int(stat.hour), 'count': int(stat.count)} for stat in hourly_stats]

def get_avg_message_length(user_id: int, start_date: datetime, end_date: datetime):
    """Get average message length using your Message model body field"""
    
    avg_length = db.session.query(func.avg(func.length(Message.body)))\
        .filter(and_(
            Message.user_id == user_id,
            Message.body.isnot(None),
            Message.created_at >= start_date,
            Message.created_at <= end_date
        )).scalar()
    
    return round(float(avg_length or 0), 1)

def get_avg_response_time(user_id: int, start_date: datetime, end_date: datetime):
    """Calculate average response time by checking consecutive message pairs"""
    
    # Get all messages for the user in chronological order using your Message model
    messages = db.session.query(Message)\
        .filter(and_(
            Message.user_id == user_id,
            Message.created_at >= start_date,
            Message.created_at <= end_date,
            Message.client_phone.isnot(None)
        ))\
        .order_by(Message.client_phone, Message.created_at).all()
    
    if len(messages) < 2:
        return 0
    
    response_times = []
    
    # Group messages by client phone to check consecutive pairs per client
    from itertools import groupby
    
    # Group messages by client phone using your client_phone field
    for client_phone, client_messages in groupby(messages, key=lambda x: x.client_phone):
        client_messages_list = list(client_messages)
        
        # Check consecutive message pairs for this client
        for i in range(len(client_messages_list) - 1):
            current_msg = client_messages_list[i]
            next_msg = client_messages_list[i + 1]
            
            # If current message is incoming and next is outgoing (our response)
            if (current_msg.direction == 'inbound' and 
                next_msg.direction == 'outbound'):
                
                # Calculate response time in minutes
                time_diff = (next_msg.created_at - current_msg.created_at).total_seconds() / 60
                
                # Only include reasonable response times (less than 24 hours)
                if 0 < time_diff <= 1440:  # 1440 minutes = 24 hours
                    response_times.append(time_diff)
    
    # Calculate average response time
    if response_times:
        avg_response_time = sum(response_times) / len(response_times)
        return round(avg_response_time, 1)
    else:
        return 0

def get_user_phone_number(user_id: int):
    """Get user's configured SignalWire phone number from your User model"""
    
    user = db.session.query(User).filter(User.id == user_id).first()
    
    if user and user.signalwire_phone_number:
        return user.signalwire_phone_number
    else:
        return "Not configured"