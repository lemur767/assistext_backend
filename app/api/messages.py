from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.client import Client
from app.models.message import Message, FlaggedMessage
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func, or_, and_

messages_bp = Blueprint('messages', __name__)

# UPDATED: All endpoints now use user_id from JWT instead of profile_id


@messages_bp.route('', methods=['GET'])
@jwt_required()
def get_user_messages():
    """Get all messages for the current user"""
    try:
        user_id = get_jwt_identity()
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        direction = request.args.get('direction')  # 'inbound', 'outbound'
        unread_only = request.args.get('unread', 'false').lower() == 'true'
        flagged_only = request.args.get('flagged', 'false').lower() == 'true'
        search = request.args.get('search', '').strip()
        client_phone = request.args.get('client_phone')
        
        # Build base query
        query = Message.query.filter(Message.user_id == user_id)
        
        # Apply filters
        if direction:
            query = query.filter(Message.direction == direction)
        
        if unread_only:
            query = query.filter(Message.is_read == False)
        
        if flagged_only:
            query = query.filter(Message.is_flagged == True)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Message.message_body.ilike(search_term),
                    Message.sender_number.contains(search),
                    Message.recipient_number.contains(search)
                )
            )
        
        if client_phone:
            query = query.filter(
                or_(
                    Message.sender_number == client_phone,
                    Message.recipient_number == client_phone
                )
            )
        
        # Order by timestamp descending
        query = query.order_by(Message.timestamp.desc())
        
        # Paginate
        result = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'messages': [msg.to_dict() for msg in result.items],
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
        current_app.logger.error(f"Error getting messages: {str(e)}")
        return jsonify({'error': 'Failed to get messages'}), 500


@messages_bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """Get recent conversations for the user"""
    try:
        user_id = get_jwt_identity()
        limit = min(request.args.get('limit', 20, type=int), 50)
        
        # Get recent conversations
        conversations = Message.get_recent_conversations(user_id, limit)
        
        # Format conversations with additional info
        conversations_data = []
        for message in conversations:
            # Get client info
            client = Client.query.filter_by(phone_number=message.sender_number).first()
            
            # Count unread messages from this client
            unread_count = Message.query.filter(
                Message.user_id == user_id,
                Message.sender_number == message.sender_number,
                Message.direction == 'inbound',
                Message.is_read == False
            ).count()
            
            # Get total message count
            total_count = Message.query.filter(
                Message.user_id == user_id,
                or_(
                    Message.sender_number == message.sender_number,
                    Message.recipient_number == message.sender_number
                )
            ).count()
            
            conversation_data = {
                'last_message': message.to_dict(include_client_info=False),
                'client': client.to_dict(user_id=user_id) if client else {
                    'phone_number': message.sender_number,
                    'name': f"Client {message.sender_number[-4:]}",
                    'display_name': f"Client {message.sender_number[-4:]}"
                },
                'unread_count': unread_count,
                'total_messages': total_count
            }
            conversations_data.append(conversation_data)
        
        return jsonify({
            'success': True,
            'conversations': conversations_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting conversations: {str(e)}")
        return jsonify({'error': 'Failed to get conversations'}), 500


@messages_bp.route('/<int:message_id>', methods=['GET'])
@jwt_required()
def get_message():
    """Get a specific message"""
    try:
        user_id = get_jwt_identity()
        message_id = request.view_args['message_id']
        
        message = Message.query.filter(
            Message.id == message_id,
            Message.user_id == user_id
        ).first()
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        return jsonify({
            'success': True,
            'message': message.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting message: {str(e)}")
        return jsonify({'error': 'Failed to get message'}), 500


@messages_bp.route('/<int:message_id>/read', methods=['POST'])
@jwt_required()
def mark_message_read():
    """Mark a message as read"""
    try:
        user_id = get_jwt_identity()
        message_id = request.view_args['message_id']
        
        message = Message.query.filter(
            Message.id == message_id,
            Message.user_id == user_id
        ).first()
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        message.mark_as_read()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Message marked as read'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking message as read: {str(e)}")
        return jsonify({'error': 'Failed to mark message as read'}), 500


@messages_bp.route('/bulk-read', methods=['POST'])
@jwt_required()
def mark_messages_read():
    """Mark multiple messages as read"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'message_ids' not in data:
            return jsonify({'error': 'Message IDs required'}), 400
        
        message_ids = data['message_ids']
        if not isinstance(message_ids, list):
            return jsonify({'error': 'Message IDs must be a list'}), 400
        
        # Update messages
        updated_count = Message.query.filter(
            Message.id.in_(message_ids),
            Message.user_id == user_id
        ).update({Message.is_read: True}, synchronize_session=False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'{updated_count} messages marked as read'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error marking messages as read: {str(e)}")
        return jsonify({'error': 'Failed to mark messages as read'}), 500


@messages_bp.route('/<int:message_id>/flag', methods=['POST'])
@jwt_required()
def flag_message():
    """Flag a message for review"""
    try:
        user_id = get_jwt_identity()
        message_id = request.view_args['message_id']
        
        message = Message.query.filter(
            Message.id == message_id,
            Message.user_id == user_id
        ).first()
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        data = request.get_json() or {}
        reason = data.get('reason', 'manual')
        severity = data.get('severity', 'medium')
        
        # Flag the message
        message.mark_as_flagged(reason)
        
        # Create detailed flag record
        flagged_message = FlaggedMessage(
            message_id=message_id,
            user_id=user_id,
            reason=reason,
            severity=severity,
            detection_method='manual'
        )
        db.session.add(flagged_message)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Message flagged successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error flagging message: {str(e)}")
        return jsonify({'error': 'Failed to flag message'}), 500


@messages_bp.route('/<int:message_id>/unflag', methods=['POST'])
@jwt_required()
def unflag_message():
    """Remove flag from a message"""
    try:
        user_id = get_jwt_identity()
        message_id = request.view_args['message_id']
        
        message = Message.query.filter(
            Message.id == message_id,
            Message.user_id == user_id
        ).first()
        
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        # Unflag the message
        message.is_flagged = False
        
        # Remove flag details
        FlaggedMessage.query.filter_by(message_id=message_id).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Message unflagged successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unflagging message: {str(e)}")
        return jsonify({'error': 'Failed to unflag message'}), 500


@messages_bp.route('/send', methods=['POST'])
@jwt_required()
def send_message():
    """Send a message to a client"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user.is_signalwire_configured():
            return jsonify({'error': 'SignalWire not configured'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['to_number', 'message']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        to_number = data['to_number']
        message_body = data['message']
        
        # Find or create client
        client = Client.find_or_create(to_number, user_id)
        
        # Check daily message limit
        today_count = Message.get_daily_count(user_id)
        if today_count >= user.daily_message_limit:
            return jsonify({'error': 'Daily message limit exceeded'}), 429
        
        # Create message record
        message = Message(
            user_id=user_id,
            client_id=client.id,
            sender_number=user.signalwire_phone_number,
            recipient_number=to_number,
            message_body=message_body,
            direction='outbound',
            status='pending',
            is_ai_generated=False
        )
        db.session.add(message)
        db.session.flush()  # Get the ID
        
        # Send via SignalWire (implement this based on your SignalWire setup)
        try:
            # TODO: Implement actual SignalWire sending
            # from app.services.sms_service import send_sms
            # signalwire_message = send_sms(
            #     from_number=user.signalwire_phone_number,
            #     to_number=to_number,
            #     body=message_body,
            #     user=user
            # )
            # message.message_sid = signalwire_message.sid
            message.status = 'sent'  # Temporary - would be set by actual response
            
            # Update user message count
            user.update_message_count(sent=1)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Message sent successfully',
                'message_data': message.to_dict()
            }), 200
            
        except Exception as send_error:
            message.status = 'failed'
            message.error_message = str(send_error)
            db.session.commit()
            
            current_app.logger.error(f"Failed to send message: {send_error}")
            return jsonify({'error': 'Failed to send message'}), 500
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error sending message: {str(e)}")
        return jsonify({'error': 'Failed to send message'}), 500


@messages_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_message_stats():
    """Get message statistics for the user"""
    try:
        user_id = get_jwt_identity()
        
        # Get date range (default to last 30 days)
        days = request.args.get('days', 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Basic counts
        total_messages = Message.query.filter(Message.user_id == user_id).count()
        
        inbound_count = Message.query.filter(
            Message.user_id == user_id,
            Message.direction == 'inbound'
        ).count()
        
        outbound_count = Message.query.filter(
            Message.user_id == user_id,
            Message.direction == 'outbound'
        ).count()
        
        ai_generated_count = Message.query.filter(
            Message.user_id == user_id,
            Message.is_ai_generated == True
        ).count()
        
        flagged_count = Message.query.filter(
            Message.user_id == user_id,
            Message.is_flagged == True
        ).count()
        
        unread_count = Message.count_unread(user_id)
        
        # Recent period stats
        recent_messages = Message.query.filter(
            Message.user_id == user_id,
            Message.timestamp >= start_date
        ).count()
        
        recent_inbound = Message.query.filter(
            Message.user_id == user_id,
            Message.direction == 'inbound',
            Message.timestamp >= start_date
        ).count()
        
        recent_outbound = Message.query.filter(
            Message.user_id == user_id,
            Message.direction == 'outbound',
            Message.timestamp >= start_date
        ).count()
        
        # Today's stats
        today_count = Message.get_daily_count(user_id)
        
        # Calculate rates
        response_rate = round((ai_generated_count / max(inbound_count, 1)) * 100, 1)
        flag_rate = round((flagged_count / max(total_messages, 1)) * 100, 1)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_messages': total_messages,
                'inbound_count': inbound_count,
                'outbound_count': outbound_count,
                'ai_generated_count': ai_generated_count,
                'flagged_count': flagged_count,
                'unread_count': unread_count,
                'today_count': today_count,
                'response_rate': response_rate,
                'flag_rate': flag_rate,
                'recent_period': {
                    'days': days,
                    'total_messages': recent_messages,
                    'inbound': recent_inbound,
                    'outbound': recent_outbound
                }
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting message stats: {str(e)}")
        return jsonify({'error': 'Failed to get message statistics'}), 500


@messages_bp.route('/conversation/<phone_number>', methods=['GET'])
@jwt_required()
def get_conversation():
    """Get conversation with a specific phone number"""
    try:
        user_id = get_jwt_identity()
        phone_number = request.view_args['phone_number']
        
        limit = min(request.args.get('limit', 50, type=int), 100)
        
        # Get conversation messages
        messages = Message.get_conversation(user_id, phone_number, limit)
        
        # Mark unread messages as read
        unread_messages = [msg for msg in messages if not msg.is_read and msg.direction == 'inbound']
        for msg in unread_messages:
            msg.mark_as_read()
        
        if unread_messages:
            db.session.commit()
        
        # Get client info
        client = Client.query.filter_by(phone_number=phone_number).first()
        
        return jsonify({
            'success': True,
            'messages': [msg.to_dict(include_client_info=False) for msg in reversed(messages)],
            'client': client.to_dict(user_id=user_id) if client else {
                'phone_number': phone_number,
                'name': f"Client {phone_number[-4:]}",
                'display_name': f"Client {phone_number[-4:]}"
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting conversation: {str(e)}")
        return jsonify({'error': 'Failed to get conversation'}), 500