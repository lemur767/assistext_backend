# app/api/messages.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.profile import Profile
from app.models.message import Message
from app.models.client import Client
from app.services.message_handler import send_response, mark_messages_as_read
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func, or_

messages_bp = Blueprint('messages', __name__)


@messages_bp.route('/profiles/<int:profile_id>/conversations', methods=['GET'])
@jwt_required()
def get_conversations(profile_id):
    """Get all conversations for a profile"""
    user_id = get_jwt_identity()
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        
        # Get unique conversations with latest message info
        base_query = db.session.query(
            Message.sender_number,
            func.max(Message.timestamp).label('last_message_time'),
            func.count(Message.id).label('total_messages'),
            func.sum(func.case([(Message.is_read == False, 1)], else_=0)).label('unread_count')
        ).filter(
            Message.profile_id == profile_id
        ).group_by(Message.sender_number)
        
        # Apply search filter
        if search:
            base_query = base_query.filter(
                or_(
                    Message.sender_number.contains(search),
                    Message.content.ilike(f'%{search}%')
                )
            )
        
        # Order by latest message
        conversations_data = base_query.order_by(func.max(Message.timestamp).desc()).all()
        
        # Paginate manually
        total = len(conversations_data)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_conversations = conversations_data[start:end]
        
        conversations = []
        for conv in paginated_conversations:
            # Get the latest message content
            latest_message = Message.query.filter(
                Message.profile_id == profile_id,
                Message.sender_number == conv.sender_number,
                Message.timestamp == conv.last_message_time
            ).first()
            
            # Get client info
            client = Client.query.filter_by(phone_number=conv.sender_number).first()
            
            conversations.append({
                'sender_number': conv.sender_number,
                'client_name': client.name if client else None,
                'client_notes': client.notes if client else None,
                'is_blocked': client.is_blocked if client else False,
                'is_flagged': client.is_flagged if client else False,
                'last_message': {
                    'content': latest_message.content if latest_message else '',
                    'timestamp': conv.last_message_time.isoformat(),
                    'is_incoming': latest_message.is_incoming if latest_message else True
                },
                'total_messages': conv.total_messages,
                'unread_count': conv.unread_count or 0
            })
        
        return jsonify({
            'conversations': conversations,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page,
                'has_next': end < total,
                'has_prev': page > 1
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting conversations: {str(e)}")
        return jsonify({'error': 'Failed to retrieve conversations'}), 500


@messages_bp.route('/profiles/<int:profile_id>/conversations/<sender_number>/messages', methods=['GET'])
@jwt_required()
def get_conversation_messages(profile_id, sender_number):
    """Get all messages in a specific conversation"""
    user_id = get_jwt_identity()
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        # Get messages for this conversation
        messages_query = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == sender_number
        ).order_by(Message.timestamp.desc())
        
        # Paginate
        result = messages_query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format messages
        messages = []
        for msg in result.items:
            messages.append(msg.to_dict())
        
        # Mark messages as read
        mark_messages_as_read(profile_id, sender_number)
        
        # Get client info
        client = Client.query.filter_by(phone_number=sender_number).first()
        
        return jsonify({
            'messages': messages,
            'client': client.to_dict() if client else None,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': result.total,
                'pages': result.pages,
                'has_next': result.has_next,
                'has_prev': result.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting conversation messages: {str(e)}")
        return jsonify({'error': 'Failed to retrieve messages'}), 500


@messages_bp.route('/profiles/<int:profile_id>/send', methods=['POST'])
@jwt_required()
def send_manual_message(profile_id):
    """Send a manual message from profile"""
    user_id = get_jwt_identity()
    data = request.json
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    # Validate required fields
    if not all([data.get('to_number'), data.get('message')]):
        return jsonify({'error': 'Missing required fields: to_number, message'}), 400
    
    try:
        to_number = data['to_number']
        message_content = data['message']
        
        # Validate message length
        if len(message_content) > 1600:  # SMS limit
            return jsonify({'error': 'Message too long (max 1600 characters)'}), 400
        
        # Send message
        result = send_response(profile, message_content, to_number, is_ai_generated=False)
        
        if result:
            return jsonify({
                'message': 'Message sent successfully',
                'message_data': result.to_dict()
            }), 200
        else:
            return jsonify({'error': 'Failed to send message'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error sending manual message: {str(e)}")
        return jsonify({'error': 'Failed to send message'}), 500


@messages_bp.route('/profiles/<int:profile_id>/conversations/<sender_number>/mark-read', methods=['POST'])
@jwt_required()
def mark_conversation_read(profile_id, sender_number):
    """Mark all messages in conversation as read"""
    user_id = get_jwt_identity()
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    try:
        marked_count = mark_messages_as_read(profile_id, sender_number)
        
        return jsonify({
            'message': f'Marked {marked_count} messages as read',
            'count': marked_count
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error marking messages as read: {str(e)}")
        return jsonify({'error': 'Failed to mark messages as read'}), 500


@messages_bp.route('/profiles/<int:profile_id>/search', methods=['GET'])
@jwt_required()
def search_messages(profile_id):
    """Search messages for a profile"""
    user_id = get_jwt_identity()
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    try:
        # Get search parameters
        query = request.args.get('q', '').strip()
        sender = request.args.get('sender', '').strip()
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        ai_only = request.args.get('ai_only', 'false').lower() == 'true'
        flagged_only = request.args.get('flagged_only', 'false').lower() == 'true'
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        if not query and not sender and not date_from:
            return jsonify({'error': 'At least one search parameter required'}), 400
        
        # Build search query
        search_query = Message.query.filter(Message.profile_id == profile_id)
        
        if query:
            search_query = search_query.filter(Message.content.ilike(f'%{query}%'))
        
        if sender:
            search_query = search_query.filter(Message.sender_number.contains(sender))
        
        if date_from:
            date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            search_query = search_query.filter(Message.timestamp >= date_from_obj)
        
        if date_to:
            date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            search_query = search_query.filter(Message.timestamp <= date_to_obj)
        
        if ai_only:
            search_query = search_query.filter(Message.ai_generated == True)
        
        if flagged_only:
            search_query = search_query.filter(Message.flagged == True)
        
        # Order by timestamp
        search_query = search_query.order_by(Message.timestamp.desc())
        
        # Paginate
        result = search_query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format results
        messages = []
        for msg in result.items:
            msg_data = msg.to_dict()
            
            # Add client info
            client = Client.query.filter_by(phone_number=msg.sender_number).first()
            msg_data['client_name'] = client.name if client else None
            
            messages.append(msg_data)
        
        return jsonify({
            'messages': messages,
            'search_params': {
                'query': query,
                'sender': sender,
                'date_from': date_from,
                'date_to': date_to,
                'ai_only': ai_only,
                'flagged_only': flagged_only
            },
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': result.total,
                'pages': result.pages,
                'has_next': result.has_next,
                'has_prev': result.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error searching messages: {str(e)}")
        return jsonify({'error': 'Failed to search messages'}), 500


@messages_bp.route('/profiles/<int:profile_id>/stats', methods=['GET'])
@jwt_required()
def get_message_stats(profile_id):
    """Get message statistics for a profile"""
    user_id = get_jwt_identity()
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    try:
        # Get date range
        days = int(request.args.get('days', 7))
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Basic stats
        total_messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.timestamp >= since_date
        ).count()
        
        incoming_messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.timestamp >= since_date,
            Message.is_incoming == True
        ).count()
        
        ai_responses = Message.query.filter(
            Message.profile_id == profile_id,
            Message.timestamp >= since_date,
            Message.is_incoming == False,
            Message.ai_generated == True
        ).count()
        
        flagged_messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.timestamp >= since_date,
            Message.flagged == True
        ).count()
        
        # Unique contacts
        unique_contacts = Message.query.filter(
            Message.profile_id == profile_id,
            Message.timestamp >= since_date,
            Message.is_incoming == True
        ).distinct(Message.sender_number).count()
        
        # Average response time
        avg_response_time = db.session.query(
            func.avg(Message.ai_processing_time)
        ).filter(
            Message.profile_id == profile_id,
            Message.timestamp >= since_date,
            Message.ai_processing_time.isnot(None)
        ).scalar() or 0
        
        return jsonify({
            'date_range': {
                'days': days,
                'since': since_date.isoformat()
            },
            'stats': {
                'total_messages': total_messages,
                'incoming_messages': incoming_messages,
                'ai_responses': ai_responses,
                'flagged_messages': flagged_messages,
                'unique_contacts': unique_contacts,
                'avg_response_time': round(avg_response_time, 2),
                'ai_response_rate': round((ai_responses / max(incoming_messages, 1)) * 100, 1)
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting message stats: {str(e)}")
        return jsonify({'error': 'Failed to retrieve statistics'}), 500