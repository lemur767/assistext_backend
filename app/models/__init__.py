from app.extensions import db
from .user import User
from .message import Message
from .client import Client
from .billing import (
    Subscription, 
    SubscriptionPlan, 
    Invoice, 
    InvoiceItem, 
    PaymentMethod
)
from .auto_reply import AutoReply
from .text_example import TextExample
from .ai_model_settings import AIModelSettings
from .flagged_message import FlaggedMessage


# Export only what we're actually importing
__all__ = [
    'User',
    'Message',
    'Client',
    'Subscription',
    'SubscriptionPlan',
    'AutoReply',
    'TextExample',
    'AIModelSettings',
    'FlaggedMessage',
    'Invoice',
    'InvoiceItem',
    'PaymentMethod'
    
]


def clear_metadata_if_needed():
    """Clear metadata if there are table conflicts"""
    if hasattr(db.metadata, '_tables'):
        # Only clear if we detect a conflict
        table_names = list(db.metadata.tables.keys())
        if len(table_names) != len(set(table_names)):
            print("⚠️  Detected duplicate table names, clearing metadata...")
            db.metadata.clear()

# Call this during import
clear_metadata_if_needed()

