"""
Business logic services package initialization.
This file imports all service modules for easy access.
"""

# Import service functions without circular imports
def get_message_handler():
    """Lazy import message handler to avoid circular imports"""
    from app.services.message_handler import (
        handle_incoming_message,
        send_response,
        check_flagged_content,
        is_within_business_hours,
        get_conversation_history,
        format_outgoing_message
    )
    return {
        'handle_incoming_message': handle_incoming_message,
        'send_response': send_response,
        'check_flagged_content': check_flagged_content,
        'is_within_business_hours': is_within_business_hours,
        'get_conversation_history': get_conversation_history,
        'format_outgoing_message': format_outgoing_message
    }

def get_ai_service():
    """Lazy import AI service to avoid circular imports"""
    from app.services.ai_service import (
        generate_ai_response,
        get_conversation_history,
        create_system_prompt
    )
    return {
        'generate_ai_response': generate_ai_response,
        'get_conversation_history': get_conversation_history,
        'create_system_prompt': create_system_prompt
    }

def get_billing_service():
    """Lazy import billing service to avoid circular imports"""
    from app.services.billing_service import (
        initialize_stripe,
        create_subscription,
        update_subscription,
        cancel_subscription,
        check_subscription_status,
        create_checkout_session
    )
    return {
        'initialize_stripe': initialize_stripe,
        'create_subscription': create_subscription,
        'update_subscription': update_subscription,
        'cancel_subscription': cancel_subscription,
        'check_subscription_status': check_subscription_status,
        'create_checkout_session': create_checkout_session
    }

def get_analytics_service():
    """Lazy import analytics service to avoid circular imports"""
    from app.services.analytics_service import AnalyticsService
    return AnalyticsService

def get_twilio_service():
    """Lazy import Twilio service to avoid circular imports"""
    from app.services.twilio_service import TwilioService
    return TwilioService

class ServiceManager:
    """Manager class for all services."""
    
    @staticmethod
    def get_analytics():
        """Get the analytics service instance."""
        analytics_cls = get_analytics_service()
        return analytics_cls()
    
    @staticmethod
    def get_message_handler():
        """Get message handler functions."""
        return get_message_handler()
    
    @staticmethod
    def get_ai_service():
        """Get AI service functions."""
        return get_ai_service()
    
    @staticmethod
    def get_billing_service():
        """Get billing service functions."""
        return get_billing_service()
    
    @staticmethod
    def get_twilio_service(user=None):
        """Get Twilio service instance."""
        twilio_cls = get_twilio_service()
        return twilio_cls(user)
