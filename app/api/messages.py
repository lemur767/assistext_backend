# app/api/messages.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.message import Message
from app.models.profile import Profile
from app.models.client import Client
from app.services.message_handler import send_response
from app.extensions import db
from datetime import datetime, timedelta

messages_bp = Blueprint('messages', __name__)

@messages_bp.route('/profile/<int:profile_id>', methods=['GET'])
@jwt_required()
def get_profile_messages(profile_id):
    user_id = get_jwt_identity()
    
    # Verify profile ownership
    profile = Profile.query.get_or_404(profile_id)
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Optional query parameters
    client_number = request.args.get('client')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    # Query messages
    query = Message.query.filter(Message.profile_id == profile_id)
    
    if client_number:
        query = query.filter(Message.sender_number == client_number)
    
    # Get total count (for pagination)
    total = query.count()
    
    # Get messages with pagination
    messages = query.order_by(Message.timestamp.desc()) \
                   .limit(limit).offset(offset).all()
    
    return jsonify({
        "total": total,
        "messages": [msg.to_dict() for msg in messages]
    }), 200


@messages_bp.route('/conversation/<int:profile_id>/<path:client_number>', methods=['GET'])
@jwt_required()
def get_conversation(profile_id, client_number):
    user_id = get_jwt_identity()
    
    # Verify profile ownership
    profile = Profile.query.get_or_404(profile_id)
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Optional query parameters
    limit = int(request.args.get('limit', 50))
    before = request.args.get('before')  # Timestamp to get messages before
    
    # Query conversation
    query = Message.query.filter(
        Message.profile_id == profile_id,
        Message.sender_number == client_number
    )
    
    if before:
        before_time = datetime.fromisoformat(before)
        query = query.filter(Message.timestamp < before_time)
    
    # Get messages
    messages = query.order_by(Message.timestamp.desc()) \
                   .limit(limit).all()
    
    
    
    # Reverse to get chronological order
    messages.reverse()
    
    return jsonify({
        "profile_id": profile_id,
        "client_number": client_number,
        "messages": [msg.to_dict() for msg in messages]
    }), 200


@messages_bp.route('/send', methods=['POST'])
@jwt_required()
def send_message():
    user_id = get_jwt_identity()
    data = request.json
    
    # Validate required fields
    if not all([data.get('profile_id'), data.get('client_number'), data.get('message')]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Verify profile ownership
    profile = Profile.query.get_or_404(data['profile_id'])
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Send message
    message = send_response(
        profile=profile,
        response_text=data['message'],
        recipient_number=data['client_number'],
        is_ai_generated=False
    )
    
    if not message:
        return jsonify({"error": "Failed to send message"}), 500
    
    return jsonify(message.to_dict()), 201


@messages_bp.route('/conversations/<int:profile_id>', methods=['GET'])
@jwt_required()
def get_conversations(profile_id):
    user_id = get_jwt_identity()
    
    # Verify profile ownership
    profile = Profile.query.get_or_404(profile_id)
    if profile.user_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get distinct client numbers for this profile
    client_numbers = db.session.query(Message.sender_number) \
                        .filter(Message.profile_id == profile_id) \
                        .distinct().all()
    client_numbers = [num[0] for num in client_numbers]
    
    conversations = []
    for number in client_numbers:
        # Get the latest message for each client
        latest_msg = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == number
        ).order_by(Message.timestamp.desc()).first()
        
        # Get unread count
        unread_count = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == number,
            Message.is_incoming == True,
            Message.is_read == False
        ).count()
        
        # Get client info
        client = Client.query.filter_by(phone_number=number).first()
        client_name = client.name if client else None
        
        conversations.append({
            "client_number": number,
            "client_name": client_name,
            "latest_message": latest_msg.to_dict() if latest_msg else None,
            "unread_count": unread_count
        })
    
    # Sort by latest message timestamp (newest first)
    conversations.sort(
        key=lambda x: x["latest_message"]["timestamp"] if x["latest_message"] else "1970-01-01T00:00:00",
        reverse=True
    )
    
    return jsonify(conversations), 200