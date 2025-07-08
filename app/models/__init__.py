# app/models/__init__.py


from app.extensions import db

# Import all models to ensure they're registered with SQLAlchemy
from .user import User, user_clients
from .client import Client
from .message import Message, FlaggedMessage



# Export models for easy importing
__all__ = [
    'db',
    'User',
    'Client', 
    'Message',
    'FlaggedMessage',
    'user_clients'
]

