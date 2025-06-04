# app/models/__init__.py
"""Import all models for easy access"""

from .user import User
from .profile import Profile
from .message import Message
from .client import Client
from .auto_reply import AutoReply
from .text_example import TextExample
from .out_of_office_reply import OutOfOfficeReply
from .profile_client import ProfileClient
from .flagged_message import FlaggedMessage
from .ai_model_settings import AIModelSettings
from .analytics import UsageMetrics, SystemHealth

__all__ = [
    'User',
    'Profile', 
    'Message',
    'Client',
    'AutoReply',
    'TextExample',
    'OutOfOfficeReply',
    'ProfileClient',
    'FlaggedMessage',
    'AIModelSettings',
    'UsageMetrics',
    'SystemHealth'
]