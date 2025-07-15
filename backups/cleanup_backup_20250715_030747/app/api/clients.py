from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.client import Client
from app.models.message import Message
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func, or_, and_

clients_bp = Blueprint('clients', __name__)

# UPDATED: Remove profile_id from all endpoints, use user_id from JWT


@clients_bp.route('', methods=['GET'])
@jwt_required()
def get_user_clients():
    """Get all clients for the current user (no profile_id needed)"""
    try:
        user_id = get_jwt_identity()
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status')
        flagged_only = request.args.get('flagged', 'false').lower() == 'true'
        client_type = request.args.get('type')  # 'new', 'regular', 'vip', 'blocked'
        
        # Build query - get clients who have messaged this user
        query = Client.get_user_clients(user_id, active_only=False, search=search)
        
        # Convert to SQLAlchemy query for pagination
        if search:
            search_term = f"%{search}%"
            query = Client.query.join(
                db.text('user_clients'), Client.id == db.text('user_clients.client_id')
            ).filter(
                db.text('user_clients.user_id') == user_id,
                or_(
                    Client.phone_number.contains(search),
                    Client.name.ilike(search_term),
                    Client.email.ilike(search_term)
                )
            )
        else:
            query = Client.query.join(
                db.text('user_clients'), Client.id == db.text('user_clients.client_id')
            ).filter(db.text('user_clients.user_id') == user_id)
        
        # Apply filters
        if status_filter == 'active':
            query = query.filter(Client.is_active == True)
        elif status_filter == 'blocked':
            query = query.filter(Client.is_blocked == True)
        elif status_filter == 'inactive':
            query = query.filter(Client.is_active == False)
        
        if client_type:
            query = query.filter(Client.client_type == client_type)
        
        if flagged_only:
            # Get clients with flagged messages
            flagged_client_ids = db.session.query(Message.client_id).filter(
                Message.user_id == user_id,
                Message.is_flagged == True
            ).distinct().subquery()
            query = query.filter(Client.id.in_(flagged_client_ids))
        
        # Order by last contact
        query = query.order_by(Client.last_contact.desc())
        
        # Paginate
        result = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Convert to dict with user-specific data
        clients_data = []
        for client in result.items:
            client_dict = client.to_dict(user_id=user_id, include_stats=True)
            
            # Add message count for this user
            message_count = Message.query.filter(
                Message.client_id == client.id,
                Message.user_id == user_id
            ).count()
            client_dict['message_count'] = message_count
            
            # Add last message info
            last_message = Message.query.filter(
                Message.client_id == client.id,
                Message.user_id == user_id
            ).order_by(Message.timestamp.desc()).first()
            
            if last_message:
                client_dict['last_message'] = {
                    'content': last_message.message_body[:100] + '...' if len(last_message.message_body) > 100 else last_message.message_body,
                    'timestamp': last_message.timestamp.isoformat(),
                    'direction': last_message.direction,
                    'is_ai_generated': last_message.is_ai_generated
                }
            
            clients_data.append(client_dict)
        
        return jsonify({
            'success': True,
            'clients': clients_data,
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
        current_app.logger.error(f"Error getting clients: {str(e)}")
        return jsonify({'error': 'Failed to get clients'}), 500


@clients_bp.route('/<int:client_id>', methods=['GET'])
@jwt_required()
def get_client_details():
    """Get detailed information about a specific client"""
    try:
        user_id = get_jwt_identity()
        client_id = request.view_args['client_id']
        
        # Verify client belongs to user
        client = Client.query.join(
            db.text('user_clients'), Client.id == db.text('user_clients.client_id')
        ).filter(
            Client.id == client_id,
            db.text('user_clients.user_id') == user_id
        ).first()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Get client data with full details
        client_data = client.to_dict(user_id=user_id, include_stats=True)
        
        # Get message history
        messages = Message.query.filter(
            Message.client_id == client_id,
            Message.user_id == user_id
        ).order_by(Message.timestamp.desc()).limit(50).all()
        
        client_data['recent_messages'] = [msg.to_dict(include_client_info=False) for msg in messages]
        
        # Get conversation stats
        total_messages = Message.query.filter(
            Message.client_id == client_id,
            Message.user_id == user_id
        ).count()
        
        ai_generated_count = Message.query.filter(
            Message.client_id == client_id,
            Message.user_id == user_id,
            Message.is_ai_generated == True
        ).count()
        
        flagged_count = Message.query.filter(
            Message.client_id == client_id,
            Message.user_id == user_id,
            Message.is_flagged == True
        ).count()
        
        client_data['conversation_stats'] = {
            'total_messages': total_messages,
            'ai_generated_count': ai_generated_count,
            'flagged_count': flagged_count,
            'response_rate': round((ai_generated_count / max(total_messages, 1)) * 100, 1)
        }
        
        return jsonify({
            'success': True,
            'client': client_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting client details: {str(e)}")
        return jsonify({'error': 'Failed to get client details'}), 500


@clients_bp.route('/<int:client_id>', methods=['PUT'])
@jwt_required()
def update_client():
    """Update client information"""
    try:
        user_id = get_jwt_identity()
        client_id = request.view_args['client_id']
        
        # Verify client belongs to user
        client = Client.query.join(
            db.text('user_clients'), Client.id == db.text('user_clients.client_id')
        ).filter(
            Client.id == client_id,
            db.text('user_clients.user_id') == user_id
        ).first()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update client basic info
        if 'name' in data:
            client.name = data['name']
        if 'email' in data:
            client.email = data['email']
        if 'client_type' in data:
            valid_types = ['new', 'regular', 'vip', 'blocked']
            if data['client_type'] in valid_types:
                client.client_type = data['client_type']
        if 'source' in data:
            client.source = data['source']
        
        # Update user-specific relationship data
        relationship_updates = {}
        if 'notes' in data:
            relationship_updates['notes'] = data['notes']
        if 'is_blocked' in data:
            relationship_updates['is_blocked'] = data['is_blocked']
            # Also update client's blocked status
            if data['is_blocked']:
                client.block_client("Blocked by user")
            else:
                client.unblock_client()
        if 'is_favorite' in data:
            relationship_updates['is_favorite'] = data['is_favorite']
        
        if relationship_updates:
            client.update_user_relationship(user_id, **relationship_updates)
        
        client.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Client updated successfully',
            'client': client.to_dict(user_id=user_id, include_stats=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating client: {str(e)}")
        return jsonify({'error': 'Failed to update client'}), 500


@clients_bp.route('/<int:client_id>/block', methods=['POST'])
@jwt_required()
def block_client():
    """Block a client"""
    try:
        user_id = get_jwt_identity()
        client_id = request.view_args['client_id']
        
        client = Client.query.join(
            db.text('user_clients'), Client.id == db.text('user_clients.client_id')
        ).filter(
            Client.id == client_id,
            db.text('user_clients.user_id') == user_id
        ).first()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        data = request.get_json() or {}
        reason = data.get('reason', 'Blocked by user')
        
        # Block client globally and update user relationship
        client.block_client(reason)
        client.update_user_relationship(user_id, is_blocked=True, notes=f"Blocked: {reason}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Client blocked successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error blocking client: {str(e)}")
        return jsonify({'error': 'Failed to block client'}), 500


@clients_bp.route('/<int:client_id>/unblock', methods=['POST'])
@jwt_required()
def unblock_client():
    """Unblock a client"""
    try:
        user_id = get_jwt_identity()
        client_id = request.view_args['client_id']
        
        client = Client.query.join(
            db.text('user_clients'), Client.id == db.text('user_clients.client_id')
        ).filter(
            Client.id == client_id,
            db.text('user_clients.user_id') == user_id
        ).first()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Unblock client and update user relationship
        client.unblock_client()
        client.update_user_relationship(user_id, is_blocked=False)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Client unblocked successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unblocking client: {str(e)}")
        return jsonify({'error': 'Failed to unblock client'}), 500


@clients_bp.route('/<int:client_id>/messages', methods=['GET'])
@jwt_required()
def get_client_messages():
    """Get message history with a specific client"""
    try:
        user_id = get_jwt_identity()
        client_id = request.view_args['client_id']
        
        # Verify client belongs to user
        client = Client.query.join(
            db.text('user_clients'), Client.id == db.text('user_clients.client_id')
        ).filter(
            Client.id == client_id,
            db.text('user_clients.user_id') == user_id
        ).first()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        # Get messages
        messages_query = Message.query.filter(
            Message.client_id == client_id,
            Message.user_id == user_id
        ).order_by(Message.timestamp.desc())
        
        result = messages_query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Mark messages as read
        unread_messages = Message.query.filter(
            Message.client_id == client_id,
            Message.user_id == user_id,
            Message.direction == 'inbound',
            Message.is_read == False
        ).all()
        
        for msg in unread_messages:
            msg.mark_as_read()
        
        if unread_messages:
            db.session.commit()
        
        return jsonify({
            'success': True,
            'messages': [msg.to_dict(include_client_info=False) for msg in result.items],
            'client': client.to_dict(user_id=user_id),
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
        current_app.logger.error(f"Error getting client messages: {str(e)}")
        return jsonify({'error': 'Failed to get client messages'}), 500


@clients_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_client_stats():
    """Get client statistics for the user"""
    try:
        user_id = get_jwt_identity()
        
        # Get all clients for user
        all_clients = Client.get_user_clients(user_id, active_only=False)
        active_clients = Client.get_user_clients(user_id, active_only=True)
        
        # Count by type
        new_clients = [c for c in all_clients if c.client_type == 'new']
        regular_clients = [c for c in all_clients if c.client_type == 'regular']
        vip_clients = [c for c in all_clients if c.client_type == 'vip']
        blocked_clients = [c for c in all_clients if c.is_blocked]
        
        # Recent activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_clients = [c for c in all_clients if c.last_contact > week_ago]
        
        # Message stats
        total_messages = Message.query.filter(Message.user_id == user_id).count()
        today_messages = Message.get_daily_count(user_id)
        unread_messages = Message.count_unread(user_id)
        
        return jsonify({
            'success': True,
            'stats': {
                'total_clients': len(all_clients),
                'active_clients': len(active_clients),
                'new_clients': len(new_clients),
                'regular_clients': len(regular_clients),
                'vip_clients': len(vip_clients),
                'blocked_clients': len(blocked_clients),
                'recent_activity': len(recent_clients),
                'total_messages': total_messages,
                'today_messages': today_messages,
                'unread_messages': unread_messages
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting client stats: {str(e)}")
        return jsonify({'error': 'Failed to get client statistics'}), 500