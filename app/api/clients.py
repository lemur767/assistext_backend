# app/api/clients.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.client import Client
from app.models.profile_client import ProfileClient
from app.models.message import Message
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func, or_, and_

clients_bp = Blueprint('clients', __name__)


@clients_bp.route('/api/clients', methods=['GET'])
@jwt_required()
def get_user_clients(user_id):
    """Get all clients for a specific profile"""
    user_id = get_jwt_identity()
    
   try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status')
        flagged_only = request.args.get('flagged', 'false').lower() == 'true'
        
        # Build query - get clients who have messaged this user
        query = db.session.query(Client).join(
            Message, Client.phone_number == Message.sender_number
        ).filter(
            Message.user_id == user_id  # Changed from profile_id to user_id
        ).distinct()
        
        # Apply filters (same as before)
        if search:
            query = query.filter(
                or_(
                    Client.phone_number.contains(search),
                    Client.name.ilike(f'%{search}%'),
                    Client.email.ilike(f'%{search}%')
                )
            )
        
        if status_filter:
            if status_filter == 'blocked':
                query = query.filter(Client.is_blocked == True)
            elif status_filter == 'regular':
                query = query.filter(Client.is_regular == True)
            elif status_filter == 'flagged':
                query = query.filter(Client.is_flagged == True)
        
        if flagged_only:
            query = query.filter(Client.is_flagged == True)
        
        # Order by last contact
        query = query.order_by(Client.last_contact.desc())
        
        # Paginate
        result = query.paginate(page=page, per_page=per_page, error_out=False)
        
        clients = []
        for client in result.items:
            client_data = client.to_dict()
            
                     
            # Get message stats for this client
            message_stats = get_client_message_stats(user_id, client.phone_number)
            client_data['message_stats'] = message_stats
            
            clients.append(client_data)
        
        return jsonify({
            'clients': clients,
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
        current_app.logger.error(f"Error getting profile clients: {str(e)}")
        return jsonify({'error': 'Failed to retrieve clients'}), 500


@clients_bp.route('/profiles/<int:profile_id>/clients/<int:client_id>', methods=['GET'])
@jwt_required()
def get_client_detail(profile_id, client_id):
    """Get detailed information about a specific client"""
    user_id = get_jwt_identity()
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    try:
        client = Client.query.get_or_404(client_id)
        
        # Get profile-specific relationship
        profile_client = ProfileClient.query.filter_by(
            
            client_id=client_id
        ).first()
        
        # Get message history
        messages = Message.query.filter(
            Message.user_id == user_id,
            Message.sender_number == client.phone_number
        ).order_by(Message.timestamp.desc()).limit(20).all()
        
        # Get interaction timeline
        timeline = get_client_timeline(profile_id, client.phone_number)
        
        client_detail = {
            'client': client.to_dict(),
            'profile_relationship': profile_client.to_dict() if profile_client else None,
            'recent_messages': [msg.to_dict() for msg in messages],
            'timeline': timeline,
            'stats': get_client_message_stats(profile_id, client.phone_number)
        }
        
        return jsonify(client_detail), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting client detail: {str(e)}")
        return jsonify({'error': 'Failed to retrieve client details'}), 500


@clients_bp.route('/profiles/<int:profile_id>/clients/<int:client_id>', methods=['PUT'])
@jwt_required()
def update_client(profile_id, client_id):
    """Update client information"""
    user_id = get_jwt_identity()
    data = request.json
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    try:
        client = Client.query.get_or_404(client_id)
        
        # Update client basic info
        if 'name' in data:
            client.name = data['name']
        if 'email' in data:
            client.email = data['email']
        if 'notes' in data:
            client.notes = data['notes']
        if 'is_blocked' in data:
            client.is_blocked = data['is_blocked']
        if 'is_flagged' in data:
            client.is_flagged = data['is_flagged']
        if 'is_regular' in data:
            client.is_regular = data['is_regular']
        if 'risk_level' in data:
            client.risk_level = data['risk_level']
        
        client.updated_at = datetime.utcnow()
        
        # Update or create profile-specific relationship
        profile_client = ProfileClient.query.filter_by(
            profile_id=profile_id,
            client_id=client_id
        ).first()
        
        if not profile_client:
            profile_client = ProfileClient(
                profile_id=profile_id,
                client_id=client_id
            )
            db.session.add(profile_client)
        
        # Update profile-specific fields
        if 'nickname' in data:
            profile_client.nickname = data['nickname']
        if 'profile_notes' in data:
            profile_client.notes = data['profile_notes']
        if 'tags' in data:
            profile_client.tags = ','.join(data['tags']) if data['tags'] else ''
        if 'relationship_status' in data:
            profile_client.relationship_status = data['relationship_status']
        
        profile_client.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Client updated successfully',
            'client': client.to_dict(),
            'profile_relationship': profile_client.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating client: {str(e)}")
        return jsonify({'error': 'Failed to update client'}), 500


@clients_bp.route('/profiles/<int:profile_id>/clients/<int:client_id>/block', methods=['POST'])
@jwt_required()
def block_client(profile_id, client_id):
    """Block a client"""
    user_id = get_jwt_identity()
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    try:
        client = Client.query.get_or_404(client_id)
        client.is_blocked = True
        client.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Client blocked successfully',
            'client': client.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error blocking client: {str(e)}")
        return jsonify({'error': 'Failed to block client'}), 500


@clients_bp.route('/profiles/<int:profile_id>/clients/<int:client_id>/unblock', methods=['POST'])
@jwt_required()
def unblock_client(profile_id, client_id):
    """Unblock a client"""
    user_id = get_jwt_identity()
    
    # Verify ownership
    profile = Profile.query.filter_by(id=profile_id, user_id=user_id).first()
    if not profile:
        return jsonify({'error': 'Profile not found'}), 404
    
    try:
        client = Client.query.get_or_404(client_id)
        client.is_blocked = False
        client.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Client unblocked successfully',
            'client': client.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unblocking client: {str(e)}")
        return jsonify({'error': 'Failed to unblock client'}), 500


def get_client_message_stats(profile_id, phone_number, days=30):
    """Get message statistics for a client"""
    try:
        since_date = datetime.utcnow() - timedelta(days=days)
        
        total_messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == phone_number,
            Message.timestamp >= since_date
        ).count()
        
        incoming_count = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == phone_number,
            Message.is_incoming == True,
            Message.timestamp >= since_date
        ).count()
        
        outgoing_count = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == phone_number,
            Message.is_incoming == False,
            Message.timestamp >= since_date
        ).count()
        
        ai_responses = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == phone_number,
            Message.is_incoming == False,
            Message.ai_generated == True,
            Message.timestamp >= since_date
        ).count()
        
        flagged_count = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == phone_number,
            Message.flagged == True,
            Message.timestamp >= since_date
        ).count()
        
        # Get first and last message dates
        first_message = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == phone_number
        ).order_by(Message.timestamp.asc()).first()
        
        last_message = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == phone_number
        ).order_by(Message.timestamp.desc()).first()
        
        return {
            'total_messages': total_messages,
            'incoming_messages': incoming_count,
            'outgoing_messages': outgoing_count,
            'ai_responses': ai_responses,
            'flagged_messages': flagged_count,
            'first_contact': first_message.timestamp.isoformat() if first_message else None,
            'last_contact': last_message.timestamp.isoformat() if last_message else None,
            'days_period': days
        }
        
    except Exception as e:
        current_app.logger.error(f"Error getting client stats: {str(e)}")
        return {}


def get_client_timeline(profile_id, phone_number, limit=50):
    """Get interaction timeline for a client"""
    try:
        # Get messages and group by day
        messages = Message.query.filter(
            Message.profile_id == profile_id,
            Message.sender_number == phone_number
        ).order_by(Message.timestamp.desc()).limit(limit).all()
        
        timeline = {}
        for msg in messages:
            date_key = msg.timestamp.date().isoformat()
            if date_key not in timeline:
                timeline[date_key] = {
                    'date': date_key,
                    'incoming_count': 0,
                    'outgoing_count': 0,
                    'ai_responses': 0,
                    'flagged_count': 0,
                    'messages': []
                }
            
            timeline[date_key]['messages'].append({
                'id': msg.id,
                'content': msg.content[:100] + '...' if len(msg.content) > 100 else msg.content,
                'is_incoming': msg.is_incoming,
                'ai_generated': msg.ai_generated,
                'flagged': msg.flagged,
                'timestamp': msg.timestamp.isoformat()
            })
            
            if msg.is_incoming:
                timeline[date_key]['incoming_count'] += 1
            else:
                timeline[date_key]['outgoing_count'] += 1
            
            if msg.ai_generated:
                timeline[date_key]['ai_responses'] += 1
            
            if msg.flagged:
                timeline[date_key]['flagged_count'] += 1
        
        # Convert to sorted list
        timeline_list = list(timeline.values())
        timeline_list.sort(key=lambda x: x['date'], reverse=True)
        
        return timeline_list
        
    except Exception as e:
        current_app.logger.error(f"Error getting client timeline: {str(e)}")
        return []


@clients_bp.route('/search', methods=['GET'])
@jwt_required()
def search_clients():
    """Search clients across all user's profiles"""
    user_id = get_jwt_identity()
    
    try:
        # Get search parameters
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        if not query or len(query) < 2:
            return jsonify({'error': 'Search query must be at least 2 characters'}), 400
        
        # Get user's profiles
        user_profiles = Profile.query.filter_by(user_id=user_id).all()
        profile_ids = [p.id for p in user_profiles]
        
        if not profile_ids:
            return jsonify({'clients': [], 'pagination': {}}), 200
        
        # Search clients who have messaged any of user's profiles
        search_query = db.session.query(Client).join(
            Message, Client.phone_number == Message.sender_number
        ).filter(
            Message.profile_id.in_(profile_ids),
            or_(
                Client.phone_number.contains(query),
                Client.name.ilike(f'%{query}%'),
                Client.email.ilike(f'%{query}%')
            )
        ).distinct()
        
        # Paginate
        result = search_query.paginate(page=page, per_page=per_page, error_out=False)
        
        clients = []
        for client in result.items:
            client_data = client.to_dict()
            
            # Add which profiles this client has contacted
            contacted_profiles = db.session.query(Profile.id, Profile.name).join(
                Message, Profile.id == Message.profile_id
            ).filter(
                Message.sender_number == client.phone_number,
                Profile.user_id == user_id
            ).distinct().all()
            
            client_data['contacted_profiles'] = [
                {'id': p.id, 'name': p.name} for p in contacted_profiles
            ]
            
            clients.append(client_data)
        
        return jsonify({
            'clients': clients,
            'search_query': query,
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
        current_app.logger.error(f"Error searching clients: {str(e)}")
        return jsonify({'error': 'Failed to search clients'}), 500