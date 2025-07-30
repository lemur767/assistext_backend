

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
"""
Consolidated Services Package
Clean 3-layer service architecture

Services are organized by business domain:
- BillingService: ALL billing operations (subscriptions, usage, invoices, payments)
- MessagingService: ALL messaging operations (SMS, AI responses, clients, templates)
- IntegrationService: ALL external integrations (SignalWire, LLM, Stripe, webhooks)
"""

# =============================================================================
# IMPORT CONSOLIDATED SERVICES
# =============================================================================

from .billing_service import BillingService
from .messaging_service import MessagingService
from .integration_service import IntegrationService

# =============================================================================
# SERVICE INSTANCES (Singleton Pattern)
# =============================================================================

# Create singleton instances for global use
_billing_service = None
_messaging_service = None
_integration_service = None

def get_billing_service() -> BillingService:
    """Get billing service singleton instance"""
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService()
    return _billing_service

def get_messaging_service() -> MessagingService:
    """Get messaging service singleton instance"""
    global _messaging_service
    if _messaging_service is None:
        _messaging_service = MessagingService()
    return _messaging_service

def get_integration_service() -> IntegrationService:
    """Get integration service singleton instance"""
    global _integration_service
    if _integration_service is None:
        _integration_service = IntegrationService()
    return _integration_service

# =============================================================================
# BACKWARDS COMPATIBILITY HELPERS
# =============================================================================

# For gradual migration from old service structure
def get_legacy_service_mapping():
    """
    Mapping of old service functions to new consolidated services
    Use this during migration to update imports gradually
    """
    billing_svc = get_billing_service()
    messaging_svc = get_messaging_service()
    integration_svc = get_integration_service()
    
    return {
        # Billing operations
        'create_subscription': billing_svc.create_subscription,
        'cancel_subscription': billing_svc.cancel_subscription,
        'track_usage': billing_svc.track_usage,
        'check_usage_limits': billing_svc.check_usage_limits,
        'generate_invoice': billing_svc.generate_invoice,
        'process_payment': billing_svc.process_payment,
        
        # Messaging operations
        'send_sms': messaging_svc.send_sms,
        'process_incoming_message': messaging_svc.process_incoming_message,
        'get_conversation_history': messaging_svc.get_client_conversation,
        'create_template': messaging_svc.create_template,
        'send_bulk_sms': messaging_svc.send_bulk_sms,
        
        # Integration operations
        'setup_signalwire': integration_svc.setup_signalwire_account,
        'purchase_phone_number': integration_svc.purchase_phone_number,
        'setup_stripe_customer': integration_svc.setup_stripe_customer,
        'add_payment_method': integration_svc.add_payment_method,
        'test_service_connections': integration_svc.get_all_service_status,
    }

# =============================================================================
# EXPORT SERVICES AND FUNCTIONS
# =============================================================================

__all__ = [
    # Service classes
    'BillingService',
    'MessagingService', 
    'IntegrationService',
    
    # Service getters
    'get_billing_service',
    'get_messaging_service',
    'get_integration_service',
    
    # Backwards compatibility
    'get_legacy_service_mapping'
]

# =============================================================================
# SERVICE HEALTH CHECK
# =============================================================================

def check_all_services_health():
    """Check health of all services"""
    try:
        billing_svc = get_billing_service()
        messaging_svc = get_messaging_service()
        integration_svc = get_integration_service()
        
        return {
            'billing_service': 'healthy',
            'messaging_service': 'healthy', 
            'integration_service': 'healthy',
            'all_services_loaded': True
        }
    except Exception as e:
        return {
            'error': str(e),
            'all_services_loaded': False
        }

# =============================================================================
# MIGRATION HELPERS
# =============================================================================

def migrate_from_old_services():
    """
    Helper function to assist with migration from old service structure
    Returns mapping of old imports to new service methods
    """
    return {
        'OLD_IMPORTS_TO_REPLACE': {
            'from app.services.billing_service import create_subscription': 
                'from app.services import get_billing_service; billing_svc = get_billing_service(); billing_svc.create_subscription',
            
            'from app.services.sms_service import send_sms':
                'from app.services import get_messaging_service; messaging_svc = get_messaging_service(); messaging_svc.send_sms',
            
            'from app.services.ai_service import generate_ai_response':
                'from app.services import get_messaging_service; messaging_svc = get_messaging_service(); messaging_svc._generate_and_send_ai_response',
            
            'from app.services.subscription_service import SubscriptionService':
                'from app.services import get_billing_service; billing_svc = get_billing_service()',
        },
        
        'FUNCTION_MAPPINGS': {
            'billing_service.create_subscription': 'billing_service.create_subscription',
            'subscription_service.create_subscription': 'billing_service.create_subscription',
            'usage_tracker.track_usage': 'billing_service.track_usage',
            'invoice_generator.generate_invoice': 'billing_service.generate_invoice',
            'sms_service.send_sms': 'messaging_service.send_sms',
            'message_handler.process_incoming_message': 'messaging_service.process_incoming_message',
            'ai_service.generate_response': 'messaging_service._generate_and_send_ai_response',
        }
    }

