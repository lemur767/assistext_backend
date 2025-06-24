# app/api/messages.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.message import Message
from app.models.profile import Profile
from app.models.client import Client
from app.extensions import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

messages_bp = Blueprint('messages', __name__)


@messages_bp.route('', methods=['GET'])
@jwt_required()
def get_messages():
    """Get messages for user's profiles"""
    try:
        user_id = get_jwt_identity()
        
        # Get query parameters
        profile_id = request.args.get('profile_id', type=int)
        sender_number = request.args.get('sender_number')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Build query
        query = db.session.query(Message).join(Profile).filter(
            Profile.user_id == user_id
        )
        
        if profile_id:
            query = query.filter(Message.profile_id == profile_id)
        
        if sender_number:
            query = query.filter(Message.sender_number == sender_number)
        
        # Order by timestamp descending
        query = query.order_by(Message.timestamp.desc())
        
        # Apply pagination
        messages = query.offset(offset).limit(limit).all()
        
        return jsonify([message.to_dict() for message in messages]), 200
        
    except Exception as e:
        logger.error(f"Error getting messages: {e}")
        return jsonify({"error": "Internal server error"}), 500


@messages_bp.route('/<int:message_id>/read', methods=['POST'])
@jwt_required()
def mark_message_read(message_id):
    """Mark a message as read"""
    try:
        user_id = get_jwt_identity()
        
        # Find message and verify ownership
        message = db.session.query(Message).join(Profile).filter(
            Message.id == message_id,
            Profile.user_id == user_id
        ).first()
        
        if not message:
            return jsonify({"error": "Message not found"}), 404
        
        message.is_read = True
        db.session.commit()
        
        return jsonify({"message": "Message marked as read"}), 200
        
    except Exception as e:
        logger.error(f"Error marking message as read: {e}")
        return jsonify({"error": "Internal server error"}), 500


@messages_bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """Get conversations grouped by sender for user's profiles"""
    try:
        user_id = get_jwt_identity()
        profile_id = request.args.get('profile_id', type=int)
        
        # Build base query
        query = db.session.query(Message).join(Profile).filter(
            Profile.user_id == user_id
        )
        
        if profile_id:
            query = query.filter(Message.profile_id == profile_id)
        
        # Get latest message per sender
        from sqlalchemy import func
        subquery = query.with_entities(
            Message.sender_number,
            Message.profile_id,
            func.max(Message.timestamp).label('latest_timestamp')
        ).group_by(Message.sender_number, Message.profile_id).subquery()
        
        # Get the actual latest messages
        latest_messages = db.session.query(Message).join(
            subquery,
            (Message.sender_number == subquery.c.sender_number) &
            (Message.profile_id == subquery.c.profile_id) &
            (Message.timestamp == subquery.c.latest_timestamp)
        ).order_by(Message.timestamp.desc()).all()
        
        conversations = []
        for message in latest_messages:
            # Get unread count for this conversation
            unread_count = db.session.query(Message).filter(
                Message.profile_id == message.profile_id,
                Message.sender_number == message.sender_number,
                Message.is_incoming == True,
                Message.is_read == False
            ).count()
            
            # Get client info if available
            client = Client.query.filter_by(phone_number=message.sender_number).first()
            
            conversations.append({
                'profile_id': message.profile_id,
                'sender_number': message.sender_number,
                'client_name': client.name if client else None,
                'latest_message': message.to_dict(),
                'unread_count': unread_count
            })
        
        return jsonify(conversations), 200
        
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({"error": "Internal server error"}), 500


@messages_bp.route('/send', methods=['POST'])
@jwt_required()
def send_message():
    """Send a message (queue for sending)"""
    try:
        user_id = get_jwt_identity()
        data = request.json
        
        # Validate required fields
        profile_id = data.get('profile_id')
        recipient_number = data.get('recipient_number')
        content = data.get('content')
        
        if not all([profile_id, recipient_number, content]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Verify profile ownership
        profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
        if not profile:
            return jsonify({"error": "Profile not found"}), 404
        
        # Queue message for sending (using Celery if available)
        try:
            from app.tasks.message_tasks import send_sms_message
            task = send_sms_message.delay(
                profile_id=profile_id,
                recipient_number=recipient_number,
                message_text=content,
                is_ai_generated=False
            )
            
            return jsonify({
                "message": "Message queued for sending",
                "task_id": task.id
            }), 202
            
        except ImportError:
            # Fallback: create message record without Celery
            message = Message(
                content=content,
                is_incoming=False,
                sender_number=recipient_number,
                profile_id=profile_id,
                ai_generated=False,
                timestamp=datetime.utcnow(),
                send_status='queued'
            )
            db.session.add(message)
            db.session.commit()
            
            return jsonify({
                "message": "Message created (manual send required)",
                "message_id": message.id
            }), 201
        
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return jsonify({"error": "Internal server error"}), 500


@messages_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "messages"}), 200
