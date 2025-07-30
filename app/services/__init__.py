"""
Clean Services Package for AssisText
Modern 3-layer service architecture

Services:
- BillingService: Billing operations (subscriptions, usage, invoices, payments)
- MessagingService: Messaging operations (SMS, AI responses, clients, templates)  
- IntegrationService: External integrations (SignalWire, LLM, Stripe, webhooks)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# SERVICE IMPORTS
# =============================================================================

from .billing_service import BillingService
from .messaging_service import MessagingService
from .integration_service import (
    IntegrationService, 
    get_integration_service as _get_unified_integration_service,
    send_sms_message,
    generate_ai_response,
    create_customer_subscription,
    process_sms_conversation,
    check_all_integrations
)

# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_billing_service: Optional[BillingService] = None
_messaging_service: Optional[MessagingService] = None
_integration_service: Optional[IntegrationService] = None

def get_billing_service() -> BillingService:
    """Get billing service singleton instance"""
    global _billing_service
    
    if _billing_service is None:
        _billing_service = BillingService()
        logger.info("✅ BillingService initialized")
    
    return _billing_service

def get_messaging_service() -> MessagingService:
    """Get messaging service singleton instance"""
    global _messaging_service
    
    if _messaging_service is None:
        _messaging_service = MessagingService()
        logger.info("✅ MessagingService initialized")
    
    return _messaging_service

def get_integration_service() -> IntegrationService:
    """Get unified integration service singleton instance"""
    global _integration_service
    
    if _integration_service is None:
        _integration_service = _get_unified_integration_service()
        logger.info("✅ Unified IntegrationService initialized")
    
    return _integration_service

# =============================================================================
# SERVICE MANAGER
# =============================================================================

class ServiceManager:
    """Centralized service manager for easy access to all services"""
    
    @staticmethod
    def get_billing_service() -> BillingService:
        """Get billing service instance"""
        return get_billing_service()
    
    @staticmethod
    def get_messaging_service() -> MessagingService:
        """Get messaging service instance"""
        return get_messaging_service()
    
    @staticmethod
    def get_integration_service() -> IntegrationService:
        """Get integration service instance"""
        return get_integration_service()
    
    @staticmethod
    def get_all_services() -> dict:
        """Get all service instances as a dictionary"""
        return {
            'billing': get_billing_service(),
            'messaging': get_messaging_service(),
            'integration': get_integration_service()
        }
    
    @staticmethod
    def check_services_health() -> dict:
        """Check health status of all services"""
        health_status = {}
        
        try:
            billing_svc = get_billing_service()
            health_status['billing'] = 'healthy'
        except Exception as e:
            health_status['billing'] = f'error: {str(e)}'
        
        try:
            messaging_svc = get_messaging_service()
            health_status['messaging'] = 'healthy'
        except Exception as e:
            health_status['messaging'] = f'error: {str(e)}'
        
        try:
            integration_svc = get_integration_service()
            # Use the integration service's built-in health check
            integration_health = integration_svc.get_all_service_status()
            health_status['integration'] = integration_health['overall_status']
        except Exception as e:
            health_status['integration'] = f'error: {str(e)}'
        
        health_status['overall'] = 'healthy' if all(
            'healthy' in str(status) for status in health_status.values()
        ) else 'degraded'
        
        return health_status

# =============================================================================
# INITIALIZATION HELPERS
# =============================================================================

def initialize_all_services() -> dict:
    """Initialize all services and return status"""
    results = {}
    
    try:
        billing_svc = get_billing_service()
        results['billing'] = 'initialized'
    except Exception as e:
        results['billing'] = f'error: {str(e)}'
    
    try:
        messaging_svc = get_messaging_service()
        results['messaging'] = 'initialized'
    except Exception as e:
        results['messaging'] = f'error: {str(e)}'
    
    try:
        integration_svc = get_integration_service()
        results['integration'] = 'initialized'
    except Exception as e:
        results['integration'] = f'error: {str(e)}'
    
    # Log results
    success_count = sum(1 for status in results.values() if status == 'initialized')
    total_count = len(results)
    
    if success_count == total_count:
        logger.info(f"✅ All {total_count} services initialized successfully")
    else:
        logger.warning(f"⚠️ Only {success_count}/{total_count} services initialized successfully")
        for service, status in results.items():
            if status != 'initialized':
                logger.error(f"❌ {service} service: {status}")
    
    return results

def reset_service_instances():
    """Reset all service instances (useful for testing)"""
    global _billing_service, _messaging_service, _integration_service
    
    _billing_service = None
    _messaging_service = None
    _integration_service = None
    
    logger.info("🔄 All service instances reset")

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Service classes
    'BillingService',
    'MessagingService', 
    'IntegrationService',
    
    # Service getters (primary interface)
    'get_billing_service',
    'get_messaging_service',
    'get_integration_service',
    
    # Service manager
    'ServiceManager',
    
    # Initialization helpers
    'initialize_all_services',
    'reset_service_instances',
    
    # Integration service convenience functions
    'send_sms_message',
    'generate_ai_response', 
    'create_customer_subscription',
    'process_sms_conversation',
    'check_all_integrations'
]

# =============================================================================
# PACKAGE INITIALIZATION
# =============================================================================

logger.info("📦 Clean services package loaded - no legacy code!")
logger.info("✅ Modern service architecture ready")