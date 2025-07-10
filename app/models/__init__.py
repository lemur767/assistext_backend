from app.extensions import db

# Import models in dependency order (least dependent first)
from .user import User
from .subscription import Subscription, SubscriptionPlan
from .message import Message
from .client import Client

# Import billing models - CONSOLIDATE INTO ONE FILE
from .billing import Invoice, InvoiceItem, PaymentMethod, Payment
from .credit_transaction import CreditTransaction
from .billing_settings import BillingSettings
from .usage import UseageRecord

# Import utility models
from .utility import ActivityLog, NotificationLog, MessageTemplate

# DO NOT import models with extend_existing=True here
# They should be imported only when needed

# Export only essential models
__all__ = [
    'db',
    'User',
    'Subscription', 
    'SubscriptionPlan',
    'Message',
    'Client',
    'Invoice',
    'InvoiceItem', 
    'PaymentMethod',
    'Payment',
    'CreditTransaction',
    'BillingSettings',
    'UseageRecord',
    'ActivityLog',
    'NotificationLog',
    'MessageTemplate'
]