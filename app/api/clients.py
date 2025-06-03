from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.client import Client
from app.models.profile import Profile
from app.models.message import Message
from app.models.user import User
from app.utils.security import sanitize_input, validate_phone_number
from sqlalchemy import desc
from datetime import datetime
import json

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('', methods=['GET'])
@jwt_required()
def get_clients():
    """Get all clients for a user's profiles"""
    user_id = get_jwt_identity()
    
    # Pagination parameters
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 20)), 100)  # Limit max to 100
    
    # Filter parameters
    profile_id = request.args.get('profile_id')
    name_filter = request.args.get('name')
    blocked_filter = request.args.get('blocked')
    is_regular_filter = request.args.get('is_regular')
    
    # Base query - get clients for all profiles owned by user
    query = Client.query.join(
        Message, Client.phone_number == Message.sender_number
    ).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Profile.user_id == user_id
    ).distinct()
    
    # Apply filters
    if profile_id:
        query = query.filter(Message.profile_id == profile_id)
    
    if name_filter:
        query = query.filter(Client.name.ilike(f'%{name_filter}%'))
    
    if blocked_filter is not None:
        is_blocked = blocked_filter.lower() == 'true'
        query = query.filter(Client.is_blocked == is_blocked)
    
    if is_regular_filter is not None:
        is_regular = is_regular_filter.lower() == 'true'
        query = query.filter(Client.is_regular == is_regular)
    
    # Execute query with pagination
    paginated_clients = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Prepare response
    clients_data = []
    for client in paginated_clients.items:
        # Get associated profiles for this client
        associated_profiles = db.session.query(Profile.id, Profile.name).join(
            Message, Profile.id == Message.profile_id
        ).filter(
            Message.sender_number == client.phone_number,
            Profile.user_id == user_id
        ).distinct().all()
        
        # Get the last message with this client
        last_message = Message.query.join(
            Profile, Message.profile_id == Profile.id
        ).filter(
            Message.sender_number == client.phone_number,
            Profile.user_id == user_id
        ).order_by(desc(Message.timestamp)).first()
        
        # Format client data
        client_data = {
            'id': client.id,
            'phone_number': client.phone_number,
            'name': client.name,
            'email': client.email,
            'is_blocked': client.is_blocked,
            'is_regular': client.is_regular,
            'notes': client.notes,
            'created_at': client.created_at.isoformat(),
            'profiles': [{'id': p.id, 'name': p.name} for p in associated_profiles],
            'last_message': {
                'content': last_message.content,
                'timestamp': last_message.timestamp.isoformat(),
                'is_incoming': last_message.is_incoming
            } if last_message else None
        }
        
        clients_data.append(client_data)
    
    return jsonify({
        'clients': clients_data,
        'pagination': {
            'total': paginated_clients.total,
            'pages': paginated_clients.pages,
            'page': page,
            'per_page': per_page,
            'has_next': paginated_clients.has_next,
            'has_prev': paginated_clients.has_prev
        }
    }), 200


@clients_bp.route('/<int:client_id>', methods=['GET'])
@jwt_required()
def get_client(client_id):
    """Get details for a specific client"""
    user_id = get_jwt_identity()
    
    # Get client
    client = Client.query.get_or_404(client_id)
    
    # Check permission (user must have at least one profile that communicated with this client)
    has_access = db.session.query(Message).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).first() is not None
    
    if not has_access:
        return jsonify({"error": "Unauthorized access to client"}), 403
    
    # Get associated profiles
    associated_profiles = db.session.query(Profile.id, Profile.name).join(
        Message, Profile.id == Message.profile_id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).distinct().all()
    
    # Get message stats
    message_stats = db.session.query(
        db.func.count(Message.id).label('total'),
        db.func.sum(db.case((Message.is_incoming == True, 1), else_=0)).label('incoming'),
        db.func.sum(db.case((Message.is_incoming == False, 1), else_=0)).label('outgoing')
    ).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).first()
    
    # Format client data
    client_data = {
        'id': client.id,
        'phone_number': client.phone_number,
        'name': client.name,
        'email': client.email,
        'is_blocked': client.is_blocked,
        'is_regular': client.is_regular,
        'notes': client.notes,
        'created_at': client.created_at.isoformat(),
        'updated_at': client.updated_at.isoformat(),
        'profiles': [{'id': p.id, 'name': p.name} for p in associated_profiles],
        'message_stats': {
            'total': message_stats.total or 0,
            'incoming': message_stats.incoming or 0,
            'outgoing': message_stats.outgoing or 0
        }
    }
    
    return jsonify(client_data), 200


@clients_bp.route('', methods=['POST'])
@jwt_required()
def create_client():
    """Create a new client record"""
    user_id = get_jwt_identity()
    data = request.json
    
    # Validate required fields
    if not data.get('phone_number'):
        return jsonify({"error": "Phone number is required"}), 400
    
    # Validate and normalize phone number
    phone_number = normalize_phone_number(data.get('phone_number'))
    if not validate_phone_number(phone_number):
        return jsonify({"error": "Invalid phone number format. Use E.164 format (e.g., +12125551234)"}), 400
    
    # Check if client already exists
    existing_client = Client.query.filter_by(phone_number=phone_number).first()
    if existing_client:
        return jsonify({"error": "Client with this phone number already exists", "client_id": existing_client.id}), 409
    
    # Create new client
    client = Client(
        phone_number=phone_number,
        name=sanitize_input(data.get('name', '')),
        email=sanitize_input(data.get('email', '')),
        notes=sanitize_input(data.get('notes', '')),
        is_regular=data.get('is_regular', False),
        is_blocked=data.get('is_blocked', False)
    )
    
    db.session.add(client)
    db.session.commit()
    
    return jsonify({
        "message": "Client created successfully",
        "client_id": client.id,
        "client": {
            'id': client.id,
            'phone_number': client.phone_number,
            'name': client.name,
            'email': client.email,
            'is_blocked': client.is_blocked,
            'is_regular': client.is_regular,
            'notes': client.notes,
            'created_at': client.created_at.isoformat(),
            'updated_at': client.updated_at.isoformat(),
        }
    }), 201


@clients_bp.route('/<int:client_id>', methods=['PUT'])
@jwt_required()
def update_client(client_id):
    """Update client information"""
    user_id = get_jwt_identity()
    data = request.json
    
    # Get client
    client = Client.query.get_or_404(client_id)
    
    # Check permission (user must have at least one profile that communicated with this client)
    has_access = db.session.query(Message).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).first() is not None
    
    if not has_access:
        return jsonify({"error": "Unauthorized access to client"}), 403
    
    # Update fields
    if 'name' in data:
        client.name = sanitize_input(data['name'])
    
    if 'email' in data:
        client.email = sanitize_input(data['email'])
    
    if 'notes' in data:
        client.notes = sanitize_input(data['notes'])
    
    if 'is_regular' in data:
        client.is_regular = bool(data['is_regular'])
    
    if 'is_blocked' in data:
        client.is_blocked = bool(data['is_blocked'])
    
    client.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        "message": "Client updated successfully",
        "client": {
            'id': client.id,
            'phone_number': client.phone_number,
            'name': client.name,
            'email': client.email,
            'is_blocked': client.is_blocked,
            'is_regular': client.is_regular,
            'notes': client.notes,
            'created_at': client.created_at.isoformat(),
            'updated_at': client.updated_at.isoformat(),
        }
    }), 200


@clients_bp.route('/<int:client_id>/block', methods=['POST'])
@jwt_required()
def block_client(client_id):
    """Block a client"""
    user_id = get_jwt_identity()
    
    # Get client
    client = Client.query.get_or_404(client_id)
    
    # Check permission
    has_access = db.session.query(Message).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).first() is not None
    
    if not has_access:
        return jsonify({"error": "Unauthorized access to client"}), 403
    
    # Update block status
    client.is_blocked = True
    client.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        "message": "Client blocked successfully",
        "client_id": client.id,
        "is_blocked": True
    }), 200


@clients_bp.route('/<int:client_id>/unblock', methods=['POST'])
@jwt_required()
def unblock_client(client_id):
    """Unblock a client"""
    user_id = get_jwt_identity()
    
    # Get client
    client = Client.query.get_or_404(client_id)
    
    # Check permission
    has_access = db.session.query(Message).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).first() is not None
    
    if not has_access:
        return jsonify({"error": "Unauthorized access to client"}), 403
    
    # Update block status
    client.is_blocked = False
    client.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        "message": "Client unblocked successfully",
        "client_id": client.id,
        "is_blocked": False
    }), 200


@clients_bp.route('/<int:client_id>/messages', methods=['GET'])
@jwt_required()
def get_client_messages(client_id):
    """Get message history with a client"""
    user_id = get_jwt_identity()
    
    # Get client
    client = Client.query.get_or_404(client_id)
    
    # Pagination parameters
    page = int(request.args.get('page', 1))
    per_page = min(int(request.args.get('per_page', 50)), 100)  # Limit max to 100
    
    # Filter by profile if specified
    profile_id = request.args.get('profile_id')
    
    # Base query
    query = Message.query.join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).order_by(desc(Message.timestamp))
    
    # Apply profile filter
    if profile_id:
        query = query.filter(Message.profile_id == profile_id)
    
    # Execute query with pagination
    paginated_messages = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format messages
    messages_data = []
    for message in paginated_messages.items:
        # Get profile name
        profile = Profile.query.get(message.profile_id)
        
        messages_data.append({
            'id': message.id,
            'content': message.content,
            'is_incoming': message.is_incoming,
            'timestamp': message.timestamp.isoformat(),
            'profile_id': message.profile_id,
            'profile_name': profile.name if profile else None,
            'ai_generated': message.ai_generated,
            'is_read': message.is_read,
            'twilio_sid': message.twilio_sid,
            'send_status': message.send_status
        })
    
    return jsonify({
        'client_id': client.id,
        'phone_number': client.phone_number,
        'client_name': client.name,
        'messages': messages_data,
        'pagination': {
            'total': paginated_messages.total,
            'pages': paginated_messages.pages,
            'page': page,
            'per_page': per_page,
            'has_next': paginated_messages.has_next,
            'has_prev': paginated_messages.has_prev
        }
    }), 200


@clients_bp.route('/<int:client_id>/mark_messages_read', methods=['POST'])
@jwt_required()
def mark_messages_read(client_id):
    """Mark all unread messages from a client as read"""
    user_id = get_jwt_identity()
    
    # Get client
    client = Client.query.get_or_404(client_id)
    
    # Get profile ID if specified
    profile_id = request.json.get('profile_id')
    
    # Base query for unread messages
    query = Message.query.join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id,
        Message.is_incoming == True,
        Message.is_read == False
    )
    
    # Apply profile filter if specified
    if profile_id:
        query = query.filter(Message.profile_id == profile_id)
    
    # Get unread messages
    unread_messages = query.all()
    
    # Mark messages as read
    count = 0
    for message in unread_messages:
        message.is_read = True
        count += 1
    
    db.session.commit()
    
    return jsonify({
        "message": f"Marked {count} messages as read",
        "count": count
    }), 200


@clients_bp.route('/search', methods=['GET'])
@jwt_required()
def search_clients():
    """Search for clients by phone number or name"""
    user_id = get_jwt_identity()
    
    # Get search query
    search_query = request.args.get('q', '')
    if not search_query or len(search_query) < 3:
        return jsonify({"error": "Search query must be at least 3 characters"}), 400
    
    # Build query
    clients = Client.query.join(
        Message, Client.phone_number == Message.sender_number
    ).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Profile.user_id == user_id,
        db.or_(
            Client.phone_number.like(f'%{search_query}%'),
            Client.name.ilike(f'%{search_query}%')
        )
    ).distinct().limit(20).all()
    
    # Format results
    results = []
    for client in clients:
        # Get associated profiles
        profiles = db.session.query(Profile.id, Profile.name).join(
            Message, Profile.id == Message.profile_id
        ).filter(
            Message.sender_number == client.phone_number,
            Profile.user_id == user_id
        ).distinct().all()
        
        results.append({
            'id': client.id,
            'phone_number': client.phone_number,
            'name': client.name,
            'is_blocked': client.is_blocked,
            'is_regular': client.is_regular,
            'profiles': [{'id': p.id, 'name': p.name} for p in profiles]
        })
    
    return jsonify({
        'query': search_query,
        'results': results
    }), 200


@clients_bp.route('/add_note', methods=['POST'])
@jwt_required()
def add_client_note():
    """Add a note to a client"""
    user_id = get_jwt_identity()
    data = request.json
    
    # Validate required fields
    if not all([data.get('client_id'), data.get('note')]):
        return jsonify({"error": "Client ID and note are required"}), 400
    
    # Get client
    client = Client.query.get_or_404(data['client_id'])
    
    # Check permission
    has_access = db.session.query(Message).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).first() is not None
    
    if not has_access:
        return jsonify({"error": "Unauthorized access to client"}), 403
    
    # Sanitize note text
    note_text = sanitize_input(data['note'])
    
    # Get existing notes or initialize empty structure
    current_notes = []
    if client.notes and client.notes.strip():
        try:
            current_notes = json.loads(client.notes)
            if not isinstance(current_notes, list):
                current_notes = []
        except (json.JSONDecodeError, ValueError):
            # If notes field contains non-JSON, convert to first note
            if client.notes.strip():
                current_notes = [{
                    'text': client.notes,
                    'timestamp': (client.updated_at or client.created_at).isoformat(),
                    'user_id': user_id
                }]
    
    # Get user info for the note
    user = User.query.get(user_id)
    username = f"{user.first_name} {user.last_name}".strip() if user else "Unknown"
    
    # Add new note
    new_note = {
        'text': note_text,
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': user_id,
        'username': username
    }
    
    current_notes.append(new_note)
    
    # Update client record
    client.notes = json.dumps(current_notes)
    client.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        "message": "Note added successfully",
        "client_id": client.id,
        "notes": current_notes
    }), 200


@clients_bp.route('/<int:client_id>/set_regular', methods=['POST'])
@jwt_required()
def set_client_regular_status(client_id):
    """Set a client as regular/non-regular"""
    user_id = get_jwt_identity()
    data = request.json
    
    # Get client
    client = Client.query.get_or_404(client_id)
    
    # Check permission
    has_access = db.session.query(Message).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).first() is not None
    
    if not has_access:
        return jsonify({"error": "Unauthorized access to client"}), 403
    
    # Update regular status
    is_regular = data.get('is_regular', False)
    client.is_regular = is_regular
    client.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        "message": f"Client {'marked as regular' if is_regular else 'marked as non-regular'} successfully",
        "client_id": client.id,
        "is_regular": client.is_regular
    }), 200


@clients_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_client_stats():
    """Get statistics about clients"""
    user_id = get_jwt_identity()
    
    # Filter by profile if specified
    profile_id = request.args.get('profile_id')
    
    # Build client query
    client_query = db.session.query(
        Client.id
    ).join(
        Message, Client.phone_number == Message.sender_number
    ).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Profile.user_id == user_id
    )
    
    if profile_id:
        client_query = client_query.filter(Profile.id == profile_id)
    
    # Get counts
    total_clients = client_query.distinct().count()
    
    blocked_clients = db.session.query(Client.id).join(
        Message, Client.phone_number == Message.sender_number
    ).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Profile.user_id == user_id,
        Client.is_blocked == True
    )
    
    if profile_id:
        blocked_clients = blocked_clients.filter(Profile.id == profile_id)
    
    blocked_count = blocked_clients.distinct().count()
    
    regular_clients = db.session.query(Client.id).join(
        Message, Client.phone_number == Message.sender_number
    ).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Profile.user_id == user_id,
        Client.is_regular == True
    )
    
    if profile_id:
        regular_clients = regular_clients.filter(Profile.id == profile_id)
    
    regular_count = regular_clients.distinct().count()
    
    # Get most recent client
    recent_client = Client.query.join(
        Message, Client.phone_number == Message.sender_number
    ).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Profile.user_id == user_id
    )
    
    if profile_id:
        recent_client = recent_client.filter(Profile.id == profile_id)
    
    recent_client = recent_client.order_by(desc(Message.timestamp)).first()
    
    recent_client_data = None
    if recent_client:
        recent_client_data = {
            'id': recent_client.id,
            'phone_number': recent_client.phone_number,
            'name': recent_client.name,
            'is_blocked': recent_client.is_blocked,
            'is_regular': recent_client.is_regular
        }
    
    return jsonify({
        'total_clients': total_clients,
        'blocked_clients': blocked_count,
        'regular_clients': regular_count,
        'most_recent_client': recent_client_data
    }), 200


@clients_bp.route('/by_phone/<phone_number>', methods=['GET'])
@jwt_required()
def get_client_by_phone(phone_number):
    """Get client by phone number"""
    user_id = get_jwt_identity()
    
    # Normalize phone number
    normalized_phone = normalize_phone_number(phone_number)
    
    # Get client
    client = Client.query.filter_by(phone_number=normalized_phone).first()
    
    if not client:
        return jsonify({"error": "Client not found"}), 404
    
    # Check permission
    has_access = db.session.query(Message).join(
        Profile, Message.profile_id == Profile.id
    ).filter(
        Message.sender_number == client.phone_number,
        Profile.user_id == user_id
    ).first() is not None
    
    if not has_access:
        return jsonify({"error": "Unauthorized access to client"}), 403
    
    # Format client data
    client_data = {
        'id': client.id,
        'phone_number': client.phone_number,
        'name': client.name,
        'email': client.email,
        'is_blocked': client.is_blocked,
        'is_regular': client.is_regular,
        'notes': client.notes,
        'created_at': client.created_at.isoformat(),
        'updated_at': client.updated_at.isoformat()
    }
    
    return jsonify(client_data), 200