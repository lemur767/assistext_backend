from .user_service import UserService
from .billing_service import BillingService
from .messaging_service import MessagingService
from .signalwire_service import SignalWireService
from .usage_service import UsageService
from .notification_service import NotificationService

# Service Factory Pattern
def get_user_service():
    return UserService()

def get_billing_service():
    return BillingService()

def get_messaging_service():
    return MessagingService()

def get_signalwire_service():
    return SignalWireService()

def get_usage_service():
    return UsageService()

def get_notification_service():
    return NotificationService()
