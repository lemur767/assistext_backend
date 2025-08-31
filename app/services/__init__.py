
# Service Factory Pattern
def get_user_service():
    from .user_service import UserService
    return UserService()

def get_billing_service():
    from .billing_service import BillingService
    return BillingService()

def get_messaging_service():
    from .messaging_service import MessagingService
    return MessagingService()

def get_sms_conversation_service():
    from .sms_conversation_service import SMSConversationService
    return SMSConversationService()


__all__ = [
    "get_user_service",
    "get_billing_service",
    "get_messaging_service",
    "get_sms_conversation_service",
]
