# app/models/__init__.py
"""
Fixed model imports to prevent SQLAlchemy mapper errors
Import order matters - import base models first, then related models
"""

from app.extensions import db

# STEP 1: Import core models first (no relationships)
from .user import User

# STEP 2: Import models that only depend on core models
# Only import Profile if you need it for registration
# Comment out for now if causing issues
# from .profile import Profile

# STEP 3: Comment out all other models until registration works
# Then add them back one by one

# Temporarily disable all other imports to isolate the issue:
"""
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
from .out_of_office_reply import OutOfOfficeReply
from .ai_model_settings import AIModelSettings
from .flagged_message import FlaggedMessage
"""

# Export only what we're actually importing
__all__ = [
    'User',
    # 'Profile',  # Add back when ready
]

# Clear any existing metadata tables that might be causing conflicts
# This helps with the "table already defined" error
def clear_metadata_if_needed():
    """Clear metadata if there are table conflicts"""
    if hasattr(db.metadata, '_tables'):
        # Only clear if we detect a conflict
        table_names = list(db.metadata.tables.keys())
        if len(table_names) != len(set(table_names)):
            print("⚠️  Detected duplicate table names, clearing metadata...")
            db.metadata.clear()

# Call this during import
clear_metadata_if_needed()# app/models/__init__.py
"""
Fixed model imports to prevent SQLAlchemy mapper errors
Import order matters - import base models first, then related models
"""

from app.extensions import db

# STEP 1: Import core models first (no relationships)
from .user import User

# STEP 2: Import models that only depend on core models
# Only import Profile if you need it for registration
# Comment out for now if causing issues
# from .profile import Profile

# STEP 3: Comment out all other models until registration works
# Then add them back one by one

# Temporarily disable all other imports to isolate the issue:
"""
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
from .out_of_office_reply import OutOfOfficeReply
from .ai_model_settings import AIModelSettings
from .flagged_message import FlaggedMessage
"""

# Export only what we're actually importing
__all__ = [
    'User',
    # 'Profile',  # Add back when ready
]

# Clear any existing metadata tables that might be causing conflicts
# This helps with the "table already defined" error
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
