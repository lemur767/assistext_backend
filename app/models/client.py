from app.extensions import db
from datetime import datetime
from typing import Dict, Any, Optional

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Client information
    name = db.Column(db.String(100))
    email = db.Column(db.String(255))
    notes = db.Column(db.Text)
    
    # Contact metadata
    first_contact = db.Column(db.DateTime, default=datetime.utcnow)
    last_contact = db.Column(db.DateTime, default=datetime.utcnow)
    total_messages = db.Column(db.Integer, default=0)
    
    # Client categorization
    client_type = db.Column(db.String(50), default='new')  # 'new', 'regular', 'vip', 'blocked'
    source = db.Column(db.String(50))  # 'referral', 'website', 'social', etc.
    
    # Status flags
    is_active = db.Column(db.Boolean, default=True)
    is_blocked = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships (UPDATED: Many-to-many with users instead of profiles)
    users = db.relationship('User', secondary='user_clients', back_populates='clients', lazy='dynamic')
    messages = db.relationship('Message', back_populates='client', lazy='dynamic')
    
    def __init__(self, **kwargs):
        super(Client, self).__init__(**kwargs)
        # Auto-generate name if not provided
        if not self.name and self.phone_number:
            self.name = f"Client {self.phone_number[-4:]}"
    
    @property
    def display_name(self) -> str:
        """Get display name for client"""
        if self.name:
            return self.name
        return f"Client {self.phone_number[-4:]}" if self.phone_number else "Unknown Client"
    
    @property
    def is_new_client(self) -> bool:
        """Check if client is new (less than 7 days old)"""
        week_ago = datetime.utcnow() - timedelta(days=7)
        return self.first_contact > week_ago
    
    @property
    def last_message_date(self) -> Optional[datetime]:
        """Get date of last message"""
        last_message = self.messages.order_by(Message.timestamp.desc()).first()
        return last_message.timestamp if last_message else None
    
    def update_contact_info(self, name: str = None, email: str = None, notes: str = None) -> None:
        """Update client contact information"""
        if name is not None:
            self.name = name
        if email is not None:
            self.email = email
        if notes is not None:
            self.notes = notes
        self.updated_at = datetime.utcnow()
    
    def block_client(self, reason: str = None) -> None:
        """Block client"""
        self.is_blocked = True
        self.is_active = False
        if reason and self.notes:
            self.notes += f"\n[BLOCKED: {reason}]"
        elif reason:
            self.notes = f"[BLOCKED: {reason}]"
        self.updated_at = datetime.utcnow()
    
    def unblock_client(self) -> None:
        """Unblock client"""
        self.is_blocked = False
        self.is_active = True
        self.updated_at = datetime.utcnow()
    
    def update_last_contact(self) -> None:
        """Update last contact timestamp"""
        self.last_contact = datetime.utcnow()
        self.total_messages += 1
    
    def get_message_history(self, user_id: int, limit: int = 50) -> list:
        """Get message history with specific user"""
        from app.models.message import Message
        return Message.query.filter(
            Message.client_id == self.id,
            Message.user_id == user_id
        ).order_by(Message.timestamp.desc()).limit(limit).all()
    
    def get_user_relationship(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get relationship details with specific user"""
        from app.models.user import user_clients
        
        relationship = db.session.query(user_clients).filter(
            user_clients.c.user_id == user_id,
            user_clients.c.client_id == self.id
        ).first()
        
        if relationship:
            return {
                'notes': relationship.notes,
                'is_blocked': relationship.is_blocked,
                'is_favorite': relationship.is_favorite,
                'created_at': relationship.created_at
            }
        return None
    
    def update_user_relationship(self, user_id: int, notes: str = None, 
                               is_blocked: bool = None, is_favorite: bool = None) -> None:
        """Update relationship with specific user"""
        from app.models.user import user_clients
        
        # Check if relationship exists
        relationship = db.session.query(user_clients).filter(
            user_clients.c.user_id == user_id,
            user_clients.c.client_id == self.id
        ).first()
        
        if relationship:
            # Update existing relationship
            update_values = {}
            if notes is not None:
                update_values['notes'] = notes
            if is_blocked is not None:
                update_values['is_blocked'] = is_blocked
            if is_favorite is not None:
                update_values['is_favorite'] = is_favorite
            
            if update_values:
                db.session.execute(
                    user_clients.update().where(
                        db.and_(
                            user_clients.c.user_id == user_id,
                            user_clients.c.client_id == self.id
                        )
                    ).values(**update_values)
                )
        else:
            # Create new relationship
            db.session.execute(
                user_clients.insert().values(
                    user_id=user_id,
                    client_id=self.id,
                    notes=notes or '',
                    is_blocked=is_blocked or False,
                    is_favorite=is_favorite or False,
                    created_at=datetime.utcnow()
                )
            )
        
        db.session.commit()
    
    def to_dict(self, user_id: int = None, include_stats: bool = False) -> Dict[str, Any]:
        """Convert client to dictionary"""
        data = {
            'id': self.id,
            'phone_number': self.phone_number,
            'name': self.name,
            'display_name': self.display_name,
            'email': self.email,
            'notes': self.notes,
            'first_contact': self.first_contact.isoformat(),
            'last_contact': self.last_contact.isoformat(),
            'total_messages': self.total_messages,
            'client_type': self.client_type,
            'source': self.source,
            'is_active': self.is_active,
            'is_blocked': self.is_blocked,
            'is_verified': self.is_verified,
            'is_new_client': self.is_new_client,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        # Include user-specific relationship data if user_id provided
        if user_id:
            relationship = self.get_user_relationship(user_id)
            if relationship:
                data['user_relationship'] = relationship
        
        # Include statistics if requested
        if include_stats:
            data['stats'] = {
                'total_messages': self.total_messages,
                'last_message_date': self.last_message_date.isoformat() if self.last_message_date else None,
                'days_since_last_contact': (datetime.utcnow() - self.last_contact).days
            }
        
        return data
    
    @classmethod
    def find_or_create(cls, phone_number: str, user_id: int, name: str = None) -> 'Client':
        """Find existing client or create new one"""
        client = cls.query.filter_by(phone_number=phone_number).first()
        
        if not client:
            # Create new client
            client = cls(
                phone_number=phone_number,
                name=name or f"Client {phone_number[-4:]}",
                first_contact=datetime.utcnow(),
                last_contact=datetime.utcnow()
            )
            db.session.add(client)
            db.session.flush()  # Get the ID
            
            # Create user-client relationship
            client.update_user_relationship(user_id)
        else:
            # Update last contact
            client.update_last_contact()
            
            # Ensure user-client relationship exists
            if not client.get_user_relationship(user_id):
                client.update_user_relationship(user_id)
        
        return client
    
    @classmethod
    def get_user_clients(cls, user_id: int, active_only: bool = True, 
                        search: str = None, limit: int = None) -> list:
        """Get all clients for a specific user"""
        from app.models.user import user_clients
        
        query = db.session.query(cls).join(
            user_clients, cls.id == user_clients.c.client_id
        ).filter(user_clients.c.user_id == user_id)
        
        if active_only:
            query = query.filter(cls.is_active == True)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    cls.phone_number.ilike(search_term),
                    cls.name.ilike(search_term),
                    cls.email.ilike(search_term)
                )
            )
        
        query = query.order_by(cls.last_contact.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()


# For backwards compatibility, keep import path working
from datetime import timedelta