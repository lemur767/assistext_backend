

# Import SignalWire helpers
try:
    from app.services.signalwire_service import (
        get_signalwire_client,
        send_sms,
        validate_signalwire_request,
        get_phone_number_info,
        format_phone_number,
        get_available_phone_numbers,
        purchase_phone_number,
        configure_webhook
    )
    
    SIGNALWIRE_AVAILABLE = True
except ImportError as e:
    SIGNALWIRE_AVAILABLE = False
    print(f"Warning: SignalWire helpers not available: {e}")


# Import Stripe client
try:
    from .stripe_client import (
        StripeClient,
        StripeSubscriptionError,
        StripeWebhookError,
        handle_stripe_errors
    )
    
    STRIPE_AVAILABLE = True
except ImportError as e:
    STRIPE_AVAILABLE = False
    print(f"Warning: Stripe client not available: {e}")

# Security helpers (if they exist)
try:
    from .security import *
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False

# Export all available utilities
__all__ = []

# Add SignalWire exports
if SIGNALWIRE_AVAILABLE:
    __all__.extend([
        'get_signalwire_client',
        'send_sms', 
        'validate_signalwire_request',
        'get_phone_number_info',
        'format_phone_number',
        'get_available_phone_numbers',
        'purchase_phone_number',
        'configure_webhook'
    ])


# Add Stripe exports
if STRIPE_AVAILABLE:
    __all__.extend([
        'StripeClient',
        'StripeSubscriptionClient',
        'StripeSubscriptionError',
        'StripeWebhookError',
        'handle_stripe_errors'
    ])

# Convenience functions that work regardless of backend
def send_message(from_number, to_number, body):
    """
    Send SMS message using available SMS service
    """
    if SIGNALWIRE_AVAILABLE:
        return send_sms(from_number, to_number, body)
    else:
        raise RuntimeError("No SMS service available")



def get_stripe_client():
    """
    Get Stripe client if available
    """
    if STRIPE_AVAILABLE:
        return StripeClient()
    else:
        raise RuntimeError("Stripe client not available")