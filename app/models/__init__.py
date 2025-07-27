from app.extensions import db

# =============================================================================
# IMPORT MODELS BY DOMAIN
# =============================================================================

# User Management Domain
from .user import User

# Billing Domain - All billing-related models in one place
from .billing import (
    SubscriptionPlan, 
    Subscription, 
    Invoice, 
    InvoiceItem,
    PaymentMethod, 
    Payment, 
    UsageRecord
)

# Messaging Domain - All messaging-related models in one place
from .messaging import (
    Client, 
    Message, 
    MessageTemplate, 
    ActivityLog, 
    NotificationLog
)

# =============================================================================
# EXPORT MODELS - ORGANIZED BY DOMAIN
# =============================================================================

__all__ = [
    # Core
    'db',
    
    # User Management
    'User',
    
    # Billing Domain
    'SubscriptionPlan', 
    'Subscription', 
    'Invoice', 
    'InvoiceItem',
    'PaymentMethod', 
    'Payment', 
    'UsageRecord',
    
    # Messaging Domain
    'Client', 
    'Message', 
    'MessageTemplate', 
    'ActivityLog', 
    'NotificationLog'
]

# =============================================================================
# DOMAIN GROUPINGS (for convenience)
# =============================================================================

# Billing models grouped together
BILLING_MODELS = [
    SubscriptionPlan, Subscription, Invoice, InvoiceItem,
    PaymentMethod, Payment, UsageRecord
]

# Messaging models grouped together  
MESSAGING_MODELS = [
    Client, Message, MessageTemplate, ActivityLog, NotificationLog
]

# All models
ALL_MODELS = [User] + BILLING_MODELS + MESSAGING_MODELS

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_billing_models():
    """Get all billing-related models"""
    return BILLING_MODELS

def get_messaging_models():
    """Get all messaging-related models"""
    return MESSAGING_MODELS

def get_all_models():
    """Get all models"""
    return ALL_MODELS 
# =============================================================================
# IMPORT MODELS BY DOMAIN
# =============================================================================

# User Management Domain
from .user import User

# Billing Domain - All billing-related models in one place
from .billing import (
    SubscriptionPlan, 
    Subscription, 
    Invoice, 
    InvoiceItem,
    PaymentMethod, 
    Payment, 
    UsageRecord
)

# Messaging Domain - All messaging-related models in one place
from .messaging import (
    Client, 
    Message, 
    MessageTemplate, 
    ActivityLog, 
    NotificationLog
)

# =============================================================================
# EXPORT MODELS - ORGANIZED BY DOMAIN
# =============================================================================

__all__ = [
    # Core
    'db',
    
    # User Management
    'User',
    
    # Billing Domain
    'SubscriptionPlan', 
    'Subscription', 
    'Invoice', 
    'InvoiceItem',
    'PaymentMethod', 
    'Payment', 
    'UsageRecord',
    
    # Messaging Domain
    'Client', 
    'Message', 
    'MessageTemplate', 
    'ActivityLog', 
    'NotificationLog'
]

# =============================================================================
# DOMAIN GROUPINGS (for convenience)
# =============================================================================

# Billing models grouped together
BILLING_MODELS = [
    SubscriptionPlan, Subscription, Invoice, InvoiceItem,
    PaymentMethod, Payment, UsageRecord
]

# Messaging models grouped together  
MESSAGING_MODELS = [
    Client, Message, MessageTemplate, ActivityLog, NotificationLog
]

# All models
ALL_MODELS = [User] + BILLING_MODELS + MESSAGING_MODELS

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_billing_models():
    """Get all billing-related models"""
    return BILLING_MODELS

def get_messaging_models():
    """Get all messaging-related models"""
    return MESSAGING_MODELS

def get_all_models():
    """Get all models"""
    return ALL_MODELS