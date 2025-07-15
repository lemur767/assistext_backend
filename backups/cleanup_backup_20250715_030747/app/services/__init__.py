

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





class ServiceManager:
    """Manager class for all services."""
    
   
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
 
