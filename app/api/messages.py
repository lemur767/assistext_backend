from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError

from app.services import get_messaging_service
from app.utils.validators import validate_request_json

messaging_bp = Blueprint('messaging', __name__)

class SendMessageSchema(Schema):
    recipient_number = fields.Str(required=True)
    content = fields.Str(required=True, validate=lambda x: len(x.strip()) > 0)
    ai_generated = fields.Bool(missing=False)

class ClientUpdateSchema(Schema):
    name = fields.Str(allow_none=True)
    email = fields.Email(allow_none=True)
    notes = fields.Str(allow_none=True)
    ai_enabled = fields.Bool(allow_none=True)
    ai_personality = fields.Str(allow_none=True)
    custom_ai_prompt = fields.Str(allow_none=True)
    tags = fields.List(fields.Str(), allow_none=True)

@messaging_bp.route('/conversations', methods=['GET'])
@jwt_required()
def get_conversations():
    """Get user's conversations"""
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        messaging_service = get_messaging_service()
        result = messaging_service.get_conversations(user_id, page, per_page)
        
        if result['success']:
            return jsonify({
                'success': True,
                'conversations': result['conversations'],
                'pagination': result['pagination']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Get conversations error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch conversations'
        }), 500

@messaging_bp.route('/conversations/<int:client_id>/messages', methods=['GET'])
@jwt_required()
def get_conversation_messages(client_id):
    """Get messages for specific conversation"""
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        messaging_service = get_messaging_service()
        result = messaging_service.get_conversation_messages(
            user_id, client_id, page, per_page
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'messages': result['messages'],
                'client': result['client'],
                'pagination': result['pagination']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 404
            
    except Exception as e:
        current_app.logger.error(f"Get conversation messages error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to fetch messages'
        }), 500

@messaging_bp.route('/send', methods=['POST'])
@jwt_required()
@validate_request_json(SendMessageSchema())
def send_message():
    """Send SMS message"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        messaging_service = get_messaging_service()
        result = messaging_service.send_message(
            user_id=user_id,
            recipient_number=data['recipient_number'],
            content=data['content'],
            ai_generated=data.get('ai_generated', False)
        )
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'signalwire_sid': result['signalwire_sid']
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Send message error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to send message'
        }), 500

@messaging_bp.route('/clients/<int:client_id>', methods=['PUT'])
@jwt_required()
@validate_request_json(ClientUpdateSchema())
def update_client(client_id):
    """Update client information"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        from app.models import Client
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        
        if not client:
            return jsonify({
                'success': False,
                'error': 'Client not found'
            }), 404
        
        # Update client fields
        for field in ['name', 'email', 'notes', 'ai_enabled', 'ai_personality', 'custom_ai_prompt', 'tags']:
            if field in data:
                setattr(client, field, data[field])
        
        from app.extensions import db
        client.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'client': client.to_dict(include_stats=True)
        }), 200
        
    except Exception as e:
        from app.extensions import db
        db.session.rollback()
        current_app.logger.error(f"Update client error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to update client'
        }), 500

@messaging_bp.route('/messages/<int:message_id>/flag', methods=['POST'])
@jwt_required()
def flag_message(message_id):
    """Flag a message for review"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        reasons = data.get('reasons', [])
        
        from app.models import Message
        message = Message.query.filter_by(id=message_id, user_id=user_id).first()
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Message not found'
            }), 404
        
        message.is_flagged = True
        message.flag_reasons = reasons
        
        from app.extensions import db
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Message flagged successfully'
        }), 200
        
    except Exception as e:
        from app.extensions import db
        db.session.rollback()
        current_app.logger.error(f"Flag message error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to flag message'
        }), 500