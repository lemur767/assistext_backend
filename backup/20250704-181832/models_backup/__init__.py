# app/models/__init__.py
from app.extensions import db

# Import all models to ensure they are registered with SQLAlchemy
from .user import User
from .profile import Profile
from .message import Message
from .client import Client

# Import all billing models from consolidated billing.py file
from .billing import (
    Subscription, 
    SubscriptionPlan, 
    Invoice, 
    InvoiceItem, 
    PaymentMethod
)

from .auto_reply import AutoReply
from .text_example import TextExample
from .out_of_office_reply import OutOfOfficeReply
from .ai_model_settings import AIModelSettings
from .flagged_message import FlaggedMessage

# Export all models
__all__ = [
    'User',
    'Profile', 
    'Message',
    'Client',
    'Subscription',
    'SubscriptionPlan',
    'Invoice',
    'InvoiceItem',
    'PaymentMethod',
    'AutoReply',
    'TextExample',
    'OutOfOfficeReply',
    'AIModelSettings',
    'FlaggedMessage'
]
