# app/services/__init__.py
"""
Services package initialization
Fixed to properly export service functions
"""

def get_billing_service():
    """Lazy import billing service to avoid circular imports"""
    try:
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
    except ImportError:
        return None

# ✅ FIXED: Properly import and return the service instance
def get_signalwire_service():
    """Get SignalWire service instance (FIXED)"""
    from app.services.signalwire_service import get_signalwire_service as _get_service
    return _get_service()

# Service manager for centralized access
class ServiceManager:
    """Manager class for all services."""
    
    @staticmethod
    def get_signalwire_service():
        """Get SignalWire service instance"""
        return get_signalwire_service()
    
    @staticmethod
    def get_billing_service():
        """Get billing service functions."""
        return get_billing_service()

# Export main functions
__all__ = [
    'get_signalwire_service',
    'get_billing_service',
    'ServiceManager'
]
