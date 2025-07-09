# app/models/__init__.py

from app.extensions import db

# Import current models (post-consolidation)
from .user import User
from .message import Message
from .client import Client

# Optional models
try:
    from .billing import Subscription
except ImportError:
    Subscription = None
try:
    from .billing import SubscriptionPlan
except ImportError:
    SubscriptionPlan = None
try:
    from .signalwire import (
        SignalWireAccount,
        SignalWirePhoneNumber
    )
except ImportError:
    SignalWireAccount = None
    SignalWirePhoneNumber = None
try:
    from .message import FlaggedMessage
except ImportError:
    FlaggedMessage = None

# Export models
__all__ = [
    'db',
    'User',
    'Message', 
    'Client'
]


if SubscriptionPlan:
    __all__.append('SubscriptionPlan')
if Subscription:
    __all__.append('Subscription')
if FlaggedMessage:
    __all__.append('FlaggedMessage')