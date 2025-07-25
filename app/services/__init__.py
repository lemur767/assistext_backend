



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

def get_signalwire_service():
    """Lazy import Signalwire service to avoid circular imports"""
    from app.services.signalwire_service import SignalWireClient, SignalWireService, SignalWireServiceError, _signalwire_service
    return { SignalWireClient, SignalWireService, SignalWireServiceError, _signalwire_service }

# Add to ServiceManager
class ServiceManager:
    """Manager class for all services."""
    
    @staticmethod
    def get_signalwire_service():
        """Get SMS service instance."""
        return get_signalwire_service()
    
    @staticmethod
    def get_billing_service():
        """Get billing service functions."""
        return get_billing_service()



